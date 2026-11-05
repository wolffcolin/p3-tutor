"""The Guide's guard (.claude/hooks/guide_guard.py).

Each test runs the guard the way Claude Code does: as a subprocess (`sys.executable guide_guard.py`)
with the PreToolUse hook input as JSON on stdin. Exit 0 lets the tool call run; exit 2 blocks it and
prints one line on stderr that starts with "p3-guide guard:". The tests cover every rule in the guard's
docstring both ways, the other tools (Read, Grep, Glob and PowerShell), the protocol (agent types,
unreadable input), and a regression for each way around the guard that was found and closed.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "guide_guard.py"
GUIDE = "p3-guide"


def run_guard(payload=None, *, raw: str | None = None):
    """Run the guard with payload as JSON on stdin (or raw text), returning (code, stderr)."""
    text = raw if raw is not None else json.dumps(payload)
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        input=text, capture_output=True, text=True,
    )  # fmt: skip
    return proc.returncode, proc.stdout, proc.stderr


def bash(command: str, agent: str | None = GUIDE) -> dict:
    data = {"tool_name": "Bash", "tool_input": {"command": command}}
    if agent is not None:
        data["agent_type"] = agent
    return data


def tool(name: str, agent: str | None = GUIDE, **tool_input) -> dict:
    data = {"tool_name": name, "tool_input": tool_input}
    if agent is not None:
        data["agent_type"] = agent
    return data


class GuardTestCase(unittest.TestCase):
    def assertAllow(self, payload, msg=""):
        code, out, err = run_guard(payload)
        self.assertEqual(code, 0, f"expected allow for {payload!r}: {err or out} {msg}")
        self.assertEqual(err, "", f"an allowed call must say nothing on stderr ({payload!r})")

    def assertBlock(self, payload, needle: str = "", msg=""):
        code, out, err = run_guard(payload)
        self.assertEqual(code, 2, f"expected block for {payload!r}: {out} {msg}")
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, f"a block prints exactly one line ({err!r})")
        self.assertTrue(lines[0].startswith("p3-guide guard:"), f"stderr was {err!r}")
        if needle:
            self.assertIn(needle, err, f"block reason for {payload!r} was {err!r}")

    def allow_bash(self, *commands):
        for command in commands:
            with self.subTest(command=command):
                self.assertAllow(bash(command))

    def block_bash(self, *commands):
        for command in commands:
            with self.subTest(command=command):
                self.assertBlock(bash(command))


class ProtocolTests(GuardTestCase):
    def test_exit_codes_and_one_stderr_line(self):
        self.assertAllow(bash("ls -la"))
        self.assertBlock(bash("rm -rf x"))

    def test_other_agent_types_allow_everything(self):
        for agent in ("builder", "general-purpose", "some-other-agent"):
            with self.subTest(agent=agent):
                self.assertAllow(bash("rm -rf /", agent=agent))
                self.assertAllow(tool("Write", agent=agent, file_path="x"))

    def test_missing_agent_type_applies_the_rules(self):
        # A main-session agent's hook input carries no agent_type; the rules still apply.
        self.assertBlock(bash("rm -rf x", agent=None))
        self.assertAllow(bash("ls", agent=None))

    def test_unreadable_json_is_blocked(self):
        for raw in ("not json", "{", '{"tool_name": ', "\x00"):
            with self.subTest(raw=raw):
                code, _out, err = run_guard(raw=raw)
                self.assertEqual(code, 2, raw)
                self.assertTrue(err.startswith("p3-guide guard:"), err)

    def test_empty_or_non_dict_input_allows(self):
        # Empty stdin becomes {}, and a valid non-object carries no tool to block.
        for raw in ("", "{}", "[]", "42", '"x"'):
            with self.subTest(raw=raw):
                code, _out, err = run_guard(raw=raw)
                self.assertEqual((code, err), (0, ""), raw)


class ReadGrepGlobTests(GuardTestCase):
    def test_ordinary_reads_are_allowed(self):
        self.assertAllow(tool("Read", file_path="README.md"))
        self.assertAllow(tool("Read", file_path="bench/compare/README.md"))  # not a key
        self.assertAllow(tool("Grep", pattern="objective", path="bench/own"))
        self.assertAllow(tool("Glob", glob="**/*.py"))

    def test_key_blocked_through_read(self):
        self.assertBlock(tool("Read", file_path="bench/compare/s3.key.json"), "blind")

    def test_key_blocked_through_read_windows_path(self):
        self.assertBlock(tool("Read", file_path="bench\\compare\\s3.key.json"), "blind")

    def test_key_blocked_through_grep_path_and_glob(self):
        self.assertBlock(tool("Grep", pattern="left", path="bench/compare/s3.key.json"), "blind")
        self.assertBlock(tool("Grep", pattern="left", glob="*.key.json"), "blind")

    def test_grep_blocks_the_whole_compare_folder(self):
        # Even a non-key path or a bare search of the folder is refused for Grep (it reads contents).
        self.assertBlock(tool("Grep", pattern="left", path="bench/compare"), "blind")
        self.assertBlock(tool("Grep", pattern="left", path="bench\\compare\\s3.json"), "blind")

    def test_key_blocked_through_glob(self):
        self.assertBlock(tool("Glob", glob="bench/compare/*.key.json"), "blind")


class PowerShellTests(GuardTestCase):
    def test_powershell_is_always_blocked(self):
        self.assertBlock(tool("PowerShell", command="Get-ChildItem"), "PowerShell")
        self.assertBlock(tool("PowerShell", command="echo hi"))


class EditWriteTests(GuardTestCase):
    def test_file_changing_tools_are_blocked(self):
        for name in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
            with self.subTest(name=name):
                self.assertBlock(tool(name, file_path="x"), "never changes a file")


class BashStructureTests(GuardTestCase):
    def test_separators_join_allowed_commands(self):
        self.allow_bash(
            "cd .. && ls",
            "ls || pwd",
            "pwd; ls",
            "cat f | grep x | sort | uniq",
            "ls\npwd\ncat f",
        )

    def test_one_bad_segment_blocks_the_whole_line(self):
        self.block_bash("ls && rm x", "echo a; rm -rf x", "cat f | rm b", "ls\nrm x")

    def test_command_and_process_substitution(self):
        self.block_bash("echo $(rm x)", "echo `rm x`", "cat <(rm x)", "tee >(rm x)", "echo $((1+1))")

    def test_name_value_prefix(self):
        self.block_bash("X=1 ls", "FOO=bar cat f")

    def test_background_is_blocked(self):
        self.block_bash("ls &", "sleep 100 &", "echo a & echo b")

    def test_redirects(self):
        self.allow_bash(
            "echo hi > /dev/null",
            "ls >/dev/null 2>&1",
            "grep x f 2>/dev/null",
            "ls 1>&2",
        )
        self.block_bash(
            "echo hi > out.txt",
            "echo hi >> out.txt",
            "ls 2> err.txt",
            "sort f -o out.txt",
            "echo hi > nul",        # Git Bash: nul is an ordinary file, not a null device
            "echo hi >& out.txt",
        )

    def test_unclosed_quote_is_blocked(self):
        self.block_bash("echo 'unterminated", 'cat "x')

    def test_crlf_is_handled_like_newlines(self):
        self.assertAllow(bash("ls\r\npwd"))
        self.assertBlock(bash("ls\r\nrm x"))

    def test_shell_operators_and_blocks_are_rejected(self):
        self.block_bash("(ls)", "{ ls; }", "! ls", "if true; then ls; fi", "for i in a; do ls; done")

    def test_unknown_commands_are_blocked(self):
        self.block_bash("rm x", "cp a b", "mv a b", "curl http://x", "sh -c ls", "bash x.sh",
                         "env ls", "xargs ls", "eval ls", "exec ls", "nohup ls", "tee f")  # fmt: skip


class BashKeyTests(GuardTestCase):
    def test_key_path_in_a_bash_command(self):
        self.block_bash(
            "cat bench/compare/s3.key.json",
            "head -n 5 bench/compare/s3.key.json",
            "git show HEAD:bench/compare/s3.key.json",
        )

    def test_key_hidden_by_quoting(self):
        # shlex concatenates the adjacent quoted pieces back into one ".key.json" token.
        self.block_bash('cat "bench/compare/s3.key"".json"', "cat bench/compare/s3.key''.json")

    def test_the_compare_folder_is_off_limits_to_bash(self):
        self.block_bash(
            "cat bench/compare/*",
            "cat bench/compare/*.json",
            "grep -r . bench/compare",
            "ls bench/compare",
            "cd bench/compare && cat s3.json",
            "cat bench\\compare\\s3.json",
        )


class BashReaderTests(GuardTestCase):
    def test_plain_readers_allowed(self):
        self.allow_bash(
            "cd tutor", "pwd", "ls -la", "cat README.md", "head -n 20 EVAL.md", "tail -n 5 f",
            "wc -l f", "grep -rn foo p3", "egrep x f", "fgrep x f", "rg foo", "sort f", "uniq f",
            "cut -d, -f1 f", "tr a b", "echo hi", "printf '%s' x", "which python", "file f",
            "stat f", "du -sh .", "basename a/b", "dirname a/b", "realpath .", "date", "date +%s",
            "diff a b", "cmp a b", "zcat f.gz", "find . -name '*.md'", "tree -L 2",
        )

    def test_gzip_only_to_stdout_or_listing(self):
        self.allow_bash("gzip -c f", "gzip -cf f", "gzip -l f", "gunzip -t f.gz", "gzip --stdout f",
                        "gzip -dc f.gz", "gunzip -lr dir")  # fmt: skip
        self.block_bash("gzip f", "gzip -S .z f", "gzip -r dir", "gunzip f.gz", "gzip --keep f")

    def test_tail_may_not_follow(self):
        self.block_bash("tail -f f", "tail -F f", "tail -5f f", "tail --follow f",
                        "tail --follow=name f", "tail --fol f", "tail --f f", "tail --retry f")  # fmt: skip
        self.allow_bash("tail -n 100 f", "tail -c 10 f", "tail --max-unchanged-stats=5 f")

    def test_sort_may_not_write_or_run_a_program(self):
        self.block_bash("sort -o out.txt f", "sort -uo out.txt f", "sort --output=x f",
                        "sort --output x f", "sort --out=x f", "sort --o=x f",
                        "sort --compress-program=gzip f", "sort --compress-prog=sh f",
                        "sort --co=sh f")  # fmt: skip
        self.allow_bash("sort f", "sort -k1 f", "sort -S 1G f", "sort -t, -k2 f",
                        "sort --files0-from=list", "sort --check f")  # fmt: skip

    def test_uniq_may_read_only_one_file(self):
        self.block_bash("uniq a b", "uniq -c a b", "uniq -f 2 a b", "uniq -f2 a b",
                        "uniq --skip-fields=1 a b")  # fmt: skip
        self.allow_bash("uniq", "uniq a", "uniq -c a", "uniq -f 2 a", "uniq -f2 a",
                        "uniq -w3 a", "uniq --skip-fields=1 a", "cat f | uniq -c")  # fmt: skip

    def test_find_may_not_act(self):
        self.block_bash(
            "find . -delete", "find . -exec rm {} ;", "find . -execdir sh ;", "find . -ok rm {} ;",
            "find . -okdir rm {} ;", "find . -fprint out", "find . -fprintf out %p", "find . -fls out",
        )
        self.allow_bash("find .", "find . -name '*.json'", "find . -type f -printf '%p\\n'")

    def test_tree_may_not_write(self):
        self.block_bash("tree -o out.txt", "tree -H . -o out.html", "tree --output=x")
        self.allow_bash("tree", "tree -a -L 2", "tree -d")

    def test_file_may_not_compile_magic(self):
        self.block_bash("file -C -m my.magic", "file -C", "file --compile -m x")
        self.allow_bash("file f", "file -i f", "file -m magic target", "file -b f")

    def test_date_may_not_set_the_clock(self):
        self.block_bash("date -s 2020-01-01", "date --set=2020-01-01", "date --se=x")
        self.allow_bash("date", "date +%s", "date -u", "date -R", "date -Iseconds", "date -r f")

    def test_rg_may_not_run_a_program(self):
        self.block_bash("rg --pre sh foo", "rg --pre=sh foo", "rg --hostname-bin sh foo",
                        "rg --hostname-bin=sh foo")  # fmt: skip
        self.allow_bash("rg foo", "rg -n foo", "rg --pre-glob '*.md' foo", "rg -z foo")


class BashGitTests(GuardTestCase):
    def test_git_reads_allowed(self):
        self.allow_bash(
            "git status", "git status --porcelain", "git log", "git log --oneline --graph",
            "git log -p", "git diff", "git diff --stat", "git diff --no-index a b", "git show",
            "git ls-files", "git ls-tree HEAD", "git rev-parse HEAD", "git shortlog -s",
            "git blame f", "git describe --always", "git cat-file -p HEAD", "git grep foo",
            "git grep -n foo",
        )

    def test_git_branch_remote_config(self):
        self.allow_bash("git branch", "git branch -a", "git branch -vv", "git branch --all",
                        "git remote", "git remote -v", "git remote get-url origin",
                        "git config --get user.name", "git config --list", "git config -l")  # fmt: skip
        self.block_bash("git branch newbranch", "git branch -D x", "git branch --list x",
                        "git remote add x y", "git remote set-url origin x",
                        "git config user.name x", "git config --unset x")  # fmt: skip

    def test_git_global_options_are_stripped(self):
        self.allow_bash("git -C ../other status", "git --no-pager log",
                        "git -C ../other --no-pager diff")  # fmt: skip
        self.block_bash("git", "git -C", "git --no-pager")

    def test_git_write_subcommands_blocked(self):
        self.block_bash("git commit -m x", "git checkout main", "git add -A", "git push",
                        "git reset --hard", "git stash", "git clean -fd", "git difftool")  # fmt: skip

    def test_git_output_and_pager_options_blocked(self):
        # --output writes a file; -O / --open-files-in-pager (and abbreviations) run a program.
        self.block_bash(
            "git log --output=x", "git diff --output x", "git show --output=x",
            "git grep -O echo foo", "git grep -Oecho foo", "git grep -iOecho foo",
            "git grep --open-files-in-pager=echo foo", "git grep --open=echo foo",
        )

    def test_git_version(self):
        self.allow_bash("git --version")


class BashP3Tests(GuardTestCase):
    def test_p3_read_subcommands(self):
        for base in ("uv run p3", "uv run python -m p3", "python -m p3", "python3 -m p3", "py -m p3", "p3"):
            for sub in ("next", "check", "report"):
                with self.subTest(command=f"{base} {sub}"):
                    self.assertAllow(bash(f"{base} {sub}"))
        self.allow_bash(
            "uv run p3 check --final", "python -m p3 report --configs c0-baseline,final",
            "uv run p3 compare --list", "python -m p3 next --root ..",
            "uv run p3 --help", "python -m p3 check -h", "p3 --version", "p3", "p3 bench --help",
        )

    def test_p3_write_or_model_subcommands_blocked(self):
        for sub in ("bench", "score", "snapshot x", "new-topic x", "rehash",
                    "compare", "compare --reveal s", "compare --resume s", "compare c0 final --job teach"):  # fmt: skip
            for base in ("uv run p3", "python -m p3", "p3"):
                with self.subTest(command=f"{base} {sub}"):
                    self.assertBlock(bash(f"{base} {sub}"))

    def test_compare_list_cannot_smuggle_reveal(self):
        self.block_bash("uv run p3 compare --list --reveal s", "p3 compare --reveal s --list")

    def test_python_only_runs_module_p3(self):
        self.block_bash("python -m http.server", "python -c 'print(1)'", "python -I -m p3 next",
                        "python -mp3 next", "python script.py", "python")  # fmt: skip

    def test_py_launcher_version_selectors(self):
        self.allow_bash("py -3 -m p3 next", "py -3.12 -m p3 check", "py -m p3 report")
        self.block_bash("py -0", "py -3 -c x")

    def test_python_full_path_and_exe(self):
        self.allow_bash("C:/Tools/Python311/python.exe -m p3 next", "python.exe -m p3 check",
                        "/usr/bin/python3 -m p3 next")  # fmt: skip

    def test_uv_run_options(self):
        self.allow_bash(
            "uv run -q p3 next", "uv run --offline p3 check", "uv run --no-project p3 next",
            "uv run --frozen p3 next", "uv run --project . p3 next", "uv run --directory . p3 next",
            "uv run --offline python -m p3 next",
        )
        self.block_bash(
            "uv run --with requests p3 next", "uv run --with=requests p3 next",
            "uv run --script x.py", "uv run x.py", "uv run python -c x", "uv run", "uv tool run x",
            "uv run python -m http.server",
        )

    def test_versions(self):
        self.allow_bash("uv --version", "python --version", "python -V", "python3 --version",
                        "py --version", "git --version", "claude --version", "claude -v",
                        "gh --version")  # fmt: skip


class BashGhTests(GuardTestCase):
    def test_gh_read_subcommands(self):
        self.allow_bash("gh run list", "gh run list --limit 3", "gh run view 1", "gh repo view",
                        "gh auth status")  # fmt: skip

    def test_gh_other_subcommands_blocked(self):
        self.block_bash("gh run rerun 1", "gh run download 1", "gh run watch", "gh pr create",
                        "gh repo clone x", "gh -R x run list")  # fmt: skip


if __name__ == "__main__":
    unittest.main()
