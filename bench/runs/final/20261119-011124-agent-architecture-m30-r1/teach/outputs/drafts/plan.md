# Plan: O3 context and memory (30 min, 4,500 words)

## 1. Win and starting point
Win: given a makerspace request, Riley sketches what is in the context at each loop step, says what is dropped, kept or saved, and picks keep, compact, write a note or retrieve a manual page, with a rough cost reason.
Knows (records 0001, 0002): the model is text in, text out; the agent loop. Quiz 0001 is ungraded, so only a short loop recall. Does not know: token, context window, cost, memory, retrieval. Has never called a model from code, so show messages as Python lists of dicts.

## 2. Big picture (opening text)
The model sees only what the program puts into each call. Everything else (earlier steps, last week's visit, the manual) must be put there, or kept elsewhere and fetched. Three places hold information: context, saved notes, retrieved sources. Each has a cost.

## 3. Sections
| # | Title | One idea | Example / figure | Practice check | Min | Words |
|---|---|---|---|---|---|---|
| 1 | Opening | Big picture above, plus the win | none | none | 1 | 150 |
| 2 | Warm-up: the loop | Each step is a separate model call | the Friday laser question, 3 steps as names only | Name who runs the tool (the program). Answer shown | 1 | 150 |
| 3 | Tokens and the context window | Context = the tokens sent in a call; tokens are what size and cost count | ~4 characters per token rule of thumb; Fig 1 | Estimate tokens of a 2,000-word manual page (~2,700). Answer shown | 3 | 450 |
| 4 | Between steps: the program resends | Calls are stateless; the messages list is the only memory, so each step's input grows | Fig 1: bar per step, small numbers, labelled illustrative | Predict step 3 input from steps 1 and 2. Answer shown | 3 | 450 |
| 5 | When history gets too long | Context rot: more tokens, worse recall. Options: clear old tool results, compact, sub-agent summary (one line, later lesson) | A 600-token manual passage cleared after use, replaced by a 40-token summary | Choose clear vs compact for 2 cases. Feedback shown | 3 | 450 |
| 6 | Between sessions: notes and the memory tool | Nothing persists unless the app stores it; notes live outside context and are read back; memory tool is client-side | Student training record saved at the end of one visit, loaded at the next; view/create calls on /memories | Which of 3 items to save (training status yes, Friday slot no). Feedback shown | 4 | 600 |
| 7 | Retrieval: finding the manual page | Up-front vs just-in-time; hybrid; simplest thing that works. Closes with the 3-places table | search_manual(machine, query) returns one passage; table: context / notes / retrieved | Place 4 items in the table. Feedback shown | 4 | 600 |
| 8 | Worked example | Trace the whole request with a token tally | Section 6 below | Pause after step 2: "what is in step 3's input?" | 5 | 750 |
| 9 | Faded practice | Apply the choices to a new request | "Book the 3D printer for my class Tuesday; what filament does the manual say?" Step 1 half-filled, then blank | Learner fills the context sketch and decisions; model answer after | 4 | 600 |
| 10 | Summary | The three places and the four choices, in 5 lines | none | none | 1 | 150 |
| 11 | Sources | The two links, one line each on what to read next | Anthropic context-engineering article; memory tool docs | none | 1 | 150 |

Sums: minutes 1+1+3+3+3+4+4+5+4+1+1 = 30. Words 150+150+450+450+450+600+600+750+600+150+150 = 4,500.

## 4. One home per idea
- Token, context window, per-token cost: s3.
- Stateless call, resending, growth per step: s4 (the formula lives here only).
- Context rot, clearing, compaction, sub-agent: s5.
- Notes, memory tool, saving across sessions, size caps, sensitive info, path validation: s6.
- Up-front vs just-in-time retrieval, hybrid: s7. Three-places table: s7.
- Stale risk of the calendar: s6 names the rule (fresh tool call), s8 shows it in step 3. Later sections only refer back.

## 5. Facts to cover
- Context = tokens included when sampling, chosen at every call: s3, because it defines the unit.
- Context rot and "smallest set of high-signal tokens": s5, as the reason to trim.
- Stateless call and resending: s4, to explain the cost growth. Writer must check wording with references-finder.
- Clear old results, compaction, sub-agent summaries: s5, as the options for long history.
- Nothing persists unless the app stores it; structured notes: s6.
- Memory tool is client-side (model requests view/create/str_replace/insert/delete/rename on /memories, the app runs them): s6, so Riley knows who does the work. Size caps, no sensitive info, path validation: s6, as app duties.
- Up-front vs just-in-time, hybrid, "simplest thing that works": s7.
- Makerspace mapping: manual by search_manual (s7), training record saved and loaded (s6), calendar by fresh call (s6 rule, s8 shown).

## 6. Examples and figures
- Fig 1 (s4): bars of input per step, each adding the previous call's output and result. Shows growth, which text alone does not. Illustrative round numbers: 1,000 system prompt and tool definitions, 20 question.
- Worked example (s8), all numbers illustrative. Request: "Am I allowed to use the laser cutter, and book it Friday?" Session start loads a 100-token training record.
  - Call 1 input 1,120 (1,000+100+20); output search_manual call, 60; result 600.
  - Call 2 input 1,780; output check_calendar, 50; result 200.
  - Call 3 input 2,030; output book call, 50; result 40.
  - Call 4 input 2,120; final answer, ~100.
  - Total input over 4 calls: 7,050 tokens. If the 40,000-token manual were pasted: 4 x 40,000 = 160,000 extra input tokens, and worse recall (s5). Cost is proportional to tokens; no real price is quoted. After the answer, the app writes a short note; the 600-token passage would be cleared first if the chat continued.
  - Show messages as a Python list, tool_use and tool_result blocks, at calls 1 and 3.
- Table (s7): context (this call, costs every step), saved notes (between sessions, loaded at start), retrieved source (fetched on demand). Columns: lives, lasts, cost, makerspace item.
- Faded practice (s9): 3D printer request, filament question; the learner gets the call 1 sketch filled, then fills calls 2 and 3 and the keep/compact/note/retrieve choices, with a model answer.

## 6b. Corrections from drafts/sources.md (override anything above)
- The "~4 characters per token / 2,000 words = 2,700 tokens" rule is NOT in a source: label it the lesson's own rough estimate ("roughly; real counts depend on the model, check with the token counting tool"), cite the Token counting docs only for measuring.
- Say "billed per token (input and output)", never "cost is proportional"; quote no prices. Cost comparisons are in tokens only.
- With the memory tool the model itself calls view /memories first; the app does not preload the record. In s6 and s8, the training record is read by a memory `view` call (a tool call at step 1), or alternatively loaded by the app into the first message when the app keeps its own database; say both are valid designs and label which the example uses. Keep worked example numbers consistent with whichever is chosen (use the app-loaded 100-token record as planned, and mention the memory-tool alternative in s6).
- Cite the Messages API docs for "stateless, full history sent each time" and the Context windows docs for what counts toward the window.

## 7. Misconceptions
- "The model remembers earlier chats on its own": s4 and s6.
- "Memory is the model learning or training": s6 (notes are files the app reads; the weights do not change; training is out of scope).
- "A bigger window means put everything in": s5 (rot, cost) and s8 (the 160,000 comparison).
- "The calendar can be remembered": s6 (stale), s8 (fresh call).
- "The model runs the memory tool": s6 (the app does).
- Check quiz 0001's results are not assumed: s2 only recalls.
