# The Guide's guard hook (see guide_guard.py): find a working Python and hand it the hook's input.
# Each candidate is tried with -c first, because on Windows "python3" can be a Microsoft Store
# placeholder that only prints a message. With no Python, the Guide's tool call is blocked.
input=$(cat)
if [ -n "$CLAUDE_PROJECT_DIR" ]; then
  guard="$CLAUDE_PROJECT_DIR/.claude/hooks/guide_guard.py"
else
  guard="$(dirname "$0")/guide_guard.py"
fi
for py in python3 python py; do
  if "$py" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" </dev/null >/dev/null 2>&1; then
    printf '%s' "$input" | "$py" "$guard"
    exit $?
  fi
done
echo "p3-guide guard: no Python found on this machine, so the Guide's tools are off; see guide/19-troubleshooting.html" >&2
exit 2
