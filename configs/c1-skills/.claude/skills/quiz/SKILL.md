---
name: quiz
description: Write a quiz and its answer key for the learner's objective - application items in unfamiliar scenarios with plausible wrong options, spread over the objective's core ideas; use it when the learner asks for a quiz or to be tested.
argument-hint: "What should the quiz cover, and how many items?"
---

# Quiz

You write one quiz and its key, and nothing else: no lesson, no grading.

## The request

$ARGUMENTS

If the request above is empty, the request is the learner's latest message.

## Read first

Read `FORMATS.md` (the quiz and key shapes, exactly), `MISSION.md`, `PREFERENCES.md`, `NOTES.md` and every file in `learning-records/`.
Then read `.claude/skills/teach/references/QUIZZES.md` for item types, option rules and the key's fields, the lessons on the objective, and earlier quizzes, keys and grades.
This skill sets the difficulty and the design process; where it differs from that guide, this skill wins.
Never write under `.claude/`.
Use Read, Glob, Grep and Write, plus web search when the objective has no lesson.

## Plan before you write

1. Pin down the objective, its id and the number of items (four or five when none is asked for).
2. List the objective's core ideas, and the distinctions inside them that learners confuse (for an architecture topic, for example, workflow versus agent, or one component's job versus another's).
3. Give each item its own idea or distinction, so no two items test the same thing; if two items would need the same insight to answer, drop one.
   When the objective has a main distinction, test it in at most one item.
4. For each item, invent a scenario the lesson did not use: a different domain, a different system, different names.
   The learner must apply the idea to it, not recognise a sentence from the lesson.

## Write application items

- Each stem is a short concrete scenario, two to four sentences with the details the answer depends on, followed by one question: what happens, what is wrong, which design fits, what would change.
- The answer must follow from reasoning about the scenario, never from a keyword.
  Do not put the objective's vocabulary in the stem or in the correct option ("the steps cannot be predicted in advance", "a model is called"); describe the behaviour and let the learner name it.
- Every wrong option is a misconception someone could really hold, and is at least half right: it applies a true idea to the wrong case, or fixes the wrong part of the problem.
  If a learner can eliminate an option by its wording alone, rewrite it.
- No option stands out by length, specificity, qualifiers ("always", "never"), or by repeating words from the stem.
  Keep options the same length and grammar, and vary the correct position.
- Mix types: mostly `mcq`, and at least one `short` item where the learner must produce the diagnosis or the design in a sentence.
- Spread the difficulty: one or two easier items that confirm the basics in a new scenario, most at application level, and at least one hard item that combines two ideas or asks the learner to find what is wrong in a design.
  None needs knowledge they were never given.

## Write the key

Follow `FORMATS.md` and the guide: `answer`, `accepted` for `short`, a one-or-two-sentence `rationale`, and a `distractors` entry for each wrong option that encodes a misconception, reusing the workspace's misconception ids.

## Check before you finish

- Cover your key and answer every item from the stem alone; rewrite any item where you hesitate, or where a careful expert could defend a second answer.
- For each item, ask whether someone who skipped the lesson could pick the answer by wording or by elimination; if so, rewrite it.
- Check that no two items test the same idea, no item answers another, and the quiz file holds no answer.
- Write the quiz to `quizzes/NNNN.json` and the key to `keys/NNNN.json` with the next number, then finish with a short message that the quiz is ready, with no answers in it.
