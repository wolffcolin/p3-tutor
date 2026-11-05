"""The review files in reviews/, read from their Markdown: p3 check judges them, and p3 report
tables their ratings.

The student writes them along the ladder (reviews/README.md says how); this docstring is the format
both sides keep to.

reviews/<step>.md, for c1-skills, c2-review, c3-split and final:

    # Reviews: <step>
    ## Quick rounds
    ### Round 1                        "optional" in the heading marks an optional round
    **Run:** <run folder or what was run>
    **My thoughts:**
    <the student's thoughts>
    **What changed:**
    - Kind: modified skill | new skill | new subagent | other
    - Files: <the files changed>
    - Why: <why>
    ## Major review
    **Run:** bench/runs/<step>/<run-id>
    **Live tries:**
    <what the student tried in tutor/>
    ### Lesson                         one per job of the step (STEP_JOBS)
    #### Pedagogy                      one per criterion of the job (CRITERIA)
    Rating: 4
    <feedback>
    ### Compared with the previous step
    ### What the next step should fix  (in final: What I would do next)
    ## Learning sessions               final only
    ### Session 1                      to 3, each with **Date:**, **Topic:**, then the text
    ## Test topics                     final only
    ### <topic-id>                     one per test topic in bench/own/

reviews/components.md:

    # Components
    ### <name>                         the skill's folder name, or the subagent's frontmatter name
    - Kind: skill | subagent
    - Step added: <step>
    - Purpose: ...
    - With and without: ...
    - Review: ...
    - Kept in final: yes | no, because ...

A text is written when it is not empty and holds no TODO outside code (a TODO in a fenced code
block or an inline code span, such as a lesson's exercise the student quotes, is not a marker). A
round is complete when My thoughts, Kind, Files and Why are written and Kind is one of the four
kinds (its Run line is not part of that, and p3 check only warns when it is left unwritten); a major
review when its Run names a run of the step, Live tries is written (the text from its label up to
the first job or closing section, sub-headings included), every criterion of the step's jobs has a
whole-number rating from 1 to 5 and written feedback (words after the rating on its line count as
feedback), and both closing sections are written; a learning session when Date, Topic and its text
are written; a test-topic section when its text is; an inventory entry when its six fields are, Kind
is skill or subagent and Kept in final starts with yes or no (a no with its reason). A ### section of
components.md with none of the six field labels is prose, unless its heading names a component that
was built. What needs the rest of the repo is for p3 check: whether the named run exists and is a
scored full run of the step on the shared topic, and whether each learning session's Topic starts
with the id of a test topic in bench/own/, the same one in all three.

A config's subagents are the .md files under its .claude/agents/ (subfolders included, README.md
left out) whose frontmatter opens on the first line and has a name, which is what Claude Code loads;
a Markdown file there without one is documentation, and not counted.

The parsing is lenient about layout and strict about names. CRLF line endings, trailing spaces,
blank lines, extra prose and extra sections are fine, and HTML comments and fenced code blocks are
skipped (a comment opener inside inline code, such as `<!--` quoted from a lesson, is text). Headings
and field names match ignoring case, spacing, bold and code marks, and a field may be written
**Name:**, **Name**: or Name: (in a list or not), with a one-line value on its line or on the next
line that is not blank, but the names must be the ones above, at the heading levels above. Every problem names its section, as in "Major review > Lesson > Pedagogy:
Rating is still TODO".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, NamedTuple

from p3 import util

REVIEWS_DIR = "reviews"
COMPONENTS_PATH = f"{REVIEWS_DIR}/components.md"
STEPS = ("c1-skills", "c2-review", "c3-split", "final")
LESSON, QUIZ, FEEDBACK, TUTOR = "Lesson", "Quiz", "Feedback", "Tutor"
CRITERIA: dict[str, tuple[str, ...]] = {
    LESSON: ("Technical correctness and facts", "Pedagogy", "Alignment with the learning goal", "Overall quality"),
    QUIZ: ("Difficulty", "Coverage of the lesson's core", "Wording and possible misreadings", "Writing quality", "Alignment with the learning goal"),
    FEEDBACK: ("Useful", "Explains enough", "Personalized to how I like things explained"),
    TUTOR: ("Guardrails", "Personalization"),
}
STEP_JOBS: dict[str, tuple[str, ...]] = {
    "c1-skills": (LESSON, QUIZ, FEEDBACK, TUTOR),
    "c2-review": (LESSON, QUIZ, FEEDBACK),
    "c3-split": (LESSON,),
    "final": (LESSON, QUIZ, FEEDBACK, TUTOR),
}
QUICK_ROUNDS = "Quick rounds"
MAJOR_REVIEW = "Major review"
LEARNING_SESSIONS = "Learning sessions"
TEST_TOPICS = "Test topics"
COMPARED = "Compared with the previous step"
NEXT_FIX = "What the next step should fix"
NEXT_DO = "What I would do next"
MIN_ROUNDS = {"c1-skills": 2, "c2-review": 2, "c3-split": 2, "final": 0}
SESSIONS = 3
KINDS = ("modified skill", "new skill", "new subagent", "other")
NEW_SUBAGENT = "new subagent"
SKILL, SUBAGENT = "skill", "subagent"
COMPONENT_FIELDS = ("Kind", "Step added", "Purpose", "With and without", "Review", "Kept in final")
RATING_MIN, RATING_MAX = 1, 5
TODO_MARK = "TODO"


def step_file(step: str) -> str:
    """The review file of a step, as a repo-relative POSIX path (reviews/<step>.md)."""
    return f"{REVIEWS_DIR}/{step}.md"


def closing_sections(step: str) -> tuple[str, str]:
    """The two sections that end a step's major review."""
    return (COMPARED, NEXT_DO if step == "final" else NEXT_FIX)


def written(text: str | None) -> bool:
    """True when a text is there, not empty, and holds no TODO marker."""
    return text is not None and bool(text.strip()) and not has_todo(text)


def has_todo(text: str) -> bool:
    """True when a text holds a TODO marker outside code: fenced code blocks and inline code spans
    are left out, because a lesson's code that the student quotes may well say TODO."""
    out, fence = [], ""
    for line in text.split("\n"):
        if fence:
            fence = "" if _closes(line, fence) else fence
            continue
        opened = _fence_open(line)
        if opened:
            fence = opened
            continue
        out.append(_CODE_SPAN.sub("", line))
    return TODO_MARK in "\n".join(out)


def name_key(text: str) -> str:
    """A heading or field name as names are compared: bold and code marks, a trailing colon and
    extra spacing dropped, curly apostrophes made straight, case folded."""
    t = text.replace("\u2018", "'").replace("\u2019", "'")
    t = re.sub(r"[*`]", "", t).strip().rstrip(":").strip()
    return " ".join(t.split()).casefold()


# ---- Markdown: lines, sections and fields ----


class Line(NamedTuple):
    number: int  # 1-based, in the file
    text: str
    code: bool  # inside a fenced code block


@dataclass
class Section:
    """A heading and what is under it: `lines` up to its first sub-heading, then `children`."""

    level: int  # 0 for the document itself
    title: str
    line: int
    lines: list[Line] = field(default_factory=list)
    children: list[Section] = field(default_factory=list)

    def all_lines(self) -> list[Line]:
        """Every line under the heading, sub-headings and their lines included."""
        out = list(self.lines)
        for c in self.children:
            out.append(Line(c.line, "#" * c.level + " " + c.title, False))
            out += c.all_lines()
        return out

    def text(self) -> str:
        return "\n".join(ln.text for ln in self.all_lines()).strip()

    def walk(self) -> Iterator[Section]:
        yield self
        for c in self.children:
            yield from c.walk()

    def child(self, name: str, level: int) -> Section | None:
        """The first direct sub-section at `level` named `name`."""
        key = name_key(name)
        return next((c for c in self.children if c.level == level and name_key(c.title) == key), None)

    def find(self, name: str, level: int) -> Section | None:
        """The first section anywhere below at `level` named `name`."""
        key = name_key(name)
        return next((s for s in self.walk() if s.level == level and name_key(s.title) == key), None)


_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")
_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
_CLOSING_HASHES = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")


def _fence_open(line: str) -> str:
    """The fence that opens a code block on `line` (three or more backticks or tildes), or "". As in
    CommonMark, a backtick fence whose info string holds a backtick is not one: a line that starts
    with ```code``` is inline code."""
    m = _FENCE.match(line)
    if not m or (m.group(1)[0] == "`" and "`" in line[m.end():]):
        return ""
    return m.group(1)


def _drop_comments(line: str, comment: bool) -> tuple[str, bool]:
    """`line` with its HTML comments taken out, and whether a comment is still open at its end;
    `comment` says one was open at its start. A comment opener inside an inline code span is text."""
    out, i = [], 0
    while i < len(line):
        if comment:
            end = line.find("-->", i)
            if end < 0:
                return "".join(out), True
            i, comment = end + 3, False
        elif line[i] == "`":
            m = _CODE_SPAN.match(line, i)
            j = m.end() if m else len(line) - len(line[i:].lstrip("`"))
            out.append(line[i:j])
            i = j
        elif line.startswith("<!--", i):
            i, comment = i + 4, True
        else:
            out.append(line[i])
            i += 1
    return "".join(out), comment


def _closes(line: str, fence: str) -> bool:
    """True when `line` closes a code block opened with `fence`."""
    m = _FENCE.match(line)
    return bool(m) and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not line.strip().strip(fence[0])


def parse_markdown(text: str) -> Section:
    """The heading tree of a Markdown text (ATX headings; HTML comments dropped, headings inside
    fenced code blocks left as text). One pass over the lines, so a comment opener inside a code
    block or an inline code span stays text, and an unclosed comment runs to the end of the file.
    Line numbers are those of the file."""
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    doc = Section(0, "", 0)
    stack = [doc]
    fence, comment = "", False
    for number, raw in enumerate(text.split("\n"), 1):
        line = raw.rstrip()
        if fence:
            stack[-1].lines.append(Line(number, line, True))
            fence = "" if _closes(line, fence) else fence
            continue
        if comment or "<!--" in line:
            line, comment = _drop_comments(line, comment)
            line = line.rstrip()
        opened = _fence_open(line)
        if opened:
            fence = opened
            stack[-1].lines.append(Line(number, line, True))
            continue
        h = _HEADING.match(line)
        if h:
            level = len(h.group(1))
            title = _CLOSING_HASHES.sub("", h.group(2) or "").strip()
            while stack[-1].level >= level:
                stack.pop()
            section = Section(level, title, number)
            stack[-1].children.append(section)
            stack.append(section)
            continue
        stack[-1].lines.append(Line(number, line, False))
    return doc


_LABELS: dict[str, re.Pattern] = {}


def _label(name: str) -> re.Pattern:
    """A field line: **Name:** value, **Name**: value or Name: value, in a list item or not."""
    if name not in _LABELS:
        words = r"\s+".join(re.escape(w) for w in name.split())
        _LABELS[name] = re.compile(r"^\s*(?:[-*+]\s+)?(?:\*\*|__)?\s*" + words + r"\s*(?:(?:\*\*|__)\s*:|:(?:\s*(?:\*\*|__))?)\s*(.*)$", re.I)
    return _LABELS[name]


@dataclass
class Fields:
    """The labeled fields of a run of lines: each field's lines (the text after the label first),
    how many times each label appears, and the lines that belong to no field."""

    values: dict[str, list[Line]]
    counts: dict[str, int]
    rest: list[Line]

    def text(self, name: str) -> str | None:
        """A field's text, or None when its label is not there."""
        if name not in self.values:
            return None
        return "\n".join(ln.text for ln in self.values[name]).strip()

    def rest_text(self) -> str:
        return "\n".join(ln.text for ln in self.rest).strip()


def fields(lines: list[Line], block: tuple[str, ...] = (), inline: tuple[str, ...] = ()) -> Fields:
    """Split lines into labeled fields. A `block` field runs from its label to the next label; an
    `inline` field is the rest of its label's line, or, when that is empty, the next line that is
    not blank, unless that is a label, a heading or code. A label met again adds to the same field."""
    names = [(name, False) for name in block] + [(name, True) for name in inline]
    patterns = [(name, _label(name), is_inline) for name, is_inline in names]
    values: dict[str, list[Line]] = {}
    counts: dict[str, int] = {}
    rest: list[Line] = []
    current: str | None = None
    take_next: str | None = None
    for ln in lines:
        found = None
        if not ln.code:
            for name, pattern, is_inline in patterns:
                m = pattern.match(ln.text)
                if m:
                    found = (name, m.group(1).strip(), is_inline)
                    break
        if found:
            name, value, is_inline = found
            counts[name] = counts.get(name, 0) + 1
            values.setdefault(name, []).append(Line(ln.number, value, False))
            current = None if is_inline else name
            take_next = name if is_inline and not value else None
            continue
        if take_next is not None and ln.text.strip():
            name, take_next = take_next, None
            if not ln.code and not _HEADING.match(ln.text):
                values[name].append(Line(ln.number, ln.text.strip(), False))
                continue
        if current is not None:
            values[current].append(ln)
        else:
            rest.append(ln)
    return Fields(values, counts, rest)


def _problem(where: str, label: str, text: str | None, missing: str) -> str | None:
    """What is wrong with a field's text (missing, empty or TODO), as '<where>: ...', or None."""
    if text is None:
        return f"{where}: {missing}"
    if not text.strip():
        return f"{where}: {label} is empty"
    if has_todo(text):
        return f"{where}: {label} is still TODO"
    return None


def _bold_missing(name: str) -> str:
    return f"no **{name}:** line"


def _bullet_missing(name: str, under: str = "") -> str:
    return f"no \"- {name}:\" line" + (f" under {under}" if under else "")


def _misplaced(doc: Section, name: str, level: int, parent: str) -> str:
    """' (line N has it as ## Name; ...)' when a heading of that name sits at another level."""
    key = name_key(name)
    other = next((s for s in doc.walk() if s.level and s.level != level and name_key(s.title) == key), None)
    if other is None:
        return ""
    return f" (line {other.line} has it as {'#' * other.level} {other.title}; make it {'#' * level} {name}, under {parent})"


# ---- the step files ----


@dataclass
class Round:
    """One quick round."""

    title: str
    line: int
    optional: bool
    run: str | None
    thoughts: str | None
    kind: str | None  # as written
    files: str | None
    why: str | None
    kind_value: str | None  # one of KINDS, when Kind is one
    problems: list[str]

    @property
    def complete(self) -> bool:
        return not self.problems

    @property
    def touched(self) -> bool:
        """True once any of My thoughts, Kind, Files or Why is written (an untouched optional
        round is left out of every count)."""
        return any(written(t) for t in (self.thoughts, self.kind, self.files, self.why))

    @property
    def run_written(self) -> bool:
        """True when the Run line names what was run (not part of complete; p3 check warns)."""
        return written(self.run)


@dataclass
class Criterion:
    """One criterion of a major review."""

    job: str
    name: str
    rating: int | None  # a whole number from 1 to 5, else None
    rating_text: str | None
    feedback: str | None
    problems: list[str]


@dataclass
class MajorReview:
    """A step's major review."""

    present: bool
    run: str | None
    run_id: str | None  # the run it names, when it names one of its step's config
    live_tries: str | None
    criteria: dict[tuple[str, str], Criterion]  # (job, criterion), every one found
    closing: dict[str, str | None]
    problems: list[str]  # what keeps it from complete, in the jobs the step reviews

    @property
    def complete(self) -> bool:
        return self.present and not self.problems

    @property
    def touched(self) -> bool:
        """True once anything but the Run line is written."""
        texts = [self.live_tries, *self.closing.values()]
        texts += [t for c in self.criteria.values() for t in (c.rating_text, c.feedback)]
        return any(written(t) for t in texts)

    def ratings(self) -> dict[tuple[str, str], int]:
        """{(job, criterion): rating} of the valid ratings, in every job reviewed."""
        return {k: c.rating for k, c in self.criteria.items() if c.rating is not None}


@dataclass
class Session:
    """One learning session (final only)."""

    title: str
    line: int
    date: str | None
    topic: str | None
    topic_id: str  # the Topic line's first word, the test topic it names ("" when none)
    text: str
    problems: list[str]

    @property
    def complete(self) -> bool:
        return not self.problems

    @property
    def touched(self) -> bool:
        return any(written(t) for t in (self.date, self.topic, self.text))


@dataclass
class TopicReview:
    """The review of one test topic (final only)."""

    title: str
    line: int
    topic: str  # the heading's first word, the topic id it names
    text: str
    problems: list[str]

    @property
    def complete(self) -> bool:
        return not self.problems


@dataclass
class StepReview:
    """reviews/<step>.md, parsed. When a ## section is missing, its list is empty and its
    *_problem says so (Quick rounds may be missing from final, where rounds are optional)."""

    step: str
    path: str
    rounds: list[Round]
    rounds_problem: str | None
    major: MajorReview
    sessions: list[Session]
    sessions_problem: str | None
    topics: list[TopicReview]
    topics_problem: str | None


_ROUND = re.compile(r"^round\s+(\d+)\b")
_SESSION = re.compile(r"^session\s+(\d+)\b")
_RUN_PATH = re.compile(r"bench[/\\]+runs[/\\]+([A-Za-z0-9][A-Za-z0-9._-]*)[/\\]+([A-Za-z0-9][A-Za-z0-9._-]*)")
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_PLACEHOLDER = re.compile(r"<[^<>\s][^<>]*>")


def run_ref(text: str | None, step: str) -> tuple[str, str] | None:
    """(config, run id) that a Run line names: bench/runs/<config>/<run-id> anywhere in it (in
    backticks, a link or prose; with / or \\), the first one of `step` when it names several, or a
    bare run id, taken as one of `step`'s. None for a line that names no run, such as the template's
    placeholder bench/runs/<step>/<run-id>."""
    if not text:
        return None
    found = [(m.group(1), m.group(2).rstrip(".")) for m in _RUN_PATH.finditer(text)]
    if found:
        return next((ref for ref in found if ref[0] == step), found[0])
    if _PLACEHOLDER.search(text):
        return None
    token = text.strip().strip("`*'\"").strip().rstrip("/\\.")
    return (step, token) if _RUN_ID.match(token) else None


def parse_rating(text: str | None, count: int = 1) -> tuple[int | None, str | None]:
    """(rating, problem) of a Rating line's value: a whole number from 1 to 5, written as 4, 4/5
    or 4 out of 5, with any words after it (rating_remark). A range such as 3-4, 3 to 4 or 3 or 4,
    and a 4+, are not a rating."""
    hint = f"a whole number from {RATING_MIN} to {RATING_MAX}"
    if text is None:
        return None, f"no Rating line (write Rating: N, N {hint})"
    if count > 1:
        return None, f"{count} Rating lines; keep one"
    value = _rating_value(text)
    if not value:
        return None, f"Rating is empty; write {hint}"
    if TODO_MARK in value:
        return None, f"Rating is still TODO; write {hint}"
    shown = value if len(value) <= 30 else value[:27] + "..."
    m = _RATING.match(value)
    if not m or (value[m.end():m.end() + 1].isalnum()):
        return None, f"Rating is {shown!r}; write {hint}"
    rest = value[m.end():]
    if re.match(r"\s*\+", rest):
        return None, f"Rating is {shown!r}; write {hint}, without the +"
    if re.match(r"\s*(?:-|/|to\b|or\b|and\b)\s*\d", rest, re.I):
        return None, f"Rating is {shown!r}; pick one, {hint}, not a range"
    if m.group(2) and m.group(2) != str(RATING_MAX):
        return None, f"Rating is {shown!r}; ratings are out of {RATING_MAX}, so write {hint}"
    if not m.group(1).isdigit():
        return None, f"Rating is {m.group(1)}; write {hint}"
    rating = int(m.group(1))
    if not RATING_MIN <= rating <= RATING_MAX:
        return None, f"Rating is {rating}; write {hint}"
    return rating, None


_RATING = re.compile(r"(\d+(?:[.,]\d+)?)(?:\s*(?:/|out\s+of)\s*(\d+))?", re.I)


def _rating_value(text: str) -> str:
    """A Rating line's value as it is read: bold, italic and code marks dropped."""
    return re.sub(r"[*_`]", "", text).strip()


def rating_remark(text: str | None) -> str:
    """The words after a valid rating on its line, such as "the best so far" in "Rating: 5 - the
    best so far", which count as feedback; "" when there are none."""
    m = _RATING.match(_rating_value(text or ""))
    if not m:
        return ""
    return _rating_value(text or "")[m.end():].strip().lstrip(".,;:-").strip()


def _kind_value(kind: str | None) -> str | None:
    if not written(kind):
        return None
    key = name_key(kind or "")
    return next((k for k in KINDS if re.match(re.escape(k) + r"\b", key)), None)


def _parse_round(section: Section) -> Round:
    where = f"{QUICK_ROUNDS} > {section.title}"
    f = fields(section.all_lines(), block=("My thoughts", "What changed"), inline=("Run",))
    thoughts, changed = f.text("My thoughts"), f.values.get("What changed")
    problems = [p for p in [_problem(where, "My thoughts", thoughts, _bold_missing("My thoughts"))] if p]
    kind = files = why = None
    if changed is None:
        problems.append(f"{where}: {_bold_missing('What changed')} (Kind, Files and Why go under it)")
    else:
        g = fields(changed, block=("Kind", "Files", "Why"))
        kind, files, why = g.text("Kind"), g.text("Files"), g.text("Why")
        for name, text in (("Kind", kind), ("Files", files), ("Why", why)):
            p = _problem(where, name, text, _bullet_missing(name, "What changed"))
            if p:
                problems.append(p)
    value = _kind_value(kind)
    if written(kind) and value is None:
        problems.append(f"{where}: Kind is {kind!r}; write one of {', '.join(KINDS)}")
    return Round(
        title=section.title, line=section.line, optional="optional" in name_key(section.title), run=f.text("Run"),
        thoughts=thoughts, kind=kind, files=files, why=why, kind_value=value, problems=problems,
    )  # fmt: skip


def _parse_criterion(section: Section, job: str, where: str) -> Criterion:
    f = fields(section.all_lines(), inline=("Rating",))
    rating_text = f.text("Rating")
    rating, problem = parse_rating(rating_text, f.counts.get("Rating", 0))
    remark = rating_remark(rating_text) if rating is not None else ""
    feedback = "\n".join(t for t in (remark, f.rest_text()) if t)
    problems = [f"{where}: {problem}"] if problem else []
    if not feedback:
        problems.append(f"{where}: no feedback below the rating (say why, with quotes or item ids)")
    elif has_todo(feedback):
        problems.append(f"{where}: the feedback is still TODO")
    return Criterion(job, section.title, rating, rating_text, feedback, problems)


def _body(section: Section) -> list[str]:
    """The text lines under a heading, its sub-sections' included, without the headings."""
    out = [ln.text for ln in section.lines]
    for c in section.children:
        out += _body(c)
    return out


def _live_tries_below(section: Section, step: str) -> str:
    """The text of ## Major review's sub-sections before its first job or closing section: Live
    tries runs up to there, so a student may give each live try a heading of its own."""
    stops = {name_key(n) for n in (*CRITERIA, *closing_sections(step))}
    out: list[str] = []
    for c in section.children:
        if c.level == 3 and name_key(c.title) in stops:
            break
        out += _body(c)
    return "\n".join(out).strip()


def _parse_major(doc: Section, step: str) -> MajorReview:
    section = doc.find(MAJOR_REVIEW, 2)
    if section is None:
        missing = f"## {MAJOR_REVIEW} is missing" + _misplaced(doc, MAJOR_REVIEW, 2, "the file's # heading") + f" (the template's {step_file(step)} has it; copy it back)"
        return MajorReview(False, None, None, None, {}, {}, [missing])
    where = MAJOR_REVIEW
    f = fields(section.lines, block=("Live tries",), inline=("Run",))
    run, live = f.text("Run"), f.text("Live tries")
    if live is not None:
        live = "\n".join(t for t in (live, _live_tries_below(section, step)) if t)
    problems = []
    example = f"bench/runs/{step}/<run-id>"
    run_id = None
    p = _problem(where, "Run", run, f"no **Run:** line (write **Run:** {example}, the run you reviewed)")
    ref = run_ref(run, step) if p is None else None
    if p:
        problems.append(p + ("" if run is None else f"; name the run you reviewed ({example})"))
    elif ref is None and _PLACEHOLDER.search(run or ""):
        problems.append(f"{where}: Run is still the placeholder {run!r}; name the run you reviewed ({example})")
    else:
        if ref is None:
            problems.append(f"{where}: Run is {run!r}; write the folder of the run you reviewed, {example}")
        elif ref[0] != step:
            problems.append(f"{where}: Run names a run of {ref[0]}; the major review of {step} reviews a full run of {step} ({example})")
        else:
            run_id = ref[1]
    p = _problem(where, "Live tries", live, _bold_missing("Live tries") + " (what you tried in tutor/ yourself)")
    if p:
        problems.append(p)
    criteria: dict[tuple[str, str], Criterion] = {}
    for job, names in CRITERIA.items():
        required = job in STEP_JOBS[step]
        job_section = section.child(job, 3)
        job_where = f"{where} > {job}"
        if job_section is None:
            if required:
                problems.append(f"{job_where}: missing; add ### {job} with its {len(names)} criteria" + _misplaced(doc, job, 3, f"## {MAJOR_REVIEW}"))
            continue
        for name in names:
            c_section = job_section.child(name, 4)
            c_where = f"{job_where} > {name}"
            if c_section is None:
                if required:
                    problems.append(f"{c_where}: missing; add #### {name}" + _misplaced(doc, name, 4, f"### {job}"))
                continue
            criterion = _parse_criterion(c_section, job, c_where)
            criteria[(job, name)] = criterion
            if required:
                problems += criterion.problems
    closing: dict[str, str | None] = {}
    for name in closing_sections(step):
        c_section = section.child(name, 3)
        if c_section is None:
            closing[name] = None
            problems.append(f"{where} > {name}: missing; add ### {name}" + _misplaced(doc, name, 3, f"## {MAJOR_REVIEW}"))
            continue
        closing[name] = c_section.text()
        p = _problem(f"{where} > {name}", "the text", closing[name], "")
        if p:
            problems.append(p)
    return MajorReview(True, run, run_id, live, criteria, closing, problems)


def _parse_sessions(doc: Section) -> tuple[list[Session], str | None]:
    section = doc.find(LEARNING_SESSIONS, 2)
    if section is None:
        return [], f"## {LEARNING_SESSIONS} is missing" + _misplaced(doc, LEARNING_SESSIONS, 2, "the file's # heading") + " (the template's reviews/final.md has it; copy it back)"
    sessions = []
    for c in section.children:
        if c.level != 3 or not _SESSION.match(name_key(c.title)):
            continue
        where = f"{LEARNING_SESSIONS} > {c.title}"
        f = fields(c.all_lines(), inline=("Date", "Topic"))
        date, topic, text = f.text("Date"), f.text("Topic"), f.rest_text()
        problems = [p for p in (_problem(where, "Date", date, _bold_missing("Date")), _problem(where, "Topic", topic, _bold_missing("Topic"))) if p]
        if not text:
            problems.append(f"{where}: no text below Date and Topic (how the session went)")
        elif has_todo(text):
            problems.append(f"{where}: the text is still TODO")
        words = name_key(topic or "").split()
        topic_id = words[0].strip(",.;:()[]'\"") if written(topic) and words else ""
        sessions.append(Session(c.title, c.line, date, topic, topic_id, text, problems))
    return sessions, None


def _parse_topics(doc: Section) -> tuple[list[TopicReview], str | None]:
    section = doc.find(TEST_TOPICS, 2)
    if section is None:
        return [], f"## {TEST_TOPICS} is missing" + _misplaced(doc, TEST_TOPICS, 2, "the file's # heading") + " (the template's reviews/final.md has it; copy it back)"
    topics = []
    for c in section.children:
        if c.level != 3:
            continue
        where = f"{TEST_TOPICS} > {c.title}"
        words = name_key(c.title).split()
        text = c.text()
        problems = []
        if not text:
            problems.append(f"{where}: no text below the heading (how c0-baseline and final compare on it)")
        elif has_todo(text):
            problems.append(f"{where}: the text is still TODO")
        topics.append(TopicReview(c.title, c.line, words[0] if words else "", text, problems))
    return topics, None


def parse_step(text: str, step: str, path: str | None = None) -> StepReview:
    """reviews/<step>.md from its text."""
    if step not in STEPS:
        raise ValueError(f"no review file for {step!r}; the steps are {', '.join(STEPS)}")
    doc = parse_markdown(text)
    rounds_section = doc.find(QUICK_ROUNDS, 2)
    rounds, rounds_problem = [], None
    if rounds_section is None:
        if MIN_ROUNDS[step]:
            rounds_problem = f"## {QUICK_ROUNDS} is missing" + _misplaced(doc, QUICK_ROUNDS, 2, "the file's # heading") + f" (the template's {step_file(step)} has it; copy it back)"
    else:
        rounds = [_parse_round(c) for c in rounds_section.children if c.level == 3 and _ROUND.match(name_key(c.title))]
    sessions, sessions_problem, topics, topics_problem = [], None, [], None
    if step == "final":
        sessions, sessions_problem = _parse_sessions(doc)
        topics, topics_problem = _parse_topics(doc)
    return StepReview(
        step=step, path=path or step_file(step), rounds=rounds, rounds_problem=rounds_problem, major=_parse_major(doc, step),
        sessions=sessions, sessions_problem=sessions_problem, topics=topics, topics_problem=topics_problem,
    )  # fmt: skip


def read_step(step: str, root: Path | None = None) -> StepReview | None:
    """reviews/<step>.md of the repo, parsed; None when the file is not there."""
    root = Path(root) if root else util.repo_root()
    path = root / step_file(step)
    if not path.is_file():
        return None
    return parse_step(util.read_text(path), step)


def all_ratings(root: Path | None = None) -> dict[str, dict[tuple[str, str], int]]:
    """{step: {(job, criterion): rating}} of every valid rating in the step files there are."""
    found = {}
    for step in STEPS:
        review = read_step(step, root)
        if review is not None:
            found[step] = review.major.ratings()
    return found


# ---- the component inventory ----


@dataclass
class Entry:
    """One entry of reviews/components.md."""

    title: str  # the heading as written
    key: str  # name_key of the heading: what a component's name is matched with
    line: int
    values: dict[str, str | None]  # COMPONENT_FIELDS
    kind: str | None  # skill or subagent, when Kind is one
    step: str | None  # Step added's first word, case folded
    kept: bool | None  # Kept in final: yes or no
    problems: list[str]
    labeled: bool = True  # holds at least one of the six field labels (without any, it may be prose)

    @property
    def complete(self) -> bool:
        return not self.problems

    @property
    def touched(self) -> bool:
        """True once any of its fields is written."""
        return any(written(v) for v in self.values.values())


def _parse_entry(section: Section) -> Entry:
    title = section.title
    where = title or "(a ### heading with no name)"
    f = fields(section.all_lines(), block=COMPONENT_FIELDS)
    values = {name: f.text(name) for name in COMPONENT_FIELDS}
    problems = []
    shown = re.sub(r"[*`]", "", title).strip()
    if not shown or TODO_MARK in shown or _PLACEHOLDER.search(shown):
        problems.append(f"{where}: give the entry its component's name (the skill's folder name, or the subagent's name)")
    for name in COMPONENT_FIELDS:
        p = _problem(where, name, values[name], _bullet_missing(name))
        if p:
            problems.append(p)
    kind = step = kept = None
    if written(values["Kind"]):
        words = name_key(values["Kind"] or "").split()
        kind = words[0].rstrip(".,;") if words and words[0].rstrip(".,;") in (SKILL, SUBAGENT) else None
        if kind is None:
            problems.append(f"{where}: Kind is {values['Kind']!r}; write skill or subagent")
    if written(values["Step added"]):
        words = name_key(values["Step added"] or "").split()
        step = words[0].rstrip(".,;") if words else None
    if written(values["Kept in final"]):
        key = name_key(values["Kept in final"] or "")
        m = re.match(r"(yes|no)\b", key)
        if m is None:
            problems.append(f"{where}: Kept in final is {values['Kept in final']!r}; start it with yes or no (no, because ...)")
        else:
            kept = m.group(1) == "yes"
            if not kept and not re.sub(r"^no\b[\s,.;:-]*", "", key):
                problems.append(f"{where}: Kept in final is no, with no reason; write no, because ...")
    return Entry(title, name_key(title), section.line, values, kind, step, kept, problems, labeled=bool(f.values))


def parse_components(text: str) -> list[Entry]:
    """The entries of reviews/components.md: every ### heading in it (the example inside the
    template's HTML comment is not one). p3 check treats one with no field label (Entry.labeled
    False) that names no component built as prose."""
    return [_parse_entry(s) for s in parse_markdown(text).walk() if s.level == 3]


def read_components(root: Path | None = None) -> list[Entry] | None:
    """reviews/components.md of the repo, parsed; None when the file is not there."""
    root = Path(root) if root else util.repo_root()
    path = root / COMPONENTS_PATH
    if not path.is_file():
        return None
    return parse_components(util.read_text(path))


# ---- the components a config holds ----


def skill_names(folder: Path) -> list[str]:
    """The skills of a config folder: each folder under .claude/skills/ that holds a SKILL.md."""
    base = Path(folder) / ".claude" / "skills"
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def subagent_name(path: Path) -> str | None:
    """A subagent's name: the `name` in its file's frontmatter, which opens with --- on the first
    line and closes with --- on a later one; None for a file with no such frontmatter or no name in
    it, which Claude Code does not load as a subagent (it is documentation, such as a checklist)."""
    lines = util.read_text(path).lstrip("\ufeff").split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        return None
    for line in lines[1:end]:
        m = re.match(r"^name\s*:\s*(.*?)\s*$", line)
        if m:
            return m.group(1).strip().strip("'\"").strip() or None
    return None


def _agent_files(folder: Path) -> Iterator[tuple[str, str | None]]:
    """(path relative to the folder, subagent name or None) of each .md file under a config
    folder's .claude/agents/ (subfolders included), README.md left out."""
    base = Path(folder) / ".claude" / "agents"
    for rel in util.list_files(base):
        leaf = rel.rsplit("/", 1)[-1].lower()
        if leaf.endswith(".md") and leaf != "readme.md":
            yield f".claude/agents/{rel}", subagent_name(base / rel)


def subagents(folder: Path) -> dict[str, str]:
    """{name: path relative to the folder} of a config folder's subagents: each .md file under
    .claude/agents/ (subfolders included, README.md left out) whose frontmatter has a name."""
    found: dict[str, str] = {}
    for rel, name in _agent_files(folder):
        if name is not None:
            found.setdefault(name, rel)
    return found


def agent_docs(folder: Path) -> list[str]:
    """The paths (relative to the folder) of the .md files under .claude/agents/ that are not
    subagents, because their frontmatter is missing or has no name; README.md is left out."""
    return [rel for rel, name in _agent_files(folder) if name is None]
