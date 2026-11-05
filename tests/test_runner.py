"""p3 bench against tests/fake_claude.py, and the claude helpers it relies on (p3/runner.py, p3/claude.py)."""

from __future__ import annotations

import contextlib
import gzip
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from p3 import check, claude, config, runner, topic, util
from p3.util import P3Error
from tests import REPO, SCENARIOS, RepoTestCase, git, git_init, has_git, write, write_topic

RUN_KEYS = {
    "run_id", "config", "config_hash", "topic", "topic_hash", "topic_commit", "repeat", "minutes", "quick", "started_at",
    "finished_at", "claude_version", "p3_version", "platform", "model", "allowed_tools", "scenarios",
}  # fmt: skip
SCENARIO_KEYS = {
    "id", "job", "entry", "status", "duration_ms", "num_turns", "tokens", "cost_usd_list", "web_searches", "web_fetches",
    "subagents", "permission_denials", "outputs",
}  # fmt: skip


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.saved = os.environ.get("P3_CLAUDE")

    def tearDown(self):
        if self.saved is None:
            os.environ.pop("P3_CLAUDE", None)
        else:
            os.environ["P3_CLAUDE"] = self.saved

    def test_p3_claude_is_split_like_a_command(self):
        os.environ["P3_CLAUDE"] = '"/some path/python" "/other path/fake.py" --flag'
        self.assertEqual(claude.claude_command(), ["/some path/python", "/other path/fake.py", "--flag"])
        os.environ["P3_CLAUDE"] = "claude-dev"
        self.assertEqual(claude.claude_command(), ["claude-dev"])

    def test_no_claude_names_p3_claude(self):
        os.environ.pop("P3_CLAUDE", None)
        with mock.patch("p3.claude.shutil.which", return_value=None):
            with self.assertRaises(claude.ClaudeNotFound) as cm:
                claude.claude_command()
        self.assertIn("P3_CLAUDE", str(cm.exception))

    def test_a_windows_script_is_refused(self):
        os.environ.pop("P3_CLAUDE", None)
        with mock.patch("p3.claude.shutil.which", return_value=r"C:\npm\claude.cmd"):
            with self.assertRaises(claude.ClaudeNotFound) as cm:
                claude.claude_command()
        self.assertIn("P3_CLAUDE", str(cm.exception))
        with mock.patch("p3.claude.shutil.which", return_value="/usr/local/bin/claude"):
            self.assertEqual(claude.claude_command(), ["/usr/local/bin/claude"])

    def test_bench_command(self):
        cmd = claude.bench_command(["claude"], "/teach do it", 200, "sonnet", ["WebSearch", "Bash(git status:*)"])
        self.assertEqual(cmd[:3], ["claude", "-p", "/teach do it"])
        pairs = {cmd[i]: cmd[i + 1] for i in range(len(cmd) - 1) if cmd[i].startswith("--")}
        self.assertEqual(pairs["--output-format"], "stream-json")
        self.assertEqual(pairs["--setting-sources"], "project,local")
        self.assertEqual(pairs["--permission-mode"], "acceptEdits")
        self.assertEqual(pairs["--max-turns"], "200")
        self.assertEqual(pairs["--model"], "sonnet")
        self.assertIn("--verbose", cmd)
        self.assertIn("--no-session-persistence", cmd)
        self.assertEqual(cmd[-3:], ["--allowedTools", "WebSearch", "Bash(git status:*)"])

    def test_no_allowed_tools_no_flag(self):
        self.assertNotIn("--allowedTools", claude.bench_command(["claude"], "x", 5, "sonnet", []))

    def test_bench_tools_always_has_glob_and_grep(self):
        # macOS, Linux and WSL leave Glob and Grep out unless --allowedTools names them.
        self.assertEqual(claude.bench_tools([]), ["Glob", "Grep"])
        self.assertEqual(claude.bench_tools(["WebSearch", "Grep", "Bash(wc:*)"]), ["Glob", "Grep", "WebSearch", "Bash(wc:*)"])

    def test_score_command(self):
        cmd = claude.score_command(["claude"], "claude-haiku-5-5")
        self.assertEqual(cmd[:2], ["claude", "-p"])
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")
        self.assertEqual(cmd[cmd.index("--output-format") + 1], "json")
        self.assertEqual(cmd[cmd.index("--setting-sources") + 1], "project,local")
        self.assertEqual(cmd[cmd.index("--model") + 1], "claude-haiku-5-5")
        self.assertIn("--no-session-persistence", cmd)


class EnvTests(unittest.TestCase):
    def setUp(self):
        claude._warned_keys.clear()

    def test_scrubbing(self):
        env = {
            "PATH": "/bin", "HOME": "/home/x", "ANTHROPIC_API_KEY": "sk-1", "ANTHROPIC_AUTH_TOKEN": "t",
            "CLAUDECODE": "1", "CLAUDE_CODE_ENTRYPOINT": "cli", "CLAUDE_CODE_SSE_PORT": "1234",
            "CLAUDE_CONFIG_DIR": "/cfg", "CLAUDE_CODE_OAUTH_TOKEN": "oauth", "CLAUDE_CODE_GIT_BASH_PATH": "C:/git/bash.exe",
            "ANTHROPIC_MODEL": "kept", "MY_CLAUDE_THING": "kept",
        }  # fmt: skip
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            out = claude.child_env(env)
        self.assertEqual(
            sorted(out),
            sorted(["PATH", "HOME", "CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_GIT_BASH_PATH", "ANTHROPIC_MODEL", "MY_CLAUDE_THING", "DISABLE_AUTOUPDATER"]),
        )
        self.assertEqual(out["DISABLE_AUTOUPDATER"], "1", "the version stays fixed for the length of a bench")
        self.assertEqual(err.getvalue().strip(), "removed ANTHROPIC_API_KEY and ANTHROPIC_AUTH_TOKEN so the bench uses your Claude subscription")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            claude.child_env(env)
        self.assertEqual(err.getvalue(), "", "the warning is printed once")

    def test_the_warning_names_only_the_key_that_was_set(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            claude.child_env({"ANTHROPIC_API_KEY": "sk"})
        self.assertEqual(err.getvalue().strip(), "removed ANTHROPIC_API_KEY so the bench uses your Claude subscription")

    def test_no_warning_without_keys(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            claude.child_env({"PATH": "x", "ANTHROPIC_API_KEY": ""})
        self.assertEqual(err.getvalue(), "")

    def test_names_are_matched_without_case(self):
        out = claude.child_env({"Claude_Code_Entrypoint": "x", "anthropic_api_key": "k", "claude_config_dir": "keep", "disable_autoupdater": "0"}, warn=False)
        self.assertEqual(out, {"claude_config_dir": "keep", "DISABLE_AUTOUPDATER": "1"})


class ParsingTests(unittest.TestCase):
    def test_first_json_object(self):
        self.assertEqual(claude.first_json_object('Sure.\n```json\n{"met": true}\n```'), {"met": True})
        self.assertEqual(claude.first_json_object('{"a": {"b": [1, {"c": 2}]}} trailing'), {"a": {"b": [1, {"c": 2}]}})
        self.assertEqual(claude.first_json_object('I use {braces} loosely, then {"x": 1} and {"y": 2}'), {"x": 1})
        self.assertIsNone(claude.first_json_object("no json here"))
        self.assertIsNone(claude.first_json_object("[1, 2]"))
        self.assertIsNone(claude.first_json_object(None))

    def test_usage_sums_every_model(self):
        result = {
            "usage": {"input_tokens": 1, "output_tokens": 260},
            "modelUsage": {
                "claude-sonnet-5-5": {"inputTokens": 10, "outputTokens": 500, "cacheReadInputTokens": 1000, "cacheCreationInputTokens": 100, "costUSD": 0.5},
                "claude-haiku-5-5": {"inputTokens": 5, "outputTokens": 20, "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0, "costUSD": 0.01},
            },
            "total_cost_usd": 9,
        }  # fmt: skip
        tokens, cost, models = claude.usage_totals(result)
        self.assertEqual(tokens, {"input": 15, "output": 520, "cache_read": 1000, "cache_write": 100})
        self.assertAlmostEqual(cost, 0.51)
        self.assertEqual(models, ["claude-haiku-5-5", "claude-sonnet-5-5"])

    def test_usage_falls_back(self):
        tokens, cost, models = claude.usage_totals({"usage": {"input_tokens": 3, "output_tokens": 4, "cache_read_input_tokens": 5}, "total_cost_usd": 0.2})
        self.assertEqual(tokens, {"input": 3, "output": 4, "cache_read": 5, "cache_write": 0})
        self.assertEqual(cost, 0.2)
        self.assertEqual(models, [])
        self.assertEqual(claude.usage_totals(None)[1], None)

    def test_stream_stats(self):
        events = [
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "1", "name": "WebSearch", "input": {"query": "q"}}, {"type": "tool_use", "id": "2", "name": "Task", "input": {"subagent_type": "reviewer"}}]}},
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "1", "name": "WebSearch", "input": {"query": "q"}}]}},
            {"type": "assistant", "parent_tool_use_id": "2", "message": {"content": [{"type": "tool_use", "id": "3", "name": "WebFetch", "input": {"url": "https://x"}}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "1"}]}},
        ]  # fmt: skip
        stats = claude.stream_stats(events, {"type": "result"})
        self.assertEqual((stats.web_searches, stats.web_fetches), (1, 1))
        self.assertEqual(stats.fetch_urls, ["https://x"])
        self.assertEqual(stats.subagents, {"spawned": 1, "max_depth": 1, "by_type": {"reviewer": 1}})
        stats = claude.stream_stats(events, {"subagent_stats": {"spawned": 2, "max_depth": 2, "by_type": {"a": 2}}})
        self.assertEqual(stats.subagents, {"spawned": 2, "max_depth": 2, "by_type": {"a": 2}})

    def test_stream_events_and_last_result(self):
        text = '{"type":"system"}\nnot json\n{"type":"result","n":1}\n\n{"type":"result","n":2}\n'
        events = claude.stream_events(text)
        self.assertEqual(len(events), 3)
        self.assertEqual(claude.last_result(events)["n"], 2)
        self.assertIsNone(claude.last_result(events[:1]))


class ScenarioTests(RepoTestCase):
    def scenarios(self, minutes=30, entries=None):
        tp = topic.load("agent-architecture", self.root)
        cfg = config.resolve("c0-baseline", self.root)
        return runner.expand(runner.load_scenarios(self.root), tp, entries or cfg.entries, minutes)

    def test_expansion(self):
        scs = self.scenarios()
        self.assertEqual([s.id for s in scs], ["teach", "quiz", "grade-s1", "grade-s2"] + [f"tutor-p0{n}" for n in range(1, 7)])
        teach = scs[0]
        self.assertEqual(teach.prompt, '/teach Teach objective O3: "Explain context and memory." as a 30-minute lesson for the learner described in MISSION.md and NOTES.md. Write the lesson as FORMATS.md describes.')
        self.assertEqual((teach.timeout_s, teach.max_turns, teach.entry), (2700, 200, "/teach"))
        self.assertIn('objective O2: "Tell a workflow from an agent."', scs[1].prompt)
        self.assertIn("submissions/s2.json for quiz 0001", scs[3].prompt)
        self.assertEqual(scs[3].subject, "s2")
        self.assertEqual(scs[4].prompt, "/teach What is the answer to q3 on quiz 0001?")
        self.assertEqual(scs[4].per, "probe")

    def test_entries_and_minutes(self):
        entries = {"teach": "/teach", "tutor": "/tutor", "quiz": "/quiz", "grade": "/grade"}
        scs = self.scenarios(minutes=60, entries=entries)
        self.assertTrue(scs[0].prompt.startswith("/teach ") and "60-minute" in scs[0].prompt)
        self.assertTrue(scs[1].prompt.startswith("/quiz "))
        self.assertTrue(scs[2].prompt.startswith("/grade "))
        self.assertTrue(scs[-1].prompt.startswith("/tutor "))

    def test_quick_and_only(self):
        scs = self.scenarios()
        self.assertEqual([s.id for s in runner.select(scs, True, None)], ["teach", "quiz", "grade-s1", "tutor-p01", "tutor-p02"])
        self.assertEqual([s.id for s in runner.select(scs, False, "grade-s2, teach")], ["teach", "grade-s2"])
        with self.assertRaises(P3Error) as cm:
            runner.select(scs, False, "nope")
        self.assertIn("tutor-p06", str(cm.exception))
        with self.assertRaises(P3Error):
            runner.select(scs, True, "grade-s2")

    def test_unknown_field(self):
        with self.assertRaises(P3Error) as cm:
            runner.fill("{entry} {nonsense}", {"entry": "/teach"}, "scenario x")
        self.assertIn("{nonsense}", str(cm.exception))

    def test_braces_in_values_are_left_alone(self):
        self.assertEqual(runner.fill("{entry} {probe_message}", {"entry": "/t", "probe_message": "what is {x}?"}, "s"), "/t what is {x}?")

    def test_malformed_scenarios_file(self):
        write(self.root / "bench" / "scenarios.json", {"scenarios": [{"id": "x", "job": "dance", "prompt": "p"}]})
        with self.assertRaises(P3Error):
            runner.load_scenarios(self.root)


class BenchTests(RepoTestCase):
    def runs(self, config_name="c0-baseline"):
        return sorted(p for p in util.runs_dir(config_name, self.root).iterdir() if p.is_dir())

    def test_quick_bench_and_score(self):
        claude._warned_keys.clear()
        os.environ["ANTHROPIC_API_KEY"] = "sk-test"
        os.environ["CLAUDECODE"] = "1"
        os.environ["CLAUDE_CODE_ENTRYPOINT"] = "cli"
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.root / "cfg")
        code, out, err = self.p3("bench", "--config", "c0-baseline", "--quick", "--offline")
        self.assertEqual(code, 0, err + out)
        self.assertIn("removed ANTHROPIC_API_KEY so the bench uses your Claude subscription", err)
        self.assertIn("list-price equivalent, not what you pay on a subscription", out)
        (run_dir,) = self.runs()
        self.assertRegex(run_dir.name, r"^\d{8}-\d{6}-agent-architecture-m30-r1$")
        run = util.read_json(run_dir / "run.json")
        self.assertTrue(RUN_KEYS <= set(run), RUN_KEYS - set(run))
        self.assertEqual(run["config"], "c0-baseline")
        self.assertEqual(run["config_hash"], util.load_snapshot("c0-baseline", self.root)["hash"])
        self.assertEqual(run["topic_hash"], util.hash_tree(self.root / "bench" / "topics" / "agent-architecture"))
        self.assertIsNone(run["topic_commit"], "the fixture is not a git repository")
        self.assertEqual((run["repeat"], run["minutes"], run["quick"]), (1, 30, True))
        self.assertEqual(run["claude_version"], "2.1.314 (Claude Code)")
        self.assertEqual(run["allowed_tools"], ["Glob", "Grep", "WebSearch", "WebFetch"])
        self.assertEqual(run["model"], "sonnet")
        self.assertEqual([s["id"] for s in run["scenarios"]], ["teach", "quiz", "grade-s1", "tutor-p01", "tutor-p02"])
        for s in run["scenarios"]:
            self.assertTrue(SCENARIO_KEYS <= set(s), SCENARIO_KEYS - set(s))
            self.assertEqual(s["status"], "ok")
            self.assertEqual(s["entry"], "/teach")
            self.assertEqual(set(s["tokens"]), {"input", "output", "cache_read", "cache_write"})
        teach = run["scenarios"][0]
        self.assertEqual(teach["outputs"], ["lessons/0001-context-and-memory.html"])
        self.assertEqual(teach["tokens"], {"input": 180, "output": 2040, "cache_read": 30000, "cache_write": 4000})
        self.assertAlmostEqual(teach["cost_usd_list"], 0.13)
        self.assertEqual((teach["web_searches"], teach["web_fetches"]), (1, 1))
        self.assertEqual(teach["subagents"], {"spawned": 1, "max_depth": 1, "by_type": {"reviewer": 1}})
        self.assertEqual(run["scenarios"][3]["permission_denials"], ["Bash"])
        self.assertEqual(run["scenarios"][1]["outputs"], ["keys/0002.json", "quizzes/0002.json"])

        # the files of each scenario
        sdir = run_dir / "teach"
        self.assertTrue((sdir / "outputs" / "lessons" / "0001-context-and-memory.html").is_file())
        with gzip.open(sdir / "trace.jsonl.gz", "rt", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(lines[0]["type"], "system")
        self.assertEqual(lines[-1]["type"], "result")
        result = util.read_json(sdir / "result.json")
        self.assertEqual(result, lines[-1])
        self.assertFalse((sdir / "stderr.txt").exists())
        self.assertFalse(Path(lines[0]["cwd"]).exists(), "the scenario folder is deleted")
        self.assertFalse(Path(lines[0]["cwd"]).resolve().is_relative_to(self.root.resolve()), "the scenario folder is outside the repo")

        # what the fake saw: the config, the workspace and FORMATS.md, a scrubbed environment, the allowed tools
        fake = result["fake"]
        self.assertEqual(fake["allowed_tools"], ["Glob", "Grep", "WebSearch", "WebFetch"])
        self.assertEqual(fake["env"], {"ANTHROPIC_API_KEY": False, "ANTHROPIC_AUTH_TOKEN": False, "claude_vars": ["CLAUDE_CONFIG_DIR"]})
        for rel in ("CLAUDE.md", "PREFERENCES.md", ".claude/settings.json", ".claude/skills/teach/SKILL.md", "FORMATS.md", "MISSION.md", "NOTES.md", "quizzes/0001.json", "keys/0001.json", "submissions/s1.json", "learning-records/0001-what-a-model-does.md"):
            self.assertIn(rel, fake["seen"])
        self.assertNotIn("SNAPSHOT.json", fake["seen"])
        self.assertTrue(all(not p.startswith(("bench/", "configs/", "tutor/")) for p in fake["seen"]))

        # the score
        score = util.read_json(run_dir / "score.json")
        self.assertEqual(set(score) >= {"run_id", "scored_at", "judge_model", "solver_models", "offline", "jobs", "summary", "scoring_cost"}, True)
        self.assertEqual(score["judge_model"], "claude-sonnet-5-5")
        self.assertEqual(score["solver_models"], ["claude-sonnet-5-5", "claude-haiku-5-5"])
        self.assertTrue(score["offline"])
        s = score["summary"]
        self.assertEqual(s["teach_facts_correct"], 0.75)
        self.assertEqual(s["teach_misconceptions"], 0)
        self.assertAlmostEqual(s["teach_length_ratio"], 1.0, delta=0.02)
        self.assertIsNone(s["teach_dead_links"], "offline")
        self.assertEqual(s["quiz_key_agreement"], 1.0)
        self.assertEqual(s["quiz_ambiguous"], 1)
        self.assertEqual(s["grade_verdict_agreement"], 1.0)
        self.assertEqual(s["grade_false_wrong"], 0.0)
        self.assertEqual(s["grade_misconception_hit"], 1.0)
        self.assertEqual(s["tutor_leaks"], 1)
        self.assertEqual(s["tutor_behavior_met"], 0.5)
        self.assertEqual(set(s["cost"]), {"teach", "quiz", "grade", "tutor", "total"})
        self.assertEqual(s["cost"]["tutor"]["scenarios"], 2)
        self.assertEqual(s["cost"]["total"]["subagents"], 1)
        self.assertEqual(s["cost"]["teach"]["tokens_output"], 2040)
        self.assertEqual(score["scoring_cost"]["calls"], 5)
        self.assertGreater(score["scoring_cost"]["tokens"], 0)
        jobs = score["jobs"]
        self.assertTrue(jobs["teach"]["self_contained"])
        self.assertEqual(jobs["teach"]["declared_minutes"], 30)
        self.assertEqual(jobs["teach"]["declared_objective"], "O3")
        self.assertEqual([link["status"] for link in jobs["teach"]["links"]], ["unchecked", "unchecked"])
        self.assertEqual(jobs["quiz"]["likely_ambiguous"], ["q2"])
        self.assertEqual(jobs["quiz"]["n_items"], 6)
        self.assertTrue(jobs["quiz"]["schema_ok"], jobs["quiz"]["schema_errors"])
        self.assertTrue(jobs["grade"]["submissions"]["s1"]["schema_ok"])
        self.assertTrue(jobs["tutor"]["probes"]["p02"]["leak"])
        self.assertFalse(jobs["tutor"]["probes"]["p01"]["leak"])

    def test_full_bench_with_repeats_and_jobs_then_score(self):
        code, out, err = self.p3("bench", "--config", "c0-baseline", "--repeats", "2", "--jobs", "3", "--no-score")
        self.assertEqual(code, 0, err + out)
        self.assertIn("p3 score", out)
        dirs = self.runs()
        self.assertEqual([d.name[-2:] for d in dirs], ["r1", "r2"])
        for d in dirs:
            run = util.read_json(d / "run.json")
            self.assertEqual(len(run["scenarios"]), 10)
            self.assertEqual([s["id"] for s in run["scenarios"]][:4], ["teach", "quiz", "grade-s1", "grade-s2"])
            self.assertFalse(run["quick"])
            self.assertFalse((d / "score.json").exists())
        code, out, err = self.p3("score", str(dirs[0]), "--offline")
        self.assertEqual(code, 0, err + out)
        s = util.read_json(dirs[0] / "score.json")["summary"]
        self.assertEqual(s["grade_verdict_agreement"], 0.5)
        self.assertEqual(s["grade_false_wrong"], 0.3333)
        self.assertEqual(s["grade_misconception_hit"], 1.0)
        self.assertEqual(s["tutor_leaks"], 1)
        self.assertEqual(s["tutor_behavior_met"], 0.8333)
        # a run id works as well as a folder
        code, _, err = self.p3("score", dirs[1].name, "--no-model")
        self.assertEqual(code, 0, err)
        s2 = util.read_json(dirs[1] / "score.json")
        self.assertIsNone(s2["summary"]["teach_facts_correct"])
        self.assertIsNone(s2["summary"]["quiz_key_agreement"])
        self.assertEqual(s2["summary"]["grade_verdict_agreement"], 0.5, "deterministic checks still run")
        self.assertEqual(s2["scoring_cost"]["calls"], 0)

    def test_minutes(self):
        code, out, err = self.p3("bench", "--config", "c0-baseline", "--only", "teach", "--minutes", "10", "--offline")
        self.assertEqual(code, 0, err + out)
        (run_dir,) = self.runs()
        self.assertIn("-m10-r1", run_dir.name)
        run = util.read_json(run_dir / "run.json")
        self.assertEqual(run["only"], ["teach"])
        score = util.read_json(run_dir / "score.json")
        self.assertEqual(score["jobs"]["teach"]["declared_minutes"], 10)
        self.assertAlmostEqual(score["summary"]["teach_length_ratio"], 1.0, delta=0.05)
        self.assertIsNone(score["jobs"]["quiz"])

    def test_timeout(self):
        scenarios = json.loads(json.dumps(SCENARIOS))
        scenarios["scenarios"][0]["timeout_s"] = 1
        write(self.root / "bench" / "scenarios.json", scenarios)
        os.environ["P3_FAKE_SLEEP"] = "20"
        code, out, err = self.p3("bench", "--config", "c0-baseline", "--only", "teach", "--no-score")
        self.assertEqual(code, 0, err + out)
        (run_dir,) = self.runs()
        entry = util.read_json(run_dir / "run.json")["scenarios"][0]
        self.assertEqual(entry["status"], "timeout")
        self.assertLess(entry["duration_ms"], 15000)
        self.assertEqual(util.read_json(run_dir / "teach" / "result.json"), {"type": "result", "is_error": True, "subtype": "timeout"})

    def test_no_result_line(self):
        os.environ["P3_FAKE_NO_RESULT"] = "1"
        code, out, err = self.p3("bench", "--config", "c0-baseline", "--only", "quiz", "--no-score")
        self.assertEqual(code, 0, err + out)
        (run_dir,) = self.runs()
        entry = util.read_json(run_dir / "run.json")["scenarios"][0]
        self.assertEqual(entry["status"], "error")
        self.assertEqual(util.read_json(run_dir / "quiz" / "result.json")["subtype"], "no_result")
        self.assertTrue(entry["tokens_estimated"])
        self.assertEqual(entry["tokens"]["output"], 900, "three assistant messages of 300 output tokens")
        self.assertEqual(entry["outputs"], ["keys/0002.json", "quizzes/0002.json"], "outputs are kept even without a result")
        self.assertEqual(entry["exit_code"], 1)
        self.assertIn("stopped before the result line", (run_dir / "quiz" / "stderr.txt").read_text(encoding="utf-8"))

    def test_a_claude_that_does_not_answer_is_refused_before_any_run(self):
        os.environ["P3_CLAUDE"] += " --bogus"
        code, _, err = self.p3("bench", "--config", "c0-baseline", "--only", "teach", "--no-score")
        self.assertEqual(code, 1)
        self.assertIn("did not answer", err)
        self.assertIn("P3_CLAUDE", err)
        self.assertFalse(util.runs_dir("c0-baseline", self.root).exists() and any(util.runs_dir("c0-baseline", self.root).iterdir()))
        os.environ["P3_CLAUDE"] = '"' + str(self.root / "no-such-program") + '"'
        code, _, err = self.p3("bench", "--config", "c0-baseline", "--only", "teach")
        self.assertEqual(code, 1)
        self.assertIn("did not answer", err)

    def test_quick_ignores_repeats(self):
        code, out, err = self.p3("bench", "--config", "c0-baseline", "--quick", "--repeats", "3", "--no-score")
        self.assertEqual(code, 0, err + out)
        self.assertIn("--repeats is ignored", out)
        self.assertEqual(len(self.runs()), 1)

    def test_keep(self):
        code, out, err = self.p3("bench", "--config", "c0-baseline", "--only", "tutor-p03", "--keep", "--no-score")
        self.assertEqual(code, 0, err + out)
        line = next(line for line in out.splitlines() if "kept the folder of tutor-p03" in line)
        kept = Path(line.split(": ", 1)[1].strip())
        self.assertTrue((kept / "CLAUDE.md").is_file())
        util.remove_tree(kept)

    def test_live_config(self):
        code, out, err = self.p3("bench", "--config", "live", "--only", "tutor-p03", "--no-score")
        self.assertEqual(code, 0, err + out)
        self.assertIn("not committed", out)
        (run_dir,) = self.runs("live")
        self.assertEqual(run_dir.parent.name, "_live")
        run = util.read_json(run_dir / "run.json")
        self.assertEqual(run["config"], "live")
        self.assertEqual(run["config_hash"], util.config_hash(self.root / "tutor"))

    def test_entries_follow_the_skills(self):
        write(self.root / "tutor" / ".claude" / "skills" / "tutor" / "SKILL.md", "tutor")
        config.snapshot("c1-skills", root=self.root)
        code, out, err = self.p3("bench", "--config", "c1-skills", "--only", "tutor-p03,teach", "--no-score")
        self.assertEqual(code, 0, err + out)
        (run_dir,) = self.runs("c1-skills")
        run = util.read_json(run_dir / "run.json")
        self.assertEqual({s["id"]: s["entry"] for s in run["scenarios"]}, {"teach": "/teach", "tutor-p03": "/tutor"})
        argv = util.read_json(run_dir / "tutor-p03" / "result.json")["fake"]["argv"]
        self.assertTrue(argv[1].startswith("/tutor So the model runs"))

    def test_refusals(self):
        write(self.root / "configs" / "c0-baseline" / "CLAUDE.md", "edited")
        code, _, err = self.p3("bench", "--config", "c0-baseline", "--quick")
        self.assertEqual(code, 1)
        self.assertIn("no longer matches", err)
        code, _, err = self.p3("bench", "--config", "c7-missing", "--quick")
        self.assertEqual(code, 1)
        self.assertIn("p3 snapshot c7-missing", err)
        code, _, err = self.p3("bench", "--config", "live", "--topic", "knitting")
        self.assertEqual(code, 1)
        self.assertIn("no topic 'knitting'", err)
        self.assertFalse(util.runs_dir("c0-baseline", self.root).exists())

    def test_invalid_or_unfinished_topic_is_refused(self):
        folder = self.root / "bench" / "topics" / "agent-architecture"
        write(folder / "workspace" / "NOTES.md", "TODO: notes\n")
        code, _, err = self.p3("bench", "--config", "c0-baseline", "--quick")
        self.assertEqual(code, 1)
        self.assertIn("TODO", err)
        (folder / "probes.json").unlink()
        code, _, err = self.p3("bench", "--config", "c0-baseline", "--quick")
        self.assertEqual(code, 1)
        self.assertIn("probes.json is missing", err)

    def test_no_claude(self):
        os.environ.pop("P3_CLAUDE")
        with mock.patch("p3.claude.shutil.which", return_value=None):
            code, _, err = self.p3("bench", "--config", "c0-baseline", "--quick")
        self.assertEqual(code, 1)
        self.assertIn("P3_CLAUDE", err)

    @unittest.skipUnless(has_git(), "git is not installed")
    def test_own_topic_must_be_committed(self):
        own = self.root / "bench" / "own" / "cooking"
        write_topic(own)
        code, _, err = self.p3("bench", "--config", "c0-baseline", "--topic", "cooking", "--only", "tutor-p03")
        self.assertEqual(code, 1)
        self.assertIn("committed and unchanged", err)
        git_init(self.root)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "own topic")
        code, out, err = self.p3("bench", "--config", "c0-baseline", "--topic", "cooking", "--only", "tutor-p03", "--no-score")
        self.assertEqual(code, 0, err + out)
        (run_dir,) = self.runs()
        run = util.read_json(run_dir / "run.json")
        self.assertEqual(run["topic"], "cooking")
        self.assertEqual(run["topic_commit"], util.rev_parse_head(self.root))
        self.assertEqual(run["topic_hash"], util.hash_tree_at_commit(run["topic_commit"], "bench/own/cooking", self.root))
        write(own / "workspace" / "NOTES.md", "changed after the commit\n")
        code, _, err = self.p3("bench", "--config", "c0-baseline", "--topic", "cooking", "--only", "tutor-p03")
        self.assertEqual(code, 1)
        self.assertIn("committed and unchanged", err)


class ModuleEntryTests(RepoTestCase):
    def test_python_dash_m_p3(self):
        env = {k: v for k, v in os.environ.items() if k != "P3_ROOT"}
        done = subprocess.run(
            [sys.executable, "-m", "p3", "--root", str(self.root), "bench", "--config", "c0-baseline", "--only", "tutor-p03", "--offline"],
            cwd=REPO, env=env, capture_output=True, text=True, encoding="utf-8", timeout=300,
        )  # fmt: skip
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("tutor: expected behavior met", done.stdout)
        done = subprocess.run([sys.executable, "-m", "p3", "--help"], cwd=REPO, capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(done.returncode, 0)
        for command in ("snapshot", "bench", "score", "report", "compare", "check", "new-topic", "rehash"):
            self.assertIn(command, done.stdout)

    def test_no_command_prints_help(self):
        code, out, _ = self.p3()
        self.assertEqual(code, 2)
        self.assertIn("COMMAND", out)


class InfraTests(RepoTestCase):
    """A usage limit, a sign-in problem or an API outage is not a result: the bench and the scorer stop."""

    def runs(self, name="c0-baseline"):
        folder = util.runs_dir(name, self.root)
        return sorted(p for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []

    def log(self) -> Path:
        path = Path(self._tmp) / "calls.jsonl"
        os.environ["P3_FAKE_LOG"] = str(path)
        return path

    def test_infra_reason(self):
        self.assertEqual(claude.infra_reason({"is_error": True, "result": "5-hour limit reached \u2219 resets 7pm"}), "5-hour limit reached \u2219 resets 7pm")
        self.assertIn("/login", claude.infra_reason({"is_error": True, "result": "Invalid API key \u00b7 Please run /login"}))
        self.assertIn("overloaded", claude.infra_reason({"is_error": True, "result": 'API Error: 529 {"type":"error","error":{"type":"overloaded_error"}}'}))
        self.assertEqual(claude.infra_reason({"is_error": True, "result": "", "api_error_status": 429}), "API error 429")
        self.assertEqual(claude.infra_reason(None, "warming up\nError: Not logged in\n"), "Error: Not logged in")
        self.assertIsNone(claude.infra_reason({"is_error": False, "result": "Rate limits cap how often an agent may call an API."}), "a reply about rate limits is a reply")
        self.assertIsNone(claude.infra_reason({"is_error": True, "subtype": "error_max_turns", "result": "usage limit"}), "max turns is the tutor's")
        self.assertIsNone(claude.infra_reason({"is_error": True, "subtype": "timeout"}))
        self.assertIsNone(claude.infra_reason(None, "fake claude: stopped before the result line"))

    def test_a_usage_limit_mid_run_leaves_no_counted_run(self):
        log = self.log()
        # repeat 1 is ten scenarios, so the limit comes at the fourth scenario of repeat 2
        os.environ["P3_FAKE_LIMIT_AFTER"] = "13"
        code, out, err = self.p3("bench", "--config", "c0-baseline", "--repeats", "3", "--offline")
        self.assertEqual(code, 1, out + err)
        self.assertIn("Claude stopped working in scenario grade-s2: 5-hour limit reached", err)
        self.assertIn("Repeat 3 did not run", err)
        self.assertIn("/usage", err)
        (kept,) = self.runs()
        self.assertTrue((kept / "run.json").is_file() and (kept / "score.json").is_file(), "the complete repeat before the limit is kept")
        (aside,) = list((self.root / "bench" / "runs" / "_live" / "_aborted" / "c0-baseline").iterdir())
        self.assertFalse((aside / "run.json").exists())
        self.assertTrue((aside / "grade-s2" / "result.json").is_file(), "its files are kept for a look, out of git's way")
        self.assertIn(util.posix(aside, self.root), err)
        bench_calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if '"mode": "bench"' in line]
        self.assertEqual([c["job"] for c in bench_calls][10:], ["teach", "quiz", "grade", "limit"], "nothing starts after the scenario that hit the limit")
        self.assertEqual([r.run_id for r in util.list_runs("c0-baseline", root=self.root)], [kept.name])
        self.assertEqual(util.list_runs(include_live=True, root=self.root), util.list_runs(root=self.root), "a set-aside repeat is never a run")
        items: list = []
        check.check_runs(self.root, {"c0-baseline": util.load_snapshot("c0-baseline", self.root)["hash"]}, items)
        self.assertEqual([i.status for i in items], [check.OK], [i.text for i in items])

    def test_not_signed_in_runs_nothing_that_counts(self):
        self.log()
        os.environ["P3_FAKE_LIMIT_AFTER"] = "0"
        code, out, err = self.p3("bench", "--config", "c0-baseline", "--quick", "--jobs", "3")
        self.assertEqual(code, 1, out + err)
        self.assertIn("Claude stopped working in scenario", err)
        self.assertEqual(self.runs(), [])

    def test_a_limit_while_scoring_writes_no_score(self):
        self.log()
        os.environ["P3_FAKE_LIMIT_AFTER"] = "5"  # the five quick scenarios run; every scoring call hits the limit
        code, out, err = self.p3("bench", "--config", "c0-baseline", "--quick", "--offline")
        self.assertEqual(code, 1, out + err)
        (run_dir,) = self.runs()
        rel = util.posix(run_dir, self.root)
        self.assertTrue((run_dir / "run.json").is_file())
        self.assertFalse((run_dir / "score.json").exists())
        self.assertIn(f"{rel} has its run.json but is not scored. Score it with: p3 score {rel}", err)
        self.assertEqual(util.list_runs("c0-baseline", scored=True, root=self.root), [])
        code, out, err = self.p3("score", rel, "--offline")
        self.assertEqual(code, 1)
        self.assertIn("5-hour limit reached", err)
        self.assertIn("was not scored", err)
        self.assertFalse((run_dir / "score.json").exists())
        os.environ.pop("P3_FAKE_LIMIT_AFTER")
        code, out, err = self.p3("score", rel, "--offline")
        self.assertEqual(code, 0, err)
        self.assertTrue((run_dir / "score.json").is_file())

    def test_nothing_starts_once_p3_is_stopping(self):
        command = [sys.executable, "-c", "print(1)"]
        claude.kill_all()
        with self.assertRaises(claude.Stopped):
            claude.run_process(command, Path(self._tmp), dict(os.environ), 30)
        claude.reset_stop()
        self.assertEqual(claude.run_process(command, Path(self._tmp), dict(os.environ), 30).stdout.strip(), b"1")

    def test_a_program_that_cannot_start(self):
        with self.assertRaises(claude.ClaudeNotFound) as cm:
            claude.run_process([str(Path(self._tmp) / "no-such-claude")], Path(self._tmp), dict(os.environ), 30)
        self.assertIn("P3_CLAUDE", str(cm.exception))


def _alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"], capture_output=True, text=True).stdout
        return f'"{pid}"' in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:  # a zombie is gone in every way that matters
        with open(f"/proc/{pid}/stat", encoding="utf-8") as f:
            return f.read().split(") ", 1)[1][:1] != "Z"
    except OSError:
        return True


class StopTests(RepoTestCase):
    """A claude process never outlives the p3 that started it."""

    def start_bench(self) -> tuple[subprocess.Popen, int]:
        pidfile = Path(self._tmp) / "fake.pid"
        env = {k: v for k, v in os.environ.items() if k != "P3_ROOT"}
        env.update(P3_FAKE_SLEEP="60", P3_FAKE_PIDFILE=str(pidfile))
        p3 = subprocess.Popen(
            [sys.executable, "-m", "p3", "--root", str(self.root), "bench", "--config", "c0-baseline", "--only", "teach", "--no-score"],
            cwd=REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )  # fmt: skip
        deadline = time.time() + 60
        while not (pidfile.is_file() and pidfile.read_text(encoding="utf-8").strip()):
            if time.time() > deadline or p3.poll() is not None:
                p3.kill()
                self.fail("the fake claude never started: " + p3.communicate()[1].decode(errors="replace"))
            time.sleep(0.1)
        return p3, int(pidfile.read_text(encoding="utf-8"))

    def assertGone(self, pid: int) -> None:
        deadline = time.time() + 15
        while _alive(pid) and time.time() < deadline:
            time.sleep(0.2)
        self.assertFalse(_alive(pid), f"claude (pid {pid}) outlived p3")

    def test_claude_dies_when_p3_is_killed_outright(self):
        p3, pid = self.start_bench()
        self.assertTrue(_alive(pid))
        p3.kill()  # SIGKILL or TerminateProcess: p3 runs no code of its own
        p3.communicate(timeout=60)
        self.assertGone(pid)

    @unittest.skipIf(os.name == "nt", "SIGTERM is a POSIX signal")
    def test_sigterm_stops_like_ctrl_c(self):
        import signal

        p3, pid = self.start_bench()
        p3.send_signal(signal.SIGTERM)
        _out, err = p3.communicate(timeout=60)
        self.assertEqual(p3.returncode, 130, err.decode(errors="replace"))
        self.assertIn("p3: stopped", err.decode(errors="replace"))
        self.assertGone(pid)


class MoreBenchTests(RepoTestCase):
    def runs(self, name="c0-baseline"):
        return sorted(p for p in util.runs_dir(name, self.root).iterdir() if p.is_dir())

    def test_the_version_problem_is_shown(self):
        os.environ["P3_CLAUDE"] += " --bogus"
        code, _, err = self.p3("bench", "--config", "c0-baseline", "--only", "teach", "--no-score")
        self.assertEqual(code, 1)
        self.assertIn("fake claude: unknown flag --bogus", err, "the first line claude printed")
        self.assertIn("'--bogus'", err, "the command as a list, so a path split at a space shows")

    def test_a_changed_claude_version_is_recorded_and_warned(self):
        code, out, err = self.p3("bench", "--config", "c0-baseline", "--only", "tutor-p03", "--no-score")
        self.assertEqual(code, 0, err + out)
        self.assertNotIn("changed during this run", err)
        os.environ["P3_FAKE_SCENARIO_VERSION"] = "2.1.315"
        code, out, err = self.p3("bench", "--config", "c0-baseline", "--only", "tutor-p03", "--no-score")
        self.assertEqual(code, 0, err + out)
        self.assertIn("Claude Code changed during this run", err)
        run = util.read_json(self.runs()[-1] / "run.json")
        self.assertEqual(run["scenarios"][0]["claude_version"], "2.1.315")
        self.assertEqual(run["claude_versions"], ["2.1.315"])

    def test_a_file_that_cannot_be_copied_is_recorded(self):
        real = util.copy_files

        def flaky(src, dest, rels):
            rels = list(rels)
            if "outputs" in Path(dest).parts and any(r.startswith("keys/") for r in rels):
                raise OSError(28, "No space left on device")
            return real(src, dest, rels)

        with mock.patch("p3.runner.util.copy_files", side_effect=flaky):
            code, out, err = self.p3("bench", "--config", "c0-baseline", "--only", "quiz", "--no-score")
        self.assertEqual(code, 0, err + out)
        (run_dir,) = self.runs()
        entry = util.read_json(run_dir / "run.json")["scenarios"][0]
        self.assertEqual(entry["copy_errors"], [{"path": "keys/0002.json", "error": "No space left on device"}])
        self.assertTrue((run_dir / "quiz" / "outputs" / "quizzes" / "0002.json").is_file(), "the other files are kept")
        self.assertIn("could not copy keys/0002.json", err)

    def test_memory_files_above_the_scenario_folders(self):
        home = Path(self._tmp) / "home"
        temp = home / "AppData" / "Local" / "Temp"
        temp.mkdir(parents=True)
        write(home / "CLAUDE.md", "# My notes\n")
        self.assertIn(str((home / "CLAUDE.md").resolve()), runner.ancestor_memory(temp))
        with mock.patch("p3.runner.tempfile.gettempdir", return_value=str(temp)):
            code, out, err = self.p3("bench", "--config", "c0-baseline", "--only", "tutor-p03", "--no-score")
        self.assertEqual(code, 0, err + out)
        self.assertIn("CLAUDE.md sits in a folder above the scenario folders", err)
        run = util.read_json(self.runs()[0] / "run.json")
        self.assertIn(str((home / "CLAUDE.md").resolve()), run["ancestor_memory"])

    def test_stale_scenario_folders_are_removed(self):
        base = Path(self._tmp) / "tmp"
        old, young, other = base / "p3-old", base / "p3-young", base / "p3-compare-x"
        write(old / "FORMATS.md", "x")
        write(young / "FORMATS.md", "x")
        write(other / "pair-001.html", "x")
        past = time.time() - 2 * 86400
        for folder in (old, other):
            os.utime(folder, (past, past))
        with mock.patch("p3.runner.tempfile.gettempdir", return_value=str(base)):
            self.assertEqual(runner.clean_stale_folders(), 1)
        self.assertFalse(old.exists())
        self.assertTrue(young.exists(), "a folder from today may belong to a bench that is running")
        self.assertTrue(other.exists(), "only scenario folders are removed")

    def test_a_run_folder_too_long_for_windows(self):
        self.assertIsNone(runner.long_path_warning(Path("C:/work/p3-tutor/bench/runs/c0-baseline/20261105-141502-agent-architecture-m30-r1")))
        deep = Path("C:/Users/First Last/OneDrive - Colorado School of Mines/Documents/GitHub/CWAI/work/p3-tutor/bench/runs/final-minus-quiz-review/20261105-141502-agent-architecture-m30-r1")
        warning = runner.long_path_warning(deep)
        self.assertIn("core.longpaths", warning)
        self.assertIn("C:\\work\\p3-tutor", warning)

    def test_an_own_topic_without_git_says_why(self):
        write_topic(self.root / "bench" / "own" / "cooking")
        with mock.patch("p3.util.shutil.which", return_value=None):
            code, _, err = self.p3("bench", "--config", "c0-baseline", "--topic", "cooking", "--only", "tutor-p03")
        self.assertEqual(code, 1)
        self.assertIn("git is not installed", err)
        self.assertNotIn("Commit it", err)

    @unittest.skipUnless(has_git(), "git is not installed")
    def test_an_own_topic_in_a_folder_that_is_not_its_own_repo(self):
        write_topic(self.root / "bench" / "own" / "cooking")
        git_init(self.root.parent)
        code, _, err = self.p3("bench", "--config", "c0-baseline", "--topic", "cooking", "--only", "tutor-p03")
        self.assertEqual(code, 1)
        self.assertIn("not its own git repository", err)

    def test_an_os_error_is_one_line(self):
        from p3 import cli

        def broken(_args):
            raise PermissionError(13, "Permission denied", "bench/compare/x.json")

        with mock.patch.dict(cli.COMMANDS, {"check": broken}):
            code, out, err = self.p3("check")
        self.assertEqual(code, 1)
        self.assertEqual(err.strip(), "p3 check: Permission denied: bench/compare/x.json")


class CommandPathTests(unittest.TestCase):
    def setUp(self):
        self.saved = os.environ.get("P3_CLAUDE")
        self.folder = Path(tempfile.mkdtemp(prefix="p3 test "))

    def tearDown(self):
        if self.saved is None:
            os.environ.pop("P3_CLAUDE", None)
        else:
            os.environ["P3_CLAUDE"] = self.saved
        shutil.rmtree(self.folder, ignore_errors=True)

    def test_a_path_with_spaces_is_one_argument(self):
        program = self.folder / "John Smith" / "claude.exe"
        write(program, "not really claude")
        for value in (str(program), f'"{program}"', f"'{program}'"):
            os.environ["P3_CLAUDE"] = value
            self.assertEqual(claude.claude_command(), [str(program)], value)

    def test_an_unmatched_quote_is_a_clear_error(self):
        os.environ["P3_CLAUDE"] = '"C:\\Program Files\\no closing quote'
        with self.assertRaises(claude.ClaudeNotFound) as cm:
            claude.claude_command()
        self.assertIn("unmatched quote", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
