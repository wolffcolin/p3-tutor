# Plan: O3 context and memory (30 min, 4,500 words)

## 1. Win and starting point
Win: Riley can decide, for the makerspace assistant, what goes in the context window each step, what is saved between sessions, and how it finds the right manual page, and say why, including cost.
Knows (records 0001, 0002): a model turns text in to text out, token by token; the agent loop at a high level. Warm-up only. Does not know: what a token or context window limits, memory, retrieval. Not yet checked: that every step is a separate model call and the program runs the tools. Quiz 0001 is ungraded, so test this in the warm-up.

## 2. Big picture (opens the lesson)
The model keeps nothing. Everything it "knows" at a step is the text the program sends it in that call, and that text is limited, costs money per token, and gets worse when it is bloated. So the design job is three decisions: what to send each step (context), what to save between sessions (notes), and what to fetch on demand (retrieval).

## 3. Sections

| # | Title | One idea | Example or figure | Practice check | Min | Words |
|---|---|---|---|---|---|---|
| 1 | Opening | Win, big picture, the three decisions | none | none | 2 | 300 |
| 2 | Warm-up | Each step is a separate call; the program runs tools | Laser-cutter Friday loop from 0002 | Q: who runs the tool, and what does the model see at step 2? Answer shown | 1.5 | 225 |
| 3 | Context and tokens | Context = all tokens sent on one call; token is the unit of the limit and of the bill; window is finite | Fixed parts of the assistant's context (system prompt, tool definitions) | Sort 4 items: in the context or not | 3 | 450 |
| 4 | Every step re-sends everything | Cost and length grow each step | Figure 1; the 4-step makerspace trace with sums | Predict step 5 input if a 500-token result arrives | 4 | 600 |
| 5 | Keeping context small | Context rot; aim for the smallest set of high-signal tokens; compaction and clearing old tool results | Compact the trace after step 2 | Which item to clear, which to keep | 3.5 | 525 |
| 6 | Memory between sessions | The model keeps nothing; the program saves; notes and progress file, read back next session | Figure 2; student training record | Is "laser trained: yes" kept by the model? Name where it lives | 3.5 | 525 |
| 7 | Finding the right page | Chunk, search, return only relevant page; pre-inference vs just-in-time vs hybrid; sub-agents in one sentence | 40-page manual stuffed vs retrieved | Pick pre-inference or just-in-time for two cases | 4 | 600 |
| 8 | Worked example | Full trace, with each item labeled context, saved or retrieved | Lens change plus Friday booking, per-step table | Spot the one item that should be cleared | 3.5 | 525 |
| 9 | Faded practice | Decide context, saved or retrieved for a new case | Equipment-fault report case; first row done, then half, then Riley alone | Immediate feedback for each row | 3.5 | 525 |
| 10 | Summary | Three decisions, one line each | none | none | 1 | 150 |
| 11 | Sources | Link both Anthropic articles with what each is for | none | none | 0.5 | 75 |

Sums: minutes 2+1.5+3+4+3.5+3.5+4+3.5+3.5+1+0.5 = 30. Words 300+225+450+600+525+525+600+525+525+150+75 = 4,500 (150 x 30).

## 4. One home per idea
- Token, context, window: section 3. Re-send growth and per-step cost: section 4 only. Context rot, compaction, clearing: 5. Between-session persistence, notes, progress file: 6. Retrieval types, chunking, stuffing cost: 7. Sub-agents: one sentence in 7, flagged as a later objective. Later sections refer back.
- Section 8 adds no new idea; it applies. Section 5 returns to the trace only to show a boundary (compaction loses detail).

## 5. Facts to cover (section: reason)
- Context is the tokens given on each call; finite window (3: defines what is limited and billed).
- Each step re-sends system prompt, tool definitions, history, tool results (4: why cost and length grow).
- Context rot, attention budget, smallest set of high-signal tokens (5: why not just fill the window).
- Compaction (summarize near the limit, restart with the summary) and clearing old tool results (5: how to stay small, and its risk of losing detail).
- Model keeps nothing between calls; the program re-sends history (3 and 4); nothing persists between sessions unless saved (6).
- Structured notes, agentic memory: agent writes NOTES.md or a to-do list outside the window and reads it back (6). Progress file plus git history bridging sessions, from the harness article (6).
- Pre-inference embedding retrieval vs just-in-time with lightweight identifiers, hybrid; manual retrieval by chunk, search, return the page (7).
- Sub-agents return condensed summaries (7, one sentence).

## 6. Examples and figures
- Trace (4), illustrative numbers, label as such. Fixed: system prompt 800 plus 4 tool definitions 1,200 = 2,000; student record 120; question 50. Step 1 input 2,170, output 60 (search_manual call). Step 2 input 2,170+60+1,500 (manual page) = 3,730, output 50 (calendar call). Step 3 input 3,730+50+300 = 4,080, output 60 (book call). Step 4 input 4,080+60+150 = 4,290, output 120 (final answer). Total input 14,270 tokens, output 290. At an illustrative $3 per million input tokens, about $0.043 per request. Shows that you pay for the early items on every step.
- Figure 1 (4): bar chart of input size over steps 1 to 4 with stacked segments (fixed, history, results). Shows growth the text only states.
- Figure 2 (6, reused in 8): three boxes, context window, saved store (student records, notes), manual index. Arrows show who loads what.
- Stuffing (7): 40,000-token manual in context on all 4 steps is about 4 x 42,170 = 168,680 input tokens, about $0.51, roughly 12 times the retrieved version, and recall worse (5).
- Compaction (5): after step 2, replace the 1,500-token page with a 100-token note ("lens: step list at manual p. 14; use isopropyl wipes only").
- Faded practice (9): a student reports a broken 3D printer nozzle and the assistant must tell staff and remember it next visit.

## 7. Misconceptions
- The model remembers earlier steps or sessions by itself: bites in 3 and 6; the program re-sends history, and without saving nothing survives.
- A bigger window means stuff the whole manual in: bites in 7 with cost and rot (5).
- Notes or memory are the same as the context window: bites in 6; notes live outside, and only what is read back enters the context.
