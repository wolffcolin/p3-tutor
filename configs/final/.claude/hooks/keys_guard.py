#!/usr/bin/env python3
"""PreToolUse guard: keep the answer keys in keys/ away from the main conversation.

Claude Code sends the tool call as JSON on stdin. Inside a subagent the input
carries "agent_type" (the subagent's name); in the main conversation it does not.
Exit 2 blocks the call and shows stderr to the model; exit 0 lets it through.
Every other outcome is decided here on purpose, so a surprise never lets a call by.
"""
import fnmatch
import json
import re
import sys

ALLOWED_AGENTS = {"grader"}

# keys/ written as a path: keys/0001.json, ./keys/x, /abs/keys/x, keys\x (after normalising).
KEYS_DIR = re.compile(r"(?<![\w.-])keys/")
# keys as a whole word on its own: ls keys, cd keys, find keys -name ..., and one alternative
# of a brace glob such as {lessons,quizzes,keys}/* or {keys,lessons}/*, or the end of a path.
KEYS_BARE = re.compile(r"""(?:^|[\s"'=(;&|<>,{/])keys(?=$|[\s"')\;&|<>,}/])""")

MESSAGE = (
    "Blocked: keys/ holds the quiz answer keys and is closed to this conversation. "
    "Grading reads them in the grader subagent, so start /grade instead of opening a key yourself."
)


def block(why):
    sys.stderr.write(MESSAGE + " (" + why + ")\n")
    sys.exit(2)


def norm(text):
    return str(text).replace("\\", "/").lower()


def hits_keys(text, bare):
    t = norm(text)
    if KEYS_DIR.search(t) or (bare and KEYS_BARE.search(t)):
        return True
    # a glob that could expand to keys: k*/0001.json, ke?s/..., */0001.json
    for tok in re.split(r"""[\s"'=(;&|<>]+""", t):
        if any(c in tok for c in "*?[") and fnmatch.fnmatch("keys", tok.split("/")[0]):
            return True
    return False


def main():
    try:
        data = json.load(sys.stdin)
        tool = data.get("tool_name", "")
        args = data.get("tool_input") or {}
        agent = data.get("agent_type")
        if not isinstance(args, dict):
            raise ValueError("tool_input is not an object")
    except Exception as exc:  # unreadable input: refuse rather than guess
        block("the guard could not read the tool call: %s" % exc)

    if agent in ALLOWED_AGENTS:
        sys.exit(0)

    if tool == "Read":
        fields = [(args.get("file_path"), True)]
    elif tool == "Grep":
        # the pattern is text to find, so only a path-shaped keys/ in it counts
        fields = [(args.get("path"), True), (args.get("glob"), True), (args.get("pattern"), False)]
    elif tool == "Glob":
        fields = [(args.get("pattern"), True), (args.get("path"), True)]
    elif tool in ("Bash", "PowerShell"):
        fields = [(args.get("command"), True)]
    else:
        sys.exit(0)

    for value, bare in fields:
        if value and hits_keys(value, bare):
            block("%s reached for keys/" % tool)
    sys.exit(0)


if __name__ == "__main__":
    main()
