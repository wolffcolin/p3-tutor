# Agent architecture Resources

## Knowledge

- [Article: "Effective context engineering for AI agents" (Anthropic Engineering)](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  Attention budget, context rot, compaction, note-taking, just-in-time retrieval, sub-agents. Use for: any decision about what stays in context and what is saved outside it.
- [Docs: Context windows (Claude Platform)](https://platform.claude.com/docs/en/build-with-claude/context-windows)
  What counts toward the window, how turns accumulate, token counting, overflow. Use for: cost and limit questions.
- [Article: "Contextual Retrieval" (Anthropic Engineering)](https://www.anthropic.com/engineering/contextual-retrieval)
  Embeddings, BM25, chunk context loss, measured failure rates, when to skip RAG. Use for: designing how the assistant finds a manual page.
- [Docs: Compaction (Claude Platform)](https://platform.claude.com/docs/en/build-with-claude/compaction)
  Server-side summarizing of long conversations. Use for: long sessions near the limit.
- [Docs: Prompt caching (Claude Platform)](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
  Lowers the price of a repeated prefix. Use for: budget planning.
- [Docs: Memory tool (Claude Platform)](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#multisession-software-development-pattern)
  A pattern for storing state across sessions. Use for: the student-record design.

## Gaps

- No community for agent builders has been vetted yet; add one when found.
