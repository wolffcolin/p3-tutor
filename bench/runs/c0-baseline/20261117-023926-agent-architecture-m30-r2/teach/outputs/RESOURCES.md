# Agent architecture Resources

## Knowledge

- [Article: "Effective context engineering for AI agents" (Anthropic Engineering)](https://anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  Context window, context rot, just-in-time retrieval, compaction, note-taking, sub-agents. Use for: anything on what goes in an agent's context and how to keep it small.
- [Article: "Managing context on the Claude Developer Platform" (Anthropic)](https://claude.com/blog/context-management)
  The memory tool (client-side, file-based) and context editing, with stated results. Use for: persisting notes between sessions and clearing stale tool results.
- [Article: "Introducing Contextual Retrieval" (Anthropic)](https://anthropic.com/research/contextual-retrieval)
  Chunking, embeddings and keyword search for long documents, with failure-rate results. Use for: finding the right page in the makerspace manuals.

## Wisdom (Communities)

- Local: the team's instructors and design-review audience
  Use for: critique of what the assistant should remember and retrieve.

## Gaps

- A beginner-level source on token counting and cost per request.
- A source on workflows versus agents and multi-agent systems (needed for later objectives).
