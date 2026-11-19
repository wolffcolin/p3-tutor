# Plan: O3 context and memory (30 min, 4,500 words)

## 1. Win and starting point
Win: Riley decides what the makerspace assistant keeps in context, what it saves between sessions, and how it finds a manual page, and justifies each choice with cost.
Knows (0001, 0002): model is text in, text out; the agent loop. Unchecked: each step is a separate call (quiz 0001 ungraded). Does not know: tokens, window, cost, memory, retrieval. Warm-up recalls 0001/0002 only.

## 2. Big picture (opens the lesson)
The model remembers nothing between calls; everything it "knows" at a step is the text sent in that call. So memory design is deciding what text to send, and every token sent costs money and attention. The lesson goes: what context is, why it grows, how to shrink it, what to store outside it, how to find a page.

## 3. Sections
| # | Title | One idea | Example / figure | Practice check | Min | Words |
|---|---|---|---|---|---|---|
| 1 | Opening | Big picture above, win stated | none | none | 1 | 150 |
| 2 | Warm-up | Recall 0001, 0002; each step is a call | Trace "Is the laser cutter free Friday?" as 2 calls | Riley says what call 2 must contain (answer: question, tool request, result) | 2 | 300 |
| 3 | Tokens and the window | Context = tokens sent per call; window = per-call token limit | Manual sentence split into tokens (rough, labelled approximate); 1 page ~1,500 tokens | Estimate tokens for a 40-page manual | 3 | 450 |
| 4 | Why cost grows per step | Each step resends all history | Fig 1; 1,000 sys + 100 question, +500/step, 4 steps | Compute step 5 input and the 5-step total | 4 | 600 |
| 5 | Attention budget, context rot | More tokens lowers recall reliability; aim for smallest high-signal set | Short: same 3 facts in 2k vs 60k tokens (no invented stats) | Why is "window is big enough" not enough? | 2 | 300 |
| 6 | Between steps | Tool results stay; clearing, then compaction | Fig 2 not here; a 1,200-token manual page cleared after use, kept as 1-line note | Choose clearing or compaction for two cases | 3 | 450 |
| 7 | Between sessions | Nothing persists unless the program saves it; notes outside the window, read back | Fig 2; training-status file read at session start | What gets written, what reads it, and when? | 3 | 450 |
| 8 | Finding the right page | Upfront vs just-in-time; hybrid | Fig 4; manual path + search tool vs embedding lookup | Pick approach for 3 data items | 4 | 600 |
| 9 | Worked example | Whole-manual paste vs retrieval, per-step sizes | Fig 3; numbers in section 6 | Riley predicts step 3 size before shown | 3 | 450 |
| 10 | Faded practice | Decide design alone | Returning student, new scenario (see 6) | Self-check against stated criteria | 3 | 450 |
| 11 | Summary and sources | Three decisions, one line each | none | none | 2 | 300 |

Minutes sum: 1+2+3+4+2+3+3+4+3+3+2 = 30. Word sum: 150+300+450+600+300+450+450+600+450+450+300 = 4,500 (150 x 30).
Each check gets short feedback in the blunt style: right answer, likely reasoning slip, fix. Not reused as quiz items.

## 4. One home per idea
- Token, context, window: 3. Per-step cost, history resend, billing sum: 4 (later sections only cite it).
- Attention budget, context rot: 5. Clearing, compaction, tool results in history: 6.
- Session persistence, structured notes: 7. Upfront, just-in-time, hybrid: 8.
- Sub-agents: one line in 6 (clean window, 1,000-2,000 token summary; multi-agent is later).
- Prompt caching: one line in 4 pointing to the Context windows doc, not taught.

## 5. Facts to cover
- Context = tokens given at sampling; no other memory between calls: 3 (the reason everything else exists).
- Token = text chunk; window = per-call limit: 3.
- Every step is a separate call resending history, previous turns kept fully, cost per step rises: 4, with the numeric example.
- Attention budget, context rot, smallest high-signal set: 5 (justifies sections 6 and 8).
- Tool result clearing lightest compaction; compaction summarizes near the limit, new window starts from summary: 6.
- Notes outside window, read back later; nothing persists unless saved: 7.
- Upfront vs just-in-time, lightweight references, Claude Code hybrid (CLAUDE.md up front, glob/grep): 8, mapped to makerspace.
- Sub-agents: 6, one line.

## 6. Examples and figures (all numbers labelled illustrative)
- Section 4 example: sys 1,000 + question 100 = 1,100 at step 1; +500 per step: 1,100, 1,600, 2,100, 2,600 = 7,400 input tokens over 4 steps; at invented $3 per million input = about 2.2 cents. Shows cost is a sum of growing contexts, not the final size.
- Fig 1: bars of context per step with the segments (system, question, accumulated results); shows growth the text numbers only list.
- Fig 2: window box (system prompt, student's question, recent results) beside storage outside (manual files, calendar, notes file); arrows for "program loads" and "program saves"; shows saved notes reach the model only when loaded.
- Fig 4: upfront (lookup, then one call) vs just-in-time (model calls search tool, loads page) timelines.
- Worked example, request "Book the laser cutter Friday 2pm and tell me the max acrylic thickness". Base 2,000 sys+tools + 100 question.
  - A, whole 60,000-token manual pasted: steps 62,100; 62,500 (training notes +400); 63,000 (calendar +500); 63,250 (booking +250); total 250,850, about 75 cents.
  - B, retrieval: 2,100; 2,500 (training notes); 3,800 (manual page +1,300); 4,300 (calendar); 4,550 (booking); total 17,250, about 5 cents. About 14.5 times cheaper, and less rot.
  - Then clear the 1,200-token page after use: show the saving at step 4 and 5 (about 1,200 less each).
- Faded practice, new scenario: student returns, asks to cancel a 3D printer slot and whether they may use the CNC router. Step 1 fully solved (what to save: training status per student, with reason); step 2 half-given (what stays in context; Riley fills in clearing choice); step 3 Riley alone (how it finds the CNC router safety page, with a cost sentence). Offer criteria, no model answer in advance.

## 7. Misconceptions (named where they bite)
- Model remembers earlier chats by itself: 3 and 7 (record 0001 floor: only trained knowledge plus given text).
- Bigger window means paste whole manuals free: 4 and 9 (cost per step) and 5 (rot).
- Saved notes are automatically seen: 7 (the program must read and insert them).
- Possible from record 0002 gap: the loop is one call; fix in 2 by showing separate calls.
