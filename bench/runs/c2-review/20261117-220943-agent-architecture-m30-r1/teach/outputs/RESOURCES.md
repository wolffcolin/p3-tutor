# Agent architecture Resources

## Knowledge

- [Anthropic Engineering: "Effective context engineering for AI agents"](https://anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  Primary source on context rot, compaction, structured note-taking, just-in-time retrieval and sub-agents. Use for: any decision about what the assistant keeps in context.
- [Claude docs: Context windows](https://platform.claude.com/docs/en/build-with-claude/context-windows)
  Official reference on what counts toward the window and how turns accumulate. Use for: token and cost reasoning, window sizes.
- [Anthropic: Contextual Retrieval](https://anthropic.com/news/contextual-retrieval)
  RAG basics (chunks, embeddings, BM25) and the lost-context failure with measured fixes. Use for: designing manual search.
- [Claude docs: Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
  Packaged approach to saving notes between sessions. Use for: per-student memory.
- [Claude docs: Compaction](https://platform.claude.com/docs/en/build-with-claude/compaction) and [Context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing)
  Summarizing history and clearing old tool results. Use for: keeping long runs within budget.

## Wisdom (Communities)

- [LangChain forum, Talking Shop](https://forum.langchain.com/c/talking-shop/12.md?page=1)
  Practitioner threads on agents and RAG. Use for: sanity-checking a design before the review.
