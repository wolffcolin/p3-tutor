# Agent architecture Resources

## Knowledge

- [Anthropic Engineering: "Effective context engineering for AI agents"](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  Primary source for context rot, attention budget, compaction, note-taking, just-in-time retrieval and sub-agents. Use for: anything about what belongs in an agent's context.
- [Claude docs: Context windows](https://platform.claude.com/docs/en/build-with-claude/context-windows)
  What counts toward the window, how history accumulates across turns, overflow behaviour. Use for: token and cost reasoning.
- [Claude docs: Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
  The client-side file memory, its six commands, security cautions, the multi-session pattern. Use for: designing notes between sessions.
- [Claude docs: Compaction](https://platform.claude.com/docs/en/build-with-claude/compaction)
  Server-side summarize-and-continue for long conversations. Use for: long-session design.
- [Anthropic: "Contextual Retrieval"](https://www.anthropic.com/news/contextual-retrieval)
  RAG pipeline, hybrid keyword plus embedding search, measured failure rates, and the 200,000-token rule of thumb for skipping retrieval. Use for: choosing and defending a retrieval design.

## Wisdom (Communities)

- r/AI_Agents on Reddit (not opened this session; named in search coverage only)
  Builders post architecture questions and post-mortems. Use for: sanity-checking designs. Noisy, so weigh against the sources above.
