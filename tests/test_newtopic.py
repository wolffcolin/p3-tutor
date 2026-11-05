"""The skeleton own topic (p3/newtopic.py)."""

from __future__ import annotations

import json
import unittest

from p3 import newtopic, topic, util
from p3.util import P3Error
from tests import RepoTestCase, git, git_init, has_git


class NewTopicTests(RepoTestCase):
    def test_skeleton_has_every_file_and_validates_with_todos(self):
        folder = newtopic.create("statics-trusses", self.root)
        self.assertEqual(folder, self.root / "bench" / "own" / "statics-trusses")
        files = util.list_files(folder)
        for rel in (
            "topic.json", "grading.json", "probes.json", "workspace/MISSION.md", "workspace/NOTES.md",
            "workspace/quizzes/0001.json", "workspace/keys/0001.json", "workspace/submissions/s1.json",
        ):  # fmt: skip
            self.assertIn(rel, files)
        self.assertTrue(any(f.startswith("workspace/learning-records/0001-") for f in files))
        v = topic.validate(folder)
        self.assertEqual(v.errors, [], "the skeleton is well formed")
        self.assertGreaterEqual(len(v.todos), 8, "every file has placeholders")
        self.assertFalse(v.ok(allow_todo=False))
        meta = util.read_json(folder / "topic.json")
        self.assertEqual(meta["id"], "statics-trusses")
        self.assertEqual(len(util.read_json(folder / "probes.json")["probes"]), topic.MIN_PROBES[topic.OWN])

    def test_json_files_are_plain_json_with_lf(self):
        folder = newtopic.create("cooking", self.root)
        for rel in util.list_files(folder):
            raw = (folder / rel).read_bytes()
            self.assertNotIn(b"\r\n", raw, rel)
            if rel.endswith(".json"):
                json.loads(raw.decode("utf-8"))
                self.assertNotIn(b"//", raw.replace(b"https://", b""), "no comments in JSON")

    def test_filled_in_it_is_valid_without_todos(self):
        folder = newtopic.create("cooking", self.root)
        for rel in util.list_files(folder):
            path = folder / rel
            path.write_text(path.read_text(encoding="utf-8").replace("TODO", "Done"), encoding="utf-8")
        v = topic.validate(folder)
        self.assertEqual((v.errors, v.todos), ([], []))

    def test_refusals(self):
        newtopic.create("cooking", self.root)
        with self.assertRaises(P3Error) as cm:
            newtopic.create("cooking", self.root)
        self.assertIn("already exists", str(cm.exception))
        with self.assertRaises(P3Error) as cm:
            newtopic.create("agent-architecture", self.root)
        self.assertIn("shared topic", str(cm.exception))
        for bad in ("Cooking", "a b", "", "-x", "../x"):
            with self.assertRaises(P3Error, msg=bad):
                newtopic.create(bad, self.root)

    def test_command(self):
        code, out, err = self.p3("new-topic", "knots")
        self.assertEqual(code, 0, err)
        self.assertIn("wrote bench/own/knots/", out)
        self.assertIn("TODO", out)
        code, _, err = self.p3("new-topic", "knots")
        self.assertEqual(code, 1)
        self.assertIn("already exists", err)

    @unittest.skipUnless(has_git(), "git is not installed")
    def test_the_bench_refuses_a_skeleton_even_when_committed(self):
        newtopic.create("knots", self.root)
        git_init(self.root)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "skeleton")
        code, _, err = self.p3("bench", "--config", "c0-baseline", "--topic", "knots", "--quick")
        self.assertEqual(code, 1)
        self.assertIn("TODO markers", err)


if __name__ == "__main__":
    unittest.main()
