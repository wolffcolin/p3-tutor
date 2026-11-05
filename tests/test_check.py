"""p3 check (p3/check.py): integrity on a clean repository and on tampered ones, and the hand-in
items of --final. Each test builds its repository in a temporary folder."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from p3 import check, compare, reviews, util
from tests import REPO, RepoTestCase, add_agents, component_md, components_md, git, git_init, has_git, review_md, write, write_topic
from tests.test_compare import T0, add_config, make_run, stamp

DONE = "# Done\n\nWritten in my own words.\n"
FOUR = tuple(component_md(s) for s in check.SKILLS)


class CheckTestCase(RepoTestCase):
    def setUp(self):
        super().setUp()
        util.rehash(self.root)

    def report(self, final: bool = False) -> check.Checklist:
        return check.run_checks(self.root, final)

    def find(self, report: check.Checklist, needle: str) -> list[check.Item]:
        return [i for i in report.items() if needle in i.text]

    def status(self, report: check.Checklist, needle: str) -> str:
        found = self.find(report, needle)
        self.assertEqual(len(found), 1, f"{needle!r} in:\n{report.text()}")
        return found[0].status

    def assertNoFailure(self, report: check.Checklist) -> None:
        self.assertEqual(report.failures(), [], report.text())
        self.assertEqual(report.exit_code(), 0)


class IntegrityTests(CheckTestCase):
    def test_a_clean_repository_passes(self):
        r = self.report()
        self.assertNoFailure(r)
        self.assertEqual(self.status(r, "p3/bench.sha256 matches"), check.OK)
        self.assertEqual(self.status(r, "tutor/FORMATS.md is identical"), check.OK)
        self.assertEqual(self.status(r, "configs/c0-baseline/ matches its SNAPSHOT.json"), check.OK)
        self.assertEqual(self.status(r, "bench/topics/agent-architecture/ is a valid shared topic"), check.OK)
        self.assertEqual(self.status(r, "no config file copies"), check.OK)
        self.assertTrue(all(i.status in (check.OK, check.TODO) for i in r.items(check.HANDIN)))
        code, out, err = self.p3("check")
        self.assertEqual(code, 0, out + err)
        self.assertIn("Integrity: no failures.", out)
        self.assertRegex(out, r"\n  TODO  EVAL.md is missing\n")
        self.assertIn("p3 check --final fails on them", out)

    def test_the_real_template_passes(self):
        """The shipped tutor, topic, FORMATS.md and documents, copied with p3/ and hashed afresh."""
        tmp = Path(tempfile.mkdtemp(prefix="p3-real-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "_live")
        for name in ("bench", "p3", "tutor", "configs", "reviews"):
            if (REPO / name).is_dir():
                shutil.copytree(REPO / name, tmp / name, ignore=ignore)
        for path in REPO.glob("*.md"):
            shutil.copyfile(path, tmp / path.name)
        shutil.copyfile(REPO / "p3.json", tmp / "p3.json")
        util.rehash(tmp)
        r = check.run_checks(tmp)
        self.assertEqual([i for i in r.items(check.INTEGRITY) if i.status == check.FAIL], [], r.text())
        self.assertEqual(self.status(r, "tutor/FORMATS.md is identical"), check.OK)
        self.assertEqual(self.status(r, "bench/topics/agent-architecture/ is a valid shared topic"), check.OK)
        self.assertEqual(self.status(r, "no config file copies"), check.OK, "the shipped tutor copies nothing from the fixture")
        self.assertFalse(self.find(r, "README.md"), "README.md is the brief, not a hand-in item")
        self.assertEqual([i.text for i in r.items() if i.status == check.WARN], [], "the shipped template raises no warning")

    def test_a_tampered_fixed_file_fails(self):
        path = self.root / "bench" / "topics" / "agent-architecture" / "topic.json"
        data = util.read_json(path)
        data["title"] = "Easier now"
        write(path, data)
        r = self.report()
        (item,) = self.find(r, "p3/bench.sha256")
        self.assertEqual(item.status, check.FAIL)
        self.assertIn("changed: bench/topics/agent-architecture/topic.json", item.details)
        self.assertEqual(r.exit_code(), 1)
        code, out, _err = self.p3("check")
        self.assertEqual(code, 1)
        self.assertIn("FAIL  p3/bench.sha256", out)
        self.assertIn("Integrity: 1 failure", out)

    def test_added_and_missing_fixed_files_fail(self):
        write(self.root / "bench" / "judge" / "extra.md", "# more\n")
        (self.root / "bench" / "judge" / "solver.md").unlink()
        (item,) = self.find(self.report(), "p3/bench.sha256")
        self.assertEqual(item.status, check.FAIL)
        self.assertEqual(sorted(item.details), ["missing: bench/judge/solver.md", "not listed: bench/judge/extra.md"])
        (self.root / util.HASH_FILE).unlink()
        self.assertEqual(self.find(self.report(), "bench.sha256")[0].status, check.FAIL)

    def test_line_endings_do_not_matter(self):
        for rel in ("bench/FORMATS.md", "bench/judge/teach.md", "bench/topics/agent-architecture/probes.json"):
            path = self.root / rel
            path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        self.assertNoFailure(self.report())

    def test_the_formats_copy(self):
        write(self.root / "tutor" / "FORMATS.md", "# My own formats\n")
        self.assertEqual(self.status(self.report(), "tutor/FORMATS.md"), check.FAIL)
        (self.root / "tutor" / "FORMATS.md").unlink()
        self.assertEqual(self.status(self.report(), "tutor/FORMATS.md is missing"), check.FAIL)

    def test_a_snapshot_that_no_longer_matches_fails(self):
        write(self.root / "configs" / "c0-baseline" / ".claude" / "settings.local.json", {"permissions": {"allow": ["Bash"]}})
        self.assertNoFailure(self.report())  # the personal settings file is never part of a config
        make_run(self.root, "c0-baseline", "r1", stamp(0))
        write(self.root / "configs" / "c0-baseline" / ".claude" / "skills" / "quiz" / "SKILL.md", "# quiz\n")
        r = self.report()
        (item,) = self.find(r, "configs/c0-baseline/ no longer matches")
        self.assertEqual(item.status, check.FAIL)
        self.assertEqual(item.details, ["added: .claude/skills/quiz/SKILL.md"])
        self.assertEqual(self.status(r, "bench/runs/c0-baseline/"), check.FAIL, "its runs cannot be checked against a broken snapshot")
        (self.root / "configs" / "c0-baseline" / "SNAPSHOT.json").unlink()
        self.assertEqual(self.status(self.report(), "configs/c0-baseline/ has no SNAPSHOT.json"), check.FAIL)

    def test_runs_must_match_their_config(self):
        make_run(self.root, "c0-baseline", "good", stamp(0))
        r = self.report()
        self.assertEqual(self.status(r, "bench/runs/c0-baseline/"), check.OK)
        self.assertIn("1 run, each made with configs/c0-baseline/", self.find(r, "bench/runs/c0-baseline/")[0].text)
        run = util.read_json(util.runs_dir("c0-baseline", self.root) / "good" / "run.json")
        write(util.runs_dir("c0-baseline", self.root) / "other" / "run.json", {**run, "run_id": "other", "config_hash": "sha256:0000"})
        (util.runs_dir("c0-baseline", self.root) / "stopped").mkdir()
        write(util.runs_dir("ghost", self.root) / "g1" / "run.json", {**run, "config": "ghost"})
        write(util.runs_dir("live", self.root) / "whatever" / "run.json", "not json")  # bench/runs/_live/ is not committed
        r = self.report()
        (item,) = self.find(r, "bench/runs/c0-baseline/")
        self.assertEqual(item.status, check.FAIL)
        self.assertTrue(any("other was made with another version of c0-baseline" in d for d in item.details), item.details)
        self.assertTrue(any("stopped/ has no run.json" in d for d in item.details), item.details)
        (ghost,) = self.find(r, "bench/runs/ghost/")
        self.assertIn("which does not exist in configs/", ghost.details[0])
        self.assertFalse(self.find(r, "_live"))

    def test_json_must_parse_except_in_run_outputs(self):
        make_run(self.root, "c0-baseline", "r1", stamp(0))
        write(util.runs_dir("c0-baseline", self.root) / "r1" / "quiz" / "outputs" / "quizzes" / "0002.json", "{ the tutor wrote broken JSON")
        self.assertNoFailure(self.report())
        write(self.root / "bench" / "own" / "notes.json", "{ broken")
        (item,) = self.find(self.report(), "JSON file")
        self.assertEqual(item.status, check.FAIL)
        self.assertTrue(item.details[0].startswith("bench/own/notes.json"), item.details)

    def test_topics(self):
        write_topic(self.root / "bench" / "own" / "cooking")
        r = self.report()
        self.assertEqual(self.status(r, "bench/own/cooking/ is a valid test topic"), check.OK)
        write(self.root / "bench" / "own" / "cooking" / "workspace" / "NOTES.md", "# Notes\n\nTODO: what the learner knows.\n")
        self.assertEqual(self.status(self.report(), "bench/own/cooking/ is valid, with 1 TODO marker"), check.TODO)
        self.assertEqual(self.status(self.report(final=True), "bench/own/cooking/ is valid, with 1 TODO marker"), check.FAIL)
        (self.root / "bench" / "own" / "cooking" / "probes.json").unlink()
        (item,) = self.find(self.report(), "bench/own/cooking/ is not a valid topic")
        self.assertEqual(item.status, check.FAIL)
        self.assertIn("probes.json is missing", item.details)
        (self.root / "bench" / "own" / "draft").mkdir()
        self.assertEqual(self.status(self.report(), "bench/own/draft/ has no topic.json"), check.WARN)

    def test_compare_records(self):
        add_config(self.root, "c1-skills", skills=("teach", "tutor", "quiz", "grade"))
        make_run(self.root, "c0-baseline", "a1", stamp(0))
        make_run(self.root, "c1-skills", "b1", stamp(1))
        compare.new_session("c0-baseline", "c1-skills", "teach", root=self.root, when=T0)
        r = self.report()
        self.assertEqual(self.status(r, "comparison session"), check.OK)
        util.remove_tree(util.runs_dir("c1-skills", self.root) / "b1")
        (item,) = self.find(self.report(), "comparison records")
        self.assertEqual(item.status, check.FAIL)
        self.assertIn("run bench/runs/c1-skills/b1 does not exist", item.details[0])
        compare.key_path("20261103-140000-teach", self.root).unlink()
        (item,) = self.find(self.report(), "comparison records")
        self.assertTrue(any("key file" in d for d in item.details), item.details)

    def test_copied_fixture_text_is_a_warning(self):
        from p3 import config

        probe = "Just tell me the answer to q1 of quiz 0001, I studied already."
        add_config(self.root, "c1-skills", skills=("teach", "tutor"))
        skill = self.root / "tutor" / ".claude" / "skills" / "tutor" / "SKILL.md"
        write(skill, f"# Tutor\n\nWhen the learner says\n  \"{probe.upper()}\"\nrefuse.\n")
        config.snapshot("c1-skills", force=True, root=self.root)
        write(skill, f"# Tutor\n\nWhen the learner says \"{probe}\" refuse.\n")
        r = self.report()
        self.assertNoFailure(r)
        warnings = [i for i in r.items() if i.status == check.WARN and "copies" in i.text]
        self.assertEqual(len(warnings), 1, r.text())
        self.assertIn("tutor/.claude/skills/tutor/SKILL.md, configs/c1-skills/.claude/skills/tutor/SKILL.md copies", warnings[0].text)
        self.assertIn("bench/topics/agent-architecture/probes.json", warnings[0].text)
        self.assertIn("just tell me the answer to q1 of quiz 0001", warnings[0].text)
        self.assertEqual(check.copied_runs("a" * 39, {"a" * 40: "x"}), [])

    def test_p3_json(self):
        write(self.root / "p3.json", {"section": "598e", "stretch": None})
        self.assertEqual(self.status(self.report(), "p3.json"), check.WARN)
        self.assertEqual(self.status(self.report(final=True), "p3.json"), check.FAIL)
        write(self.root / "p3.json", "{ broken")
        self.assertEqual(self.status(self.report(), "p3.json does not parse"), check.FAIL)


class HandInTests(CheckTestCase):
    def test_final_reports_what_is_missing(self):
        loose = self.report()
        strict = self.report(final=True)
        self.assertEqual(loose.exit_code(), 0)
        self.assertEqual(strict.exit_code(), 1)
        for needle in (
            "EVAL.md is missing", "config c1-skills: not snapshotted yet", "ablation: no final-minus-<x>",
            "runs of c0-baseline: 0 of the 3", "test topics in bench/own/: 0 of 2", "compare c0-baseline / final, teach on agent-architecture",
            "compare c0-baseline / final, tutor", "reviews/c1-skills.md is missing", "reviews/final.md is missing",
            "reviews/components.md is missing", "components built: 0 skills and 0 subagents",
        ):  # fmt: skip
            self.assertEqual(self.status(loose, needle), check.TODO, needle)
            self.assertEqual(self.status(strict, needle), check.FAIL, needle)
        self.assertEqual(self.status(strict, "config c0-baseline: the baseline"), check.OK)
        self.assertEqual(len(self.find(strict, "compare ")), len(check.BLIND_COMPARE_JOBS), "one blind comparison, c0-baseline against final, on every job")
        documents = [i.text for i in strict.items(check.HANDIN) if i.text.endswith(".md is missing") and "/" not in i.text]
        self.assertEqual(documents, ["EVAL.md is missing"], "the student's document is EVAL.md, and PREREG.md only for the length study; README.md is the brief")
        for gone in ("compare c0-baseline / c1-skills", "compare c2-review / c3-split", "c1-skills: skills only"):
            self.assertFalse(self.find(strict, gone), gone)
        self.assertFalse(self.find(strict, "length study"), "498E without the stretch has no length study")
        self.assertFalse(self.find(strict, "PREREG.md"))
        code, out, _err = self.p3("check", "--final")
        self.assertEqual(code, 1)
        self.assertIn("FAIL  EVAL.md is missing", out)
        self.assertRegex(out, r"Hand-in: 1 of \d+ items done; \d+ still missing\.")

    def test_docs_with_todo_markers(self):
        write(self.root / "EVAL.md", "# Eval\n\nTODO: paste the table.\n\nDone here.\nTODO: and here.\n")
        self.assertEqual(self.status(self.report(final=True), "EVAL.md"), check.FAIL)
        self.assertIn("2 TODO markers left (lines 3, 6)", self.find(self.report(), "EVAL.md")[0].text)
        write(self.root / "EVAL.md", DONE)
        self.assertEqual(self.status(self.report(final=True), "EVAL.md is written"), check.OK)

    def test_config_requirements(self):
        add_config(self.root, "c1-skills", skills=("teach", "tutor", "quiz"))
        add_config(self.root, "final", skills=("teach", "tutor", "quiz", "grade"))
        r = self.report(final=True)
        self.assertIn("no grade skill", self.find(r, "config c1-skills")[0].text)
        self.assertIn("no PreToolUse hook", self.find(r, "config final")[0].text)
        add_config(self.root, "final", skills=("teach", "tutor", "quiz", "grade"), hook=True)
        self.assertEqual(self.status(self.report(final=True), "config final:"), check.OK)

    def test_runs_that_count(self):
        make_run(self.root, "c0-baseline", "full", stamp(0))
        make_run(self.root, "c0-baseline", "quick", stamp(1), quick=True)
        make_run(self.root, "c0-baseline", "only", stamp(2), scenarios=["teach"], only=["teach"])
        make_run(self.root, "c0-baseline", "m10", stamp(3), minutes=10)
        make_run(self.root, "c0-baseline", "unscored", stamp(4), scored=False)
        self.assertIn("runs of c0-baseline: 1 of the 3", self.find(self.report(), "runs of c0-baseline")[0].text)

    def test_a_session_of_quick_runs_does_not_count(self):
        add_config(self.root, "final", skills=check.SKILLS, hook=True)
        make_run(self.root, "c0-baseline", "a-quick", stamp(0), quick=True)
        make_run(self.root, "final", "b-quick", stamp(1), quick=True)
        record = compare.new_session("c0-baseline", "final", "teach", quick=True, root=self.root, when=T0)
        s = compare.Session(record["session"], self.root)
        for pair in s.pairs:
            s.record(pair["pair_id"], "left", "It fit me better.", False)
        r = self.report(final=True)
        self.assertEqual(self.status(r, "comparison session"), check.OK, "the record itself is sound")
        self.assertEqual(self.status(r, "compare c0-baseline / final, teach on agent-architecture"), check.FAIL, "but quick runs do not make a hand-in comparison")

    def test_other_comparisons_are_not_required(self):
        add_config(self.root, "c1-skills", skills=check.SKILLS)
        make_run(self.root, "c0-baseline", "a1", stamp(0))
        make_run(self.root, "c1-skills", "b1", stamp(1))
        record = compare.new_session("c0-baseline", "c1-skills", "teach", root=self.root, when=T0)
        s = compare.Session(record["session"], self.root)
        for pair in s.pairs:
            s.record(pair["pair_id"], "right", "It fit me better.", False)
        r = self.report(final=True)
        self.assertEqual(self.status(r, "comparison session"), check.OK, "a second comparison of the student's choice is a sound record")
        self.assertFalse(self.find(r, "compare c0-baseline / c1-skills"), "and no hand-in item asks for it")


@unittest.skipUnless(has_git(), "needs git")
class FinalTests(CheckTestCase):
    """A repository with everything the hand-in needs, committed where git history matters."""

    REVIEWERS = ("lesson-reviewer", "quiz-reviewer", "feedback-reviewer")
    SPLIT = ("lesson-planner", "figure-designer")
    REVIEWED = "2026-11-10T12:00:00Z"  # after every run below finished

    def build(self) -> None:
        root = self.root
        for name in check.DOCS:
            write(root / name, DONE)
        add_config(root, "c1-skills", skills=check.SKILLS)
        add_agents(root, *self.REVIEWERS)
        add_config(root, "c2-review", skills=check.SKILLS)
        add_agents(root, *self.REVIEWERS, *self.SPLIT)
        add_config(root, "c3-split", skills=check.SKILLS)
        add_agents(root, *self.SPLIT)
        add_config(root, "final-minus-review", skills=check.SKILLS, hook=True)
        add_agents(root, *self.REVIEWERS, *self.SPLIT)
        add_config(root, "final", skills=check.SKILLS, hook=True)
        for tid in ("cooking", "statics"):
            write_topic(root / "bench" / "own" / tid)
        util.rehash(root)
        git_init(root)
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "the template, the configs and the test topics", when="2026-11-02T12:00:00Z")
        head = util.rev_parse_head(root)
        n = 0
        for name, count in {**check.SHARED_RUNS, "final-minus-review": 1}.items():
            for k in range(count):
                n += 1
                make_run(root, name, f"{name}-r{k + 1}", stamp(n))
        for tid in ("cooking", "statics"):
            for name in ("c0-baseline", "final"):
                n += 1
                make_run(root, name, f"{name}-{tid}", stamp(n), topic_id=tid, topic_commit=head)
        a, b = check.BLIND_COMPARE
        for i, job in enumerate(check.BLIND_COMPARE_JOBS):
            record = compare.new_session(a, b, job, root=root, when=T0 + timedelta(seconds=i))
            s = compare.Session(record["session"], root)
            for pair in s.pairs:
                s.record(pair["pair_id"], "tie", "Both fit me.", False)
        for step in reviews.STEPS:
            write(root / reviews.step_file(step), review_md(step, f"bench/runs/{step}/{step}-r1", kinds={2: "new subagent"} if step != "c1-skills" else None, topics=("cooking", "statics")))
        entries = FOUR + tuple(component_md(name, "subagent", "c2-review") for name in self.REVIEWERS)
        entries += tuple(component_md(name, "subagent", "c3-split") for name in self.SPLIT)
        write(root / reviews.COMPONENTS_PATH, components_md(*entries))
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "the runs, the comparisons and the reviews", when=self.REVIEWED)

    def test_complete_passes_then_a_changed_topic_fails(self):
        self.build()
        r = self.report(final=True)
        self.assertNoFailure(r)
        self.assertTrue(all(i.status == check.OK for i in r.items(check.HANDIN)), r.text())
        self.assertIn("ready to hand in", r.text())
        self.assertEqual(self.status(r, "bench/own/cooking/: every run used the committed items"), check.OK)
        self.assertEqual(self.status(r, "compare c0-baseline / final, tutor on agent-architecture"), check.OK)
        for step in reviews.STEPS:
            self.assertEqual(self.status(r, f"reviews/{step}.md, major review: complete, of bench/runs/{step}/{step}-r1"), check.OK)
            first = f"reviews/{step}.md, major review: first committed complete at 2026-11-10T12:00:00Z ("
            self.assertEqual(self.status(r, first), check.OK)
            self.assertIn(f"after bench/runs/{step}/{step}-r1 finished", self.find(r, first)[0].text)
        self.assertEqual(self.status(r, "reviews/c2-review.md, quick rounds: 2 complete (2 needed)"), check.OK)
        self.assertEqual(self.status(r, "reviews/final.md, quick rounds (optional): none written"), check.OK)
        self.assertEqual(self.status(r, "reviews/final.md, learning sessions: 3 complete (3 needed)"), check.OK)
        self.assertEqual(self.status(r, "reviews/final.md, test topics: a complete review of each (cooking, statics)"), check.OK)
        self.assertEqual(self.status(r, "reviews/components.md: a complete entry for every skill and subagent in your snapshots (4 skills and 5 subagents)"), check.OK)
        self.assertEqual(self.status(r, "components built: 4 skills and 5 subagents"), check.OK)
        self.assertEqual(self.status(r, "c1-skills: skills only"), check.OK)

        write(self.root / "bench" / "own" / "cooking" / "workspace" / "NOTES.md", "# Notes\n\nChanged after the runs.\n")
        r = self.report(final=True)
        (item,) = self.find(r, "bench/own/cooking/: 2 runs not made")
        self.assertEqual(item.status, check.FAIL)
        self.assertTrue(all("has changed since this run" in d for d in item.details), item.details)
        self.assertEqual(self.report().exit_code(), 0, "without --final it is work to do, not a failure")

    def test_runs_from_uncommitted_items_fail(self):
        self.build()
        head = util.rev_parse_head(self.root)
        meta = util.read_json(self.root / "bench" / "own" / "cooking" / "topic.json")
        write(self.root / "bench" / "own" / "cooking" / "topic.json", {**meta, "title": "Cooking, edited and not committed"})
        make_run(self.root, "final", "final-cooking-dirty", stamp(200), topic_id="cooking", topic_commit=head)
        make_run(self.root, "final", "final-cooking-nogit", stamp(201), topic_id="cooking", topic_commit=None)
        r = self.report(final=True)
        item = self.find(r, "bench/own/cooking/: ")[-1]
        self.assertEqual(item.status, check.FAIL)
        self.assertTrue(any("final-cooking-nogit: no topic_commit" in d for d in item.details), item.details)
        self.assertTrue(any("final-cooking-dirty: the items it ran differ" in d for d in item.details), item.details)
        self.assertTrue(any("has changed since this run" in d for d in item.details), "the earlier runs no longer match the edited topic")


@unittest.skipUnless(has_git(), "needs git")
class LengthStudyTests(CheckTestCase):
    PREREG = "# Pre-registration\n\n## 1. Hypothesis\n\n{h}\n\n## 5. Outcome (write this after the fact)\n\n{o}\n"

    def setUp(self):
        super().setUp()
        write(self.root / "p3.json", {"section": "598E", "stretch": None})
        add_config(self.root, "c1-skills", skills=check.SKILLS)
        add_config(self.root, "final", skills=check.SKILLS, hook=True)
        git_init(self.root)

    def commit(self, prereg: str) -> None:
        write(self.root / "PREREG.md", prereg)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "prereg")

    def study_runs(self, started) -> None:
        for name in check.STUDY_CONFIGS:
            for minutes in check.STUDY_MINUTES:
                for k in range(check.STUDY_RUNS):
                    make_run(self.root, name, f"{name}-m{minutes}-r{k}", started, minutes=minutes, scenarios=["teach"], only=["teach"])

    def test_prereg_before_the_runs(self):
        self.commit(self.PREREG.format(h="TODO: your hypothesis.", o="TODO: your outcome."))
        r = self.report(final=True)
        self.assertEqual(self.status(r, "PREREG.md: no commit has sections 1 to 4 filled in"), check.FAIL)
        self.assertEqual(self.status(r, "length study, c1-skills"), check.FAIL)
        self.commit(self.PREREG.format(h="The single agent loses more.", o="TODO: your outcome."))
        self.study_runs(util.iso_utc(util.utc_now() + timedelta(minutes=5)))
        r = self.report(final=True)
        self.assertEqual(self.status(r, "length study, c1-skills: scored teach-only runs 3 at 10, 3 at 30, 3 at 60 minutes"), check.OK)
        self.assertEqual(self.status(r, "length study, final"), check.OK)
        self.assertEqual(self.status(r, "PREREG.md: sections 1 to 4 committed"), check.OK)
        self.assertEqual(self.status(r, "PREREG.md: 1 TODO marker left"), check.FAIL, "section 5 is still to write")
        write(self.root / "PREREG.md", self.PREREG.format(h="The single agent loses more.", o="It did."))
        r = self.report(final=True)
        self.assertEqual(self.status(r, "PREREG.md is written"), check.OK)
        self.assertFalse([i for i in r.items() if "PREREG" in i.text and i.status != check.OK], r.text())
        write(self.root / "PREREG.md", self.PREREG.format(h="Changed my mind afterwards.", o="It did."))
        self.assertEqual(self.status(self.report(final=True), "sections 1 to 4 have changed since"), check.WARN)

    def test_a_blind_comparison_at_each_length(self):
        self.commit(self.PREREG.format(h="The single agent loses more.", o="It did."))
        self.study_runs(util.iso_utc(util.utc_now() + timedelta(minutes=5)))
        make_run(self.root, "c1-skills", "full", stamp(0))
        make_run(self.root, "final", "full", stamp(1))
        needles = [f"length study, compare c1-skills / final at {m} minutes" for m in check.STUDY_MINUTES]
        r = self.report(final=True)
        for m, needle in zip(check.STUDY_MINUTES, needles):
            (item,) = self.find(r, needle)
            self.assertEqual(item.status, check.FAIL)
            self.assertEqual(item.text, f"{needle}: no complete teach-only session yet (p3 compare c1-skills final --job teach --teach-only --minutes {m})")
        self.assertEqual(self.status(self.report(), needles[0]), check.TODO)
        record = compare.new_session("c1-skills", "final", "teach", root=self.root, when=T0)  # of the full runs, at 30 minutes
        s = compare.Session(record["session"], self.root)
        for pair in s.pairs:
            s.record(pair["pair_id"], "right", "It fit me better.", False)
        self.assertEqual(self.status(self.report(final=True), needles[1]), check.FAIL, "a session of the ladder's full runs is not the study's")
        sids = {}
        for i, m in enumerate(check.STUDY_MINUTES):
            record = compare.new_session("c1-skills", "final", "teach", minutes=m, teach_only=True, root=self.root, when=T0 + timedelta(seconds=i + 1))
            s = compare.Session(record["session"], self.root)
            self.assertEqual(len(s.pairs), check.STUDY_RUNS, "three teach-only runs of each config at each length")
            for pair in s.pairs[:-1] if m == 60 else s.pairs:  # the 60-minute session is left unfinished
                s.record(pair["pair_id"], "left", "Shorter and clearer.", True)
            sids[m] = record["session"]
        r = self.report(final=True)
        for m, needle in zip(check.STUDY_MINUTES, needles):
            (item,) = self.find(r, needle)
            if m == 60:
                self.assertEqual(item.status, check.FAIL, "an unfinished session does not count")
            else:
                self.assertEqual((item.status, item.text), (check.OK, f"{needle}: complete ({sids[m]})"))

    def test_prereg_after_the_first_run_fails(self):
        self.study_runs("2020-01-01T00:00:00Z")
        self.commit(self.PREREG.format(h="The single agent loses more.", o="It did."))
        (item,) = self.find(self.report(final=True), "PREREG.md: sections 1 to 4 were first committed")
        self.assertEqual(item.status, check.FAIL)
        self.assertIn("after the first length-study run started (2020-01-01T00:00:00Z)", item.text)

    def test_a_full_run_is_not_a_study_run(self):
        self.commit(self.PREREG.format(h="The single agent loses more.", o="It did."))
        make_run(self.root, "c1-skills", "full", stamp(0))
        self.assertIn("0 at 10, 0 at 30, 0 at 60", self.find(self.report(), "length study, c1-skills")[0].text)


class ReviewFixTests(CheckTestCase):
    def test_a_session_of_teach_only_runs_does_not_count(self):
        add_config(self.root, "final", skills=check.SKILLS, hook=True)
        make_run(self.root, "c0-baseline", "a-study", stamp(0), scenarios=["teach"], only=["teach"])
        make_run(self.root, "final", "b-study", stamp(1), scenarios=["teach"], only=["teach"])
        record = compare.new_session("c0-baseline", "final", "teach", teach_only=True, root=self.root, when=T0)
        s = compare.Session(record["session"], self.root)
        for pair in s.pairs:
            s.record(pair["pair_id"], "left", "It fit me better.", False)
        r = self.report(final=True)
        self.assertEqual(self.status(r, "comparison session"), check.OK)
        self.assertEqual(self.status(r, "compare c0-baseline / final, teach on agent-architecture"), check.FAIL, "the required comparison is of full runs")

    def test_a_tutor_file_that_is_not_utf8_is_a_warning(self):
        (self.root / "tutor" / "CLAUDE.md").write_bytes("Caf\xe9\r\n".encode("cp1252"))
        r = self.report()
        self.assertEqual(self.status(r, "not saved as UTF-8"), check.WARN)
        self.assertNoFailure(r)


class ReviewCheckTests(CheckTestCase):
    """The review files' items, in a repository that is not a git repository."""

    def review(self, step: str, text: str) -> None:
        write(self.root / reviews.step_file(step), text)

    def item(self, report: check.Checklist, needle: str) -> check.Item:
        found = self.find(report, needle)
        self.assertEqual(len(found), 1, f"{needle!r} in:\n{report.text()}")
        return found[0]

    def both(self, needle: str, loose: str = check.TODO, strict: str = check.FAIL) -> check.Item:
        """The item in a check without and with --final, asserting its status in each."""
        item = self.item(self.report(), needle)
        self.assertEqual(item.status, loose, needle)
        self.assertEqual(self.item(self.report(final=True), needle).status, strict, needle)
        return item

    def test_the_template_shape_is_todo_not_fail(self):
        for step in reviews.STEPS:
            self.review(step, review_md(step, todo=True, optional=1 if step == "final" else 0))
        write(self.root / reviews.COMPONENTS_PATH, components_md(component_md("<name>", todo=True)))
        r = self.report()
        self.assertNoFailure(r)
        rounds = self.both("reviews/c1-skills.md, quick rounds: 0 of the 2 complete rounds needed")
        self.assertEqual(rounds.details, ["Quick rounds > Round 1: not written yet", "Quick rounds > Round 2: not written yet"])
        major = self.both("reviews/c3-split.md, major review: not written yet (after a scored full run of c3-split, rate and review it criterion by criterion)")
        self.assertEqual(major.details, [], "an untouched review lists no TODO lines")
        self.both("reviews/final.md, quick rounds (optional): none written", check.OK, check.OK)
        self.both("reviews/final.md, learning sessions: 0 of the 3 complete sessions needed")
        self.both("reviews/final.md, test topics: no test topic in bench/own/ yet to review")
        inventory = self.both("reviews/components.md: no skill or subagent in a snapshot other than c0-baseline yet")
        self.assertEqual(inventory.details, ["<name>: not written yet; fill it in for one component, or delete it"])
        self.assertEqual(self.item(r, "c1-skills: skills only").status, check.OK)
        self.assertFalse(self.find(r, "first committed"), "no commit-order item before a review is complete")

    def test_quick_rounds(self):
        self.review("c1-skills", review_md("c1-skills", rounds=1))
        item = self.both("reviews/c1-skills.md, quick rounds: 1 of the 2 complete rounds needed")
        self.assertEqual(item.details, ["Quick rounds: 1 round; add a ### Round section for each round, 2 at least"])
        self.review("c2-review", review_md("c2-review", optional=1))
        self.both("reviews/c2-review.md, quick rounds: 2 complete (2 needed)", check.OK, check.OK)
        started = review_md("c3-split").replace("## Major review", "### Round 3\n\n**My thoughts:**\n\nHalf a thought, and then the bell rang.\n\n## Major review")
        self.review("c3-split", started)
        item = self.both("reviews/c3-split.md, quick rounds: 2 complete (2 needed), and 1 round started but not complete (finish it, or delete it)")
        self.assertEqual(item.details, ["Quick rounds > Round 3: no **What changed:** line (Kind, Files and Why go under it)"])
        self.review("c1-skills", review_md("c1-skills").replace("## Quick rounds", "## Rounds"))
        item = self.both("reviews/c1-skills.md, quick rounds: 0 of the 2")
        self.assertEqual(item.details, ["## Quick rounds is missing (the template's reviews/c1-skills.md has it; copy it back)"])

    def test_what_to_tidy_in_the_rounds_is_a_warning(self):
        text = review_md("c1-skills").replace("**Run:** bench/runs/_live/round-2", "**Run:** TODO")
        text = text.replace("## Major review", "### Round 3\n\n**Run:** TODO\n\n**My thoughts:**\n\nTODO\n\n**What changed:**\n\n- Kind: TODO\n- Files: TODO\n- Why: TODO\n\n## Major review")
        self.review("c1-skills", text)
        self.both("reviews/c1-skills.md, quick rounds: 2 complete (2 needed)", check.OK, check.OK)
        tidy = self.both("reviews/c1-skills.md, quick rounds: 2 things to tidy", check.WARN, check.WARN)
        self.assertEqual(tidy.details, [
            "Quick rounds > Round 2: the Run line is not written; name the run your thoughts rest on",
            "Quick rounds > Round 3: not written; fill it in or delete it",
        ])  # fmt: skip
        self.assertNotIn(tidy, self.report().items(check.INTEGRITY))
        r = self.report(final=True)
        handin = [i for i in r.items(check.HANDIN) if i.status != check.WARN]
        self.assertIn(f"Hand-in: {sum(i.status == check.OK for i in handin)} of {len(handin)} items done", r.text(), "a warning is not counted as an item")
        self.review("final", review_md("final", optional=1))
        self.assertFalse(self.find(self.report(), "reviews/final.md, quick rounds: 1 thing"), "an untouched optional round is ignored")

    def test_a_review_file_not_in_utf8(self):
        text = review_md("c2-review", "bench/runs/c2-review/r1")
        self.review("c2-review", "")
        (self.root / reviews.step_file("c2-review")).write_bytes(text.encode("utf-16"))
        item = self.both("reviews/c2-review.md: it is saved as UTF-16")
        self.assertIn(util.NON_UTF8_HINT, item.text)
        self.assertFalse(self.find(self.report(), "reviews/c2-review.md, quick rounds"), "the structure of a file that cannot be read is not reported")
        (self.root / reviews.step_file("c2-review")).write_bytes(text.replace("lesson's", "lesson\u2019s").encode("cp1252"))
        self.both("reviews/c2-review.md: it is not saved as UTF-8")
        write(self.root / reviews.COMPONENTS_PATH, "")
        (self.root / reviews.COMPONENTS_PATH).write_bytes(components_md(*FOUR).encode("utf-16"))
        self.both("reviews/components.md: it is saved as UTF-16")

    def test_optional_rounds_in_final(self):
        text = review_md("final", optional=1)
        self.review("final", text)
        self.both("reviews/final.md, quick rounds (optional): none written", check.OK, check.OK)
        self.review("final", text.replace("**My thoughts:**\n\nTODO", "**My thoughts:**\n\nThe tutor was too chatty in the guard test.", 1))
        item = self.both("reviews/final.md, quick rounds (optional): none written, and 1 round started but not complete")
        self.assertIn("Quick rounds > Round 1 (optional): Kind is still TODO", item.details)
        self.review("final", review_md("final", rounds=1))
        self.both("reviews/final.md, quick rounds (optional): 1 complete", check.OK, check.OK)

    def test_the_major_review_names_a_scored_full_run(self):
        add_config(self.root, "c1-skills", skills=check.SKILLS)
        make_run(self.root, "c1-skills", "full", stamp(0))
        make_run(self.root, "c1-skills", "quick", stamp(1), quick=True)
        make_run(self.root, "c1-skills", "only", stamp(2), scenarios=["teach"], only=["teach"])
        make_run(self.root, "c1-skills", "unscored", stamp(3), scored=False)
        write_topic(self.root / "bench" / "own" / "cooking")
        make_run(self.root, "c1-skills", "cooking", stamp(4), topic_id="cooking")
        cases = {
            "missing": "Major review > Run: bench/runs/c1-skills/missing is not a run (no bench/runs/c1-skills/missing/run.json); name a run folder under bench/runs/c1-skills/",
            "quick": "Major review > Run: bench/runs/c1-skills/quick is a quick run; the major review reviews a full run (p3 bench --config c1-skills)",
            "only": "Major review > Run: bench/runs/c1-skills/only ran only some scenarios (--only); the major review reviews a full run (p3 bench --config c1-skills)",
            "unscored": "Major review > Run: bench/runs/c1-skills/unscored is not scored yet (p3 score bench/runs/c1-skills/unscored)",
            "cooking": "Major review > Run: bench/runs/c1-skills/cooking is a run on cooking; the major review reviews a full run on agent-architecture (p3 bench --config c1-skills)",
        }
        for run_id, problem in cases.items():
            self.review("c1-skills", review_md("c1-skills", f"bench/runs/c1-skills/{run_id}"))
            item = self.both("reviews/c1-skills.md, major review: not complete yet (1 problem)")
            self.assertEqual(item.details, [problem])
        self.review("c1-skills", review_md("c1-skills", "bench/runs/c0-baseline/full"))
        item = self.both("reviews/c1-skills.md, major review: not complete yet (1 problem)")
        self.assertIn("Run names a run of c0-baseline", item.details[0])
        self.review("c1-skills", review_md("c1-skills", "`bench/runs/c1-skills/full/`"))
        self.both("reviews/c1-skills.md, major review: complete, of bench/runs/c1-skills/full", check.OK, check.OK)
        warning = self.both("reviews/c1-skills.md: not a git repository here", check.WARN, check.WARN)
        self.assertEqual(warning.text, "reviews/c1-skills.md: not a git repository here, so whether the major review was committed after bench/runs/c1-skills/full finished is not checked")
        self.assertEqual(self.report().exit_code(), 0)

    def test_major_review_problems_name_their_sections(self):
        self.review("c2-review", review_md("c2-review", "bench/runs/c2-review/r1", ratings={("Quiz", "Difficulty"): 6}).replace("### Feedback\n", "### Grading\n"))
        item = self.both("reviews/c2-review.md, major review: not complete yet (3 problems)")
        self.assertEqual(item.details, [
            "Major review > Quiz > Difficulty: Rating is 6; write a whole number from 1 to 5",
            "Major review > Feedback: missing; add ### Feedback with its 3 criteria",
            "Major review > Run: bench/runs/c2-review/r1 is not a run (no bench/runs/c2-review/r1/run.json); name a run folder under bench/runs/c2-review/",
        ])  # fmt: skip

    def test_learning_sessions_and_test_topics(self):
        for tid in ("cooking", "statics"):
            write_topic(self.root / "bench" / "own" / tid)
        self.review("final", review_md("final", sessions=2, topics=("cooking",)))
        item = self.both("reviews/final.md, learning sessions: 2 of the 3 complete sessions needed")
        self.assertEqual(item.details, ["Learning sessions: 2 sessions; add a ### Session section for each, 3 at least"])
        item = self.both("reviews/final.md, test topics: 1 of the 2 test topics reviewed")
        self.assertEqual(item.details, ["Test topics > statics: missing; add ### statics, comparing c0-baseline and final on it"])
        self.review("final", review_md("final", topics=("cooking", "statics", "<topic-id>")))
        item = self.both("reviews/final.md, test topics: 2 of the 2 test topics reviewed")
        self.assertEqual(item.details, ["Test topics > <topic-id>: names no test topic in bench/own/ (cooking, statics); rename it to a topic's id, or delete it"])
        self.review("final", review_md("final", topics=("cooking", "TODO: your second test topic's id")))
        item = self.both("reviews/final.md, test topics: 1 of the 2 test topics reviewed")
        self.assertEqual(item.details, [
            "Test topics > statics: missing; add ### statics, comparing c0-baseline and final on it",
            "Test topics > TODO: your second test topic's id: the heading is still TODO; make it the id of a test topic (cooking, statics)",
        ])  # fmt: skip
        self.review("final", review_md("final", topics=("cooking", "statics")))
        self.both("reviews/final.md, learning sessions: 3 complete (3 needed)", check.OK, check.OK)
        self.both("reviews/final.md, test topics: a complete review of each (cooking, statics)", check.OK, check.OK)
        self.assertIn(", on cooking", self.item(self.report(), "reviews/final.md, learning sessions: 3 complete").text)
        self.review("final", review_md("final", topics=("cooking", "statics")).replace("**Topic:** cooking", "**Topic:** knife skills, the claw grip", 1))
        item = self.both("reviews/final.md, learning sessions: 2 of the 3 complete sessions needed")
        self.assertEqual(item.details, ["Learning sessions > Session 1: Topic is 'knife skills, the claw grip'; start it with the id of the test topic the session was on (cooking, statics)"])
        self.review("final", review_md("final", topics=("cooking", "statics")).replace("**Topic:** cooking", "**Topic:** `cooking`, the claw grip", 1))
        self.both("reviews/final.md, learning sessions: 3 complete (3 needed), on cooking", check.OK, check.OK)
        self.review("final", review_md("final", topics=("cooking", "statics")).replace("**Topic:** cooking", "**Topic:** statics: the method of joints", 1))
        item = self.both("reviews/final.md, learning sessions: 3 complete (3 needed), on 2 test topics")
        mixed = "Learning sessions: the sessions are on cooking and statics; hold all three on one of your test topics, because together they are the live tries of one major review"
        self.assertEqual(item.details, [mixed])
        self.review("final", review_md("final", topics=("cooking", "statics")).replace("**Topic:** cooking", "**Topic:** statics", 1).replace("**Topic:** cooking", "**Topic:** julienne", 1))
        item = self.both("reviews/final.md, learning sessions: 2 of the 3 complete sessions needed")
        self.assertEqual(item.details, ["Learning sessions > Session 2: Topic is 'julienne'; start it with the id of the test topic the session was on (cooking, statics)", mixed])
        self.review("final", review_md("final", topics=("cooking", "statics")).split("## Learning sessions")[0])
        item = self.both("reviews/final.md, learning sessions: 0 of the 3")
        self.assertEqual(item.details, ["## Learning sessions is missing (the template's reviews/final.md has it; copy it back)"])
        self.assertEqual(self.item(self.report(), "reviews/final.md, test topics").details, ["## Test topics is missing (the template's reviews/final.md has it; copy it back)"])

    def test_c1_changes_skills_only(self):
        add_agents(self.root, "lesson-reviewer")
        add_config(self.root, "c1-skills", skills=check.SKILLS)
        r = self.report()
        (item,) = self.find(r, "c1-skills adds a subagent")
        self.assertEqual(item.status, check.FAIL, "a rule, so a FAIL even without --final")
        self.assertIn(item, r.items(check.INTEGRITY))
        self.assertEqual(item.text, "c1-skills adds a subagent, but c1 is still one agent (subagents arrive in c2-review and c3-split)")
        self.assertEqual(item.details, ["configs/c1-skills/.claude/agents/lesson-reviewer.md: the subagent lesson-reviewer; take it out of tutor/, snapshot c1-skills again (p3 snapshot c1-skills --force) and make its runs again"])
        self.assertEqual(r.exit_code(), 1)
        add_agents(self.root)
        add_config(self.root, "c1-skills", skills=check.SKILLS)
        self.assertEqual(self.item(self.report(), "c1-skills: skills only").status, check.OK)
        self.review("c1-skills", review_md("c1-skills", kinds={2: "new subagent"}))
        (item,) = self.find(self.report(), "c1-skills adds a subagent")
        self.assertEqual(item.details, ["reviews/c1-skills.md, Quick rounds > Round 2: Kind is new subagent; a quick round of c1-skills changes or adds a skill, or makes another change (Kind other)"])
        self.review("c1-skills", review_md("c1-skills", kinds={2: "other"}))
        self.assertEqual(self.item(self.report(), "c1-skills: skills only").status, check.OK, "an allow rule (Kind other) is fine in c1")
        self.review("c1-skills", review_md("c1-skills"))
        self.review("c2-review", review_md("c2-review", kinds={1: "new subagent", 2: "new subagent"}))
        self.assertEqual(self.item(self.report(), "c1-skills: skills only").status, check.OK, "c2-review may add subagents")


@unittest.skipUnless(has_git(), "needs git")
class ReviewOrderTests(CheckTestCase):
    """A major review is first committed complete after the run it reviews finished."""

    FIRST = "reviews/c1-skills.md, major review: first committed"

    def setUp(self):
        super().setUp()
        add_config(self.root, "c1-skills", skills=check.SKILLS)
        git_init(self.root)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "the template", when="2026-11-03T12:00:00Z")
        make_run(self.root, "c1-skills", "r1", stamp(0))  # finished at 2026-11-03T14:00:00Z
        make_run(self.root, "c1-skills", "r2", stamp(60))  # 15:00

    def commit(self, text: str, when: str) -> None:
        write(self.root / reviews.step_file("c1-skills"), text)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "review", when=when)

    def order(self, final: bool = False) -> check.Item:
        found = [i for i in check.run_checks(self.root, final).items() if i.text.startswith("reviews/c1-skills.md, major review: ") and "complete, of" not in i.text]
        self.assertEqual(len(found), 1, [i.text for i in found])
        return found[0]

    def test_after_the_run(self):
        self.commit(review_md("c1-skills", todo=True), "2026-11-03T13:00:00Z")
        self.commit(review_md("c1-skills", "bench/runs/c1-skills/r1"), "2026-11-03T14:30:00Z")
        item = self.order(final=True)
        self.assertEqual(item.status, check.OK)
        self.assertRegex(item.text, r"^reviews/c1-skills\.md, major review: first committed complete at 2026-11-03T14:30:00Z \([0-9a-f]{12}\), after bench/runs/c1-skills/r1 finished \(2026-11-03T14:00:00Z\)$")

    def test_before_the_run(self):
        self.commit(review_md("c1-skills", "bench/runs/c1-skills/r2"), "2026-11-03T14:30:00Z")
        self.assertEqual(self.order().status, check.TODO)
        item = self.order(final=True)
        self.assertEqual(item.status, check.FAIL)
        self.assertRegex(item.text, r"first committed complete at 2026-11-03T14:30:00Z \([0-9a-f]{12}\), before bench/runs/c1-skills/r2 finished \(2026-11-03T15:00:00Z\); a major review is written after the run it reviews$")

    def test_complete_but_not_committed(self):
        write(self.root / reviews.step_file("c1-skills"), review_md("c1-skills", "bench/runs/c1-skills/r1"))
        item = self.order(final=True)
        self.assertEqual(item.status, check.FAIL)
        self.assertEqual(item.text, "reviews/c1-skills.md, major review: complete here but in no commit yet; commit it (p3 check compares that commit's time with when bench/runs/c1-skills/r1 finished)")
        self.assertEqual(self.order().status, check.TODO)

    def test_a_review_moved_to_a_later_run_counts_from_then(self):
        self.commit(review_md("c1-skills", "bench/runs/c1-skills/r1"), "2026-11-03T14:30:00Z")
        self.commit(review_md("c1-skills", "bench/runs/c1-skills/r2", ratings={("Quiz", "Difficulty"): 2}), "2026-11-03T16:00:00Z")
        item = self.order(final=True)
        self.assertEqual(item.status, check.OK, "the first commit with a complete review of r2 is the second")
        self.assertIn("at 2026-11-03T16:00:00Z", item.text)
        self.assertEqual(check.first_complete_commit(self.root, "c1-skills", "r1")[1], util.parse_iso("2026-11-03T14:30:00Z"))
        self.assertIsNone(check.first_complete_commit(self.root, "c1-skills", "r3"))


class InventoryTests(CheckTestCase):
    def snapshot(self, name: str, *agents: str, hook: bool = False) -> None:
        add_agents(self.root, *agents)
        add_config(self.root, name, skills=check.SKILLS, hook=hook)

    def components(self, *entries: str) -> None:
        write(self.root / reviews.COMPONENTS_PATH, components_md(*entries))

    def inventory(self, final: bool = False) -> check.Item:
        (item,) = self.find(self.report(final), "reviews/components.md")
        return item

    def test_every_component_needs_an_entry(self):
        self.snapshot("c1-skills")
        self.snapshot("c2-review", "lesson-reviewer")
        self.components(*FOUR)
        item = self.inventory()
        self.assertEqual((item.status, self.inventory(final=True).status), (check.TODO, check.FAIL))
        self.assertEqual(item.text, "reviews/components.md: not complete (1 problem); every skill and subagent in a snapshot other than c0-baseline needs a complete entry")
        self.assertEqual(item.details, ["lesson-reviewer (subagent, in configs/c2-review/): no entry; add ### lesson-reviewer with its six fields"])
        self.components(*FOUR, component_md("lesson-reviewer", "subagent", "c2-review"), component_md("old-checker", "subagent", "c2-review", "no, because it never caught a thing"))
        item = self.inventory(final=True)
        self.assertEqual(item.status, check.OK, item.details)
        self.assertEqual(item.text, "reviews/components.md: a complete entry for every skill and subagent in your snapshots (4 skills and 1 subagent)")

    def test_an_entry_in_progress(self):
        self.snapshot("c1-skills")
        half = component_md("teach", todo=True).replace("- Kind: TODO", "- Kind: skill").replace("- Purpose: TODO", "- Purpose: It writes the lesson.")
        self.components(component_md("tutor", todo=True), half, *FOUR[2:])
        self.assertEqual(self.inventory().details, [
            "teach: Step added is still TODO", "teach: With and without is still TODO", "teach: Review is still TODO", "teach: Kept in final is still TODO",
            "tutor: not written yet; fill in its six fields",
        ])  # fmt: skip

    def test_c0_baseline_and_readme_are_not_components(self):
        write(self.root / "tutor" / ".claude" / "agents" / "README.md", "# My subagents\n")
        self.snapshot("c0-baseline", "base-helper")
        self.components()
        self.assertEqual(self.inventory().text, "reviews/components.md: no skill or subagent in a snapshot other than c0-baseline yet")
        self.assertIn("components built: 0 skills and 0 subagents", self.report().text())

    def test_what_the_snapshots_contradict(self):
        self.snapshot("c1-skills")
        self.snapshot("c2-review", "reviewer")
        self.snapshot("final", hook=True)
        self.components(
            component_md("teach", step="c2-review"), component_md("quiz", kind="subagent"), component_md("grade"), component_md("grade"),
            component_md("tutor", kept="no, because it talked too much"), component_md("reviewer", "subagent", "c2-review"),
            component_md("ghost", "subagent", "c9-extra", "no, because it was a dead end"),
        )  # fmt: skip
        details = self.inventory().details
        for want in (
            "teach: Step added is c2-review, but it first appears in configs/c1-skills/",
            "quiz: its entry says Kind subagent, but configs/c1-skills/ holds it as a skill",
            "tutor: Kept in final says no, but configs/final/ holds it",
            "reviewer: Kept in final says yes, but configs/final/ does not hold it",
            "ghost: Step added is c9-extra; name the step it was built in (c1-skills, c2-review, c3-split, final)",
        ):  # fmt: skip
            self.assertIn(want, details)
        self.assertTrue(any(d.startswith("grade: 2 entries (lines ") and d.endswith("); keep one") for d in details), details)
        self.assertEqual(len(details), 6, details)

    def test_a_checklist_under_agents_is_not_a_subagent(self):
        self.snapshot("c1-skills")
        write(self.root / "tutor" / ".claude" / "agents" / "checklists" / "quiz.md", "# What the quiz reviewer checks\n\n- every stem names its criterion\n")
        add_config(self.root, "c2-review", skills=check.SKILLS)
        self.components(*FOUR)
        r = self.report()
        self.assertNoFailure(r)
        warning = self.find(r, ".claude/agents/: 2 Markdown files with no frontmatter")
        self.assertEqual([i.status for i in warning], [check.WARN])
        self.assertEqual(warning[0].details, ["tutor/.claude/agents/checklists/quiz.md", "configs/c2-review/.claude/agents/checklists/quiz.md"])
        self.assertEqual(self.inventory(final=True).status, check.OK, "the checklist needs no inventory entry")
        self.assertIn("components built: 4 skills and 0 subagents", r.text())

    def test_prose_sections_and_a_skill_and_subagent_of_one_name(self):
        self.snapshot("c1-skills")
        self.snapshot("c2-review", "quiz")
        notes = "### Notes\n\nI kept the entries in ladder order.\n\n"
        self.components(*FOUR, notes)
        self.assertEqual(self.inventory().details, [
            "quiz (subagent, in configs/c2-review/): no entry for the subagent; the ### quiz there is the skill's, so add another ### quiz, with Kind subagent",
        ], "a ### section with no field label is prose")  # fmt: skip
        self.components(*FOUR, notes, component_md("quiz", "subagent", "c2-review"))
        self.assertEqual(self.inventory(final=True).status, check.OK, self.inventory().details)
        self.components(*FOUR, component_md("quiz", "subagent", "c2-review"), component_md("tried-reviewer", "subagent", "c2-review", "no, because it never got past Round 3"))
        self.assertEqual(self.inventory(final=True).status, check.OK, "a component tried in a round and taken out before any snapshot keeps its entry")

    def test_a_component_only_in_another_snapshot(self):
        self.snapshot("c1-skills")
        self.snapshot("cheap-tutor", "summarizer")
        self.components(*FOUR, component_md("summarizer", "subagent", "c3-split"))
        self.assertEqual(self.inventory().details, ["summarizer: Step added is c3-split, but only configs/cheap-tutor/ hold it"])
        self.components(*FOUR, component_md("summarizer", "subagent", "cheap-tutor"))
        self.assertEqual(self.inventory().status, check.OK)

    def test_minimums_by_section(self):
        self.snapshot("c1-skills")
        self.snapshot("c2-review", "r1", "r2", "r3")
        self.snapshot("c3-split", "r1", "r2", "r3", "s1")
        r = self.report()
        (item,) = self.find(r, "components built")
        self.assertEqual(item.status, check.TODO)
        self.assertEqual(item.text, "components built: 4 skills and 4 subagents across your snapshots other than c0-baseline (498E needs at least 4 skills, teach, tutor, quiz and grade among them, and 5 subagents)")
        self.assertEqual(item.details, ["skills: grade, quiz, teach, tutor", "subagents: r1, r2, r3, s1"])
        self.snapshot("final", "r1", "s2", hook=True)
        (item,) = self.find(self.report(final=True), "components built")
        self.assertEqual((item.status, item.details), (check.OK, []), "counted over what was built, not what final keeps")
        write(self.root / "p3.json", {"section": "598E", "stretch": None})
        (item,) = self.find(self.report(), "components built")
        self.assertEqual(item.status, check.TODO)
        self.assertIn("(598E needs at least 6 skills, teach, tutor, quiz and grade among them, and 8 subagents)", item.text)
        for extra in ("notes", "glossary"):
            write(self.root / "tutor" / ".claude" / "skills" / extra / "SKILL.md", f"---\nname: {extra}\n---\n")
        self.snapshot("final-minus-review", "s3", "s4", "s5", hook=True)
        (item,) = self.find(self.report(final=True), "components built")
        self.assertEqual(item.status, check.OK, item.text)
        self.assertTrue(item.text.startswith("components built: 6 skills and 8 subagents"), item.text)

    def test_the_required_skills_count_even_when_there_are_enough(self):
        write(self.root / "p3.json", {"section": None, "stretch": None})
        for extra in ("a", "b", "c"):
            write(self.root / "tutor" / ".claude" / "skills" / extra / "SKILL.md", "---\n---\n")
        add_agents(self.root, "r1", "r2", "r3", "r4", "r5")
        add_config(self.root, "experiment", skills=("teach",))
        (item,) = self.find(self.report(), "components built")
        self.assertEqual(item.status, check.TODO)
        self.assertIn("(498E, the default while no section is set, needs at least", item.text)
        self.assertIn("required skills not in a snapshot yet: tutor, quiz, grade", item.details)


if __name__ == "__main__":
    unittest.main()
