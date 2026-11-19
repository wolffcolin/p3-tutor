# Plan: O3 context and memory (30 min, 4,500 words)

## 1. Win and starting point
Win: Riley can sketch what the makerspace assistant keeps in context, what it saves between sessions, and how it finds the right manual page, with a reason for each.
Knows (0001, 0002, NOTES): text in/text out; the agent loop. Does not know: tokens, context window, cost, memory, retrieval. Re-teach nothing except as warm-up.

## 2. Big picture (opens the lesson, before any chunk)
The model sees only the text in front of it on each call, and that text has a size limit and a price. So the design question is what text goes in on each step, what is written down for next time, and what is fetched only when needed. Three places, three jobs: the window, saved notes, retrieval.

## 3. Sections
| # | Title | One idea | Example/figure | Practice check | Min | Words |
|---|---|---|---|---|---|---|
| 1 | Opening | The three places text can live | none | none | 1 | 150 |
| 2 | Warm-up | Each step is a separate call; the program runs tools | Recall of "Is the laser cutter free Friday?" trace | Riley says who runs check_calendar and how many model calls the trace made, before reading the answer | 2 | 300 |
| 3 | Tokens and the context window | Window = all text the model can reference, incl. its own reply; measured in tokens; working memory, not training data | One manual sentence split into rough tokens (labeled approximate) | Does the model's reply count toward the window? | 3 | 450 |
| 4 | Everything counts, every step re-sends | Input of each call = system prompt + tool defs + all history + new message; cost grows | Figure 1 | Predict: is step 4's input bigger or smaller than step 3's, and why | 3 | 450 |
| 5 | Worked example: the four-step loop | Cumulative input re-sent, as arithmetic | Numbers in part 6 | Riley recomputes one step before it is shown | 4 | 600 |
| 6 | Context rot and curating | More is not better: attention budget, rot; lightest fix is clearing old tool results, heavier is compaction | Clearing the 1,500-token page (part 6) | Which tool result would you clear, and what stays? | 4 | 600 |
| 7 | Memory between sessions | Nothing persists unless the program saves it; notes in storage outside the window, read back later | Student record saved after a visit, read at next start | What does the program write when a student passes training? | 3 | 450 |
| 8 | Finding the right page | Pre-retrieval vs just-in-time vs hybrid; sub-agents in one sentence only | Figure 2 | Which identifier does the assistant keep in context? | 4 | 600 |
| 9 | Faded practice and the sketch | Apply all three to a new request | Part A arithmetic, part B sketch (part 6) | The task itself | 4 | 600 |
| 10 | Summary | Three places, one reason each | none | none | 1 | 150 |
| 11 | Sources | Where to read more | Two links, one line each | none | 1 | 150 |

Minutes sum: 1+2+3+3+4+4+3+4+4+1+1 = 30. Word budgets sum: 150+300+450+450+600+600+450+600+600+150+150 = 4,500 (= 150 x 30).

## 4. One home per idea
- Token, context window, working memory vs training data: section 3.
- What counts toward the window; re-send of history; cost growth; each step a separate call (recalled in 2, extended here): section 4.
- Cumulative input arithmetic: section 5.
- Context rot, attention budget, clearing, compaction: section 6.
- Persistence between sessions, structured notes: section 7.
- Retrieval, pre vs just-in-time, hybrid, sub-agent summaries: section 8.
Later sections point back, never re-explain.

## 5. Facts to cover (section: reason)
- Window includes the model's own reply and is not training data (3: defines "memory" inside the model).
- System prompt, messages, tool results, tool defs, output all count (4: shows where fixed cost comes from).
- Each turn re-sends all history; each step is a model call (4, worked in 5: why a long loop costs more than its final size, which matters for the budget).
- Context rot, attention budget (6: reason to curate despite big windows).
- Clearing old tool results as lightest compaction; compaction summarizes near the limit and continues in a fresh window (6: two levers, different cost).
- Nothing persists across sessions unless saved; note-taking such as NOTES.md or to-do lists (7: how the assistant remembers training status).
- Pre-retrieval (embedding search before inference) vs just-in-time (keep file paths and queries, load with tools), hybrid often best (8: how it finds the page).
- Sub-agents return condensed summaries (8: one sentence; multi-agent is a later lesson).

## 6. Examples and figures
- Worked example (5): tools search_manual, check_calendar, book_slot; request "book the laser cutter Friday, check its manual for the max material thickness". Show a running-sum table.
  - Fixed prefix: system prompt 800 + tool defs 700 + user message 60 = 1,560.
  - Step 1 input 1,560; output 60 (calls search_manual); result, a manual page, 1,500.
  - Step 2 input 1,560+60+1,500 = 3,120; output 70 (check_calendar); result 400.
  - Step 3 input 3,120+70+400 = 3,590; output 60 (book_slot); result 100.
  - Step 4 input 3,590+60+100 = 3,750; output 120 (final answer).
  - Total input billed 12,020 (1,560+3,120+3,590+3,750); total output 310; final context 3,870, so input billed is about 3.1 times the final context. Price only as an explicit illustration ($1 per million input tokens gives about $0.012), never a real rate.
- Clearing (6): replace the 1,500-token page with an 80-token note after step 2. Step 3 input 1,700+70+400 = 2,170; step 4 input 2,170+60+100 = 2,330; saves 1,420 on each later step. Show what is lost (the page text) and the cue to re-fetch it.
- Figure 1 (4): stacked bars for steps 1-4 at 1,560 / 3,120 / 3,590 / 3,750, segments for fixed prefix, model outputs, tool results. Shows growth the sentence "history is re-sent" does not.
- Figure 2 (8): three columns (in the window / saved outside / retrieved on demand), one item each: system prompt; one student-record line; a manual file path plus section id. Shows where data lives and when it enters the window. The rest is left for Riley's sketch.
- Section 7 record: small JSON such as {"student":"s-1042","laser_cutter":"trained","3d_printer":"not trained"}; invented, labeled as an example; written and read by the program.
- Practice (9): Part A, request "book the band saw", with a read_student_record step. Step 1 input 1,560, output 50, result 120. Step 2 input 1,730, output 60, result 1,200 (manual). Step 3 input 2,990 given, output 80, result 100. Step 4 input 3,170, total input 9,450. Fade: steps 1-2 shown, step 3 half-filled, step 4 and total blank. Optional: swap the 1,200 page for an 80-token note and step 4 becomes 2,050. Part B: Riley sketches three lists (in context, saved, retrieved) with a reason each; a short model answer follows the task.

## 7. Misconceptions (named where they bite)
- The model remembers between sessions by itself: section 7 (each session starts blank; the program saves and reloads).
- A bigger window means no curation: section 6 (context rot).
- Retrieval means the model searching its training: section 8 (the search runs in a tool over our files and results enter the window; ties to 0001).
- In section 4: "the model remembers earlier steps" is also false; earlier steps are re-sent text.
