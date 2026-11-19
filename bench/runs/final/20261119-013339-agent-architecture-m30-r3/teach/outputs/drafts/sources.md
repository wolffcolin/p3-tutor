# Sources for O3 (context and memory)

Pages opened: A = https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents ; B = https://platform.claude.com/docs/en/build-with-claude/context-windows.md

## Verified claims
- Window = all text the model can reference, including its own response; not the training data; "working memory": supported (B, "How the context window works").
- System prompt, every message (incl. tool results), tool definitions, and the output all count: supported (B: "Everything in the request counts toward the context window...").
- Each turn's input = all previous history plus the new message; previous turns preserved completely; output becomes input next turn: supported (B, "Progressive token accumulation", "Input-output flow").
- Context rot, more context not automatically better, curate: supported (B: "accuracy and recall degrade, a phenomenon known as context rot"; A: recall decreases as context grows).
- Attention budget: supported (A: "Every new token introduced depletes this budget by some amount").
- Tool result clearing is the lightest compaction: supported (A: "one of the safest lightest touch forms of compaction"; B lists tool result clearing under context editing).
- Compaction summarizes and restarts in a fresh window: supported (A: "summarizing its contents, and reinitiating a new context window with the summary").
- Notes persisted outside the window, e.g. NOTES.md: supported (A: "writes notes persisted to memory outside of the context window").
- Pre-retrieval (embedding-based, before inference) vs just-in-time (file paths, stored queries, links, loaded with tools): supported (A).
- Sub-agents return condensed summary, often 1,000-2,000 tokens: supported (A).

## Fix before writing
- "Hybrid often best": partly supported. A describes a hybrid (some data up front for speed, further exploration at the agent's discretion); the fetched text did not show a "best" ranking. Write "the article describes a hybrid: some data up front, the rest fetched on demand."
- "Nothing persists across sessions unless saved": partly supported. A and B only say notes outside the window can be saved and reloaded (B's tip on state artifacts for multi-session agents). Frame it as "the window starts with only what the program puts in it", not as a quoted rule.
- "Each step is a separate call": B implies it (each turn: input, then output) but does not use the phrase. Safe as "each turn sends the full history again".
- Replacing a 1,500-token page with an 80-token note: that is the lesson's design. B/A only say old tool results are cleared; do not say the docs insert a note. Do not call the 1,420 saving a documented figure.
- Token size and the "sentence split into tokens" illustration: not checked on either page; keep labeled approximate, and do not cite a tokens-per-word figure.
- Pricing: no rate was checked; keep "$1 per million" as an explicit illustration.
- Window sizes: B says up to 1M tokens depending on model (200k on others); avoid a single number.

## Best links for "Go further"
- Primary: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents (opened)
- https://platform.claude.com/docs/en/build-with-claude/context-windows.md (opened; exact mechanics)
- https://platform.claude.com/docs/en/build-with-claude/context-editing (linked from B, not opened; do not cite as verified)
