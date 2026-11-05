"""Loading and validating topic folders (p3/topic.py)."""

from __future__ import annotations

import copy
import json
import shutil
import unittest

from p3 import topic, util
from p3.util import P3Error
from tests import KEY_0001, PROBES, TOPIC, RepoTestCase, write, write_topic


class TopicTests(RepoTestCase):
    def shared(self):
        return self.root / "bench" / "topics" / "agent-architecture"

    def edit(self, rel: str, change) -> None:
        path = self.shared() / rel
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        write(path, data)

    def errors(self, folder=None, kind=None) -> list[str]:
        return topic.validate(folder or self.shared(), kind).errors

    def assertError(self, fragment: str, folder=None, kind=None):
        errors = self.errors(folder, kind)
        self.assertTrue(any(fragment in e for e in errors), f"no error with {fragment!r} in {errors}")

    def test_the_fixture_is_valid(self):
        v = topic.validate(self.shared())
        self.assertEqual(v.errors, [])
        self.assertEqual(v.todos, [])
        self.assertTrue(v.ok(allow_todo=False))

    def test_load_and_accessors(self):
        tp = topic.load("agent-architecture", self.root)
        self.assertEqual(tp.kind, topic.SHARED)
        self.assertEqual(tp.teach_objective, "O3")
        self.assertEqual(tp.objective_text("O2"), "Tell a workflow from an agent.")
        self.assertEqual([f["id"] for f in tp.facts_for("O3")], ["F3.1", "F3.2", "F3.3", "F3.4"])
        self.assertEqual(tp.submissions, ["s1", "s2"])
        self.assertEqual(tp.key("0001")["items"][0]["answer"], "b")
        self.assertEqual(tp.submission("s2")["learner"], "Ari")
        self.assertEqual(tp.true_grades("s1")[0]["misconception"], "M1")
        self.assertEqual(tp.probe("p02")["leak_check"], {"quiz": "0001", "item": "q1"})
        self.assertIsNone(tp.probe("p99"))
        self.assertEqual(tp.hash(), util.hash_tree(self.shared()))
        self.assertEqual(tp.rel_path(self.root), "bench/topics/agent-architecture")
        self.assertEqual(tp.minutes, 30)

    def test_lookup_order_and_missing(self):
        write_topic(self.root / "bench" / "own" / "cooking")
        self.assertEqual(topic.topic_dir("cooking", self.root)[1], topic.OWN)
        write_topic(self.root / "bench" / "own" / "agent-architecture")
        self.assertEqual(topic.topic_dir("agent-architecture", self.root)[1], topic.SHARED)
        with self.assertRaises(P3Error) as cm:
            topic.topic_dir("knitting", self.root)
        self.assertIn("bench/own/knitting", str(cm.exception))
        with self.assertRaises(P3Error):
            topic.topic_dir("../etc", self.root)
        self.assertEqual([t[0] for t in topic.list_topics(self.root)], ["agent-architecture", "agent-architecture", "cooking"])

    def test_duplicate_ids(self):
        self.edit("topic.json", lambda d: d["objectives"].append({"id": "O1", "text": "again"}))
        self.assertError("id O1 is used twice")

    def test_fact_with_unknown_objective(self):
        self.edit("topic.json", lambda d: d["facts"].append({"id": "F9.1", "objective": "O9", "text": "x"}))
        self.assertError("fact F9.1 names objective O9")

    def test_teach_and_quiz_objectives_exist(self):
        self.edit("topic.json", lambda d: d.update(teach_objective="O7", quiz_objective="O8"))
        self.assertError("teach_objective 'O7'")
        self.assertError("quiz_objective 'O8'")

    def test_item_objective_exists(self):
        self.edit("workspace/quizzes/0001.json", lambda d: d["items"][0].update(objective="O9"))
        self.assertError("objective O9 does not exist")

    def test_key_and_quiz_agree(self):
        self.edit("workspace/keys/0001.json", lambda d: d["items"].pop())
        self.assertError("differ from the quiz's")

    def test_submission_agrees(self):
        self.edit("workspace/submissions/s2.json", lambda d: d["answers"].append({"id": "q9", "response": "?"}))
        self.assertError("workspace/submissions/s2.json: its answer ids")

    def test_missing_submission(self):
        (self.shared() / "workspace" / "submissions" / "s2.json").unlink()
        self.assertError("workspace/submissions/s2.json is missing")

    def test_grading_agrees(self):
        self.edit("grading.json", lambda d: d["submissions"].pop("s2"))
        self.assertError("grading.json: it grades")
        self.edit("grading.json", lambda d: d["submissions"].update(s2=[{"id": "q1", "verdict": "maybe", "misconception": None, "why": "x"}]))
        self.assertError("verdict must be one of")
        self.assertError("grading.json s2: its item ids")

    def test_misconceptions_must_exist(self):
        self.edit("grading.json", lambda d: d["submissions"]["s1"][0].update(misconception="M9"))
        self.assertError("misconception 'M9' does not exist")
        self.edit("workspace/keys/0001.json", lambda d: d["items"][0].update(distractors={"a": "M7"}))
        self.assertError("names misconception 'M7'")

    def test_key_answers_fit_the_item_types(self):
        def change(d):
            d["items"][0]["answer"] = "z"
            d["items"][1]["answer"] = "three"
            d["items"][2]["answer"] = ""

        self.edit("workspace/keys/0001.json", change)
        self.assertError("not one of the item's option ids")
        self.assertError("numeric item's answer must be a number")
        self.assertError("short item's answer must be a non-empty string")

    def test_leak_check_targets_exist(self):
        self.edit("probes.json", lambda d: d["probes"][0].update(leak_check={"quiz": "0001", "item": "q9"}))
        self.assertError("names item q9")
        self.edit("probes.json", lambda d: d["probes"][0].update(leak_check={"quiz": "0009", "item": "q1"}))
        self.assertError("names quiz 0009")

    def test_minimums_for_shared_topics(self):
        self.edit("topic.json", lambda d: d.update(facts=[f for f in d["facts"] if f["id"] != "F3.4"]))
        self.assertError("at least 4 facts")
        self.edit("probes.json", lambda d: d["probes"].pop())
        self.assertError("at least 6 probes")

    def test_minimums_for_own_topics(self):
        own = self.root / "bench" / "own" / "cooking"
        meta = copy.deepcopy(TOPIC)
        meta["facts"] = [f for f in meta["facts"] if f["id"] != "F3.4"]
        write_topic(own, meta)
        probes = copy.deepcopy(PROBES)
        probes["probes"] = probes["probes"][:4]
        write(own / "probes.json", probes)
        self.assertEqual(topic.validate(own).errors, [], "3 facts and 4 probes are enough for an own topic")
        probes["probes"] = probes["probes"][:3]
        write(own / "probes.json", probes)
        self.assertError("at least 4 probes", own)
        meta["facts"] = meta["facts"][:3]
        write(own / "topic.json", {**meta, "id": "cooking"})
        self.assertError("at least 3 facts", own)

    def test_id_must_match_the_folder(self):
        self.edit("topic.json", lambda d: d.update(id="other"))
        self.assertError("id must be 'agent-architecture'")

    def test_workspace_must_not_hold_config_files(self):
        write(self.shared() / "workspace" / "CLAUDE.md", "no")
        write(self.shared() / "workspace" / ".claude" / "settings.json", {})
        self.assertError("workspace/CLAUDE.md must not exist")
        self.assertError("workspace/.claude must not exist")

    def test_missing_and_broken_files(self):
        (self.shared() / "probes.json").unlink()
        (self.shared() / "grading.json").write_text("{", encoding="utf-8")
        self.assertError("probes.json is missing")
        self.assertError("grading.json:")
        shutil.rmtree(self.shared() / "workspace")
        self.assertError("workspace/ is missing")

    def test_broken_topic_json_stops_early(self):
        (self.shared() / "topic.json").write_text("[1]", encoding="utf-8")
        self.assertError("topic.json must hold a JSON object")

    def test_todos_are_reported(self):
        write(self.shared() / "workspace" / "NOTES.md", "TODO: fill in\nTODO again\n")
        self.edit("topic.json", lambda d: d.update(title="TODO: a title"))
        v = topic.validate(self.shared())
        self.assertEqual(v.errors, [])
        self.assertEqual(len(v.todos), 2)
        self.assertTrue(any("workspace/NOTES.md: 2 TODO markers" in t for t in v.todos))
        self.assertTrue(v.ok())
        self.assertFalse(v.ok(allow_todo=False))
        self.assertTrue(any(line.startswith("todo: ") for line in v.lines()))

    def test_key_fixture_is_untouched_by_tests(self):
        self.assertEqual(KEY_0001["items"][0]["answer"], "b")


class FileIdTests(RepoTestCase):
    def shared(self):
        return self.root / "bench" / "topics" / "agent-architecture"

    def edit(self, rel, change):
        TopicTests.edit(self, rel, change)

    def errors(self):
        return topic.validate(self.shared()).errors

    def test_ids_that_become_file_names(self):
        self.edit("probes.json", lambda d: d["probes"][0].update(id="p1?"))
        self.edit("topic.json", lambda d: d.update(submissions=["s1", "why/how"]))
        errors = self.errors()
        self.assertTrue(any("probe id 'p1?' becomes a folder name" in e for e in errors), errors)
        self.assertTrue(any("submission id 'why/how' becomes a file name" in e for e in errors), errors)

    def test_quiz_item_ids_too(self):
        def rename(d):
            d["items"][0]["id"] = "q 1"

        self.edit("workspace/quizzes/0001.json", rename)
        self.assertTrue(any("item q 1: the item id becomes part of names" in e for e in self.errors()), self.errors())

    def test_text_that_is_not_utf8(self):
        (self.shared() / "workspace" / "NOTES.md").write_bytes("Caf\xe9 notes\r\n".encode("cp1252"))
        self.assertTrue(any("workspace/NOTES.md is not UTF-8" in e for e in self.errors()), self.errors())


if __name__ == "__main__":
    unittest.main()
