# Sources check for O3 (context and memory)

Pages opened: A = https://anthropic.com/engineering/effective-context-engineering-for-ai-agents ; B = https://platform.claude.com/docs/en/build-with-claude/context-windows

## Verified claims
1. Context = set of tokens included when sampling from an LLM: supported (A): "Context refers to the set of tokens included when sampling from a large-language model."
2. Window = all text the model can reference, including its response; counts system prompt, messages, tool results, tool definitions: supported (B).
3. Each turn's input = all previous history plus the new message; previous turns preserved completely: supported (B): "previous turns are preserved completely"; "Input phase: all previous conversation history plus the current user message".
4. Output of a turn becomes input of the next: supported (B).
5. Resent history is billed as input tokens: partly supported (B). It says this explicitly for kept thinking blocks ("billed as input tokens, like the rest of the conversation history"); it does not give a per-step cost formula.
6. Attention budget and context rot (recall weakens as tokens grow): supported (A, B): "As token count grows, accuracy and recall degrade, a phenomenon known as context rot."
7. Aim for smallest high-signal token set: supported (A): "the smallest possible set of high-signal tokens that maximize the likelihood of some desired outcome."
8. Tool result clearing is lightest compaction; compaction summarizes near the limit and restarts from the summary: supported (A); B lists tool result clearing under context editing and server-side compaction as the primary strategy.
9. Notes persisted outside the window and read back: supported (A): agent "regularly writes notes persisted to memory outside of the context window".
10. Upfront vs just-in-time, lightweight identifiers, Claude Code hybrid (CLAUDE.md up front, glob/grep): supported (A).
11. Sub-agents return 1,000-2,000 token summaries: supported (A): "often 1,000-2,000 tokens".
12. Prompt caching: supported (B): caching "changes what you pay for those tokens, not whether they count" toward the window.

## Fix before writing
- "Model remembers nothing between calls": neither page states it in those words. B shows the history is resent each turn, which implies it. Say "in the API, the history is sent again each turn" and cite B; do not quote it as a statement of statelessness.
- Window size: B says up to 1M tokens depending on the model (200k on some). Do not give one fixed number. Your 60,000-token manual example fits, but label it illustrative.
- Cost per step: the doc supports growth in input per turn, not the 1,100/1,600/... figures or the $3 per million rate. Label both as invented.
- "1 page ~1,500 tokens" and the token-split example: no page read supports these. Keep "rough, illustrative" or drop.
- Sub-agent size: say "often 1,000-2,000 tokens", not a fixed rule.
- Compaction in B is server-side, beta, Claude 4.6 and later; A describes the idea generally. Teach the idea, not the beta feature.

## Best links for "Go further"
- Primary: https://anthropic.com/engineering/effective-context-engineering-for-ai-agents
- https://platform.claude.com/docs/en/build-with-claude/context-windows (history growth, what counts, caching)
- https://www.anthropic.com/research/building-effective-agents (already in RESOURCES.md; not opened this session, so only cite from the existing entry)
- Seen as links on B, not opened: memory tool, context editing, compaction pages. Not added to RESOURCES.md.
