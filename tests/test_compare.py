"""The blind comparison (p3/compare.py): pairing, blinding, the records, the pages, terminal mode,
the sign test and the reveal. The run folders are written directly (see make_run), except in
EndToEndTests, which benches two configs against tests/fake_claude.py first."""

from __future__ import annotations

import contextlib
import http.client
import io
import re
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from p3 import compare, config, topic, util
from p3.util import P3Error
from tests import RepoTestCase, write

T0 = datetime(2026, 11, 3, 14, 0, 0, tzinfo=timezone.utc)
MARKERS = {}


def add_config(root: Path, name: str, skills=("teach",), hook: bool = False) -> dict:
    """Shape tutor/ as a config with these skills (and a PreToolUse hook), then snapshot it as `name`."""
    tutor = root / "tutor"
    for skill in ("teach", "tutor", "quiz", "grade"):
        path = tutor / ".claude" / "skills" / skill / "SKILL.md"
        if skill in skills:
            write(path, f"---\nname: {skill}\n---\n\nThe {skill} skill of {name}.\n")
        elif path.exists():
            util.remove_tree(path.parent)
    settings = {"permissions": {"allow": ["WebSearch", "WebFetch"]}}
    if hook:
        settings["hooks"] = {"PreToolUse": [{"matcher": "Read|Grep|Glob|Bash", "hooks": [{"type": "command", "command": "python .claude/hooks/guard.py"}]}]}
    write(tutor / ".claude" / "settings.json", settings)
    write(tutor / "CLAUDE.md", f"# Tutor\n\nYou are a tutor ({name}).\n")
    return config.snapshot(name, force=True, root=root)


def scenario_ids(tp: topic.Topic, quick: bool = False) -> list[str]:
    subs = tp.submissions[:1] if quick else tp.submissions
    probes = [p["id"] for p in tp.probes][: 2 if quick else None]
    return ["teach", "quiz"] + [f"grade-{s}" for s in subs] + [f"tutor-{p}" for p in probes]


def make_run(
    root: Path, cfg: str, run_id: str, started: str, *, topic_id: str = "agent-architecture", minutes: int = 30,
    quick: bool = False, scenarios: list[str] | None = None, scored: bool = True, marker: str | None = None,
    tokens: int = 1000, topic_commit: str | None = None, only=None, summary: dict | None = None,
) -> Path:
    """Write a complete run folder (run.json, outputs, result.json files and score.json) as p3 bench
    and p3 score would leave it; every text the tutor wrote carries `marker`."""
    marker = marker or MARKERS.get(cfg) or f"{cfg.upper()}-MADE"
    tp = topic.load(topic_id, root)
    folder = util.runs_dir(cfg, root) / run_id
    entries = []
    items = [i["id"] for i in tp.quiz(tp.graded_quiz)["items"]]
    for sid in scenarios or scenario_ids(tp, quick):
        job = sid.split("-")[0]
        out = folder / sid / "outputs"
        entry = {
            "id": sid, "job": job, "entry": "/teach", "status": "ok", "duration_ms": 120000, "num_turns": 4,
            "tokens": {"input": 10, "output": 100, "cache_read": tokens - 110, "cache_write": 0}, "cost_usd_list": 0.05,
            "web_searches": 0, "web_fetches": 0, "subagents": {"spawned": 1, "max_depth": 1, "by_type": {"reviewer": 1}},
            "permission_denials": [], "outputs": [], "changed": [],
        }  # fmt: skip
        reply = "Done."
        if job == "teach":
            write(out / "lessons" / "0001-context.html", f"<!doctype html><html><head><meta charset=\"utf-8\"><title>Lesson</title></head><body><h1>{marker} lesson</h1><img src=\"../assets/fig.svg\" alt=\"\"></body></html>\n")
            write(out / "assets" / "fig.svg", "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"10\" height=\"10\"></svg>\n")
            entry["outputs"] = ["assets/fig.svg", "lessons/0001-context.html"]
        elif job == "quiz":
            write(out / "quizzes" / "0002.json", {"id": "0002", "objective": "O2", "title": f"{marker} quiz", "items": [
                {"id": "q1", "type": "mcq", "objective": "O2", "stem": "Who owns the control flow in a workflow?", "options": [{"id": "a", "text": "The model"}, {"id": "b", "text": "The program"}]},
                {"id": "q2", "type": "numeric", "objective": "O2", "stem": "How many steps?", "unit": "steps"},
            ]})  # fmt: skip
            write(out / "keys" / "0002.json", {"id": "0002", "items": [
                {"id": "q1", "answer": "b", "rationale": f"{marker} rationale", "distractors": {"a": "M1"}},
                {"id": "q2", "answer": 3, "tolerance": 0, "rationale": "Three."},
            ]})  # fmt: skip
            entry["outputs"] = ["keys/0002.json", "quizzes/0002.json"]
        elif job == "grade":
            sub = sid.removeprefix("grade-")
            entry["submission"] = sub
            grades = [{"id": iid, "verdict": "correct" if n % 2 else "wrong", "misconception": None if n % 2 else "M1", "feedback": f"{marker} feedback on {sub} {iid}"} for n, iid in enumerate(items)]
            write(out / "grades" / f"0001-{sub}.json", {"quiz": "0001", "submission": sub, "items": grades, "summary": "ok"})
            entry["outputs"] = [f"grades/0001-{sub}.json"]
        elif job == "tutor":
            entry["probe"] = sid.removeprefix("tutor-")
            reply = f"{marker} reply to {entry['probe']}: **think** about the loop."
        write(folder / sid / "result.json", {"type": "result", "is_error": False, "result": reply})
        entries.append(entry)
    run = {
        "run_id": run_id, "config": cfg, "config_hash": util.load_snapshot(cfg, root)["hash"], "topic": topic_id,
        "topic_hash": tp.hash(), "topic_commit": topic_commit, "repeat": 1, "minutes": minutes, "quick": quick,
        "started_at": started, "finished_at": started, "claude_version": "2.1.314 (Claude Code)", "p3_version": "0.1.0",
        "platform": "test", "model": "sonnet", "allowed_tools": [], "only": only, "scenarios": entries,
    }  # fmt: skip
    write(folder / "run.json", run)
    if scored:
        values = {
            "teach_facts_correct": 0.75, "teach_misconceptions": 0, "teach_length_ratio": 1.0, "teach_dead_links": 0,
            "quiz_key_agreement": 1.0, "quiz_ambiguous": 0, "grade_verdict_agreement": 0.5, "grade_false_wrong": 0.25,
            "grade_misconception_hit": 1.0, "tutor_leaks": 0, "tutor_behavior_met": 1.0, "cost": {},
        }  # fmt: skip
        values.update(summary or {})
        jobs = {
            "teach": {"lesson": "lessons/0001-context.html"},
            "quiz": {"quiz": "quizzes/0002.json", "key": "keys/0002.json"},
            "grade": {"submissions": {s: {"grades": f"grades/0001-{s}.json"} for s in tp.submissions}},
        }
        write(folder / "score.json", {"run_id": run_id, "scored_at": started, "jobs": jobs, "summary": values})
    return folder


def stamp(minutes: int) -> str:
    return util.iso_utc(T0 + timedelta(minutes=minutes))


class CompareTestCase(RepoTestCase):
    """A repo with c0-baseline and c1-skills, three scored full runs of c0-baseline and two of
    c1-skills on the shared topic, plus runs the comparison must leave out."""

    def setUp(self):
        super().setUp()
        MARKERS.update({"c0-baseline": "ALPHA", "c1-skills": "BETA"})
        add_config(self.root, "c1-skills", skills=("teach", "tutor", "quiz", "grade"))
        for k in range(3):
            make_run(self.root, "c0-baseline", f"runA{k + 1}", stamp(10 * k), tokens=1000)
        for k in range(2):
            make_run(self.root, "c1-skills", f"runB{k + 1}", stamp(10 * k + 5), tokens=3000)
        make_run(self.root, "c1-skills", "runB-quick", stamp(1), quick=True)
        make_run(self.root, "c1-skills", "runB-unscored", stamp(2), scored=False)
        make_run(self.root, "c1-skills", "runB-m10", stamp(3), minutes=10)

    def session(self, job: str, seed: int = 7, when=None) -> compare.Session:
        record = compare.new_session("c0-baseline", "c1-skills", job, seed=seed, root=self.root, when=when or T0)
        return compare.Session(record["session"], self.root)


class PairingTests(CompareTestCase):
    def test_pairs_by_repeat_order(self):
        s = self.session("teach")
        self.assertEqual([p["run_pair"] for p in s.pairs], [["runA1", "runB1"], ["runA2", "runB2"]], "oldest first, min(nA, nB) run pairs")
        self.assertEqual([p["item"] for p in s.pairs], ["teach", "teach"])
        self.assertEqual([p["pair_id"] for p in s.pairs], ["001", "002"])

    def test_items_per_job(self):
        quiz = self.session("quiz", when=T0)
        self.assertEqual([p["item"] for p in quiz.pairs], ["quiz", "quiz"])
        grade = self.session("grade", when=T0 + timedelta(seconds=1))
        self.assertEqual(len(grade.pairs), 2 * 2 * 3, "one pair per item per submission per run pair")
        self.assertEqual([p["item"] for p in grade.pairs[:4]], ["grade-s1/q1", "grade-s1/q2", "grade-s1/q3", "grade-s2/q1"])
        tutor = self.session("tutor", when=T0 + timedelta(seconds=2))
        self.assertEqual(len(tutor.pairs), 2 * 6)
        self.assertEqual(tutor.pairs[0]["item"], "tutor-p01")
        self.assertEqual(tutor.pairs[6]["run_pair"], ["runA2", "runB2"])

    def test_runs_of_some_scenarios_are_never_paired(self):
        """A run made with --only, even the oldest, never takes a full run's place in the repeat order."""
        make_run(self.root, "c0-baseline", "runA-only", stamp(-5), scenarios=["teach", "tutor-p01"], only=["teach", "tutor-p01"])
        s = self.session("tutor")
        self.assertEqual([p["run_pair"] for p in s.pairs[::6]], [["runA1", "runB1"], ["runA2", "runB2"]])
        self.assertNotIn("runA-only", {p["run_pair"][0] for p in s.pairs})
        recs = compare.runs_for("c0-baseline", "agent-architecture", "tutor", 30, False, self.root)
        self.assertNotIn("runA-only", [r.dir.name for r in recs])

    def test_teach_only_runs_pair_only_with_teach_only(self):
        """The length study's runs: --teach-only pairs them, and nothing else does."""
        make_run(self.root, "c0-baseline", "runA-study", stamp(40), scenarios=["teach"], only=["teach"])
        make_run(self.root, "c1-skills", "runB-study1", stamp(41), scenarios=["teach"], only=["teach"])
        make_run(self.root, "c1-skills", "runB-study2", stamp(42), scenarios=["teach"], only=["teach"])
        full = self.session("teach")
        self.assertEqual([p["run_pair"] for p in full.pairs], [["runA1", "runB1"], ["runA2", "runB2"]], "the study's runs are not full runs")
        record = compare.new_session("c0-baseline", "c1-skills", "teach", teach_only=True, seed=1, root=self.root, when=T0 + timedelta(seconds=5))
        self.assertEqual([p["run_pair"] for p in record["pairs"]], [["runA-study", "runB-study1"]])
        self.assertTrue(record["teach_only"])
        with self.assertRaises(P3Error) as cm:
            compare.new_session("c0-baseline", "c1-skills", "quiz", teach_only=True, root=self.root, when=T0 + timedelta(seconds=6))
        self.assertIn("--job teach", str(cm.exception))
        add_config(self.root, "c2-review", skills=("teach",))
        make_run(self.root, "c2-review", "runC-study", stamp(43), scenarios=["teach"], only=["teach"])
        with self.assertRaises(P3Error) as cm:
            compare.new_session("c0-baseline", "c2-review", "teach", root=self.root, when=T0 + timedelta(seconds=7))
        self.assertIn("add --teach-only", str(cm.exception), "the refusal points at the runs that do exist")

    def test_refuses_without_scored_runs(self):
        add_config(self.root, "c2-review", skills=("teach",))
        make_run(self.root, "c2-review", "c-unscored", stamp(50), scored=False)
        with self.assertRaises(P3Error) as cm:
            compare.new_session("c0-baseline", "c2-review", "teach", root=self.root)
        message = str(cm.exception)
        self.assertIn("c2-review has no scored full run on agent-architecture", message)
        self.assertIn("p3 score bench/runs/c2-review/c-unscored", message)
        self.assertFalse(list(compare.compare_dir(self.root).glob("*.json")), "nothing is written when it refuses")

    def test_refusal_names_quick_and_other_lengths(self):
        add_config(self.root, "c3-split", skills=("teach",))
        make_run(self.root, "c3-split", "q", stamp(60), quick=True)
        make_run(self.root, "c3-split", "m60", stamp(61), minutes=60)
        with self.assertRaises(P3Error) as cm:
            compare.new_session("c0-baseline", "c3-split", "grade", root=self.root)
        self.assertIn("1 scored quick run", str(cm.exception))
        self.assertIn("at 60 minutes", str(cm.exception))
        with self.assertRaises(P3Error):
            compare.new_session("c0-baseline", "c3-split", "teach", minutes=60, root=self.root)  # c0-baseline has no 60-minute run
        record = compare.new_session("c1-skills", "c3-split", "teach", quick=True, root=self.root, when=T0)
        self.assertEqual(record["pairs"][0]["run_pair"], ["runB-quick", "q"])
        self.assertTrue(record["quick"])

    def test_refusals(self):
        for a, b, job, needle in (
            ("c0-baseline", "c0-baseline", "teach", "two different configs"),
            ("c0-baseline", "live", "teach", "live runs are not committed"),
            ("c0-baseline", "nope", "teach", "no config named 'nope'"),
            ("c0-baseline", "c1-skills", "lecture", "--job must be one of"),
        ):
            with self.assertRaises(P3Error) as cm:
                compare.new_session(a, b, job, root=self.root)
            self.assertIn(needle, str(cm.exception))


class BlindingTests(unittest.TestCase):
    CONFIGS = ["c0-baseline", "c1-skills"]
    IDS = [f"{i:03d}" for i in range(1, 11)]

    def test_the_same_seed_gives_the_same_sides(self):
        self.assertEqual(compare.assign_sides(self.IDS, self.CONFIGS, 99), compare.assign_sides(self.IDS, self.CONFIGS, 99))

    def test_pinned_sides(self):
        sides = compare.assign_sides(self.IDS, self.CONFIGS, 12345)
        self.assertEqual("".join("A" if v["left"] == "c0-baseline" else "B" for v in sides.values()), "AABAAABAAA")

    def test_each_pair_shows_both_configs(self):
        for v in compare.assign_sides(self.IDS, self.CONFIGS, 3).values():
            self.assertEqual(sorted(v.values()), self.CONFIGS)

    def test_seeds_differ_and_sides_balance(self):
        ids = [f"{i:03d}" for i in range(1, 401)]
        a = compare.assign_sides(ids, self.CONFIGS, 1)
        b = compare.assign_sides(ids, self.CONFIGS, 2)
        self.assertNotEqual(a, b)
        lefts = sum(1 for v in a.values() if v["left"] == "c0-baseline")
        self.assertTrue(150 < lefts < 250, lefts)


class SignTestTests(unittest.TestCase):
    def test_exact_two_sided_values(self):
        self.assertAlmostEqual(compare.sign_test(8, 2), 0.109375)
        self.assertAlmostEqual(compare.sign_test(9, 1), 0.021484375)
        self.assertAlmostEqual(compare.sign_test(8, 1), 0.0390625)
        self.assertAlmostEqual(compare.sign_test(3, 0), 0.25)
        self.assertAlmostEqual(compare.sign_test(10, 0), 0.001953125)
        self.assertEqual(compare.sign_test(5, 5), 1.0)
        self.assertEqual(compare.sign_test(6, 4), 0.75390625)
        self.assertEqual(compare.sign_test(0, 0), 1.0)

    def test_symmetric(self):
        for a in range(0, 12):
            for b in range(0, 12):
                self.assertEqual(compare.sign_test(a, b), compare.sign_test(b, a))
                self.assertLessEqual(compare.sign_test(a, b), 1.0)

    def test_format(self):
        self.assertEqual(compare.fmt_p(0.109375), "0.11")
        self.assertEqual(compare.fmt_p(0.021484375), "0.02")
        self.assertEqual(compare.fmt_p(0.001953125), "0.002")
        self.assertEqual(compare.fmt_p(1e-7), "< 0.001")


class RecordTests(CompareTestCase):
    def test_the_two_files(self):
        record = compare.new_session("c0-baseline", "c1-skills", "grade", seed=42, root=self.root, when=T0)
        sid = record["session"]
        self.assertEqual(sid, "20261103-140000-grade")
        saved = util.read_json(compare.session_path(sid, self.root))
        self.assertEqual(saved, record)
        for key in ("session", "job", "topic", "configs", "created_at", "pairs", "picks", "complete"):
            self.assertIn(key, saved)
        self.assertEqual(saved["configs"], ["c0-baseline", "c1-skills"])
        self.assertEqual(saved["created_at"], "2026-11-03T14:00:00Z")
        self.assertEqual((saved["picks"], saved["complete"]), ([], False))
        self.assertEqual(set(saved["pairs"][0]), {"pair_id", "run_pair", "item"})
        key = util.read_json(compare.key_path(sid, self.root))
        self.assertEqual(key["seed"], 42)
        self.assertEqual(key["pairs"], compare.assign_sides([p["pair_id"] for p in saved["pairs"]], saved["configs"], 42))
        text = compare.session_path(sid, self.root).read_text(encoding="utf-8")
        self.assertNotIn('"left"', text, "the session file never holds the mapping")
        self.assertNotIn('"seed"', text)

    def test_session_ids(self):
        self.assertEqual(compare.session_id("bench/compare/20261103-140000-teach.json"), "20261103-140000-teach")
        self.assertEqual(compare.session_id("20261103-140000-teach.key.json"), "20261103-140000-teach")
        self.assertEqual(compare.session_id("../../etc"), "etc", "only the file name is used, so no path can leave bench/compare/")
        with self.assertRaises(P3Error):
            compare.session_id("not an id!")
        compare.new_session("c0-baseline", "c1-skills", "teach", root=self.root, when=T0)
        with self.assertRaises(P3Error):
            compare.new_session("c0-baseline", "c1-skills", "teach", root=self.root, when=T0)

    def test_picks_are_saved_at_once(self):
        s = self.session("teach")
        s.record("001", "left", "  Clearer\n examples. ", False)
        on_disk = util.read_json(s.path)
        self.assertEqual(len(on_disk["picks"]), 1)
        pick = on_disk["picks"][0]
        self.assertEqual({k: pick[k] for k in ("pair_id", "choice", "reason", "could_tell")}, {"pair_id": "001", "choice": "left", "reason": "Clearer examples.", "could_tell": False})
        self.assertFalse(on_disk["complete"])
        s.record("001", "tie", "On second look, the same.", True)
        self.assertEqual([(p["pair_id"], p["choice"]) for p in util.read_json(s.path)["picks"]], [("001", "tie")], "a second answer replaces the first")
        s.record("002", "right", "Shorter.", True)
        self.assertTrue(util.read_json(s.path)["complete"])
        self.assertIsNone(s.next_open())

    def test_bad_picks_are_refused(self):
        s = self.session("teach")
        for args in (("009", "left", "x", True), ("001", "both", "x", True), ("001", "left", "   ", True), ("001", "left", "x", "yes")):
            with self.assertRaises(P3Error):
                s.record(*args)
        self.assertEqual(util.read_json(s.path)["picks"], [])

    def test_a_missing_key_or_run_is_reported(self):
        s = self.session("teach")
        util.remove_tree(util.runs_dir("c1-skills", self.root) / "runB2")
        with self.assertRaises(P3Error) as cm:
            compare.Session(s.id, self.root)
        self.assertIn("bench/runs/c1-skills/runB2", str(cm.exception))
        s.key_path.unlink()
        with self.assertRaises(P3Error) as cm:
            compare.Session(s.id, self.root)
        self.assertIn("key file", str(cm.exception))


class RevealTests(CompareTestCase):
    def finish(self, s: compare.Session, picks: list[tuple[str, str, bool]]) -> None:
        for pair, (choice, reason, tell) in zip(s.pairs, picks):
            s.record(pair["pair_id"], choice, reason, tell)

    def test_an_unfinished_session_is_not_revealed(self):
        s = self.session("tutor")
        s.record("001", "left", "Warmer.", False)
        with self.assertRaises(P3Error) as cm:
            compare.reveal(s.id, self.root)
        self.assertIn("11 of 12 pairs have no pick yet", str(cm.exception))
        self.assertNotIn("revealed", util.read_json(s.path))

    def test_tally_order_and_record(self):
        s = self.session("tutor", seed=12345)
        side = s.key["pairs"]
        # pick c1-skills nine times, c0-baseline twice, and one tie
        wanted = ["c1-skills"] * 9 + ["c0-baseline"] * 2 + [None]
        picks = []
        for n, (pair, winner) in enumerate(zip(s.pairs, wanted)):
            choice = "tie" if winner is None else ("left" if side[pair["pair_id"]]["left"] == winner else "right")
            picks.append((choice, f"reason {n + 1} for {winner or 'tie'}", n < 3))
        self.finish(s, picks)
        text, record = compare.reveal(s.id, self.root)
        self.assertEqual(record["wins"], {"c0-baseline": 2, "c1-skills": 9})
        self.assertEqual((record["ties"], record["non_tie"]), (1, 11))
        self.assertAlmostEqual(record["p_value"], round(compare.sign_test(9, 2), 6))
        self.assertEqual(record["could_tell"], {"yes": 3, "pairs": 12, "share": 0.25})
        self.assertEqual(len(record["reasons"]["c1-skills"]), 9)
        self.assertTrue(all("for c1-skills" in r["reason"] for r in record["reasons"]["c1-skills"]))
        self.assertTrue(all("for c0-baseline" in r["reason"] for r in record["reasons"]["c0-baseline"]))
        self.assertEqual(record["reasons"]["tie"][0]["item"], "tutor-p06")

        # quality first, then cost
        order = ["### Tally", "### Sign test", "### Could you tell", "### Reasons, by the config that won", "### Objective checks (tutor)", "### Cost per tutor scenario"]
        positions = [text.index(h) for h in order]
        self.assertEqual(positions, sorted(positions), text)
        self.assertIn("`c0-baseline` won 2, `c1-skills` won 9, and 1 was a tie.", text)
        self.assertIn("9 of the 11 non-tie picks went to `c1-skills`; the exact two-sided sign-test p-value is 0.07.", text)
        self.assertIn(compare.READING_LINE, text)
        self.assertIn("You could tell which config made which in 3 of 12 pairs (25%).", text)
        self.assertLess(text.index("reason 1 for c1-skills"), text.index("### Objective checks"))
        self.assertNotIn("tokens", text[: text.index("### Cost per")])
        cost = text[text.index("### Cost per tutor scenario"):]
        self.assertIn("| `c0-baseline` | 2 | 12 | 1.0k | 100 | 2.0 | 1 | 0.05 |", cost)
        self.assertIn("| `c1-skills` | 2 | 12 | 3.0k | 100 | 2.0 | 1 | 0.05 |", cost)
        self.assertIn("`c1-skills` used 3.0x the tokens and 1.0x the minutes of `c0-baseline`", cost)
        self.assertIn("list-price equivalent, not what you pay on a subscription", cost)
        checks = text[text.index("### Objective checks"): text.index("### Cost per")]
        self.assertIn("| answer leaks | 0 | 0 |", checks)
        self.assertIn("| expected behavior met (share) | 1.00 | 1.00 |", checks)

        saved = util.read_json(s.path)["revealed"]
        self.assertEqual(saved["wins"], record["wins"])
        first = saved["revealed_at"]
        _text, again = compare.reveal(s.id, self.root)
        self.assertEqual(again["revealed_at"], first, "a second reveal keeps the first time")
        with self.assertRaises(P3Error):
            compare.Session(s.id, self.root).record("001", "left", "changed my mind", False)

    def test_few_pairs_say_so(self):
        s = self.session("teach")
        self.finish(s, [("left" if s.key["pairs"][p["pair_id"]]["left"] == "c1-skills" else "right", "Better.", False) for p in s.pairs])
        text, record = compare.reveal(s.id, self.root)
        self.assertIn("no split can reach 0.05", text)
        self.assertEqual(record["p_value"], 0.5)
        self.assertIn("| facts present and correct (share) | 0.75 | 0.75 |", text)

    def test_all_ties(self):
        s = self.session("teach")
        self.finish(s, [("tie", "same", False), ("tie", "same", True)])
        text, record = compare.reveal(s.id, self.root)
        self.assertIn("Every pick was a tie", text)
        self.assertEqual(record["p_value"], 1.0)


class PageTests(CompareTestCase):
    def app(self, job: str, seed: int = 12345) -> compare.CompareApp:
        return compare.CompareApp(self.session(job, seed=seed), token="tok")

    def form(self, **fields) -> bytes:
        from urllib.parse import urlencode

        return urlencode({"token": "tok", **fields}).encode()

    def test_flow(self):
        app = self.app("tutor")
        s = app.s
        r = app.handle("GET", "/")
        self.assertEqual((r.status, dict(r.headers)["Location"]), (303, "/pair/1"))
        r = app.handle("GET", "/pair/1")
        self.assertEqual(r.status, 200)
        body = r.body.decode()
        self.assertIn("Pair 1 of 12", body)
        self.assertIn(">Left<", body)
        self.assertIn(">Right<", body)
        for secret in ("c0-baseline", "c1-skills", "runA", "runB", "bench/runs", "key.json"):
            self.assertNotIn(secret, body, f"the page must not show {secret}")
        left = s.key["pairs"]["001"]["left"]
        marker = MARKERS[left]
        self.assertLess(body.index(">Left<"), body.index(f"{marker} reply to p01"))
        self.assertLess(body.index(f"{marker} reply to p01"), body.index(">Right<"), "the left config's reply is in the left column")
        self.assertIn("<strong>think</strong>", body)
        self.assertIn("What is the answer to q3 on quiz 0001?", body, "the probe's message is shown")

        r = app.handle("POST", "/pair/1", self.form(pair_id="001", choice="left", reason="  ", could_tell="no"))
        self.assertEqual(r.status, 400)
        self.assertIn("Say why, in one sentence.", r.body.decode())
        r = app.handle("POST", "/pair/1", self.form(pair_id="001", choice="left", reason="Warmer.", could_tell="no", token="wrong"))
        self.assertEqual(r.status, 403)
        self.assertEqual(util.read_json(s.path)["picks"], [])

        r = app.handle("POST", "/pair/1", self.form(pair_id="001", choice="left", reason="Warmer <b>tone</b>.", could_tell="no"))
        self.assertEqual((r.status, dict(r.headers)["Location"]), (303, "/pair/2"))
        self.assertEqual(util.read_json(s.path)["picks"][0]["reason"], "Warmer <b>tone</b>.")
        again = app.handle("GET", "/pair/1").body.decode()
        self.assertIn("Warmer &lt;b&gt;tone&lt;/b&gt;.", again, "a saved answer is shown escaped")
        self.assertIn('value="left" required checked', again)
        for k in range(2, 13):
            r = app.handle("POST", f"/pair/{k}", self.form(pair_id=f"{k:03d}", choice="tie", reason="Same.", could_tell="yes"))
        self.assertEqual(dict(r.headers)["Location"], "/done")
        self.assertTrue(app.finished.is_set())
        done = app.handle("GET", "/done")
        self.assertIn(f"p3 compare --reveal {s.id}", done.body.decode())
        self.assertTrue(util.read_json(s.path)["complete"])
        self.assertEqual(app.handle("GET", "/pair/13").status, 404)
        self.assertEqual(app.handle("GET", "/pair/x").status, 404)

    def test_lessons_are_framed_from_the_run_outputs(self):
        app = self.app("teach")
        body = app.handle("GET", "/pair/1").body.decode()
        self.assertEqual(body.count('<iframe class="frame" src="/frame/1/'), 2)
        self.assertIn('sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox"', body)
        left = app.s.key["pairs"]["001"]["left"]
        r = app.handle("GET", "/frame/1/left/lessons/0001-context.html")
        self.assertEqual(r.status, 200)
        self.assertIn(f"{MARKERS[left]} lesson", r.body.decode())
        headers = dict(r.headers)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("sandbox", headers["Content-Security-Policy"])
        self.assertEqual(app.handle("GET", "/frame/1/right/assets/fig.svg").status, 200, "relative assets work")
        self.assertEqual(app.handle("GET", "/frame/1/left/MISSION.md").status, 200, "the starting workspace is the fallback")
        for bad in (
            "/frame/1/left/../run.json", "/frame/1/left/%2e%2e/%2e%2e/run.json", "/frame/1/left/..%2f..%2frun.json",
            "/frame/1/left/lessons%5c..%5c..%5crun.json", "/frame/1/up/lessons/0001-context.html", "/frame/9/left/lessons/0001-context.html",
            f"/frame/1/left/{'%2e%2e/' * 6}bench/compare/{app.s.id}.key.json", "/frame/1/left/C:/Windows/win.ini",
        ):  # fmt: skip
            self.assertEqual(app.handle("GET", bad).status, 404, bad)
        self.assertEqual(self.app("tutor").handle("GET", "/frame/1/left/result.json").status, 404, "frames are for lessons only")

    def test_quiz_and_grade_pages(self):
        quiz = self.app("quiz").handle("GET", "/pair/1").body.decode()
        self.assertIn("ALPHA quiz", quiz)
        self.assertIn("BETA quiz", quiz)
        self.assertIn('<span class="tag key">key</span>', quiz)
        self.assertIn("M1: The model runs the tools itself.", quiz, "a distractor's misconception is named")
        self.assertIn("<b>Key:</b> 3 steps (exact)", quiz)
        app = compare.CompareApp(self.session("grade", when=T0 + timedelta(seconds=5)), token="tok")
        grade = app.handle("GET", "/pair/1").body.decode()
        self.assertIn("Quiz 0001 · item q1 · multiple choice · submission s1", grade)
        self.assertIn("a (The model itself)", grade, "the learner's mcq answer with its text")
        self.assertIn("Answer key", grade)
        self.assertEqual(grade.count('<div class="verdict wrong">wrong</div>'), 2)
        self.assertIn("feedback on s1 q1", grade)

    def test_a_missing_output_is_shown_as_missing(self):
        s = self.session("teach")
        left = s.key["pairs"]["001"]["left"]
        run = util.runs_dir(left, self.root) / s.pairs[0]["run_pair"][s.configs.index(left)]
        (run / "teach" / "outputs" / "lessons" / "0001-context.html").unlink()
        body = compare.CompareApp(compare.Session(s.id, self.root), token="t").handle("GET", "/pair/1").body.decode()
        self.assertIn("This version wrote no lesson.", body)
        self.assertEqual(body.count("<iframe"), 1)


class ServerTests(CompareTestCase):
    def test_starting_the_server_looks_up_no_host_name(self):
        """socket.getfqdn is a reverse DNS query, which can take many seconds on a Mac."""
        app = compare.CompareApp(self.session("teach"))
        with mock.patch("socket.getfqdn", side_effect=AssertionError("getfqdn was called")):
            server = compare.make_server(app, 0)
        server.server_close()
        self.assertEqual(server.server_port, app.port)

    def test_over_http(self):
        app = compare.CompareApp(self.session("teach"))
        server = compare.make_server(app, 0)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        try:
            port = app.port

            def request(method, path, body=None, host=None):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                headers = {"Content-Type": "application/x-www-form-urlencoded"} if body else {}
                if host:
                    headers["Host"] = host
                conn.request(method, path, body=body, headers=headers)
                resp = conn.getresponse()
                data = resp.read()
                conn.close()
                return resp, data

            resp, _ = request("GET", "/")
            self.assertEqual((resp.status, resp.getheader("Location")), (303, "/pair/1"))
            resp, data = request("GET", "/pair/1")
            self.assertEqual(resp.status, 200)
            self.assertIn("default-src 'none'", resp.getheader("Content-Security-Policy"))
            token = re.search(r'name="token" value="([^"]+)"', data.decode()).group(1)
            resp, _ = request("POST", "/pair/1", f"token={token}&pair_id=001&choice=right&reason=Clearer.&could_tell=no".encode())
            self.assertEqual((resp.status, resp.getheader("Location")), (303, "/pair/2"))
            self.assertEqual(util.read_json(app.s.path)["picks"][0]["choice"], "right")
            resp, _ = request("GET", "/pair/1", host="evil.example:80")
            self.assertEqual(resp.status, 421, "a request for another host is refused")
            resp, _ = request("GET", "/frame/1/left/lessons/0001-context.html")
            self.assertEqual(resp.status, 200)
        finally:
            server.shutdown()
            server.server_close()

    def test_a_port_in_use(self):
        app = compare.CompareApp(self.session("teach"))
        first = compare.make_server(app, 0)
        try:
            with self.assertRaises(P3Error) as cm:
                compare.make_server(compare.CompareApp(self.session("quiz")), first.server_address[1])
            self.assertIn("--port", str(cm.exception))
        finally:
            first.server_close()


class TerminalTests(CompareTestCase):
    def test_answers_on_stdin(self):
        s = self.session("teach")
        answers = iter(["x", "l", "", "More examples.", "maybe", "n", "tie", "Both fine.", "yes"])
        folder = Path(self._tmp) / "pairs"
        code = terminal_run(s, answers, folder)
        self.assertEqual(code, 0)
        picks = util.read_json(s.path)["picks"]
        self.assertEqual([(p["choice"], p["reason"], p["could_tell"]) for p in picks], [("left", "More examples.", False), ("tie", "Both fine.", True)])
        page = (folder / "pair-001.html").read_text(encoding="utf-8")
        self.assertIn("Pair 1 of 2", page)
        self.assertIn('src="pair-001/left/lessons/0001-context.html"', page)
        self.assertIn("Answer the three questions in the terminal.", page)
        self.assertNotIn("<form", page)
        self.assertTrue((folder / "pair-001" / "left" / "lessons" / "0001-context.html").is_file())
        self.assertTrue((folder / "pair-001" / "right" / "assets" / "fig.svg").is_file())
        for name in s.configs:
            self.assertNotIn(name, page)

    def test_stopping_saves_and_resume_continues(self):
        s = self.session("tutor")
        out = terminal_output(s, iter(["r", "Kinder.", "y"]), Path(self._tmp) / "t1")
        self.assertIn("1 of 12 pairs answered, all saved. Continue with: p3 compare --resume", out)
        self.assertEqual(len(util.read_json(s.path)["picks"]), 1)
        again = compare.Session(s.id, self.root)
        self.assertEqual(again.next_open(), 2)
        answers = iter(["l", "Clearer.", "n"] * 11)
        terminal_run(again, answers, Path(self._tmp) / "t2")
        self.assertTrue(util.read_json(s.path)["complete"])


def terminal_run(s, answers, folder) -> int:
    import contextlib
    import io

    def ask(_prompt):
        try:
            return next(answers)
        except StopIteration:
            raise EOFError from None

    with contextlib.redirect_stdout(io.StringIO()):
        return compare.terminal(s, ask=ask, folder=folder)


def terminal_output(s, answers, folder) -> str:
    import contextlib
    import io

    def ask(_prompt):
        try:
            return next(answers)
        except StopIteration:
            raise EOFError from None

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        compare.terminal(s, ask=ask, folder=folder)
    return buf.getvalue()


class CommandTests(CompareTestCase):
    def test_terminal_session_then_reveal_and_list(self):
        answers = iter(["l", "Clearer.", "n"] * 2)
        with mock.patch("builtins.input", side_effect=lambda _p="": next(answers)), mock.patch("p3.compare.tempfile.mkdtemp", return_value=str(Path(self._tmp) / "cli")):
            code, out, err = self.p3("compare", "c0-baseline", "c1-skills", "--job", "teach", "--terminal")
        self.assertEqual(code, 0, err + out)
        sid = re.search(r"session (\d{8}-\d{6}-teach)", out).group(1)
        self.assertIn("2 pairs from 2 pairs of runs", out)
        self.assertIn("do not open it before the reveal", out)
        self.assertIn(f"All 2 pairs are answered. See which config was which: p3 compare --reveal {sid}", out)
        code, out, err = self.p3("compare", "--list")
        self.assertEqual(code, 0, err)
        self.assertRegex(out, rf"{sid}\s+teach\s+agent-architecture\s+c0-baseline / c1-skills\s+2/2\s+complete")
        code, out, err = self.p3("compare", "--resume", sid)
        self.assertIn("is complete", out)
        code, out, err = self.p3("compare", "--reveal", sid)
        self.assertEqual(code, 0, err)
        self.assertIn("### Tally", out)
        code, out, err = self.p3("compare", "--list")
        self.assertIn("revealed", out)
        code, out, err = self.p3("compare", "--resume", sid)
        self.assertIn("has been revealed", out)

    def test_usage_errors(self):
        code, _out, err = self.p3("compare", "c0-baseline")
        self.assertEqual(code, 1)
        self.assertIn("give the two configs", err)
        code, _out, err = self.p3("compare", "c0-baseline", "c1-skills")
        self.assertIn("--job is required", err)
        code, _out, err = self.p3("compare", "--list", "--reveal", "x")
        self.assertIn("one at a time", err)
        code, _out, err = self.p3("compare", "--reveal", "20990101-000000-teach")
        self.assertIn("there is no session", err)
        code, out, _err = self.p3("compare", "--list")
        self.assertIn("No comparison sessions yet", out)

    def test_server_mode_runs_until_done(self):
        """serve() with no browser: answer every pair over HTTP from another thread, and it returns."""
        s = self.session("teach")
        real_make_server = compare.make_server
        workers, errors = [], []

        def answer(app):
            try:
                for k in (1, 2):
                    conn = http.client.HTTPConnection("127.0.0.1", app.port, timeout=10)
                    conn.request("POST", f"/pair/{k}", body=f"token={app.token}&pair_id={k:03d}&choice=left&reason=Fine.&could_tell=no", headers={"Content-Type": "application/x-www-form-urlencoded"})
                    conn.getresponse().read()
                    conn.close()
            except Exception as exc:  # fail the test, rather than leave serve() waiting for answers forever
                errors.append(exc)
                app.finished.set()

        def spy(app, port=None):
            # the server listens once it is made, so the answers can start then, however long that took
            server = real_make_server(app, port)
            workers.append(threading.Thread(target=answer, args=(app,), daemon=True))
            workers[-1].start()
            return server

        buf = io.StringIO()
        with mock.patch("p3.compare.make_server", spy), mock.patch("p3.compare.DONE_GRACE_S", 0), contextlib.redirect_stdout(buf):
            code = compare.serve(s, open_browser=False)
        for worker in workers:
            worker.join(10)
        self.assertEqual(errors, [])
        self.assertEqual(code, 0)
        self.assertIn("All 2 pairs are answered", buf.getvalue())
        self.assertTrue(util.read_json(s.path)["complete"])


class MarkdownTests(unittest.TestCase):
    def test_everything_is_escaped(self):
        out = compare.md('<script>alert("x")</script> and <img src=x onerror=alert(1)>')
        self.assertNotIn("<script", out)
        self.assertNotIn("<img", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertNotIn("javascript:", compare.md("[click](javascript:alert(1))").replace("[click](javascript:alert(1))", ""))
        self.assertNotIn("<a ", compare.md("[click](javascript:alert(1))"))
        self.assertNotIn('" onmouseover', compare.md('[x](https://e.com/" onmouseover="alert(1))'))

    def test_inline(self):
        self.assertEqual(compare.inline("**bold**, *it*, `a < b`"), "<strong>bold</strong>, <em>it</em>, <code>a &lt; b</code>")
        self.assertEqual(compare.inline("2 * 3 * 4"), "2 * 3 * 4")
        self.assertIn('<a href="https://example.com/a_b_c" target="_blank" rel="noopener noreferrer">ref</a>', compare.inline("[ref](https://example.com/a_b_c)"))
        self.assertIn('href="https://example.com/x"', compare.inline("see https://example.com/x."))
        self.assertTrue(compare.inline("see https://example.com/x.").endswith("</a>."))
        self.assertEqual(compare.inline("snake_case_name"), "snake_case_name")

    def test_blocks(self):
        out = compare.md("# Title\n\nFirst line\nsecond line\n\n- one\n- two\n\n1. a\n2. b\n\n> quoted\n\n```\nx = 1 < 2\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |")
        self.assertIn("<h3>Title</h3>", out)
        self.assertIn("<p>First line<br>second line</p>", out)
        self.assertIn("<ul><li>one</li><li>two</li></ul>", out)
        self.assertIn("<ol><li>a</li><li>b</li></ol>", out)
        self.assertIn("<blockquote><p>quoted</p></blockquote>", out)
        self.assertIn("<pre><code>x = 1 &lt; 2</code></pre>", out)
        self.assertIn("<thead><tr><th>a</th><th>b</th></tr></thead><tbody><tr><td>1</td><td>2</td></tr></tbody>", out)
        self.assertEqual(compare.md(""), "")
        self.assertEqual(compare.md(None), "")


class EndToEndTests(RepoTestCase):
    """Bench two configs against the fake claude, compare their grades in the terminal, reveal,
    and check that p3 check accepts the records."""

    def test_bench_compare_reveal_check(self):
        add_config(self.root, "c1-skills", skills=("teach", "tutor", "quiz", "grade"))
        for name in ("c0-baseline", "c1-skills"):
            code, out, err = self.p3("bench", "--config", name, "--offline", "--jobs", "4")
            self.assertEqual(code, 0, err + out)
        answers = iter(["r", "It names the misconception.", "n"] * 6)
        with mock.patch("builtins.input", side_effect=lambda _p="": next(answers)), mock.patch("p3.compare.tempfile.mkdtemp", return_value=str(Path(self._tmp) / "e2e")):
            code, out, err = self.p3("compare", "c0-baseline", "c1-skills", "--job", "grade", "--terminal")
        self.assertEqual(code, 0, err + out)
        self.assertIn("6 pairs from 1 pair of runs", out)
        page = (Path(self._tmp) / "e2e" / "pair-001.html").read_text(encoding="utf-8")
        self.assertIn("The program runs the tool, not the model.", page, "the fake grader's feedback is shown")
        self.assertIn("Learner's answer", page)
        sid = re.search(r"session (\d{8}-\d{6}-grade)", out).group(1)
        code, out, err = self.p3("compare", "--reveal", sid)
        self.assertEqual(code, 0, err)
        self.assertIn("ties", out.split("### Sign test")[0])
        self.assertIn("| verdict agreement |", out)
        self.assertIn("### Cost per grade scenario", out)
        util.rehash(self.root)
        code, out, err = self.p3("check")
        self.assertEqual(code, 0, out + err)
        self.assertIn("bench/compare/: 1 comparison session, each with its key, existing configs and runs", out)


class ServerErrorTests(CompareTestCase):
    def test_a_dropped_connection_is_quiet_and_anything_else_one_line(self):
        app = compare.CompareApp(self.session("teach"))
        server = compare.make_server(app, 0)
        try:
            for exc, quiet in ((ConnectionResetError(10054, "reset"), True), (BrokenPipeError(32, "pipe"), True), (ValueError("odd"), False)):
                err = io.StringIO()
                try:
                    raise exc
                except Exception:
                    with contextlib.redirect_stderr(err):
                        server.handle_error(None, ("127.0.0.1", 1))
                self.assertEqual(err.getvalue() == "", quiet, err.getvalue())
                self.assertNotIn("Traceback", err.getvalue())
        finally:
            server.server_close()

    def test_a_pick_that_cannot_be_saved_says_so(self):
        app = compare.CompareApp(self.session("teach"))
        server = compare.make_server(app, 0)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", app.port, timeout=10)
            with mock.patch.object(app.s, "record", side_effect=PermissionError(13, "Permission denied")):
                conn.request("POST", "/pair/1", body=f"token={app.token}&pair_id=001&choice=left&reason=Clear.&could_tell=no".encode(), headers={"Content-Type": "application/x-www-form-urlencoded"})
                resp = conn.getresponse()
                body = resp.read().decode()
            conn.close()
            self.assertEqual(resp.status, 503)
            self.assertIn("could not be saved", body)
            self.assertEqual(util.read_json(app.s.path)["picks"], [])
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
