# Writing a quiz and its key

A quiz is retrieval practice that also shows you and the learner where they stand.
Each item tests one thing that matters for the objective, at the learner's level, with exactly one defensible answer.
`FORMATS.md` gives the exact shape of the quiz and key files; this guide is about making them good.

## Before you write

- Pin down the objective, its id, and how many items were asked for; after a lesson, write four or five.
- Find the objective's core: the handful of ideas a learner must get right to have met it, from the lesson or from a high-trust source you found.
  Cover the core first, and skip trivia and phrasing the lesson happened to use.
- Read `NOTES.md`, the learning records and the earlier keys' distractors for the misconceptions this learner has or is likely to have, and their ids.
- Take the next number in `quizzes/`; the key gets the same number in `keys/`.
- Every item serves the requested objective and carries its id.

## Choosing item types

- `mcq` when the wrong answers are predictable: each distractor is a misconception or a typical error, so a wrong pick tells you something.
- `numeric` when the objective involves a quantity: state the unit in the stem and in `unit`, and the precision you expect.
- `short` when the learner should produce the idea themselves: ask for a word, a phrase or one sentence, so the key can give the answer in a few words.
- Mix the types when the objective allows it.

## Difficulty

- Aim at the zone of proximal development: mostly items that ask the learner to apply or explain the idea in a new case, not to recall a sentence.
- One or two items should stretch them, and none should need knowledge they were never given.
- Spread the difficulty through the quiz instead of stacking the hard items at the end.
- When the objective has not been taught yet, write the quiz as a check of the objective itself, at the level its wording states, from the source you read.
  Do not write a lesson unless you were asked for one, and say in your message that the quiz is ahead of the lessons.

## Writing stems

- One question per item, complete on its own: a learner who knows the idea can answer it without the lesson open.
- Plain, exact wording, with no double negatives, no "all of the above" or "none of the above", and no trick wording.
- Give every number, unit and condition the answer depends on.
- Make sure no item gives away another item's answer.

## Writing options (`mcq`)

- Three to five options, usually four, with ids `a`, `b`, `c`, `d`.
- Every option plausible to someone holding the misconception it encodes; no joke options.
- All options the same number of words, and the same number of characters if possible, with the same grammar and level of detail.
- Vary which position holds the correct answer across items, and give nothing away by formatting or order.
- Exactly one option is correct; check that no distractor is also defensible.

## Writing the key

- `answer`: the option id, the number in the item's unit, or the shortest complete reference answer for a `short` item.
- `accepted`: for a `short` item, the other wordings that are just as correct, such as synonyms, a symbol, or a common phrasing.
- `tolerance`: for a `numeric` item, the absolute tolerance the stem's precision implies; for an answer rounded to whole milliamps, 0.5.
- `rationale`: why the answer is right, in one or two sentences, and what a typical wrong answer shows.
- `distractors`: each wrong option that encodes a misconception, mapped to that misconception's id; reuse the ids the workspace already has.

## Check before you finish

- Answer every item yourself from its stem alone, without looking at your key, and compare.
  Rewrite any item where you hesitate, or where a careful expert could argue for a second answer.
- Check that every item serves the objective and carries its id.
- Check that the quiz file holds no answers and that no item repeats a practice question from the lesson.

## Giving a quiz in the chat

When the learner wants to take a quiz in a live session, show its title and each item's stem and options, and never anything from `keys/`.
Collect their answers, write them exactly as given to the next `submissions/sN.json` as `FORMATS.md` shows, and grade that submission.
