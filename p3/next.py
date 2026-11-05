"""`p3 next`: where you are on the project's map, and the one next thing to do, with the guide page
that explains it. The Guide (claude --agent p3-guide) runs it at the start of every session.

    p3 next: 498E (C:\\...\\work\\p3-tutor)

    Done:  1 Set up, 2 The baseline, 3 Your preferences
    Now:   4 Step 1, c1-skills: quick rounds (1 of at least 2 complete)
    Next:  In the Builder window, say: Act on Round 2 of reviews/c1-skills.md.
    Read:  guide/08-step1-skills.html#rounds
    Also:  the baseline's runs: 2 of 3 scored full runs (start the last one in a plain terminal)

It reads the state p3 check reads, makes no model call and changes nothing, and it exits 0 unless
the repo cannot be read.

- Integrity first: while p3 check has an integrity failure, Now is that failure, Next its FAIL line
  (with its details) and Read guide/19-troubleshooting.html. A run folder with no run.json that
  changed in the last RUNNING_MINUTES is a bench still running (p3 bench writes run.json when the
  last scenario ends), so it is not a failure here, and Also names it.
- The map is a fixed list of stages, each a list of items in order; the length
  study's stage and items are on it only for 598E or the length-study stretch. Now is the first
  stage with an item not done, Next that item's action and Read its guide page and anchor.
- A long run (a full bench run, from minutes to over an hour with repeats, started in a plain terminal) does not hold
  the map back once you have moved on: a stage whose only items left are long runs counts as passed
  as soon as an item of a later stage is done. Within a stage the items stay in order, because a
  major review needs its run. An item that needs runs left behind sends you back to the first of
  them instead (Item.needs): a blind comparison pairs only the runs there are when it starts, the
  open review of the test topics reads their runs, and EVAL.md reports on every run.
- Also lists at most two items not done from the stages before the current one (the long runs
  left behind), and, when Next is a long run, the first later item that waits for no run, as
  "While it runs: ...".
- Done lists the stages before the current one and every later stage already complete.
- Once every item of the map is done, Now is 12 Hand in: the first FAIL line of p3 check --final
  while it has one, and then what is left outside the repo (the video, the push and the Canvas post).
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from p3 import check, compare, reviews, topic, util
from p3.util import P3Error

GUIDE = "guide"
TROUBLESHOOTING = "19-troubleshooting.html"
HAND_IN = "15-hand-in.html"
# origin is the course template itself (the repo was cloned, not made with Use this template)
TEMPLATE_URL_RE = re.compile(r"[:/]Mines-Coding-with-AI-Agents/P3-tutor(?:\.git)?/*$", re.I)
# longer than one scenario may take (teach's limit is 45 minutes), so a bench still running has
# written a file into its run folder within it
RUNNING_MINUTES = 90
MAX_ALSO = 2
MAX_DETAILS = 5
TOPIC_CONFIGS = ("c0-baseline", "final")  # the two configs run on each test topic
LIVE_TRY = "Run the live tutor (uv run p3 bench --config live --quick, or --only with the scenarios you are working on)"
# (stage number, step number, step, guide page) of the three steps of the ladder; EVAL.md's
# sections 2 to 4 are steps 1 to 3
STEP_STAGES = ((4, 1, "c1-skills", "08-step1-skills.html"), (5, 2, "c2-review", "09-step2-review-loops.html"), (7, 3, "c3-split", "10-step3-split.html"))
WORDS = {1: "one", 2: "two", 3: "three"}
ALL_RUNS = "*"  # in Item.needs: every long run of the map


@dataclass
class Item:
    """One item of the map: what it is with its state (as Now shows it after the stage), whether it
    is done, and what to do about it."""

    name: str
    done: bool
    action: str = ""  # Next: the one thing to do
    page: str = ""  # its guide page, with an anchor where the guide has one
    long: bool = False  # a long run, started in a plain terminal
    waits: bool = False  # it needs a run made first, so it is never a "While it runs" item
    also: str = ""  # how Also names a long run once its stage is passed
    key: str = ""  # a long run's name, for `needs`
    needs: tuple[str, ...] = ()  # the long runs (keys, or ALL_RUNS) it cannot be done without


@dataclass
class Stage:
    number: int
    title: str
    items: list[Item]

    @property
    def label(self) -> str:
        return f"{self.number} {self.title}"

    @property
    def complete(self) -> bool:
        return all(i.done for i in self.items)


@dataclass
class Report:
    """What p3 next prints."""

    header: str
    done: list[str]
    now: str
    action: str
    read: str
    details: list[str] = field(default_factory=list)  # lines under Next, such as a FAIL line's
    also: list[str] = field(default_factory=list)

    def text(self) -> str:
        out = [self.header, "", f"Done:  {', '.join(self.done) if self.done else 'nothing yet'}", f"Now:   {self.now}", f"Next:  {self.action}"]
        out += [f"         {d}" for d in self.details]
        out.append(f"Read:  {self.read}")
        out += [("Also:  " if n == 0 else "       ") + line for n, line in enumerate(self.also)]
        return "\n".join(out) + "\n"


# ---- small helpers ----


_plural = check._plural  # "1 run", "2 runs", as p3 check words them


def _and(words: list[str]) -> str:
    """"a", "a and b", "a, b and c"."""
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + f" and {words[-1]}"


def _word(n: int) -> str:
    return WORDS.get(n, str(n))


def _sentence(text: str) -> str:
    return text if text.endswith((".", "?", "!")) else text + "."


def _without(prefix: str, text: str) -> str:
    """A review problem without the section it names first ("Quick rounds > Round 1: "), when the
    sentence around it already says where."""
    for head in (f"{prefix}: ", f"{prefix} > "):
        if text.startswith(head):
            return text[len(head):]
    return text


def _lines(numbers: list[int]) -> str:
    """"line 3" or "lines 3, 6, ..." for TODO markers, as p3 check shows them."""
    shown = ", ".join(map(str, numbers[:10])) + (", ..." if len(numbers) > 10 else "")
    return f"line{'s' if len(numbers) != 1 else ''} {shown}"


def _bench(name: str, topic_id: str = util.SHARED_TOPIC, minutes: int | None = None, repeats: int = 1) -> str:
    """The p3 bench command for a long run: --topic for a test topic, --only teach --minutes M for
    the length study, --repeats for how many are missing."""
    cmd = f"uv run p3 bench --config {name}"
    if topic_id != util.SHARED_TOPIC:
        cmd += f" --topic {topic_id}"
    if minutes is not None:
        cmd += f" --only teach --minutes {minutes}"
    if repeats > 1:
        cmd += f" --repeats {repeats}"
    return cmd


def _start(what: str, cmd: str) -> str:
    return f"In a plain terminal at the repo root, start {what} with this command, and leave it running: {cmd}"


def _score(root: Path, rec: util.RunRecord) -> str:
    rel = util.posix(rec.dir, root)
    return f"{rel} finished but is not scored; in a plain terminal at the repo root, score it: uv run p3 score {rel}"


def _them(have: int, need: int) -> str:
    """What Also says to start: "it", "them", "the last one" or "the last two"."""
    if have == 0:
        return "it" if need == 1 else "them"
    left = need - have
    return "the last one" if left == 1 else f"the last {_word(left)}"


def _runs_item(root: Path, name: str, need: int, page: str, label: str, topic_id: str = util.SHARED_TOPIC) -> Item:
    """`need` scored full runs of a config, as p3 check counts them: on the shared topic at its 30
    minutes, or on a test topic at any length. A run with no score yet is scored, not run again."""
    minutes = check.BENCH_MINUTES if topic_id == util.SHARED_TOPIC else None
    have = len(check._full_runs(root, name, topic_id, minutes))
    runs = _plural(need, "scored full run")
    on = "" if topic_id == util.SHARED_TOPIC else f" on {topic_id}"
    so_far = f"{have} so far" if have else "none yet"
    item = Item(f"{runs} of {name}{on} ({so_far})", have >= need, page=page, long=True, key=f"runs:{name}")
    if item.done:
        return item
    left = need - have
    unscored = util.list_runs(name, topic_id, scored=False, quick=False, minutes=minutes, kind=util.FULL, root=root)
    if unscored:
        item.action = _score(root, unscored[0])
        item.also = f"{label}: {have} of {runs} (score {util.posix(unscored[0].dir, root)} in a plain terminal)"
        return item
    what = "the full run" if need == 1 else "the last full run" if left == 1 else f"the last {_word(left)} full runs" if have else f"the {_word(need)} full runs"
    item.action = _start(what, _bench(name, topic_id, repeats=left))
    item.also = f"{label}: {have} of {runs} (start {_them(have, need)} in a plain terminal)"
    return item


def _study_item(root: Path, name: str, page: str) -> Item:
    """The length study's runs of a config: three scored teach-only runs at each length."""
    need = check.STUDY_RUNS
    counts = {m: len(util.list_runs(name, util.SHARED_TOPIC, scored=True, quick=False, minutes=m, kind=util.TEACH_ONLY, root=root)) for m in check.STUDY_MINUTES}
    cells = ", ".join(f"{c} at {m}" for m, c in counts.items())
    lengths = _and([str(m) for m in check.STUDY_MINUTES])
    item = Item(f"{need} teach-only runs of {name} at each of {lengths} minutes ({cells})", all(c >= need for c in counts.values()), page=page, long=True, key=f"study:{name}")
    if item.done:
        return item
    minutes = next(m for m, c in counts.items() if c < need)
    have = counts[minutes]
    unscored = util.list_runs(name, util.SHARED_TOPIC, scored=False, quick=False, minutes=minutes, kind=util.TEACH_ONLY, root=root)
    if unscored:
        item.action = _score(root, unscored[0])
    else:
        what = f"the {minutes}-minute runs" if not have else f"the last {minutes}-minute run" if need - have == 1 else f"the last {_word(need - have)} {minutes}-minute runs"
        item.action = _start(what, _bench(name, minutes=minutes, repeats=need - have))
    item.also = f"the length study's runs of {name}: {cells} minutes, of {need} each (start the rest in a plain terminal)"
    return item


# ---- what the map reads ----


@dataclass
class Repo:
    """The repo as the map reads it; each review file is parsed once."""

    root: Path
    section: str | None
    study: bool  # 598E, or the length-study stretch
    configs: list[str]
    own: list[str]  # the test topics in bench/own/
    integrity_ok: bool
    parsed: dict[str, reviews.StepReview | None] = field(default_factory=dict)

    def review(self, step: str) -> reviews.StepReview | None:
        if step not in self.parsed:
            self.parsed[step] = reviews.read_step(step, self.root)
        return self.parsed[step]

    def review_problem(self, rel: str) -> tuple[str, str] | None:
        """(state, action) for a review file that is missing or not UTF-8, which p3 cannot read."""
        if not (self.root / rel).is_file():
            return f"{rel} is missing", f"Copy {rel} back from the template; your reviews go in it."
        problem = util.utf8_problem(self.root / rel)
        if problem:
            return f"{rel} is not UTF-8", f"{rel}: {problem}, so p3 cannot read its headings; {util.NON_UTF8_HINT}."
        return None


def running_runs(root: Path, now: float | None = None) -> list[str]:
    """The run folders under bench/runs/ (bench/runs/_live/ left out, as p3 check leaves it out)
    with no run.json and a file changed in the last RUNNING_MINUTES, as repo-relative paths: a bench
    still running, which p3 check reports as a run that was stopped."""
    base = root / "bench" / "runs"
    if not base.is_dir():
        return []
    now = time.time() if now is None else now
    found = []
    for folder in sorted(p for p in base.iterdir() if p.is_dir() and p.name != util.LIVE_RUNS_DIR and not p.name.startswith(".")):
        for run_dir in sorted(p for p in folder.iterdir() if p.is_dir()):
            if not (run_dir / "run.json").is_file() and now - _last_change(run_dir) <= RUNNING_MINUTES * 60:
                found.append(f"bench/runs/{folder.name}/{run_dir.name}")
    return found


def _last_change(folder: Path) -> float:
    """The newest modification time of a folder and of everything in it (0 for a folder gone, as
    when p3 bench sets a stopped repeat aside)."""
    try:
        newest = folder.stat().st_mtime
    except OSError:
        return 0.0
    for dirpath, dirnames, filenames in os.walk(folder):
        for name in dirnames + filenames:
            try:
                newest = max(newest, (Path(dirpath) / name).stat().st_mtime)
            except OSError:
                continue
    return newest


def failures(report: check.Checklist, running: list[str], section: str | None = None) -> list[check.Item]:
    """The FAIL items of a checklist (of one section when given), without the runs still going:
    their details are dropped, and an item left with no detail is dropped."""
    found = []
    for item in report.items(section):
        if item.status != check.FAIL:
            continue
        details = [d for d in item.details if not any(d.startswith(f"{rel}/ has no run.json") for rel in running)]
        if item.details and not details:
            continue
        found.append(check.Item(item.status, item.text, details))
    return found


def _settings(root: Path) -> dict:
    data, _error = check._read_json(root / "p3.json")
    return data if isinstance(data, dict) else {}


def _git_origin(root: Path) -> str:
    """The URL of the origin remote, or "" when there is none."""
    done = util._git(["remote", "get-url", "origin"], root)
    return done.stdout.strip() if done is not None and done.returncode == 0 else ""


# ---- the stages ----


def _setup(repo: Repo) -> Stage:
    page = "01-setup.html"
    copy = "Set up your repo as the setup page says: make your own copy of the template on GitHub (Use this template), clone it with git into work/p3-tutor, and run p3 next there."
    problem = util.git_problem(repo.root)
    if problem:
        origin = Item(f"your own repo, cloned with git ({problem})", False, copy, page)
    else:
        url = _git_origin(repo.root)
        if not url:
            origin = Item("an origin remote, your own repo on GitHub (this clone has none)", False, "Point origin at your own repo on GitHub: git remote add origin https://github.com/<your-github-username>/p3-tutor.git", page)
        elif TEMPLATE_URL_RE.search(url):
            origin = Item(f"an origin remote that is your own repo (origin is the course template, {url})", False, copy, page)
        else:
            origin = Item(f"an origin remote that is your own repo ({url})", True, page=page)
    integrity = Item("no integrity failure in p3 check", repo.integrity_ok, "Run p3 check and fix its first FAIL line.", TROUBLESHOOTING)
    return Stage(1, "Set up", [origin, integrity])


def _baseline(repo: Repo) -> Stage:
    page = "03-baseline.html"
    first = Item("a first run of c0-baseline", bool(util.list_runs("c0-baseline", root=repo.root)), page=f"{page}#quick-run")
    if not first.done:
        first.name += " (none yet)"
        first.action = "Run the baseline once, quickly, in a terminal at the repo root: uv run p3 bench --config c0-baseline --quick"
    runs = _runs_item(repo.root, "c0-baseline", check.SHARED_RUNS["c0-baseline"], f"{page}#full-runs", "the baseline's runs")
    return Stage(2, "The baseline", [first, runs])


def _preferences(repo: Repo) -> Stage:
    mine, shipped = repo.root / "tutor" / "PREFERENCES.md", repo.root / "configs" / "c0-baseline" / "PREFERENCES.md"
    done = mine.is_file() and (not shipped.is_file() or util.normalized_bytes(mine) != util.normalized_bytes(shipped))
    name = "your own tutor/PREFERENCES.md" + ("" if done else " (it is still the one the template ships)" if mine.is_file() else " (it is missing)")
    action = "Write how you like to learn in tutor/PREFERENCES.md, in your own words, under its five headings."
    return Stage(3, "Your preferences", [Item(name, done, action, "04-preferences.html")])


def _rounds(repo: Repo, step: str, page: str) -> Item:
    """The quick rounds of a step: the advice for the first round that is not complete, then for
    adding a round, then (in step 1) for a required skill still missing from tutor/."""
    rel = reviews.step_file(step)
    problem = repo.review_problem(rel)
    if problem:
        return Item(f"quick rounds ({problem[0]})", False, problem[1], page)
    review = repo.review(step)
    need = reviews.MIN_ROUNDS[step]
    complete = [r for r in review.rounds if r.complete]
    state = f"{len(complete)} of at least {need} complete" if len(complete) < need else f"{len(complete)} complete"
    if review.rounds_problem:
        return Item(f"quick rounds ({state})", False, f"Fix {rel}: {_sentence(review.rounds_problem)}", page)
    # an untouched optional round is left out of every count, as p3 check leaves it out
    first = next((r for r in review.rounds if not r.complete and (r.touched or not r.optional)), None)
    if first is not None:
        k = _number(first.title)
        if not first.touched:
            action = f"{LIVE_TRY}, then write what you noticed under Round {k} > My thoughts in {rel}."
        elif reviews.written(first.thoughts) and None not in (first.kind, first.files, first.why) and not any(reviews.written(t) for t in (first.kind, first.files, first.why)):
            action = f"In the Builder window, say: Act on Round {k} of {rel}."
        else:
            action = f"Finish Round {k} in {rel}: {_sentence(_without(f'{reviews.QUICK_ROUNDS} > {first.title}', first.problems[0]))}"
        return Item(f"quick rounds ({state})", False, action, page)
    k = max((_number(r.title) for r in review.rounds), default=0) + 1
    if len(complete) < need:
        return Item(f"quick rounds ({state})", False, f"Add Round {k} to {rel} by copying the last round with its marker lines.", page)
    lacking = [s for s in check.SKILLS if s not in check._skills(repo.root / "tutor")] if step == check.C1 else []
    if lacking:
        action = f"Add a round for the {lacking[0]} skill: copy the last round of {rel} with its marker lines, as Round {k}."
        return Item(f"quick rounds ({state}; no {lacking[0]} skill in tutor/ yet)", False, action, page)
    return Item(f"quick rounds ({state})", True, page=page)


def _number(title: str) -> int:
    """The number of a "Round 2" or "Session 2" heading."""
    m = re.search(r"\d+", reviews.name_key(title))
    return int(m.group(0)) if m else 0


def _snapshot(repo: Repo, name: str, page: str, action: str, hook: bool = False) -> Item:
    """A snapshot of the ladder, with the four skills (and in final the guard)."""
    if name not in repo.configs:
        return Item(f"snapshot {name} (not made yet)", False, action, page)
    folder = repo.root / "configs" / name
    lacking = [s for s in check.SKILLS if s not in check._skills(folder)]
    no_hook = hook and not check._has_pretooluse_hook(folder)
    problems = [f"no {_and(lacking)} skill" + ("s" if len(lacking) > 1 else "")] if lacking else []
    problems += ["no PreToolUse hook"] if no_hook else []
    if not problems:
        return Item(f"snapshot {name}", True, page=page)
    what = _and(problems)
    fix = f"configs/{name}/ has {what}; put {'it' if len(lacking) + no_hook == 1 else 'them'} in tutor/ and snapshot again: uv run p3 snapshot {name} --force"
    runs = util.list_runs(name, root=repo.root)
    if runs:
        one = len(runs) == 1
        fix += f" (its {_plural(len(runs), 'run')} then no longer {'matches' if one else 'match'} it, so delete {'it' if one else 'them'} and run the new snapshot again)"
    return Item(f"snapshot {name} ({what} in it)", False, _sentence(fix), page)


def _major(repo: Repo, step: str, page: str, committed: bool = False) -> Item:
    """The major review of a step, complete as p3 check judges it; for final also first committed
    complete after its run finished."""
    rel = reviews.step_file(step)
    name = "the major review" + (", complete and committed" if committed else "")
    problem = repo.review_problem(rel)
    if problem:
        return Item(f"{name} ({problem[0]})", False, problem[1], page, waits=True)
    review = repo.review(step)
    scratch: list[check.Item] = []
    rec = check._check_major(repo.root, True, review, scratch)
    if rec is None:
        if review.major.present and not review.major.touched:
            runs = check._full_runs(repo.root, step, util.SHARED_TOPIC)
            target = util.posix(runs[-1].dir, repo.root) if runs else f"a scored full run of {step}"
            action = f"Write the major review of {target} in {rel}, under ## Major review: its Run line, your live tries of the tutor, then each criterion rated from 1 to 5 with feedback."
            return Item(f"{name} (not written yet)", False, action, page, waits=True)
        problems = scratch[0].details
        action = f"Finish the major review in {rel}: {_sentence(_without(reviews.MAJOR_REVIEW, problems[0]))}"
        return Item(f"{name} ({_plural(len(problems), 'thing')} left)", False, action, page, waits=True)
    if not committed:
        return Item(f"{name} (of {util.posix(rec.dir, repo.root)})", True, page=page, waits=True)
    scratch = []
    check._check_review_order(repo.root, True, review, rec, scratch)
    order = scratch[0]
    if order.status == check.OK:
        return Item(name, True, page=page, waits=True)
    if "in no commit yet" in order.text:
        action = f"Commit and push {rel}, so your open review is on record before the blind comparison."
        return Item(f"{name} (complete, not committed yet)", False, action, page, waits=True)
    return Item(f"{name} (not committed after its run)", False, _sentence(order.text), page, waits=True)


def _eval_section(repo: Repo, number: int, step_number: int, page: str) -> Item:
    """A section of EVAL.md, found by its heading (## 2. Step 1), with no TODO marker in it."""
    name = f"section {number} of EVAL.md"
    path = repo.root / "EVAL.md"
    if not path.is_file():
        return Item(f"{name} (EVAL.md is missing)", False, "Copy EVAL.md back from the template; your write-up goes in it.", page, waits=True)
    text = util.read_text(path)
    lines = text.split("\n")
    heading = re.compile(rf"^##\s+{number}\.\s*Step\s+{step_number}\b", re.I)
    start = next((n for n, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        if not check._todo_lines(text):
            return Item(name, True, page=page, waits=True)
        action = f"Put back the heading of section {number} of EVAL.md, which starts with ## {number}. Step {step_number}, as the template has it; p3 next finds the section by it."
        return Item(f"{name} (its heading is not there)", False, action, page, waits=True)
    end = next((n for n in range(start + 1, len(lines)) if re.match(r"^#{1,2}\s", lines[n])), len(lines))
    todo = [start + n for n in check._todo_lines("\n".join(lines[start:end]))]
    if not todo:
        return Item(name, True, page=page, waits=True)
    markers = _plural(len(todo), "TODO marker")
    action = f"Write section {number} of EVAL.md in your own words: {markers} left ({_lines(todo)})."
    return Item(f"{name} ({markers} left)", False, action, page, waits=True)


def _inventory(repo: Repo, step: str, page: str) -> Item:
    """An entry in reviews/components.md for each skill and subagent of the step's snapshot, with
    its Purpose and Review written (Kept in final waits for final)."""
    rel = reviews.COMPONENTS_PATH
    name = "the inventory entries"
    if step not in repo.configs:
        return Item(f"{name} (no snapshot {step} yet)", False, f"Snapshot {step} first: uv run p3 snapshot {step}", page)
    problem = repo.review_problem(rel)
    if problem:
        return Item(f"{name} ({problem[0]})", False, problem[1], page)
    folder = repo.root / "configs" / step
    built = [(reviews.SKILL, n) for n in reviews.skill_names(folder)] + [(reviews.SUBAGENT, n) for n in sorted(reviews.subagents(folder))]
    entries = reviews.read_components(repo.root) or []
    missing, unwritten = [], []
    for kind, component in built:
        key = reviews.name_key(component)
        entry = next((e for e in entries if e.key == key and e.kind in (kind, None)), None)
        if entry is None:
            missing.append(component)
        elif not (reviews.written(entry.values.get("Purpose")) and reviews.written(entry.values.get("Review"))):
            unwritten.append(component)
    state = f"{len(built) - len(missing) - len(unwritten)} of {_plural(len(built), 'component')} of configs/{step}/ with Purpose and Review written"
    if missing:
        action = f"In the Builder window, say: Add an entry to {rel} for each component of configs/{step}/ that has none ({_and(missing)}), with Kind, Step added, and With and without."
    elif unwritten:
        action = f"Write Purpose and Review for {_and(unwritten)} in {rel}; they are yours to write, and reviews/README.md says what each holds."
    else:
        return Item(f"{name} ({state})", True, page=page)
    return Item(f"{name} ({state})", False, action, page)


# what a step must hold before its snapshot, which neither p3 next nor p3 check can see
STEP_READY = {
    check.C1: "When the four skills are in and you are happy with the tutor",
    "c2-review": "When teach, quiz and grade each have their review loop and you are happy with the tutor",
    "c3-split": "When the teach job is split across its subagents and you are happy with the tutor",
}


def _step(repo: Repo, number: int, step_number: int, step: str, page: str) -> Stage:
    snapshot = f"{STEP_READY[step]}, snapshot it: uv run p3 snapshot {step} (or add another round first)."
    items = [
        _rounds(repo, step, f"{page}#rounds"),
        _snapshot(repo, step, f"{page}#snapshot", snapshot),
        _runs_item(repo.root, step, check.SHARED_RUNS[step], f"{page}#full-run", f"the run of {step}"),
        _major(repo, step, f"{page}#major-review"),
        _eval_section(repo, step_number + 1, step_number, f"{page}#eval"),
        _inventory(repo, step, f"{page}#inventory"),
    ]
    return Stage(number, f"Step {step_number}, {step}", items)


def _prereg(repo: Repo, page: str) -> Item:
    """PREREG.md with sections 1 to 4 written (section 5 is written after the runs) and committed,
    before the first length-study run, as p3 check judges it."""
    name = "PREREG.md, sections 1 to 4 written and committed"
    path = repo.root / "PREREG.md"
    if not path.is_file():
        return Item(f"{name} (PREREG.md is missing)", False, "Copy PREREG.md back from the template; your plan for the length study goes in it.", page)
    todo = check._todo_lines(check._prereg_head(util.read_text(path)))
    if todo:
        markers = _plural(len(todo), "TODO marker")
        return Item(f"{name} ({markers} left)", False, f"Write sections 1 to 4 of PREREG.md, your plan, before any length-study run: {markers} left ({_lines(todo)}).", page)
    scratch: list[check.Item] = []
    check.check_length_study(repo.root, True, scratch)
    found = next(i for i in scratch if i.text.startswith("PREREG.md"))
    if found.status == check.OK:
        return Item(name, True, page=page)
    if found.status == check.WARN:  # not a git repository, which stage 1 already says
        return Item(f"{name} (git cannot tell when)", False, _sentence(found.text), page)
    if "no commit has" in found.text:
        return Item(f"{name} (not committed yet)", False, "Commit and push PREREG.md before the first length-study run.", page)
    action = f"{found.text}; the plan must be committed before the runs, so delete the length-study runs made before it and make them again."
    return Item(f"{name} (committed after a run)", False, action, page)


def _study(repo: Repo) -> Stage:
    page = "16-stretch-and-598e.html"
    return Stage(6, "The length study, part 1", [_prereg(repo, f"{page}#prereg"), _study_item(repo.root, check.STUDY_CONFIGS[0], f"{page}#length-runs")])


def _test_topics(repo: Repo) -> Stage:
    page = "11-test-topics.html"
    own, need = repo.own, check.OWN_TOPICS
    start = "Start a test topic with uv run p3 new-topic <id> (lowercase letters, digits and hyphens), then write its items yourself, as bench/own/README.md says."
    if len(own) < need:
        count = Item(f"{_word(need)} test topics in bench/own/ ({len(own)} so far)", False, start, page)
    elif len(own) > need:
        count = Item(f"{_word(need)} test topics in bench/own/ ({len(own)}: {_and(own)})", False, f"Keep exactly {_word(need)} test topics in bench/own/: the hand-in needs {_word(need)}, so delete the others ({_and(own)} are there now).", page)
    else:
        count = Item(f"{_word(need)} test topics in bench/own/ ({_and(own)})", True, page=page)
    bad = []
    for tid in own:
        v = topic.validate(repo.root / "bench" / "own" / tid, topic.OWN)
        if not v.ok(allow_todo=False):
            bad.append((tid, v))
    if not own:
        valid = Item("each valid, with no TODO left (no test topic yet)", False, start, page)
    elif bad:
        tid, v = bad[0]
        verb = "Fix" if v.errors else "Finish"
        valid = Item(f"each valid, with no TODO left (bench/own/{tid}/ is not yet)", False, f"{verb} bench/own/{tid}/: {_sentence((v.errors or v.todos)[0])}", page)
    else:
        valid = Item("each valid, with no TODO left", True, page=page)
    dirty = [tid for tid in own if not util.path_clean_and_tracked(f"bench/own/{tid}", repo.root)]
    if not own:
        committed = Item("each committed, with no change since (no test topic yet)", False, start, page)
    elif dirty:
        tid = dirty[0]
        if util.list_runs(None, tid, root=repo.root):
            action = f"bench/own/{tid}/ has changed since it was committed, and it has runs, so restore it from git (git restore bench/own/{tid}); to fix a real mistake in it, follow \"Commit before the first run\" in bench/own/README.md."
        else:
            action = f"Commit and push bench/own/{tid}/ before any run on it, so the runs show its items were written first."
        committed = Item(f"each committed, with no change since (bench/own/{tid}/ is not)", False, action, page)
    else:
        committed = Item("each committed, with no change since", True, page=page)
    return Stage(8, "Test topics", [count, valid, committed])


def _ablation_runs(repo: Repo, page: str, names: list[str]) -> Item:
    if not names:
        return Item(f"the full run of a {check.ABLATION_PREFIX}<x> snapshot (no snapshot yet)", False, page=page, long=True)
    for name in names:
        if len(check._full_runs(repo.root, name, util.SHARED_TOPIC, check.BENCH_MINUTES)) < check.ABLATION_RUNS:
            return _runs_item(repo.root, name, check.ABLATION_RUNS, page, f"the run of {name}")
    return Item(f"the full run of {_and(names)}", True, page=page, long=True)


def _topic_runs(repo: Repo, page: str) -> Item:
    """A scored full run of c0-baseline and of final on each test topic."""
    pairs = [(tid, name) for tid in repo.own for name in TOPIC_CONFIGS]
    missing = [(tid, name) for tid, name in pairs if not check._full_runs(repo.root, name, tid)]
    total = max(len(pairs), check.OWN_TOPICS * len(TOPIC_CONFIGS))
    have = len(pairs) - len(missing)
    item = Item(f"runs of {_and(list(TOPIC_CONFIGS))} on both test topics ({have} of {total} so far)", len(repo.own) >= check.OWN_TOPICS and not missing, page=page, long=True, key="topic-runs")
    item.also = f"the test topics' runs: {have} of {total} (start the rest in a plain terminal)"
    if not missing:
        return item
    tid, name = missing[0]
    unscored = util.list_runs(name, tid, scored=False, quick=False, kind=util.FULL, root=repo.root)
    item.action = _score(repo.root, unscored[0]) if unscored else _start(f"the run of {name} on {tid}", _bench(name, tid))
    return item


def _sessions(repo: Repo, page: str) -> Item:
    """Three complete learning sessions in reviews/final.md, all on one test topic."""
    rel = reviews.step_file("final")
    need = reviews.SESSIONS
    name = f"{_word(need)} learning sessions"
    problem = repo.review_problem(rel)
    if problem:
        return Item(f"{name} ({problem[0]})", False, problem[1], page)
    review = repo.review("final")
    scratch: list[check.Item] = []
    check._check_sessions(True, review, repo.own, scratch)
    problems = {id(s): check._session_problems(s, repo.own) for s in review.sessions}
    complete = [s for s in review.sessions if not problems[id(s)]]
    state = f"{len(complete)} of {need} complete"
    if scratch[0].status == check.OK:
        return Item(f"{name} ({state})", True, page=page)
    if review.sessions_problem:
        return Item(f"{name} ({state})", False, f"Fix {rel}: {_sentence(review.sessions_problem)}", page)
    first = next((s for s in review.sessions if problems[id(s)] and (s.touched or len(complete) < need)), None)
    if first is None and len(complete) < need:
        k = max((_number(s.title) for s in review.sessions), default=0) + 1
        action = f"Add Session {k} to {rel} by copying the last session with its Date and Topic lines."
    elif first is None:  # enough complete sessions, on more than one test topic
        action = f"Fix {rel}: {_sentence(_without(reviews.LEARNING_SESSIONS, scratch[0].details[-1]))}"
    elif not first.touched:
        on = sorted({s.topic_id for s in complete})  # all three on one topic, so the one the others are on
        others = "as your other session was" if len(complete) == 1 else "as your other sessions were"
        where = f"on {on[0]}, {others}" if len(on) == 1 else f"on one of your test topics ({_and(repo.own)})" if repo.own else "on one of your test topics"
        action = f"Hold learning session {_number(first.title)}: open a terminal in tutor/, start claude there with tutor/ as you snapshotted final, and learn something {where}; then write it up under {first.title} in {rel}."
    else:
        action = f"Finish {first.title} in {rel}: {_sentence(_without(f'{reviews.LEARNING_SESSIONS} > {first.title}', problems[id(first)][0]))}"
    return Item(f"{name} ({state})", False, action, page)


def _final(repo: Repo) -> Stage:
    page = "12-final.html"
    guard = check._has_pretooluse_hook(repo.root / "tutor")
    guard_action = "In the Builder window, say: Add the guard to tutor/.claude/settings.json, a PreToolUse hook that keeps the answer keys in keys/ away from the main conversation while the grader can still read them."
    snapshot = "Snapshot the tutor as final, and commit tutor/ with it, so git restore tutor/ brings it back after the ablation: uv run p3 snapshot final"
    ablations = [n for n in repo.configs if n.startswith(check.ABLATION_PREFIX)]
    ablation = "Make the ablation: take one component out of tutor/, snapshot it as final-minus-<the component> (uv run p3 snapshot final-minus-<x>), then bring tutor/ back with git restore tutor/."
    items = [
        Item("the guard, a PreToolUse hook in tutor/.claude/settings.json" + ("" if guard else " (not there yet)"), guard, guard_action, f"{page}#guard"),
        _snapshot(repo, "final", f"{page}#snapshot", snapshot, hook=True),
        _runs_item(repo.root, "final", check.SHARED_RUNS["final"], f"{page}#runs", "the runs of final"),
        Item(f"an ablation snapshot, {check.ABLATION_PREFIX}<x>" + (f" ({_and(ablations)})" if ablations else " (none yet)"), bool(ablations), ablation, f"{page}#ablation"),
        _ablation_runs(repo, f"{page}#ablation", ablations),
        _topic_runs(repo, f"{page}#test-topic-runs"),
    ]
    if repo.study:
        items.append(_study_item(repo.root, "final", "16-stretch-and-598e.html#length-runs"))
    items += [_sessions(repo, f"{page}#learning-sessions"), _major(repo, "final", f"{page}#major-review", committed=True)]
    return Stage(9, "final", items)


def _open_session(root: Path, configs: tuple[str, str], job: str, teach_only: bool = False, minutes: int | None = None) -> str | None:
    """The id of an unfinished comparison session of these configs and job on the shared topic (of
    full runs, or of the length study's runs at `minutes`), which --resume continues."""
    for path in compare.session_files(root):
        record, _error = check._read_json(path)
        if not isinstance(record, dict) or record.get("complete") is True or not isinstance(record.get("configs"), list):
            continue
        if set(map(str, record["configs"])) != set(configs) or record.get("job") != job or record.get("topic") != util.SHARED_TOPIC:
            continue
        if record.get("quick") or bool(record.get("teach_only")) != teach_only or (teach_only and record.get("minutes") != minutes):
            continue
        return str(record.get("session") or path.stem)
    return None


def _compare_action(sid: str | None, what: str, cmd: str) -> str:
    if sid:
        return f"Finish the {what} you started, in your own terminal at the repo root: uv run p3 compare --resume {sid}"
    return f"In your own terminal at the repo root, start the {what}: {cmd}"


def _blind(repo: Repo) -> Stage:
    page = "13-blind-comparison.html"
    a, b = check.BLIND_COMPARE
    complete = {(configs, job, tid) for (configs, job, tid, _minutes) in check.complete_sessions(repo.root)}
    jobs = check.BLIND_COMPARE_JOBS
    done = [j for j in jobs if (frozenset((a, b)), j, util.SHARED_TOPIC) in complete]
    state = f"{len(done)} of {len(jobs)} jobs" + (f": {_and(done)}" if done else "")
    # its pairs come from the runs there are when it starts, so it waits for all of both configs' runs
    item = Item(f"complete sessions of {a} against {b}, one for each of {_and(list(jobs))} ({state})", len(done) == len(jobs), page=page, waits=True, needs=(f"runs:{a}", f"runs:{b}"))
    if not item.done:
        job = next(j for j in jobs if j not in done)
        item.action = _compare_action(_open_session(repo.root, (a, b), job), f"blind comparison of the {job} job", f"uv run p3 compare {a} {b} --job {job}")
    items = [item]
    if repo.study:
        a, b = check.STUDY_CONFIGS
        sessions = check.complete_sessions(repo.root, teach_only=True)
        have = [m for m in check.STUDY_MINUTES if (frozenset((a, b)), "teach", util.SHARED_TOPIC, m) in sessions]
        lengths = _and([str(m) for m in check.STUDY_MINUTES])
        study = Item(
            f"the length study's teach-only sessions of {a} against {b} at {lengths} minutes ({len(have)} of {len(check.STUDY_MINUTES)})", len(have) == len(check.STUDY_MINUTES),
            page=page, waits=True, needs=(f"study:{a}", f"study:{b}"),
        )  # fmt: skip
        if not study.done:
            m = next(m for m in check.STUDY_MINUTES if m not in have)
            study.action = _compare_action(_open_session(repo.root, (a, b), "teach", True, m), f"teach-only comparison at {m} minutes", f"uv run p3 compare {a} {b} --job teach --teach-only --minutes {m}")
        items.append(study)
    return Stage(10, "The blind comparison", items)


def _writeup(repo: Repo) -> Stage:
    page = "14-write-up.html"
    rel = reviews.step_file("final")
    name = f"your open review of each test topic in {rel}"
    problem = repo.review_problem(rel)
    if problem:
        topics = Item(f"{name} ({problem[0]})", False, problem[1], page, waits=True)
    else:
        scratch: list[check.Item] = []
        check._check_topic_reviews(True, repo.review("final"), repo.own, scratch)
        found = scratch[0]
        detail = _without(reviews.TEST_TOPICS, found.details[0]) if found.details else found.text
        topics = Item(name, found.status == check.OK, f"Finish ## {reviews.TEST_TOPICS} in {rel}: {_sentence(detail)}", page, waits=True, needs=("topic-runs",))
    scratch = []
    check.check_inventory(repo.root, True, repo.section, scratch)
    bad = [i for i in scratch if i.status != check.OK]
    inventory = Item(f"{reviews.COMPONENTS_PATH} complete, with the minimum of components built", not bad, page=page)
    if bad and bad[0].text.startswith("components built"):
        inventory.action = f"Your snapshots are short of the minimum: {_sentence(bad[0].text)}"
    elif bad:
        inventory.action = f"Finish {reviews.COMPONENTS_PATH}: {_sentence(bad[0].details[0] if bad[0].details else bad[0].text)}"
    scratch = []
    check.check_docs(repo.root, True, repo.study, scratch)
    bad = [i for i in scratch if i.status != check.OK]
    docs = Item(("EVAL.md and PREREG.md" if repo.study else "EVAL.md") + " with no TODO left", not bad, page=page, waits=True, needs=(ALL_RUNS,))
    if bad:
        docs.action = f"{bad[0].text}; copy it back from the template." if bad[0].text.endswith("is missing") else f"Write the rest of {_sentence(bad[0].text)}"
    return Stage(11, "The write-up", [topics, inventory, docs])


def stages(repo: Repo) -> list[Stage]:
    """The map, stage by stage: 1 to 11 (12 Hand in is p3 check --final itself)."""
    found = [_setup(repo), _baseline(repo), _preferences(repo)]
    for number, step_number, step, page in STEP_STAGES:
        if number == 7 and repo.study:  # the length study needs only c1-skills, so it comes before step 3
            found.append(_study(repo))
        found.append(_step(repo, number, step_number, step, page))
    found += [_test_topics(repo), _final(repo), _blind(repo), _writeup(repo)]
    return found


def current(found: list[Stage]) -> int | None:
    """The index of the stage you are in: the first with an item not done, unless its only items
    left are long runs and an item of a later stage is done (you moved on while they run). None
    when every stage is done or passed."""
    for n, stage in enumerate(found):
        left = [i for i in stage.items if not i.done]
        if not left:
            continue
        moved_on = any(i.done for later in found[n + 1:] for i in later.items)
        if not (moved_on and all(i.long for i in left)):
            return n
    return None


def position(found: list[Stage]) -> tuple[int, Item] | None:
    """(stage index, item) of what to do next: the first item not done of the current stage, unless
    it needs a long run left behind in a stage passed (a blind comparison pairs only the runs there
    are), or everything left is such a run; then the stage of the first of those runs, which is a
    long run itself. None when every item of the map is done."""
    n = current(found)
    item = next(i for i in found[n].items if not i.done) if n is not None else None
    if item is None or (item.waits and item.needs):
        wanted = item.needs if item is not None else (ALL_RUNS,)
        blocker = next((i for s in found for i in s.items if i.long and not i.done and (ALL_RUNS in wanted or i.key in wanted)), None)
        if blocker is not None:
            n = next(k for k, s in enumerate(found) if any(i is blocker for i in s.items))
            item = next(i for i in found[n].items if not i.done)
    return (n, item) if item is not None else None


# ---- the command ----


def _details(item: check.Item) -> list[str]:
    shown = item.details[:MAX_DETAILS]
    if len(item.details) > MAX_DETAILS:
        shown.append(f"... and {len(item.details) - MAX_DETAILS} more (p3 check lists them all)")
    return shown


def where(root: Path | None = None) -> Report:
    """Where the repo is on the map, as a Report (nothing is printed)."""
    root = Path(root) if root else util.repo_root()
    if not ((root / "p3.json").is_file() or (root / "bench" / "scenarios.json").is_file()):
        raise P3Error(f"{root} is not a P3 repository (it has no p3.json); run p3 next in your repo's root folder")
    settings = _settings(root)
    section, stretch = settings.get("section"), settings.get("stretch")
    header = f"p3 next: {section or 'no section'}" + (f", stretch {stretch}" if stretch else "") + f" ({root})"
    running = running_runs(root)
    broken = failures(check.run_checks(root), running, check.INTEGRITY)
    own = [tid for tid, kind, _folder in topic.list_topics(root) if kind == topic.OWN]
    study = section == "598E" or stretch == check.LENGTH_STUDY
    repo = Repo(root, section, study, util.list_configs(root), own, not broken)
    found = stages(repo)
    at = position(found)
    n = at[0] if at else len(found)  # past the last stage: 12 Hand in
    also = [f"{rel} has no run.json yet: a bench still running (or one that stopped, which you delete)" for rel in running]
    also += [i.also or i.name for s in found[:n] for i in s.items if not i.done][:MAX_ALSO]
    done = [s.label for k, s in enumerate(found) if k < n or (k > n and s.complete)]
    if broken:
        count = "an integrity failure" if len(broken) == 1 else f"{len(broken)} integrity failures; this is the first"
        return Report(header, done, f"1 Set up: p3 check reports {count}", broken[0].text, f"{GUIDE}/{TROUBLESHOOTING}", _details(broken[0]), also)
    if at is None:
        left = failures(check.run_checks(root, final=True), running)
        if left:
            now = f"12 Hand in: p3 check --final passes ({_plural(len(left), 'FAIL line')} left)"
            return Report(header, done, now, left[0].text, f"{GUIDE}/{HAND_IN}", _details(left[0]), also)
        action = "What is left is outside the repo: record your 5 to 10 minute video, commit and push your last changes, then post your repo's URL and the video in the Project 3 discussion on Canvas."
        return Report(header, done, "12 Hand in: everything p3 check --final checks is done", action, f"{GUIDE}/{HAND_IN}", also=also)
    stage, item = found[n], at[1]
    if item.long:
        k = next(k for k, i in enumerate(stage.items) if i is item)
        later = stage.items[k + 1:] + [i for s in found[n + 1:] for i in s.items]
        follow = next((i for i in later if not i.done and not i.long and not i.waits), None)
        if follow is not None:
            also.append(f"While it runs: {follow.action} See {GUIDE}/{follow.page}.")
    return Report(header, done, f"{stage.label}: {item.name}", item.action, f"{GUIDE}/{item.page}", also=also)


def main(args) -> int:
    """The p3 next command."""
    print(where().text(), end="")
    return 0
