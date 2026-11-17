# Agent architecture Resources

## Knowledge

- [Article: "Effective context engineering for AI agents" (Anthropic Engineering)](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  Context as a finite resource, context rot, compaction, structured note-taking, up-front vs just-in-time retrieval, sub-agents. Use for: context, memory and retrieval decisions (objective O3), and later multi-agent trade-offs.
- [Article: "Building effective agents" (Anthropic)](https://www.anthropic.com/research/building-effective-agents)
  The augmented model (retrieval, tools, memory) as the base unit, workflows vs agents, start simple. Use for: workflow-vs-agent and architecture arguments. Note: the page says some tooling has changed since it was written.
- [Paper: "Lost in the Middle: How Language Models Use Long Contexts" (Liu et al., TACL 2024)](https://arxiv.org/abs/2307.03172)
  Shows accuracy is best when relevant information is at the start or end of a long input. Use for: why stuffing a long context is not free.

## Wisdom (Communities)

- None added yet; the learner has not said whether they want communities. Their design team and review are the first place to test ideas.

## Gaps

- A practical, code-level guide to building a manual search tool (chunking, embeddings) in Python for a beginner.
