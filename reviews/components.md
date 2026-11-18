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
- Review: The tutor skill made the responses better in Round 2 compared with Round 1. The response to the Q2 answer request was shorter and more helpful. It replaced an overly lengthy academic integrity expanation with a targeted hint about the tool-call loop. It did still ask too many follow-up questions, which is why I refined the skill again in Round 2. 
- Kept in final: TODO

### quiz

- Kind: skill
- Step added: c1-skills
- Purpose: The quiz skill generates quizzes and answer keys that fit the learning objectives. It uses varied questions to test understanding rather than just simple recall. Keeping it separate from teach allows its question-writing to be improved and fine-tuned separately. It is a skill because quiz generation is a primary task rather than a background task. 
- With and without: reviews/c1-skills.md, Round 3 (without) and Round 4 (with)
- Review: The quiz skill made both the variety and difficulty of questions better. Round 3 had several repetitions in questions about distinguishing workflows from agents, and Round 4 had more interesting applications. This includes Q2's code-controlled retry loop and the approval step requirements in Q5. On the other hand, Q3 was still a bit ambiguous because the troubleshooting process could have been implemented in conditional logic. 
- Kept in final: TODO

### grade

- Kind: skill
- Step added: c1-skills
- Purpose: The grade skill checks quiz submissions using their answer keys. It gives feedback to identify what mistakes the user made, locate misconceptions, and give instructions on how to correct these problems. Keeping this functionality separate lets it be fine tuned to my preferences without affecting how quizzes are generating. It is a skill because grading is a primary task rather than a review of another agent's work. 
- With and without: reviews/c1-skills.md, Round 4 (without) and Round 5 (with)
- Review: The grade skill still had effective misconception detection and it made the feedback more concise. In the full run of c1-skills, submission s1's Q2 and Q4 identified the M4 misconception, while Q5 effectively explained what was missing in the answer. The benchmark kept the 1.00 verdict agreement and misconception detection, although these scores were already perfect before the change. 
- Kept in final: TODO

### teach

- Kind: skill
- Step added: c1-skills
- Purpose: The teach skill creates lessons with structure to introduce big picture concepts before breaking the ideas down into manageable chunks. It gives worked examples and visualizations to help the user's understanding. The goal is for it to produce a complete lesson of a requested length while avoiding any repetition that isn't needed. It fits best as a skill because it is a primary function. Specialized writing or reviewing work could be delegated to subagents. 
- With and without: reviews/c1-skills.md, Round 5 (without) and bench/runs/c1-skills/20261117-061050-agent-architecture-m30-r1 (with, the full run of c1-skills)
- Review: Rewriting the teach skill kept the useful structure and the examples while removing some of the unnecessary repetition. However, the full c1-skills lesson's length ratio was only 0.56, in comparison with the baseline's 0.65. The factual coverage fell from 1.00 to 0.83. The rewrite made the lesson more concise, but it didn't successfully keep the right amount of content, so it could be that this change did not pay off.
- Kept in final: TODO

### quiz-reviewer

- Kind: subagent
- Step added: c2-review
- Purpose: The quiz reviewer checks the generated quizzes for ambiguous wording, incorrect or non-unique answers, easy to recognize distractors, and whether the questions truly test real application of the learned knowledge and concepts. My c1-skills review found problems like Q3 assuming that unpredictable troubleshooting needs an agent when branching logic could also work, and Q6 making assumptions about cost predictability that were misleading. The reviewer is a subagent because it needs fresh context to be truly independant in how it evaluates questions instead of relying on the same agent that wrote them. 
- With and without: reviews/c2-review.md, Round 1 (without) and Round 2 (with)
- Review: The reviewer made question quality better by rewriting Q5 so the student had to actually propose their own solution instead of just being told the answer. It also fixed Q4's wording that sort of lead the student to the correct answer. I think these improvements were worthwhile, but the quiz tokens rose from 135k to 335k without affecting the automated scores at all. 
- Kept in final: TODO

### grade-reviewer

- Kind: subagent
- Step added: c2-review
- Purpose: The grade reviewer was built to check the quality of the grading feedback instead of just focusing on the verdict accuracy that was already perfect in c1-skills. It checks if the feedback actually differentiates correct conclusions from incorrect reasoning, as seen in s2 Q4, and what specifically an answer was missing, as seen in s1 Q5, and avoids any repetition or lengthy explanations that were not necessary. It is a subagent because checking the generated feedback independently helps it catch problems that the grading skill could overlook when checking its own output. 
- With and without: reviews/c2-review.md, Round 2 (without) and Round 3 (with)
- Review: The reviewer made some small improvements, like getting rid of the repeated explanations in s1 Q4 and making s2 Q6 more specific to what the student's reasoning actually was. However, grading accuract was already perfect. I don't think the small improvements justify doubling the grading tokens from 283k to 575k. 
- Kept in final: TODO

### lesson-reviewer

- Kind: subagent
- Step added: c2-review
- Purpose: The lesson reviewer subagent checks the generated output lessons for how factually complete they are, how much content depth they have, how accurate the section timings are, and how aligned they are with learning objectives. The c1-skills lesson's length ratio was only 0.56 and the factual coverage was 0.83. This implies that the lesson needs to have more content without adding unnecessary repetition. It is a subagent because a separate reviewer can check the completed lesson and find gaps independently, which the original writer could have missed. 
- With and without: reviews/c2-review.md, Round 3 (without) and the full run of c2-review (with)
- Review: The reviewer found significant omissions, which lead it to adding cost comparisons for retrievals, details on persistent memory, and practice exercises. Factual coverage rose from 0.83 to 1.00, and the length ratio rose from 0.56 to 0.65. I think these improvements are worth it, even though the tokens used increased from 399k to 1.33M. I believe this because it addressed significant weaknesses from c1-skills. 
- Kept in final: TODO

### lesson-planner

- Kind: subagent
- Step added: c3-split
- Purpose: The lesson planner creates an outline before the lesson is written, to ensure the correct structure and length. This outline includes learning objectives, section order, examples, exercises, and word budgets for each section. The c2-review lesson only achieved a length ratio of 0.65, so I wanted a separate planner that would be more effective at creating complete, appropriately long lessons. It is a subagent because planning is a distinct task that supports the writer to have a clear structure without generating the entire lesson itself.
- With and without: reviews/c3-split.md, Round 1 (without) and Round 2 (with)
- Review: Adding the planner improved the length ratio from 0.65 to 0.70, and it kept full factual coverage. This resulted in an outline that had a 4,500 word budget and distributed topics and examples throughout. It was useful for helping the writer produce a better lesson. However, the resulting lesson was only 3,131 words, so the planning on its own did not fully solve the length problem. I think it was a useful improvement, but it needed a more specialized writer to fully achieve its purpose. 
- Kept in final: TODO

### lesson-writer

- Kind: subagent
- Step added: c3-split
- Purpose: The lesson writer takes the outline from the planner, and it produces a complete lesson. It follows the word budgets for each section to develop explanations, worked examples and exercises. The planner on its own wasn't able to create the correct length lesson, so I thought a subagent that was focused on producing enough content to fit the length requirements without adding filler would help. It is a subagent because it has a specialized purpose within the overall workflow. 
- With and without: reviews/c3-split.md, Round 2 (without) and Round 3 (with)
- Review: The writer helped the length ratio rise from 0.70 to 1.00 while keeping the full factual coverage. The additional content added was actually useful for the learner, I especially liked the expanded token counting example and the exercises that gradually removed hints as the lesson went on. The token usage did rise from 1.30M to 1.62M, and the runtime rose from 4.3 to 5.6 minutes. I think this improvement was worth the added cost, because it was the most substantial improvement in the completeness of the lesson during c3-split.
- Kept in final: TODO

### visual-designer

- Kind: subagent
- Step added: c3-split
- Purpose: The visual designer had the responsibility of creating diagrams after a lesson was written based on the lesson and plan to determine what should be illustrated. I wanted figures to accurately represent concepts taught instead of simply making the lesson look better. It is a subagent because visual design is a separate task the supports lesson creation a as whole and it benefits from having a specific focus.
- With and without: reviews/c3-split.md, Round 3 (without) and Round 4 (with)
- Review: The visual designer made the diagrams better without significantly affecting the length of the lesson, as the length ratio stayed close to the target at 0.99. The context window diagram represented the token quantities more accurately and the retrieval diagram explained how search results reduce context usage effectively. The token consumption actually decreased from 1.62M to 1.40M, but runtime rose slightly. I think this component was worthwhile because it made the quality of the explanations better without adding much cost.
- Kept in final: TODO

### references-finder

- Kind: subagent
- Step added: c3-split
- Purpose: The references finder checks the most important technical claims made in the lesson against some external sources before the lesson is fully written. I wanted the writer to have references that were verified ready before the lesson was written instead of citations only getting checked after the lesson was written, to ensure accuracy. It is a subagent because source verification is a distinct task that involves research, and it supports the writer without having to redo the entire lesson review. 
- With and without: reviews/c3-split.md, Round 4 (without) and the full run of c3-split (with)
- Review: The references finder finished successfully and the report it created identified 11 technical claims that were supported by sources. The benchmark maintained full coverage of the facts, and it didn't find any misconceptions or dead links. The length ratio was 1.01. However, the teach run consumed 2.06M tokens and it took 7.5 minutes, which is significantly longer and more costly than the non-finder run which consumed 1.40M tokens and took 5.8 minutes. I liked that the explanations were supported by sources, but this is a significant added cost. I think it did improve the confidence the learner could have in the technical accuracy of the lesson, but the automated scores were already fairly strong before it was added. 
- Kept in final: TODO
