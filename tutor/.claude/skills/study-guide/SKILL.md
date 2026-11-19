---
name: study-guide
description: Combine the learner's existing lessons into one structured Markdown study guide that summarizes the concepts across lessons and explains how they connect, and save it to study-guides/. Only when the learner asks for a study guide.
argument-hint: "Which topic or lessons should the guide cover? (optional, default all lessons)"
disable-model-invocation: true
---

# Study guide

You turn the lessons that already exist into one study guide that works across them, and write one file: no new lesson, no quiz, no change to any other file.
A cheat sheet in `cheatsheets/` covers one lesson, as a page to look things up in; this guide is for studying several lessons as one body of knowledge, so its value is in the connections between lessons, not in a shorter copy of each.

## The request

$ARGUMENTS

If the request above is empty, use every lesson in `lessons/`.
If it names a topic, an objective id or some lessons, use only the matching ones, and say in the guide which lessons you left out and why.

## What to read

Read `PREFERENCES.md` (how the learner likes things explained), `MISSION.md` and `NOTES.md`.
Then read every lesson you are using in `lessons/` in full, and the cheat sheets in `cheatsheets/` that belong to them, to see what each lesson itself judged worth looking up.
Use `learning-records/` and `grades/` only to tell what the learner already knows or keeps missing, so you can give those ideas more or less room; never quote them in the guide.
Never read, search or list `keys/`: a hook blocks it here, and a study guide needs no answer key.
Use Read, Glob, Grep and Write only.

## Build the guide from the lessons only

- Every concept, term, number and example in the guide comes from a lesson you read.
  Add no outside fact, no new example, no new source and no explanation of your own about how things work: if a connection is not supported by what the lessons say, leave it out.
- A connection is allowed when the lessons give both ends: one lesson defines or uses an idea that another lesson relies on, extends, contrasts with or contradicts.
  Say which lessons, and what each says, in a clause, so the learner can check it.
- Mark the guide's own inference as such ("the lessons suggest...") and keep it to a sentence.
- Where two lessons differ or one lesson revises another, say so plainly and name both.
- Carry over a lesson's references only as links the lesson itself gave.

## When there is only one lesson

Work with that lesson alone.
Write the guide from it, say in its opening line that it covers a single lesson and that connections across lessons need more than one, and leave the section on connections as one line saying so.
Do not stretch the lesson, invent a second topic or borrow from the cheat sheet beyond what the lesson holds.
If there is no lesson, write no guide: tell the learner there is nothing to build from and that `/teach` makes a lesson first.

## Write the guide

Number the file like the others here: scan `study-guides/` for the highest number, add one, and create the folder when the first guide is written.
Write `study-guides/NNNN-<slug>.md` with the Write tool, where the slug names the topic; never overwrite an earlier guide.
Write plain Markdown, in the learner's preferred style, as long as the lessons need and no longer, with these parts in this order:

```md
# {Topic}: study guide

Covers: {each lesson as a relative link, such as [0001](../lessons/0001-slug.html), with its title}

## The big picture
{a short paragraph: what the lessons add up to}

## Key concepts
### {Concept}
{what it is, in the lessons' own terms, and the lesson it comes from}

## How the concepts connect
- {Concept A} and {concept B}: {the relationship}, from {lesson} and {lesson}

## Terms to know
- **{term}**: {definition from the lessons}

## Questions to test yourself
{three to six open questions answerable from the guide, with no answers given}
```

Leave out a section the lessons give nothing for, rather than filling it.
Questions to test yourself carry no answers, so the guide never competes with the quizzes.

## Finish

Reply with the guide's path, which lessons it covers, and one sentence on the main connection it draws (or that there was only one lesson), then stop.
