# Reviews: c1-skills

Your quick rounds while you build `c1-skills`, and then its major review, once you have snapshotted it and made its full run.
In this step no round adds a subagent, because subagents arrive in `c2-review` and `c3-split`: a round changes or adds a skill, or makes another change the skills need, such as an allow rule (Kind `other`).
Your first round can start from the tutor as it ships, so the baseline is the output without your first change.
The major review covers all four jobs, and its previous step is `c0-baseline`, so compare with your baseline runs.
What it finds becomes the checklists of your reviewer subagents in `c2-review`, so be specific.
`reviews/README.md` says how to write each part.
You write your thoughts, ratings and feedback; Claude Code writes only the What changed part of each round.
Keep every heading as it is, because `p3 check` reads them, and add a round by copying the last one with its marker lines.

## Quick rounds

### Round 1

**Run:** bench/runs/_live/20261117-025331-agent-architecture-m30-r1

**My thoughts:** 

I liked the overall structure, especially how the big picture was introduced before breaking concepts down into chunks that had concrete worked examples. I would like to see more concise explanations with less repetition, leaving more room for me to ask follow-up questions rather than giving everything up front. Future quizzes should focus more on applying these new concepts to unfamiliar scenarios, and the conversational type of feedback should be direct and diagnostic, without any long refusals or generic advice, especially when a concise explanation or targeted hint would work. 

**What changed:**

- Kind: new skill
- Files: tutor/.claude/skills/tutor/SKILL.md
- Why: Your thoughts asked for direct, diagnostic feedback with no long refusals or generic advice and for room to ask follow-ups, so the chat job now has its own skill that caps replies near 120 words, diagnoses first, and declines quiz-answer requests in one sentence plus a targeted hint.

### Round 2

**Run:** bench/runs/_live/20261117-042854-agent-architecture-m30-r1

**My thoughts:**

The updated responses are definitely better. I like that they're more concise, and less preachy. They also give more relevant guidance rather than being generic. For example, the changed Q2 output gets rid of the unnecessary lecture about academic integrity and gives targeted questions about the tool-call loop instead. The tutor is still assigning several followup questions instead of giving a specific hint that would be more efficient. Future changes should try to minimize the back and forth. 
**What changed:**

- Kind: modified skill
- Files: tutor/.claude/skills/tutor/SKILL.md
- Why: Your thoughts liked the shorter, less preachy replies but found the tutor still sets several follow-up questions, so the skill now states the hint as a fact, allows at most one question per reply, and keeps declining quiz answers in a single sentence.

### Round 3

**Run:** bench/runs/_live/20261117-051310-agent-architecture-m30-r1

**My thoughts:** The round 2 changes helped somewhat. The Q2 tutor response is shorter and gives more direct guidance, but Q3 is still verbose. The quiz is structured properly and the answer key seems to be correct. A lot of the questions are too easy because the correct answer is obvious from the wording. For example, Q2 says that a model is called, which makes it easy to eliminate option D, while Q5 almost gives away the answer because it emphasizes that the required steps can't be predicted in advance. Q3, Q5 and Q6 test the same workflow / agent distinction. I think more varied scenarios, with plausible incorrect options, and some harder questions that require deeper application of the concepts instead of straightforward recognition. These improvements should be implemented as a new, dedicated quiz skill instead of modifying existing skills. 

**What changed:**

- Kind: new skill
- Files: tutor/.claude/skills/quiz/SKILL.md
- Why: Your thoughts found quiz items too easy to answer from the wording, three items on the same workflow and agent distinction, and asked for a dedicated quiz skill, so it now plans one distinction per item, writes unfamiliar scenarios with plausible wrong options and no giveaway vocabulary, and includes a hard item.

### Round 4

**Run:** bench/runs/_live/20261117-053742-agent-architecture-m30-r1

**My thoughts:**

The new quiz skill made the output much better. The scenarios are more realistic and the questions require the user to actually apply concepts instead of just recognizing definitions. As an example, Q2 tests whether a code-controlled retry loop counts as an agent, and Q5 tests how to enforce approval steps. Both of these are more interesting than the previous quiz's repetitive questions about whether something is a workflow or an agent. However, Q3 assumes that unpredictable sequences of checks need an agent even though you could use conditional logic. Q6 is very similar to the previous quiz's Q2. The existing grading feedback is fairly good. Especially with Q2 and Q4 identifying the underlying misconception and Q5 explaining exactly what was missing. However, some of these explanations are too long, especially for Q2 and Q6, and the summary repeats information that was covered in the individual feedback already. For this round, I want to create a new dedicated grade skill that preserves the useful feedback that diagnoses the problems while making explanations more concise and direct. Do this instead of making further changes to the quiz skill. 

**What changed:**

- Kind: new skill
- Files: tutor/.claude/skills/grade/SKILL.md
- Why: Your thoughts found the grading feedback diagnostic but too long (q2, q6) with a summary that repeats the item feedback, and asked for a dedicated grade skill, so it keeps the diagnosis-then-fix order, caps each item at about 50 words, and limits the summary to the pattern, one thing to work on and a next step.

### Round 5

**Run:** bench/runs/_live/20261117-025331-agent-architecture-m30-r1

**My thoughts:**

The lesson does generally follow my preferences properly. It introduces the big picture before explaining concepts and giving the worked examples. I especially liked the token counting example in "What is kept between steps." However, there is some repetition that isn't required in between sections, especially when it explains how the context grows and increases costs. This makes the lesson denser and longer than it should be. Another issue is the section times total up to 35 minutes, while the lesson is labelled as being 30 minutes. I'd like to rewrite the teach skill to produce shorter, more concise lessons that keep useful examples and diagrams without repeating concepts too much. This makes teach responsible only for lesson generation since quiz and grading have their own dedicated skills. The lesson should still meet the requested duration, however, I just want to get rid of repitition rather than reduce the amount of instructive content. 

**What changed:**

- Kind: modified skill
- Files: tutor/.claude/skills/teach/SKILL.md
- Why: Your thoughts found repetition between sections and chunk times summing to 35 minutes in a 30-minute lesson, so teach is now lesson-only, plans chunk times that add up to the requested minutes, gives each idea one home, and spends the freed words on examples and practice.

## Major review

**Run:** bench/runs/c1-skills/20261117-061050-agent-architecture-m30-r1

**Live tries:**

I tested the tutor using three live prompts. These covered quiz guardrails, personalization and a misconception correction.

I first asked for the answer to Q2 for a quiz that was unsubmitted. The tutor refused to confirm or reveal the answer to this question and offered a conceptual hint instead. The response was appropriately concise, but it couldn't access the quiz because the directory wasn't present. 

I then asked for a brief conceptual explanation of PPO, even though it was outside the immediate learning objective. Unlike in the benchmark response, the tutor was direct in its answer, it didn't give any math, which is something I requested it to avoid, and it gave an example that was helpful to my understanding. This was a good demonstration of personalization.

Third, I gave a misconception that language models automatically remember previous sessions. The tutor was able to immediately correct this and explained how external storage provides persistent memory. However, it did record this misconception in a NOTES.md file, and it inferred some preferences from a very limited interaction. This seemed unnecessary for a very simple conceptual question.

Overall, the live interactions I had were better than the benchmark's tutor behavior score of 0.50 suggested. The responses were usually fairly direct and useful, but the tutor could be better about when and what it records in persistent memory. 

### Lesson

#### Technical correctness and facts

Rating: 4/5

The explanations look to be technically correct. The token calculations in "Why every step costs more than the last" and the final practice example are consistent. However, the benchmark only credited 0.83 of the expected facts, whereas the baseline has 1.00. This suggests that some required information was omitted, or not explained well enough. No misconceptions were asserted as facts. 

#### Pedagogy

Rating: 4/5

The lesson does follow my preferences. It introduces the big picture before explaining individual concepts. The examples and diagrams for token counting were useful, and the sections were manageable without having too much repetition. However, the lesson could use more substantial practice to support the duration it stated. 

#### Alignment with the learning goal

Rating: 4/5

The lesson covers the major concepts in O3. This includes context windows, accumulated token costs, persistent memory and retrieval. The final worked example combines these ideas by asking what information belongs in context rather than external storage or retrieval. This is a useful application of the learning objective. 

#### Overall quality

Rating: 3/5

The presentation was clear, and it was well organized. It had diagrams and worked examples that were useful for helping understanding. However, the benchmark reports that the length ratio was 0.56. This is down from the baseline average of 0.65 and it is below the accepted range. The rewrite improves conciseness but it did seem to sacrifice some instructional depth and factual coverage. 

### Quiz

#### Difficulty

Rating: 4/5

The quiz uses scenarios that are realistic, and they require the user to apply concepts rather than simply memorizing basic definitions. Q4 asks how to enforce identity verification, whereas Q5 requires the user to select an architecture that handles both predictable and unpredictable requests. Some questions, especially Q1, are still fairly easy as the scenario strongly implies what the correct answer is. 

#### Coverage of the lesson's core

Rating: 4/5

For the O4 objective that was assigned, the quiz covers control flow, retry loops, architecture choices, and cost predictability. Q2 tests whether the user understands the distinction between code-controlled and model-controlled loops. Q5 applies the same principles to a hybrid architecture. The quiz addresses a different objective from the O3 lesson, which is expected by the benchmark. 

#### Wording and possible misreadings

Rating: 3/5

Most of the questions were clear, and the automated grader didn't find any ambiguous items or incorrect keys. On the other hand, Q3 could have been more clear in distinguishing model-directed troubleshooting from very complex conditional logic. Q6 also discusses promising a maximum cost based on a fixed number of calls, but token usage can vary between calls. 

#### Writing quality

Rating: 4/5

The questions were written in a readable manner. They used scenarios of sufficient variation, and they included enough plausible but incorrect options. The clinic and makerspace examples are relevant, but they're not unnecessarily complicated and they don't make the process of learning more complicated. However, some of the questions could still have harder distractions. 

#### Alignment with the learning goal

Rating: 4/5

The quiz is effective in testing the O4 goal, which is understanding when a workflow or an agent is a more appropriate choice. Q2 covers control flow ownership, and Q5 tests whether a fixed workflow should be kept and used for more predicatable tasks while an agent handles more complicated exceptions. The key agreement score was 1.00, which matches the baseline. 

### Feedback

#### Useful

Rating: 5/5

The feedback identifies specific misunderstandings the user had, and it provides advice the user can implement to fix this mistake. In submission s1, Q2 and Q4 both find misconception M4, which was about models executing tools. Q5 explains which part of the answer was missing, and it is specific and clear about it. The summaries identify what the main problems are, and they suggest next steps that could help the user correct these problems. 

#### Explains enough

Rating: 4/5

The explanations given are detailed enough for the user without being overly lengthy. As an example, the explanation in submission s2's Q4 explains why the numerical answer given is correct, even though the reasoning was not. Q6 was able to identify the parts of the tool description are missing. The benchmark said it had perfect verdict agreement and misconception detection, matching the baseline. 

#### Personalized to how I like things explained

Rating: 4/5

The grading feedback is direct and specific, making it clear what I needed to understand. It also avoids annoying excessive encouragement, which matched my preferences. It usually was able to explain the underlying mistake instead of just marking an answer as wrong. This matched my preferences well, but I think some of the feedback could have been shortened by a little bit.

### Tutor

#### Guardrails

Rating: 4/5

The tutor did not reveal any of the answers in the Q2 and Q3 quiz probes. The benchmark also reported zero answer leaks, which matched the baseline. Rather than reinforcing misconceptions, the tutor corrected them. However, the PPO response seemed to be unnecessarily restrictive, as it refused to explain the concept instead of providing a brief, relevant explanation. 

#### Personalization

Rating: 3/5

The tutor was effective at providing clear explanations and examples that were concise and did not run on or add more complexity than information. On the other hand, some of the responses were longer than I would have liked, and sometimes the tutor would redirect a question rather than giving a direct answer to clear it up immediately. The score for the expected behavior was 0.50, and comparing this to the baseline average of 0.56, the automated results do not show an improvement.

### Compared with the previous step

In comparison with the c0-baseline, c1-skills made the tutor responsibilties more separate and clear, which enabled it to provide responses that were better matched to my preferences, which were concise and direct explanations. Additionally, this change reduced the number of tokens used from 1.75M to 1.25M, and it brought the estimated cost from $1.72 to $1.50 per run. However, the total runtime was still 5.4 minutes.

The automated quality had mixed results. The lesson factual coverage fell from 1.00 to 0.83. The length ratio went from 0.65 to 0.56, and tutor expected behavior fell from 0.56 to 0.50. On the other hand, quiz and grading accuracy were perfect, but quiz cost increased from $0.18 to $0.24. Because the baseline used three runs and c1-skills used only one, these results should be taken with caution.

Overall, the skills made the tutor more modular and cheaper. However, there was no overall improvement in benchmark quality. 

### What the next step should fix

The biggest priority I have is to improve how complete each lesson was and how long they were, and still making sure no unnecessary repetition was included. A lesson reviewer should check the factual coverage of the lesson, whether the duration of the lesson actually matches the generated content, and identify any explanations or opportunities for practice that are missing. 

The reviewer for the quiz should look for any ambiguous wording, implausible distractors, and whether the questions actually require the user to apply the topics learned instead of just memorizing definitions. The grade reviewer should keep the accuracy and misconception detection but make sure that the feedback is concise and useful. It is important to keep the overhead the reviewers add in mind, especially since c1 already has perfect quiz and grading accuracy. 
