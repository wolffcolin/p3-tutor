# Agent architecture Resources

## Knowledge

- [Anthropic Engineering: Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  Context window as a finite attention budget, context rot, just-in-time retrieval, compaction, note-taking, sub-agents. Use for: any decision about what an agent keeps in context.
- [Claude docs: Context windows](https://platform.claude.com/docs/en/build-with-claude/context-windows)
  How turns accumulate, what counts toward the window, compaction and context editing. Use for: token and cost questions.
- [Claude docs: Memory tool](https://platform.claude.com/docs/agents-and-tools/tool-use/memory-tool)
  Client-side file-based memory across sessions, the six commands, security notes, multi-session pattern. Use for: designing what is saved between sessions.
- [Anthropic Engineering: Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)
  Chunking, embeddings, BM25, contextual chunks, benchmark failure rates, "under 200k tokens skip RAG" advice. Use for: finding the right page in a long manual.

## Wisdom (Communities)

- Claude Developer Discord (found by name in search; invite link not verified)
  Use for: asking builders about memory and retrieval choices.

## Gaps

- A verified community link, and a source on workflow-versus-agent design and multi-agent trade-offs (later lessons).
