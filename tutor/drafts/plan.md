# Plan: O1, multi-agent orchestration (15 min)

## 1. Win and starting point
Win: given a complex software task, the learner sketches an orchestrator-worker split (what the lead does, what each subagent is told, what comes back) and says whether splitting is worth it.
Starting point: CS master's student, comfortable with single agents and tool calling. NOTES.md: a model is stateless between sessions, memory is only loaded text (reuse this as the hook for "a subagent starts fresh"). Wants brief answers, no math. No MISSION.md, records or earlier lessons exist, so nothing is re-taught.

## 2. Big picture (opens the lesson)
One agent has one context window and works one step at a time. A team splits a big task: a lead agent plans, workers run in parallel, the lead combines their results. This lesson shows how to write the split, and when it costs more than it returns.

## 3. Sections
| # | Title | One idea | Example / figure | Practice check | Min | Words |
|---|---|---|---|---|---|---|
| 1 | Opening | Goal and big picture | none | none | 1 | 150 |
| 2 | Predict first | Surface intuition about cost and fit | Prediction: "migrate one API across 40 modules; would 10 parallel agents be 10x cheaper or costlier?" | Learner commits to a guess; answered in S5 | 1 | 150 |
| 3 | The orchestrator-worker shape | Lead plans, spawns, synthesizes | Fig 1 | Name the lead's three verbs | 1.5 | 225 |
| 4 | What each subagent is told | Four-part brief | Vague vs complete brief | Spot which of the four parts is missing | 1.5 | 225 |
| 5 | Subagents in Claude Code | Isolated context, summary back | Fig 2, a 6-line agent file | Why can't it see the chat? | 1.5 | 225 |
| 6 | How many agents | Effort scaling | Three-row tier table | Pick a tier for a task | 1.5 | 225 |
| 7 | When splitting pays | Cost versus fit | Fit checklist; answers S2 | Judge two tasks | 1.5 | 225 |
| 8 | Worked example | Full split of a task | API migration, Fig 3 | Learner predicts one step before it is shown | 2.5 | 375 |
| 9 | Faded practice | Learner does the split | New task, half-filled template | Learner completes the rest | 2 | 300 |
| 10 | Summary and sources | Recap, links | none | One-line self-test | 1 | 150 |

Minutes sum: 1+1+1.5+1.5+1.5+1.5+1.5+2.5+2+1 = 15. Word budgets sum: 150+150+225+225+225+225+225+375+300+150 = 2250 (150 x 15).

## 4. One home per idea
- Orchestrator-worker, lead/synthesis, CitationAgent: S3.
- Four-part brief, duplicated work and gaps: S4.
- Own context, fresh start, summary back, Markdown+frontmatter, description-based delegation, nesting depth 3, 20 concurrent: S5.
- Effort tiers: S6.
- 4x and 15x tokens, the 90.2% result, fit and poor fit, coding caveat, coordination weakness: S7.
- Sequential dependency: S8. Later sections only refer back.

## 5. Facts to cover
- S3: lead plans, parallel subagents, lead synthesizes; CitationAgent as a separate agent that attributes claims (shows roles can be split by job, not just by topic).
- S4: objective, output format, tools/sources, task boundary; vague briefs caused duplicated work and gaps (reason for the four parts).
- S5: own window, system prompt, tools, permissions; fresh start (ties to the stateless note); only a summary returns, so the main context stays clean; name and description required, tools optional; delegation follows the description; nesting depth 3; 20 concurrent; each subagent spends its own tokens (leads into cost).
- S6: 1 agent with 3-10 calls; 2-4 agents with 10-15 calls each; 10+ with divided duties. Reason: the lead should size effort to the task.
- S7: about 4x (agent vs chat), about 15x (multi-agent vs chat); Opus 4 lead with Sonnet 4 workers beat single Opus 4 by 90.2% on their internal research eval (state it as their eval, not a general law). Good fit: parallelizable, exceeds one window, many tools, value covers the cost. Poor fit: shared context, many dependencies, most coding has fewer parallel parts, weak real-time coordination.

## 6. Examples and figures
- Running example (S2, S4, S8, S9): migrating a payments API from v1 to v2 across a repo. Numbers: 40 modules in 4 groups of 10; lead plus 4 module workers, 1 read-only explorer, 1 test-runner/reviewer.
- Fig 1 (S3): lead box, arrows out to workers, arrows back labelled "summary". Shows direction and what travels, which prose cannot.
- Fig 2 (S5): main context versus subagent context, with only a summary crossing. Shows why the parent stays clean.
- Fig 3 (S8): the split as a timeline: explorer first (sequential), 4 workers in parallel, then tests and review (sequential). Shows which steps wait.
- S4 contrast: a vague line ("update the payments code") against a full message: objective (move modules 11-20 to v2 client), format (list of files changed plus open questions, under 200 words), tools (read, edit, grep; no network; do not touch tests), end (stop at module boundary; do not touch shared config). Shows the failure of overlap.
- S8 mechanical steps: (1) explorer maps callers, returns a summary; (2) the shared v2 client wrapper is written first by the lead, because the workers depend on it: the one sequential dependency; (3) workers run in parallel; (4) test-runner runs and reports failures by module; (5) lead synthesizes. Count tokens relatively (about 15x chat), no arithmetic beyond that.
- S9: a different task (add audit logging to 12 services), template with the lead steps filled and subagent briefs and the sequential step blank. Healthcare is optional; use it only if it fits (for example a record-lookup service), otherwise leave it out.

## 7. Misconceptions
- S5: "a subagent sees the chat" (NOTES.md stateless point). Correct: it starts fresh.
- S4: "a short delegation is enough, the worker will figure it out". Correct: vague briefs duplicated work.
- S7: "more agents is always better or faster". Correct: about 15x tokens, and coding has fewer parallel parts.
- S6: "always spawn many workers". Correct: simple facts need one agent.
- S3: parallel means no ordering. Correct: dependencies stay sequential (confirmed in S8).
