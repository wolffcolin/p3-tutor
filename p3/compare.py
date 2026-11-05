"""`p3 compare`: a blind side-by-side comparison of two configs' outputs, then the reveal.

    p3 compare <config-a> <config-b> --job teach|quiz|grade|tutor [--topic t] [--minutes M] [--quick]
               [--teach-only] [--terminal] [--port P]
    p3 compare --resume <session-id> [--terminal] [--port P]
    p3 compare --reveal <session-id>
    p3 compare --list

- The pairs come from the scored full runs of the two configs on the topic (quick runs and --only
  runs left out; --quick pairs quick runs instead, and --teach-only, with --job teach, the runs of
  the teach scenario alone, as the length study makes them), at one lesson length (the topic's,
  unless --minutes says otherwise), matched by repeat order, oldest first, min(nA, nB) run pairs. Teach: the two lessons of each run pair. Quiz: the two
  quizzes, each with its key. Grade: one pair per item per submission (the item and the learner's
  response, then each version's verdict and feedback). Tutor: one pair per probe (the message, then
  each reply). No model is called.
- Which config is on the left is decided for each pair by random.Random(seed), with the seed from
  secrets. The mapping and the seed go in bench/compare/<session>.key.json, which no page reads;
  bench/compare/<session>.json holds the pairs and the picks, and each pick is saved as it is made.
- Server mode (the default) serves one page per pair on 127.0.0.1 and opens it in the browser:
  lessons in sandboxed frames served from the run's outputs, the other jobs as escaped HTML.
  --terminal writes each pair as an HTML file and asks the three questions in the terminal.
- --reveal prints the tally, the exact two-sided sign test, how often you could tell, your reasons
  grouped by the config that won, the objective checks, and only then the cost per scenario; it
  also writes the reveal into the session file.
"""

from __future__ import annotations

import html
import math
import mimetypes
import os
import random
import re
import secrets
import sys
import tempfile
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from fractions import Fraction
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socketserver import TCPServer
from typing import Callable
from urllib.parse import parse_qs, quote, unquote, urlsplit

from p3 import config, report, topic, util
from p3.claude import COST_LABEL
from p3.score import SUMMARY_LABELS, option_choice
from p3.util import P3Error

JOBS = ("teach", "quiz", "grade", "tutor")
CHOICES = ("left", "right", "tie")
SIDES = ("left", "right")
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
READING_LINE = "With 10 pairs, 8 or more is suggestive and 9 or more strong."
MAX_REASON = 2000
MAX_POST = 64 * 1024
DONE_GRACE_S = 2.0
JOB_NOUN = {"teach": "lesson", "quiz": "quiz", "grade": "graded answer", "tutor": "tutor reply"}
JOB_HINT = {
    "teach": "Two lessons on the same objective. Skim both, then pick the one that would have fit you better as a learner.",
    "quiz": "Two quizzes on the same objective, each shown with its answer key.",
    "grade": "One learner answer, graded twice. Compare the verdicts and the feedback.",
    "tutor": "One message from the learner, answered twice.",
}
_KINDS = {key: kind for key, _label, kind in report.QUALITY}
CHECKS = {job: [(key, label.split(": ", 1)[-1], _KINDS.get(key, "count")) for key, label in SUMMARY_LABELS if key.startswith(job + "_")] for job in JOBS}
COST_COLUMNS = (("tokens", "tokens", "tokens"), ("output", "output tokens", "tokens"), ("minutes", "minutes", "minutes"), ("subagents", "subagents", "count"), ("cost", "list-price $", "usd"))


# ---- sessions on disk ----


def compare_dir(root: Path) -> Path:
    return Path(root) / "bench" / "compare"


def session_id(arg: str) -> str:
    """A session id from an id, a file name such as <id>.json, or a path to one."""
    name = Path(str(arg).strip()).name
    for suffix in (".key.json", ".json"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    if not SESSION_ID_RE.match(name):
        raise P3Error(f"{arg!r} is not a session id; p3 compare --list shows them")
    return name


def session_path(sid: str, root: Path) -> Path:
    return compare_dir(root) / f"{sid}.json"


def key_path(sid: str, root: Path) -> Path:
    return compare_dir(root) / f"{sid}.key.json"


def session_files(root: Path) -> list[Path]:
    """Every session record in bench/compare/ (not the key files), sorted by name."""
    base = compare_dir(root)
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if p.is_file() and p.name.endswith(".json") and not p.name.endswith(".key.json"))


# ---- pairing and blinding ----


def runs_for(config_name: str, topic_id: str, job: str, minutes: int | None, quick: bool, root: Path, teach_only: bool = False) -> list[util.RunRecord]:
    """The scored runs of one kind (full runs, or teach-only runs with `teach_only`) of a config on a
    topic that ran the job, oldest first. A run made with --only for some other scenario is never
    paired, so it cannot take a full run's place in the repeat order."""
    kind = util.TEACH_ONLY if teach_only else util.FULL
    recs = util.list_runs(config_name, topic_id, scored=True, minutes=minutes, quick=quick, kind=kind, root=root)
    return [r for r in recs if any(s.get("job") == job for s in r.run.get("scenarios") or [])]


def scenario_ids(run: dict, job: str) -> list[str]:
    return [str(s["id"]) for s in run.get("scenarios") or [] if s.get("job") == job and s.get("id")]


def quiz_item_ids(tp: topic.Topic) -> list[str]:
    """The item ids of the topic's graded quiz, in quiz order."""
    quiz = tp.quiz(tp.graded_quiz)
    return [str(i["id"]) for i in quiz.get("items") or [] if isinstance(i, dict) and i.get("id")]


def pair_items(job: str, run_a: dict, run_b: dict, tp: topic.Topic) -> list[str]:
    """What one pair of runs gives for a job, as item strings: the scenario id for teach, quiz and
    tutor (one pair per probe), and "<scenario id>/<quiz item id>" for grade (one pair per item per
    submission). Only scenarios both runs have are paired."""
    in_b = set(scenario_ids(run_b, job))
    common = [sid for sid in scenario_ids(run_a, job) if sid in in_b]
    if job in ("teach", "quiz"):
        return common[:1]
    if job == "tutor":
        return common
    items = quiz_item_ids(tp)
    return [f"{sid}/{iid}" for sid in common for iid in items]


def build_pairs(job: str, recs_a: list[util.RunRecord], recs_b: list[util.RunRecord], tp: topic.Topic) -> list[dict]:
    """The pairs of a session: run pairs by repeat order (oldest first, min(nA, nB) of them), then
    the job's items within each run pair. Each pair is {"pair_id", "run_pair": [run a, run b], "item"}."""
    pairs: list[dict] = []
    for ra, rb in zip(recs_a, recs_b):
        for item in pair_items(job, ra.run, rb.run, tp):
            pairs.append({"pair_id": f"{len(pairs) + 1:03d}", "run_pair": [ra.dir.name, rb.dir.name], "item": item})
    return pairs


def assign_sides(pair_ids: list[str], configs: list[str], seed: int) -> dict[str, dict[str, str]]:
    """{pair_id: {"left": config, "right": config}}, decided for each pair in order by
    random.Random(seed): the same seed always gives the same sides."""
    rng = random.Random(seed)
    a, b = configs
    sides = {}
    for pid in pair_ids:
        left = a if rng.random() < 0.5 else b
        sides[pid] = {"left": left, "right": b if left == a else a}
    return sides


def _missing_runs_message(name: str, topic_id: str, job: str, minutes: int, quick: bool, root: Path, teach_only: bool = False) -> str:
    kind = ("quick " if quick else "") + ("teach-only" if teach_only else "full")
    if quick and not teach_only:
        kind = "quick"
    wanted = util.TEACH_ONLY if teach_only else util.FULL
    msg = f"{name} has no scored {kind} run on {topic_id} at {minutes} minutes that ran the {job} job"
    every = util.list_runs(name, topic_id, root=root)
    unscored = [r for r in every if not r.scored]
    other_kind = [r for r in every if r.scored and bool(r.run.get("quick")) != quick and util.run_kind(r.run) == wanted]
    same = [r for r in every if r.scored and bool(r.run.get("quick")) == quick and util.run_kind(r.run) == wanted]
    other_length = sorted({int(r.run.get("minutes") or 0) for r in same if r.run.get("minutes") != minutes})
    teach_runs = [r for r in every if r.scored and bool(r.run.get("quick")) == quick and r.run.get("minutes") == minutes and util.run_kind(r.run) == util.TEACH_ONLY]
    hints = []
    if not every:
        hints.append(f"run it first: p3 bench --config {name}" + (f" --topic {topic_id}" if topic_id != util.SHARED_TOPIC else ""))
    if unscored:
        hints.append(f"{len(unscored)} of its runs on {topic_id} {'is' if len(unscored) == 1 else 'are'} not scored; score with p3 score {util.posix(unscored[-1].dir, root)}")
    if other_kind:
        hints.append(f"it has {len(other_kind)} scored {'full' if quick else 'quick'} run{'s' if len(other_kind) != 1 else ''}; the comparison uses {kind} runs" + ("" if quick else " (add --quick to pair quick runs, for trying the tool out)"))
    if other_length:
        hints.append(f"its scored {kind} runs are at {', '.join(map(str, other_length))} minutes (pick a length with --minutes M)")
    if teach_runs and not teach_only and job == "teach":
        hints.append(f"it has {len(teach_runs)} scored teach-only run{'s' if len(teach_runs) != 1 else ''} at {minutes} minutes (add --teach-only to pair those, as the length study does)")
    return msg + (": " + "; ".join(hints) if hints else "")


def new_session(
    config_a: str, config_b: str, job: str, topic_id: str = util.SHARED_TOPIC, *,
    minutes: int | None = None, quick: bool = False, teach_only: bool = False, seed: int | None = None, root: Path | None = None, when=None,
) -> dict:
    """Pair the two configs' runs, blind the pairs, and write bench/compare/<session>.key.json and
    <session>.json; returns the session record. Refuses when either config has no scored run."""
    root = Path(root) if root else util.repo_root()
    if job not in JOBS:
        raise P3Error(f"--job must be one of {', '.join(JOBS)}")
    if teach_only and job != "teach":
        raise P3Error("--teach-only pairs the runs of the teach scenario alone, so it goes with --job teach")
    for name in (config_a, config_b):
        if name == util.LIVE_CONFIG:
            raise P3Error("live runs are not committed and cannot be compared; snapshot the tutor (p3 snapshot <name>) and bench the snapshot")
        config.check_name(name)
        util.load_snapshot(name, root)
    if config_a == config_b:
        raise P3Error(f"a comparison needs two different configs, and both are {config_a}; snapshot the other version under its own name first")
    tp = topic.load(topic_id, root)
    minutes = int(minutes) if minutes else tp.minutes
    recs_a = runs_for(config_a, tp.id, job, minutes, quick, root, teach_only)
    recs_b = runs_for(config_b, tp.id, job, minutes, quick, root, teach_only)
    missing = [_missing_runs_message(n, tp.id, job, minutes, quick, root, teach_only) for n, recs in ((config_a, recs_a), (config_b, recs_b)) if not recs]
    if missing:
        raise P3Error("nothing to compare: " + "; and ".join(missing))
    pairs = build_pairs(job, recs_a, recs_b, tp)
    if not pairs:
        raise P3Error(f"the runs of {config_a} and {config_b} on {tp.id} have no {job} scenario in common")
    seed = secrets.randbits(64) if seed is None else int(seed)
    base = compare_dir(root)
    base.mkdir(parents=True, exist_ok=True)
    while True:
        sid = f"{util.stamp(when)}-{job}"
        if not session_path(sid, root).exists() and not key_path(sid, root).exists():
            break
        if when is not None:
            raise P3Error(f"a session {sid} already exists")
        time.sleep(1)
    configs = [config_a, config_b]
    record = {
        "session": sid,
        "job": job,
        "topic": tp.id,
        "configs": configs,
        "created_at": util.iso_utc(when),
        "minutes": minutes,
        "quick": bool(quick),
        "teach_only": bool(teach_only),
        "pairs": pairs,
        "picks": [],
        "complete": False,
    }
    key = {"seed": seed, "pairs": assign_sides([p["pair_id"] for p in pairs], configs, seed)}
    util.replace_json(key_path(sid, root), key)  # the key first, so a session never exists without one
    util.replace_json(session_path(sid, root), record)
    return record


# ---- one loaded session ----


@dataclass
class SideRun:
    """One side of a pair: the config, its run folder, and the parsed run.json and score.json."""

    config: str
    run_id: str
    dir: Path
    run: dict
    score: dict | None

    def scenario(self, sid: str) -> dict | None:
        return next((s for s in self.run.get("scenarios") or [] if s.get("id") == sid), None)

    def outputs_dir(self, sid: str) -> Path:
        return self.dir / sid / "outputs"

    def job_score(self, job: str) -> dict:
        jobs = (self.score or {}).get("jobs") or {}
        return jobs.get(job) or {}


class Session:
    """A comparison session loaded from bench/compare/: the record, its key, and the runs behind
    each pair. record() saves a pick at once."""

    def __init__(self, sid: str, root: Path | None = None):
        self.root = Path(root) if root else util.repo_root()
        self.id = session_id(sid)
        self.path = session_path(self.id, self.root)
        self.key_path = key_path(self.id, self.root)
        if not self.path.is_file():
            raise P3Error(f"there is no session {self.id} (no {util.posix(self.path, self.root)}); p3 compare --list shows them")
        self.data = util.read_json(self.path)
        if not self.key_path.is_file():
            raise P3Error(f"the key file of session {self.id} is missing ({util.posix(self.key_path, self.root)}), so its pairs cannot be shown or revealed")
        self.key = util.read_json(self.key_path)
        problems = record_problems(self.data, self.key)
        if problems:
            raise P3Error(f"session {self.id} is broken: " + "; ".join(problems))
        gone = sorted({
            f"bench/runs/{name}/{pair['run_pair'][n]}" for pair in self.data["pairs"] for n, name in enumerate(self.data["configs"])
            if not (util.runs_dir(name, self.root) / pair["run_pair"][n] / "run.json").is_file()
        })  # fmt: skip
        if gone:
            raise P3Error(f"session {self.id} uses runs that no longer exist: {', '.join(gone)}")
        self.lock = threading.Lock()
        self._runs: dict[tuple[str, str], SideRun] = {}
        self._topic: topic.Topic | None = None

    @property
    def job(self) -> str:
        return self.data["job"]

    @property
    def configs(self) -> list[str]:
        return list(self.data["configs"])

    @property
    def pairs(self) -> list[dict]:
        return self.data["pairs"]

    @property
    def picks(self) -> list[dict]:
        return self.data.get("picks") or []

    @property
    def topic(self) -> topic.Topic:
        if self._topic is None:
            self._topic = topic.load(self.data["topic"], self.root)
        return self._topic

    def pick_for(self, pair_id: str) -> dict | None:
        return next((p for p in self.picks if p.get("pair_id") == pair_id), None)

    def answered(self) -> int:
        ids = {p["pair_id"] for p in self.pairs}
        return len({p.get("pair_id") for p in self.picks} & ids)

    def next_open(self) -> int | None:
        """The 1-based number of the first pair without a pick, or None when every pair has one."""
        return next((k for k, p in enumerate(self.pairs, 1) if self.pick_for(p["pair_id"]) is None), None)

    def side(self, pair: dict, which: str) -> SideRun:
        """The run shown on one side ("left" or "right") of a pair."""
        name = self.key["pairs"][pair["pair_id"]][which]
        run_id = pair["run_pair"][self.configs.index(name)]
        cached = self._runs.get((name, run_id))
        if cached is None:
            folder = util.runs_dir(name, self.root) / run_id
            if not (folder / "run.json").is_file():
                raise P3Error(f"a run of session {self.id} no longer exists ({util.posix(folder, self.root)}/run.json)")
            run = util.read_json(folder / "run.json")
            score = None
            if (folder / "score.json").is_file():
                try:
                    score = util.read_json(folder / "score.json")
                except P3Error:
                    score = None
            cached = SideRun(name, run_id, folder, run if isinstance(run, dict) else {}, score if isinstance(score, dict) else None)
            self._runs[(name, run_id)] = cached
        return cached

    def record(self, pair_id: str, choice: str, reason: str, could_tell: bool) -> dict:
        """Save one pick (replacing an earlier pick for the same pair) and return it."""
        with self.lock:
            if self.data.get("revealed"):
                raise P3Error(f"session {self.id} has been revealed, so its picks are final")
            if not any(p["pair_id"] == pair_id for p in self.pairs):
                raise P3Error(f"session {self.id} has no pair {pair_id}")
            if choice not in CHOICES:
                raise P3Error("the choice must be left, right or tie")
            reason = " ".join(str(reason or "").split())
            if not reason:
                raise P3Error("say why, in one sentence")
            if not isinstance(could_tell, bool):
                raise P3Error("could you tell must be yes or no")
            pick = {"pair_id": pair_id, "choice": choice, "reason": reason[:MAX_REASON], "could_tell": could_tell, "picked_at": util.iso_utc()}
            order = {p["pair_id"]: n for n, p in enumerate(self.pairs)}
            picks = [p for p in self.picks if p.get("pair_id") != pair_id] + [pick]
            picks.sort(key=lambda p: order.get(p.get("pair_id"), len(order)))
            self.data["picks"] = picks
            self.data["complete"] = self.answered() == len(self.pairs)
            util.replace_json(self.path, self.data)
            return pick


def record_problems(record, key) -> list[str]:
    """What is wrong with a session record and its key (empty when nothing is)."""
    if not isinstance(record, dict):
        return ["the session file must hold a JSON object"]
    problems = []
    for name in ("session", "job", "topic", "configs", "pairs"):
        if name not in record:
            problems.append(f"no {name}")
    if problems:
        return problems
    configs = record["configs"]
    if not (isinstance(configs, list) and len(configs) == 2 and all(isinstance(c, str) for c in configs) and configs[0] != configs[1]):
        return ["configs must name two different configs"]
    if record["job"] not in JOBS:
        problems.append(f"job {record['job']!r} is not one of {', '.join(JOBS)}")
    pairs = record["pairs"]
    if not isinstance(pairs, list) or not all(isinstance(p, dict) and isinstance(p.get("pair_id"), str) and isinstance(p.get("run_pair"), list) and len(p["run_pair"]) == 2 for p in pairs):
        return problems + ["every pair needs a pair_id and a run_pair of two run ids"]
    ids = [p["pair_id"] for p in pairs]
    if len(set(ids)) != len(ids):
        problems.append("a pair id is used twice")
    if not isinstance(key, dict) or not isinstance(key.get("pairs"), dict):
        return problems + ["the key file has no pairs"]
    for pid in ids:
        sides = key["pairs"].get(pid)
        if not isinstance(sides, dict) or sorted([sides.get("left"), sides.get("right")], key=str) != sorted(configs):
            problems.append(f"the key has no left and right for pair {pid}")
    for pick in record.get("picks") or []:
        if not isinstance(pick, dict) or pick.get("pair_id") not in ids or pick.get("choice") not in CHOICES:
            problems.append(f"a pick does not fit the pairs: {pick!r}"[:200])
    return problems


# ---- what each side shows ----


def _read_json_or_none(path: Path):
    try:
        return util.read_json(path)
    except P3Error:
        return None


def _new_outputs(entry: dict | None) -> list[str]:
    if not entry:
        return []
    changed = set(entry.get("changed") or [])
    return [p for p in entry.get("outputs") or [] if p not in changed]


def lesson_of(side: SideRun, sid: str) -> tuple[str | None, str | None]:
    """(the lesson's path inside the scenario's outputs, a note) for a teach side: the lesson the
    scorer used, else the one new lessons/*.html."""
    out = side.outputs_dir(sid)
    rel = side.job_score("teach").get("lesson")
    if isinstance(rel, str) and (out / rel).is_file():
        return rel, None
    lessons = sorted(p for p in _new_outputs(side.scenario(sid)) if re.match(r"^lessons/[^/]+\.html?$", p) and (out / p).is_file())
    if not lessons:
        return None, None
    note = f"This version wrote {len(lessons)} lessons; this is the first." if len(lessons) > 1 else None
    return lessons[0], note


def quiz_of(side: SideRun, sid: str) -> tuple[str | None, object, object]:
    """(quiz path, parsed quiz or the raw text when it does not parse, parsed key or None)."""
    out = side.outputs_dir(sid)
    scored = side.job_score("quiz")
    rel = scored.get("quiz") if isinstance(scored.get("quiz"), str) else None
    key_rel = scored.get("key") if isinstance(scored.get("key"), str) else None
    if rel is None or not (out / rel).is_file():
        quizzes = sorted(p for p in _new_outputs(side.scenario(sid)) if re.match(r"^quizzes/[^/]+\.json$", p) and (out / p).is_file())
        rel = quizzes[-1] if quizzes else None
        key_rel = f"keys/{Path(rel).stem}.json" if rel else None
    if rel is None:
        return None, None, None
    quiz = _read_json_or_none(out / rel)
    if quiz is None:
        quiz = util.read_text(out / rel)
    key = _read_json_or_none(out / key_rel) if key_rel and (out / key_rel).is_file() else None
    return rel, quiz, key


def grade_of(side: SideRun, sid: str, submission: str, item_id: str, graded_quiz: str) -> tuple[str, dict | None]:
    """("ok" | "no-file" | "bad-file" | "no-item", the grade entry for the item)."""
    out = side.outputs_dir(sid)
    subs = side.job_score("grade").get("submissions") or {}
    rel = (subs.get(submission) or {}).get("grades") if isinstance(subs, dict) else None
    if not isinstance(rel, str) or not (out / rel).is_file():
        found = sorted(p for p in (side.scenario(sid) or {}).get("outputs") or [] if re.match(rf"^grades/[^/]*-{re.escape(submission)}\.json$", p) and (out / p).is_file())
        preferred = f"grades/{graded_quiz}-{submission}.json"
        rel = preferred if preferred in found else (found[-1] if found else None)
    if rel is None:
        return "no-file", None
    doc = _read_json_or_none(out / rel)
    if not isinstance(doc, dict):
        return "bad-file", None
    entry = next((i for i in doc.get("items") or [] if isinstance(i, dict) and str(i.get("id")) == item_id), None)
    return ("ok", entry) if entry is not None else ("no-item", None)


def reply_of(side: SideRun, sid: str) -> str | None:
    result = _read_json_or_none(side.dir / sid / "result.json")
    reply = result.get("result") if isinstance(result, dict) else None
    return reply if isinstance(reply, str) and reply.strip() else None


# ---- HTML ----


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


_TOKEN = "\x00{}\x00"
_CODE_RE = re.compile(r"`([^`\n]+)`")
_LINK_RE = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)")
_URL_RE = re.compile(r"(?<![\w/\"'=])(https?://[^\s<>\"')\]]+[^\s<>\"')\].,;:!?])")
_EMPHASIS = (
    (re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<![\w_])__(?=\S)(.+?)(?<=\S)__(?![\w_])"), r"<strong>\1</strong>"),
    (re.compile(r"(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])"), r"<em>\1</em>"),
    (re.compile(r"(?<![\w_])_(?=[^\s_])(.+?)(?<=[^\s_])_(?![\w_])"), r"<em>\1</em>"),
)


def inline(text: str) -> str:
    """One line of Markdown-ish text as safe HTML: code spans, links, bold and italic; everything
    else escaped."""
    saved: list[str] = []

    def keep(fragment: str) -> str:
        saved.append(fragment)
        return _TOKEN.format(len(saved) - 1)

    def link(url: str, label: str) -> str:
        return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{label}</a>'

    text = text.replace("\x00", "")
    text = _CODE_RE.sub(lambda m: keep(f"<code>{esc(m.group(1))}</code>"), text)
    text = _LINK_RE.sub(lambda m: keep(link(m.group(2), esc(m.group(1)))), text)
    text = _URL_RE.sub(lambda m: keep(link(m.group(1), esc(m.group(1)))), text)
    text = esc(text)
    for pattern, replacement in _EMPHASIS:
        text = pattern.sub(replacement, text)
    return re.sub(r"\x00(\d+)\x00", lambda m: saved[int(m.group(1))], text)


def md(text) -> str:
    """Markdown-ish text (what tutors and graders write) as safe HTML: paragraphs with their line
    breaks, headings, lists, quotes, fenced code and pipe tables. Every character of the input is
    escaped; nothing in it can add a tag or an attribute of its own."""
    if not isinstance(text, str) or not text.strip():
        return ""
    out: list[str] = []
    para: list[str] = []
    items: list[str] = []
    list_tag: str | None = None
    quote_lines: list[str] = []
    table: list[str] = []

    def flush() -> None:
        nonlocal list_tag
        if para:
            out.append("<p>" + "<br>".join(inline(line) for line in para) + "</p>")
            para.clear()
        if items:
            out.append(f"<{list_tag}>" + "".join(f"<li>{inline(i)}</li>" for i in items) + f"</{list_tag}>")
            items.clear()
            list_tag = None
        if quote_lines:
            out.append("<blockquote><p>" + "<br>".join(inline(line) for line in quote_lines) + "</p></blockquote>")
            quote_lines.clear()
        if table:
            out.append(_table(table))
            table.clear()

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("```") or s.startswith("~~~"):
            flush()
            fence = s[:3]
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence):
                code.append(lines[i])
                i += 1
            out.append(f"<pre><code>{esc(chr(10).join(code))}</code></pre>")
            i += 1
            continue
        if not s:
            flush()
        elif table or (s.startswith("|") and s.count("|") >= 2):
            if not (s.startswith("|") and s.count("|") >= 2):
                flush()
                continue
            table.append(s)
        elif m := re.match(r"^(#{1,6})\s+(.+?)\s*#*$", s):
            flush()
            level = min(6, len(m.group(1)) + 2)
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
        elif re.match(r"^([-*_])(\s*\1){2,}$", s):
            flush()
            out.append("<hr>")
        elif m := re.match(r"^[-*+]\s+(.*)$", s):
            if list_tag != "ul":
                flush()
                list_tag = "ul"
            items.append(m.group(1))
        elif m := re.match(r"^\d{1,3}[.)]\s+(.*)$", s):
            if list_tag != "ol":
                flush()
                list_tag = "ol"
            items.append(m.group(1))
        elif s.startswith(">"):
            if para or items or table:
                flush()
            quote_lines.append(s.lstrip(">").strip())
        elif items and line[:1] in (" ", "\t"):
            items[-1] += " " + s
        else:
            if items or quote_lines or table:
                flush()
            para.append(s)
        i += 1
    flush()
    return "\n".join(out)


def _table(rows: list[str]) -> str:
    cells = [[c.strip() for c in row.strip().strip("|").split("|")] for row in rows]
    if len(cells) >= 2 and all(re.match(r"^:?-{2,}:?$", c) for c in cells[1] if c):
        head, body = cells[0], cells[2:]
    else:
        head, body = None, cells
    parts = ["<div class=\"table\"><table>"]
    if head:
        parts.append("<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead>")
    parts.append("<tbody>" + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>" for row in body) + "</tbody>")
    parts.append("</table></div>")
    return "".join(parts)


CSS = """
:root {
  color-scheme: light dark;
  --bg: #f4f5f7; --card: #ffffff; --ink: #1c2128; --muted: #5b6573; --line: #dfe3e8; --soft: #f0f3f7;
  --accent: #2a62d4; --accent-ink: #ffffff; --accent-soft: #e7eefc;
  --ok: #17663f; --ok-bg: #e3f3ea; --mid: #7a4f00; --mid-bg: #fbefd8; --bad: #a3231b; --bad-bg: #fbe6e4;
  --shadow: 0 -6px 24px rgba(20, 30, 45, 0.08);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #121519; --card: #1b1f25; --ink: #e5e8ec; --muted: #9aa3ae; --line: #2d333b; --soft: #20252c;
    --accent: #7ea6ff; --accent-ink: #0f1420; --accent-soft: #1e2a42;
    --ok: #7fd3a4; --ok-bg: #173325; --mid: #f0c272; --mid-bg: #3a2c12; --bad: #ff9a90; --bad-bg: #3d1c19;
    --shadow: 0 -6px 24px rgba(0, 0, 0, 0.4);
  }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--bg); color: var(--ink); min-height: 100vh; display: flex; flex-direction: column;
  font: 16px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
a { color: var(--accent); }
.page { flex: 1 0 auto; width: 100%; max-width: 1480px; margin: 0 auto; padding: 28px 28px 40px; }
header.top { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px 24px; margin-bottom: 6px; }
header.top h1 { font-size: 20px; line-height: 1.3; margin: 0; font-weight: 650; }
header.top .where { color: var(--muted); font-size: 15px; }
header.top .count { margin-left: auto; font-weight: 600; font-variant-numeric: tabular-nums; }
.bar { height: 4px; background: var(--line); border-radius: 2px; overflow: hidden; margin: 10px 0 18px; }
.bar span { display: block; height: 100%; background: var(--accent); }
.hint { color: var(--muted); margin: 0 0 22px; }
.notice { background: var(--mid-bg); color: var(--mid); border-radius: 10px; padding: 12px 16px; margin: 0 0 22px; font-weight: 550; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 22px 26px; min-width: 0; }
.shared { margin-bottom: 24px; }
.cols { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 24px; align-items: start; }
@media (max-width: 920px) { .cols { grid-template-columns: minmax(0, 1fr); } .page { padding: 18px 16px 32px; } }
.label {
  display: inline-block; margin: 0; padding: 3px 12px; border-radius: 999px; line-height: 1.5;
  background: var(--accent-soft); color: var(--accent); font-size: 13px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
}
.side-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
.side-head a { font-size: 14px; }
.meta { color: var(--muted); font-size: 14px; margin-bottom: 6px; }
.empty { color: var(--muted); font-style: italic; margin: 8px 0; }
.frame { width: 100%; height: calc(100vh - 360px); min-height: 460px; border: 1px solid var(--line); border-radius: 10px; background: #ffffff; display: block; }
.prose { overflow-wrap: anywhere; }
.prose > :first-child { margin-top: 0; }
.prose > :last-child { margin-bottom: 0; }
.prose p, .prose ul, .prose ol, .prose blockquote, .prose pre, .prose .table { margin: 0 0 12px; }
.prose h3, .prose h4, .prose h5, .prose h6 { margin: 18px 0 8px; line-height: 1.35; }
.prose h3 { font-size: 19px; } .prose h4 { font-size: 17px; } .prose h5, .prose h6 { font-size: 16px; }
.prose ul, .prose ol { padding-left: 24px; }
.prose li + li { margin-top: 4px; }
.prose blockquote { border-left: 3px solid var(--line); padding-left: 14px; color: var(--muted); }
.prose code { font: 14px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; background: var(--soft); padding: 1px 5px; border-radius: 5px; }
.prose pre { background: var(--soft); padding: 12px 14px; border-radius: 8px; overflow-x: auto; }
.prose pre code { background: none; padding: 0; }
.prose hr { border: 0; border-top: 1px solid var(--line); margin: 16px 0; }
.prose .table { overflow-x: auto; }
.prose table { border-collapse: collapse; font-size: 15px; }
.prose th, .prose td { border: 1px solid var(--line); padding: 6px 10px; text-align: left; vertical-align: top; }
.message { font-size: 17px; }
dl.facts { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 6px 18px; margin: 14px 0 0; }
dl.facts dt { color: var(--muted); }
dl.facts dd { margin: 0; overflow-wrap: anywhere; }
ol.options, ul.options { list-style: none; padding: 0; margin: 10px 0 0; }
.options li { display: flex; gap: 10px; align-items: baseline; padding: 6px 10px; border-radius: 8px; }
.options li + li { margin-top: 2px; }
.options .opt { font-weight: 700; min-width: 1.4em; font-variant-numeric: tabular-nums; }
.options li.is-key { background: var(--ok-bg); }
.tag { display: inline-block; font-size: 12px; font-weight: 700; letter-spacing: 0.04em; padding: 1px 8px; border-radius: 999px; white-space: nowrap; }
.tag.key { background: var(--ok); color: var(--card); }
.tag.mis { background: var(--soft); color: var(--muted); font-weight: 600; letter-spacing: 0; white-space: normal; }
ol.items { list-style: none; padding: 0; margin: 0; }
ol.items > li { padding: 16px 0; border-top: 1px solid var(--line); }
ol.items > li:first-child { border-top: 0; padding-top: 4px; }
.answer { margin-top: 10px; }
.answer b { font-weight: 650; }
.rationale { color: var(--muted); margin-top: 8px; font-size: 15px; }
.quiz-title { font-size: 18px; margin: 0 0 4px; }
.verdict { display: inline-block; padding: 3px 14px; border-radius: 999px; font-weight: 700; text-transform: capitalize; margin-bottom: 12px; }
.verdict.correct { background: var(--ok-bg); color: var(--ok); }
.verdict.partial { background: var(--mid-bg); color: var(--mid); }
.verdict.wrong { background: var(--bad-bg); color: var(--bad); }
.verdict.other { background: var(--soft); color: var(--muted); }
.misconception { color: var(--muted); font-size: 15px; margin: 0 0 12px; }
form.pick {
  position: sticky; bottom: 0; z-index: 5; margin-top: 28px; background: var(--card); border-top: 1px solid var(--line);
  box-shadow: var(--shadow); padding: 16px 28px 18px;
}
.pick .row { max-width: 1480px; margin: 0 auto; display: flex; flex-wrap: wrap; align-items: flex-end; gap: 14px 26px; }
.pick fieldset { border: 0; padding: 0; margin: 0; min-width: 0; }
.pick legend, .pick .q { display: block; font-size: 14px; font-weight: 600; color: var(--muted); margin-bottom: 6px; padding: 0; }
.seg { display: inline-flex; border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
.seg label { position: relative; cursor: pointer; }
.seg input { position: absolute; opacity: 0; width: 1px; height: 1px; }
.seg span { display: block; padding: 8px 18px; font-weight: 600; user-select: none; }
.seg label + label span { border-left: 1px solid var(--line); }
.seg input:checked + span { background: var(--accent); color: var(--accent-ink); }
.seg input:focus-visible + span { outline: 2px solid var(--accent); outline-offset: -4px; }
.why { flex: 1 1 320px; min-width: 0; }
.why input {
  width: 100%; font: inherit; color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 10px; padding: 8px 12px;
}
.why input:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
.pick button {
  font: inherit; font-weight: 650; color: var(--accent-ink); background: var(--accent); border: 0; border-radius: 10px; padding: 9px 22px; cursor: pointer;
}
.pick button:focus-visible { outline: 3px solid var(--accent-soft); outline-offset: 2px; }
.pick .nav { flex-basis: 100%; display: flex; gap: 18px; font-size: 14px; color: var(--muted); }
.error { flex-basis: 100%; color: var(--bad); font-weight: 600; }
@media (max-width: 920px) { form.pick { position: static; padding: 18px 16px 22px; box-shadow: none; } }
.terminal-note { margin-top: 28px; color: var(--muted); text-align: center; }
.done { max-width: 640px; margin: 12vh auto; text-align: center; }
.done h1 { font-size: 26px; margin-bottom: 8px; }
.done code { font: 15px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; background: var(--soft); padding: 3px 8px; border-radius: 6px; }
"""


def page(title: str, body: str) -> str:
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{esc(title)}</title>\n<style>{CSS}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
    )


def _option_text(item: dict, option_id) -> str | None:
    return next((str(o.get("text") or "") for o in item.get("options") or [] if isinstance(o, dict) and o.get("id") == option_id), None)


def _misconception(tp: topic.Topic, mid) -> str:
    text = next((m.get("text") for m in tp.misconceptions if m.get("id") == mid), None)
    return f"{mid}: {text}" if text else str(mid)


def _answer_text(item: dict, answer) -> str:
    """How an answer reads for an item: an mcq option id with the option's text, else the answer."""
    if answer is None:
        return ""
    if item.get("type") == "mcq":
        oid = option_choice(item, answer)
        text = _option_text(item, oid) if oid is not None else None
        if text and str(answer).strip() != text.strip():
            return f"{answer} ({text})"
    return str(answer)


def _options_html(item: dict, key_item: dict | None, tp: topic.Topic) -> str:
    distractors = (key_item or {}).get("distractors") if isinstance((key_item or {}).get("distractors"), dict) else {}
    rows = []
    for option in item.get("options") or []:
        if not isinstance(option, dict):
            continue
        oid = option.get("id")
        is_key = key_item is not None and key_item.get("answer") == oid
        extra = ' <span class="tag key">key</span>' if is_key else ""
        if oid in distractors:
            extra += f' <span class="tag mis">misconception {esc(_misconception(tp, distractors[oid]))}</span>'
        rows.append(f'<li class="{"is-key" if is_key else ""}"><span class="opt">{esc(oid)}</span><span>{inline(str(option.get("text") or ""))}{extra}</span></li>')
    return f'<ol class="options">{"".join(rows)}</ol>' if rows else ""


def _type_name(kind) -> str:
    return {"mcq": "multiple choice", "numeric": "numeric", "short": "short answer"}.get(kind, str(kind or "item"))


def quiz_html(quiz, key, tp: topic.Topic) -> str:
    """One version's quiz with its key, as HTML."""
    if isinstance(quiz, str):
        return '<p class="empty">This quiz file is not valid JSON; here is what it holds.</p>' + f'<div class="prose"><pre><code>{esc(quiz[:20000])}</code></pre></div>'
    if not isinstance(quiz, dict):
        return '<p class="empty">This version wrote no quiz.</p>'
    key_items = {str(k.get("id")): k for k in (key or {}).get("items") or [] if isinstance(k, dict)} if isinstance(key, dict) else {}
    items = [i for i in quiz.get("items") or [] if isinstance(i, dict)]
    head = [f'<h3 class="quiz-title">{inline(str(quiz.get("title") or "Quiz"))}</h3>']
    meta = [f"{len(items)} item{'s' if len(items) != 1 else ''}"]
    if quiz.get("objective"):
        meta.insert(0, f"objective {quiz.get('objective')}")
    head.append(f'<div class="meta">{esc(" · ".join(meta))}</div>')
    if not isinstance(key, dict):
        head.append('<p class="empty">This version wrote no answer key for it.</p>')
    rows = []
    for item in items:
        k = key_items.get(str(item.get("id")))
        meta_bits = [str(item.get("id") or "?"), _type_name(item.get("type"))]
        if item.get("objective"):
            meta_bits.append(str(item["objective"]))
        parts = [f'<div class="meta">{esc(" · ".join(meta_bits))}</div>', f'<div class="prose">{md(str(item.get("stem") or ""))}</div>']
        if item.get("type") == "mcq":
            parts.append(_options_html(item, k, tp))
        if k is not None:
            if item.get("type") != "mcq":
                answer = esc(_answer_text(item, k.get("answer")))
                if item.get("type") == "numeric":
                    if item.get("unit"):
                        answer += f" {esc(item['unit'])}"
                    tolerance = k.get("tolerance")
                    if isinstance(tolerance, (int, float)) and not isinstance(tolerance, bool):
                        answer += f" (within ±{esc(tolerance)})" if tolerance > 0 else " (exact)"
                parts.append(f'<div class="answer"><b>Key:</b> {answer}</div>')
                accepted = [a for a in k.get("accepted") or [] if isinstance(a, str)]
                if accepted:
                    parts.append(f'<div class="answer"><b>Also accepted:</b> {esc("; ".join(accepted))}</div>')
            if k.get("rationale"):
                parts.append(f'<div class="rationale prose">{md(str(k["rationale"]))}</div>')
        elif isinstance(key, dict):
            parts.append('<p class="empty">The key has no entry for this item.</p>')
        rows.append(f"<li>{''.join(parts)}</li>")
    body = f'<ol class="items">{"".join(rows)}</ol>' if rows else '<p class="empty">The quiz has no items.</p>'
    return "".join(head) + body


def grade_shared_html(tp: topic.Topic, submission: str, item_id: str) -> str:
    """The item, the learner's response and the key's answer, shown once above both grades."""
    try:
        quiz = tp.quiz(tp.graded_quiz)
        key = tp.key(tp.graded_quiz)
        sub = tp.submission(submission)
    except P3Error as exc:
        return f'<section class="card shared"><p class="empty">{esc(exc)}</p></section>'
    item = next((i for i in quiz.get("items") or [] if isinstance(i, dict) and str(i.get("id")) == item_id), {})
    key_item = next((k for k in key.get("items") or [] if isinstance(k, dict) and str(k.get("id")) == item_id), {})
    answer = next((a for a in sub.get("answers") or [] if isinstance(a, dict) and str(a.get("id")) == item_id), {})
    meta = f"Quiz {tp.graded_quiz} · item {item_id} · {_type_name(item.get('type'))} · submission {submission}"
    parts = [f'<div class="meta">{esc(meta)}</div>', f'<div class="prose message">{md(str(item.get("stem") or ""))}</div>']
    if item.get("type") == "mcq":
        parts.append(_options_html(item, None, tp))
    response = _answer_text(item, answer.get("response"))
    key_answer = _answer_text(item, key_item.get("answer"))
    if item.get("type") == "numeric" and item.get("unit") and key_answer:
        key_answer += f" {item['unit']}"
    parts.append('<dl class="facts">')
    parts.append(f'<dt>Learner\'s answer</dt><dd class="prose">{md(response) or "<span class=empty>(no answer)</span>"}</dd>')
    if key_answer:
        parts.append(f"<dt>Answer key</dt><dd>{esc(key_answer)}</dd>")
    parts.append("</dl>")
    return f'<section class="card shared">{"".join(parts)}</section>'


def grade_side_html(status: str, entry: dict | None, tp: topic.Topic) -> str:
    if status == "no-file":
        return '<p class="empty">This version wrote no grades for this submission.</p>'
    if status == "bad-file":
        return '<p class="empty">This version\'s grades file is not valid JSON.</p>'
    if status == "no-item" or entry is None:
        return '<p class="empty">This version\'s grades have no entry for this item.</p>'
    verdict = str(entry.get("verdict") or "no verdict")
    css = verdict if verdict in topic.VERDICTS else "other"
    parts = [f'<div class="verdict {css}">{esc(verdict)}</div>']
    if entry.get("misconception"):
        parts.append(f'<p class="misconception">Misconception {esc(_misconception(tp, entry["misconception"]))}</p>')
    feedback = md(str(entry.get("feedback") or ""))
    parts.append(f'<div class="prose">{feedback}</div>' if feedback else '<p class="empty">No feedback.</p>')
    return "".join(parts)


def parse_item(item: str) -> tuple[str, str | None]:
    """("<scenario id>", "<quiz item id>" or None) from a pair's item string."""
    sid, _, sub = str(item).partition("/")
    return sid, (sub or None)


def pair_body(s: Session, k: int, frame_url: Callable[[int, str, str], str]) -> str:
    """The shared part and the two columns of pair k (1-based)."""
    pair = s.pairs[k - 1]
    sid, sub_item = parse_item(pair["item"])
    sides = {which: s.side(pair, which) for which in SIDES}
    shared = ""
    columns = {}
    if s.job == "teach":
        for which, side in sides.items():
            rel, note = lesson_of(side, sid)
            if rel is None:
                columns[which] = ("", '<p class="empty">This version wrote no lesson.</p>')
                continue
            url = frame_url(k, which, rel)
            notice = f'<p class="empty">{esc(note)}</p>' if note else ""
            frame = f'<iframe class="frame" src="{esc(url)}" title="{which.title()} lesson" sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox" referrerpolicy="no-referrer"></iframe>'
            columns[which] = (f'<a href="{esc(url)}" target="_blank" rel="noopener">Open in a new tab</a>', notice + frame)
    elif s.job == "quiz":
        for which, side in sides.items():
            _rel, quiz, key = quiz_of(side, sid)
            columns[which] = ("", quiz_html(quiz, key, s.topic))
    elif s.job == "grade":
        entry = sides["left"].scenario(sid) or sides["right"].scenario(sid) or {}
        submission = str(entry.get("submission") or sid.removeprefix("grade-"))
        shared = grade_shared_html(s.topic, submission, sub_item or "")
        for which, side in sides.items():
            status, grade = grade_of(side, sid, submission, sub_item or "", s.topic.graded_quiz)
            columns[which] = ("", grade_side_html(status, grade, s.topic))
    else:
        entry = sides["left"].scenario(sid) or sides["right"].scenario(sid) or {}
        probe = s.topic.probe(str(entry.get("probe") or sid.removeprefix("tutor-"))) or {}
        shared = (
            f'<section class="card shared"><div class="meta">The learner\'s message (probe {esc(probe.get("id") or sid)})</div>'
            f'<div class="prose message">{md(str(probe.get("message") or ""))}</div></section>'
        )
        for which, side in sides.items():
            reply = reply_of(side, sid)
            columns[which] = ("", f'<div class="prose">{md(reply)}</div>' if reply else '<p class="empty">This version gave no reply.</p>')
    cols = []
    for which in SIDES:
        extra, content = columns[which]
        cols.append(f'<article class="card side" aria-label="{which.title()}"><div class="side-head"><h2 class="label">{which.title()}</h2>{extra}</div>{content}</article>')
    return shared + f'<div class="cols">{"".join(cols)}</div>'


def header_html(s: Session, k: int) -> str:
    n = len(s.pairs)
    done = s.answered()
    width = round(100 * done / n) if n else 100
    where = f"{s.job} · {s.topic.id}"
    return (
        f'<header class="top"><h1>Blind comparison</h1><span class="where">{esc(where)}</span>'
        f'<span class="count">Pair {k} of {n}</span></header>'
        f'<div class="bar" title="{done} of {n} answered"><span style="width: {width}%"></span></div>'
        f'<p class="hint">{esc(JOB_HINT[s.job])}</p>'
    )


def form_html(s: Session, k: int, token: str, values: dict | None = None, error: str | None = None) -> str:
    pair = s.pairs[k - 1]
    values = values or {}
    picked = s.pick_for(pair["pair_id"]) or {}
    choice = values.get("choice", picked.get("choice"))
    reason = values.get("reason", picked.get("reason", ""))
    tell = values.get("could_tell", {True: "yes", False: "no"}.get(picked.get("could_tell")))

    def radio(name: str, value: str, label: str, current) -> str:
        checked = " checked" if current == value else ""
        return f'<label><input type="radio" name="{name}" value="{value}" required{checked}><span>{label}</span></label>'

    nav = []
    if k > 1:
        nav.append(f'<a href="/pair/{k - 1}">Previous pair</a>')
    if picked:
        nav.append("This pair has a saved answer; saving again replaces it.")
    nav.append(f"{s.answered()} of {len(s.pairs)} answered; each answer is saved when you submit it.")
    return (
        f'<form class="pick" method="post" action="/pair/{k}"><div class="row">'
        + (f'<p class="error" role="alert">{esc(error)}</p>' if error else "")
        + f'<input type="hidden" name="pair_id" value="{esc(pair["pair_id"])}"><input type="hidden" name="token" value="{esc(token)}">'
        + '<fieldset><legend>Which fits you better?</legend><div class="seg">'
        + radio("choice", "left", "Left", choice) + radio("choice", "tie", "Tie", choice) + radio("choice", "right", "Right", choice)
        + "</div></fieldset>"
        + f'<label class="why"><span class="q">Why, in one sentence</span><input type="text" name="reason" required maxlength="{MAX_REASON}" autocomplete="off" value="{esc(reason)}"></label>'
        + '<fieldset><legend>Could you tell which config made which?</legend><div class="seg">'
        + radio("could_tell", "yes", "Yes", tell) + radio("could_tell", "no", "No", tell)
        + "</div></fieldset>"
        + '<button type="submit">Save and next</button>'
        + f'<div class="nav">{" ".join(f"<span>{x}</span>" if not x.startswith("<a") else x for x in nav)}</div>'
        + "</div></form>"
    )  # fmt: skip


def pair_page(s: Session, k: int, token: str, values: dict | None = None, error: str | None = None) -> str:
    """The server page of pair k: the two versions and the sticky form."""

    def frame_url(n: int, which: str, rel: str) -> str:
        return f"/frame/{n}/{which}/{quote(rel)}"

    body = f'<main class="page">{header_html(s, k)}{pair_body(s, k, frame_url)}</main>{form_html(s, k, token, values, error)}'
    return page(f"Pair {k} of {len(s.pairs)} - blind comparison", body)


def terminal_page(s: Session, k: int) -> str:
    """The page terminal mode writes for pair k: the two versions, answered in the terminal."""

    def frame_url(n: int, which: str, rel: str) -> str:
        return f"pair-{n:03d}/{which}/{quote(rel)}"

    body = f'<main class="page">{header_html(s, k)}{pair_body(s, k, frame_url)}<p class="terminal-note">Answer the three questions in the terminal.</p></main>'
    return page(f"Pair {k} of {len(s.pairs)} - blind comparison", body)


def done_page(s: Session) -> str:
    body = (
        '<main class="page"><div class="done">'
        f"<h1>All {len(s.pairs)} pairs are answered</h1>"
        "<p>Your picks are saved. You can close this tab.</p>"
        f"<p>See which config was which in your terminal with <code>p3 compare --reveal {esc(s.id)}</code></p>"
        "</div></main>"
    )
    return page("Blind comparison done", body)


def message_page(title: str, text: str) -> str:
    return page(title, f'<main class="page"><div class="done"><h1>{esc(title)}</h1><p>{esc(text)}</p></div></main>')


# ---- server mode ----


@dataclass
class Response:
    status: int
    body: bytes = b""
    headers: list[tuple[str, str]] = field(default_factory=list)


PAGE_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; frame-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
FRAME_CSP = "sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox"


class CompareApp:
    """The comparison pages of one session, as a function from a request to a response, so the
    server is a thin layer over it (and tests can call it directly).

    GET /            the first pair without a pick, or the done page
    GET /pair/<k>    pair k: the two versions and the form
    POST /pair/<k>   save the pick for pair k, then go on to the next open pair
    GET /frame/<k>/<left|right>/<path>   a file of that side's lesson (teach only), from the run's outputs
    GET /done        the done page

    Nothing under bench/compare/ is ever served. A POST needs the page's token, which a lesson in
    its sandboxed frame cannot read."""

    def __init__(self, session: Session, token: str | None = None):
        self.s = session
        self.token = token or secrets.token_urlsafe(18)
        self.finished = threading.Event()
        self.port: int | None = None

    def _html(self, status: int, text: str) -> Response:
        return Response(status, text.encode("utf-8"), [("Content-Type", "text/html; charset=utf-8"), ("Content-Security-Policy", PAGE_CSP)])

    def _redirect(self, where: str) -> Response:
        return Response(303, b"", [("Location", where)])

    def _not_found(self) -> Response:
        return self._html(404, message_page("Not found", "There is nothing at this address."))

    def host_ok(self, host: str | None) -> bool:
        """Only requests addressed to this server (127.0.0.1 or localhost on its port) are answered."""
        if self.port is None or host is None:
            return True
        return host.lower() in {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}

    def _pair_number(self, text: str) -> int | None:
        if not text.isdigit():
            return None
        k = int(text)
        return k if 1 <= k <= len(self.s.pairs) else None

    def handle(self, method: str, target: str, body: bytes = b"") -> Response:
        path = urlsplit(target).path
        parts = [p for p in path.split("/") if p]
        if method == "GET" and not parts:
            k = self.s.next_open()
            return self._redirect(f"/pair/{k}" if k else "/done")
        if method == "GET" and parts == ["done"]:
            if self.s.next_open() is not None:
                return self._redirect("/")
            self.finished.set()
            return self._html(200, done_page(self.s))
        if len(parts) == 2 and parts[0] == "pair":
            k = self._pair_number(parts[1])
            if k is None:
                return self._not_found()
            if method == "GET":
                return self._html(200, pair_page(self.s, k, self.token))
            if method == "POST":
                return self._submit(k, body)
        if method == "GET" and len(parts) >= 4 and parts[0] == "frame":
            return self._frame(parts[1], parts[2], parts[3:])
        if method == "GET" and parts == ["favicon.ico"]:
            return Response(204)
        if method not in ("GET", "POST"):
            return Response(405, b"", [("Allow", "GET, POST")])
        return self._not_found()

    def _submit(self, k: int, body: bytes) -> Response:
        form = {name: values[0] for name, values in parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True).items()}
        if not secrets.compare_digest(form.get("token", ""), self.token):
            return self._html(403, message_page("This form has expired", "Reload the page and answer again; nothing was saved."))
        pair = self.s.pairs[k - 1]
        if form.get("pair_id") != pair["pair_id"]:
            return self._redirect(f"/pair/{k}")
        values = {"choice": form.get("choice"), "reason": form.get("reason", ""), "could_tell": form.get("could_tell")}
        error = None
        if values["choice"] not in CHOICES:
            error = "Pick left, right or tie."
        elif not " ".join(values["reason"].split()):
            error = "Say why, in one sentence."
        elif values["could_tell"] not in ("yes", "no"):
            error = "Say whether you could tell which config made which."
        if error is None:
            try:
                self.s.record(pair["pair_id"], values["choice"], values["reason"], values["could_tell"] == "yes")
            except P3Error as exc:
                error = str(exc)
        if error is not None:
            return self._html(400, pair_page(self.s, k, self.token, values, error))
        if self.s.next_open() is None:
            self.finished.set()
            return self._redirect("/done")
        return self._redirect(f"/pair/{self.s.next_open()}")

    def _frame(self, number: str, which: str, rel_parts: list[str]) -> Response:
        k = self._pair_number(number)
        if self.s.job != "teach" or k is None or which not in SIDES:
            return self._not_found()
        rel_parts = "/".join(unquote(p) for p in rel_parts).split("/")
        if any(p in ("", ".", "..") or "\\" in p or ":" in p or "\x00" in p for p in rel_parts):
            return self._not_found()
        pair = self.s.pairs[k - 1]
        sid, _ = parse_item(pair["item"])
        side = self.s.side(pair, which)
        rel = "/".join(rel_parts)
        for base in (side.outputs_dir(sid), self.s.topic.workspace):
            target = _inside(base, rel)
            if target is not None:
                kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                if kind.startswith("text/") or kind in ("image/svg+xml", "application/javascript"):
                    kind += "; charset=utf-8"
                headers = [("Content-Type", kind), ("Content-Security-Policy", FRAME_CSP), ("X-Content-Type-Options", "nosniff")]
                return Response(200, target.read_bytes(), headers)
        return self._not_found()


def _inside(base: Path, rel: str) -> Path | None:
    """base/rel when it is a file inside base (no way out through .. or links), else None."""
    try:
        root = base.resolve()
        target = (base / rel).resolve()
    except (OSError, RuntimeError):
        return None
    if target.is_file() and target.is_relative_to(root):
        return target
    return None


class _Server(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR lets a second server take a port that is already in use, so it is off there.
    allow_reuse_address = os.name != "nt"
    daemon_threads = True

    def server_bind(self):
        """HTTPServer's own server_bind looks up the address's host name (socket.getfqdn), a reverse
        DNS query that can take many seconds on a Mac; nothing here uses that name, so skip it."""
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]

    def handle_error(self, request, client_address):
        """A browser that drops a connection (leaving a page while its frames load) is normal; say
        nothing. Anything else gets one line instead of a traceback."""
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionError, TimeoutError)):
            return
        print(f"  (the comparison page hit an error and carries on: {exc!r})", file=sys.stderr)


def make_server(app: CompareApp, port: int | None = None) -> ThreadingHTTPServer:
    """An HTTP server on 127.0.0.1 (on `port`, or a free one) that answers with app.handle."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "p3-compare"
        sys_version = ""

        def do_GET(self):
            self._answer("GET")

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_POST:
                self._send(Response(413))
                return
            self._answer("POST", self.rfile.read(length))

        def _answer(self, method: str, body: bytes = b"") -> None:
            if not app.host_ok(self.headers.get("Host")):
                self._send(Response(421, b"wrong host"))
                return
            try:
                resp = app.handle(method, self.path, body)
            except P3Error as exc:
                resp = app._html(500, message_page("Something is wrong with this session", str(exc)))
            except OSError as exc:
                # a pick could not be saved: OneDrive or a virus scanner holding the session file, a full disk
                text = f"The session file is busy or cannot be written ({exc.strerror or exc}). Go back and submit the answer again; every answer saved before this one is safe."
                resp = app._html(503, message_page("Your answer could not be saved", text))
            self._send(resp)

        def _send(self, resp: Response) -> None:
            self.send_response(resp.status)
            for name, value in resp.headers:
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(resp.body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(resp.body)

        def log_message(self, format, *args):
            pass  # the terminal stays quiet; the page shows everything

    try:
        server = _Server(("127.0.0.1", int(port or 0)), Handler)
    except OSError as exc:
        raise P3Error(f"cannot listen on 127.0.0.1:{port}: {exc.strerror or exc}; pick another port with --port, or leave it out for a free one") from None
    app.port = server.server_address[1]
    return server


def serve(s: Session, port: int | None = None, open_browser: bool = True) -> int:
    """Server mode: serve the session's pages until every pair has a pick or Ctrl-C."""
    app = CompareApp(s)
    server = make_server(app, port)
    url = f"http://127.0.0.1:{app.port}/"
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
    thread.start()
    print(f"  the comparison page: {url}")
    print(f"  each answer is saved when you submit it; stop with Ctrl-C and continue later with p3 compare --resume {s.id}")
    if open_browser:
        try:
            if not webbrowser.open(url):
                print("  (no browser opened by itself; open the address above)")
        except Exception:  # a broken browser setup must not stop the comparison
            print("  (no browser opened by itself; open the address above)")
    stopped = False
    try:
        while not app.finished.wait(0.5):
            pass
        time.sleep(DONE_GRACE_S)  # let the browser load the done page
    except KeyboardInterrupt:
        stopped = True
    finally:
        server.shutdown()
        server.server_close()
    return _finish(s, stopped)


def _finish(s: Session, stopped: bool) -> int:
    n, done = len(s.pairs), s.answered()
    if done == n:
        answered = "The pair is answered" if n == 1 else f"All {n} pairs are answered"
        print(f"\n{answered}. See which config was which: p3 compare --reveal {s.id}")
    else:
        print(f"\n{'Stopped. ' if stopped else ''}{done} of {n} pairs answered, all saved. Continue with: p3 compare --resume {s.id}")
    return 0


# ---- terminal mode ----


def write_terminal_pair(s: Session, k: int, folder: Path) -> Path:
    """Write pair k as one side-by-side HTML file in `folder` (with each side's lesson files beside
    it, for teach) and return its path."""
    pair = s.pairs[k - 1]
    if s.job == "teach":
        sid, _ = parse_item(pair["item"])
        for which in SIDES:
            side = s.side(pair, which)
            dest = folder / f"pair-{k:03d}" / which
            assets = s.topic.workspace / "assets"
            if assets.is_dir():
                util.copy_files(assets, dest / "assets", util.list_files(assets))
            out = side.outputs_dir(sid)
            util.copy_files(out, dest, util.list_files(out))
    path = folder / f"pair-{k:03d}.html"
    util.write_text(path, terminal_page(s, k))
    return path


def _ask(prompt: str, ask: Callable[[str], str], accept: dict[str, object], again: str) -> object:
    while True:
        answer = ask(prompt).strip().lower()
        if answer in accept:
            return accept[answer]
        print(f"  {again}")


def terminal(s: Session, ask: Callable[[str], str] | None = None, folder: Path | None = None) -> int:
    """Terminal mode: write each open pair as an HTML file, print its path, and ask the three
    questions on stdin (or with `ask`), saving each answer at once."""
    ask = ask or input
    folder = Path(folder) if folder else Path(tempfile.mkdtemp(prefix="p3-compare-"))
    print(f"  each pair is written as an HTML file in {folder}; open it, then answer here (Ctrl-C or an empty input stream stops, and every answer so far is saved)")
    choices = {"l": "left", "left": "left", "r": "right", "right": "right", "t": "tie", "tie": "tie"}
    yes_no = {"y": True, "yes": True, "n": False, "no": False}
    stopped = False
    try:
        while (k := s.next_open()) is not None:
            path = write_terminal_pair(s, k, folder)
            print(f"\nPair {k} of {len(s.pairs)}: {path}")
            choice = _ask("  Which fits you better? left, right or tie [l/r/t]: ", ask, choices, "Type l, r or t.")
            while True:
                reason = " ".join(ask("  Why, in one sentence: ").split())
                if reason:
                    break
                print("  A reason is required.")
            could_tell = _ask("  Could you tell which config made which? [y/n]: ", ask, yes_no, "Type y or n.")
            s.record(s.pairs[k - 1]["pair_id"], str(choice), reason, bool(could_tell))
            print("  saved")
    except (EOFError, KeyboardInterrupt):
        stopped = True
    return _finish(s, stopped)


# ---- the reveal ----


def sign_test(wins_a: int, wins_b: int) -> float:
    """The exact two-sided sign-test p-value for wins_a against wins_b (ties already left out):
    the chance, if each pick were a fair coin flip, of a split at least this lopsided either way."""
    n = wins_a + wins_b
    if n == 0:
        return 1.0
    k = max(wins_a, wins_b)
    tail = Fraction(sum(math.comb(n, i) for i in range(k, n + 1)), 2**n)
    return float(min(Fraction(1), 2 * tail))


def fmt_p(p: float) -> str:
    if p < 0.001:
        return "< 0.001"
    return f"{p:.3f}" if p < 0.01 else f"{p:.2f}"


def _mean_cell(values: list, kind: str) -> str:
    return report.cell(values, kind, len(values)) if values else "-"


def job_cost(s: Session) -> dict[str, dict]:
    """{config: {"runs", "scenarios", and per-scenario lists of tokens, output, minutes, subagents
    and cost}} over the job's scenarios in the session's runs, from run.json."""
    out = {}
    for index, name in enumerate(s.configs):
        run_ids = list(dict.fromkeys(p["run_pair"][index] for p in s.pairs))
        stats: dict = {"runs": len(run_ids), "scenarios": 0, "tokens": [], "output": [], "minutes": [], "subagents": [], "cost": []}
        for run_id in run_ids:
            run = _read_json_or_none(util.runs_dir(name, s.root) / run_id / "run.json") or {}
            for entry in run.get("scenarios") or []:
                if entry.get("job") != s.job:
                    continue
                tokens = entry.get("tokens") or {}
                stats["scenarios"] += 1
                stats["tokens"].append(sum(int(v or 0) for v in tokens.values()))
                stats["output"].append(int(tokens.get("output") or 0))
                stats["minutes"].append(round(int(entry.get("duration_ms") or 0) / 60000, 2))
                stats["subagents"].append(int((entry.get("subagents") or {}).get("spawned") or 0))
                if isinstance(entry.get("cost_usd_list"), (int, float)):
                    stats["cost"].append(float(entry["cost_usd_list"]))
        out[name] = stats
    return out


def job_checks(s: Session) -> dict[str, dict[str, list]]:
    """{config: {summary key: [value per run]}} of the job's headline numbers from score.json."""
    out = {}
    for index, name in enumerate(s.configs):
        run_ids = list(dict.fromkeys(p["run_pair"][index] for p in s.pairs))
        values: dict[str, list] = {key: [] for key, _, _ in CHECKS[s.job]}
        for run_id in run_ids:
            score = _read_json_or_none(util.runs_dir(name, s.root) / run_id / "score.json") or {}
            summary = score.get("summary") or {}
            for key in values:
                values[key].append(summary.get(key))
        out[name] = values
    return out


def reveal(sid: str, root: Path | None = None) -> tuple[str, dict]:
    """The reveal of a complete session as Markdown, and the record it writes into the session file
    ("revealed"): tally, sign test, could-tell share, reasons by winner, objective checks, cost."""
    s = Session(sid, root)
    n = len(s.pairs)
    missing = n - s.answered()
    if missing:
        raise P3Error(f"session {s.id} is not finished: {missing} of {n} pairs have no pick yet. Finish it first with p3 compare --resume {s.id}; revealing early would end the blinding")
    a, b = s.configs
    wins = {a: 0, b: 0}
    ties = 0
    reasons: dict[str, list[dict]] = {a: [], b: [], "tie": []}
    items = {p["pair_id"]: p["item"] for p in s.pairs}
    for pick in s.picks:
        entry = {"pair_id": pick["pair_id"], "item": items.get(pick["pair_id"]), "reason": pick.get("reason", "")}
        if pick["choice"] == "tie":
            ties += 1
            reasons["tie"].append(entry)
        else:
            winner = s.key["pairs"][pick["pair_id"]][pick["choice"]]
            wins[winner] += 1
            reasons[winner].append(entry)
    non_tie = wins[a] + wins[b]
    p = sign_test(wins[a], wins[b])
    told = sum(1 for pick in s.picks if pick.get("could_tell") is True)
    checks = job_checks(s)
    cost = job_cost(s)
    leader = a if wins[a] > wins[b] else b if wins[b] > wins[a] else None
    runs = len({tuple(p["run_pair"]) for p in s.pairs})

    lines = [f"## Blind comparison {s.id}", ""]
    kind = "teach-only runs" if s.data.get("teach_only") else "full runs"
    kind = f"quick {kind}" if s.data.get("quick") else kind
    lines.append(f"Job {s.job} on {s.topic.id}, `{a}` against `{b}`: {n} pair{'s' if n != 1 else ''} from {runs} pair{'s' if runs != 1 else ''} of {kind} at {s.data.get('minutes') or s.topic.minutes} minutes.")
    lines += ["", "### Tally", ""]
    lines.append(f"`{a}` won {wins[a]}, `{b}` won {wins[b]}, and {ties} {'was a tie' if ties == 1 else 'were ties'}.")
    lines += ["", "### Sign test", ""]
    if non_tie:
        lead = f"{max(wins.values())} of the {non_tie} non-tie picks went to `{leader}`" if leader else f"the {non_tie} non-tie picks split evenly"
        lines.append(f"{lead[0].upper() + lead[1:]}; the exact two-sided sign-test p-value is {fmt_p(p)}.")
    else:
        lines.append("Every pick was a tie, so there is nothing to test.")
    lines.append(READING_LINE)
    lines.append("The p-value is the chance of a split at least this lopsided if the two configs were equally good.")
    if 0 < non_tie <= 5:
        lines.append(f"With {non_tie} non-tie pick{'s' if non_tie != 1 else ''}, no split can reach 0.05, so your reasons and the objective checks carry the weight here.")
    lines += ["", "### Could you tell", ""]
    lines.append(f"You could tell which config made which in {told} of {n} pairs ({round(100 * told / n) if n else 0}%).")
    lines += ["", "### Reasons, by the config that won", ""]
    for group, title in ((a, f"`{a}` won"), (b, f"`{b}` won"), ("tie", "Ties")):
        lines.append(f"{title} ({len(reasons[group])}):")
        lines.append("")
        lines += [f"- pair {r['pair_id']}, {r['item']}: {r['reason']}" for r in reasons[group]] or ["- none"]
        lines.append("")
    lines += [f"### Objective checks ({s.job})", "", "Mean over the runs in this session, with the range in brackets; from score.json.", ""]
    head = ["check", f"`{a}`", f"`{b}`"]
    rows = [[label] + [_mean_cell(checks[name][key], kind) for name in (a, b)] for key, label, kind in CHECKS[s.job]]
    lines += [report.table(head, rows), ""]
    lines += [f"### Cost per {s.job} scenario", "", "Mean per scenario over the runs in this session, with the range in brackets; from run.json.", ""]
    head = ["config", "runs", "scenarios"] + [label for _, label, _ in COST_COLUMNS]
    rows = [[f"`{name}`", str(cost[name]["runs"]), str(cost[name]["scenarios"])] + [_mean_cell(cost[name][key], kind) for key, _, kind in COST_COLUMNS] for name in (a, b)]
    lines += [report.table(head, rows), ""]
    ratios = []
    for key, label in (("tokens", "the tokens"), ("minutes", "the minutes")):
        ma, mb = (sum(cost[x][key]) / len(cost[x][key]) if cost[x][key] else 0 for x in (a, b))
        if ma > 0 and mb > 0:
            ratios.append(f"{mb / ma:.1f}x {label}")
    if ratios:
        lines.append(f"Per scenario, `{b}` used {' and '.join(ratios)} of `{a}`.")
    lines.append(f"list-price $ is the {COST_LABEL}.")

    previous = s.data.get("revealed") if isinstance(s.data.get("revealed"), dict) else {}
    record = {
        "revealed_at": previous.get("revealed_at") or util.iso_utc(),
        "wins": wins,
        "ties": ties,
        "non_tie": non_tie,
        "p_value": round(p, 6),
        "could_tell": {"yes": told, "pairs": n, "share": round(told / n, 4) if n else None},
        "reasons": reasons,
        "objective": {name: {key: [v for v in vals if v is not None] for key, vals in checks[name].items()} for name in (a, b)},
        "cost": {name: {k: v for k, v in cost[name].items()} for name in (a, b)},
    }
    with s.lock:
        s.data["revealed"] = record
        util.replace_json(s.path, s.data)
    return "\n".join(lines) + "\n", record


# ---- listing ----


def list_text(root: Path) -> str:
    """One line per session: id, job, topic, configs, picks and status."""
    rows = []
    for path in session_files(root):
        data = _read_json_or_none(path)
        if not isinstance(data, dict):
            rows.append((path.stem, "?", "?", "(the file does not parse)", "", ""))
            continue
        pairs = data.get("pairs") or []
        picks = {p.get("pair_id") for p in data.get("picks") or [] if isinstance(p, dict)}
        status = "revealed" if data.get("revealed") else "complete" if data.get("complete") else "open"
        configs = " / ".join(str(c) for c in data.get("configs") or [])
        rows.append((str(data.get("session") or path.stem), str(data.get("job") or "?"), str(data.get("topic") or "?"), configs, f"{len(picks)}/{len(pairs)}", status))
    if not rows:
        return "No comparison sessions yet; start one with p3 compare <config-a> <config-b> --job teach\n"
    rows.insert(0, ("session", "job", "topic", "configs", "picks", "status"))
    widths = [max(len(r[i]) for r in rows) for i in range(6)]
    lines = ["  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows]
    lines.insert(1, "  ".join("-" * w for w in widths))
    open_ = [r[0] for r in rows[1:] if r[5] == "open"]
    tail = [f"\nContinue an open one with p3 compare --resume {open_[-1]}"] if open_ else []
    done = [r[0] for r in rows[1:] if r[5] == "complete"]
    tail += [f"Reveal a complete one with p3 compare --reveal {done[-1]}"] if done else []
    return "\n".join(lines + tail) + "\n"


# ---- the command ----


def main(args) -> int:
    """The p3 compare command (args: the argparse Namespace from p3.cli)."""
    root = util.repo_root()
    configs = list(getattr(args, "configs", None) or [c for c in (getattr(args, "config_a", None), getattr(args, "config_b", None)) if c])
    modes = [name for name in ("list", "reveal", "resume") if getattr(args, name, None)]
    if len(modes) > 1 or (modes and configs):
        raise P3Error("use one at a time: two configs with --job, --resume <session>, --reveal <session> or --list")
    if getattr(args, "list", False):
        print(list_text(root), end="")
        return 0
    if getattr(args, "reveal", None):
        text, _record = reveal(args.reveal, root)
        print(text, end="")
        return 0
    if getattr(args, "resume", None):
        s = Session(args.resume, root)
        if s.data.get("revealed"):
            print(f"Session {s.id} has been revealed; its picks are final. See it again with p3 compare --reveal {s.id}")
            return 0
        if s.next_open() is None:
            print(f"Session {s.id} is complete. See which config was which: p3 compare --reveal {s.id}")
            return 0
        print(f"p3 compare: resuming {s.id} ({s.job} on {s.topic.id}, {s.answered()} of {len(s.pairs)} pairs answered)")
    else:
        if len(configs) != 2:
            raise P3Error("give the two configs to compare and the job, such as: p3 compare c0-baseline final --job teach (or --resume, --reveal or --list)")
        job = getattr(args, "job", None)
        if not job:
            raise P3Error("--job is required: teach, quiz, grade or tutor")
        record = new_session(
            configs[0], configs[1], job, getattr(args, "topic", None) or util.SHARED_TOPIC,
            minutes=getattr(args, "minutes", None), quick=bool(getattr(args, "quick", False)),
            teach_only=bool(getattr(args, "teach_only", False)), root=root,
        )  # fmt: skip
        s = Session(record["session"], root)
        runs = len({tuple(p["run_pair"]) for p in s.pairs})
        print(f"p3 compare: session {s.id}, {s.job} on {s.topic.id}, {len(s.pairs)} pair{'s' if len(s.pairs) != 1 else ''} from {runs} pair{'s' if runs != 1 else ''} of runs")
        print(f"  which config is on which side is in {util.posix(s.key_path, root)}; do not open it before the reveal")
        _warn_changed_configs(s)
    if getattr(args, "terminal", False):
        return terminal(s)
    return serve(s, getattr(args, "port", None))


def _warn_changed_configs(s: Session) -> None:
    for index, name in enumerate(s.configs):
        try:
            recorded = util.load_snapshot(name, s.root)["hash"]
        except P3Error:
            continue
        for run_id in dict.fromkeys(p["run_pair"][index] for p in s.pairs):
            run = _read_json_or_none(util.runs_dir(name, s.root) / run_id / "run.json") or {}
            if run.get("config_hash") and run["config_hash"] != recorded:
                print(f"  warning: run {run_id} was made with another version of {name} than configs/{name}/ holds now; p3 check will fail on it")

