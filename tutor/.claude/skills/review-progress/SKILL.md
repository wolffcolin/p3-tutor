---
name: review-progress
description: Summarize the learner's progress from their grades and learning records - strengths, recurring weaknesses and up to three next steps, each tied to evidence - and save a short report to progress-reports/. Only when the learner asks for a progress review.
argument-hint: "Anything to focus on, such as one objective? (optional)"
disable-model-invocation: true
---

# Review progress

You summarize how the learner is doing from the evidence already in the workspace, write one short report, and nothing else: no lesson, no quiz, no grading, and no change to any other file.

## The request

$ARGUMENTS

If the request above is empty, review everything.
If it names an objective, weight the review toward it and still say what else the records show.

## What to read

Read `PREFERENCES.md` (how the learner likes things said), `MISSION.md` and `NOTES.md`.
Then read every file in `grades/` and every file in `learning-records/`, and a quiz in `quizzes/` only to see which idea an item tested.
A learning record marked `status: superseded by NNNN` is history: use the newer one for what the learner knows now, and the older one only to show how their understanding changed.
`NOTES.md` holds the tutor's own working notes, so use it for leads and check each against a grade or a record before you rely on it.
Never read, search or list `keys/`: a hook blocks it here and a progress review does not need it, because the grades already hold every verdict and misconception id.
Use Read, Glob, Grep and Write only.

## Decide what the evidence supports

- **Strength:** an idea the learner showed they can use, for example a `correct` verdict on a quiz item that tested it, or a learning record that says they demonstrated it.
  One correct item is a hint, and the same idea right in two places is a strength; say which one you have.
- **Recurring weakness:** the same misconception id, or the same idea, wrong or `partial` in two or more items or submissions, or a record or note that says a misconception is still open.
  A single miss is a slip until it repeats, so list it as one thing to watch, not as a weakness.
- **Next steps:** at most three, each tied to a weakness, or to a strength that unlocks the next idea, and each a concrete action such as a lesson, a quiz on one idea, or a section to revisit.
  Fewer is fine; do not pad to three.
- Cite every claim: the grades file and item (`grades/0001-s1.json, q3`), the learning record (`learning-records/0002-...md`) or the `NOTES.md` line behind it, and say what it showed in a few words.
  Quote a verdict or a misconception id exactly as the file has it.
- **Not enough evidence:** with no grades and no learning records, or with only one submission or one record, say so plainly, report only what that one piece shows, and name what would make the review possible (such as a quiz and its grading).
  Never infer a strength or a weakness the files do not show, never guess at a trend from a single point, and never fill a section with a general remark; an empty section reads "Not enough evidence yet", with the reason.

## Write the report

Number reports like the other files here: scan `progress-reports/` for the highest number and add one, and create the folder when the first report is written.
Write `progress-reports/NNNN-progress.md` with the Write tool, in the learner's preferred style and under about 400 words, in this shape:

```md
# Progress review NNNN

Based on: {how many grades files and learning records, and the newest one}

## Strengths
- {the idea}: {what showed it} ({citation})

## Recurring weaknesses
- {the idea or misconception id}: {where it repeated} ({citations})

## Next steps
1. {one concrete action}, because {the evidence} ({citation})

## Evidence gaps
{what you could not tell, and what would show it; "None" when there is nothing to add}
```

Never overwrite an earlier report: each review is a new numbered file, so the learner can see change over time.
When an earlier report exists, note in one sentence under the heading what has changed since it, and only where the new evidence shows it.

## Finish

Reply with the report's path and the one most important finding, in a sentence or two, then stop.
