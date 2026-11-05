"""The Markdown report of scored runs (p3/report.py)."""

from __future__ import annotations

import unittest

from p3 import report, reviews, util
from p3.util import P3Error
from tests import RepoTestCase, review_md, write


def summary(**values) -> dict:
    base = {key: None for key, _, _ in report.QUALITY}
    base.update(values)
    cost = {"scenarios": 1, "tokens_total": 1000, "tokens_output": 100, "minutes": 2.0, "subagents": 0, "cost_usd_list": 0.5}
    base["cost"] = {job: dict(cost) for job in ("teach", "quiz", "grade", "tutor", "total")}
    return base


class CellTests(unittest.TestCase):
    def test_cells(self):
        self.assertEqual(report.cell([0.5, 0.7, 0.9], "share", 3), "0.70 (0.50-0.90)")
        self.assertEqual(report.cell([0.5], "share", 1), "0.50")
        self.assertEqual(report.cell([0.5, 0.5], "share", 2), "0.50")
        self.assertEqual(report.cell([1, None, 3], "count", 3), "2 (1-3, n=2)")
        self.assertEqual(report.cell([None, None], "share", 2), "-")
        self.assertEqual(report.cell([1500000, 500000], "tokens", 2), "1.00M (500.0k-1.50M)")
        self.assertEqual(report.cell([True], "count", 1), "-", "booleans are not numbers here")

    def test_config_order(self):
        names = ["zeta", "final", "final-minus-review", "c1-skills", "c0-baseline", "alpha", "c3-split", "c2-review"]
        self.assertEqual(report.config_order(names), ["c0-baseline", "c1-skills", "c2-review", "c3-split", "final", "final-minus-review", "alpha", "zeta"])


class ReportTests(RepoTestCase):
    def make_run(self, config, run_id, started, scored=True, quick=False, minutes=30, topic="agent-architecture", **values):
        folder = util.runs_dir(config, self.root) / run_id
        util.write_json(folder / "run.json", {"run_id": run_id, "config": config, "topic": topic, "minutes": minutes, "quick": quick, "started_at": started, "scenarios": []})
        if scored:
            util.write_json(folder / "score.json", {"run_id": run_id, "summary": summary(**values)})

    def setUp(self):
        super().setUp()
        self.make_run("final", "r3", "2026-11-20T10:00:00Z", teach_facts_correct=1.0, tutor_leaks=0)
        self.make_run("c0-baseline", "r1", "2026-11-03T10:00:00Z", teach_facts_correct=0.5, tutor_leaks=2, grade_false_wrong=0.25)
        self.make_run("c0-baseline", "r2", "2026-11-04T10:00:00Z", teach_facts_correct=0.75, tutor_leaks=1)
        self.make_run("c0-baseline", "r-quick", "2026-11-05T10:00:00Z", quick=True, teach_facts_correct=0.0)
        self.make_run("c0-baseline", "r-unscored", "2026-11-06T10:00:00Z", scored=False)
        self.make_run("c0-baseline", "r-other", "2026-11-06T10:00:00Z", topic="cooking", teach_facts_correct=0.1)

    def rows(self, text: str, heading: str) -> list[list[str]]:
        block = text.split(f"### {heading}\n", 1)[1].strip("\n").split("\n\n", 1)[0]
        lines = [line for line in block.splitlines() if line.startswith("|")]
        return [[c.strip() for c in line.strip("|").split("|")] for line in lines[2:]]

    def test_quality_table(self):
        text = report.report_text()
        self.assertIn("## Results on agent-architecture", text)
        rows = self.rows(text, "Quality")
        self.assertEqual([r[0] for r in rows], ["`c0-baseline`", "`final`"])
        base = rows[0]
        self.assertEqual(base[1], "2", "two full scored runs; the quick, unscored and other-topic runs are left out")
        self.assertEqual(base[2], "0.62 (0.50-0.75)")
        header = [label for _, label, _ in report.QUALITY]
        self.assertEqual(base[2 + header.index("leaks")], "1.5 (1-2)")
        self.assertEqual(base[2 + header.index("false wrong")], "0.25 (n=1)")
        self.assertEqual(base[2 + header.index("key agreement")], "-")
        self.assertEqual(rows[1][2], "1.00")

    def test_cost_tables(self):
        text = report.report_text()
        for job in ("teach", "quiz", "grade", "tutor"):
            self.assertIn(f"### Cost: {job}", text)
        self.assertIn("### Cost: all jobs", text)
        row = self.rows(text, "Cost: teach")[0]
        self.assertEqual(row, ["`c0-baseline`", "2", "1.0k", "100", "2.0", "0", "0.50"])
        self.assertIn("list-price equivalent, not what you pay on a subscription", text)
        self.assertIn("rough reading-time estimate", text)

    def test_filters(self):
        rows = self.rows(report.report_text(configs=["final", "c0-baseline"]), "Quality")
        self.assertEqual([r[0] for r in rows], ["`final`", "`c0-baseline`"])
        rows = self.rows(report.report_text(quick=True), "Quality")
        self.assertEqual([(r[0], r[1]) for r in rows], [("`c0-baseline`", "1")])
        rows = self.rows(report.report_text(topic_id="cooking"), "Quality")
        self.assertEqual(rows[0][2], "0.10")
        with self.assertRaises(P3Error):
            report.report_text(topic_id="knitting")

    def test_several_lengths_get_a_minutes_column(self):
        self.make_run("final", "r10", "2026-11-21T10:00:00Z", minutes=10, teach_facts_correct=0.9)
        text = report.report_text()
        self.assertIn("| config | minutes | runs |", text)
        rows = self.rows(text, "Quality")
        self.assertEqual([(r[0], r[1]) for r in rows], [("`c0-baseline`", "30"), ("`final`", "10"), ("`final`", "30")])
        rows = self.rows(report.report_text(minutes=10), "Quality")
        self.assertEqual(len(rows), 1)

    def test_command(self):
        code, out, err = self.p3("report", "--configs", "c0-baseline")
        self.assertEqual(code, 0, err)
        self.assertIn("`c0-baseline`", out)
        self.assertNotIn("`final`", out)
        code, _, err = self.p3("report", "--topic", "knitting")
        self.assertEqual(code, 1)
        self.assertIn("no scored full runs", err)

    def test_only_quick_runs_says_so(self):
        self.make_run("c1-skills", "q1", "2026-11-07T10:00:00Z", quick=True, teach_facts_correct=0.5)
        with self.assertRaisesRegex(P3Error, r"only quick runs are scored so far \(c1-skills\): add --quick"):
            report.report_text(configs=["c1-skills"])
        self.assertIn("`c1-skills`", report.report_text(configs=["c1-skills"], quick=True))


class ReportFromBenchTests(RepoTestCase):
    def test_a_real_run(self):
        code, out, err = self.p3("bench", "--config", "c0-baseline", "--offline")
        self.assertEqual(code, 0, err + out)
        code, out, err = self.p3("report")
        self.assertEqual(code, 0, err)
        row = next(line for line in out.splitlines() if line.startswith("| `c0-baseline`"))
        self.assertIn("| 0.75 |", row)
        self.assertIn("| 0.50 |", row, "grade verdict agreement")


class RunKindTests(RepoTestCase):
    """Runs made with --only never mix into the full runs' rows; --teach-only shows the length study's."""

    def make_run(self, config, run_id, started, jobs, only=None, **values):
        folder = util.runs_dir(config, self.root) / run_id
        scenarios = [{"id": job, "job": job} for job in jobs]
        util.write_json(folder / "run.json", {"run_id": run_id, "config": config, "topic": "agent-architecture", "minutes": 30, "quick": False, "started_at": started, "only": only, "scenarios": scenarios})
        data = summary(**values)
        for job in ("teach", "quiz", "grade", "tutor"):
            if job not in jobs:
                data["cost"][job] = {"scenarios": 0, "tokens_total": 0, "tokens_output": 0, "minutes": 0, "subagents": 0, "cost_usd_list": None}
        util.write_json(folder / "score.json", {"run_id": run_id, "summary": data})

    def setUp(self):
        super().setUp()
        everything = ["teach", "quiz", "grade", "tutor"]
        self.make_run("final", "full1", "2026-11-20T10:00:00Z", everything, teach_facts_correct=1.0, tutor_leaks=0)
        self.make_run("final", "study1", "2026-11-21T10:00:00Z", ["teach"], only=["teach"], teach_facts_correct=0.2)
        self.make_run("final", "probe1", "2026-11-21T11:00:00Z", ["tutor"], only=["tutor-p01"], tutor_leaks=5)
        self.make_run("c1-skills", "study2", "2026-11-22T10:00:00Z", ["teach"], only=["teach"], teach_facts_correct=0.4)

    def rows(self, text, heading):
        return ReportTests.rows(self, text, heading)

    def test_only_full_runs_by_default(self):
        text = report.report_text()
        (final,) = self.rows(text, "Quality")
        header = [label for _, label, _ in report.QUALITY]
        self.assertEqual(final[:3], ["`final`", "1", "1.00"], "the teach-only and the one-probe runs are left out")
        self.assertEqual(final[2 + header.index("leaks")], "0")
        self.assertEqual(self.rows(text, "Cost: quiz")[0][1], "1", "so a job a partial run never ran is not averaged in as zero")
        self.assertIn("wrong keys", text)

    def test_teach_only(self):
        text = report.report_text(teach_only=True)
        self.assertEqual([(r[0], r[1], r[2]) for r in self.rows(text, "Quality")], [("`c1-skills`", "1", "0.40"), ("`final`", "1", "0.20")])
        self.assertNotIn("| leaks", text, "only the teach checks")
        self.assertNotIn("### Cost: quiz", text)
        with self.assertRaisesRegex(P3Error, "only teach-only runs are scored so far \\(c1-skills\\): add --teach-only"):
            report.report_text(configs=["c1-skills"])
        code, out, err = self.p3("report", "--teach-only", "--configs", "final")
        self.assertEqual(code, 0, err)
        self.assertIn("Scored teach-only runs", out)


class RatingsTests(RepoTestCase):
    """"Your ratings": the major reviews' ratings, one row per criterion, one column per step."""

    def review(self, step: str, text: str) -> None:
        write(self.root / reviews.step_file(step), text)

    def table_rows(self, text: str) -> list[list[str]]:
        block = text.split("## Your ratings\n", 1)[1]
        lines = [line for line in block.splitlines() if line.startswith("|")]
        return [[c.strip() for c in line.strip("|").split("|")] for line in lines]

    def test_the_table(self):
        self.review("c1-skills", review_md("c1-skills", ratings={(reviews.LESSON, "Pedagogy"): 2, (reviews.TUTOR, "Guardrails"): "5/5"}))
        self.review("c3-split", review_md("c3-split", ratings={(reviews.LESSON, "Pedagogy"): 5, (reviews.LESSON, "Overall quality"): 6}))
        self.review("final", review_md("final", todo=True))
        text = report.ratings_table()
        self.assertTrue(text.startswith("## Your ratings\n\n"), text)
        rows = self.table_rows(text)
        self.assertEqual(rows[0], ["job", "criterion", "c1-skills", "c2-review", "c3-split", "final"])
        self.assertEqual(rows[1], ["---", "---", "---:", "---:", "---:", "---:"])
        body = rows[2:]
        self.assertEqual(len(body), sum(len(c) for c in reviews.CRITERIA.values()))
        self.assertEqual([r[0] for r in body], [job for job, names in reviews.CRITERIA.items() for _ in names], "grouped by job, in order")
        by = {(r[0], r[1]): r[2:] for r in body}
        self.assertEqual(by[(reviews.LESSON, "Technical correctness and facts")], ["4", "-", "4", "-"])
        self.assertEqual(by[(reviews.LESSON, "Pedagogy")], ["2", "-", "5", "-"])
        self.assertEqual(by[(reviews.LESSON, "Overall quality")], ["4", "-", "-", "-"], "a rating p3 check rejects is a dash")
        self.assertEqual(by[(reviews.QUIZ, "Coverage of the lesson's core")], ["4", "-", "-", "-"], "c3-split reviews the lesson only")
        self.assertEqual(by[(reviews.TUTOR, "Guardrails")], ["5", "-", "-", "-"])

    def test_after_the_tables_and_alone(self):
        ReportTests.make_run(self, "c0-baseline", "r1", "2026-11-03T10:00:00Z", teach_facts_correct=0.5)
        self.assertNotIn("Your ratings", report.report_text(), "no rating yet, no table")
        self.review("c1-skills", review_md("c1-skills"))
        code, out, err = self.p3("report")
        self.assertEqual(code, 0, err)
        self.assertLess(out.index("Costs are per run"), out.index("## Your ratings"))
        self.assertTrue(out.endswith("|\n"), repr(out[-40:]))
        self.assertNotIn("Your ratings", report.report_text(ratings=False))
        code, out, err = self.p3("report", "--reviews")
        self.assertEqual(code, 0, err)
        self.assertTrue(out.startswith("## Your ratings\n"), out)
        self.assertNotIn("## Results", out)
        self.assertEqual(len(self.table_rows(out)), 2 + 14)

    def test_only_under_the_shared_topics_full_runs(self):
        """The major reviews review full runs on the shared topic, so a report of a test topic, of quick
        runs or of the length study's teach-only runs leaves the ratings out."""
        ReportTests.make_run(self, "c0-baseline", "r1", "2026-11-03T10:00:00Z", teach_facts_correct=0.5)
        ReportTests.make_run(self, "c0-baseline", "r-quick", "2026-11-03T11:00:00Z", quick=True, teach_facts_correct=0.5)
        ReportTests.make_run(self, "c0-baseline", "r-cook", "2026-11-03T12:00:00Z", topic="cooking", teach_facts_correct=0.5)
        teach_only = util.runs_dir("c0-baseline", self.root) / "r-teach"
        util.write_json(teach_only / "run.json", {
            "run_id": "r-teach", "config": "c0-baseline", "topic": "agent-architecture", "minutes": 10, "quick": False,
            "started_at": "2026-11-03T13:00:00Z", "only": ["teach"], "scenarios": [{"id": "teach", "job": "teach"}],
        })  # fmt: skip
        util.write_json(teach_only / "score.json", {"run_id": "r-teach", "summary": summary(teach_facts_correct=0.5)})
        self.review("c1-skills", review_md("c1-skills"))
        self.assertIn("## Your ratings", report.report_text())
        self.assertIn("## Your ratings", report.report_text(configs=["c0-baseline"]), "EVAL.md pastes p3 report --configs a,b with the ratings")
        for kwargs in ({"topic_id": "cooking"}, {"quick": True}, {"teach_only": True}):
            self.assertNotIn("Your ratings", report.report_text(**kwargs), kwargs)
        self.assertIn("or a job that step does not review (Tutor in c2-review; Quiz, Feedback and Tutor in c3-split)", report.ratings_table())

    def test_no_ratings_yet(self):
        self.assertIsNone(report.ratings_table())
        self.review("c2-review", review_md("c2-review", todo=True))
        self.assertIsNone(report.ratings_table())
        code, out, err = self.p3("report", "--reviews")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("no ratings in reviews/ yet: each criterion of a major review (reviews/<step>.md) holds a line Rating: N", err)


if __name__ == "__main__":
    unittest.main()
