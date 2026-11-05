"""Snapshots, their validation, entry resolution, allowed tools and the model (p3/config.py)."""

from __future__ import annotations

import unittest

from p3 import config, util
from p3.util import P3Error
from tests import RepoTestCase, write


class SnapshotTests(RepoTestCase):
    snapshot = False

    def test_snapshot_copies_the_config_only(self):
        data = config.snapshot("c0-baseline", root=self.root)
        folder = self.root / "configs" / "c0-baseline"
        self.assertEqual(data["files"], [".claude/settings.json", ".claude/skills/teach/SKILL.md", "CLAUDE.md", "PREFERENCES.md"])
        for rel in data["files"]:
            self.assertEqual((folder / rel).read_bytes(), (self.root / "tutor" / rel).read_bytes())
        self.assertFalse((folder / "MISSION.md").exists(), "learner files are not part of a config")
        self.assertFalse((folder / "FORMATS.md").exists())
        saved = util.read_json(folder / "SNAPSHOT.json")
        self.assertEqual(set(saved), {"name", "hash", "created_at", "files"})
        self.assertEqual(saved["name"], "c0-baseline")
        self.assertEqual(saved["hash"], util.config_hash(self.root / "tutor"))
        self.assertIsNotNone(util.parse_iso(saved["created_at"]))
        self.assertTrue(saved["created_at"].endswith("Z"))

    def test_snapshot_refuses_to_overwrite_without_force(self):
        config.snapshot("c1-skills", root=self.root)
        with self.assertRaises(P3Error) as cm:
            config.snapshot("c1-skills", root=self.root)
        self.assertIn("--force", str(cm.exception))

    def test_force_replaces_the_whole_snapshot(self):
        write(self.root / "tutor" / ".claude" / "agents" / "old.md", "old")
        config.snapshot("c1-skills", root=self.root)
        (self.root / "tutor" / ".claude" / "agents" / "old.md").unlink()
        write(self.root / "tutor" / ".claude" / "skills" / "quiz" / "SKILL.md", "quiz")
        data = config.snapshot("c1-skills", force=True, root=self.root)
        folder = self.root / "configs" / "c1-skills"
        self.assertFalse((folder / ".claude" / "agents" / "old.md").exists())
        self.assertTrue((folder / ".claude" / "skills" / "quiz" / "SKILL.md").exists())
        self.assertIn(".claude/skills/quiz/SKILL.md", data["files"])
        self.assertTrue(config.verify_snapshot("c1-skills", self.root)[0])

    def test_names(self):
        for good in ("c0-baseline", "final", "final-minus-review", "a", "9x"):
            self.assertEqual(config.check_name(good), good)
        for bad in ("", "-x", "C1", "has space", "a_b", "x" * 42, "live", "../up", "c1/skills"):
            with self.assertRaises(P3Error, msg=bad):
                config.check_name(bad)

    def test_tampering_is_detected(self):
        config.snapshot("c1-skills", root=self.root)
        ok, recorded, actual = config.verify_snapshot("c1-skills", self.root)
        self.assertTrue(ok)
        self.assertEqual(recorded, actual)
        write(self.root / "configs" / "c1-skills" / "CLAUDE.md", "edited by hand")
        ok, recorded, actual = config.verify_snapshot("c1-skills", self.root)
        self.assertFalse(ok)
        with self.assertRaises(P3Error) as cm:
            config.resolve("c1-skills", self.root)
        self.assertIn("no longer matches", str(cm.exception))

    def test_line_endings_are_not_tampering(self):
        config.snapshot("c1-skills", root=self.root)
        path = self.root / "configs" / "c1-skills" / "CLAUDE.md"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        self.assertTrue(config.verify_snapshot("c1-skills", self.root)[0])

    def test_learner_files_in_a_snapshot_do_not_count(self):
        config.snapshot("c1-skills", root=self.root)
        write(self.root / "configs" / "c1-skills" / "NOTES.md", "a learner file")
        self.assertTrue(config.verify_snapshot("c1-skills", self.root)[0])

    def test_missing_snapshot(self):
        with self.assertRaises(P3Error) as cm:
            config.resolve("c9-nothing", self.root)
        self.assertIn("p3 snapshot c9-nothing", str(cm.exception))
        (self.root / "configs" / "broken").mkdir(parents=True)
        with self.assertRaises(P3Error):
            config.load_snapshot("broken", self.root)

    def test_list_configs(self):
        config.snapshot("c1-skills", root=self.root)
        config.snapshot("c0-baseline", root=self.root)
        (self.root / "configs" / "not-a-snapshot").mkdir()
        self.assertEqual(config.list_configs(self.root), ["c0-baseline", "c1-skills"])

    def test_snapshot_command(self):
        code, out, err = self.p3("snapshot", "c1-skills")
        self.assertEqual(code, 0, err)
        self.assertIn("configs/c1-skills/", out)
        code, _, err = self.p3("snapshot", "c1-skills")
        self.assertEqual(code, 1)
        self.assertIn("--force", err)
        code, _, err = self.p3("snapshot", "c1-skills", "--force")
        self.assertEqual(code, 0, err)
        code, _, err = self.p3("snapshot", "Bad_Name")
        self.assertEqual(code, 1)
        self.assertIn("not a valid config name", err)

    def test_empty_tutor(self):
        import shutil

        shutil.rmtree(self.root / "tutor")
        (self.root / "tutor").mkdir()
        with self.assertRaises(P3Error):
            config.snapshot("c1-skills", root=self.root)


class ResolutionTests(RepoTestCase):
    def test_baseline_routes_every_job_to_teach(self):
        cfg = config.resolve("c0-baseline", self.root)
        self.assertEqual(cfg.entries, {"teach": "/teach", "tutor": "/teach", "quiz": "/teach", "grade": "/teach"})
        self.assertFalse(cfg.live)

    def test_each_skill_gets_its_own_entry(self):
        tutor = self.root / "tutor"
        write(tutor / ".claude" / "skills" / "quiz" / "SKILL.md", "quiz")
        write(tutor / ".claude" / "skills" / "grade" / "notes.md", "a folder without SKILL.md is not a skill")
        write(tutor / ".claude" / "skills" / "tutor" / "SKILL.md", "tutor")
        self.assertEqual(config.entries(tutor), {"teach": "/teach", "tutor": "/tutor", "quiz": "/quiz", "grade": "/teach"})

    def test_allowed_tools(self):
        tutor = self.root / "tutor"
        self.assertEqual(config.allowed_tools(tutor), ["WebSearch", "WebFetch"])
        write(tutor / ".claude" / "settings.json", {"permissions": {"allow": ["Read", "Bash(git status:*)", 7, ""], "deny": ["Bash"]}})
        self.assertEqual(config.allowed_tools(tutor), ["Read", "Bash(git status:*)"])
        write(tutor / ".claude" / "settings.json", {"hooks": {}})
        self.assertEqual(config.allowed_tools(tutor), [])
        (tutor / ".claude" / "settings.json").unlink()
        self.assertEqual(config.allowed_tools(tutor), [])
        self.assertEqual(config.settings(tutor), {})

    def test_model(self):
        tutor = self.root / "tutor"
        self.assertEqual(config.model(tutor), "sonnet")
        write(tutor / ".claude" / "settings.json", {"model": "claude-opus-5-5"})
        self.assertEqual(config.model(tutor), "claude-opus-5-5")
        write(tutor / ".claude" / "settings.json", {"model": ""})
        self.assertEqual(config.model(tutor), "sonnet")

    def test_broken_settings(self):
        (self.root / "tutor" / ".claude" / "settings.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(P3Error):
            config.resolve("live", self.root)
        write(self.root / "tutor" / ".claude" / "settings.json", [1, 2])
        with self.assertRaises(P3Error):
            config.allowed_tools(self.root / "tutor")

    def test_live(self):
        cfg = config.resolve("live", self.root)
        self.assertTrue(cfg.live)
        self.assertEqual(cfg.folder, self.root / "tutor")
        self.assertEqual(cfg.hash, util.config_hash(self.root / "tutor"))
        self.assertNotIn("MISSION.md", cfg.files)

    def test_reexports(self):
        self.assertIs(config.config_hash, util.config_hash)
        self.assertIs(config.config_files, util.config_files)
        self.assertIs(config.load_snapshot, util.load_snapshot)


class EncodingTests(RepoTestCase):
    snapshot = False

    def test_a_file_that_is_not_utf8_is_refused(self):
        (self.root / "tutor" / "PREFERENCES.md").write_bytes("I like \u201cplain\u201d words.\r\n".encode("cp1252"))
        with self.assertRaises(P3Error) as cm:
            config.snapshot("c1-skills", root=self.root)
        self.assertIn("tutor/PREFERENCES.md is not UTF-8", str(cm.exception))
        self.assertIn("Save with Encoding", str(cm.exception))
        self.assertFalse((self.root / "configs" / "c1-skills").exists())


if __name__ == "__main__":
    unittest.main()
