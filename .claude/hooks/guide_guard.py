"""The Guide's guard: a PreToolUse hook that keeps the Guide (claude --agent p3-guide) read-only.

.claude/agents/p3-guide.md registers it, through guide_guard.sh, which finds a Python to run it.
Claude Code sends the hook's input as JSON on stdin. Exit 0 lets the tool call run; exit 2 blocks
it, and the Guide reads the one line printed on stderr. The Guide's tools are Read, Glob, Grep and
Bash, and the rules are:

- Read, Grep and Glob: anything except a blind comparison's key, bench/compare/*.key.json.
- PowerShell: nothing (the Guide uses Bash).
- Bash: only the read-only commands below, joined by &&, ||, ;, | or new lines, with no command or
  process substitution, no NAME=value prefix, no background &, and no output redirect except to
  /dev/null and descriptor copies such as 2>&1. It also refuses any reference to the blind
  comparison folder (bench/compare/), and the options of the allowed commands that would write a
  file, follow forever or run a program (sort -o/--output and --compress-program, tail -f/--follow,
  uniq's second file operand, tree -o, file -C, date -s, git grep -O/--open-files-in-pager and
  --output, and rg --pre/--hostname-bin), including their GNU abbreviations.

A blind key can still turn up in a search over the whole repo; the Guide's instructions forbid
looking, and this guard is a second line, not a proof. Course-owned: tests/test_guide_guard.py
covers every rule.
"""

from __future__ import annotations

import json
import shlex
import sys

GUIDE = "p3-guide"
KEY = ".key.json"

# commands that only read, with the options that would make them write, follow or hang
READERS = {
    "cd", "pwd", "ls", "cat", "head", "tail", "wc", "grep", "egrep", "fgrep", "rg", "sort", "uniq",
    "cut", "tr", "echo", "printf", "which", "file", "stat", "du", "tree", "basename", "dirname",
    "realpath", "date", "diff", "cmp", "zcat", "find", "gzip", "gunzip",
}
FIND_ACTIONS = {"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf", "-fls"}
GIT_READS = {"status", "log", "diff", "show", "ls-files", "ls-tree", "rev-parse", "shortlog", "blame", "describe", "cat-file", "grep"}
GIT_BRANCH_FLAGS = {"-a", "-r", "-v", "-vv", "--all", "--list", "--show-current"}
P3_READS = {"next", "check", "report"}
P3_HELP = {"--help", "-h"}
UV_FLAGS = {"-q", "--quiet", "--no-project", "--offline", "--frozen", "--no-sync", "--locked"}
UV_VALUE_FLAGS = {"--project", "--directory"}
PYTHONS = {"python", "python3", "py"}
SEPARATORS = {"&&", "||", ";", "|", "|&"}
TO_FILE = {">", ">>", "&>", "&>>", ">|"}
NULL = {"/dev/null"}  # the Guide's Bash is Git Bash on every OS, where "nul" is an ordinary file


class Blocked(Exception):
    """A command the Guide may not run; the message says why."""


def name_of(word: str) -> str:
    """A command's name without its folder or .exe, lowercased: C:/x/python.exe is python."""
    base = word.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return base[:-4] if base.endswith(".exe") else base


def _opt_prefix(arg: str, full: str) -> bool:
    """True when arg is --<p> or --<p>=..., with <p> a non-empty prefix of full: a GNU long option
    written out or abbreviated. sort --output, --out and --o all mean --output, so all three match
    _opt_prefix(arg, "output"). This over-matches an ambiguous abbreviation (which the tool would
    reject anyway), which only ever blocks more, never less."""
    if not arg.startswith("--"):
        return False
    name = arg[2:].split("=", 1)[0]
    return bool(name) and full.startswith(name)


def split(command: str) -> list[list[str]]:
    """The command's segments (one simple command each), redirects to /dev/null and descriptor
    copies taken out; raises Blocked for anything the Guide may not use."""
    for bad, why in (("$(", "command substitution"), ("`", "command substitution"), ("<(", "process substitution"), (">(", "process substitution")):
        if bad in command:
            raise Blocked(why)
    lex = shlex.shlex(command.replace("\r", "").replace("\n", " ; "), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        tokens = list(lex)
    except ValueError as exc:  # an unclosed quote
        raise Blocked(f"the command cannot be read ({exc})") from None
    segments: list[list[str]] = [[]]
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if tok in SEPARATORS:
            segments.append([])
        elif tok == "&":
            raise Blocked("a background command (&)")
        elif tok in TO_FILE:
            if nxt is None or nxt.lower() not in NULL:
                raise Blocked("an output redirect to a file")
            _drop_descriptor(segments[-1])
            i += 1
        elif tok == ">&":
            if nxt is None or not (nxt.isdigit() or nxt.lower() in NULL):
                raise Blocked("an output redirect to a file")
            _drop_descriptor(segments[-1])
            i += 1
        elif tok == "<":
            if nxt is None:
                raise Blocked("an input redirect with no file")
            i += 1  # reading a file is fine
        elif tok and all(ch in "();<>|&" for ch in tok):
            raise Blocked(f"the shell operator {tok}")
        else:
            segments[-1].append(tok)
        i += 1
    return [s for s in segments if s]


def _drop_descriptor(segment: list[str]) -> None:
    """2>/dev/null tokenizes as 2, >, /dev/null; the 2 is the redirect's, not an argument."""
    if segment and segment[-1].isdigit():
        segment.pop()


def check_p3(args: list[str]) -> None:
    """The arguments after p3 (or python -m p3)."""
    if args[:1] == ["--root"]:
        args = args[2:]
    if not args or args[0] in P3_HELP | {"--version"}:
        return
    sub, rest = args[0], args[1:]
    if rest and all(a in P3_HELP for a in rest):
        return
    if sub in P3_READS:
        return
    if sub == "compare" and "--list" in rest and not {"--reveal", "--resume"} & set(rest):
        return
    raise Blocked(f"p3 {sub} is not one of the Guide's read-only commands (next, check, report, compare --list)")


def check_python(args: list[str]) -> None:
    if args and args[0].startswith("-") and args[0][1:2].isdigit():  # py -3 or py -3.12
        args = args[1:]
    if args in (["--version"], ["-V"]):
        return
    if args[:2] == ["-m", "p3"]:
        check_p3(args[2:])
        return
    raise Blocked("Python may run only -m p3 with a read-only command, or --version")


def check_uv(args: list[str]) -> None:
    if args == ["--version"]:
        return
    if not args or args[0] != "run":
        raise Blocked("uv may run only uv run p3 with a read-only command, or uv --version")
    rest = args[1:]
    while rest and rest[0].startswith("-"):
        if rest[0] in UV_FLAGS:
            rest = rest[1:]
        elif rest[0] in UV_VALUE_FLAGS and len(rest) > 1:
            rest = rest[2:]
        else:
            raise Blocked(f"the uv option {rest[0]}")
    if rest[:1] == ["p3"]:
        check_p3(rest[1:])
    elif rest and name_of(rest[0]) in PYTHONS:
        check_python(rest[1:])
    else:
        raise Blocked("uv run may run only p3 or python -m p3")


def check_git(args: list[str]) -> None:
    while args and args[0] in ("-C", "--no-pager"):
        args = args[2:] if args[0] == "-C" else args[1:]
    if args == ["--version"]:
        return
    if not args:
        raise Blocked("git with no command")
    sub, rest = args[0], args[1:]
    for opt in rest:
        # --output writes a file; --open-files-in-pager (and its abbreviations) and -O (bare,
        # with an attached command such as -Oecho, or bundled such as -iOecho) run a program.
        if opt.startswith(("--output", "--open")):
            raise Blocked(f"git {sub} with an option that writes a file or opens files in a program")
        if opt.startswith("-") and not opt.startswith("--") and "O" in opt:
            raise Blocked(f"git {sub} with -O, which opens the files it finds in a program")
    if sub in GIT_READS:
        return
    if sub == "branch" and all(a in GIT_BRANCH_FLAGS for a in rest):
        return
    if sub == "remote" and (rest in ([], ["-v"]) or rest[:1] == ["get-url"]):
        return
    if sub == "config" and rest[:1] and rest[0] in ("--get", "--get-all", "--list", "-l"):
        return
    raise Blocked(f"git {sub} is not one of the Guide's read-only git commands")


def check_uniq(args: list[str]) -> None:
    """uniq's second file operand is an OUTPUT file it overwrites (uniq [INPUT [OUTPUT]]), so at
    most one operand may be read. -f/-s/-w and their long forms take the next token as a value, and
    a short bundle ending in f, s or w (such as -cf 2) takes the token after it, so neither counts."""
    operands = skip = after_ddash = 0
    for a in args:
        if skip:
            skip = 0
        elif after_ddash:
            operands += 1
        elif a == "--":
            after_ddash = 1
        elif a in ("-f", "-s", "-w", "--skip-fields", "--skip-chars", "--check-chars"):
            skip = 1  # its value is the next token
        elif a.startswith("-") and a != "-":
            skip = 1 if (not a.startswith("--") and a[-1] in "fsw") else 0
        else:
            operands += 1
    if operands > 1:
        raise Blocked("uniq that writes its output to a second file (it may read at most one file)")


def check_reader(name: str, args: list[str]) -> None:
    short = [a for a in args if a.startswith("-") and not a.startswith("--")]
    if name == "tail" and (any("f" in a.lower() for a in short) or any(_opt_prefix(a, "follow") or _opt_prefix(a, "retry") for a in args)):
        raise Blocked("tail that follows a file, which never ends")
    if name == "sort" and (any("o" in a for a in short) or any(_opt_prefix(a, "output") or _opt_prefix(a, "compress-program") for a in args)):
        raise Blocked("sort that writes its output to a file or runs a compression program")
    if name == "uniq":
        check_uniq(args)
    if name == "find" and FIND_ACTIONS & set(args):
        raise Blocked("find with an action that runs a command, deletes or writes")
    if name == "tree" and (any("o" in a for a in short) or any(_opt_prefix(a, "output") for a in args)):
        raise Blocked("tree that writes its output to a file (-o)")
    if name == "file" and (any("C" in a for a in short) or any(_opt_prefix(a, "compile") for a in args)):
        raise Blocked("file -C, which compiles a magic file to disk")
    if name == "date" and (any(a.startswith("-s") for a in short) or any(_opt_prefix(a, "set") for a in args)):
        raise Blocked("date that sets the system clock (-s/--set)")
    if name == "rg" and any(a in ("--pre", "--hostname-bin") or a.startswith(("--pre=", "--hostname-bin=")) for a in args):
        raise Blocked("rg with a preprocessor or hostname command, which runs a program")
    if name in ("gzip", "gunzip"):
        flags = [a for a in args if a.startswith("-")]
        safe = {"--stdout", "--to-stdout", "--list", "--test"}
        if not any(a in safe or (not a.startswith("--") and set(a[1:]) & set("clt")) for a in flags):
            raise Blocked(f"{name} that writes files (use -c, -l or -t)")


def check_segment(words: list[str]) -> None:
    first = words[0]
    if "=" in first and not first.startswith("-") and first.split("=", 1)[0].isidentifier():
        raise Blocked("a NAME=value prefix")
    name, args = name_of(first), words[1:]
    if name in READERS:
        check_reader(name, args)
    elif name == "git":
        check_git(args)
    elif name == "uv":
        check_uv(args)
    elif name in PYTHONS:
        check_python(args)
    elif name == "p3":
        check_p3(args)
    elif name == "claude" and args in (["--version"], ["-v"]):
        pass
    elif name == "gh" and (args == ["--version"] or args[:2] in (["run", "list"], ["run", "view"], ["repo", "view"], ["auth", "status"])):
        pass
    else:
        raise Blocked(f'"{first}" is not one of its read-only commands')


def check_bash(command: str) -> None:
    low = command.replace("\\", "/").lower()  # before shlex eats the Windows backslashes
    if KEY in low:
        raise Blocked("it never opens a blind comparison's key")
    if "bench/compare" in low:  # a glob or folder read, under either slash, that sweeps up the keys
        raise Blocked("it never reads the blind comparison folder (bench/compare/); the picks stay blind until the student runs p3 compare --reveal")
    segments = split(command)
    if not segments:
        raise Blocked("an empty command")
    for words in segments:
        for word in words:
            if KEY in word.lower():  # a key path hidden by quoting, e.g. "x.key"".json", survives shlex
                raise Blocked("it never opens a blind comparison's key")
        check_segment(words)


def decide(data: dict) -> str | None:
    """None to allow the call, or the reason to block it."""
    agent = data.get("agent_type")
    if agent is not None and agent != GUIDE:
        return None
    tool = data.get("tool_name") or ""
    tool_input = data.get("tool_input") or {}
    if tool in ("Read", "Grep", "Glob"):
        named = " ".join(str(tool_input.get(k) or "") for k in ("file_path", "path", "pattern", "glob")).lower()
        if KEY in named or (tool == "Grep" and "bench/compare" in named.replace("\\", "/")):
            return "the Guide never opens a blind comparison's key (bench/compare/*.key.json); the picks stay blind until the student runs p3 compare --reveal"
        return None
    if tool == "PowerShell":
        return "the Guide uses Bash, not PowerShell"
    if tool == "Bash":
        try:
            check_bash(str(tool_input.get("command") or ""))
        except Blocked as exc:
            return (f"the Guide only reads, so it cannot run this: {exc}. "
                    "Tell the student who runs it instead: the Builder (give the exact sentence to say) or the student in a plain terminal (give the exact command).")
        return None
    if tool in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
        return "the Guide never changes a file; tell the student what to ask the Builder"
    return None


def main() -> int:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        print("p3-guide guard: could not read the hook input, so the call is blocked", file=sys.stderr)
        return 2
    reason = decide(data if isinstance(data, dict) else {})
    if reason is None:
        return 0
    print(f"p3-guide guard: {reason}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
