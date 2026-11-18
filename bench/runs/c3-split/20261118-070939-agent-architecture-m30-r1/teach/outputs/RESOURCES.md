# Agents Resources

## Knowledge

- [Article: "Effective context engineering for AI agents" (Anthropic Engineering)](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  Primary source on context as a finite resource, context rot, compaction, tool-result clearing, notes, retrieval styles, sub-agents. Use for: anything on what goes in the context window and how to keep it small.
- [Article: "Effective harnesses for long-running agents" (Anthropic Engineering)](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
  Explains that each session starts with no memory and how a progress file plus git history bridge sessions. Use for: memory between sessions.
- [Docs: "Context windows" (Claude API docs)](https://platform.claude.com/docs/en/build-with-claude/context-windows)
  Official definition of the context window, what counts toward it (system prompt, messages, tool results, tool definitions), per-turn accumulation, context rot, compaction. Use for: definitions and the re-send mechanism.

## Wisdom (Communities)

None yet.
