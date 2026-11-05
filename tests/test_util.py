"""Hashing, JSON files, run listing, the fixed-file hash list and the git helpers (p3/util.py)."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from p3 import util
from p3.util import P3Error
from tests import RepoTestCase, git, git_init, has_git, write


class TempDir(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="p3-test-"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class HashingTests(TempDir):
    def test_crlf_and_lf_hash_the_same(self):
        (self.dir / "lf").mkdir()
        (self.dir / "crlf").mkdir()
        (self.dir / "lf" / "a.md").write_bytes(b"line one\nline two\n")
        (self.dir / "crlf" / "a.md").write_bytes(b"line one\r\nline two\r\n")
        self.assertEqual(util.hash_tree(self.dir / "lf"), util.hash_tree(self.dir / "crlf"))
        self.assertEqual(util.file_digest(self.dir / "lf" / "a.md"), util.file_digest(self.dir / "crlf" / "a.md"))
        self.assertTrue(util.hash_tree(self.dir / "lf").startswith("sha256:"))

    def test_binary_files_hash_as_they_are(self):
        data = b"\xff\xfe\r\n\x00binary"
        (self.dir / "b.png").write_bytes(data)
        self.assertEqual(util.normalized_bytes(self.dir / "b.png"), data)
        (self.dir / "c.png").write_bytes(data.replace(b"\r\n", b"\n"))
        self.assertNotEqual(util.file_digest(self.dir / "b.png"), util.file_digest(self.dir / "c.png"))

    def test_hash_covers_paths_and_content_and_ignores_order(self):
        write(self.dir / "a.txt", "x")
        write(self.dir / "b.txt", "y")
        h1 = util.hash_files(self.dir, ["a.txt", "b.txt"])
        self.assertEqual(h1, util.hash_files(self.dir, ["b.txt", "a.txt"]))
        write(self.dir / "b.txt", "z")
        self.assertNotEqual(h1, util.hash_files(self.dir, ["a.txt", "b.txt"]))
        write(self.dir / "b.txt", "y")
        (self.dir / "b.txt").rename(self.dir / "c.txt")
        self.assertNotEqual(h1, util.hash_files(self.dir, ["a.txt", "c.txt"]))

    def test_hash_scheme_is_path_nul_content_nul(self):
        import hashlib

        write(self.dir / "x" / "a.md", "hi\n")
        expected = "sha256:" + hashlib.sha256(b"x/a.md\0hi\n\0").hexdigest()
        self.assertEqual(util.hash_files(self.dir, ["x/a.md"]), expected)

    def test_junk_files_are_not_listed_or_hashed(self):
        write(self.dir / "a.md", "a")
        before = util.hash_tree(self.dir)
        write(self.dir / ".DS_Store", "junk")
        write(self.dir / "sub" / "Thumbs.db", "junk")
        write(self.dir / "__pycache__" / "m.cpython-314.pyc", "junk")
        self.assertEqual(util.list_files(self.dir), ["a.md"])
        self.assertEqual(util.hash_tree(self.dir), before)

    def test_list_files_of_a_missing_folder_is_empty(self):
        self.assertEqual(util.list_files(self.dir / "nope"), [])


class JsonTests(TempDir):
    def test_round_trip_writes_lf_and_utf8(self):
        path = self.dir / "deep" / "x.json"
        util.write_json(path, {"name": "Zoë", "n": [1, 2]})
        raw = path.read_bytes()
        self.assertNotIn(b"\r\n", raw)
        self.assertTrue(raw.endswith(b"\n"))
        self.assertIn("Zoë".encode("utf-8"), raw)
        self.assertEqual(util.read_json(path), {"name": "Zoë", "n": [1, 2]})

    def test_read_json_accepts_a_bom(self):
        path = self.dir / "bom.json"
        path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"a": 1}).encode("utf-8"))
        self.assertEqual(util.read_json(path), {"a": 1})

    def test_read_json_errors_name_the_file(self):
        with self.assertRaises(P3Error) as cm:
            util.read_json(self.dir / "missing.json")
        self.assertIn("missing.json", str(cm.exception))
        (self.dir / "bad.json").write_text("{nope", encoding="utf-8")
        with self.assertRaises(P3Error) as cm:
            util.read_json(self.dir / "bad.json")
        self.assertIn("not valid JSON", str(cm.exception))

    def test_times(self):
        when = util.parse_iso("2026-11-03T14:05:09Z")
        self.assertEqual(util.iso_utc(when), "2026-11-03T14:05:09Z")
        self.assertEqual(util.stamp(when), "20261103-140509")
        self.assertIsNone(util.parse_iso("not a time"))


class ConfigFileTests(TempDir):
    def test_config_files_are_claude_md_preferences_and_dot_claude(self):
        for rel in ("CLAUDE.md", "PREFERENCES.md", ".claude/settings.json", ".claude/skills/teach/SKILL.md", "MISSION.md", "NOTES.md", "lessons/0001-x.html", "keys/0001.json", "SNAPSHOT.json", "FORMATS.md"):
            write(self.dir / rel, "x")
        self.assertEqual(util.config_files(self.dir), [".claude/settings.json", ".claude/skills/teach/SKILL.md", "CLAUDE.md", "PREFERENCES.md"])

    def test_local_settings_are_not_part_of_a_config(self):
        write(self.dir / "CLAUDE.md", "x")
        before = util.config_hash(self.dir)
        write(self.dir / ".claude" / "settings.local.json", {"permissions": {"allow": ["Bash"]}})
        self.assertEqual(util.config_files(self.dir), ["CLAUDE.md"])
        self.assertEqual(util.config_hash(self.dir), before)

    def test_learner_files_do_not_change_the_config_hash(self):
        write(self.dir / "CLAUDE.md", "x")
        before = util.config_hash(self.dir)
        write(self.dir / "NOTES.md", "the learner wrote this")
        write(self.dir / "lessons" / "0001-a.html", "<p>hi</p>")
        self.assertEqual(util.config_hash(self.dir), before)
        write(self.dir / ".claude" / "agents" / "reviewer.md", "a subagent")
        self.assertNotEqual(util.config_hash(self.dir), before)


class FixedFileTests(RepoTestCase):
    def test_fixed_set(self):
        write(self.root / "p3" / "x.py", "print(1)\n")
        write(self.root / "p3" / "notes.txt", "not python")
        files = util.fixed_files(self.root)
        self.assertIn("bench/FORMATS.md", files)
        self.assertIn("bench/scenarios.json", files)
        self.assertIn("bench/judge/teach.md", files)
        self.assertIn("bench/topics/agent-architecture/topic.json", files)
        self.assertIn("p3/x.py", files)
        self.assertNotIn("p3/notes.txt", files)
        self.assertFalse(any(f.startswith("bench/own/") or f.startswith("bench/runs/") for f in files))

    def test_rehash_then_verify(self):
        write(self.root / "p3" / "x.py", "print(1)\n")
        hashes = util.rehash(self.root)
        text = (self.root / util.HASH_FILE).read_text(encoding="utf-8")
        self.assertTrue(text.startswith("#"))
        lines = [line for line in text.splitlines() if not line.startswith("#")]
        self.assertEqual(lines, sorted(lines, key=lambda line: line.split("  ", 1)[1]))
        self.assertEqual(len(lines), len(hashes))
        self.assertTrue(all(len(line.split("  ")[0]) == 64 for line in lines))
        self.assertEqual(util.verify_fixed(self.root), {"missing": [], "changed": [], "extra": []})

        # CRLF in a fixed file is not a change
        path = self.root / "bench" / "FORMATS.md"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        self.assertEqual(util.verify_fixed(self.root)["changed"], [])

        write(self.root / "bench" / "judge" / "teach.md", "tampered\n")
        write(self.root / "bench" / "judge" / "extra.md", "new\n")
        (self.root / "p3" / "x.py").unlink()
        result = util.verify_fixed(self.root)
        self.assertEqual(result["changed"], ["bench/judge/teach.md"])
        self.assertEqual(result["extra"], ["bench/judge/extra.md"])
        self.assertEqual(result["missing"], ["p3/x.py"])

    def test_hash_file_reader_accepts_a_prefix(self):
        write(self.root / "h.sha256", "# comment\n\nsha256:abc  bench/a.md\ndef  bench/b c.md\n")
        self.assertEqual(util.read_hash_file(self.root / "h.sha256"), {"bench/a.md": "abc", "bench/b c.md": "def"})

    def test_rehash_command(self):
        code, out, _ = self.p3("rehash")
        self.assertEqual(code, 0)
        self.assertIn("instructor only", out)
        self.assertTrue((self.root / util.HASH_FILE).is_file())

    def test_verify_without_hash_file(self):
        with self.assertRaises(P3Error):
            util.verify_fixed(self.root)


class RepoRootTests(RepoTestCase):
    def test_env_wins(self):
        self.assertEqual(util.repo_root(), self.root.resolve())

    def test_found_from_a_subfolder(self):
        import os

        os.environ.pop("P3_ROOT")
        old = Path.cwd()
        try:
            os.chdir(self.root / "tutor" / ".claude")
            self.assertEqual(util.repo_root(), self.root.resolve())
        finally:
            os.chdir(old)


class ListRunsTests(RepoTestCase):
    def make_run(self, config: str, run_id: str, started: str, topic="agent-architecture", scored=True, minutes=30, quick=False):
        folder = util.runs_dir(config, self.root) / run_id
        util.write_json(folder / "run.json", {"run_id": run_id, "config": config, "topic": topic, "started_at": started, "minutes": minutes, "quick": quick, "scenarios": []})
        if scored:
            util.write_json(folder / "score.json", {"run_id": run_id, "summary": {"x": 1}})
        return folder

    def test_filters_and_order(self):
        self.make_run("c0-baseline", "r-b", "2026-11-03T10:00:00Z")
        self.make_run("c0-baseline", "r-a", "2026-11-03T11:00:00Z", scored=False)
        self.make_run("c1-skills", "r-c", "2026-11-03T09:00:00Z", topic="cooking")
        self.make_run("c1-skills", "r-d", "2026-11-03T12:00:00Z", quick=True, minutes=10)
        self.make_run("live", "r-live", "2026-11-03T08:00:00Z")
        bad = util.runs_dir("c1-skills", self.root) / "r-broken"
        bad.mkdir(parents=True)
        (bad / "run.json").write_text("{", encoding="utf-8")

        ids = [r.run_id for r in util.list_runs(root=self.root)]
        self.assertEqual(ids, ["r-c", "r-b", "r-a", "r-d"])
        self.assertEqual([r.run_id for r in util.list_runs("c0-baseline")], ["r-b", "r-a"])
        self.assertEqual([r.run_id for r in util.list_runs(topic="agent-architecture", scored=True)], ["r-b", "r-d"])
        self.assertEqual([r.run_id for r in util.list_runs(quick=False, minutes=30)], ["r-c", "r-b", "r-a"])
        self.assertEqual([r.run_id for r in util.list_runs("live")], ["r-live"])
        self.assertIn("r-live", [r.run_id for r in util.list_runs(include_live=True)])

    def test_record_access(self):
        folder = self.make_run("c0-baseline", "r-1", "2026-11-03T10:00:00Z")
        (rec,) = util.list_runs("c0-baseline")
        run_dir, run, score = rec
        self.assertEqual(run_dir, folder)
        self.assertIs(rec["run"], run)
        self.assertEqual(rec.score["summary"], {"x": 1})
        self.assertEqual(rec[2], score)
        self.assertEqual(rec.path, folder)
        self.assertEqual(rec.config, "c0-baseline")
        self.assertTrue(rec.scored)
        self.assertEqual(rec.get("nope", 5), 5)


@unittest.skipUnless(has_git(), "git is not installed")
class GitTests(RepoTestCase):
    def setUp(self):
        super().setUp()
        git_init(self.root)
        write(self.root / "bench" / "own" / "cooking" / "topic.json", {"id": "cooking"})
        write(self.root / "bench" / "own" / "cooking" / "workspace" / "NOTES.md", "line\r\nline\r\n")

    def test_outside_a_repo(self):
        shutil.rmtree(self.root / ".git")
        self.assertFalse(util.git_available(self.root))
        self.assertIsNone(util.rev_parse_head(self.root))
        self.assertIsNone(util.git_show_bytes("HEAD", "p3.json", self.root))
        self.assertFalse(util.path_clean_and_tracked("bench/own/cooking", self.root))
        self.assertIsNone(util.first_commit_time("p3.json", self.root))

    def test_clean_and_tracked(self):
        self.assertTrue(util.git_available(self.root))
        self.assertIsNone(util.rev_parse_head(self.root))
        self.assertFalse(util.path_clean_and_tracked("bench/own/cooking", self.root))
        git(self.root, "add", "-A")
        self.assertFalse(util.path_clean_and_tracked("bench/own/cooking", self.root), "staged but not committed")
        git(self.root, "commit", "-q", "-m", "topic")
        self.assertTrue(util.path_clean_and_tracked("bench/own/cooking", self.root))
        head = util.rev_parse_head(self.root)
        self.assertRegex(head, r"^[0-9a-f]{40}$")
        write(self.root / "bench" / "own" / "cooking" / "probes.json", {"probes": []})
        self.assertFalse(util.path_clean_and_tracked("bench/own/cooking", self.root), "an untracked file")
        (self.root / "bench" / "own" / "cooking" / "probes.json").unlink()
        write(self.root / "bench" / "own" / "cooking" / "topic.json", {"id": "changed"})
        self.assertFalse(util.path_clean_and_tracked("bench/own/cooking", self.root), "a changed file")

    def test_show_and_hash_at_commit(self):
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "topic")
        head = util.rev_parse_head(self.root)
        folder = self.root / "bench" / "own" / "cooking"
        self.assertEqual(util.git_show_bytes(head, "bench/own/cooking/topic.json", self.root), (folder / "topic.json").read_bytes())
        self.assertIsNone(util.git_show_bytes(head, "bench/own/cooking/nope.json", self.root))
        self.assertEqual(util.git_ls_files_at(head, "bench/own/cooking", self.root), ["topic.json", "workspace/NOTES.md"])
        self.assertEqual(util.hash_tree_at_commit(head, "bench/own/cooking", self.root), util.hash_tree(folder))
        self.assertIsNone(util.hash_tree_at_commit(head, "bench/own/nothing", self.root))

    def test_first_commit_time(self):
        self.assertIsNone(util.first_commit_time("p3.json", self.root))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "first")
        first = util.first_commit_time("p3.json", self.root)
        self.assertIsNotNone(first)
        self.assertEqual(first.utcoffset().total_seconds(), 0)
        delta = abs((util.utc_now() - first).total_seconds())
        self.assertLess(delta, 600)

    def test_file_versions(self):
        self.assertEqual(list(util.git_file_versions("notes.md", self.root)), [], "never committed")
        for n, text in enumerate(("one\n", "two\n"), 1):
            write(self.root / "notes.md", text)
            git(self.root, "add", "-A")
            git(self.root, "commit", "-q", "-m", f"version {n}", when=f"2026-11-0{n}T12:00:00Z")
        (self.root / "notes.md").unlink()
        git(self.root, "commit", "-q", "-am", "gone", when="2026-11-03T12:00:00Z")
        versions = list(util.git_file_versions("notes.md", self.root))
        self.assertEqual([(when.isoformat(), data) for _commit, when, data in versions], [
            ("2026-11-01T12:00:00+00:00", b"one\n"), ("2026-11-02T12:00:00+00:00", b"two\n"), ("2026-11-03T12:00:00+00:00", None),
        ])  # fmt: skip
        self.assertEqual([c for c, _w, _d in versions], [c for c, _w in util.git_log_path("notes.md", self.root)])
        util.remove_tree(self.root / ".git")  # git's objects are read-only on Windows
        self.assertEqual(list(util.git_file_versions("notes.md", self.root)), [], "not a git repository")

    def test_file_versions_in_one_git_process(self):
        """A process per version costs tens of milliseconds on Windows, so they are read in one."""
        texts = [f"version {n}\n" + "x" * (n * 1000) for n in range(1, 6)]
        for n, text in enumerate(texts, 1):
            write(self.root / "my notes.md", text)
            git(self.root, "add", "-A")
            git(self.root, "commit", "-q", "-m", f"version {n}")
        calls: list[str] = []
        real = util._git

        def counting(args, *rest, **kwargs):
            calls.append(args[0])
            return real(args, *rest, **kwargs)

        with mock.patch.object(util, "_git", counting):
            versions = list(util.git_file_versions("my notes.md", self.root))
        self.assertEqual([data for _c, _w, data in versions], [t.encode("utf-8") for t in texts])
        self.assertEqual(calls.count("cat-file"), 1, calls)
        self.assertNotIn("show", calls)


class RunKindAndGitProblemTests(RepoTestCase):
    def test_run_kind(self):
        self.assertEqual(util.run_kind({"only": None, "scenarios": [{"job": "teach"}, {"job": "quiz"}]}), util.FULL)
        self.assertEqual(util.run_kind({"only": ["teach"], "scenarios": [{"job": "teach"}]}), util.TEACH_ONLY)
        self.assertEqual(util.run_kind({"only": ["teach", "tutor-p01"], "scenarios": [{"job": "teach"}, {"job": "tutor"}]}), util.PARTIAL)
        self.assertEqual(util.run_kind({"only": ["x"], "scenarios": []}), util.PARTIAL)

    def test_text_that_is_not_utf8(self):
        self.assertTrue(util.is_non_utf8_text("caf\xe9".encode("cp1252")))
        self.assertFalse(util.is_non_utf8_text("caf\xe9".encode("utf-8")))
        self.assertFalse(util.is_non_utf8_text(b"\x89PNG\r\n\x1a\n\x00\x00\xff"), "binary files are hashed as they are")

    def test_git_problem(self):
        from unittest import mock

        with mock.patch("p3.util.shutil.which", return_value=None):
            self.assertIn("git is not installed", util.git_problem(self.root))
        if not has_git():
            return
        self.assertIsNotNone(util.git_problem(self.root), "not a repository (or inside someone else's)")
        git_init(self.root.parent)
        self.assertIn("not its own git repository", util.git_problem(self.root))
        git_init(self.root)
        self.assertIsNone(util.git_problem(self.root))


if __name__ == "__main__":
    unittest.main()
