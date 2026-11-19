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
Never write under `.claude/`.
Never read, search or list `keys/`: a hook blocks it for this conversation, and the `grader` subagent is the only one that reads a key.

## Grade with the grader

Verdicts, misconception ids and the feedback are written by the `grader` subagent, which holds the rules for them, so this skill does not repeat them.

1. **Grade:** start the `grader` subagent with a task message that names the quiz (`quizzes/NNNN.json`), the submission (`submissions/sN.json`) and the objective, and nothing about what the answers should be.
   Wait for its report before you do anything else.
   It writes the draft to `drafts/NNNN-sN-grades.json`; read the draft, and never write a draft to `grades/`, because the bench reads that folder and it gets the final file once.
2. **Finish:** write the draft unchanged as `grades/NNNN-sN.json`, once, with the Write tool directly (not a shell copy).
   You cannot see the key, so you never change a verdict or a misconception id yourself.
3. Write a learning record when the grades are evidence of real understanding or of a misconception to work on (`.claude/skills/teach/references/LEARNING-RECORD-FORMAT.md`), and update `NOTES.md`.
4. Finish with the grader's summary and the next step in the chat, in the same few words, with nothing the grades file does not already say at more length.
