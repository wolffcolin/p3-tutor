"""The scorer's checks, one by one, and scoring a run with stubbed model calls (p3/score.py)."""

from __future__ import annotations

import os
import shutil
import ssl
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from p3 import claude, score, util
from p3.util import P3Error
from tests import RepoTestCase, write

MCQ = {"id": "q1", "type": "mcq", "options": [{"id": "a", "text": "The model itself"}, {"id": "b", "text": "The program around the model, which returns the result"}, {"id": "c", "text": "Nobody"}]}
MCQ_KEY = {"id": "q1", "answer": "b"}
NUMERIC = {"id": "q2", "type": "numeric"}
SHORT = {"id": "q3", "type": "short"}


def lesson(body: str, head: str = "") -> str:
    return f"<!doctype html><html><head><title>Title words here</title>{head}</head><body>{body}</body></html>"


class LengthTests(unittest.TestCase):
    def test_ratio_and_bounds(self):
        self.assertEqual(score.length_check(4500, 30), {"words": 4500, "est_minutes": 30.0, "length_ratio": 1.0, "length_ok": True})
        self.assertFalse(score.length_check(2000, 30)["length_ok"])
        self.assertTrue(score.length_check(2700, 30)["length_ok"], "0.6 exactly is on length")
        self.assertFalse(score.length_check(2699, 30)["length_ok"])
        self.assertTrue(score.length_check(6750, 30)["length_ok"], "1.5 exactly is on length")
        self.assertFalse(score.length_check(6751, 30)["length_ok"])
        self.assertAlmostEqual(score.length_check(1500, 10)["length_ratio"], 1.0)

    def test_visible_words_leave_out_script_style_and_title(self):
        html = lesson(
            "<h1>Two words</h1><p>three more words</p><script>var a = 'not these words';</script>"
            "<style>.x { color: red }</style><p>and &amp; four - here</p>",
            head="<script>also not</script><style>p{}</style>",
        )
        parsed = score.parse_lesson(html)
        text = parsed.visible_text()
        self.assertNotIn("not these", text)
        self.assertNotIn("Title", text)
        self.assertNotIn("color", text)
        self.assertEqual(score.count_words(text), 2 + 3 + 3, "'&' and '-' are not words")


class SelfContainedTests(unittest.TestCase):
    def test_remote_scripts_and_stylesheets(self):
        html = lesson(
            '<img src="https://example.com/a.png"><img src="assets/b.png"><img src="data:image/png;base64,xx">',
            head=(
                '<meta name="p3-minutes" content="30"><meta name="P3-Objective" content="O3">'
                '<script src="https://cdn.example.com/x.js"></script><script src="assets/local.js"></script>'
                '<link rel="stylesheet" href="//fonts.example.com/f.css"><link rel="stylesheet" href="assets/s.css">'
                '<link rel="icon" href="https://example.com/favicon.ico">'
                '<style>@import url("https://example.com/more.css"); body { margin: 0 }</style>'
            ),
        )
        parsed = score.parse_lesson(html)
        self.assertEqual(parsed.remote_scripts, ["https://cdn.example.com/x.js"])
        self.assertEqual(parsed.remote_stylesheets, ["//fonts.example.com/f.css", "https://example.com/more.css"])
        self.assertEqual(parsed.remote_images, ["https://example.com/a.png"])
        self.assertEqual(parsed.meta["p3-minutes"], "30")
        self.assertEqual(parsed.meta["p3-objective"], "O3")

    def test_a_clean_lesson(self):
        parsed = score.parse_lesson(lesson('<p>See <a href="https://example.com/x">this</a>, <a href="lessons/0002-b.html">next</a>, <a href="#top">top</a> and <a href="https://example.com/x">again</a>.</p>'))
        self.assertEqual(parsed.remote_scripts + parsed.remote_stylesheets, [])
        self.assertEqual(parsed.links, ["https://example.com/x"], "external links only, each once")


class LinkTests(unittest.TestCase):
    def opener(self, codes):
        def open_(url, timeout):
            self.assertEqual(timeout, score.LINK_TIMEOUT_S)
            code = codes[url]
            if isinstance(code, Exception):
                raise code
            if isinstance(code, int) and code >= 400:
                raise urllib.error.HTTPError(url, code, "x", {}, None)
            return code

        return open_

    def test_classification(self):
        codes = {
            "https://ok": 200, "https://moved": 301, "https://gone": 410, "https://missing": 404, "https://forbidden": 403,
            "https://broken": 500, "https://down": OSError("no route"), "https://slow": TimeoutError(),
        }  # fmt: skip
        opener = self.opener(codes)
        got = {url: score.classify_link(url, opener)[0] for url in codes}
        self.assertEqual(got, {
            "https://ok": "ok", "https://moved": "ok", "https://gone": "dead", "https://missing": "dead", "https://forbidden": "unknown",
            "https://broken": "unknown", "https://down": "unknown", "https://slow": "unknown",
        })  # fmt: skip
        self.assertEqual(score.classify_link("https://missing", opener), ("dead", 404))

    def test_offline_checks_nothing(self):
        self.assertEqual(score.check_links(["https://x"], offline=True), [{"url": "https://x", "status": "unchecked", "code": None}])
        self.assertEqual(score.check_links([], offline=False), [])


class GradeTests(unittest.TestCase):
    TRUE = [
        {"id": "q1", "verdict": "wrong", "misconception": "M1"},
        {"id": "q2", "verdict": "correct", "misconception": None},
        {"id": "q3", "verdict": "correct", "misconception": None},
        {"id": "q4", "verdict": "partial", "misconception": "M2"},
    ]

    def test_metrics(self):
        graded = {"items": [
            {"id": "q1", "verdict": "wrong", "misconception": "M1", "feedback": "No: the program runs it."},
            {"id": "q2", "verdict": "partial", "misconception": None, "feedback": "Almost."},
            {"id": "q3", "verdict": "correct", "misconception": None, "feedback": "  "},
            {"id": "q4", "verdict": "partial", "misconception": "M3", "feedback": "Half."},
        ]}  # fmt: skip
        m = score.grade_metrics(self.TRUE, graded)
        self.assertEqual(m["verdict_agreement"], 0.75)
        self.assertEqual(m["false_wrong_rate"], 0.5, "q2 was right and graded partial")
        self.assertEqual(m["misconception_hit_rate"], 0.5, "q1 named M1; q4 named M3, not M2")
        self.assertEqual(m["feedback_present"], 0.75, "blank feedback does not count")

    def test_missing_items_count_against(self):
        m = score.grade_metrics(self.TRUE, {"items": [{"id": "q2", "verdict": "correct", "misconception": None, "feedback": "ok"}]})
        self.assertEqual(m["verdict_agreement"], 0.25)
        self.assertEqual(m["false_wrong_rate"], 0.5)
        self.assertEqual(m["misconception_hit_rate"], 0.0)
        m = score.grade_metrics(self.TRUE, None)
        self.assertEqual((m["verdict_agreement"], m["false_wrong_rate"], m["feedback_present"]), (0.0, 1.0, 0.0))

    def test_rates_without_a_base_are_none(self):
        m = score.grade_metrics([{"id": "q1", "verdict": "wrong", "misconception": None}], {"items": []})
        self.assertIsNone(m["false_wrong_rate"])
        self.assertIsNone(m["misconception_hit_rate"])

    def test_pooled_over_items(self):
        a = score.grade_metrics(self.TRUE, {"items": [{"id": i["id"], **i, "feedback": "x"} for i in self.TRUE]})
        b = score.grade_metrics(self.TRUE[:1], None)
        pooled = score.pooled_grades([a, b])
        self.assertEqual(pooled["verdict_agreement"], 0.8, "4 of 5 items, not the mean of 1.0 and 0.0")

    def test_schema(self):
        good = {"quiz": "0001", "submission": "s1", "items": [{"id": "q1", "verdict": "correct", "misconception": None, "feedback": "ok"}], "summary": "ok"}
        self.assertEqual(score.grade_schema_errors(good), [])
        bad = {"quiz": "0001", "items": [{"id": "q1", "verdict": "fine", "feedback": 3}]}
        errors = score.grade_schema_errors(bad)
        self.assertTrue(any("submission" in e for e in errors))
        self.assertTrue(any("verdict" in e for e in errors))
        self.assertTrue(any("misconception" in e for e in errors))
        self.assertTrue(any("feedback" in e for e in errors))
        self.assertEqual(score.grade_schema_errors([]), ["the grades file must hold a JSON object"])


class LeakTests(unittest.TestCase):
    def leak(self, reply, item=MCQ, key=MCQ_KEY):
        return score.detect_leak(reply, item, key)[0]

    def test_mcq_option_id_patterns(self):
        for reply in (
            "OK, the answer is b.", "The answer is (B).", "the answer is [b], because the program runs it", "Answer: b",
            "It's option b.", "Go with option (b)", "(b) is correct.", "b) is the correct one", "B is right",
            "the correct answer is b", "The answer would be b",
        ):  # fmt: skip
            self.assertTrue(self.leak(reply), reply)

    def test_mcq_non_leaks(self):
        for reply in (
            "I can't give you the answer, but think about who runs the code.",
            "Option c is a common trap.", "What do you think the answer is?", "Think about b-trees later.",
            "Let's go back to the agent loop.", "",
        ):  # fmt: skip
            self.assertFalse(self.leak(reply), reply)

    def test_mcq_bare_id_needs_an_end(self):
        item = {"id": "q1", "type": "mcq", "options": [{"id": "a", "text": "Loop"}, {"id": "b", "text": "Line"}]}
        key = {"id": "q1", "answer": "a"}
        self.assertFalse(self.leak("The answer is a loop that runs until it stops.", item, key))
        self.assertTrue(self.leak("The answer is a.", item, key))
        self.assertTrue(self.leak("the answer is a, since it loops", item, key))

    def test_mcq_option_text(self):
        self.assertTrue(self.leak("Really it's the program around the model, which returns the result."))
        short = {"id": "q1", "type": "mcq", "options": [{"id": "a", "text": "Yes"}, {"id": "b", "text": "No way"}]}
        self.assertFalse(self.leak("No way am I telling you.", short, {"id": "q1", "answer": "b"}), "option texts under 12 characters are not checked")

    def test_numeric(self):
        key = {"id": "q2", "answer": 3, "tolerance": 0}
        self.assertTrue(self.leak("You get 3 results back.", NUMERIC, key))
        self.assertFalse(self.leak("You get 30 results back.", NUMERIC, key))
        self.assertFalse(self.leak("Count them yourself.", NUMERIC, key))
        self.assertFalse(self.leak("About 2.99.", NUMERIC, key))
        self.assertTrue(self.leak("About 2.99.", NUMERIC, {"id": "q2", "answer": 3}), "default 1% tolerance")
        self.assertTrue(self.leak("It is 1,200 ms.", NUMERIC, {"id": "q2", "answer": 1200}))

    def test_short(self):
        key = {"id": "q3", "answer": "the program", "accepted": ["the harness", "it"]}
        self.assertTrue(self.leak("It's the Program, obviously.", SHORT, key))
        self.assertTrue(self.leak("the harness does that", SHORT, key))
        self.assertFalse(self.leak("Programs are fun.", SHORT, key))
        self.assertFalse(self.leak("it depends", SHORT, key), "accepted forms under 4 characters are not checked")


class MatchingTests(unittest.TestCase):
    def test_mcq(self):
        for answer in ("b", "B", "(b)", "b.", "b) The program", "[B]", "option b", "The program around the model, which returns the result"):
            self.assertTrue(score.match_answer(MCQ, MCQ_KEY, answer), answer)
        self.assertFalse(score.match_answer(MCQ, MCQ_KEY, "a"))
        self.assertFalse(score.match_answer(MCQ, MCQ_KEY, "I don't know"))
        self.assertIsNone(score.match_answer(MCQ, MCQ_KEY, None))
        self.assertIsNone(score.match_answer(MCQ, MCQ_KEY, "  "))

    def test_numeric(self):
        self.assertTrue(score.match_answer(NUMERIC, {"answer": 3, "tolerance": 0.5}, "3.4"))
        self.assertFalse(score.match_answer(NUMERIC, {"answer": 3, "tolerance": 0.5}, "3.6"))
        self.assertTrue(score.match_answer(NUMERIC, {"answer": 200}, 201.9), "within 1%")
        self.assertFalse(score.match_answer(NUMERIC, {"answer": 200}, 202.5))
        self.assertTrue(score.match_answer(NUMERIC, {"answer": 3}, "3 calls"))
        self.assertTrue(score.match_answer(NUMERIC, {"answer": 0}, "0"))
        self.assertFalse(score.match_answer(NUMERIC, {"answer": 3}, "three"))

    def test_short(self):
        key = {"answer": "The Program", "accepted": ["the harness"]}
        self.assertTrue(score.match_answer(SHORT, key, "  the   program. "))
        self.assertTrue(score.match_answer(SHORT, key, "The harness"))
        self.assertIsNone(score.match_answer(SHORT, key, "the code that calls the model"), "unscored, not wrong")

    def test_solver_agreement(self):
        self.assertTrue(score.answers_agree(MCQ, MCQ_KEY, "(a)", "a"))
        self.assertFalse(score.answers_agree(MCQ, MCQ_KEY, "a", "c"))
        self.assertIsNone(score.answers_agree(MCQ, MCQ_KEY, "dunno", "no idea"))
        self.assertTrue(score.answers_agree(NUMERIC, {"answer": 100}, "100.5", "100"))
        self.assertFalse(score.answers_agree(NUMERIC, {"answer": 100}, "120", "100"))
        self.assertIsNone(score.answers_agree(SHORT, {"answer": "x y z"}, "abc", "abc"))
        self.assertTrue(score.answers_agree(SHORT, {"answer": "x y z"}, "X Y Z", "x y z"))


class SolverReportTests(RepoTestCase):
    """apply_solvers on a hand-made quiz: key agreement, likely wrong keys and likely ambiguous items."""

    def test_flags(self):
        run_dir = self.root / "bench" / "runs" / "x" / "r"
        quiz = {"id": "0002", "objective": "O2", "title": "t", "items": [
            {"id": "q1", "type": "mcq", "objective": "O2", "stem": "s", "options": [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}]},
            {"id": "q2", "type": "mcq", "objective": "O2", "stem": "s", "options": [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}]},
            {"id": "q3", "type": "numeric", "objective": "O2", "stem": "s"},
            {"id": "q4", "type": "short", "objective": "O2", "stem": "s"},
        ]}  # fmt: skip
        key = {"id": "0002", "items": [{"id": "q1", "answer": "a"}, {"id": "q2", "answer": "a"}, {"id": "q3", "answer": 10}, {"id": "q4", "answer": "loop"}]}
        write(run_dir / "quiz" / "outputs" / "quizzes" / "0002.json", quiz)
        write(run_dir / "quiz" / "outputs" / "keys" / "0002.json", key)
        out = {"quiz": "quizzes/0002.json", "key": "keys/0002.json", "items": [], "likely_wrong_key": [], "likely_ambiguous": []}

        def reply(answers):
            return claude.Reply({"answers": [{"id": k, "answer": v} for k, v in answers.items()]}, "", None, 10, 0.01, "m", 0.1)

        replies = {
            score.SOLVER_MODELS[0]: reply({"q1": "a", "q2": "b", "q3": "12", "q4": "a cycle"}),
            score.SOLVER_MODELS[1]: reply({"q1": "b", "q2": "b", "q3": "12"}),
        }
        score.apply_solvers(out, replies, run_dir, {"id": "quiz"})
        self.assertEqual(out["key_agreement"], round(1 / 3, 4), "q1 agrees; q2 and q3 do not; q4 is unscored")
        self.assertEqual(out["likely_wrong_key"], ["q2", "q3"])
        self.assertEqual(out["likely_ambiguous"], ["q1"])
        self.assertEqual(out["scorable_items"], 3)


class SchemaTests(unittest.TestCase):
    QUIZ = {"id": "0002", "objective": "O2", "title": "t", "items": [{"id": "q1", "type": "mcq", "objective": "O2", "stem": "s", "options": [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}]}, {"id": "q2", "type": "numeric", "objective": "O2", "stem": "s", "unit": "s"}]}
    KEY = {"id": "0002", "items": [{"id": "q1", "answer": "b"}, {"id": "q2", "answer": 4}]}

    def test_good(self):
        self.assertEqual(score.quiz_schema_errors(self.QUIZ, self.KEY, "0002"), [])

    def test_bad(self):
        self.assertIn("the key is missing or is not a JSON object", score.quiz_schema_errors(self.QUIZ, None, "0002"))
        errors = score.quiz_schema_errors(self.QUIZ, {"id": "0003", "items": [{"id": "q1", "answer": "z"}]}, "0002")
        self.assertTrue(any("key's id" in e for e in errors))
        self.assertTrue(any("option ids" in e for e in errors))
        self.assertTrue(any("differ" in e for e in errors))
        quiz = {**self.QUIZ, "items": [{"id": "q1", "type": "essay", "objective": "O2", "stem": "s"}]}
        self.assertTrue(any("type must be" in e for e in score.quiz_schema_errors(quiz, self.KEY, "0002")))


class JudgePromptTests(RepoTestCase):
    def test_inputs_are_appended(self):
        prompt = score.judge_prompt(self.root, "tutor", {"learner_summary": "a junior", "reply": "<reply>\nhi\n</reply>"})
        self.assertTrue(prompt.startswith("# Tutor judge"))
        self.assertIn("## Input", prompt)
        self.assertIn("### The learner\n\na junior", prompt)
        self.assertIn("### The tutor's reply\n\n<reply>\nhi\n</reply>", prompt)

    def test_placeholders_are_filled(self):
        write(self.root / "bench" / "judge" / "tutor.md", 'Learner: {{learner_summary}}\nReply: {{ reply }}\nReturn {"met": true}\n')
        prompt = score.judge_prompt(self.root, "tutor", {"learner_summary": "a junior", "reply": "hi {{learner_summary}} {x}"})
        self.assertEqual(prompt, 'Learner: a junior\nReply: hi {{learner_summary}} {x}\nReturn {"met": true}\n', "one pass of plain replacement: braces in a prompt or an input stay as they are")

    def test_placeholders_must_fit_the_inputs(self):
        write(self.root / "bench" / "judge" / "tutor.md", "Learner: {{learner_summary}}\nReply: {{reply}}\nUnknown: {{other}}\n")
        with self.assertRaisesRegex(P3Error, r"\{\{other\}\}, which the scorer does not fill"):
            score.judge_prompt(self.root, "tutor", {"learner_summary": "a junior", "reply": "hi"})
        write(self.root / "bench" / "judge" / "tutor.md", "Learner: {{learner_summary}}\n")
        with self.assertRaisesRegex(P3Error, "never shows the model reply"):
            score.judge_prompt(self.root, "tutor", {"learner_summary": "a junior", "reply": "hi"})

    def test_missing_prompt(self):
        with self.assertRaises(P3Error):
            score.judge_prompt(self.root, "nothing", {})


class ScoreRunTests(RepoTestCase):
    """Scoring runs made with the fake claude, with the model calls and the links stubbed."""

    def setUp(self):
        super().setUp()
        code, out, err = self.p3("bench", "--config", "c0-baseline", "--quick", "--no-score")
        self.assertEqual(code, 0, err + out)
        (self.run_dir,) = [p for p in util.runs_dir("c0-baseline", self.root).iterdir()]
        self.calls = []

    def ask(self, prompt, model):
        self.calls.append((model, prompt))
        if '"misconceptions_asserted"' in prompt:
            data = {"facts": [{"id": "F3.1", "present": True, "correct": True}, {"id": "F3.2", "present": True, "correct": False}, {"id": "F9.9", "present": True, "correct": True}], "misconceptions_asserted": ["M2", "M9"], "level_fit": 3, "notes": "n"}
        elif '"met"' in prompt:
            data = {"met": True, "notes": "fine"}
        else:
            data = None
        return claude.Reply(data, "", None if data else "no JSON object in the reply", 100, 0.05, model, 0.1)

    def opener(self, url, timeout):
        if "gone" in url:
            raise urllib.error.HTTPError(url, 404, "x", {}, None)
        return 200

    def test_stubbed_judges_and_links(self):
        result = score.score_run(self.run_dir, ask=self.ask, opener=self.opener, root=self.root, quiet=True)
        teach = result["jobs"]["teach"]
        self.assertEqual([link["status"] for link in teach["links"]], ["ok", "dead"])
        self.assertEqual(result["summary"]["teach_dead_links"], 1)
        self.assertEqual(teach["judge"]["misconceptions_asserted"], ["M2"], "unknown ids are dropped")
        self.assertEqual([f["id"] for f in teach["judge"]["facts"]], ["F3.1", "F3.2", "F3.3", "F3.4"], "facts the judge left out count as absent")
        self.assertEqual(result["summary"]["teach_facts_correct"], 0.25)
        self.assertEqual(teach["facts_present"], 0.5)
        self.assertEqual(result["summary"]["teach_misconceptions"], 1)
        self.assertEqual(teach["judge"]["level_fit"], 3)
        self.assertIsNone(result["summary"]["quiz_key_agreement"], "the stub's solvers gave no answers")
        self.assertTrue(any("model call failed" in w for w in result["warnings"]))
        self.assertEqual(result["summary"]["tutor_behavior_met"], 1.0)
        models = sorted(m for m, _ in self.calls)
        self.assertEqual(models, sorted(["claude-sonnet-5-5"] * 3 + list(score.SOLVER_MODELS)))
        solver_prompt = next(p for m, p in self.calls if m == "claude-haiku-5-5")
        self.assertNotIn('"answer": "b"', solver_prompt.split("## Input", 1)[1], "the solvers never see the key")
        self.assertIn("Who runs a tool the model asks for?", solver_prompt)
        teach_prompt = next(p for m, p in self.calls if '"misconceptions_asserted"' in p)
        self.assertIn("F3.4", teach_prompt)
        self.assertIn("The model runs the tools itself.", teach_prompt)
        self.assertIn("<lesson>", teach_prompt)
        self.assertNotIn("notCounted", teach_prompt, "the judge sees the visible text only")
        self.assertEqual(result["scoring_cost"]["calls"], 5)
        self.assertAlmostEqual(result["scoring_cost"]["cost_usd_list"], 0.25)

    def test_no_lesson_and_two_lessons_are_failures(self):
        outputs = self.run_dir / "teach" / "outputs" / "lessons"
        run = util.read_json(self.run_dir / "run.json")
        teach = run["scenarios"][0]
        shutil.copy(outputs / "0001-context-and-memory.html", outputs / "0002-again.html")
        teach["outputs"].append("lessons/0002-again.html")
        util.write_json(self.run_dir / "run.json", run)
        result = score.score_run(self.run_dir, offline=True, ask=self.ask, root=self.root, quiet=True)
        self.assertFalse(result["jobs"]["teach"]["ok"])
        self.assertIn("found 2", result["jobs"]["teach"]["error"])
        self.assertEqual(result["summary"]["teach_facts_correct"], 0.0)
        teach["outputs"] = []
        util.write_json(self.run_dir / "run.json", run)
        result = score.score_run(self.run_dir, offline=True, no_model=True, root=self.root, quiet=True)
        self.assertIn("found 0", result["jobs"]["teach"]["error"])
        self.assertIsNone(result["summary"]["teach_facts_correct"], "not judged at all with --no-model")
        self.assertIsNone(result["summary"]["teach_length_ratio"])

    def test_a_changed_workspace_file_is_not_a_new_lesson(self):
        run = util.read_json(self.run_dir / "run.json")
        run["scenarios"][0]["changed"] = ["lessons/0001-context-and-memory.html"]
        util.write_json(self.run_dir / "run.json", run)
        result = score.score_run(self.run_dir, offline=True, no_model=True, root=self.root, quiet=True)
        self.assertIn("found 0", result["jobs"]["teach"]["error"])

    def test_missing_grades_file(self):
        (self.run_dir / "grade-s1" / "outputs" / "grades" / "0001-s1.json").unlink()
        run = util.read_json(self.run_dir / "run.json")
        run["scenarios"][2]["outputs"] = []
        util.write_json(self.run_dir / "run.json", run)
        result = score.score_run(self.run_dir, offline=True, no_model=True, root=self.root, quiet=True)
        sub = result["jobs"]["grade"]["submissions"]["s1"]
        self.assertFalse(sub["schema_ok"])
        self.assertEqual(result["summary"]["grade_verdict_agreement"], 0.0)
        self.assertEqual(result["summary"]["grade_false_wrong"], 1.0)

    def test_one_solver_failing_leaves_the_comparison_unknown(self):
        def ask(prompt, model):
            if model == score.SOLVER_MODELS[1]:
                return claude.Reply(None, "", "no reply within 600 s", 0, 0.0, model, 600)
            return claude.ask_json(prompt, model, 60)

        result = score.score_run(self.run_dir, offline=True, ask=ask, root=self.root, quiet=True)
        self.assertEqual(result["summary"]["quiz_key_agreement"], 1.0)
        self.assertIsNone(result["summary"]["quiz_ambiguous"])
        self.assertIsNone(result["summary"]["quiz_wrong_key"])

    def test_no_model_judges_no_behavior(self):
        result_path = self.run_dir / "tutor-p01" / "result.json"
        util.write_json(result_path, {"type": "result", "is_error": True, "subtype": "timeout"})
        result = score.score_run(self.run_dir, offline=True, no_model=True, root=self.root, quiet=True)
        self.assertIsNone(result["summary"]["tutor_behavior_met"], "an empty reply alone must not make the share 0")
        self.assertEqual(result["summary"]["tutor_leaks"], 1, "the leak check still runs")
        result = score.score_run(self.run_dir, offline=True, ask=self.ask, root=self.root, quiet=True)
        self.assertEqual(result["summary"]["tutor_behavior_met"], 0.5, "with the judge on, an empty reply is not met")

    def test_topic_change_is_a_warning(self):
        write(self.root / "bench" / "topics" / "agent-architecture" / "workspace" / "NOTES.md", "changed\n")
        result = score.score_run(self.run_dir, offline=True, no_model=True, root=self.root, quiet=True)
        self.assertTrue(any("has changed since this run" in w for w in result["warnings"]))

    def test_score_command_errors(self):
        code, _, err = self.p3("score", "bench/runs/nothing")
        self.assertEqual(code, 1)
        self.assertIn("no run at", err)
        os.environ.pop("P3_CLAUDE")
        from unittest import mock

        with mock.patch("p3.claude.shutil.which", return_value=None):
            code, _, err = self.p3("score", str(self.run_dir), "--offline")
            self.assertEqual(code, 1)
            self.assertIn("P3_CLAUDE", err)
            code, _, err = self.p3("score", str(self.run_dir), "--offline", "--no-model")
            self.assertEqual(code, 0, err)

    def test_summary_text(self):
        result = score.score_run(self.run_dir, offline=True, no_model=True, root=self.root, quiet=True)
        text = score.summary_text(result)
        self.assertIn("grade: verdict agreement", text)
        self.assertIn("1.00", text)


class LeakBoundaryTests(unittest.TestCase):
    """The leak check reads numbers and option ids the way a reader would, not as any digit or letter."""

    def leak(self, reply, item=MCQ, key=MCQ_KEY, ignore=()):
        return score.detect_leak(reply, item, key, ignore=ignore)[0]

    def test_numbers_inside_ids_are_not_answers(self):
        q4 = {"id": "q4", "type": "numeric"}
        self.assertFalse(self.leak("Let's look at q4 together: what happens on each pass?", q4, {"id": "q4", "answer": 4}))
        self.assertFalse(self.leak("I can't give answers to quiz 0001 before grading.", NUMERIC, {"id": "q2", "answer": 1}))
        self.assertFalse(self.leak("Quiz 1234 stays closed.", NUMERIC, {"id": "q2", "answer": 1234}, ignore=("1234",)), "the quiz's own id")
        self.assertFalse(self.leak("See grades/0001-s1.json, fact F3.1 and the 4th step.", NUMERIC, {"id": "q2", "answer": 1}))
        self.assertTrue(self.leak("It takes 4 passes.", q4, {"id": "q4", "answer": 4}))
        self.assertTrue(self.leak("q4: 4.", q4, {"id": "q4", "answer": 4}))
        self.assertTrue(self.leak("Each call takes 1200ms.", NUMERIC, {"id": "q2", "answer": 1200}), "a unit may follow")
        self.assertTrue(self.leak("About 2.99, so 3.", NUMERIC, {"id": "q2", "answer": 3, "tolerance": 0}))

    def test_the_article_a_is_not_option_a(self):
        item = {"id": "q1", "type": "mcq", "options": [{"id": "a", "text": "A step limit"}, {"id": "b", "text": "More context"}]}
        key = {"id": "q1", "answer": "a"}
        for reply in (
            "That is a choice a lot of learners make.", "Pick an option a learner might choose, then tell me why.",
            "a is right there in the loop, look again.", "The answer is a matter of who runs the loop.",
        ):  # fmt: skip
            self.assertFalse(self.leak(reply, item, key), reply)
        for reply in ("The answer is a.", "It's option A.", "Option (a) is correct.", "I think A is right.", "The answer is: a", "Go with option a."):
            self.assertTrue(self.leak(reply, item, key), reply)

    def test_answer_is_with_a_colon(self):
        self.assertTrue(self.leak("The answer is: b"))
        self.assertTrue(self.leak("The correct answer is: (B), because the program runs it."))

    def test_a_name_that_ends_in_the_letter(self):
        self.assertFalse(self.leak("My plan B is the right fallback here."))
        self.assertTrue(self.leak("Yes, b is right."))
        self.assertTrue(self.leak("So B is correct."))


class CertificateTests(unittest.TestCase):
    def test_a_certificate_failure_is_named(self):
        cert = urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed"))

        def opener(url, timeout):
            raise cert if "a" in url else score.CertificateProblem(url)

        self.assertEqual(score.check_link("https://a", opener), {"url": "https://a", "status": "unknown", "code": None, "error": "certificate"})
        links = score.check_links(["https://a", "https://b"], False, opener)
        self.assertTrue(score.certificates_failed(links))
        self.assertFalse(score.certificates_failed([]))
        self.assertFalse(score.certificates_failed(links + [{"url": "https://c", "status": "dead", "code": 404}]))
        self.assertEqual(score.classify_link("https://a", opener), ("unknown", None))

    def test_the_opener_tries_the_system_bundle(self):
        bundle = Path(tempfile.mkdtemp(prefix="p3-certs-")) / "cert.pem"
        bundle.write_text("x", encoding="utf-8")
        seen = []

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def urlopen(request, timeout, context=None):
            seen.append(context)
            if context is None:
                raise urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed"))
            return Response()

        try:
            with mock.patch.object(score, "CERT_FILES", (str(bundle),)), mock.patch("p3.score.ssl.create_default_context", return_value="bundle-context"), mock.patch("p3.score.urllib.request.urlopen", side_effect=urlopen):
                self.assertEqual(score.default_opener("https://x", 5), 200)
                self.assertEqual(seen, [None, "bundle-context"])
            with mock.patch.object(score, "CERT_FILES", ()), mock.patch("p3.score.urllib.request.urlopen", side_effect=urlopen):
                with self.assertRaises(score.CertificateProblem):
                    score.default_opener("https://x", 5)
        finally:
            shutil.rmtree(bundle.parent, ignore_errors=True)


class ScoreFailureTests(RepoTestCase):
    """Jobs that failed, and scoring that cannot finish."""

    def setUp(self):
        super().setUp()
        code, out, err = self.p3("bench", "--config", "c0-baseline", "--quick", "--no-score")
        self.assertEqual(code, 0, err + out)
        (self.run_dir,) = [p for p in util.runs_dir("c0-baseline", self.root).iterdir()]
        self.calls = []

    def ask(self, prompt, model):
        self.calls.append(model)
        return claude.ask_json(prompt, model, 60)

    def set_scenario(self, sid, status, result):
        run = util.read_json(self.run_dir / "run.json")
        next(s for s in run["scenarios"] if s["id"] == sid)["status"] = status
        util.write_json(self.run_dir / "run.json", run)
        util.write_json(self.run_dir / sid / "result.json", result)

    def test_a_probe_with_no_reply_is_not_a_clean_probe(self):
        # p02 is the probe the fake tutor leaks on; with no reply there is nothing to call a leak or not
        self.set_scenario("tutor-p02", "timeout", {"type": "result", "is_error": True, "subtype": "timeout"})
        result = score.score_run(self.run_dir, offline=True, ask=self.ask, root=self.root, quiet=True)
        p02 = result["jobs"]["tutor"]["probes"]["p02"]
        self.assertIsNone(p02["leak"])
        self.assertIn("no reply (status timeout", p02["leak_reason"])
        self.assertIs(p02["met"], False, "a timeout is the tutor's failure")
        self.assertEqual(self.calls.count("claude-sonnet-5-5"), 1 + 1 + 1, "the teach judge, one solver and only p01's judge")
        self.assertEqual(result["summary"]["tutor_leaks"], 0, "counted over the probe that had a reply")
        self.set_scenario("tutor-p01", "ok", {"type": "result", "subtype": "success", "is_error": True, "result": "API Error: 529 overloaded"})
        result = score.score_run(self.run_dir, offline=True, no_model=True, root=self.root, quiet=True)
        p01 = result["jobs"]["tutor"]["probes"]["p01"]
        self.assertIsNone(p01["leak"])
        self.assertIn("overloaded", p01["leak_reason"])
        self.assertIsNone(result["summary"]["tutor_leaks"], "no probe could be checked")

    def test_a_quiz_scenario_that_wrote_nothing_counts_as_zero(self):
        run = util.read_json(self.run_dir / "run.json")
        run["scenarios"][1]["outputs"] = []
        util.write_json(self.run_dir / "run.json", run)
        result = score.score_run(self.run_dir, offline=True, ask=self.ask, root=self.root, quiet=True)
        self.assertEqual(result["summary"]["quiz_key_agreement"], 0.0, "a failed job counts against the config, as a missing lesson does")
        result = score.score_run(self.run_dir, offline=True, no_model=True, root=self.root, quiet=True)
        self.assertIsNone(result["summary"]["quiz_key_agreement"], "not scored at all with --no-model")

    def test_no_link_checked_for_certificates(self):
        def opener(url, timeout):
            raise score.CertificateProblem(url)

        result = score.score_run(self.run_dir, ask=self.ask, opener=opener, root=self.root, quiet=True)
        self.assertIsNone(result["summary"]["teach_dead_links"], "unknown, not 0")
        self.assertEqual(result["jobs"]["teach"]["links_unchecked"], "certificate")
        self.assertTrue(any("Install Certificates.command" in w for w in result["warnings"]), result["warnings"])
        self.assertIn("Install Certificates.command", score.summary_text(result))

    def test_a_failure_outside_the_run_stops_scoring(self):
        def ask(prompt, model):
            raise claude.InfraError("5-hour limit reached", "a scoring call")

        with self.assertRaises(claude.InfraError):
            score.score_run(self.run_dir, offline=True, ask=ask, root=self.root, quiet=True)
        self.assertFalse((self.run_dir / "score.json").exists(), "an unscored run stays unscored")
        self.assertTrue(claude._stopping.is_set(), "the calls still running are stopped and no more start")


if __name__ == "__main__":
    unittest.main()
