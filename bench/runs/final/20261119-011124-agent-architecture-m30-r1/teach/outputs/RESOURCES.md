# Agent architecture Resources

## Knowledge

- [Article: "Effective context engineering for AI agents" (Anthropic Engineering)](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  Primary source on what goes into an agent's context, context rot, compaction, note-taking, just-in-time retrieval and sub-agents. Use for: anything about context and memory design.
- [Docs: Memory tool (Claude Platform)](https://platform.claude.com/en/docs/agents-and-tools/tool-use/memory-tool)
  How a client-side file memory works: the model requests file operations under /memories, the application runs them. Use for: what "memory between sessions" looks like in code, the six commands, and its security duties.
- [Announcement: "Managing context on the Claude Developer Platform" (Anthropic)](https://www.anthropic.com/news/context-management)
  Introduces context editing (clearing stale tool results) and the memory tool (redirects to claude.com/blog/context-management). Use for: why clearing old tool results helps; Anthropic's own reported results (internal evaluation figures).
- [Docs: Using the Messages API (Claude Platform)](https://platform.claude.com/docs/en/build-with-claude/working-with-messages)
  States the Messages API is stateless and the full history is sent each time. Use for: why the program resends the messages list.
- [Docs: Context windows (Claude Platform)](https://platform.claude.com/docs/en/build-with-claude/context-windows)
  What counts toward the window (system prompt, messages, tool results, tool definitions, output), how turns accumulate, context rot, compaction. Use for: the context window and per-turn growth.
- [Docs: Token counting (Claude Platform)](https://platform.claude.com/docs/en/build-with-claude/token-counting)
  Counting input tokens before a call; counts are estimates; newer tokenizer yields about 30 percent more tokens. Use for: how to measure tokens, not for a characters-per-token rule.

## Wisdom (Communities)

No community has been vetted yet.

## Gaps

- A vetted community for agent builders, to test architecture choices.
- A source for a characters-per-token rule of thumb (the ~4 characters rule is not on the pages read) and for per-token pricing for the makerspace budget.
