# Agent architecture Resources

## Knowledge

- [Article: "Effective context engineering for AI agents" (Anthropic Engineering)](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  Primary source on context rot, attention budget, just-in-time retrieval, compaction, note-taking and sub-agents. Use for: what belongs in context, and how to keep it small.
- [Docs: "Context windows" (Claude Platform Docs)](https://platform.claude.com/docs/en/build-with-claude/context-windows)
  Official description of what counts toward the window, how turns accumulate, overflow behavior. Use for: exact mechanics and limits.
- [Docs: "Memory tool" (Claude Platform Docs)](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
  Client-side file memory across sessions, command list, security notes, multisession pattern. Use for: designing and building notes.
- [Article: "Introducing Contextual Retrieval" (Anthropic)](https://www.anthropic.com/news/contextual-retrieval)
  Chunking, embeddings, BM25, hybrid retrieval, and when to skip RAG. Use for: making the manuals searchable.

## Wisdom (Communities)

No community chosen yet. The makerspace staff and the project sponsor are the most relevant real-world check for what students ask.

## Gaps

- A high-trust community for agent builders has not been vetted yet.
