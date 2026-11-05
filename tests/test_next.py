"""p3 next (p3/next.py): the map stage by stage, the round advice, integrity first, Also, the length
study and the done state. Each test builds its repository in a temporary folder with the made-up
fixture (tests/__init__.py), as a git repository with an origin of the student's own, since the
first stage of the map reads git."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import unittest
from datetime import timedelta
from pathlib import Path

from p3 import check, compare, reviews, util
from p3 import next as p3next
from tests import RepoTestCase, add_agents, component_md, components_md, git, git_init, has_git, review_md, write, write_topic
from tests.test_compare import T0, add_config, make_run, stamp

ORIGIN = "https://github.com/student/p3-tutor.git"
TOPICS = ("cooking", "statics")
REVIEWERS = ("lesson-reviewer", "quiz-reviewer", "feedback-reviewer")
SPLIT = ("lesson-planner", "figure-designer")
# 598E builds at least six skills and eight subagents: these on top of the four skills, REVIEWERS and SPLIT
EXTRA_SKILLS = ("notes", "glossary")
EXTRA_REVIEWERS = ("fact-checker", "pedagogy-reviewer", "alignment-reviewer")
BEFORE = "2026-11-02T12:00:00Z"  # before every run below (they start at T0, 2026-11-03T14:00:00Z)
REVIEWED = "2026-11-10T12:00:00Z"  # after every run below finished
GUARD = {
    "permissions": {"allow": ["WebSearch", "WebFetch"]},
    "hooks": {"PreToolUse": [{"matcher": "Read|Grep|Glob|Bash", "hooks": [{"type": "command", "command": "python .claude/hooks/guard.py"}]}]},
}
EVAL_SECTIONS = (
    (1, "The baseline, `c0-baseline`"), (2, "Step 1: `c1-skills` against `c0-baseline`"), (3, "Step 2: `c2-review` against `c1-skills`"),
    (4, "Step 3: `c3-split` against `c2-review`"), (5, "`final` against `c0-baseline`, with repeats"),
)  # fmt: skip
PREREG = "# Pre-registration: the length study\n\n## 1. Hypothesis\n\n{h}\n\n## 5. Outcome (write this after the fact)\n\n{o}\n"
LIVE_TRY = "Run the live tutor (uv run p3 bench --config live --quick, or --only with the scenarios you are working on), then write what you noticed under Round {k} > My thoughts in reviews/{step}.md."
START = "In a plain terminal at the repo root, start {what} with this command, and leave it running: {cmd}"
SESSION_1 = (
    "Hold learning session 1: open a terminal in tutor/, start claude there with tutor/ as you snapshotted final, and learn something on one of your test topics "
    "(cooking and statics); then write it up under Session 1 in reviews/final.md."
)  # fmt: skip


def eval_md(done=()) -> str:
    """EVAL.md shaped as the template ships it, two TODO lines in each section (section n's on lines
    10n + 9 and 10n + 13), with the sections in `done` written ("all" for every one)."""
    out = ["# Evaluation report", "", "Write each section in your own words.", ""]
    for n, title in EVAL_SECTIONS:
        written = done == "all" or n in done
        out += [f"## {n}. {title}", "", "### What changed", "", "My own words." if written else f"TODO: what changed in section {n}.", ""]
        out += ["### What it cost", "", "My own words." if written else "TODO: paste the report tables.", ""]
    return "\n".join(out)


def round_md(n: int, thoughts: bool = True, changed: bool = True, kind: str = "new skill") -> str:
    """One quick round: My thoughts and What changed written, or left as the template's markers."""
    return "\n".join([
        f"### Round {n}", "", f"**Run:** bench/runs/_live/round-{n}", "", "**My thoughts:**", "", "Quiz 0002 q3 gives its answer away in the stem." if thoughts else "TODO", "",
        "**What changed:**", "", f"- Kind: {kind if changed else 'TODO'}", f"- Files: {'tutor/.claude/skills/quiz/SKILL.md' if changed else 'TODO'}",
        f"- Why: {'So that each stem asks without telling.' if changed else 'TODO'}", "",
    ])  # fmt: skip


def step_md(step: str, *rounds: str, major: str | None = None, ratings: dict | None = None) -> str:
    """reviews/<step>.md with these rounds and a complete major review of `major` (a run folder), or
    the template's untouched major review."""
    rest = (review_md(step, major, ratings=ratings) if major else review_md(step, todo=True)).split("## Major review", 1)[1]
    return f"# Reviews: {step}\n\n## Quick rounds\n\n" + "\n".join(rounds) + "\n## Major review" + rest


def session_md(n: int, topic: str = "cooking", untouched: bool = False) -> str:
    if untouched:
        return f"### Session {n}\n\n**Date:** TODO\n\n**Topic:** TODO\n\nTODO\n"
    return f"### Session {n}\n\n**Date:** 2026-11-2{n}\n\n**Topic:** {topic}\n\nForty minutes on knife skills; quiz 0003 q2 was fair.\n"


def final_md(*sessions: str) -> str:
    """reviews/final.md as the template ships it, but with these learning sessions."""
    head, rest = review_md("final", topics=TOPICS, todo=True).split("## Learning sessions")
    return head + "## Learning sessions\n\n" + "\n".join(sessions) + "\n## Test topics" + rest.split("## Test topics")[1]


@unittest.skipUnless(has_git(), "needs git")
class NextTestCase(RepoTestCase):
    """A fixture repository shaped like a fresh copy of the template: a git repository with the
    student's own origin, and the review files, the inventory and EVAL.md as the template ships them."""

    def setUp(self):
        super().setUp()
        util.rehash(self.root)
        git_init(self.root)
        git(self.root, "remote", "add", "origin", ORIGIN)
        for step in reviews.STEPS:
            write(self.root / reviews.step_file(step), review_md(step, todo=True, optional=1 if step == "final" else 0))
        write(self.root / reviews.COMPONENTS_PATH, components_md(component_md("TODO: the component's name", todo=True)))
        write(self.root / "EVAL.md", eval_md())
        self.entries: list[str] = []
        self.reviewers = REVIEWERS
        self.minute = 0

    def where(self) -> p3next.Report:
        return p3next.where(self.root)

    def assertAt(self, now: str, action: str | None = None, read: str | None = None) -> p3next.Report:
        """Assert Now (and Next and Read when given), and return the report."""
        r = self.where()
        self.assertEqual(r.now, now, r.text())
        if action is not None:
            self.assertEqual(r.action, action, r.text())
        if read is not None:
            self.assertEqual(r.read, read, r.text())
        return r

    def run_of(self, cfg: str, run_id: str, **kwargs) -> Path:
        """make_run, each run a minute after the one before."""
        self.minute += 1
        return make_run(self.root, cfg, run_id, stamp(self.minute), **kwargs)

    # ---- the stages, done one by one ----

    def baseline(self, full: int = 3) -> None:
        self.run_of("c0-baseline", "quick", quick=True)
        for k in range(full):
            self.run_of("c0-baseline", f"full-{k + 1}")

    def preferences(self) -> None:
        write(self.root / "tutor" / "PREFERENCES.md", "# How I like to learn\n\nCode first, then the idea.\n")

    def step(self, step: str, agents: tuple[str, ...] = (), kind: str = "new skill") -> None:
        """Every item of a step: two rounds, the snapshot (with the four skills), its full run, its
        major review, its EVAL.md section and an inventory entry for each new component."""
        write(self.root / reviews.step_file(step), step_md(step, round_md(1, kind=kind), round_md(2, kind=kind), major=f"bench/runs/{step}/{step}-r1"))
        add_agents(self.root, *agents)
        add_config(self.root, step, skills=check.SKILLS)
        self.run_of(step, f"{step}-r1")
        write(self.root / "EVAL.md", eval_md(done=set(range(1, reviews.STEPS.index(step) + 3))))
        built = [(name, "skill") for name in reviews.skill_names(self.root / "configs" / step)] + [(name, "subagent") for name in agents]
        self.entries += [component_md(name, kind, step) for name, kind in built if not any(e.startswith(f"### {name}\n") for e in self.entries)]
        write(self.root / reviews.COMPONENTS_PATH, components_md(*self.entries))

    def study(self, runs: int = check.STUDY_RUNS, name: str = "c1-skills") -> None:
        for minutes in check.STUDY_MINUTES:
            for k in range(runs):
                self.run_of(name, f"{name}-m{minutes}-r{k + 1}", minutes=minutes, scenarios=["teach"], only=["teach"])

    def prereg(self) -> None:
        write(self.root / "PREREG.md", PREREG.format(h="The single agent loses more at 60 minutes.", o="TODO: the outcome."))
        git(self.root, "add", "PREREG.md")
        git(self.root, "commit", "-q", "-m", "the plan of the length study", when=BEFORE)

    def topics(self) -> None:
        for tid in TOPICS:
            write_topic(self.root / "bench" / "own" / tid)
        git(self.root, "add", "bench/own")
        git(self.root, "commit", "-q", "-m", "the test topics", when=BEFORE)

    def final(self, runs: int = 3) -> None:
        """Every item of final: the guard, the snapshot, its runs, the ablation, the runs on the test
        topics, the learning sessions and the major review, committed after the runs."""
        add_agents(self.root, *self.reviewers)
        add_config(self.root, "final-minus-split", skills=check.SKILLS, hook=True)
        add_agents(self.root, *self.reviewers, *SPLIT)
        add_config(self.root, "final", skills=check.SKILLS, hook=True)
        for k in range(runs):
            self.run_of("final", f"final-r{k + 1}")
        self.run_of("final-minus-split", "final-minus-split-r1")
        head = util.rev_parse_head(self.root)
        for tid in TOPICS:
            for name in ("c0-baseline", "final"):
                self.run_of(name, f"{name}-{tid}", topic_id=tid, topic_commit=head)
        write(self.root / reviews.step_file("final"), review_md("final", "bench/runs/final/final-r1", topics=TOPICS))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "final and its reviews", when=REVIEWED)

    def compares(self, jobs=check.BLIND_COMPARE_JOBS) -> None:
        a, b = check.BLIND_COMPARE
        for i, job in enumerate(jobs):
            record = compare.new_session(a, b, job, root=self.root, when=T0 + timedelta(seconds=i))
            s = compare.Session(record["session"], self.root)
            for pair in s.pairs:
                s.record(pair["pair_id"], "tie", "Both fit me.", False)

    def build(self, through: int, study: bool = False) -> None:
        """Every stage of the map up to `through`, as a student who did each in turn."""
        if study:
            write(self.root / "p3.json", {"section": "598E", "stretch": None})
            for name in EXTRA_SKILLS:
                write(self.root / "tutor" / ".claude" / "skills" / name / "SKILL.md", f"---\nname: {name}\n---\n\nThe {name} skill.\n")
            self.reviewers = REVIEWERS + EXTRA_REVIEWERS
        stages = [
            (2, self.baseline), (3, self.preferences), (4, lambda: self.step("c1-skills")), (5, lambda: self.step("c2-review", self.reviewers, "new subagent")),
            (6, (lambda: (self.prereg(), self.study())) if study else (lambda: None)), (7, lambda: self.step("c3-split", SPLIT, "new subagent")),
            (8, self.topics), (9, self.final), (10, self.compares),
        ]  # fmt: skip
        for number, do in stages:
            if number <= through:
                do()
        if through >= 11:
            self.write_up(study)

    def write_up(self, study: bool = False) -> None:
        """EVAL.md (and PREREG.md's outcome) written, and everything committed."""
        write(self.root / "EVAL.md", eval_md(done="all"))
        if study:
            write(self.root / "PREREG.md", PREREG.format(h="The single agent loses more at 60 minutes.", o="It did, by a little."))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "the write-up", when=REVIEWED)


class TemplateTests(NextTestCase):
    def test_a_fresh_copy_starts_at_the_baseline(self):
        r = self.assertAt(
            "2 The baseline: a first run of c0-baseline (none yet)",
            "Run the baseline once, quickly, in a terminal at the repo root: uv run p3 bench --config c0-baseline --quick",
            "guide/03-baseline.html#quick-run",
        )
        self.assertEqual((r.done, r.also), (["1 Set up"], []))
        code, out, err = self.p3("next")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(out, (
            f"p3 next: 498E ({self.root})\n\n"
            "Done:  1 Set up\n"
            "Now:   2 The baseline: a first run of c0-baseline (none yet)\n"
            "Next:  Run the baseline once, quickly, in a terminal at the repo root: uv run p3 bench --config c0-baseline --quick\n"
            "Read:  guide/03-baseline.html#quick-run\n"
        ))  # fmt: skip

    def test_the_command_is_listed(self):
        from p3 import cli

        self.assertIn("next", cli.parser().format_help())
        self.assertIn("p3 next", cli.__doc__)

    def test_a_folder_that_is_not_a_p3_repository(self):
        empty = Path(tempfile.mkdtemp(prefix="p3-empty-"))
        self.addCleanup(shutil.rmtree, empty, True)
        os.environ["P3_ROOT"] = str(empty)
        code, _out, err = self.p3("next")
        self.assertEqual(code, 1)
        self.assertIn("is not a P3 repository (it has no p3.json)", err)

    def test_the_header_names_the_section_and_the_stretch(self):
        write(self.root / "p3.json", {"section": "498E", "stretch": "length-study"})
        self.assertEqual(self.where().header, f"p3 next: 498E, stretch length-study ({self.root})")
        write(self.root / "p3.json", {"section": None, "stretch": None})
        self.assertEqual(self.where().header, f"p3 next: no section ({self.root})")


class SetupTests(NextTestCase):
    def test_the_origin_remote(self):
        git(self.root, "remote", "remove", "origin")
        self.assertAt(
            "1 Set up: an origin remote, your own repo on GitHub (this clone has none)",
            "Point origin at your own repo on GitHub: git remote add origin https://github.com/<your-github-username>/p3-tutor.git",
            "guide/01-setup.html",
        )
        git(self.root, "remote", "add", "origin", ORIGIN)
        for url in ("https://github.com/Mines-Coding-with-AI-Agents/P3-tutor.git", "git@github.com:mines-coding-with-ai-agents/p3-tutor", "https://github.com/Mines-Coding-with-AI-Agents/P3-tutor/"):
            git(self.root, "remote", "set-url", "origin", url)
            r = self.where()
            self.assertEqual(r.now, f"1 Set up: an origin remote that is your own repo (origin is the course template, {url})", url)
            self.assertIn("make your own copy of the template on GitHub (Use this template)", r.action)
            self.assertEqual(r.done, [])
        git(self.root, "remote", "set-url", "origin", "https://github.com/Mines-Coding-with-AI-Agents/P3-tutor-alice.git")
        self.assertEqual(self.where().done, ["1 Set up"], "a repo of the course's organization with another name is the student's own")

    def test_outside_a_git_repository(self):
        util.remove_tree(self.root / ".git")
        r = self.where()
        self.assertTrue(r.now.startswith("1 Set up: your own repo, cloned with git (git cannot use this folder as a repository"), r.now)
        self.assertEqual(r.read, "guide/01-setup.html")
        self.assertIn("clone it with git into work/p3-tutor", r.action)


class IntegrityTests(NextTestCase):
    def test_an_integrity_failure_comes_first(self):
        self.baseline()
        self.preferences()
        path = self.root / "bench" / "topics" / "agent-architecture" / "topic.json"
        write(path, {**util.read_json(path), "title": "Easier now"})
        r = self.assertAt("1 Set up: p3 check reports an integrity failure", read="guide/19-troubleshooting.html")
        self.assertTrue(r.action.startswith("p3/bench.sha256: 1 fixed file differ from the course's version; restore it with git"), r.action)
        self.assertEqual(r.details, ["changed: bench/topics/agent-architecture/topic.json"])
        self.assertEqual(r.done, ["2 The baseline", "3 Your preferences"], "the stages after it that are complete")
        write(self.root / "tutor" / "FORMATS.md", "# My own formats\n")
        self.assertAt("1 Set up: p3 check reports 2 integrity failures; this is the first")
        code, out, _err = self.p3("next")
        self.assertEqual(code, 0, "p3 next reports the failure; p3 check is the command that fails")
        self.assertIn("\nNext:  p3/bench.sha256: 1 fixed file differ", out)
        self.assertIn("\n         changed: bench/topics/agent-architecture/topic.json\nRead:  guide/19-troubleshooting.html\n", out)

    def test_many_details_are_cut_short(self):
        for n in range(8):
            write(self.root / "bench" / "judge" / f"extra-{n}.md", "# more\n")
        r = self.where()
        self.assertEqual(len(r.details), p3next.MAX_DETAILS + 1)
        self.assertEqual(r.details[-1], "... and 3 more (p3 check lists them all)")

    def test_a_bench_still_running_is_not_a_failure(self):
        self.baseline(full=1)
        folder = util.runs_dir("c0-baseline", self.root) / "20261103-150000-agent-architecture-m30-r1"
        write(folder / "teach" / "result.json", {"type": "result", "is_error": False, "result": "Done."})
        self.assertEqual(check.run_checks(self.root).exit_code(), 1, "p3 check reports the folder as a stopped run")
        rel = util.posix(folder, self.root)
        r = self.assertAt("2 The baseline: 3 scored full runs of c0-baseline (1 so far)")
        self.assertEqual(r.also[0], f"{rel} has no run.json yet: a bench still running (or one that stopped, which you delete)")
        old = time.time() - (p3next.RUNNING_MINUTES + 30) * 60
        for path in [folder, *folder.rglob("*")]:
            os.utime(path, (old, old))
        r = self.assertAt("1 Set up: p3 check reports an integrity failure")
        self.assertEqual(r.details, [f"{rel}/ has no run.json (a run that was stopped; delete it)"])


class BaselineTests(NextTestCase):
    def test_the_full_runs_are_long_runs(self):
        self.run_of("c0-baseline", "quick", quick=True)
        r = self.assertAt(
            "2 The baseline: 3 scored full runs of c0-baseline (none yet)",
            START.format(what="the three full runs", cmd="uv run p3 bench --config c0-baseline --repeats 3"),
            "guide/03-baseline.html#full-runs",
        )
        self.assertEqual(r.also, ["While it runs: Write how you like to learn in tutor/PREFERENCES.md, in your own words, under its five headings. See guide/04-preferences.html."])
        self.run_of("c0-baseline", "full-1")
        self.assertAt("2 The baseline: 3 scored full runs of c0-baseline (1 so far)", START.format(what="the last two full runs", cmd="uv run p3 bench --config c0-baseline --repeats 2"))
        self.run_of("c0-baseline", "full-2")
        self.assertAt("2 The baseline: 3 scored full runs of c0-baseline (2 so far)", START.format(what="the last full run", cmd="uv run p3 bench --config c0-baseline"))
        self.run_of("c0-baseline", "full-3", scored=False)
        self.assertAt(
            "2 The baseline: 3 scored full runs of c0-baseline (2 so far)",
            "bench/runs/c0-baseline/full-3 finished but is not scored; in a plain terminal at the repo root, score it: uv run p3 score bench/runs/c0-baseline/full-3",
        )

    def test_only_scored_full_runs_at_30_minutes_count(self):
        self.run_of("c0-baseline", "quick", quick=True)
        self.run_of("c0-baseline", "only", scenarios=["teach"], only=["teach"])
        self.run_of("c0-baseline", "m10", minutes=10)
        self.assertAt("2 The baseline: 3 scored full runs of c0-baseline (none yet)")

    def test_preferences(self):
        self.baseline()
        name = "3 Your preferences: your own tutor/PREFERENCES.md (it is still the one the template ships)"
        self.assertAt(name, "Write how you like to learn in tutor/PREFERENCES.md, in your own words, under its five headings.", "guide/04-preferences.html")
        path = self.root / "tutor" / "PREFERENCES.md"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        self.assertAt(name)  # line endings do not count
        self.preferences()
        self.assertEqual(self.where().done, ["1 Set up", "2 The baseline", "3 Your preferences"])


class AlsoTests(NextTestCase):
    def test_the_baseline_run_left_behind_shows_under_also(self):
        """The baseline's last run left behind, while step 1 goes on."""
        self.baseline(full=2)
        self.preferences()
        write(self.root / reviews.step_file("c1-skills"), step_md("c1-skills", round_md(1), round_md(2, changed=False)))
        self.assertEqual(self.where().text().split("\n", 1)[1], (
            "\n"
            "Done:  1 Set up, 2 The baseline, 3 Your preferences\n"
            "Now:   4 Step 1, c1-skills: quick rounds (1 of at least 2 complete)\n"
            "Next:  In the Builder window, say: Act on Round 2 of reviews/c1-skills.md.\n"
            "Read:  guide/08-step1-skills.html#rounds\n"
            "Also:  the baseline's runs: 2 of 3 scored full runs (start the last one in a plain terminal)\n"
        ))  # fmt: skip

    def test_long_runs_hold_their_stage_until_you_move_on(self):
        self.baseline(full=0)
        self.assertAt("2 The baseline: 3 scored full runs of c0-baseline (none yet)")
        self.preferences()
        r = self.assertAt("4 Step 1, c1-skills: quick rounds (0 of at least 2 complete)")
        self.assertEqual(r.also, ["the baseline's runs: 0 of 3 scored full runs (start them in a plain terminal)"])
        self.assertEqual(r.done, ["1 Set up", "2 The baseline", "3 Your preferences"])

    def test_other_items_always_hold_their_stage(self):
        """Test topics written early, as the pace suggests, move nothing past a step's rounds."""
        self.baseline()
        self.preferences()
        self.topics()
        r = self.assertAt("4 Step 1, c1-skills: quick rounds (0 of at least 2 complete)")
        self.assertEqual(r.done, ["1 Set up", "2 The baseline", "3 Your preferences", "8 Test topics"], "a later stage already complete is listed too")
        self.assertEqual(r.also, [])

    def test_at_most_two_runs_left_behind(self):
        self.baseline(full=2)
        self.preferences()
        self.step("c1-skills")
        self.step("c2-review", REVIEWERS, "new subagent")
        self.step("c3-split", SPLIT, "new subagent")
        self.topics()
        self.final(runs=1)
        util.remove_tree(util.runs_dir("final-minus-split", self.root) / "final-minus-split-r1")
        self.compares()  # of the runs there were: one pair of runs each
        entries = [e for e in self.entries if not e.startswith("### teach\n")] + [component_md("teach", kept="TODO")]  # Kept in final: only stage 11 reads it
        write(self.root / reviews.COMPONENTS_PATH, components_md(*entries))
        r = self.assertAt("11 The write-up: reviews/components.md complete, with the minimum of components built", "Finish reviews/components.md: teach: Kept in final is still TODO.")
        self.assertEqual(r.also, [
            "the baseline's runs: 2 of 3 scored full runs (start the last one in a plain terminal)",
            "the runs of final: 1 of 3 scored full runs (start the last two in a plain terminal)",
        ], "the ablation's run is left behind too, and Also shows two")  # fmt: skip
        self.assertEqual(r.done, ["1 Set up", "2 The baseline", "3 Your preferences", "4 Step 1, c1-skills", "5 Step 2, c2-review", "7 Step 3, c3-split", "8 Test topics", "9 final", "10 The blind comparison"])

    def test_what_needs_a_run_left_behind_goes_back_to_it(self):
        """The blind comparison pairs only the runs there are, so it waits for all of them."""
        self.build(9)
        util.remove_tree(util.runs_dir("final", self.root) / "final-r3")
        r = self.assertAt(
            "9 final: 3 scored full runs of final (2 so far)",
            START.format(what="the last full run", cmd="uv run p3 bench --config final"),
            "guide/12-final.html#runs",
        )
        self.assertEqual(r.also, [], "everything after it is done or waits for a run")
        self.assertEqual(r.done, ["1 Set up", "2 The baseline", "3 Your preferences", "4 Step 1, c1-skills", "5 Step 2, c2-review", "7 Step 3, c3-split", "8 Test topics"])


class RoundTests(NextTestCase):
    def setUp(self):
        super().setUp()
        self.baseline()
        self.preferences()

    def rounds(self, *rounds: str, step: str = "c1-skills") -> None:
        write(self.root / reviews.step_file(step), step_md(step, *rounds))

    def skills(self, *names: str) -> None:
        for name in names:
            write(self.root / "tutor" / ".claude" / "skills" / name / "SKILL.md", f"---\nname: {name}\n---\n")

    def test_the_round_advice(self):
        page = "guide/08-step1-skills.html#rounds"
        now = "4 Step 1, c1-skills: quick rounds ({})"
        self.assertAt(now.format("0 of at least 2 complete"), LIVE_TRY.format(k=1, step="c1-skills"), page)
        self.rounds(round_md(1, changed=False), round_md(2, thoughts=False, changed=False))
        self.assertAt(now.format("0 of at least 2 complete"), "In the Builder window, say: Act on Round 1 of reviews/c1-skills.md.", page)
        self.rounds(round_md(1).replace("- Files: tutor/.claude/skills/quiz/SKILL.md", "- Files: TODO"), round_md(2, thoughts=False, changed=False))
        self.assertAt(now.format("0 of at least 2 complete"), "Finish Round 1 in reviews/c1-skills.md: Files is still TODO.")
        self.rounds(round_md(1, thoughts=False), round_md(2, thoughts=False, changed=False))
        self.assertAt(now.format("0 of at least 2 complete"), "Finish Round 1 in reviews/c1-skills.md: My thoughts is still TODO.")
        self.rounds(round_md(1))
        self.assertAt(now.format("1 of at least 2 complete"), "Add Round 2 to reviews/c1-skills.md by copying the last round with its marker lines.")
        self.rounds(round_md(1), round_md(2))
        self.assertAt(
            "4 Step 1, c1-skills: quick rounds (2 complete; no tutor skill in tutor/ yet)",
            "Add a round for the tutor skill: copy the last round of reviews/c1-skills.md with its marker lines, as Round 3.",
        )
        self.skills("tutor", "quiz")
        self.rounds(round_md(1), round_md(2), round_md(3))
        self.assertAt("4 Step 1, c1-skills: quick rounds (3 complete; no grade skill in tutor/ yet)")
        self.skills("grade")
        self.assertAt(
            "4 Step 1, c1-skills: snapshot c1-skills (not made yet)",
            "When the four skills are in and you are happy with the tutor, snapshot it: uv run p3 snapshot c1-skills (or add another round first).",
            "guide/08-step1-skills.html#snapshot",
        )
        self.rounds(round_md(1), round_md(2), round_md(3), round_md(4, thoughts=False, changed=False))
        self.assertAt(now.format("3 complete"), LIVE_TRY.format(k=4, step="c1-skills"), page)

    def test_an_untouched_optional_round_is_left_out(self):
        self.skills(*check.SKILLS)
        self.rounds(round_md(1), round_md(2), round_md(3, thoughts=False, changed=False).replace("### Round 3", "### Round 3 (optional)"))
        self.assertAt("4 Step 1, c1-skills: snapshot c1-skills (not made yet)")

    def test_a_review_file_that_cannot_be_read(self):
        rel = reviews.step_file("c1-skills")
        write(self.root / rel, step_md("c1-skills", round_md(1)).replace("## Quick rounds", "## Rounds"))
        self.assertAt(
            "4 Step 1, c1-skills: quick rounds (0 of at least 2 complete)",
            "Fix reviews/c1-skills.md: ## Quick rounds is missing (the template's reviews/c1-skills.md has it; copy it back).",
        )
        (self.root / rel).write_bytes(step_md("c1-skills", round_md(1)).encode("utf-16"))
        self.assertAt(
            "4 Step 1, c1-skills: quick rounds (reviews/c1-skills.md is not UTF-8)",
            f"reviews/c1-skills.md: it is saved as UTF-16 (as Windows PowerShell's > and Out-File write files), not UTF-8, so p3 cannot read its headings; {util.NON_UTF8_HINT}.",
        )
        (self.root / rel).unlink()
        self.assertAt("4 Step 1, c1-skills: quick rounds (reviews/c1-skills.md is missing)", "Copy reviews/c1-skills.md back from the template; your reviews go in it.")


class StepTests(NextTestCase):
    def setUp(self):
        super().setUp()
        self.baseline()
        self.preferences()

    def test_step_1_item_by_item(self):
        page = "guide/08-step1-skills.html"
        rounds = step_md("c1-skills", round_md(1), round_md(2))
        write(self.root / reviews.step_file("c1-skills"), rounds)
        add_config(self.root, "c1-skills", skills=("teach", "tutor", "quiz"))
        self.assertAt("4 Step 1, c1-skills: quick rounds (2 complete; no grade skill in tutor/ yet)")
        write(self.root / "tutor" / ".claude" / "skills" / "grade" / "SKILL.md", "---\nname: grade\n---\n")
        self.assertAt(
            "4 Step 1, c1-skills: snapshot c1-skills (no grade skill in it)",
            "configs/c1-skills/ has no grade skill; put it in tutor/ and snapshot again: uv run p3 snapshot c1-skills --force.",
            f"{page}#snapshot",
        )
        early = self.run_of("c1-skills", "too-early")
        self.assertAt(
            "4 Step 1, c1-skills: snapshot c1-skills (no grade skill in it)",
            "configs/c1-skills/ has no grade skill; put it in tutor/ and snapshot again: uv run p3 snapshot c1-skills --force "
            "(its 1 run then no longer matches it, so delete it and run the new snapshot again).",
        )  # fmt: skip
        util.remove_tree(early)
        add_config(self.root, "c1-skills", skills=check.SKILLS)
        builder = (
            "In the Builder window, say: Add an entry to reviews/components.md for each component of configs/c1-skills/ that has none "
            "(grade, quiz, teach and tutor), with Kind, Step added, and With and without."
        )  # fmt: skip
        r = self.assertAt(
            "4 Step 1, c1-skills: 1 scored full run of c1-skills (none yet)",
            START.format(what="the full run", cmd="uv run p3 bench --config c1-skills"),
            f"{page}#full-run",
        )
        self.assertEqual(r.also, [f"While it runs: {builder} See {page}#inventory."], "the major review and EVAL.md wait for the run")
        self.run_of("c1-skills", "c1-skills-r1")
        self.assertAt(
            "4 Step 1, c1-skills: the major review (not written yet)",
            "Write the major review of bench/runs/c1-skills/c1-skills-r1 in reviews/c1-skills.md, under ## Major review: its Run line, your live tries of the tutor, then each criterion rated from 1 to 5 with feedback.",
            f"{page}#major-review",
        )
        ratings = {("Lesson", "Pedagogy"): "TODO", ("Tutor", "Guardrails"): "4.5"}
        write(self.root / reviews.step_file("c1-skills"), step_md("c1-skills", round_md(1), round_md(2), major="bench/runs/c1-skills/c1-skills-r1", ratings=ratings))
        self.assertAt(
            "4 Step 1, c1-skills: the major review (2 things left)",
            "Finish the major review in reviews/c1-skills.md: Lesson > Pedagogy: Rating is still TODO; write a whole number from 1 to 5.",
        )
        write(self.root / reviews.step_file("c1-skills"), step_md("c1-skills", round_md(1), round_md(2), major="bench/runs/c1-skills/c1-skills-r1"))
        self.assertAt(
            "4 Step 1, c1-skills: section 2 of EVAL.md (2 TODO markers left)",
            "Write section 2 of EVAL.md in your own words: 2 TODO markers left (lines 19, 23).",
            f"{page}#eval",
        )
        write(self.root / "EVAL.md", eval_md(done={2}))
        self.assertAt("4 Step 1, c1-skills: the inventory entries (0 of 4 components of configs/c1-skills/ with Purpose and Review written)", builder, f"{page}#inventory")
        teach = component_md("teach", todo=True).replace("- Kind: TODO", "- Kind: skill").replace("- Purpose: TODO", "- Purpose: It writes the lesson.")
        write(self.root / reviews.COMPONENTS_PATH, components_md(teach, *(component_md(s) for s in ("tutor", "quiz", "grade"))))
        self.assertAt(
            "4 Step 1, c1-skills: the inventory entries (3 of 4 components of configs/c1-skills/ with Purpose and Review written)",
            "Write Purpose and Review for teach in reviews/components.md; they are yours to write, and reviews/README.md says what each holds.",
        )
        write(self.root / reviews.COMPONENTS_PATH, components_md(*(component_md(s, kept="TODO") for s in check.SKILLS)))
        r = self.assertAt("5 Step 2, c2-review: quick rounds (0 of at least 2 complete)", LIVE_TRY.format(k=1, step="c2-review"), "guide/09-step2-review-loops.html#rounds")
        self.assertEqual(r.done, ["1 Set up", "2 The baseline", "3 Your preferences", "4 Step 1, c1-skills"], "Kept in final waits for final")

    def test_eval_md_sections_are_found_by_their_headings(self):
        self.step("c1-skills")
        write(self.root / "EVAL.md", eval_md(done={2}).replace("## 2. Step 1:", "## Two. Step one:"))
        self.assertAt(
            "4 Step 1, c1-skills: section 2 of EVAL.md (its heading is not there)",
            "Put back the heading of section 2 of EVAL.md, which starts with ## 2. Step 1, as the template has it; p3 next finds the section by it.",
        )
        write(self.root / "EVAL.md", eval_md(done="all").replace("## 2. Step 1:", "## Two. Step one:"))
        self.assertTrue(self.where().now.startswith("5 Step 2, c2-review"), "with no TODO anywhere, the section is written wherever it is")
        (self.root / "EVAL.md").unlink()
        self.assertAt("4 Step 1, c1-skills: section 2 of EVAL.md (EVAL.md is missing)", "Copy EVAL.md back from the template; your write-up goes in it.")

    def test_steps_2_and_3(self):
        self.step("c1-skills")
        write(self.root / reviews.step_file("c2-review"), step_md("c2-review", round_md(1, kind="new subagent"), round_md(2, kind="new subagent")))
        self.assertAt(
            "5 Step 2, c2-review: snapshot c2-review (not made yet)",
            "When teach, quiz and grade each have their review loop and you are happy with the tutor, snapshot it: uv run p3 snapshot c2-review (or add another round first).",
            "guide/09-step2-review-loops.html#snapshot",
        )  # step 2 asks for no skill: subagents come in it
        self.step("c2-review", REVIEWERS, "new subagent")
        r = self.assertAt("7 Step 3, c3-split: quick rounds (0 of at least 2 complete)", LIVE_TRY.format(k=1, step="c3-split"), "guide/10-step3-split.html#rounds")
        self.assertEqual(r.done, ["1 Set up", "2 The baseline", "3 Your preferences", "4 Step 1, c1-skills", "5 Step 2, c2-review"], "498E has no length study")
        add_agents(self.root, *SPLIT)
        add_config(self.root, "c3-split", skills=check.SKILLS)
        self.run_of("c3-split", "c3-split-r1")
        write(self.root / reviews.step_file("c3-split"), step_md("c3-split", round_md(1, kind="new subagent"), round_md(2, kind="new subagent"), major="bench/runs/c3-split/c3-split-r1"))
        write(self.root / "EVAL.md", eval_md(done={2, 3, 4}))
        self.assertAt(
            "7 Step 3, c3-split: the inventory entries (4 of 6 components of configs/c3-split/ with Purpose and Review written)",
            "In the Builder window, say: Add an entry to reviews/components.md for each component of configs/c3-split/ that has none (figure-designer and lesson-planner), with Kind, Step added, and With and without.",
            "guide/10-step3-split.html#inventory",
        )


class LengthStudyTests(NextTestCase):
    def setUp(self):
        super().setUp()
        self.build(5, study=True)

    def test_the_plan_then_the_runs(self):
        page = "guide/16-stretch-and-598e.html"
        name = "6 The length study, part 1: PREREG.md, sections 1 to 4 written and committed"
        self.assertAt(f"{name} (PREREG.md is missing)", read=f"{page}#prereg")
        write(self.root / "PREREG.md", PREREG.format(h="TODO: your hypothesis.", o="TODO: the outcome."))
        self.assertAt(f"{name} (1 TODO marker left)", "Write sections 1 to 4 of PREREG.md, your plan, before any length-study run: 1 TODO marker left (line 5).", f"{page}#prereg")
        write(self.root / "PREREG.md", PREREG.format(h="The single agent loses more at 60 minutes.", o="TODO: the outcome."))
        self.assertAt(f"{name} (not committed yet)", "Commit and push PREREG.md before the first length-study run.")
        self.prereg()
        runs = "6 The length study, part 1: 3 teach-only runs of c1-skills at each of 10, 30 and 60 minutes ({})"
        r = self.assertAt(
            runs.format("0 at 10, 0 at 30, 0 at 60"),
            START.format(what="the 10-minute runs", cmd="uv run p3 bench --config c1-skills --only teach --minutes 10 --repeats 3"),
            f"{page}#length-runs",
        )
        self.assertEqual(r.also, [f"While it runs: {LIVE_TRY.format(k=1, step='c3-split')} See guide/10-step3-split.html#rounds."])
        for k in range(3):
            self.run_of("c1-skills", f"m10-r{k}", minutes=10, scenarios=["teach"], only=["teach"])
        self.run_of("c1-skills", "m30-r0", minutes=30, scenarios=["teach"], only=["teach"])
        self.assertAt(
            runs.format("3 at 10, 1 at 30, 0 at 60"),
            START.format(what="the last two 30-minute runs", cmd="uv run p3 bench --config c1-skills --only teach --minutes 30 --repeats 2"),
        )
        self.run_of("c1-skills", "m30-r1", minutes=30, scenarios=["teach"], only=["teach"], scored=False)
        self.assertAt(
            runs.format("3 at 10, 1 at 30, 0 at 60"),
            "bench/runs/c1-skills/m30-r1 finished but is not scored; in a plain terminal at the repo root, score it: uv run p3 score bench/runs/c1-skills/m30-r1",
        )
        util.remove_tree(util.runs_dir("c1-skills", self.root) / "m30-r1")
        # step 3's rounds while the study's runs go on: its stage is passed, and they are left behind
        write(self.root / reviews.step_file("c3-split"), step_md("c3-split", round_md(1, kind="new subagent"), round_md(2, kind="new subagent")))
        r = self.assertAt("7 Step 3, c3-split: snapshot c3-split (not made yet)")
        self.assertEqual(r.also, ["the length study's runs of c1-skills: 3 at 10, 1 at 30, 0 at 60 minutes, of 3 each (start the rest in a plain terminal)"])
        self.assertIn("6 The length study, part 1", r.done)

    def test_a_plan_committed_after_the_runs(self):
        for k in range(3):
            make_run(self.root, "c1-skills", f"early-r{k}", "2020-01-01T00:00:00Z", minutes=10, scenarios=["teach"], only=["teach"])
        self.prereg()
        r = self.assertAt("6 The length study, part 1: PREREG.md, sections 1 to 4 written and committed (committed after a run)")
        self.assertIn("after the first length-study run started (2020-01-01T00:00:00Z); the plan must be committed before the runs", r.action)

    def test_the_stretch_on_498e(self):
        write(self.root / "p3.json", {"section": "498E", "stretch": "length-study"})
        self.assertTrue(self.where().now.startswith("6 The length study, part 1: "))
        write(self.root / "p3.json", {"section": "498E", "stretch": None})
        self.assertTrue(self.where().now.startswith("7 Step 3, c3-split: "))


class LaterStageTests(NextTestCase):
    def test_test_topics(self):
        self.build(7)
        page = "guide/11-test-topics.html"
        start = "Start a test topic with uv run p3 new-topic <id> (lowercase letters, digits and hyphens), then write its items yourself, as bench/own/README.md says."
        self.assertAt("8 Test topics: two test topics in bench/own/ (0 so far)", start, page)
        write_topic(self.root / "bench" / "own" / "cooking")
        write(self.root / "bench" / "own" / "cooking" / "workspace" / "NOTES.md", "# Notes\n\nTODO: what the learner knows.\n")
        self.assertAt("8 Test topics: two test topics in bench/own/ (1 so far)", start)
        write_topic(self.root / "bench" / "own" / "statics")
        self.assertAt("8 Test topics: each valid, with no TODO left (bench/own/cooking/ is not yet)", "Finish bench/own/cooking/: workspace/NOTES.md: 1 TODO marker to fill in.", page)
        write_topic(self.root / "bench" / "own" / "cooking")
        self.assertAt("8 Test topics: each committed, with no change since (bench/own/cooking/ is not)", "Commit and push bench/own/cooking/ before any run on it, so the runs show its items were written first.")
        write_topic(self.root / "bench" / "own" / "knots")
        self.assertAt(
            "8 Test topics: two test topics in bench/own/ (3: cooking, knots and statics)",
            "Keep exactly two test topics in bench/own/: the hand-in needs two, so delete the others (cooking, knots and statics are there now).",
        )
        util.remove_tree(self.root / "bench" / "own" / "knots")
        git(self.root, "add", "bench/own")
        git(self.root, "commit", "-q", "-m", "the test topics", when=BEFORE)
        self.assertAt(
            "9 final: the guard, a PreToolUse hook in tutor/.claude/settings.json (not there yet)",
            "In the Builder window, say: Add the guard to tutor/.claude/settings.json, a PreToolUse hook that keeps the answer keys in keys/ away from the main conversation while the grader can still read them.",
            "guide/12-final.html#guard",
        )
        meta = util.read_json(self.root / "bench" / "own" / "cooking" / "topic.json")
        self.run_of("c0-baseline", "c0-cooking", topic_id="cooking", topic_commit=util.rev_parse_head(self.root))
        write(self.root / "bench" / "own" / "cooking" / "topic.json", {**meta, "title": "Cooking, edited after its runs"})
        r = self.assertAt("8 Test topics: each committed, with no change since (bench/own/cooking/ is not)")
        self.assertIn("it has runs, so restore it from git (git restore bench/own/cooking)", r.action)

    def test_final_item_by_item(self):
        self.build(8)
        page = "guide/12-final.html"
        tutor_settings = self.root / "tutor" / ".claude" / "settings.json"
        add_agents(self.root, *REVIEWERS, *SPLIT)
        write(tutor_settings, GUARD)
        self.assertAt(
            "9 final: snapshot final (not made yet)",
            "Snapshot the tutor as final, and commit tutor/ with it, so git restore tutor/ brings it back after the ablation: uv run p3 snapshot final",
            f"{page}#snapshot",
        )
        add_config(self.root, "final", skills=check.SKILLS)
        write(tutor_settings, GUARD)
        self.assertAt("9 final: snapshot final (no PreToolUse hook in it)", "configs/final/ has no PreToolUse hook; put it in tutor/ and snapshot again: uv run p3 snapshot final --force.")
        add_config(self.root, "final", skills=check.SKILLS, hook=True)
        ablation = "Make the ablation: take one component out of tutor/, snapshot it as final-minus-<the component> (uv run p3 snapshot final-minus-<x>), then bring tutor/ back with git restore tutor/."
        r = self.assertAt("9 final: 3 scored full runs of final (none yet)", START.format(what="the three full runs", cmd="uv run p3 bench --config final --repeats 3"), f"{page}#runs")
        self.assertEqual(r.also, [f"While it runs: {ablation} See {page}#ablation."])
        for k in range(3):
            self.run_of("final", f"final-r{k + 1}")
        self.assertAt("9 final: an ablation snapshot, final-minus-<x> (none yet)", ablation, f"{page}#ablation")
        add_agents(self.root, *REVIEWERS)
        add_config(self.root, "final-minus-split", skills=check.SKILLS, hook=True)
        r = self.assertAt("9 final: 1 scored full run of final-minus-split (none yet)", START.format(what="the full run", cmd="uv run p3 bench --config final-minus-split"), f"{page}#ablation")
        self.assertEqual(r.also, [f"While it runs: {SESSION_1} See {page}#learning-sessions."])
        self.run_of("final-minus-split", "final-minus-split-r1")
        head = util.rev_parse_head(self.root)
        self.run_of("c0-baseline", "c0-cooking", topic_id="cooking", topic_commit=head)
        self.assertAt(
            "9 final: runs of c0-baseline and final on both test topics (1 of 4 so far)",
            START.format(what="the run of final on cooking", cmd="uv run p3 bench --config final --topic cooking"),
            f"{page}#test-topic-runs",
        )
        for tid, name in (("cooking", "final"), ("statics", "c0-baseline"), ("statics", "final")):
            self.run_of(name, f"{name}-{tid}", topic_id=tid, topic_commit=head)
        self.assertAt("9 final: three learning sessions (0 of 3 complete)", SESSION_1, f"{page}#learning-sessions")
        write(self.root / reviews.step_file("final"), final_md(session_md(1), session_md(2, topic="TODO")))
        self.assertAt("9 final: three learning sessions (1 of 3 complete)", "Finish Session 2 in reviews/final.md: Topic is still TODO.")
        write(self.root / reviews.step_file("final"), final_md(session_md(1)))
        self.assertAt("9 final: three learning sessions (1 of 3 complete)", "Add Session 2 to reviews/final.md by copying the last session with its Date and Topic lines.")
        write(self.root / reviews.step_file("final"), final_md(session_md(1), session_md(2, untouched=True), session_md(3)))
        self.assertAt(
            "9 final: three learning sessions (2 of 3 complete)",
            "Hold learning session 2: open a terminal in tutor/, start claude there with tutor/ as you snapshotted final, and learn something on cooking, as your other sessions were; then write it up under Session 2 in reviews/final.md.",
        )
        write(self.root / reviews.step_file("final"), final_md(session_md(1), session_md(2), session_md(3)))
        self.assertAt(
            "9 final: the major review, complete and committed (not written yet)",
            "Write the major review of bench/runs/final/final-r3 in reviews/final.md, under ## Major review: its Run line, your live tries of the tutor, then each criterion rated from 1 to 5 with feedback.",
            f"{page}#major-review",
        )
        write(self.root / reviews.step_file("final"), review_md("final", "bench/runs/final/final-r1", topics=TOPICS))
        self.assertAt("9 final: the major review, complete and committed (complete, not committed yet)", "Commit and push reviews/final.md, so your open review is on record before the blind comparison.")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "final", when=REVIEWED)
        self.assertAt(
            "10 The blind comparison: complete sessions of c0-baseline against final, one for each of teach, quiz, grade and tutor (0 of 4 jobs)",
            "In your own terminal at the repo root, start the blind comparison of the teach job: uv run p3 compare c0-baseline final --job teach",
            "guide/13-blind-comparison.html",
        )

    def test_learning_sessions_on_two_topics(self):
        self.build(9)
        write(self.root / reviews.step_file("final"), review_md("final", "bench/runs/final/final-r1", topics=TOPICS).replace("**Topic:** cooking", "**Topic:** statics", 1))
        self.assertAt(
            "9 final: three learning sessions (3 of 3 complete)",
            "Fix reviews/final.md: the sessions are on cooking and statics; hold all three on one of your test topics, because together they are the live tries of one major review.",
        )

    def test_the_blind_comparison(self):
        self.build(9)
        a, b = check.BLIND_COMPARE
        self.compares(jobs=("teach",))
        record = compare.new_session(a, b, "quiz", root=self.root, when=T0 + timedelta(seconds=30))
        self.assertAt(
            "10 The blind comparison: complete sessions of c0-baseline against final, one for each of teach, quiz, grade and tutor (1 of 4 jobs: teach)",
            f"Finish the blind comparison of the quiz job you started, in your own terminal at the repo root: uv run p3 compare --resume {record['session']}",
        )
        s = compare.Session(record["session"], self.root)
        for pair in s.pairs:
            s.record(pair["pair_id"], "left", "It fit me better.", False)
        self.compares(jobs=("grade", "tutor"))
        self.assertAt("11 The write-up: EVAL.md with no TODO left", "Write the rest of EVAL.md: 2 TODO markers left (lines 49, 53).", "guide/14-write-up.html")

    def test_the_length_study_comparisons(self):
        self.build(10, study=True)
        r = self.assertAt(
            "9 final: 3 teach-only runs of final at each of 10, 30 and 60 minutes (0 at 10, 0 at 30, 0 at 60)",
            START.format(what="the 10-minute runs", cmd="uv run p3 bench --config final --only teach --minutes 10 --repeats 3"),
            "guide/16-stretch-and-598e.html#length-runs",
        )
        self.assertEqual(r.also, [], "everything after it is done or waits for a run")
        self.study(name="final")
        a, b = check.STUDY_CONFIGS
        now = "10 The blind comparison: the length study's teach-only sessions of c1-skills against final at 10, 30 and 60 minutes ({} of 3)"
        self.assertAt(now.format(0), "In your own terminal at the repo root, start the teach-only comparison at 10 minutes: uv run p3 compare c1-skills final --job teach --teach-only --minutes 10")
        sids = {}
        for i, m in enumerate(check.STUDY_MINUTES):
            record = compare.new_session(a, b, "teach", minutes=m, teach_only=True, root=self.root, when=T0 + timedelta(minutes=5, seconds=i))
            s = compare.Session(record["session"], self.root)
            for pair in s.pairs[:-1] if m == 30 else s.pairs:
                s.record(pair["pair_id"], "left", "Shorter and clearer.", True)
            sids[m] = record["session"]
        self.assertAt(now.format(2), f"Finish the teach-only comparison at 30 minutes you started, in your own terminal at the repo root: uv run p3 compare --resume {sids[30]}")


class HandInTests(NextTestCase):
    def test_the_write_up_then_the_done_state(self):
        self.build(10)
        page = "guide/14-write-up.html"
        write(self.root / reviews.step_file("final"), review_md("final", "bench/runs/final/final-r1", topics=("cooking",)))
        self.assertAt(
            "11 The write-up: your open review of each test topic in reviews/final.md",
            "Finish ## Test topics in reviews/final.md: statics: missing; add ### statics, comparing c0-baseline and final on it.",
            page,
        )
        write(self.root / reviews.step_file("final"), review_md("final", "bench/runs/final/final-r1", topics=TOPICS))
        tried = component_md("summarizer", "subagent", "c2-review", "TODO")  # one tried in a round and taken out: only stage 11 reads it
        write(self.root / reviews.COMPONENTS_PATH, components_md(*self.entries, tried))
        self.assertAt("11 The write-up: reviews/components.md complete, with the minimum of components built", "Finish reviews/components.md: summarizer: Kept in final is still TODO.", page)
        write(self.root / reviews.COMPONENTS_PATH, components_md(*self.entries))
        self.assertAt("11 The write-up: EVAL.md with no TODO left", "Write the rest of EVAL.md: 2 TODO markers left (lines 49, 53).", page)
        self.write_up()
        r = self.assertAt(
            "12 Hand in: everything p3 check --final checks is done",
            "What is left is outside the repo: record your 5 to 10 minute video, commit and push your last changes, then post your repo's URL and the video in the Project 3 discussion on Canvas.",
            "guide/15-hand-in.html",
        )
        self.assertEqual(r.done, [
            "1 Set up", "2 The baseline", "3 Your preferences", "4 Step 1, c1-skills", "5 Step 2, c2-review", "7 Step 3, c3-split",
            "8 Test topics", "9 final", "10 The blind comparison", "11 The write-up",
        ])  # fmt: skip
        self.assertEqual(r.also, [])
        self.assertEqual(check.run_checks(self.root, final=True).exit_code(), 0)
        code, out, _err = self.p3("next")
        self.assertEqual(code, 0)
        self.assertIn("\nNow:   12 Hand in: everything p3 check --final checks is done\n", out)

    def test_what_only_p3_check_final_still_fails(self):
        self.build(11)
        write(self.root / "p3.json", {"section": "598e", "stretch": None})
        self.assertAt("12 Hand in: p3 check --final passes (1 FAIL line left)", "p3.json: section is '598e'; set it to \"498E\" or \"598E\"", "guide/15-hand-in.html")

    def test_the_done_state_of_598e(self):
        self.build(11, study=True)
        self.study(name="final")
        a, b = check.STUDY_CONFIGS
        for i, m in enumerate(check.STUDY_MINUTES):
            record = compare.new_session(a, b, "teach", minutes=m, teach_only=True, root=self.root, when=T0 + timedelta(minutes=5, seconds=i))
            s = compare.Session(record["session"], self.root)
            for pair in s.pairs:
                s.record(pair["pair_id"], "left", "Shorter and clearer.", True)
        r = self.assertAt("12 Hand in: everything p3 check --final checks is done")
        self.assertEqual(len(r.done), 11, "1 to 11 with the length study")
        self.assertIn("6 The length study, part 1", r.done)


class MapTests(unittest.TestCase):
    """current() and position() on made-up stages."""

    DONE, TODO, LONG = (True, False), (False, False), (False, True)

    def stage(self, number: int, *items) -> p3next.Stage:
        return p3next.Stage(number, f"Stage {number}", [i if isinstance(i, p3next.Item) else p3next.Item(f"item {k}", i[0], long=i[1]) for k, i in enumerate(items)])

    def test_the_current_stage(self):
        done, todo, long = self.DONE, self.TODO, self.LONG
        self.assertEqual(p3next.current([self.stage(1, done), self.stage(2, todo)]), 1)
        self.assertEqual(p3next.current([self.stage(1, done, long), self.stage(2, todo)]), 0, "nothing later is done yet")
        self.assertEqual(p3next.current([self.stage(1, done, long), self.stage(2, todo, done)]), 1, "an item of a later stage is done")
        self.assertEqual(p3next.current([self.stage(1, long, todo), self.stage(2, done)]), 0, "a stage with more than long runs left holds")
        self.assertIsNone(p3next.current([self.stage(1, done, long), self.stage(2, done)]))
        self.assertIsNone(p3next.current([self.stage(1, done), self.stage(2, done)]))

    def test_an_item_that_needs_a_run_left_behind(self):
        runs = p3next.Item("runs", False, long=True, key="runs:x")
        other = p3next.Item("other runs", False, long=True, key="runs:y")
        waits = p3next.Item("compare", False, waits=True, needs=("runs:x",))
        found = [self.stage(1, self.DONE, other, runs), self.stage(2, waits, self.DONE)]
        self.assertEqual(p3next.current(found), 1)
        n, item = p3next.position(found)
        self.assertEqual(n, 0)
        self.assertIs(item, other, "the first item not done of the stage it goes back to")
        runs.done = other.done = True
        self.assertEqual(p3next.position(found), (1, waits))
        waits.done = True
        self.assertIsNone(p3next.position(found))
        runs.done = False
        self.assertEqual(p3next.position(found), (0, runs), "a run left behind once everything else is done")


if __name__ == "__main__":
    unittest.main()
