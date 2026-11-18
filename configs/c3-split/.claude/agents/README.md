# Subagents

This folder holds the tutor's subagents, one Markdown file per subagent, such as `.claude/agents/grader.md`.
The baseline tutor has none: you add them when you build review loops (`c2-review`), split up the teach job (`c3-split`), and keep the keys away from the tutor (`final`).
This README has no frontmatter, so Claude Code treats it as documentation, not as a subagent.

## What a subagent is

A subagent is a separate Claude with its own system prompt, its own tools and a fresh context window.
The main conversation starts one with the Agent tool and a task message it writes; the subagent does the work and returns one report.
A subagent does not see the main conversation's history, the skills it already invoked or the files it already read.
It starts with its own system prompt, the task message, the CLAUDE.md files (in the bench, only the tutor's; in your own sessions in `tutor/`, also every CLAUDE.md above it and your `~/.claude/CLAUDE.md`), a git status snapshot when it runs in a repo, and the full text of any skills its `skills` field names.
So the task message has to carry what the subagent needs, or tell it which files to read.

## The file

```markdown
---
name: quiz-reviewer
description: Reviews a draft quiz and its key for one objective and returns numbered findings. Use after drafting a quiz, before finishing.
tools: Read, Glob, Grep
model: sonnet
maxTurns: 20
---

You review one quiz and its key against the objective it serves.
(The rest of the system prompt: what to check, how to report, when to stop.)
```

The frontmatter sits between two `---` lines, and the first one must be the file's first line; the Markdown after it is the subagent's system prompt.
Only `name` and `description` are required.
Field names are case-sensitive camelCase, and Claude Code silently ignores a field it does not recognize, so a misspelled field fails without an error.

## Fields

| Field | What it does |
|---|---|
| `name` | Required. The subagent's id, such as `grader` or `quiz-reviewer`: no `:`, at most 256 characters, unique in this folder. Hooks receive it as `agent_type`. The file name does not have to match. |
| `description` | Required. When the main conversation should delegate to it: name the job and the moment. |
| `tools` | The tools it may use, as `Read, Grep, Glob` or a YAML list. Left out, it inherits every tool available to subagents, the Agent tool included, so it can start subagents of its own. |
| `disallowedTools` | Tools removed from what it would otherwise get. |
| `model` | `sonnet`, `opus`, `haiku`, a full model id, or `inherit`. Left out, it runs on the main conversation's model. |
| `maxTurns` | The most agentic turns it may take before it stops and returns what it has. |
| `skills` | Skills whose full content is loaded into its context at startup, such as `[quiz]`. Without it, the subagent can still invoke skills itself. |
| `effort` | `low`, `medium`, `high`, `xhigh` or `max`, in place of the session's effort level. |
| `permissionMode` | `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions` or `plan`. |
| `background` | `true` keeps it in the background even when Claude asks to wait for it. |
| `omitClaudeMd` | `true` starts it without the CLAUDE.md files, for a subagent that gets everything from its task message. |
| `hooks` | Hooks scoped to this subagent; they do not run in the bench (below). |
| `mcpServers`, `memory`, `isolation`, `color`, `initialPrompt`, `autoCompactWindow` | Rarely useful for a tutor; see the docs. |

The full reference is https://code.claude.com/docs/en/sub-agents.md.

## What the bench shows

I checked these against Claude Code 2.1.314, the way the bench runs it: `claude -p` in a fresh folder that was never trusted.

- **Hooks in `.claude/settings.json` fire in the bench; hooks in subagent frontmatter do not.**
  A PreToolUse hook in the project's `.claude/settings.json` blocked a tool call in a `claude -p` run in a fresh folder, which is how the bench runs every scenario.
  A subagent's frontmatter hooks run only once the folder's workspace trust dialog has been accepted, and the docs say a `-p` session never counts as trusted, so a guard in frontmatter silently does nothing in the bench.
  Put every guard in `tutor/.claude/settings.json`, and keep any script it runs under `tutor/.claude/` (for example in `.claude/hooks/`), so the script is part of the config and is copied into every scenario folder.
- **A hook can tell a subagent from the main conversation.**
  Inside a subagent, the JSON a hook receives carries `agent_type` (the subagent's `name`) and an `agent_id`; in the main conversation it carries neither.
  A PreToolUse hook that allowed reading a file only when `agent_type` was `"grader"` let a `grader` subagent read it and blocked the main conversation.
  Hooks from `.claude/settings.json` fire for a subagent's tool calls just as they do for the main conversation's.
  Remember that `Read` is not the only way to read a file: `Grep`, `Glob`, `Bash` (`cat keys/0001.json`) and, on Windows, `PowerShell` (`Get-Content keys/0001.json`) can too.
- **Subagents cost tokens, and the bench counts them.**
  Each run's `run.json` records every scenario's tokens summed over every model used, so subagents and the model behind web search are included, along with how many subagents it started, how deeply they nested, and of which types.
- **Tools have to be allowed in `tutor/.claude/settings.json`.**
  A `claude -p` run in a fresh folder ignores the project's `permissions.allow`, so the bench passes that list with `--allowedTools`, and runs with `--permission-mode acceptEdits` so file edits inside the folder go through.
  A bench run has no one to approve anything else, so a tool call that would need a permission prompt is denied and counted in `run.json` as a permission denial.
  The Agent tool, which starts a subagent, needs no allow entry, and the allow list also covers your subagents' tool calls.
  A subagent's `permissionMode` field has no effect in the bench, because a subagent started from an `acceptEdits` session runs in that mode.
- **The bench always adds Glob and Grep.**
  On macOS, Linux and WSL, Claude Code leaves the Glob and Grep tools out by default and searches with `find` and `grep` through Bash instead; naming them in `--allowedTools` brings them back.
  So the bench always passes them, and every config can search its workspace the same way on every system.
  In your own sessions in `tutor/` on those systems, searches still go through Bash, so a guard has to cover Bash as well as Glob and Grep, and on Windows PowerShell too.

## Working with subagents

- A subagent the main conversation starts runs in the background by default; in a `claude -p` session, Claude waits for it when it judges it should or when told to, so a skill that needs a subagent's report should say to wait for the report before going on.
- In your own interactive sessions in `tutor/` (the terminal, VS Code or the desktop app), Claude can wait for a subagent only once fork mode is off, and it is on by default.
  To turn it off, put `{"env": {"CLAUDE_CODE_FORK_SUBAGENT": "0"}}` in `tutor/.claude/settings.local.json`, then start `claude` again.
  That file is personal, is never part of a config and never reaches the bench, which is the point: in `claude -p`, turning fork mode off makes nested subagents start in the background instead, so putting it in `tutor/.claude/settings.json` would change how your tutor runs in the bench.
- A subagent with the Agent tool can start subagents of its own, up to three layers below the main conversation by default; give a reviewer an explicit `tools` list to keep it from starting more.
- Every file in this folder is part of the config: `p3 snapshot` copies it, and the bench copies it into every scenario folder.
