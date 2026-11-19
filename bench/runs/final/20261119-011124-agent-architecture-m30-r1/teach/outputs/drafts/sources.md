# Sources check for O3 (context and memory)

## Verified claims
1. Stateless API, full history resent: SUPPORTED. https://platform.claude.com/docs/en/build-with-claude/working-with-messages : "The Messages API is stateless, which means that you always send the full conversational history." (A beta "message threads" feature can keep it server-side; ignore.)
2. Context = tokens included when sampling: SUPPORTED. Engineering article: "Context refers to the set of tokens included when sampling from a large-language model."
3. What fills the window: SUPPORTED. https://platform.claude.com/docs/en/build-with-claude/context-windows : system prompt, every message incl. tool results, tool definitions, and the output all count; each turn's output becomes next turn's input.
4. Context rot: SUPPORTED. Article: as context grows, "the model's ability to accurately recall information ... decreases"; context-windows page names it "context rot". "Smallest set of high-signal tokens" is a direct quote.
5. Tool result clearing, compaction: SUPPORTED. Article calls tool result clearing "one of the safest lightest touch forms of compaction"; compaction = summarising a conversation nearing the window limit.
6. Sub-agent summaries: SUPPORTED. Article: sub-agent returns "a condensed, distilled summary ... (often 1,000-2,000 tokens)".
7. Memory tool client-side, six commands: SUPPORTED. Memory docs: "Claude requests file operations, and your application runs them"; commands view, create, str_replace, insert, delete, rename.
8. App duties: SUPPORTED. Path traversal validation, cap file sizes, expire old files; for sensitive data "Claude usually refuses" but add your own stripping.
9. Up-front vs just-in-time, hybrid, "do the simplest thing that works": SUPPORTED (article).
10. Announcement figures (29% context editing, 39% with memory, 84% fewer tokens): SUPPORTED, from Anthropic's own evaluations (first two "internal evaluation set for agentic search"). https://claude.com/blog/context-management

## Fix before writing
- **~4 characters per token: UNSUPPORTED.** No page read states it. Say "roughly three-quarters of a word per token in English, an estimate" only as the lesson's own rule of thumb, labelled approximate, or drop it. Token counting docs say counts are estimates and newer models' tokenizer gives about 30 percent more tokens for the same text, so the 2,000 words ~ 2,700 tokens answer is only illustrative.
- **Billing: PARTLY SUPPORTED.** Docs confirm input and output tokens are counted and billed (billing reflects your content; thinking tokens are billed as output). No page read says "cost is proportional to tokens" or gives prices. Use "you are billed per token, input and output, so more resent text costs more"; give no prices.
- **Memory loading at session start: PARTLY.** With the memory tool, the API adds an instruction and Claude itself calls view on /memories first; the app does not preload it. Word the training-record example as "the model views /memories, the app runs it", or call it a custom app step if the lesson loads it itself.
- Memory tool: `create` may overwrite or error on an existing path; do not claim it never overwrites.
- Memory is "stored" only where the app puts it; the docs say file contents live entirely in your application.

## Best links for "Go further"
- Primary: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- https://platform.claude.com/en/docs/agents-and-tools/tool-use/memory-tool
- https://platform.claude.com/docs/en/build-with-claude/context-windows
- https://claude.com/blog/context-management (the news URL redirects here)
- https://platform.claude.com/docs/en/build-with-claude/working-with-messages
