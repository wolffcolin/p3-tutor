# FORMATS.md - the output contract

This is the contract between a tutor and the scripts that read its work.
The bench copies this file into every scenario folder as `FORMATS.md`, and `tutor/FORMATS.md` is an identical copy for live sessions; `p3 check` fails when the two differ.
Every path below is relative to the workspace root, the folder the tutor runs in.
How a tutor produces these files is up to its author, but the paths, names and keys below are fixed.

## How the bench runs a request

Each request runs headless in a fresh copy of the workspace, with no one there to answer a question, and it is done when the session ends.
Every file the tutor writes or changes in that copy is kept; the rest of the copy is thrown away.
For a tutor request (a message from the learner), the reply is the session's last message, so it comes after every file the tutor writes.

## General rules

- Text files are UTF-8.
  A JSON file holds exactly one object, with no comments and no trailing commas.
- A numbered file has a four-digit number `NNNN`: `0001`, `0002` and so on.
  A new file takes the next number after the highest one already in its folder, or `0001` when the folder is empty or missing.
  There are two exceptions: a key takes its quiz's number, and a grades file is named after the quiz and the submission it grades.
- A slug matches `[a-z0-9-]+`, such as `ohms-law-in-series`.
- Never change an existing quiz, key or submission; a quiz that needs fixing becomes a new quiz.
- Objective ids (`O1`, `O2`, ...) and misconception ids (`M1`, `M2`, ...) are shared across the workspace.
  Take them from the request and the learner's files (`MISSION.md`, `NOTES.md`, the learning records, earlier quizzes and keys), and never invent a new id for something that already has one.

## The files

| Path | Written by | Holds |
|---|---|---|
| `lessons/NNNN-<slug>.html` | the tutor | one lesson |
| `quizzes/NNNN.json` | the tutor | one quiz's items, without the answers |
| `keys/NNNN.json` | the tutor, with its quiz | the answers to quiz `NNNN` |
| `submissions/sN.json` | the bench, or the tutor when the learner answers a quiz in the chat | one learner's answers to one quiz |
| `grades/NNNN-sN.json` | the tutor | verdicts and feedback on submission `sN` of quiz `NNNN` |
| `learning-records/NNNN-<slug>.md` | the tutor | one thing the learner has shown or established |

Other files in the workspace, such as `MISSION.md`, `NOTES.md` and anything under `assets/`, have no format the bench depends on.

## Lessons

`lessons/NNNN-<slug>.html`, one new file per teach request.

- A complete HTML document: `<!doctype html>`, then `<html>` with a `<head>` and a `<body>`.
- The head declares what was asked for in two meta tags:
  - `<meta name="p3-minutes" content="30">`: the lesson length requested, in whole minutes.
  - `<meta name="p3-objective" content="O3">`: the id of the objective the lesson teaches.

  When a request names no length or no objective id, the tutor chooses one and declares it the same way, and reuses that objective id in quizzes on the same objective.
- Self-contained, so it renders the same from any folder with no network:
  - CSS inline in `<style>`, or in a file under `assets/` linked with a relative path such as `../assets/lesson.css`; no stylesheet from the web, and so no web fonts.
  - Scripts inline, or in a file under `assets/`; no `<script src>` that points at `http://` or `https://`.
  - Images inline (SVG, or a `data:` URI) or in a file under `assets/`; an image loaded from the web counts as a warning.
  - Ordinary `<a href>` links to external pages are allowed, and encouraged for references.
- Length: the bench estimates reading time as the lesson's visible words divided by 150, after dropping everything inside `<script>` and `<style>`, and counts the length as fitting when the estimate is between 0.6 and 1.5 times the requested minutes.
  This is a rough reading-time estimate and nothing more: it cannot tell how long an exercise takes.
  For a 30-minute lesson, 4,500 words estimate to 30 minutes, and anything from 2,700 to 6,750 words fits.

A complete lesson head, in a minimal valid document:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="p3-minutes" content="30">
  <meta name="p3-objective" content="O2">
  <title>Ohm's law: predicting the current in a circuit</title>
  <style>
    body { max-width: 40rem; margin: 0 auto; padding: 2rem 1rem; font-family: Georgia, serif; line-height: 1.6; }
  </style>
</head>
<body>
  <main>
    <h1>Ohm's law: predicting the current in a circuit</h1>
    <p>By the end of this lesson you can predict the current in a simple circuit before you measure it.</p>
  </main>
</body>
</html>
```

## Quizzes

`quizzes/NNNN.json`, for example `quizzes/0002.json`:

```json
{
  "id": "0002",
  "objective": "O2",
  "title": "Ohm's law in a simple circuit",
  "items": [
    {
      "id": "q1",
      "type": "mcq",
      "objective": "O2",
      "stem": "A 6 V battery drives a current through a single 3-ohm resistor. The resistor is swapped for a 6-ohm one. What happens to the current?",
      "options": [
        {"id": "a", "text": "It doubles to 4 A"},
        {"id": "b", "text": "It halves to 1 A"},
        {"id": "c", "text": "It stays at 2 A"},
        {"id": "d", "text": "It drops to 0 A"}
      ]
    },
    {
      "id": "q2",
      "type": "numeric",
      "objective": "O2",
      "stem": "A 9 V battery is connected across a 450-ohm resistor. How much current flows, in milliamps?",
      "unit": "mA"
    },
    {
      "id": "q3",
      "type": "short",
      "objective": "O2",
      "stem": "Two identical bulbs are wired in series with a battery. Compared with the current through the first bulb, is the current through the second smaller, the same, or larger?"
    }
  ]
}
```

- `id`: the quiz's number as a string, the same as in its file name.
- `objective`: the id of the objective the quiz serves.
- `title`: a short title for the learner.
- `items`: the questions in order, with ids `q1`, `q2` and so on.
  - `type`: `mcq` (pick one option), `numeric` (a number) or `short` (a word, a phrase or a sentence).
  - `objective`: the id of the objective this item serves.
  - `stem`: the question, complete on its own, with any unit the answer needs.
  - `options`: only for `mcq`, where it is required: two or more options, each with an `id` (`a`, `b`, `c` and so on) and a `text`.
  - `unit`: optional, only for `numeric`: the unit the answer is given in.
- A quiz never holds an answer; the answers go in its key.

## Keys

`keys/NNNN.json`, with the same number and `id` as its quiz, for example `keys/0002.json`:

```json
{
  "id": "0002",
  "items": [
    {
      "id": "q1",
      "answer": "b",
      "rationale": "The battery fixes the voltage, so I = V / R = 6 V / 6 ohm = 1 A: doubling the resistance halves the current.",
      "distractors": {"c": "M1"}
    },
    {
      "id": "q2",
      "answer": 20,
      "tolerance": 0.5,
      "rationale": "I = V / R = 9 V / 450 ohm = 0.02 A, which is 20 mA. An answer of 0.02 has the right arithmetic in the wrong unit."
    },
    {
      "id": "q3",
      "answer": "the same",
      "accepted": ["same", "equal", "it is the same", "the same current"],
      "rationale": "Charge is not used up going around a series loop, so the current is the same everywhere in it. An answer of smaller shows M2."
    }
  ]
}
```

- `items`: one entry per quiz item, with the same ids in the same order.
  - `answer`: for `mcq`, the correct option's id; for `numeric`, a JSON number in the item's unit; for `short`, the reference answer, as short as it can be while still complete.
  - `accepted`: optional, for `short`: other wordings that are also fully correct.
  - `tolerance`: optional, for `numeric`: an absolute tolerance, so a number within `answer` plus or minus `tolerance` matches the answer; without it, the bench allows 1% of the answer either way.
  - `rationale`: why the answer is right and, where it helps the grader, which misconception a typical wrong answer shows.
  - `distractors`: optional, for `mcq`: maps the id of a wrong option to the id of the misconception it is built on, for the options where one applies.

In these examples, `M1` (a battery always supplies the same current) and `M2` (current is used up as it flows) stand for misconceptions the workspace already names.

## Submissions

`submissions/sN.json` (`s1`, `s2` and so on): one learner's answers to one quiz.
The bench writes them; in a live session, the tutor writes one when the learner answers a quiz in the chat.

```json
{
  "quiz": "0002",
  "learner": "Sam",
  "answers": [
    {"id": "q1", "response": "c"},
    {"id": "q2", "response": "0.02"},
    {"id": "q3", "response": "Same as the first - nothing gets used up going round the loop"}
  ]
}
```

- `quiz`: the id of the quiz answered.
- `learner`: who answered.
- `answers`: one entry per item answered, with the item's `id` and the learner's `response`, a string exactly as they gave it (an option id, a number with or without a unit, or free text).

## Grades

`grades/NNNN-sN.json`, named after the quiz and the submission: the grades for `submissions/s1.json` on quiz `0002` go in `grades/0002-s1.json`.

```json
{
  "quiz": "0002",
  "submission": "s1",
  "items": [
    {
      "id": "q1",
      "verdict": "wrong",
      "misconception": "M1",
      "feedback": "You picked 'It stays at 2 A', as if the battery always pushes out the same current. A battery fixes the voltage, and the current follows from the resistance: 6 V / 6 ohm = 1 A, so doubling the resistance halves the current."
    },
    {
      "id": "q2",
      "verdict": "partial",
      "misconception": null,
      "feedback": "Your arithmetic is right: 9 / 450 = 0.02. That number is in amps, though, and the question asked for milliamps: 0.02 A is 20 mA. Carry the unit through every step and convert at the end."
    },
    {
      "id": "q3",
      "verdict": "correct",
      "misconception": null,
      "feedback": "Right, and your reason is the key idea: nothing is used up going around a series loop, so both bulbs carry the same current."
    }
  ],
  "summary": "You can use Ohm's law, and you already know that current is not used up in a loop. The idea to fix is what a battery holds steady: its voltage, not its current. Before your next calculation, predict whether the current will go up or down, then check."
}
```

- `quiz` and `submission`: the ids of what was graded.
- `items`: one entry per quiz item, with the same ids in the same order, including items the learner left unanswered.
  - `verdict`: `correct` when the response means what the key's answer means, however it is worded and by whatever valid route it is reached; `partial` when part of it is right, such as the right method with the wrong unit, or the right answer with a stated reason or an added claim that is wrong; `wrong` otherwise, including no response.
  - `misconception`: the id of the misconception the response shows in its answer or in its reasoning, or `null` when it shows none (a correct answer, a slip, an incomplete answer, a blank); a `partial` verdict can name one, just as a `wrong` one can.
  - `feedback`: never empty; written to the learner, it says what was right, what was not, and why.
- `summary`: a few sentences to the learner on the whole submission and what to work on next.

## Learning records

`learning-records/NNNN-<slug>.md`, in the teach skill's format: one record per thing the learner has shown they understand, prior knowledge they disclosed, a misconception they corrected, or a change in their mission.

```md
# {Short title of what was learned or established}

{One to three sentences: what was learned or established, and why it matters for future sessions.}
```

Optional, and only when they add value: YAML frontmatter with `status: active` or `status: superseded by NNNN`, and paragraphs headed `**Evidence:**` and `**Implications:**`.
A record notes evidence of learning; material that was only covered does not get one.

For example, `learning-records/0003-current-is-not-used-up.md`:

```md
# Current is the same everywhere in a series loop

The learner explained, unprompted, that both bulbs in a series circuit carry the same current because nothing is used up going around the loop.
Later lessons can build on this; the misconception still open is M1, that a battery supplies a fixed current.

**Evidence:** quiz 0002, submission s1, item q3.
```

## What the bench reads

- **Teach:** the one new lesson.
  It checks the two meta tags, that the lesson is self-contained, the length estimate and every external link (a 404 or 410 counts as dead), and a judge model checks the lesson's facts and whether it asserts a known misconception.
  No new lesson, or more than one, is a failure.
- **Quiz:** the one new quiz and its key.
  It checks the shapes above and every item's objective, then two solver models answer the items without the key: an item where both solvers agree with each other but not with the key is a likely wrong key, and one where they disagree is likely ambiguous.
  A solver's answer to a `short` item counts only when it equals the key's `answer` or an `accepted` form, ignoring case and spacing.
- **Grade:** the new grades file for each submission, compared with true grades: the share of matching verdicts, how often a correct response is graded otherwise, how often the right misconception is named, and whether every item has feedback.
- **Tutor:** the final message.
  It checks whether the message gives away a quiz answer, and a judge model checks whether it does what a good tutor would.
- **Every request:** the tokens, turns, time and subagents it used.
