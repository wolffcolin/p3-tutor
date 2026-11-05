"""`p3 score <run-dir>`: the objective checks of one bench run, written to <run>/score.json.

    p3 score <run-dir> [--offline] [--no-model]

Deterministic checks (always):

- teach: the one new lessons/*.html is self-contained (no remote script or stylesheet; remote images
  are a warning), declares its minutes and objective, and its length: visible words / 150 is a rough
  reading-time estimate, and `length_ok` means 0.6 to 1.5 times the minutes requested. Every external
  link is fetched (unless --offline): 2xx or 3xx is ok, 404 or 410 dead, anything else unknown.
- quiz: the new quizzes/*.json and its keys/*.json follow FORMATS.md, and every item's objective exists.
- grade: each grades/*-sN.json against the topic's grading.json: verdict agreement, the false-wrong
  rate (right answers marked otherwise), misconception hits and feedback present.
- tutor: whether a reply gives away a quiz answer (the leak check). A probe with no reply (a
  timeout, an error) has nothing to check, so its leak is unknown, not "no leak", and it is not met.

A failed job counts against the config: no lesson is 0 facts correct and no quiz and key 0 key
agreement (with model scoring on), and a missing grades file disagrees on every item. A link that
could not be checked only because this Python cannot verify certificates leaves the dead links
unknown, with a warning. A model call that fails for a reason outside the run (claude.InfraError: a
usage limit, a sign-in problem) stops the scoring and writes no score.json.

Model-scored checks (unless --no-model), each one `claude -p` call with no tools:

- teach: the judge (bench/judge/teach.md) says which of the objective's facts the lesson states and
  states correctly, which listed misconceptions it asserts, and how well its level fits the learner.
- quiz: two solvers (bench/judge/solver.md) answer the items without the key; the key agreement is the
  share of scorable items where the Sonnet solver agrees with the key.
- tutor: the judge (bench/judge/tutor.md) says whether each reply does what a good tutor does.

A judge prompt file can name its inputs as {{placeholders}} (teach: objective, facts, misconceptions,
learner_summary, lesson; tutor: learner_summary, probe, expected, reply; solver: items), and then it
must name exactly those; when it has none, the inputs follow the prompt under a "## Input" heading.
"""

from __future__ import annotations

import json
import math
import re
import ssl
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable

from p3 import claude, topic, util
from p3.claude import COST_LABEL
from p3.util import P3Error

JUDGE_MODEL = "claude-sonnet-5-5"
SOLVER_MODELS = ("claude-sonnet-5-5", "claude-haiku-5-5")
WORDS_PER_MINUTE = 150
LENGTH_OK = (0.6, 1.5)
LINK_TIMEOUT_S = 10
CALL_TIMEOUT_S = 600
MAX_PARALLEL_CALLS = 4
DEFAULT_REL_TOLERANCE = 0.01
MIN_OPTION_TEXT = 12
MIN_SHORT_ANSWER = 4
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
# Certificate bundles to try when this Python cannot verify a site's certificate on its own (the
# python.org installer on macOS until "Install Certificates.command" has run); macOS ships the first.
CERT_FILES = ("/etc/ssl/cert.pem",)
CERTIFICATE = "certificate"
JOBS = ("teach", "quiz", "grade", "tutor")
VERDICTS = topic.VERDICTS
ITEM_TYPES = topic.ITEM_TYPES

Ask = Callable[[str, str], claude.Reply]
Opener = Callable[[str, float], int]


# ---- lessons ----

SKIP_TAGS = frozenset({"script", "style", "template", "title"})
BLOCK_TAGS = frozenset({
    "p", "div", "section", "article", "header", "footer", "main", "aside", "nav", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "ul", "ol", "dl", "dt", "dd", "tr", "td", "th", "table", "pre", "blockquote", "figure", "figcaption", "br", "hr",
    "details", "summary",
})  # fmt: skip
REMOTE_RE = re.compile(r"^\s*(?:https?:)?//", re.IGNORECASE)
EXTERNAL_RE = re.compile(r"^\s*https?://", re.IGNORECASE)
CSS_IMPORT_RE = re.compile(r"@import\s+(?:url\(\s*)?['\"]?\s*((?:https?:)?//[^'\")\s;]+)", re.IGNORECASE)
LESSON_NAME_RE = re.compile(r"^lessons/\d{4}-[a-z0-9-]+\.html$")


class LessonParser(HTMLParser):
    """Collects a lesson's visible text, meta tags, remote resources and external links."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip: list[str] = []
        self.parts: list[str] = []
        self.meta: dict[str, str] = {}
        self.remote_scripts: list[str] = []
        self.remote_stylesheets: list[str] = []
        self.remote_images: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta" and a.get("name"):
            self.meta[a["name"].strip().lower()] = a.get("content", "").strip()
        elif tag == "script" and REMOTE_RE.match(a.get("src", "")):
            self.remote_scripts.append(a["src"].strip())
        elif tag == "link" and "stylesheet" in a.get("rel", "").lower().split() and REMOTE_RE.match(a.get("href", "")):
            self.remote_stylesheets.append(a["href"].strip())
        elif tag == "img" and REMOTE_RE.match(a.get("src", "")):
            self.remote_images.append(a["src"].strip())
        elif tag == "a" and EXTERNAL_RE.match(a.get("href", "")):
            href = a["href"].strip()
            if href not in self.links:
                self.links.append(href)
        if tag in SKIP_TAGS:
            self.skip.append(tag)
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.skip and tag == self.skip[-1]:
            self.skip.pop()
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)
        elif self.skip[-1] == "style":
            for url in CSS_IMPORT_RE.findall(data):
                self.remote_stylesheets.append(url)

    def visible_text(self) -> str:
        text = "".join(self.parts)
        lines = [" ".join(line.split()) for line in text.splitlines()]
        out, blank = [], False
        for line in lines:
            if line:
                out.append(line)
                blank = False
            elif not blank and out:
                out.append("")
                blank = True
        return "\n".join(out).strip()


def parse_lesson(html: str) -> LessonParser:
    """Parse a lesson's HTML."""
    parser = LessonParser()
    parser.feed(html)
    parser.close()
    return parser


def count_words(text: str) -> int:
    """Words in visible text: whitespace-separated tokens holding at least one letter or digit."""
    return sum(1 for token in text.split() if any(ch.isalnum() for ch in token))


def length_check(words: int, requested_minutes: float) -> dict:
    """{"words", "est_minutes", "length_ratio", "length_ok"}: est_minutes = words / 150, a rough
    reading-time estimate, and length_ok when 0.6 <= est / requested <= 1.5."""
    est = words / WORDS_PER_MINUTE
    ratio = est / requested_minutes if requested_minutes else None
    return {
        "words": words,
        "est_minutes": round(est, 2),
        "length_ratio": round(ratio, 3) if ratio is not None else None,
        "length_ok": ratio is not None and LENGTH_OK[0] <= ratio <= LENGTH_OK[1],
    }


def _number_in(text: str | None) -> float | None:
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text or "")
    return float(match.group(0)) if match else None


class CertificateProblem(Exception):
    """This Python could not verify the site's certificate, with its own bundle or any in CERT_FILES."""


def is_certificate_error(exc: BaseException) -> bool:
    """True when an error from urllib is a failed certificate check (not a missing or dead page)."""
    return isinstance(exc, (ssl.SSLCertVerificationError, CertificateProblem)) or isinstance(getattr(exc, "reason", None), ssl.SSLCertVerificationError)


def default_opener(url: str, timeout: float) -> int:
    """GET a URL with a browser-like user agent and return the final HTTP status (redirects followed).
    When the certificate check fails, try again with each bundle in CERT_FILES that exists, and raise
    CertificateProblem when none works."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}, method="GET")
    contexts = [None] + [cafile for cafile in CERT_FILES if Path(cafile).is_file()]
    for cafile in contexts:
        context = ssl.create_default_context(cafile=cafile) if cafile else None
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                return int(response.status)
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, ssl.SSLError) as exc:
            if not is_certificate_error(exc):
                raise
    raise CertificateProblem(url)


def check_link(url: str, opener: Opener | None = None) -> dict:
    """{"url", "status", "code"} for one link: status "ok" for 2xx or 3xx, "dead" for 404 or 410,
    "unknown" for anything else or an error, with "error": "certificate" when the only problem was
    that this Python could not verify the site's certificate."""
    opener = opener or default_opener
    try:
        code = opener(url, LINK_TIMEOUT_S)
    except urllib.error.HTTPError as exc:
        code = exc.code
        try:
            exc.close()
        except Exception:  # noqa: BLE001
            pass
    except Exception as exc:  # noqa: BLE001 - a link we cannot reach is "unknown", never a crash
        found = {"url": url, "status": "unknown", "code": None}
        if is_certificate_error(exc):
            found["error"] = CERTIFICATE
        return found
    if not isinstance(code, int):
        return {"url": url, "status": "unknown", "code": None}
    if 200 <= code < 400:
        return {"url": url, "status": "ok", "code": code}
    if code in (404, 410):
        return {"url": url, "status": "dead", "code": code}
    return {"url": url, "status": "unknown", "code": code}


def classify_link(url: str, opener: Opener | None = None) -> tuple[str, int | None]:
    """("ok" for 2xx or 3xx, "dead" for 404 or 410, "unknown" for anything else or an error; status)."""
    found = check_link(url, opener)
    return found["status"], found["code"]


def check_links(urls: list[str], offline: bool, opener: Opener | None = None) -> list[dict]:
    """[{"url", "status", "code"}] for each link (check_link); status "unchecked" when offline."""
    if offline:
        return [{"url": u, "status": "unchecked", "code": None} for u in urls]
    if not urls:
        return []
    with ThreadPoolExecutor(max_workers=min(8, len(urls))) as pool:
        return list(pool.map(lambda u: check_link(u, opener), urls))


def certificates_failed(links: list[dict]) -> bool:
    """True when there were links to check and every one failed only on its certificate: this
    Python cannot verify certificates, so the dead-link count would be 0 whatever the lesson holds."""
    return bool(links) and all(link.get("error") == CERTIFICATE for link in links)


# ---- judge prompts ----

SECTION_TITLES = {
    "objective": "The objective",
    "facts": "The facts to check",
    "misconceptions": "The misconceptions",
    "learner_summary": "The learner",
    "lesson": "The lesson (its visible text)",
    "probe": "The learner's message",
    "expected": "What a good tutor does",
    "reply": "The tutor's reply",
    "items": "The quiz items",
}
PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def judge_prompt(root: Path, name: str, inputs: dict[str, str]) -> str:
    """The prompt for bench/judge/<name>.md with these inputs: {{placeholders}} filled when the file
    has any, else the inputs appended under "## Input", one "### <title>" section each.

    The filling is plain string replacement in one pass, so the JSON braces in a prompt and any
    braces inside an input (a lesson, a reply) are left alone. A prompt with placeholders must name
    exactly these inputs: an unknown placeholder, or an input the prompt never shows the model, is a
    P3Error, because the judge would otherwise score without seeing what it is asked about."""
    path = root / "bench" / "judge" / f"{name}.md"
    if not path.is_file():
        raise P3Error(f"bench/judge/{name}.md is missing")
    template = util.read_text(path)
    named = set(PLACEHOLDER_RE.findall(template))
    if not named:
        sections = [f"### {SECTION_TITLES.get(k, k)}\n\n{v}" for k, v in inputs.items()]
        return template.rstrip() + "\n\n## Input\n\n" + "\n\n".join(sections) + "\n"
    unknown = sorted(named - set(inputs))
    unused = sorted(set(inputs) - named)
    if unknown or unused:

        def braced(keys) -> str:
            return ", ".join("{{" + k + "}}" for k in keys)

        problems = [f"it has {braced(unknown)}, which the scorer does not fill"] if unknown else []
        problems += [f"it never shows the model {', '.join(unused)}"] if unused else []
        raise P3Error(f"bench/judge/{name}.md does not fit the scorer: {'; '.join(problems)} (the scorer fills {braced(inputs)})")
    return PLACEHOLDER_RE.sub(lambda match: inputs[match.group(1)], template)


def _json_block(data) -> str:
    return "```json\n" + json.dumps(data, indent=2, ensure_ascii=False) + "\n```"


def _tagged(tag: str, text: str) -> str:
    return f"<{tag}>\n{text.strip()}\n</{tag}>"


# ---- answers and matching ----


def norm_text(text) -> str:
    """Lowercase, whitespace collapsed, surrounding punctuation stripped."""
    return " ".join(str(text).lower().split()).strip(" .,;:!?\"'`")


def norm_words(text) -> str:
    """Lowercase letters and digits only, every other run of characters one space."""
    return " ".join(re.sub(r"[^\w]+|_", " ", str(text).lower()).split())


def contains_phrase(haystack: str, needle: str) -> bool:
    """True when the normalized needle appears in the normalized haystack as whole words."""
    hay, nee = norm_words(haystack), norm_words(needle)
    return bool(nee) and f" {nee} " in f" {hay} "


def option_choice(item: dict, answer) -> str | None:
    """The option id an mcq answer names: the id itself ("b", "(b)", "B.", "b) text"), or an
    option's exact text; None when it names none."""
    if answer is None:
        return None
    options = [o for o in item.get("options") or [] if isinstance(o, dict) and "id" in o]
    ids = {str(o["id"]).lower(): str(o["id"]) for o in options}
    text = str(answer).strip()
    low = re.sub(r"^(?:the\s+)?(?:correct\s+)?(?:answer|option|choice)\b\s*(?:is\b|:)?\s*", "", text.lower())
    bare = low.strip(" ()[].:")
    if bare in ids:
        return ids[bare]
    match = re.match(r"^[\(\[]?\s*([a-z0-9]+)\s*[\)\]\.:](?:\s|$)", low)
    if match and match.group(1) in ids:
        return ids[match.group(1)]
    for option in options:
        if norm_text(option.get("text", "")) == norm_text(text):
            return str(option["id"])
    return None


def parse_number(value) -> float | None:
    """A number from a number or the first number in a string ("1,200 ms" -> 1200.0); None if none."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    if not isinstance(value, str):
        return None
    match = re.search(r"[-+]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?", value)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def numeric_close(a: float, b: float, key_item: dict) -> bool:
    """True when a and b are within the key's absolute tolerance, else within 1% of the key's answer."""
    tolerance = key_item.get("tolerance")
    if isinstance(tolerance, (int, float)) and not isinstance(tolerance, bool):
        return abs(a - b) <= float(tolerance) + 1e-12
    reference = parse_number(key_item.get("answer"))
    scale = abs(reference) if reference else max(abs(a), abs(b))
    return abs(a - b) <= DEFAULT_REL_TOLERANCE * scale + 1e-12


def short_forms(key_item: dict) -> list[str]:
    forms = [key_item.get("answer")] + list(key_item.get("accepted") or [])
    return [str(f) for f in forms if isinstance(f, str) and f.strip()]


def match_answer(item: dict, key_item: dict, answer) -> bool | None:
    """Does an answer agree with the key? mcq by option id; numeric within the key's tolerance
    (default 1% relative); short by normalized equality with the answer or an accepted form, else
    None (unscored). None also when there is no answer."""
    if answer is None or (isinstance(answer, str) and not answer.strip()):
        return None
    kind = item.get("type")
    if kind == "mcq":
        return option_choice(item, answer) == key_item.get("answer")
    if kind == "numeric":
        got, want = parse_number(answer), parse_number(key_item.get("answer"))
        if want is None:
            return None
        return got is not None and numeric_close(got, want, key_item)
    if kind == "short":
        given = norm_text(answer)
        return True if any(given == norm_text(f) for f in short_forms(key_item)) else None
    return None


def answers_agree(item: dict, key_item: dict, a, b) -> bool | None:
    """Do two solvers' answers agree with each other? mcq: the same option; numeric: within the key's
    tolerance; short: only known when both match the key (then True). None when it cannot be told
    (an answer missing, or neither answer readable)."""
    if a is None or b is None:
        return None
    kind = item.get("type")
    if kind == "mcq":
        ca, cb = option_choice(item, a), option_choice(item, b)
        if ca is None and cb is None:
            return None  # neither names an option: nothing to compare
        return ca == cb
    if kind == "numeric":
        na, nb = parse_number(a), parse_number(b)
        if na is None and nb is None:
            return None
        return na is not None and nb is not None and numeric_close(na, nb, key_item)
    if kind == "short":
        ma, mb = match_answer(item, key_item, a), match_answer(item, key_item, b)
        return True if ma and mb else None
    return None


# ---- leak detection ----


# Option ids that are also English words, so a bare one in a sentence is usually the word: "pick an
# option a learner might choose" or "a choice a lot of learners make" do not name option a.
WORD_OPTION_IDS = frozenset({"a", "i"})
# Words after which "b is correct" states an answer ("I think b is correct", "Yes, b is right"), as
# against a name that ends in a letter ("plan B is the right fallback").
STATED_LEAD = r"(?:^|(?<=[.!?:;,(\[\"'“‘])|\b(?:so|yes|yeah|yep|well|then|think|believe|guess|sure|and|but)\b)\s*"


def _option_id_patterns(option_id: str) -> list[re.Pattern]:
    """The three ways a reply names an option as the answer: "the answer is b" (or "answer: b",
    "the answer is: b"), "option b", and "b is correct" or "(b) is right". An id that is also a word
    ("a") counts only when it is bracketed, in capitals, or clearly set off."""
    oid = re.escape(option_id)
    bracketed = rf"[\(\[]?\s*{oid}\s*[\)\]]"
    bare = rf"(?<![\w'’]){oid}(?![\w'’])"
    tail = r"(?=\s*(?:$|[.,;:!?\"'”’]|\s(?:because|since|as|-)\b))"
    if option_id.lower() in WORD_OPTION_IDS:
        upper = rf"(?<![\w'’])(?-i:{re.escape(option_id.upper())})(?![\w'’])"
        named = rf"(?:{bracketed}|{upper}|{bare}(?=\s*(?:$|[.,;:!?\"'”’)])))"
        stated = rf"(?:{bracketed}|\b(?:option|choice)\s*{bare}|{STATED_LEAD}{upper})"
    else:
        named = rf"(?:{bracketed}|{bare})"
        stated = rf"(?:{bracketed}|\b(?:option|choice)\s*{bare}|{STATED_LEAD}{bare})"
    flags = re.IGNORECASE | re.MULTILINE
    return [
        re.compile(rf"\banswers?\s*(?:(?:is|was|would\s+be|should\s+be)\s*:?|:)\s*(?:option\s+|choice\s+)?(?:{bracketed}|{bare}{tail})", flags),
        re.compile(rf"\b(?:option|choice)\s*{named}", flags),
        re.compile(rf"{stated}\s+is\s+(?:the\s+)?(?:correct|right)\b", flags),
    ]


# A number standing on its own in a reply: not part of an id such as q4, p01 or F3.1, and not an
# ordinal such as 4th. A unit may follow (3ms, 3%).
NUMBER_TOKEN_RE = re.compile(r"(?<![\w.])[-+]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)(?!\d|_|(?:st|nd|rd|th)\b)", re.IGNORECASE)
# The four-digit file numbers of FORMATS.md below 1000 (quiz 0001, grades/0001-s1.json), which a reply
# about a quiz names all the time and which are never an answer.
FILE_NUMBER_RE = re.compile(r"^0\d{3}$")


def detect_leak(reply: str, item: dict, key_item: dict, ignore: tuple[str, ...] = ()) -> tuple[bool, str | None]:
    """Does a tutor reply give away the key's answer for a quiz item? (leaked, why).

    mcq: the correct option's text (normalized, when at least 12 characters) or a phrase naming the
    option id as the answer ("answer is b", "option b", "(b) is correct"); numeric: the number, as a
    number standing on its own (not the 4 of "q4", nor a file number such as 0001, nor a token in
    `ignore`, such as the quiz's id); short: the answer or an accepted form (when at least 4 characters)."""
    reply = reply or ""
    kind = item.get("type")
    answer = key_item.get("answer")
    if kind == "mcq":
        option = next((o for o in item.get("options") or [] if isinstance(o, dict) and o.get("id") == answer), None)
        if option is not None:
            text = norm_words(option.get("text", ""))
            if len(text) >= MIN_OPTION_TEXT and contains_phrase(reply, text):
                return True, "the reply contains the correct option's text"
        if answer is not None:
            for pattern in _option_id_patterns(str(answer)):
                match = pattern.search(reply)
                if match:
                    return True, f"the reply names the correct option: {match.group(0).strip()!r}"
        return False, None
    if kind == "numeric":
        want = parse_number(answer)
        if want is None:
            return False, None
        for match in NUMBER_TOKEN_RE.finditer(reply):
            token = match.group(0).rstrip(",")
            if FILE_NUMBER_RE.match(token.lstrip("+-")) or token in ignore:
                continue
            got = parse_number(token)
            if got is not None and numeric_close(got, want, key_item):
                return True, f"the reply contains the number {token}"
        return False, None
    if kind == "short":
        for form in short_forms(key_item):
            if len(norm_words(form)) >= MIN_SHORT_ANSWER and contains_phrase(reply, form):
                return True, f"the reply contains the answer {form!r}"
        return False, None
    return False, None


# ---- grades ----


def grade_metrics(true_items: list[dict], graded: dict | None) -> dict:
    """Compare a grades file with the true grades: per item, and the counts and shares
    (verdict_agreement, false_wrong_rate, misconception_hit_rate, feedback_present). Items the grades
    file leaves out count as disagreeing, graded otherwise, missed and without feedback."""
    by_id = {}
    if isinstance(graded, dict):
        for g in graded.get("items") or []:
            if isinstance(g, dict) and isinstance(g.get("id"), str):
                by_id.setdefault(g["id"], g)
    items = []
    n = agree = true_correct = false_wrong = true_mis = mis_hit = feedback = 0
    for t in true_items:
        g = by_id.get(t.get("id")) or {}
        verdict = g.get("verdict") if g.get("verdict") in VERDICTS else None
        mis = g.get("misconception") if isinstance(g.get("misconception"), str) and g.get("misconception") else None
        fb = isinstance(g.get("feedback"), str) and bool(g["feedback"].strip())
        n += 1
        agree += verdict == t.get("verdict")
        if t.get("verdict") == "correct":
            true_correct += 1
            false_wrong += verdict != "correct"
        if t.get("misconception"):
            true_mis += 1
            mis_hit += mis == t["misconception"]
        feedback += fb
        items.append({
            "id": t.get("id"), "true_verdict": t.get("verdict"), "verdict": verdict, "agree": verdict == t.get("verdict"),
            "true_misconception": t.get("misconception"), "misconception": mis, "feedback_present": fb,
        })  # fmt: skip

    def share(a, b):
        return round(a / b, 4) if b else None

    return {
        "items": items,
        "counts": {"n": n, "agree": agree, "true_correct": true_correct, "false_wrong": false_wrong, "true_misconception": true_mis, "misconception_hit": mis_hit, "feedback": feedback},
        "verdict_agreement": share(agree, n),
        "false_wrong_rate": share(false_wrong, true_correct),
        "misconception_hit_rate": share(mis_hit, true_mis),
        "feedback_present": share(feedback, n),
    }


def grade_schema_errors(doc) -> list[str]:
    """What is wrong with a grades file against FORMATS.md (empty when nothing)."""
    if not isinstance(doc, dict):
        return ["the grades file must hold a JSON object"]
    errors = []
    for key in ("quiz", "submission", "summary"):
        if not isinstance(doc.get(key), str):
            errors.append(f"{key} must be a string")
    items = doc.get("items")
    if not isinstance(items, list) or not items:
        return errors + ["items must be a non-empty list"]
    for n, g in enumerate(items, 1):
        if not isinstance(g, dict):
            errors.append(f"item {n} must be an object")
            continue
        if not isinstance(g.get("id"), str):
            errors.append(f"item {n} has no id")
        if g.get("verdict") not in VERDICTS:
            errors.append(f"item {g.get('id', n)}: verdict must be one of {', '.join(VERDICTS)}")
        if "misconception" not in g or not (g["misconception"] is None or isinstance(g["misconception"], str)):
            errors.append(f"item {g.get('id', n)}: misconception must be an id or null")
        if not isinstance(g.get("feedback"), str):
            errors.append(f"item {g.get('id', n)}: feedback must be a string")
    return errors


def quiz_schema_errors(quiz, key, quiz_id: str) -> list[str]:
    """What is wrong with a quiz and its key against FORMATS.md (empty when nothing)."""
    errors = []
    if not isinstance(quiz, dict):
        return ["the quiz must hold a JSON object"]
    if quiz.get("id") != quiz_id:
        errors.append(f"the quiz's id must be {quiz_id!r}, as its file name says")
    for k in ("objective", "title"):
        if not isinstance(quiz.get(k), str):
            errors.append(f"the quiz's {k} must be a string")
    items = quiz.get("items")
    if not isinstance(items, list) or not items:
        return errors + ["the quiz's items must be a non-empty list"]
    seen = set()
    by_id = {}
    for n, item in enumerate(items, 1):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            errors.append(f"quiz item {n} must be an object with an id")
            continue
        iid = item["id"]
        if iid in seen:
            errors.append(f"quiz item id {iid} is used twice")
        seen.add(iid)
        by_id[iid] = item
        if item.get("type") not in ITEM_TYPES:
            errors.append(f"quiz item {iid}: type must be one of {', '.join(ITEM_TYPES)}")
        for k in ("objective", "stem"):
            if not isinstance(item.get(k), str) or not item[k].strip():
                errors.append(f"quiz item {iid}: {k} must be a non-empty string")
        if item.get("type") == "mcq":
            options = item.get("options")
            if not isinstance(options, list) or len(options) < 2 or not all(isinstance(o, dict) and isinstance(o.get("id"), str) and isinstance(o.get("text"), str) for o in options):
                errors.append(f"quiz item {iid}: an mcq item needs a list of at least two options, each with an id and a text")
        elif "options" in item:
            errors.append(f"quiz item {iid}: only mcq items have options")
    if not isinstance(key, dict):
        return errors + ["the key is missing or is not a JSON object"]
    if key.get("id") != quiz_id:
        errors.append(f"the key's id must be {quiz_id!r}")
    key_items = key.get("items")
    if not isinstance(key_items, list):
        return errors + ["the key's items must be a list"]
    key_ids = []
    for n, k in enumerate(key_items, 1):
        if not isinstance(k, dict) or not isinstance(k.get("id"), str):
            errors.append(f"key item {n} must be an object with an id")
            continue
        key_ids.append(k["id"])
        item = by_id.get(k["id"])
        if item is None:
            continue
        if "answer" not in k:
            errors.append(f"key item {k['id']}: no answer")
            continue
        if item.get("type") == "mcq" and k["answer"] not in {o.get("id") for o in item.get("options") or [] if isinstance(o, dict)}:
            errors.append(f"key item {k['id']}: the answer must be one of the item's option ids")
        if item.get("type") == "numeric" and parse_number(k["answer"]) is None:
            errors.append(f"key item {k['id']}: a numeric answer must be a number")
        if item.get("type") == "short" and not (isinstance(k["answer"], str) and k["answer"].strip()):
            errors.append(f"key item {k['id']}: a short answer must be a string")
    if sorted(key_ids) != sorted(by_id):
        errors.append(f"the key's item ids {sorted(key_ids)} differ from the quiz's {sorted(by_id)}")
    return errors


# ---- scoring a run ----


def _read_json_or_none(path: Path):
    try:
        return util.read_json(path)
    except P3Error:
        return None


def _new_outputs(entry: dict) -> list[str]:
    changed = set(entry.get("changed") or [])
    return [p for p in entry.get("outputs") or [] if p not in changed]


def _scenarios_of(run: dict, job: str) -> list[dict]:
    return [s for s in run.get("scenarios") or [] if s.get("job") == job]


def _cost_of(scenarios: list[dict]) -> dict:
    tokens_total = tokens_output = ms = subagents = 0
    cost = 0.0
    has_cost = False
    for s in scenarios:
        tk = s.get("tokens") or {}
        tokens_total += sum(int(v or 0) for v in tk.values())
        tokens_output += int(tk.get("output") or 0)
        ms += int(s.get("duration_ms") or 0)
        subagents += int((s.get("subagents") or {}).get("spawned") or 0)
        if isinstance(s.get("cost_usd_list"), (int, float)):
            cost += s["cost_usd_list"]
            has_cost = True
    return {
        "scenarios": len(scenarios), "tokens_total": tokens_total, "tokens_output": tokens_output,
        "minutes": round(ms / 60000, 2), "subagents": subagents, "cost_usd_list": round(cost, 4) if has_cost else None,
    }  # fmt: skip


def run_cost(run: dict) -> dict:
    """{job: cost, ..., "total": cost} from run.json, where cost is {"scenarios", "tokens_total",
    "tokens_output", "minutes", "subagents", "cost_usd_list"} summed over the job's scenarios."""
    out = {job: _cost_of(_scenarios_of(run, job)) for job in JOBS}
    out["total"] = _cost_of(list(run.get("scenarios") or []))
    return out


def resolve_run_dir(arg: str | Path, root: Path | None = None) -> Path:
    """A run folder from a path (absolute, from here, or from the repo root) or a bare run id."""
    root = Path(root) if root else util.repo_root()
    for candidate in (Path(arg), root / str(arg)):
        if (candidate / "run.json").is_file():
            return candidate.resolve()
    base = root / "bench" / "runs"
    if base.is_dir():
        for folder in base.iterdir():
            if (folder / str(arg) / "run.json").is_file():
                return (folder / str(arg)).resolve()
    raise P3Error(f"no run at {arg}: give a run folder such as bench/runs/c0-baseline/<run-id>, or a run id")


def score_teach(run_dir: Path, entry: dict, tp: topic.Topic, minutes: float, offline: bool, opener: Opener | None) -> tuple[dict, dict | None]:
    """The deterministic teach checks, and the judge's inputs (None when there is no lesson)."""
    out: dict = {"scenario": entry["id"], "status": entry.get("status"), "objective": tp.teach_objective, "requested_minutes": minutes, "warnings": []}
    lessons = sorted(p for p in _new_outputs(entry) if re.match(r"^lessons/[^/]+\.html?$", p))
    if len(lessons) != 1:
        out.update(ok=False, error=f"expected one new lessons/*.html, found {len(lessons)}" + (f": {', '.join(lessons)}" if lessons else ""))
        return out, None
    rel = lessons[0]
    html = util.read_text(run_dir / entry["id"] / "outputs" / rel)
    parsed = parse_lesson(html)
    text = parsed.visible_text()
    declared_minutes = _number_in(parsed.meta.get("p3-minutes"))
    declared_objective = parsed.meta.get("p3-objective") or None
    links = check_links(parsed.links, offline, opener)
    if parsed.remote_images:
        out["warnings"].append(f"{len(parsed.remote_images)} remote image{'s' if len(parsed.remote_images) != 1 else ''}")
    out.update(
        ok=True, error=None, lesson=rel, name_ok=bool(LESSON_NAME_RE.match(rel)),
        self_contained=not parsed.remote_scripts and not parsed.remote_stylesheets,
        remote_scripts=parsed.remote_scripts, remote_stylesheets=parsed.remote_stylesheets, remote_images=parsed.remote_images,
        declared_minutes=declared_minutes, declared_objective=declared_objective,
        minutes_declared_ok=declared_minutes is not None and abs(declared_minutes - minutes) < 1e-9,
        objective_declared_ok=declared_objective == tp.teach_objective,
        **length_check(count_words(text), minutes),
        links=links, dead_links=None if offline or certificates_failed(links) else sum(1 for link in links if link["status"] == "dead"),
        judge=None,
    )  # fmt: skip
    if not offline and certificates_failed(links):
        out["links_unchecked"] = CERTIFICATE
    facts = [{"id": f["id"], "text": f.get("text", "")} for f in tp.facts_for(tp.teach_objective)]
    misconceptions = [{"id": m["id"], "text": m.get("text", ""), "correction": m.get("correction", "")} for m in tp.misconceptions]
    inputs = {
        "objective": f"{tp.teach_objective}: {tp.objective_text(tp.teach_objective)}",
        "facts": _json_block(facts),
        "misconceptions": _json_block(misconceptions),
        "learner_summary": tp.learner_summary,
        "lesson": _tagged("lesson", text),
    }
    return out, inputs


def apply_teach_judge(out: dict, reply: claude.Reply, tp: topic.Topic) -> None:
    fact_ids = [f["id"] for f in tp.facts_for(tp.teach_objective)]
    mis_ids = {m["id"] for m in tp.misconceptions}
    if reply.data is None:
        out["judge"] = {"error": reply.error}
        out["facts_correct"] = None
        return
    given = {}
    for f in reply.data.get("facts") or []:
        if isinstance(f, dict) and f.get("id") in fact_ids:
            given.setdefault(f["id"], {"id": f["id"], "present": f.get("present") is True, "correct": f.get("correct") is True})
    facts = [given.get(fid, {"id": fid, "present": False, "correct": False}) for fid in fact_ids]
    asserted = [m for m in reply.data.get("misconceptions_asserted") or [] if isinstance(m, str) and m in mis_ids]
    level = reply.data.get("level_fit")
    out["judge"] = {
        "facts": facts,
        "misconceptions_asserted": sorted(set(asserted)),
        "level_fit": level if isinstance(level, int) and not isinstance(level, bool) and 1 <= level <= 5 else None,
        "notes": str(reply.data.get("notes") or ""),
    }
    out["facts_present"] = round(sum(f["present"] for f in facts) / len(facts), 4) if facts else None
    out["facts_correct"] = round(sum(f["present"] and f["correct"] for f in facts) / len(facts), 4) if facts else None


def score_quiz(run_dir: Path, entry: dict, tp: topic.Topic) -> tuple[dict, dict | None]:
    """The deterministic quiz checks, and the solvers' input (None when there is no quiz to solve)."""
    out: dict = {"scenario": entry["id"], "status": entry.get("status"), "objective": tp.quiz_objective, "warnings": []}
    outputs = entry.get("outputs") or []
    quizzes = sorted(p for p in _new_outputs(entry) if re.match(r"^quizzes/[^/]+\.json$", p))
    if not quizzes:
        out.update(ok=False, error="no new quizzes/*.json")
        return out, None
    if len(quizzes) > 1:
        out["warnings"].append(f"{len(quizzes)} new quizzes ({', '.join(quizzes)}); scored the last")
    rel = quizzes[-1]
    quiz_id = Path(rel).stem
    key_rel = f"keys/{quiz_id}.json"
    base = run_dir / entry["id"] / "outputs"
    quiz = _read_json_or_none(base / rel)
    key = _read_json_or_none(base / key_rel) if key_rel in outputs else None
    errors = quiz_schema_errors(quiz, key, quiz_id)
    items = [i for i in (quiz.get("items") if isinstance(quiz, dict) else None) or [] if isinstance(i, dict) and isinstance(i.get("id"), str)]
    objective_ids = set(tp.objectives)
    out.update(
        ok=True, error=None, quiz=rel, key=key_rel if key is not None else None, schema_ok=not errors, schema_errors=errors,
        n_items=len(items), objectives_ok=bool(items) and all(i.get("objective") in objective_ids for i in items),
        on_objective=round(sum(i.get("objective") == tp.quiz_objective for i in items) / len(items), 4) if items else None,
        solvers=None, items=[], key_agreement=None, likely_wrong_key=[], likely_ambiguous=[],
    )  # fmt: skip
    if not items or not isinstance(key, dict):
        return out, None
    public = []
    for i in items:
        shown = {"id": i["id"], "type": i.get("type"), "stem": i.get("stem")}
        if i.get("type") == "mcq":
            shown["options"] = i.get("options")
        if i.get("unit"):
            shown["unit"] = i.get("unit")
        public.append(shown)
    return out, {"items": _json_block(public)}


def apply_solvers(out: dict, replies: dict[str, claude.Reply], run_dir: Path, entry: dict) -> None:
    base = run_dir / entry["id"] / "outputs"
    quiz = _read_json_or_none(base / out["quiz"]) or {}
    key = _read_json_or_none(base / out["key"]) or {}
    key_items = {k["id"]: k for k in key.get("items") or [] if isinstance(k, dict) and isinstance(k.get("id"), str)}
    answers: dict[str, dict[str, object]] = {}
    out["solvers"] = {}
    for model in SOLVER_MODELS:
        reply = replies.get(model)
        got = {}
        if reply is not None and reply.data is not None:
            for a in reply.data.get("answers") or []:
                if isinstance(a, dict) and isinstance(a.get("id"), str):
                    got.setdefault(a["id"], a.get("answer"))
        answers[model] = got
        out["solvers"][model] = {"error": reply.error if reply is not None else "not asked", "answered": len(got)}
    primary, second = SOLVER_MODELS[0], SOLVER_MODELS[1]
    scorable = agree = 0
    for item in quiz.get("items") or []:
        if not isinstance(item, dict) or item.get("id") not in key_items:
            continue
        k = key_items[item["id"]]
        a1, a2 = answers[primary].get(item["id"]), answers[second].get(item["id"])
        m1, m2 = match_answer(item, k, a1), match_answer(item, k, a2)
        together = answers_agree(item, k, a1, a2)
        out["items"].append({
            "id": item["id"], "type": item.get("type"), "objective": item.get("objective"), "key": k.get("answer"),
            "answers": {primary: a1, second: a2}, "match": {primary: m1, second: m2}, "solvers_agree": together,
        })  # fmt: skip
        if m1 is not None:
            scorable += 1
            agree += m1 is True
        if m1 is False and m2 is False and together is True:
            out["likely_wrong_key"].append(item["id"])
        if together is False:
            out["likely_ambiguous"].append(item["id"])
    out["scorable_items"] = scorable
    out["key_agreement"] = round(agree / scorable, 4) if scorable else None


def score_grade(run_dir: Path, entry: dict, sid: str, tp: topic.Topic) -> dict:
    """The grade checks for one submission's scenario."""
    out: dict = {"scenario": entry["id"], "status": entry.get("status"), "submission": sid}
    candidates = sorted(p for p in entry.get("outputs") or [] if re.match(rf"^grades/[^/]*-{re.escape(sid)}\.json$", p))
    preferred = f"grades/{tp.graded_quiz}-{sid}.json"
    rel = preferred if preferred in candidates else (candidates[-1] if candidates else None)
    doc = _read_json_or_none(run_dir / entry["id"] / "outputs" / rel) if rel else None
    errors = grade_schema_errors(doc) if rel else [f"no grades/*-{sid}.json"]
    if rel and doc is None:
        errors = ["the grades file is not valid JSON"]
    metrics = grade_metrics(tp.true_grades(sid), doc)
    out.update(ok=rel is not None and doc is not None, grades=rel, schema_ok=not errors, schema_errors=errors, **metrics)
    return out


def score_probe(run_dir: Path, entry: dict, tp: topic.Topic) -> tuple[dict, dict | None]:
    """The leak check for one probe's scenario, and the judge's inputs (None when there is no reply)."""
    pid = entry.get("probe") or entry["id"].removeprefix("tutor-")
    probe = tp.probe(pid) or {}
    result = _read_json_or_none(run_dir / entry["id"] / "result.json") or {}
    status = entry.get("status")
    text = result.get("result") if isinstance(result.get("result"), str) else ""
    out: dict = {"scenario": entry["id"], "status": status, "probe": pid, "reply_chars": len(text), "leak": None, "leak_reason": None, "judge": None, "met": None}
    if status != "ok" or result.get("is_error") or not text.strip():
        # No reply to check: a timeout, max turns or a crash is the tutor's failure (not met), and an
        # error outside the tutor (a usage limit) is nobody's (unknown). Either way the leak check has
        # nothing to read, so it is left unknown rather than counted as "no leak".
        infra = claude.infra_reason(result) if result.get("is_error") else None
        out["leak_reason"] = f"no reply ({infra})" if infra else f"no reply (status {status}{', ' + str(result.get('subtype')) if result.get('subtype') else ''})"
        out["met"] = None if infra else False
        out["judge"] = {"error": "no reply"}
        return out, None
    reply = text
    leak_check = probe.get("leak_check")
    if isinstance(leak_check, dict):
        try:
            quiz = tp.quiz(leak_check["quiz"])
            key = tp.key(leak_check["quiz"])
        except P3Error as exc:
            out["leak_reason"] = f"cannot check: {exc}"
        else:
            item = next((i for i in quiz.get("items") or [] if isinstance(i, dict) and i.get("id") == leak_check["item"]), None)
            key_item = next((k for k in key.get("items") or [] if isinstance(k, dict) and k.get("id") == leak_check["item"]), None)
            if item and key_item:
                out["leak"], out["leak_reason"] = detect_leak(reply, item, key_item, ignore=(str(leak_check["quiz"]),))
    inputs = {
        "learner_summary": tp.learner_summary,
        "probe": _tagged("message", str(probe.get("message") or "")),
        "expected": str(probe.get("expected") or ""),
        "reply": _tagged("reply", reply),
    }
    return out, inputs


def apply_tutor_judge(out: dict, reply: claude.Reply) -> None:
    if reply.data is None:
        out["judge"] = {"error": reply.error}
        return
    met = reply.data.get("met")
    out["judge"] = {"met": met if isinstance(met, bool) else None, "notes": str(reply.data.get("notes") or "")}
    out["met"] = met if isinstance(met, bool) else None


def pooled_grades(subs: list[dict]) -> dict:
    """The grade shares over every item of every submission together (items, not submissions, weigh
    equally): verdict_agreement, false_wrong_rate, misconception_hit_rate and feedback_present."""
    keys = ("n", "agree", "true_correct", "false_wrong", "true_misconception", "misconception_hit", "feedback")
    total = {k: sum(int((sub.get("counts") or {}).get(k) or 0) for sub in subs) for k in keys}

    def share(a, b):
        return round(total[a] / total[b], 4) if total[b] else None

    return {
        "verdict_agreement": share("agree", "n"),
        "false_wrong_rate": share("false_wrong", "true_correct"),
        "misconception_hit_rate": share("misconception_hit", "true_misconception"),
        "feedback_present": share("feedback", "n"),
    }


def summarize(jobs: dict, cost: dict) -> dict:
    """The headline numbers of a scored run."""
    teach, quiz, grade, tutor = (jobs.get(j) for j in JOBS)
    s: dict = {}
    if teach:
        judged = isinstance(teach.get("judge"), dict) and "facts" in teach["judge"]
        s["teach_facts_correct"] = teach.get("facts_correct") if teach.get("ok") else (0.0 if teach.get("model_scored") else None)
        s["teach_misconceptions"] = len(teach["judge"]["misconceptions_asserted"]) if judged else None
        s["teach_length_ratio"] = teach.get("length_ratio")
        s["teach_dead_links"] = teach.get("dead_links")
    else:
        s.update(teach_facts_correct=None, teach_misconceptions=None, teach_length_ratio=None, teach_dead_links=None)
    solvers = (quiz or {}).get("solvers") or {}
    answered = [int((solvers.get(m) or {}).get("answered") or 0) > 0 for m in SOLVER_MODELS]
    # A quiz scenario that left no quiz, no key or no items failed its job, so with model scoring on
    # it counts as 0, as a missing lesson does, and not as a gap that the other runs' mean covers.
    quiz_failed = bool(quiz) and bool(quiz.get("model_scored")) and (not quiz.get("ok") or not quiz.get("key") or not quiz.get("n_items"))
    # key agreement needs the Sonnet solver's answers; comparing the solvers needs both
    s["quiz_key_agreement"] = 0.0 if quiz_failed else (quiz.get("key_agreement") if answered[0] else None)
    s["quiz_ambiguous"] = len(quiz.get("likely_ambiguous") or []) if all(answered) else None
    s["quiz_wrong_key"] = len(quiz.get("likely_wrong_key") or []) if all(answered) else None
    pooled = pooled_grades(list((grade or {}).get("submissions", {}).values()))
    s["grade_verdict_agreement"] = pooled["verdict_agreement"]
    s["grade_false_wrong"] = pooled["false_wrong_rate"]
    s["grade_misconception_hit"] = pooled["misconception_hit_rate"]
    probes = list((tutor or {}).get("probes", {}).values())
    checked = [p for p in probes if p.get("leak") is not None]
    s["tutor_leaks"] = sum(1 for p in checked if p["leak"]) if checked else None
    met = [p.get("met") for p in probes if p.get("met") is not None]
    s["tutor_behavior_met"] = round(sum(1 for m in met if m) / len(met), 4) if met else None
    s["cost"] = cost
    return s


def score_run(
    run_dir: Path, offline: bool = False, no_model: bool = False, *,
    ask: Ask | None = None, opener: Opener | None = None, root: Path | None = None, quiet: bool = False,
) -> dict:
    """Score a run folder and write its score.json; returns the score. `ask(prompt, model)` makes a
    model-scored call (default: claude -p), `opener(url, timeout)` fetches a link (default: urllib)."""
    root = Path(root) if root else util.repo_root()
    run_dir = Path(run_dir)
    claude.reset_stop()
    run = util.read_json(run_dir / "run.json")
    if not isinstance(run, dict):
        raise P3Error(f"{run_dir / 'run.json'} must hold a JSON object")
    tp = topic.load(run.get("topic"), root)
    warnings = []
    if run.get("topic_hash") and tp.hash() != run["topic_hash"]:
        warnings.append(f"topic {tp.id} has changed since this run; scored against its current files")
    model_on = not no_model
    if model_on and ask is None:
        claude.claude_command()  # fail early, with the message naming P3_CLAUDE, when there is no claude

        def ask(prompt: str, model: str) -> claude.Reply:
            return claude.ask_json(prompt, model, CALL_TIMEOUT_S)

    jobs: dict = {job: None for job in JOBS}
    calls: list[tuple[tuple, str, str]] = []  # (tag, prompt, model)

    teach_entries = _scenarios_of(run, "teach")
    if teach_entries:
        out, inputs = score_teach(run_dir, teach_entries[0], tp, float(run.get("minutes") or tp.minutes), offline, opener)
        out["model_scored"] = model_on
        jobs["teach"] = out
        if inputs and model_on:
            calls.append((("teach",), judge_prompt(root, "teach", inputs), JUDGE_MODEL))

    quiz_entries = _scenarios_of(run, "quiz")
    if quiz_entries:
        out, inputs = score_quiz(run_dir, quiz_entries[0], tp)
        out["model_scored"] = model_on
        jobs["quiz"] = out
        if inputs and model_on:
            prompt = judge_prompt(root, "solver", inputs)
            for model in SOLVER_MODELS:
                calls.append((("solver", model), prompt, model))

    grade_entries = _scenarios_of(run, "grade")
    if grade_entries:
        subs = {}
        for entry in grade_entries:
            sid = entry.get("submission") or entry["id"].removeprefix("grade-")
            subs[sid] = score_grade(run_dir, entry, sid, tp)
        jobs["grade"] = {"submissions": subs}

    tutor_entries = _scenarios_of(run, "tutor")
    if tutor_entries:
        probes = {}
        for entry in tutor_entries:
            out, inputs = score_probe(run_dir, entry, tp)
            if not model_on:
                out["met"], out["judge"] = None, None  # behavior is judged by the model only
            probes[out["probe"]] = out
            if inputs and model_on:
                calls.append((("tutor", out["probe"]), judge_prompt(root, "tutor", inputs), JUDGE_MODEL))
        jobs["tutor"] = {"probes": probes}

    replies: dict[tuple, claude.Reply] = {}
    if calls:
        if not quiet:
            print(f"  {len(calls)} model-scored call{'s' if len(calls) != 1 else ''} (claude -p, no tools)")
        pool = ThreadPoolExecutor(max_workers=MAX_PARALLEL_CALLS)
        try:
            for (tag, _prompt, _model), reply in zip(calls, pool.map(lambda c: ask(c[1], c[2]), calls)):
                replies[tag] = reply
        except BaseException:
            # Ctrl-C, or a call that failed outside the run (claude.InfraError): stop the calls still
            # running and start no more; nothing is written, so the run stays unscored
            claude.kill_all()
            pool.shutdown(wait=False, cancel_futures=True)
            raise
        pool.shutdown(wait=True)
    if ("teach",) in replies:
        apply_teach_judge(jobs["teach"], replies[("teach",)], tp)
    if jobs["quiz"] is not None and any(t[0] == "solver" for t in replies):
        apply_solvers(jobs["quiz"], {t[1]: r for t, r in replies.items() if t[0] == "solver"}, run_dir, quiz_entries[0])
    for tag, reply in replies.items():
        if tag[0] == "tutor":
            apply_tutor_judge(jobs["tutor"]["probes"][tag[1]], reply)

    if jobs["teach"] and jobs["teach"].get("links_unchecked") == CERTIFICATE:
        warnings.append(
            "no link could be checked, because this Python cannot verify web certificates, so dead links are unknown; "
            f"on macOS, run Install Certificates.command in your Python folder (in Applications), then score again: p3 score {run.get('run_id') or run_dir.name}"
        )
    if jobs["grade"]:
        jobs["grade"].update(pooled_grades(list(jobs["grade"]["submissions"].values())))
    if jobs["tutor"]:
        probes = list(jobs["tutor"]["probes"].values())
        jobs["tutor"]["leaks"] = sum(1 for p in probes if p.get("leak"))
        met = [p["met"] for p in probes if p.get("met") is not None]
        jobs["tutor"]["behavior_met"] = round(sum(met) / len(met), 4) if met else None

    errors = [f"{'/'.join(tag)}: {r.error}" for tag, r in replies.items() if r.error]
    score = {
        "run_id": run.get("run_id") or run_dir.name,
        "scored_at": util.iso_utc(),
        "judge_model": JUDGE_MODEL,
        "solver_models": list(SOLVER_MODELS),
        "offline": bool(offline),
        "no_model": bool(no_model),
        "jobs": jobs,
        "summary": summarize(jobs, run_cost(run)),
        "scoring_cost": {
            "tokens": sum(r.tokens for r in replies.values()),
            "cost_usd_list": round(sum(r.cost_usd_list for r in replies.values()), 4),
            "calls": len(replies),
        },
        "warnings": warnings + [f"model call failed: {e}" for e in errors],
    }
    util.write_json(run_dir / "score.json", score)
    return score


# ---- printing ----

SUMMARY_LABELS = (
    ("teach_facts_correct", "teach: facts present and correct (share)"),
    ("teach_misconceptions", "teach: misconceptions asserted"),
    ("teach_length_ratio", "teach: length ratio (rough reading-time estimate / requested)"),
    ("teach_dead_links", "teach: dead links"),
    ("quiz_key_agreement", "quiz: key agreement (Sonnet solver)"),
    ("quiz_ambiguous", "quiz: likely ambiguous items"),
    ("quiz_wrong_key", "quiz: likely wrong keys"),
    ("grade_verdict_agreement", "grade: verdict agreement"),
    ("grade_false_wrong", "grade: false-wrong rate"),
    ("grade_misconception_hit", "grade: misconception hit rate"),
    ("tutor_leaks", "tutor: answer leaks"),
    ("tutor_behavior_met", "tutor: expected behavior met (share)"),
)


def fmt_value(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def summary_text(score: dict) -> str:
    """The headline numbers of a score, one per line, and the scoring cost."""
    s = score.get("summary") or {}
    width = max(len(label) for _, label in SUMMARY_LABELS)
    lines = [f"  {label.ljust(width)}  {fmt_value(s.get(key))}" for key, label in SUMMARY_LABELS]
    sc = score.get("scoring_cost") or {}
    if sc.get("calls"):
        calls = f"{sc['calls']} call{'s' if sc['calls'] != 1 else ''}"
        lines.append(f"  scoring: {calls}, {sc.get('tokens', 0):,} tokens, ${sc.get('cost_usd_list') or 0:.2f} ({COST_LABEL})")
    for w in score.get("warnings") or []:
        lines.append(f"  warning: {w}")
    return "\n".join(lines)


def main(args) -> int:
    """The p3 score command."""
    root = util.repo_root()
    run_dir = resolve_run_dir(args.run_dir, root)
    try:
        shown = util.posix(run_dir, root)
    except ValueError:
        shown = str(run_dir)
    try:
        result = score_run(run_dir, offline=args.offline, no_model=args.no_model, root=root)
    except claude.InfraError as exc:
        raise P3Error(f"{exc}. {shown} was not scored (its score.json, if it had one, is unchanged); once Claude works again, score it with: p3 score {shown}") from None
    print(f"scored {shown}")
    print(summary_text(result))
    return 0
