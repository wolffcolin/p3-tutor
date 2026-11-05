"""Running `claude -p`: finding the command, cleaning the environment, and reading what comes back.

Two kinds of call go through here.

- **Bench scenarios** (p3 bench): `claude -p <prompt> --output-format stream-json --verbose
  --no-session-persistence --setting-sources project,local --permission-mode acceptEdits
  --max-turns <n> --model <model>` plus `--allowedTools Glob Grep <tool> ...` with the tools the config
  allows (Glob and Grep always, see bench_tools), run in the scenario's own folder. The whole stdout stream is the trace; its last `"type": "result"`
  line is the result.
- **Scoring calls** (p3 score): `claude -p --output-format json --no-session-persistence
  --setting-sources project,local --tools "" --model <model>` with the prompt on standard input, in an
  empty temporary folder; the reply's first JSON object is the answer.

The claude command is $P3_CLAUDE when set (the path of the program, spaces and all, or a command
string split as a shell would split it, which is how the tests swap in tests/fake_claude.py), else
`claude` on the PATH.

Every call uses your Claude subscription: ANTHROPIC_API_KEY and ANTHROPIC_AUTH_TOKEN are removed from
the child's environment, and so is every variable whose name starts with CLAUDE (which Claude Code
sets when you run p3 from inside it), except CLAUDE_CONFIG_DIR, CLAUDE_CODE_OAUTH_TOKEN and
CLAUDE_CODE_GIT_BASH_PATH, which say where and how you are signed in. DISABLE_AUTOUPDATER=1 is set,
so Claude Code does not update itself halfway through a long bench run.

A call that fails because of the account or the service, not the tutor (a usage limit, a sign-in
problem, an overloaded API), is an InfraError (`infra_reason` tells them apart), and the bench and the
scorer stop rather than record it as a result. Every claude process p3 starts is stopped with p3:
on Ctrl-C or SIGTERM by kill_all(), and when p3 itself is killed, by a small watchdog process on
macOS and Linux and by a Windows job object.

Costs are the list-price figures Claude Code reports: a list-price equivalent, not what you pay on a
subscription.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from p3.util import P3Error

CLAUDE_ENV = "P3_CLAUDE"
KEY_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
KEEP_CLAUDE_VARS = ("CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_GIT_BASH_PATH")
SET_VARS = {"DISABLE_AUTOUPDATER": "1"}
COST_LABEL = "list-price equivalent, not what you pay on a subscription"
SUBAGENT_TOOLS = ("Task", "Agent")
SEARCH_TOOLS = ("Glob", "Grep")

_warned_keys: set[str] = set()
_live: set[subprocess.Popen] = set()
_live_lock = threading.Lock()
_stopping = threading.Event()


class ClaudeNotFound(P3Error):
    """No claude command to run."""


class InfraError(P3Error):
    """A claude call failed for a reason outside the tutor: a usage limit, a sign-in problem or an
    API outage. Its result measures nothing, so the bench and the scorer stop instead of recording it."""

    def __init__(self, reason: str, where: str | None = None):
        self.reason = reason
        self.where = where
        super().__init__(f"Claude stopped working{f' in {where}' if where else ''}: {reason}")


class Stopped(P3Error):
    """p3 is stopping (Ctrl-C, or an InfraError elsewhere), so no new claude process is started."""


# ---- the command ----


def _unquote(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    return token


def claude_command() -> list[str]:
    """The claude command as an argument list. $P3_CLAUDE, when set, is either the path of the
    program (used as it is, so a path with spaces needs no quotes; surrounding quotes are allowed)
    or a command string split with shlex (POSIX rules except on Windows, where quotes around a path
    with spaces are removed). Without it, the full path of `claude` on the PATH. Raises
    ClaudeNotFound with a message naming P3_CLAUDE when there is none."""
    env = os.environ.get(CLAUDE_ENV, "").strip()
    if env:
        whole = env[1:-1] if len(env) >= 2 and env[0] == env[-1] and env[0] in "\"'" and env[0] not in env[1:-1] else env
        if Path(whole).is_file():
            return [whole]
        try:
            parts = [_unquote(t) for t in shlex.split(env, posix=(os.name != "nt"))]
        except ValueError as exc:
            raise ClaudeNotFound(f"{CLAUDE_ENV} has an unmatched quote ({exc}): {env!r}; set it to the full path of the claude program, with no quotes or with a quote at each end") from None
        if parts:
            return parts
    path = shutil.which("claude")
    if not path:
        raise ClaudeNotFound(
            "Could not find the claude command. Install Claude Code (see setup.md in the course repo) and open a new terminal, "
            f"or set {CLAUDE_ENV} to the full path of the claude program."
        )
    if Path(path).suffix.lower() in (".cmd", ".bat", ".ps1"):
        # Windows runs a .cmd or .bat file through cmd.exe, which treats quotes, & | < > and % in a
        # prompt as its own syntax, so a prompt would arrive broken.
        raise ClaudeNotFound(
            f"The claude command here is {path}, a Windows script that cannot pass a prompt safely. "
            "Install Claude Code with the official installer from setup.md in the course repo so that `where claude` lists claude.exe first, "
            f"or set {CLAUDE_ENV} to the full path of claude.exe."
        )
    return [path]


def bench_tools(allowed_tools: list[str]) -> list[str]:
    """The tools a bench scenario passes with --allowedTools: Glob and Grep first, then the config's
    allow list. On macOS, Linux and WSL, Claude Code leaves Glob and Grep out of the default tool set
    and searches through Bash, which a bench run does not allow; naming them in --allowedTools brings
    them back, so every config can search its workspace the same way on every system."""
    return [*SEARCH_TOOLS, *(t for t in allowed_tools if t not in SEARCH_TOOLS)]


def bench_command(claude: list[str], prompt: str, max_turns: int, model: str, allowed_tools: list[str]) -> list[str]:
    """The command line of one bench scenario; allowed_tools is the full list from
    bench_tools()."""
    cmd = [
        *claude, "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--setting-sources", "project,local",
        "--permission-mode", "acceptEdits",
        "--max-turns", str(int(max_turns)),
        "--model", model,
    ]  # fmt: skip
    if allowed_tools:
        # One --allowedTools followed by every rule, last on the line, since it takes every word after it.
        cmd += ["--allowedTools", *allowed_tools]
    return cmd


def score_command(claude: list[str], model: str) -> list[str]:
    """The command line of one scoring call; the prompt goes on standard input."""
    return [
        *claude, "-p",
        "--output-format", "json",
        "--no-session-persistence",
        "--setting-sources", "project,local",
        "--tools", "",
        "--model", model,
    ]  # fmt: skip


# ---- the environment ----


def child_env(environ: dict[str, str] | None = None, warn: bool = True) -> dict[str, str]:
    """A copy of the environment for a claude child: without ANTHROPIC_API_KEY and ANTHROPIC_AUTH_TOKEN
    (with a one-line warning on standard error the first time either is removed) and without every
    variable whose name starts with CLAUDE, except CLAUDE_CONFIG_DIR, CLAUDE_CODE_OAUTH_TOKEN and
    CLAUDE_CODE_GIT_BASH_PATH; with DISABLE_AUTOUPDATER=1, so every scenario of a run uses the same
    Claude Code version."""
    source = dict(os.environ if environ is None else environ)
    keep_upper = {k.upper() for k in KEEP_CLAUDE_VARS}
    key_upper = {k.upper() for k in KEY_VARS}
    env = {}
    removed_keys = []
    for name, value in source.items():
        upper = name.upper()
        if upper in key_upper:
            if value:
                removed_keys.append(upper)
            continue
        if upper.startswith("CLAUDE") and upper not in keep_upper:
            continue
        env[name] = value
    for name, value in SET_VARS.items():
        for existing in [k for k in env if k.upper() == name]:
            del env[existing]
        env[name] = value
    new = [k for k in removed_keys if k not in _warned_keys]
    if warn and new:
        _warned_keys.update(new)
        print(f"removed {' and '.join(sorted(new))} so the bench uses your Claude subscription", file=sys.stderr)
    return env


# ---- running a process ----


@dataclass
class Proc:
    returncode: int | None
    timed_out: bool
    seconds: float
    stdout: bytes
    stderr: bytes


# The watchdog that starts claude on macOS and Linux. It runs in the new session p3 makes for each
# claude, starts claude there, and blocks reading a pipe whose other end only p3 holds. The pipe
# reaches end-of-file however p3 ends, a crash or SIGKILL included, and then the watchdog kills its
# whole process group: claude and every tool it started.
WATCHDOG = r"""
import os, signal, subprocess, sys, threading
fd = int(sys.argv[1])
try:
    child = subprocess.Popen(sys.argv[2:])
except OSError as exc:
    sys.stderr.write("p3-watchdog: cannot start %s: %s\n" % (sys.argv[2], exc))
    sys.exit(127)
def watch():
    try:
        while os.read(fd, 4096):
            pass
    except OSError:
        pass
    try:
        os.killpg(os.getpgid(0), signal.SIGKILL)
    except OSError:
        pass
threading.Thread(target=watch, daemon=True).start()
code = child.wait()
sys.exit(code if code >= 0 else 128 - code)
"""
WATCHDOG_MARK = b"p3-watchdog: cannot start "
_job = None  # Windows: (kernel32, job handle) once made, False when it cannot be made


def _windows_job():
    """A Windows job object that kills every process in it when p3 exits (its last handle closes),
    however p3 exits; None when it cannot be made."""
    global _job
    if _job is None:
        _job = False
        try:
            import ctypes
            from ctypes import wintypes

            class Basic(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64), ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD),
                ]  # fmt: skip

            class Extended(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", Basic), ("IoInfo", ctypes.c_ulonglong * 6), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]  # fmt: skip

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            kernel32.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
            kernel32.SetInformationJobObject.restype = wintypes.BOOL
            kernel32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
            kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
            kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
            kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
            job = kernel32.CreateJobObjectW(None, None)
            if job:
                info = Extended()
                info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                if kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):  # JobObjectExtendedLimitInformation
                    _job = (kernel32, job)
                else:
                    kernel32.CloseHandle(job)
        except (OSError, AttributeError, ValueError, TypeError):
            _job = False
    return _job or None


def _join_job(proc: subprocess.Popen) -> None:
    """On Windows, put a new child in p3's job object, so it cannot outlive p3 (best effort)."""
    if os.name != "nt":
        return
    job = _windows_job()
    if job is None:
        return
    kernel32, handle = job
    process = kernel32.OpenProcess(0x0100 | 0x0001, False, proc.pid)  # PROCESS_SET_QUOTA | PROCESS_TERMINATE
    if process:
        kernel32.AssignProcessToJobObject(handle, process)
        kernel32.CloseHandle(process)


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill a process and every process it started (claude runs tools and subagents as children)."""
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        proc.kill()
    except OSError:
        pass


def kill_all() -> None:
    """Kill every claude process this p3 process started that is still running (on Ctrl-C, SIGTERM
    or an InfraError), and start no new one until reset_stop()."""
    with _live_lock:
        _stopping.set()
        procs = list(_live)
    for proc in procs:
        _kill_tree(proc)


def reset_stop() -> None:
    """Allow new claude processes again (p3 bench and p3 score start with this)."""
    _stopping.clear()


def stopping() -> bool:
    """True after kill_all(), until reset_stop()."""
    return _stopping.is_set()


def run_process(cmd: list[str], cwd: Path, env: dict[str, str], timeout: float, stdin_text: str | None = None) -> Proc:
    """Run a command in `cwd` with `env`, standard input from `stdin_text` (or nothing), until it ends
    or `timeout` seconds pass (then it is killed with its children). Output is collected through
    temporary files, so a long trace never fills a pipe. Raises Stopped when p3 is stopping (after
    kill_all), so nothing new starts once a stop has begun.

    On macOS and Linux the command runs in a new session under the watchdog above; on Windows it
    joins p3's job object. Either way it ends with p3, even when p3 is killed outright."""
    start = time.perf_counter()
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        argv, kwargs = list(cmd), {}
        guard_read = guard_write = None
        if os.name != "nt":
            kwargs["start_new_session"] = True
            if sys.executable:
                guard_read, guard_write = os.pipe()
                argv = [sys.executable, "-I", "-c", WATCHDOG, str(guard_read), *cmd]
                kwargs["pass_fds"] = (guard_read,)
        try:
            with _live_lock:
                if _stopping.is_set():
                    raise Stopped("p3 is stopping, so it starts no new claude process")
                try:
                    proc = subprocess.Popen(
                        argv, cwd=str(cwd), env=env, stdout=out, stderr=err,
                        stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL, **kwargs,
                    )  # fmt: skip
                except OSError as exc:
                    raise ClaudeNotFound(f"could not start {cmd[0]}: {exc}; set {CLAUDE_ENV} to the full path of the claude program") from None
                _live.add(proc)
        except BaseException:
            if guard_write is not None:
                os.close(guard_write)
            raise
        finally:
            if guard_read is not None:
                os.close(guard_read)  # the watchdog holds its own copy
        _join_job(proc)
        writer = None
        if stdin_text is not None:

            def feed():
                try:
                    proc.stdin.write(stdin_text.encode("utf-8"))
                    proc.stdin.close()
                except OSError:
                    pass

            writer = threading.Thread(target=feed, daemon=True)
            writer.start()
        timed_out = False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_tree(proc)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
        finally:
            with _live_lock:
                _live.discard(proc)
            if guard_write is not None:
                os.close(guard_write)
        if writer is not None:
            writer.join(timeout=5)
        seconds = time.perf_counter() - start
        out.seek(0)
        err.seek(0)
        stdout, stderr = out.read(), err.read()
        if guard_read is not None and proc.returncode == 127 and stderr.startswith(WATCHDOG_MARK):
            detail = stderr[len(WATCHDOG_MARK) :].decode("utf-8", errors="replace").strip()
            raise ClaudeNotFound(f"could not start {detail}; set {CLAUDE_ENV} to the full path of the claude program")
        return Proc(proc.returncode, timed_out, seconds, stdout, stderr)


def version_check(claude: list[str]) -> tuple[str | None, str]:
    """(the first line of `claude --version`, or None when it does not answer; what went wrong,
    in one line, when it did not)."""
    try:
        done = subprocess.run(
            [*claude, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, env=child_env(warn=False), stdin=subprocess.DEVNULL,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    lines = [line.strip() for line in (done.stdout or "").splitlines() if line.strip()]
    if done.returncode == 0 and lines:
        return lines[0], ""
    problem = next((line.strip() for line in (done.stderr or "").splitlines() if line.strip()), "")
    return None, problem or f"exit code {done.returncode} and no version line"


def claude_version(claude: list[str]) -> str | None:
    """The first line of `claude --version`, or None when it does not answer."""
    return version_check(claude)[0]


# ---- failures outside the tutor ----

INFRA_RE = re.compile(
    r"usage limit|limit reached|hit your limit|rate[ _-]?limit|overloaded|credit balance|"
    r"invalid api key|please run /login|not logged in|oauth token|authentication[ _-]?error|"
    r"api error:?\s*(?:401|403|429|5\d\d)\b|connection error",
    re.IGNORECASE,
)
INFRA_STATUS = frozenset({401, 403, 429, 500, 502, 503, 504, 529})


def infra_reason(result: dict | None, stderr: str = "") -> str | None:
    """Why a claude call failed for a reason outside the tutor (a usage limit, a sign-in problem, an
    API outage), in Claude Code's own words; None when it did not fail, or failed for another reason
    (a timeout, max turns, a crash). Only a result with is_error, or no result at all, is read, so a
    lesson or a reply that talks about rate limits is never mistaken for one."""
    texts = []
    if isinstance(result, dict):
        if not result.get("is_error") or result.get("subtype") == "error_max_turns":
            return None
        text = result.get("result") if isinstance(result.get("result"), str) else ""
        status = result.get("api_error_status")
        if isinstance(status, int) and not isinstance(status, bool) and status in INFRA_STATUS:
            return _first_line(text) or f"API error {status}"
        texts.append(text)
    texts.append(stderr or "")
    for text in texts:
        match = INFRA_RE.search(text)
        if match:
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            return _first_line(text[line_start : line_end if line_end != -1 else len(text)])
    return None


def _first_line(text: str) -> str:
    line = next((x.strip() for x in str(text or "").splitlines() if x.strip()), "")
    return line[:300]


# ---- reading results ----


def stream_events(text: str) -> list[dict]:
    """The JSON objects of a stream-json trace, one per line (lines that do not parse are skipped)."""
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def init_version(events: list[dict]) -> str | None:
    """The Claude Code version a stream's system/init event names, when it names one."""
    for event in events:
        if event.get("type") == "system" and event.get("subtype") == "init":
            for key in ("claude_code_version", "version"):
                if isinstance(event.get(key), str) and event[key].strip():
                    return event[key].strip()
            return None
    return None


def last_result(events: list[dict]) -> dict | None:
    """The last event with "type": "result", or None."""
    for event in reversed(events):
        if event.get("type") == "result":
            return event
    return None


def _num(value) -> float:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def usage_totals(result: dict | None) -> tuple[dict, float | None, list[str]]:
    """(tokens, cost_usd_list, models) from a result: tokens {"input", "output", "cache_read",
    "cache_write"} and the list-price cost summed over every model in modelUsage (which counts
    subagents and web search, which "usage" leaves out), falling back on "usage" and "total_cost_usd"."""
    tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    if not isinstance(result, dict):
        return tokens, None, []
    usage = result.get("modelUsage")
    if isinstance(usage, dict) and usage:
        cost = 0.0
        has_cost = False
        for per in usage.values():
            if not isinstance(per, dict):
                continue
            tokens["input"] += int(_num(per.get("inputTokens")))
            tokens["output"] += int(_num(per.get("outputTokens")))
            tokens["cache_read"] += int(_num(per.get("cacheReadInputTokens")))
            tokens["cache_write"] += int(_num(per.get("cacheCreationInputTokens")))
            if isinstance(per.get("costUSD"), (int, float)):
                cost += per["costUSD"]
                has_cost = True
        if not has_cost and isinstance(result.get("total_cost_usd"), (int, float)):
            cost, has_cost = float(result["total_cost_usd"]), True
        return tokens, (round(cost, 6) if has_cost else None), sorted(usage)
    plain = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    tokens["input"] = int(_num(plain.get("input_tokens")))
    tokens["output"] = int(_num(plain.get("output_tokens")))
    tokens["cache_read"] = int(_num(plain.get("cache_read_input_tokens")))
    tokens["cache_write"] = int(_num(plain.get("cache_creation_input_tokens")))
    cost = result.get("total_cost_usd")
    return tokens, (round(float(cost), 6) if isinstance(cost, (int, float)) else None), []


@dataclass
class StreamStats:
    """What a trace says about tool use: web searches and fetches, and subagents."""

    web_searches: int = 0
    web_fetches: int = 0
    search_queries: list[str] = field(default_factory=list)
    fetch_urls: list[str] = field(default_factory=list)
    subagents: dict = field(default_factory=lambda: {"spawned": 0, "max_depth": 0, "by_type": {}})


def stream_stats(events: list[dict], result: dict | None) -> StreamStats:
    """Count the WebSearch and WebFetch tool calls in a trace (subagents' included) and take the
    subagent counts from the result's subagent_stats, or from the Task/Agent calls when it has none."""
    stats = StreamStats()
    seen: set[str] = set()
    spawned_types: dict[str, int] = {}
    for event in events:
        if event.get("type") != "assistant":
            continue
        message = event.get("message") if isinstance(event.get("message"), dict) else {}
        for block in message.get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            block_id = str(block.get("id") or "")
            if block_id:
                if block_id in seen:
                    continue
                seen.add(block_id)
            name = block.get("name")
            data = block.get("input") if isinstance(block.get("input"), dict) else {}
            if name == "WebSearch":
                stats.web_searches += 1
                if isinstance(data.get("query"), str):
                    stats.search_queries.append(data["query"])
            elif name == "WebFetch":
                stats.web_fetches += 1
                if isinstance(data.get("url"), str):
                    stats.fetch_urls.append(data["url"])
            elif name in SUBAGENT_TOOLS:
                kind = str(data.get("subagent_type") or "general-purpose")
                spawned_types[kind] = spawned_types.get(kind, 0) + 1
    if stats.web_searches == 0 and isinstance(result, dict) and isinstance(result.get("modelUsage"), dict):
        stats.web_searches = int(sum(_num((m or {}).get("webSearchRequests")) for m in result["modelUsage"].values() if isinstance(m, dict)))
    sub = result.get("subagent_stats") if isinstance(result, dict) else None
    if isinstance(sub, dict):
        stats.subagents = {
            "spawned": int(_num(sub.get("spawned"))),
            "max_depth": int(_num(sub.get("max_depth"))),
            "by_type": dict(sub.get("by_type")) if isinstance(sub.get("by_type"), dict) else {},
        }
    elif spawned_types:
        stats.subagents = {"spawned": sum(spawned_types.values()), "max_depth": 1, "by_type": spawned_types}
    return stats


def first_json_object(text: str) -> dict | None:
    """The first JSON object in a model's reply, inside a fenced code block or not; None when there is none."""
    if not isinstance(text, str):
        return None
    decoder = json.JSONDecoder()
    start = text.find("{")
    while start != -1:
        try:
            value, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
            continue
        if isinstance(value, dict):
            return value
        start = text.find("{", start + 1)
    return None


# ---- one scoring call ----


@dataclass
class Reply:
    """A scoring call's answer: the first JSON object of the reply (None on an error), the reply text,
    the error, the tokens and list-price cost it took, and the model asked."""

    data: dict | None
    text: str
    error: str | None
    tokens: int
    cost_usd_list: float
    model: str
    seconds: float


def ask_json(prompt: str, model: str, timeout: float = 600) -> Reply:
    """Ask `model` one question with no tools, in an empty temporary folder, and parse the first JSON
    object of the reply. Raises InfraError when the call failed for a reason outside the question
    (a usage limit, a sign-in problem, an API outage), since every later call would fail the same way."""
    cmd = score_command(claude_command(), model)
    with tempfile.TemporaryDirectory(prefix="p3-score-", ignore_cleanup_errors=True) as empty:
        proc = run_process(cmd, Path(empty), child_env(), timeout, stdin_text=prompt)
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    if proc.timed_out:
        return Reply(None, "", f"no reply within {int(timeout)} s", 0, 0.0, model, proc.seconds)
    data = None
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        result = last_result(stream_events(stdout))
        data = result
    if not isinstance(data, dict):
        reason = infra_reason(None, stderr + "\n" + stdout)
        if reason:
            raise InfraError(reason, f"a scoring call to {model}")
        detail = (stderr.strip() or stdout.strip() or "no output")[:300]
        return Reply(None, "", f"unreadable reply: {detail}", 0, 0.0, model, proc.seconds)
    tokens, cost, _models = usage_totals(data)
    total = sum(tokens.values())
    text = data.get("result") if isinstance(data.get("result"), str) else ""
    reason = infra_reason(data, stderr)
    if reason:
        raise InfraError(reason, f"a scoring call to {model}")
    if data.get("is_error"):
        reason = text or data.get("subtype") or "error"
        return Reply(None, text, str(reason)[:300], total, cost or 0.0, model, proc.seconds)
    obj = first_json_object(text)
    if obj is None:
        return Reply(None, text, "no JSON object in the reply", total, cost or 0.0, model, proc.seconds)
    return Reply(obj, text, None, total, cost or 0.0, model, proc.seconds)
