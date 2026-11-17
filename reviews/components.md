# Components

One entry for every skill and every subagent you built, from `c1-skills` to `final`, including the ones you dropped, even one you took out again before any snapshot.
The heading is the skill's folder name or the subagent's `name` from its frontmatter, and `reviews/README.md` says what each field holds.
Replace the empty entry at the bottom with your first component, and copy it for each one after that.
Claude Code may fill in Kind, Step added, and With and without; Purpose, Review and Kept in final are yours.

<!--
An example of a finished entry:

### quiz-reviewer

- Kind: subagent
- Step added: c2-review
- Purpose: My c1 review found two quiz items that could be read two ways (q2 and q4) and one whose correct option repeated the stem; a reviewer with a fresh context reads the draft the way a learner will, which the quiz skill writing its own items cannot do, so it is a subagent and not a step in the skill.
- With and without: reviews/c2-review.md, Round 1 (without) and Round 2 (with)
- Review: Without it, q2 asked which design "is better" with no criterion; with it, every stem names its criterion and the reviewer's record shows two items flagged and fixed in one pass, for about 0.6M more tokens per quiz, which I think a quiz is worth, because a misread item teaches the wrong thing.
- Kept in final: yes
-->

### tutor

- Kind: skill
- Step added: c1-skills
- Purpose: The tutor skill handles questions and follow-up explanantions in a conversation with the student. These occur outside lessons and quizzes. It needs to adapt to my preferences for how I learn, and give concise and direct guidance that still respects quiz answer restrictions. It is a skill instead of a subagent because it is a primary task that interacts with the user, rather than a background or supporting task. 
- With and without: reviews/c1-skills.md, Round 1 (without) and Round 2 (with)
- Review: TODO
- Kept in final: TODO

### quiz

- Kind: skill
- Step added: c1-skills
- Purpose: The quiz skill generates quizzes and answer keys that fit the learning objectives. It uses varied questions to test understanding rather than just simple recall. Keeping it separate from teach allows its question-writing to be improved and fine-tuned separately. It is a skill because quiz generation is a primary task rather than a background task. 
- With and without: reviews/c1-skills.md, Round 3 (without) and Round 4 (with)
- Review: TODO
- Kept in final: TODO

### grade

- Kind: skill
- Step added: c1-skills
- Purpose: The grade skill checks quiz submissions using their answer keys. It gives feedback to identify what mistakes the user made, locate misconceptions, and give instructions on how to correct these problems. Keeping this functionality separate lets it be fine tuned to my preferences without affecting how quizzes are generating. It is a skill because grading is a primary task rather than a review of another agent's work. 
- With and without: reviews/c1-skills.md, Round 4 (without) and Round 5 (with)
- Review: TODO
- Kept in final: TODO

### teach

- Kind: skill
- Step added: c1-skills
- Purpose: The teach skill creates lessons with structure to introduce big picture concepts before breaking the ideas down into manageable chunks. It gives worked examples and visualizations to help the user's understanding. The goal is for it to produce a complete lesson of a requested length while avoiding any repetition that isn't needed. It fits best as a skill because it is a primary function. Specialized writing or reviewing work could be delegated to subagents. 
- With and without: reviews/c1-skills.md, Round 5 (without) and Round 6 (with)
- Review: TODO
- Kept in final: TODO
