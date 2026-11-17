# Agent architecture Resources

## Knowledge

- [Article: "Effective context engineering for AI agents" (Anthropic Engineering)](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  Context rot, just-in-time retrieval, compaction, note-taking, sub-agents. Use for: what to keep in context, memory and retrieval choices.
- [Docs: "Context windows" (Anthropic)](https://platform.claude.com/docs/en/build-with-claude/context-windows)
  What counts toward the window and how history accumulates across turns. Use for: token and cost reasoning.
- [Docs: Memory tool (Anthropic)](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
  File-based memory across sessions. Use for: designing what the assistant saves between visits.
- [Article: "Building effective agents" (Anthropic)](https://www.anthropic.com/research/building-effective-agents)
  Workflows versus agents, the augmented LLM, and "start simple". Use for: architecture arguments at design reviews.

## Wisdom (Communities)

- The learner's own senior design team and design reviews are the practice venue so far. No outside community has been chosen yet.

## Gaps

- A high-trust, beginner-level source on retrieval and chunking (keyword versus semantic search) for long manuals.
