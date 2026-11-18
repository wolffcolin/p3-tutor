# Grading a submission

Grading gives the learner a verdict on each answer and feedback that helps them learn, in the way they like it.
It is also your best evidence of what they know, so it feeds the learning records.
`FORMATS.md` gives the exact shape of the grades file; this guide is about grading well.

## Before you grade

- Read the quiz, its key and the submission, and the lesson on the quiz's objective if there is one.
- Read `PREFERENCES.md` for how this learner likes feedback, and `NOTES.md` and the learning records for what they already know.

## Verdicts

- Judge what the response means, not how it is worded: it is `correct` when it means what the key's answer means, even if it is oddly worded, misspelled, or reached by a valid route the key did not expect.
- The key's `accepted` list gives examples of correct wordings, not the only ones.
- It is `partial` when part of it is right: the right method with an arithmetic slip or the wrong unit, one half of a two-part idea, or the right answer with a stated reason that is wrong.
- It is `wrong` when it misses the idea, contradicts it, or is blank.
- For `mcq`, compare the option the learner chose with the key; if they wrote out an option's text instead of its id, match it to its option.
- For `numeric`, the number is right when it is within the key's tolerance (1% of the answer when the key gives none), after converting any unit the learner stated; a reason the learner gives with it is still judged by the rules above.
- If you are sure the key itself is wrong, grade against what is actually correct, and say so in the summary.

## Misconceptions

- Name a misconception id when the response shows that misconception: for `mcq`, the key's `distractors` entry for the chosen option; for other items, the misconception the learner's answer or reasoning shows, from the ids the workspace already uses (the keys' distractors and rationales, `NOTES.md`, the learning records).
- Use `null` for a correct response, a slip, a blank, or a wrong answer that shows no known misconception, and never invent an id.

## Feedback

Write each item's feedback to the learner, in the style `PREFERENCES.md` asks for.

- **Correct:** say so, and add the one insight that makes it stick or links it to the next idea; for an unusual route, say why it works.
- **Partial:** say what was right, exactly what was off, and how to fix it.
- **Wrong:** give the right idea and why it holds, in plain words with a concrete example; when a misconception is behind it, name the wrong belief plainly and say why it is tempting, without blame.
- Keep each item's feedback short enough to read in a few seconds, two to four sentences, unless the learner wants more.
- The `summary` says what the learner has down, the one thing to work on next, and a concrete next step, such as a section of a lesson to revisit or a practice to try.

## After grading

- Write a learning record when the grades are evidence: real understanding of something non-trivial, or a misconception to work on (`LEARNING-RECORD-FORMAT.md` in this folder).
- Update `NOTES.md` with what the learner knows and does not yet know.
- Add a term to `GLOSSARY.md` when the learner used it correctly (`GLOSSARY-FORMAT.md` in this folder).
- Finish in the chat with the summary and the next step.
