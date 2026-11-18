# Sources for O3: context and memory

## Verified claims
Context = ECE (effective-context-engineering article), HARN (harnesses article), DOCS (platform.claude.com/docs/en/build-with-claude/context-windows).

1. Context is finite: supported. ECE: "a finite resource with diminishing marginal returns". DOCS: window is "all the text a language model can reference... including the response itself".
2. Each step re-sends system prompt, tool definitions, history, tool results: supported (DOCS). "Everything in the request counts toward the context window: the system prompt, every message... (including tool results...), and your tool definitions"; each turn's input is "all previous conversation history plus the current user message".
3. Context rot, attention budget: supported (ECE; DOCS). Recall "decreases" as tokens grow; models have an "attention budget".
4. Smallest set of high-signal tokens: supported (ECE), "the smallest possible set of high-signal tokens".
5. Compaction: supported (ECE). Summarize a conversation nearing the limit and restart with the summary.
6. Clearing old tool results: supported (ECE). "One of the safest lightest touch forms of compaction". The "risk of losing detail" is the lesson's inference for summarizing, not a quote.
7. No memory between sessions: supported (HARN). "each new session begins with no memory of what came before".
8. Notes / agentic memory: supported (ECE). Notes "persisted to memory outside of the context window", e.g. a to-do list or a NOTES.md.
9. Progress file plus git history: supported (HARN). "claude-progress.txt file alongside the git history".
10. Pre-inference vs just-in-time vs hybrid: supported (ECE). "embedding-based pre-inference time retrieval"; just-in-time uses "lightweight identifiers (file paths, stored queries, web links)"; hybrid retrieves some up front.
11. Sub-agents return condensed summaries: supported (ECE). Explore with tens of thousands of tokens, return "often 1,000-2,000 tokens".

Counts: 11 checked (some merged), 11 supported, 0 partly, 0 unsupported. But see below.

## Fix before writing
- Cost trace (partly supported, mechanism only). Sources confirm the re-send and that all of it counts toward the window. None gives the lesson's token numbers or the $3 per million; keep them labelled illustrative. DOCS says prompt caching "changes what you pay for those tokens, not whether they count", so write "without caching, you pay for early items on every step", not "always".
- "The model keeps nothing between calls" is the lesson's wording. DOCS shows the API carries history only because the caller sends it. Say "the program sends the history each call".
- "Chunk, search, return the page" for manuals is not in ECE; present it as the lesson's own example of just-in-time retrieval.
- "12 times" and "recall worse" for stuffing: the 12x is the lesson's arithmetic; recall decline is supported only generally (context rot), not for a 40,000-token manual.
- Window sizes vary by model (200k to 1M, DOCS). Don't state one number as universal.

## Best links for "Go further"
- https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents (primary)
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents (sessions, progress file)
- https://platform.claude.com/docs/en/build-with-claude/context-windows (official definitions, compaction, tool-result clearing)
