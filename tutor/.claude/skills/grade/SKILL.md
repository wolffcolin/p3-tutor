---
name: grade
description: Grade the learner's submission to a quiz - a verdict per item, the misconception behind each miss, short direct feedback and a brief summary; use it when the learner submits answers or asks for a quiz to be graded.
argument-hint: "Which quiz or submission should I grade?"
---

# Grade

You grade one submission and write its grades file, its learning record and your notes, and nothing else: no new quiz, no lesson.

## The request

$ARGUMENTS

If the request above is empty, the request is the learner's latest message.
When the learner submits a complete set of answers to a quiz given in the chat, record them as the next `submissions/sN.json`, as `FORMATS.md` shows, and grade that.
One answer offered for checking before the quiz is handed in is not a submission: do not grade it.

## Read first

Read `FORMATS.md` (the grades file, exactly), `MISSION.md`, `PREFERENCES.md`, `NOTES.md` and every file in `learning-records/`.
Then read `.claude/skills/teach/references/GRADING.md` for the verdict rules (meaning over wording, `partial`, tolerance, misconception ids), the quiz, its key, the submission, and the lesson on the objective if there is one.
This skill sets how the feedback is written; where it differs from that guide, this skill wins.
Never write under `.claude/`.

## Verdicts and misconceptions

Follow the guide: judge what the response means, use `partial` for a half-right answer, name a misconception id only when the response shows it, and use `null` otherwise.
Never invent an id.
If you are sure the key is wrong, grade against what is right and say so in the summary.

## Write the feedback

The learner wants to be told what went wrong and how to fix it, in as few words as will do it, and reads only what is short.
Each item's feedback follows the same order, and stops when the fix is stated:

- **Correct:** one sentence, naming the reason it works.
  Add a second only for an unusual route, or for one insight that links to the next idea.
  Never restate the question or praise.
- **Partial:** one sentence on what was right, then the exact gap and the fix.
- **Wrong:** (1) the diagnosis, your best idea of where the reasoning went wrong, naming the misconception in plain words; (2) the correct idea in one or two sentences, with a small example only if the idea is new.
  Give the corrected reasoning, not a lecture on the topic.

Limits:

- Aim for 25 to 50 words per item and never more than 70; a correct item is usually under 25.
- Be blunt but not rude, with no praise padding, no hedging and no generic advice ("review the lesson", "think carefully about").
  Point at the specific step in their reasoning, or the specific thing in the scenario they missed.
- Do not repeat across items: when two misses share one misconception, explain it in the first and say "same misconception as q2" in the next, in a clause.
- If the item's rationale is in the key, use it as your source, not as text to paste.

## The summary

The `summary` adds only what the item feedback does not say, in at most three sentences:

- the pattern across the misses, if there is one (or that they have the idea down, if there is none);
- the one thing to work on next;
- one concrete next step, such as a named lesson section or a kind of practice.

Do not list or re-explain individual items, and do not restate the score.

## After grading

1. Write `grades/NNNN-sN.json` exactly as `FORMATS.md` shows.
2. Write a learning record when the grades are evidence of real understanding or of a misconception to work on (`.claude/skills/teach/references/LEARNING-RECORD-FORMAT.md`), and update `NOTES.md`.
3. Finish with the summary and the next step in the chat, in the same few words, with nothing the grades file does not already say at more length.
