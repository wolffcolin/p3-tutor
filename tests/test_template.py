"""The shipped template end to end: the real tutor, fixture, FORMATS.md, scenarios and judge prompts,
copied into a temporary folder and run through bench, score, report, compare and check with
tests/fake_claude.py standing in for claude.

The other test modules use a small made-up fixture (tests/__init__.py); this one catches the seams
between the parts that only the real files can show, such as a judge prompt whose placeholders the
scorer does not fill, or a probe whose leak check the fixture's key does not support."""

from __future__ import annotations

import contextlib
import io
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from p3 import check, claude, cli, compare, config, reviews, score, topic, util
from tests import ENV_KEYS, REPO, fake_command

SHIPPED = ("bench", "p3", "tutor", "configs", "reviews")
QUICK = ["teach", "quiz", "grade-s1", "tutor-p01", "tutor-p02"]


def copy_template(dest: Path) -> Path:
    """The template as a student gets it (no runs, no compare records), in `dest`."""
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "_live")
    for name in SHIPPED:
        if (REPO / name).is_dir():
            shutil.copytree(REPO / name, dest / name, ignore=ignore)
    for name in ("runs", "compare"):
        folder = dest / "bench" / name
        for child in folder.iterdir() if folder.is_dir() else []:
            if child.is_dir():
                util.remove_tree(child)
            elif child.name != ".gitkeep":
                child.unlink()
    for path in REPO.glob("*.md"):
        shutil.copyfile(path, dest / path.name)
    shutil.copyfile(REPO / "p3.json", dest / "p3.json")
    return dest


class TemplateTests(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ENV_KEYS}
        for k in ENV_KEYS:
            os.environ.pop(k, None)
        self._tmp = Path(tempfile.mkdtemp(prefix="p3-template-"))
        self.root = copy_template(self._tmp / "repo")
        os.environ["P3_ROOT"] = str(self.root)
        os.environ["P3_CLAUDE"] = fake_command()
        if not (self.root / "configs" / "c0-baseline" / "SNAPSHOT.json").is_file():
            config.snapshot("c0-baseline", root=self.root)  # before the template's first snapshot exists
        util.rehash(self.root)  # p3/ may be mid-edit; the committed hash file is CI's business

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self._tmp, ignore_errors=True)

    def p3(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_the_baseline_snapshot(self):
        """c0-baseline as it ships: one teach skill for all four jobs, web search and fetch allowed.
        (template-ci also checks that it equals the shipped tutor/; a student's tutor/ moves on.)"""
        ok, recorded, actual = config.verify_snapshot("c0-baseline", REPO)
        self.assertTrue(ok, f"configs/c0-baseline/ no longer matches its SNAPSHOT.json ({recorded} vs {actual})")
        self.assertEqual(config.entries(REPO / "configs" / "c0-baseline"), {job: "/teach" for job in config.JOBS})
        self.assertEqual(config.allowed_tools(REPO / "configs" / "c0-baseline"), ["WebSearch", "WebFetch"])

    def test_bench_score_report_compare_and_check(self):
        tp = topic.load("agent-architecture", self.root)
        self.assertTrue(topic.validate(tp.path).ok(allow_todo=False))

        code, out, err = self.p3("bench", "--config", "c0-baseline", "--quick", "--no-score")
        self.assertEqual(code, 0, err + out)
        (run_dir,) = list(util.runs_dir("c0-baseline", self.root).iterdir())
        run = util.read_json(run_dir / "run.json")
        self.assertEqual([s["id"] for s in run["scenarios"]], QUICK)
        self.assertTrue(all(s["status"] == "ok" for s in run["scenarios"]), run["scenarios"])
        self.assertEqual({s["entry"] for s in run["scenarios"]}, {"/teach"})
        self.assertEqual(run["allowed_tools"], ["Glob", "Grep", "WebSearch", "WebFetch"])

        prompts: list[tuple[str, str]] = []

        def ask(prompt: str, model: str) -> claude.Reply:
            prompts.append((model, prompt))
            return claude.ask_json(prompt, model, 120)

        result = score.score_run(run_dir, offline=True, ask=ask, root=self.root, quiet=True)
        self.assertEqual(result["warnings"], [])
        self.assertEqual(len(prompts), 5, "the teach judge, two solvers and two tutor judges")
        for model, prompt in prompts:
            self.assertNotRegex(prompt, r"\{\{\s*[a-z_]+\s*\}\}", f"a placeholder is left in a prompt for {model}")
        teach_prompt = next(p for _, p in prompts if '"misconceptions_asserted"' in p)
        tutor_prompts = [p for _, p in prompts if '"met"' in p and '"misconceptions_asserted"' not in p]
        solver_prompts = [p for _, p in prompts if '"answers"' in p and '"met"' not in p]
        self.assertEqual((len(tutor_prompts), len(solver_prompts)), (2, 2))
        self.assertIn(tp.learner_summary, teach_prompt)
        for fact in tp.facts_for(tp.teach_objective):
            self.assertIn(fact["id"], teach_prompt)
        for m in tp.misconceptions:
            self.assertIn(m["id"], teach_prompt)
        self.assertEqual(teach_prompt.count("<lesson>"), 2, "the prompt names the tag once and the scorer wraps the lesson once")
        self.assertIn("An agent keeps what matters in its context", teach_prompt)
        p01 = tp.probe("p01")
        p01_prompt = next(p for p in tutor_prompts if p01["message"] in p)
        self.assertIn(tp.learner_summary, p01_prompt)
        self.assertIn(p01["expected"], p01_prompt)
        self.assertEqual(p01_prompt.count("<message>"), 2)
        self.assertEqual(p01_prompt.count("<reply>"), 2)
        key = tp.key(tp.graded_quiz)
        for prompt in solver_prompts:
            self.assertNotIn("rationale", prompt, "the solvers never see a key")
        self.assertTrue(key["items"])

        s = result["summary"]
        for name in ("teach_facts_correct", "teach_misconceptions", "teach_length_ratio", "quiz_key_agreement", "quiz_ambiguous", "grade_verdict_agreement", "grade_false_wrong", "grade_misconception_hit", "tutor_leaks", "tutor_behavior_met"):
            self.assertIsNotNone(s[name], name)
        probes = result["jobs"]["tutor"]["probes"]
        self.assertTrue(probes["p01"]["leak"], "the fake tutor gives the answer to 'just tell me', and the fixture's key catches it")
        self.assertIn("(b)", probes["p01"]["leak_reason"])
        self.assertFalse(probes["p02"]["leak"])
        self.assertEqual(result["jobs"]["teach"]["declared_objective"], tp.teach_objective)
        self.assertTrue(result["jobs"]["teach"]["minutes_declared_ok"])
        self.assertTrue(result["jobs"]["quiz"]["schema_ok"], result["jobs"]["quiz"]["schema_errors"])
        self.assertTrue(result["jobs"]["grade"]["submissions"]["s1"]["schema_ok"])

        code, out, err = self.p3("report", "--quick")
        self.assertEqual(code, 0, err)
        self.assertIn("| `c0-baseline` | 1 |", out)

        config.snapshot("c0-copy", root=self.root)
        code, out, err = self.p3("bench", "--config", "c0-copy", "--quick", "--offline")
        self.assertEqual(code, 0, err + out)
        code, _out, err = self.p3("compare", "c0-baseline", "c0-baseline", "--job", "tutor", "--terminal", "--quick")
        self.assertEqual(code, 1)
        self.assertIn("two different configs", err)
        code, _out, err = self.p3("compare", "c0-baseline", "c0-copy", "--job", "tutor", "--terminal")
        self.assertEqual(code, 1)
        self.assertIn("add --quick", err, "the template's first runs are quick, and the message says how to pair them")
        record = compare.new_session("c0-baseline", "c0-copy", "tutor", quick=True, seed=3, root=self.root)
        self.assertEqual([p["item"] for p in record["pairs"]], ["tutor-p01", "tutor-p02"])
        session = compare.Session(record["session"], self.root)
        answers = iter(["l", "It asked me what I thought first.", "n", "t", "Both fine.", "y"])
        with contextlib.redirect_stdout(io.StringIO()):
            compare.terminal(session, ask=lambda _prompt: next(answers), folder=self._tmp / "pairs")
        page = (self._tmp / "pairs" / "pair-001.html").read_text(encoding="utf-8")
        self.assertIn("stuck on q3", page)
        self.assertNotIn("c0-baseline", page, "the page never names a config")
        self.assertNotIn("c0-copy", page)
        code, out, err = self.p3("compare", "--reveal", record["session"])
        self.assertEqual(code, 0, err)
        self.assertRegex(out, r"`c0-baseline` won [01], `c0-copy` won [01], and 1 was a tie\.")
        self.assertLess(out.index("### Tally"), out.index("### Sign test"))
        self.assertLess(out.index("### Reasons, by the config that won"), out.index("### Cost per tutor scenario"))

        r = check.run_checks(self.root)
        self.assertEqual([i for i in r.items(check.INTEGRITY) if i.status == check.FAIL], [], r.text())
        self.assertEqual(r.exit_code(), 0)
        self.assertTrue(re.search(r"bench/runs/c0-baseline/: 1 run, each made with configs/c0-baseline/", r.text()), r.text())
        strict = check.run_checks(self.root, final=True)
        self.assertEqual(strict.exit_code(), 1, "the template is not a finished hand-in")
        self.assertIn("compare c0-baseline / final, tutor on agent-architecture: no complete session yet", strict.text())
        self.assertNotIn("compare c0-baseline / c1-skills", strict.text(), "the only required blind comparison is c0-baseline against final")

    @unittest.skipUnless((REPO / reviews.REVIEWS_DIR).is_dir(), "the template's reviews/ is not in this checkout yet")
    def test_the_shipped_review_files(self):
        """reviews/ as it ships: every file p3 check reads is there and parses, every item it makes is
        work to do (TODO) without --final and a FAIL with it, and reviews/README.md holds no TODO."""
        readme = self.root / reviews.REVIEWS_DIR / "README.md"
        self.assertTrue(readme.is_file(), "reviews/README.md tells the student how to use the files")
        self.assertNotIn("TODO", util.read_text(readme))
        for step in reviews.STEPS:
            review = reviews.read_step(step, self.root)
            self.assertIsNotNone(review, f"the template ships {reviews.step_file(step)}")
            self.assertTrue(review.major.present, step)
            self.assertFalse(review.major.complete or review.major.touched, f"{step}: the major review ships with every text TODO")
            self.assertEqual(review.major.ratings(), {}, step)
            self.assertIsNone(review.rounds_problem, step)
            if step == "final":
                self.assertEqual([(r.optional, r.touched) for r in review.rounds], [(True, False)], "one optional round, untouched")
                self.assertIsNone(review.sessions_problem)
                self.assertEqual(len(review.sessions), reviews.SESSIONS)
                self.assertFalse(any(s.touched for s in review.sessions))
                self.assertIsNone(review.topics_problem)
                self.assertTrue(review.topics and all(t.problems for t in review.topics), "the test-topic sections ship as TODO placeholders")
            else:
                self.assertEqual([(r.optional, r.touched) for r in review.rounds], [(False, False), (False, False)], step)
            structural = [p for p in review.major.problems if "is still TODO" not in p and "still the placeholder" not in p]
            self.assertEqual(structural, [], f"{step}: every heading and field p3 check reads is in place")
        entries = reviews.read_components(self.root)
        self.assertIsNotNone(entries, "the template ships reviews/components.md")
        self.assertEqual(len(entries), 1, "one empty entry; the example sits inside an HTML comment")
        self.assertTrue(all("is still TODO" in p or "give the entry" in p for p in entries[0].problems), entries[0].problems)
        loose, strict = check.run_checks(self.root), check.run_checks(self.root, final=True)
        self.assertEqual(loose.exit_code(), 0, loose.text())
        mine = [i for i in loose.items(check.HANDIN) if i.text.startswith(f"{reviews.REVIEWS_DIR}/")]
        self.assertEqual(len(mine), 11, "rounds and major review of each step, final's sessions and test topics, the inventory")
        for item in mine:
            optional = "quick rounds (optional)" in item.text
            self.assertEqual(item.status, check.OK if optional else check.TODO, item.text)
        for item in strict.items(check.HANDIN):
            if item.text.startswith(f"{reviews.REVIEWS_DIR}/"):
                self.assertEqual(item.status, check.OK if "quick rounds (optional)" in item.text else check.FAIL, item.text)
        self.assertEqual([i.status for i in loose.items() if "c1-skills: skills only" in i.text], [check.OK])


if __name__ == "__main__":
    unittest.main()
