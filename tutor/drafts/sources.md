# Sources for O1 (multi-agent orchestration)

A = https://www.anthropic.com/engineering/multi-agent-research-system
D = https://code.claude.com/docs/en/sub-agents (first 100,000 of 116,382 characters read)

## Verified claims

- Four-part brief: supported, A: "an objective, an output format, guidance on the tools and sources to use, and clear task boundaries".
- Vague briefs caused duplicated work and gaps: supported, A: one subagent explored the 2021 chip crisis while two others duplicated work on 2025 supply chains.
- CitationAgent attributes claims: supported, A: it pinpoints where citations belong so every claim is attributed.
- Effort tiers: supported, A: "1 agent with 3-10 tool calls"; "2-4 subagents with 10-15 calls each"; "more than 10 subagents with clearly divided responsibilities".
- About 4x (agent vs chat) and about 15x (multi-agent vs chat): supported, A: "agents typically use about 4x more tokens than chat", "multi-agent systems use about 15x more".
- 90.2%: supported, A: Opus 4 lead plus Sonnet 4 subagents beat single-agent Opus 4 on their internal research eval.
- Poor fit (shared context, many dependencies, coding): supported, A: "most coding tasks involve fewer truly parallelizable tasks than research".
- Weak real-time coordination: supported, A: agents "are not yet great at coordinating and delegating to other agents in real time".
- Value must cover cost: supported, A: tasks where "the value of the task is high enough to pay for the increased performance".
- Own window, prompt, tools, permissions; fresh start; summary only: supported, D: "own context window with a custom system prompt, specific tool access, and independent permissions"; "doesn't see your conversation history"; "returns only the summary".
- Markdown with frontmatter, only name and description required, tools optional: supported, D (tools inherited if omitted).
- Delegation follows description: supported, D: "Claude uses each subagent's description to decide when to delegate".
- Nesting depth 3: supported, D: "up to three layers below the main conversation", default, configurable.
- 20 concurrent: supported, D: the 21st spawn fails with "Concurrent subagent limit reached", default, configurable.

## Fix before writing

- "Fresh start": add "except a fork, which inherits the parent conversation" (D), or say "a regular subagent".
- Nesting and 20 concurrent are defaults: write "by default".
- The lead also runs subagents synchronously, waiting for each batch (A); do not imply workers run fully asynchronously.
- The article's lead spins up 3-5 subagents in parallel; the plan's 4 workers plus 2 others fits, but do not cite the 4 and 6 as from the source.
- 90.2%: say "on Anthropic's internal research eval", not a general law.
- The tier numbers are from the research setting; for coding say "illustrative".

## Best links for "Go further"

- https://www.anthropic.com/engineering/multi-agent-research-system (primary)
- https://code.claude.com/docs/en/sub-agents (build and delegate in Claude Code)
