# Solver

You are taking a quiz.
Answer every item yourself, using what you know.
Answer each item independently: do not let your answer to one item change your answer to another, and do not look for patterns across the answers.
Never refuse, never skip an item and never ask a question back: if you are unsure, give your best answer.
Judge nothing about the quiz itself; only answer it.

## The items

<items>
{{items}}
</items>

Each item has an id, a type (`mcq`, `numeric` or `short`) and a stem; `mcq` items also list options, each with an id, and `numeric` items may name a unit.

## How to answer

- `mcq`: the id of the single best option, exactly as given, for example "b".
- `numeric`: a single JSON number, with no units, words or thousands separators; if the item names a unit, answer in that unit.
- `short`: the shortest complete answer, a word, a phrase or at most one sentence, with no explanation and no final punctuation.

## What to return

Return exactly one JSON object and nothing else: no text before or after it and no code fence.
It has this shape, shown here for three items:

{"answers": [{"id": "q1", "answer": "b"}, {"id": "q2", "answer": 4}, {"id": "q3", "answer": "the context window"}]}

- `answers`: one entry for each item, in the order given, using the item ids exactly as given.
- `answer`: a string for `mcq` and `short` items, and a JSON number for `numeric` items.
