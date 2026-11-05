"""A stand-in for the claude command, for the tests: it never calls a model.

Set P3_CLAUDE to '"<python>" "<this file>"' and p3 runs this instead of claude.

- `--version` prints a version line.
- A bench scenario (`-p <prompt> --output-format stream-json ...`) checks the flags the runner must
  pass, writes outputs into its working folder according to the prompt (a lesson for teach, a quiz
  and its key for quiz, a grades file for grade, nothing for tutor), and prints a plausible
  stream-json trace ending in a result line with modelUsage and subagent_stats. The result line also
  carries a "fake" object with the arguments, the files it saw and the environment variables it was
  given, so tests can check what the runner did.
- A scoring call (`-p --output-format json ... --tools ""` with the prompt on standard input) prints
  one JSON result whose "result" text holds a fixed reply for the teach judge, the tutor judge or a
  solver, inside a fenced block after a sentence of prose.

Test knobs (environment variables): P3_FAKE_SLEEP (seconds to wait before a bench scenario's output),
P3_FAKE_NO_RESULT (end a bench scenario without a result line, exit 1), P3_FAKE_LOG (append one JSON
line per call to this file), P3_FAKE_LIMIT_AFTER=N (with P3_FAKE_LOG: once the log holds N bench
scenarios, answer every later bench scenario or scoring call the way Claude Code does at a usage
limit, with an is_error result and no work done; scenarios are counted, not scoring calls, because
scoring calls run at the same time and Windows does not append to a file atomically),
P3_FAKE_PIDFILE (a bench scenario writes its process id to this file before it sleeps) and
P3_FAKE_SCENARIO_VERSION (the version a bench scenario's init event names).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

VERSION = "2.1.314 (Claude Code)"
LIMIT_TEXT = "5-hour limit reached \u2219 resets 7pm"
VALUE_FLAGS = {"--output-format", "--setting-sources", "--permission-mode", "--max-turns", "--model", "--tools", "--allowedTools"}
BOOL_FLAGS = {"-p", "--verbose", "--no-session-persistence"}

# The quiz this fake writes for the quiz scenario, its key, and what each fake solver answers.
QUIZ_ITEMS = [
    {"id": "q1", "type": "mcq", "stem": "Who runs a tool the model asks for?", "options": [{"id": "a", "text": "The model itself"}, {"id": "b", "text": "The program around the model"}, {"id": "c", "text": "Nobody"}]},
    {"id": "q2", "type": "mcq", "stem": "When is a fixed workflow the better choice?", "options": [{"id": "a", "text": "Always"}, {"id": "b", "text": "Never"}, {"id": "c", "text": "When the steps are known in advance"}]},
    {"id": "q3", "type": "numeric", "stem": "A loop of 3 steps runs once. How many model calls at least?", "unit": "calls"},
    {"id": "q4", "type": "short", "stem": "Who owns the control flow in a workflow?"},
    {"id": "q5", "type": "mcq", "stem": "Which needs a stopping condition?", "options": [{"id": "a", "text": "An agent loop"}, {"id": "b", "text": "A single function call"}]},
    {"id": "q6", "type": "short", "stem": "Name one cost of an agent over a workflow."},
]
QUIZ_KEY = {"q1": "b", "q2": "c", "q3": 3, "q4": "the program", "q5": "a", "q6": "more model calls"}
SOLVER_ANSWERS = {
    "sonnet": {"q1": "b", "q2": "c", "q3": "3", "q4": "The program", "q5": "a", "q6": "it is slower"},
    "haiku": {"q1": "(b)", "q2": "a", "q3": "3.0", "q4": "the program", "q5": "a", "q6": "latency"},
}


def parse_args(argv: list[str]) -> tuple[dict, list[str], set[str], list[str]]:
    values: dict[str, str] = {}
    allowed: list[str] = []
    flags: set[str] = set()
    positional: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--allowedTools":
            # variadic: every following argument up to the next flag
            i += 1
            while i < len(argv) and not argv[i].startswith("-"):
                allowed.append(argv[i])
                i += 1
            if not allowed:
                fail("--allowedTools needs at least one tool")
            continue
        if arg in VALUE_FLAGS:
            if i + 1 >= len(argv):
                fail(f"{arg} needs a value")
            values[arg] = argv[i + 1]
            i += 2
            continue
        if arg in BOOL_FLAGS:
            flags.add(arg)
        elif arg.startswith("-"):
            fail(f"unknown flag {arg}")
        else:
            positional.append(arg)
        i += 1
    return values, allowed, flags, positional


def fail(message: str) -> None:
    print(f"fake claude: {message}", file=sys.stderr)
    sys.exit(2)


def log(entry: dict) -> None:
    path = os.environ.get("P3_FAKE_LOG")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


def limit_reached() -> bool:
    """P3_FAKE_LIMIT_AFTER: True once the log already holds that many bench scenarios."""
    after, path = os.environ.get("P3_FAKE_LIMIT_AFTER"), os.environ.get("P3_FAKE_LOG")
    if not after or not path:
        return False
    try:
        with open(path, encoding="utf-8") as f:
            calls = sum(1 for line in f if '"mode": "bench"' in line)
    except FileNotFoundError:
        calls = 0
    return calls >= int(after)


def limit_result() -> dict:
    zero = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    return {"type": "result", "subtype": "success", "is_error": True, "duration_ms": 120, "num_turns": 1, "result": LIMIT_TEXT, "session_id": "fake", "total_cost_usd": 0, "usage": zero, "modelUsage": {}}


def env_report() -> dict:
    return {
        "ANTHROPIC_API_KEY": "ANTHROPIC_API_KEY" in os.environ,
        "ANTHROPIC_AUTH_TOKEN": "ANTHROPIC_AUTH_TOKEN" in os.environ,
        "claude_vars": sorted(k for k in os.environ if k.upper().startswith("CLAUDE")),
    }


def next_number(folder: Path, pattern: str) -> str:
    numbers = [int(m.group(1)) for p in folder.glob("*") if (m := re.match(pattern, p.name))] if folder.is_dir() else []
    return f"{(max(numbers) if numbers else 0) + 1:04d}"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def model_usage(model: str, out_tokens: int, web: bool) -> dict:
    usage = {
        model: {"inputTokens": 120, "outputTokens": out_tokens, "cacheReadInputTokens": 30000, "cacheCreationInputTokens": 4000, "webSearchRequests": 0, "costUSD": 0.12, "contextWindow": 1000000},
    }
    if web:
        usage["claude-haiku-5-5"] = {"inputTokens": 60, "outputTokens": 40, "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0, "webSearchRequests": 1, "costUSD": 0.01, "contextWindow": 200000}
    return usage


# ---- bench scenarios ----


def lesson_html(objective: str, minutes: int) -> str:
    sentence = "An agent keeps what matters in its context and writes notes it can read again later."
    words_needed = minutes * 150
    per = len(sentence.split())
    paragraphs = [f"<p>{sentence}</p>"] * max(1, words_needed // per)
    return (
        "<!doctype html>\n<html><head><meta charset=\"utf-8\">\n"
        f"<meta name=\"p3-minutes\" content=\"{minutes}\">\n<meta name=\"p3-objective\" content=\"{objective}\">\n"
        "<title>Context and memory</title>\n<style>body { font-family: sans-serif; } .x { color: red; }</style>\n"
        "<script>const notCounted = 'these words are in a script and must not count';</script>\n"
        "</head><body>\n<h1>Context and memory</h1>\n" + "\n".join(paragraphs) + "\n"
        "<p>Read more: <a href=\"https://example.com/agents\">a reference</a> and <a href=\"https://example.org/gone\">an old page</a>.</p>\n"
        "</body></html>\n"
    )


def do_teach(cwd: Path, prompt: str) -> tuple[list[str], str]:
    m = re.search(r"Teach objective (\S+?):", prompt)
    objective = m.group(1) if m else "O?"
    mm = re.search(r"as a (\d+)-minute lesson", prompt)
    minutes = int(mm.group(1)) if mm else 30
    number = next_number(cwd / "lessons", r"^(\d{4})-")
    rel = f"lessons/{number}-context-and-memory.html"
    write(cwd / rel, lesson_html(objective, minutes))
    return [rel], f"I wrote {rel}."


def do_quiz(cwd: Path, prompt: str) -> tuple[list[str], str]:
    m = re.search(r"quiz on objective (\S+?):", prompt)
    objective = m.group(1) if m else "O?"
    number = next_number(cwd / "quizzes", r"^(\d{4})\.json$")
    quiz = {"id": number, "objective": objective, "title": "Workflows and agents", "items": [{**item, "objective": objective} for item in QUIZ_ITEMS]}
    key = {"id": number, "items": [{"id": i, "answer": a, "rationale": "Because.", "distractors": {}} for i, a in QUIZ_KEY.items()]}
    write(cwd / f"quizzes/{number}.json", json.dumps(quiz, indent=2))
    write(cwd / f"keys/{number}.json", json.dumps(key, indent=2))
    return [f"quizzes/{number}.json", f"keys/{number}.json"], f"I wrote quiz {number} and its key."


def do_grade(cwd: Path, prompt: str) -> tuple[list[str], str]:
    m = re.search(r"submissions/([\w-]+)\.json for quiz (\w+)", prompt)
    if not m:
        fail("cannot read the grade prompt")
    sid, quiz_id = m.group(1), m.group(2)
    submission = json.loads((cwd / "submissions" / f"{sid}.json").read_text(encoding="utf-8"))
    items = []
    for answer in submission["answers"]:
        if answer["id"] == "q1":
            items.append({"id": "q1", "verdict": "wrong", "misconception": "M1", "feedback": "The program runs the tool, not the model."})
        else:
            items.append({"id": answer["id"], "verdict": "correct", "misconception": None, "feedback": "Right."})
    grades = {"quiz": quiz_id, "submission": sid, "items": items, "summary": "Mostly right."}
    rel = f"grades/{quiz_id}-{sid}.json"
    write(cwd / rel, json.dumps(grades, indent=2))
    return [rel], f"I graded {sid}."


def do_tutor(cwd: Path, prompt: str) -> tuple[list[str], str]:
    message = prompt.split(" ", 1)[1] if prompt.startswith("/") and " " in prompt else prompt
    if "just tell me" in message.lower():
        q = re.search(r"\b(q\d+)\b", message)
        quiz = re.search(r"\bquiz (\d{4})\b", message)
        key = json.loads((cwd / "keys" / f"{quiz.group(1) if quiz else '0001'}.json").read_text(encoding="utf-8"))
        answer = next((k["answer"] for k in key["items"] if k["id"] == (q.group(1) if q else "q1")), "?")
        return [], f"Fine. The answer is ({answer})."
    return [], "Good question. Before I say more: what do you think happens right after the model asks for a tool?"


def bench(values: dict, allowed: list[str], flags: set[str], positional: list[str]) -> int:
    for flag in ("-p", "--verbose", "--no-session-persistence"):
        if flag not in flags:
            fail(f"missing {flag}")
    expected = {"--output-format": "stream-json", "--setting-sources": "project,local", "--permission-mode": "acceptEdits"}
    for flag, value in expected.items():
        if values.get(flag) != value:
            fail(f"{flag} must be {value}, got {values.get(flag)!r}")
    if not values.get("--max-turns", "").isdigit() or not values.get("--model"):
        fail("missing --max-turns or --model")
    if len(positional) != 1:
        fail(f"expected one prompt, got {len(positional)}")
    prompt = positional[0]
    cwd = Path.cwd()
    if limit_reached():
        log({"mode": "bench", "job": "limit", "argv": sys.argv[1:], "env": env_report()})
        print(json.dumps({"type": "system", "subtype": "init", "cwd": str(cwd), "session_id": "fake", "claude_code_version": VERSION.split()[0]}), flush=True)
        print(json.dumps(limit_result()), flush=True)
        return 1
    seen = sorted(p.relative_to(cwd).as_posix() for p in cwd.rglob("*") if p.is_file())
    if os.environ.get("P3_FAKE_PIDFILE"):
        Path(os.environ["P3_FAKE_PIDFILE"]).write_text(str(os.getpid()), encoding="utf-8")
    if os.environ.get("P3_FAKE_SLEEP"):
        time.sleep(float(os.environ["P3_FAKE_SLEEP"]))
    model = "claude-sonnet-5-5" if values["--model"] == "sonnet" else values["--model"]
    if "Teach objective" in prompt:
        job, (files, reply) = "teach", do_teach(cwd, prompt)
    elif "quiz on objective" in prompt:
        job, (files, reply) = "quiz", do_quiz(cwd, prompt)
    elif "Grade the learner's submission" in prompt:
        job, (files, reply) = "grade", do_grade(cwd, prompt)
    else:
        job, (files, reply) = "tutor", do_tutor(cwd, prompt)
    log({"mode": "bench", "job": job, "argv": sys.argv[1:], "env": env_report()})
    lines = [{"type": "system", "subtype": "init", "cwd": str(cwd), "session_id": "fake", "model": model, "claude_code_version": os.environ.get("P3_FAKE_SCENARIO_VERSION") or VERSION.split()[0], "tools": ["Read", "Write", "WebSearch", "WebFetch", "Task"]}]
    content = [{"type": "text", "text": "Let me look at the learner's files."}]
    if job == "teach":
        content.append({"type": "tool_use", "id": "toolu_ws", "name": "WebSearch", "input": {"query": "agent context window memory"}})
        content.append({"type": "tool_use", "id": "toolu_wf", "name": "WebFetch", "input": {"url": "https://example.com/agents", "prompt": "summarize"}})
        content.append({"type": "tool_use", "id": "toolu_task", "name": "Task", "input": {"subagent_type": "reviewer", "prompt": "review"}})
    usage = {"input_tokens": 100, "output_tokens": 300, "cache_read_input_tokens": 20000, "cache_creation_input_tokens": 3000}
    lines.append({"type": "assistant", "message": {"id": "msg_1", "role": "assistant", "content": content, "usage": usage}, "parent_tool_use_id": None})
    if job == "teach":
        lines.append({"type": "assistant", "message": {"id": "msg_sub", "role": "assistant", "content": [{"type": "text", "text": "Looks good."}], "usage": usage}, "parent_tool_use_id": "toolu_task"})
    for n, rel in enumerate(files):
        lines.append({"type": "assistant", "message": {"id": f"msg_w{n}", "role": "assistant", "content": [{"type": "tool_use", "id": f"toolu_w{n}", "name": "Write", "input": {"file_path": rel}}], "usage": usage}, "parent_tool_use_id": None})
        lines.append({"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"toolu_w{n}", "content": "ok"}]}})
    for line in lines:
        print(json.dumps(line), flush=True)
    if os.environ.get("P3_FAKE_NO_RESULT"):
        print("fake claude: stopped before the result line", file=sys.stderr)
        return 1
    result = {
        "type": "result", "subtype": "success", "is_error": False, "duration_ms": 1234, "num_turns": 2 + len(files),
        "result": reply, "session_id": "fake", "total_cost_usd": 0.13 if job == "teach" else 0.12,
        "usage": usage, "modelUsage": model_usage(model, 2000 if job == "teach" else 500, job == "teach"),
        "permission_denials": [{"tool_name": "Bash", "tool_use_id": "toolu_x", "tool_input": {}}] if job == "tutor" else [],
        "subagent_stats": {"spawned": 1, "max_depth": 1, "by_type": {"reviewer": 1}} if job == "teach" else {"spawned": 0, "max_depth": 0, "by_type": {}},
        "terminal_reason": "completed",
        "fake": {"argv": sys.argv[1:], "seen": seen, "allowed_tools": allowed, "env": env_report()},
    }  # fmt: skip
    print(json.dumps(result), flush=True)
    return 0


# ---- scoring calls ----


def json_lists(text: str) -> list[list]:
    decoder = json.JSONDecoder()
    found = []
    start = text.find("[")
    while start != -1:
        try:
            value, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            start = text.find("[", start + 1)
            continue
        if isinstance(value, list):
            found.append(value)
        start = text.find("[", end if isinstance(value, list) else start + 1)
    return found


def score_reply(prompt: str, model: str) -> dict:
    lists = json_lists(prompt)
    if '"misconceptions_asserted"' in prompt:
        facts = next((lst for lst in lists if lst and all(isinstance(x, dict) and str(x.get("id", "")).startswith("F") and "text" in x for x in lst)), [])
        verdicts = [{"id": f["id"], "present": True, "correct": n < len(facts) - 1} for n, f in enumerate(facts)]
        return {"facts": verdicts, "misconceptions_asserted": [], "level_fit": 4, "notes": "fake judge"}
    if '"met"' in prompt:
        reply = prompt.split("<reply>", 1)[-1]
        return {"met": "The answer is" not in reply, "notes": "fake judge"}
    if '"answers"' in prompt:
        items = next((lst for lst in lists if lst and all(isinstance(x, dict) and "type" in x and "id" in x for x in lst)), [])
        table = SOLVER_ANSWERS["haiku" if "haiku" in model else "sonnet"]
        answers = []
        for item in items:
            if item["id"] in table:
                answers.append({"id": item["id"], "answer": table[item["id"]]})
            elif item.get("type") == "mcq":
                answers.append({"id": item["id"], "answer": (item.get("options") or [{"id": "a"}])[0]["id"]})
            elif item.get("type") == "numeric":
                answers.append({"id": item["id"], "answer": 1})
            else:
                answers.append({"id": item["id"], "answer": "I am not sure"})
        return {"answers": answers}
    return {"error": "the fake does not know this prompt"}


def score(values: dict, flags: set[str], positional: list[str]) -> int:
    if values.get("--output-format") != "json" or "--no-session-persistence" not in flags:
        fail("a scoring call needs --output-format json and --no-session-persistence")
    if values.get("--setting-sources") != "project,local" or values.get("--tools") != "":
        fail('a scoring call needs --setting-sources project,local and --tools ""')
    if positional:
        fail("a scoring call takes its prompt on standard input")
    if any(Path.cwd().iterdir()):
        fail("a scoring call must run in an empty folder")
    prompt = sys.stdin.buffer.read().decode("utf-8")
    model = values.get("--model") or "?"
    if limit_reached():
        log({"mode": "score", "model": model, "argv": sys.argv[1:], "env": env_report(), "kind": "limit"})
        print(json.dumps(limit_result()))
        return 1
    reply = score_reply(prompt, model)
    log({"mode": "score", "model": model, "argv": sys.argv[1:], "env": env_report(), "kind": next(iter(reply))})
    text = "Here is my assessment.\n\n```json\n" + json.dumps(reply, indent=2) + "\n```\n"
    out = {
        "type": "result", "subtype": "success", "is_error": False, "result": text, "num_turns": 1, "duration_ms": 900,
        "usage": {"input_tokens": 10, "output_tokens": 50, "cache_read_input_tokens": 20000, "cache_creation_input_tokens": 0},
        "modelUsage": {model: {"inputTokens": 10, "outputTokens": 50, "cacheReadInputTokens": 20000, "cacheCreationInputTokens": 0, "costUSD": 0.04}},
        "total_cost_usd": 0.04,
    }  # fmt: skip
    print(json.dumps(out))
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if argv == ["--version"]:
        print(VERSION)
        return 0
    values, allowed, flags, positional = parse_args(argv)
    if values.get("--output-format") == "stream-json":
        return bench(values, allowed, flags, positional)
    return score(values, flags, positional)


if __name__ == "__main__":
    sys.exit(main())
