# Reviews: c2-review

Your quick rounds while you build the review loops on teach, quiz and grade, and then the major review of `c2-review`.
Add one reviewer subagent per round, so the run before it shows the output without it and the run after it shows the output with it.
The major review covers the lesson, the quiz and the feedback, and its previous step is `c1-skills`.
Say in it whether the problems your `c1-skills` review found are gone.
`reviews/README.md` says how to write each part.
You write your thoughts, ratings and feedback; Claude Code writes only the What changed part of each round.
Keep every heading as it is, because `p3 check` reads them, and add a round by copying the last one with its marker lines.

## Quick rounds

### Round 1

**Run:** bench/runs/c1-skills/20261117-061050-agent-architecture-m30-r1

**My thoughts:**

The c1-skills quiz was better than the baseline. This is especially true with its use of the realistic scenarios that required me to apply concepts instead of simply memorizing definitions. Some of the questions still had issues that a separate reviewer could help identify. Q3 assumes that any unpredictable troubleshooting needs an agent, but complex enough conditional logic could handle it as well. Q6 is possibly misleading because it implies that a fixed number of calls to a model can guaranteee a maximum cost, but this doesn't consider that token usage can change between calls.

For this round I want to add a quiz reviewer subagent that checks whether the generated questions are good independently and before they are finalized. The checklist for this reviewer should cover ambiguous wording, whether the intended answer is actually correct, plausible distractors, coverage of learning concepts, and especially whether questions require the user to really apply concepts learned instead of just giving away their answers. The reviewer should find specific problems and give targeted fixes, rather than just approving the quiz. 

To control token cost bloat, the review loop should allow at most one review and revision pass. The reviewer should check the initial draft, identify any specific issues, and request a revision only in the case that it finds a serious, substantive problem. If no issues are identified, the original draft should be finalized without revision. 

**What changed:**

- Kind: new subagent
- Files: tutor/.claude/agents/quiz-reviewer.md, tutor/.claude/skills/quiz/SKILL.md
- Why: Your thoughts asked for an independent quiz reviewer with a specific checklist and at most one review pass, so quiz-reviewer checks the draft in eight points drawn from your c1 findings (q3's unstated assumption, q6's cost claim, answer-giving wording), and the quiz skill drafts in drafts/, reviews once, revises only on a serious finding, and writes the final files once.

### Round 2

**Run:** bench/runs/_live/20261117-212054-agent-architecture-m30-r1

**My thoughts:**

The quiz reviewer caused some useful improvements. It was able to identify a few real problems, with Q4 allowing multiple defensible answers, Q5 having obvious distractors, and Q6 not ruling out a fixed workflow with branches clearly. The revised quiz fixes these problems. Q5 was changed to be a numeric question that had the learner calculate extra model calls, which is harder than just recognizing the correct explanation. The Q4 rewrite made the expected answer clearer. 

The reviewer was able to avoid the problems I raised in the c1-skills quiz. This is especially visible in the ambiguous distinction between decisions driven by agents, and conditional logic. On the other hand, the quiz did become much more expensive. The tokens increased from roughly 135k to 358k. The revisions definitely made the question quality better, but I'm not convinced yet that the improvement was worth the extra cost for every quiz.

For this round I want to add a grade reviewer subagent. The grading is already accurate, and it has perfect verdict agreement and misconception detection. Because of this, the reviewer should focus on feedback quality instead of just checking correctness again. Its checklist should verify that the partial credit explanations can differentiate correct conclusions from bad reasoning, which can be seen in submission s2's Q4, and that the feedback surfaces specific missing information, as seen in s1 Q5. Additionally, it should flag any repetitive explanations, unnecessary encouragement, and summaries that just repeat the individual feedback. To be aware of costs, the loop should only allow at most one review and revise pass, with revision only occurring when a significant problem is found. 

**What changed:**

- Kind: new subagent
- Files: tutor/.claude/agents/grade-reviewer.md, tutor/.claude/skills/grade/SKILL.md
- Why: Your thoughts asked for a grade reviewer focused on feedback quality, with at most one pass and revision only for a significant problem, so grade-reviewer checks nine points (reasoning versus conclusion as in s2 q4, missing detail as in s1 q5, repetition, padding, summary overlap), and the grade skill drafts in drafts/, reviews once, and writes grades/ once.

### Round 3

**Run:** bench/runs/c1-skills/20261117-061050-agent-architecture-m30-r1

**My thoughts:**

The grade reviewer was implemented, but I haven't run it with grading scenarios yet, meaning I can't determine if it actually improved feedback. The checklist did cover the problems that I found and mentioned earlier. This includes distinguishing correct conclusions from wrong reasoning, as in s2 Q4, and explaining the specific parts of an answer that are missing, as in s1 Q5. It also includes avoiding any repetitive explanations or summaries. The skill also keeps the review loop at one pass, to control for token costs. I will evaluate the actual performance in the c2-review major review. 

In this round, I want to add a teach reviewer subagent. The c1-skills lesson was well and clearly structured but the length was not enough. The length ratio was 0.56 against the minimum accepted 0.60. The factual coverage decreased to 0.83. This reviewer should check that all the important facts and learning objectives are covered, that the lesson has enough instructional content to cover the requested duration, and that section times add up correctly. It should flag any repetitive explanations, insufficient examples and practice, and any missed opportunities for the learner to apply concepts. The goal is for completeness and depth to be improved without adding repetition that isn't needed. 

Since lesson generation is already expensive, the teach review loop should allow at most one review and revision pass. The reviewer needs to report specific and actionable revisions for only significant problems, instead of encouraging more writing that doesn't have any real learning benefit. 

**What changed:**

- Kind: new subagent
- Files: tutor/.claude/agents/lesson-reviewer.md, tutor/.claude/skills/teach/SKILL.md
- Why: Your thoughts asked for a lesson reviewer for coverage, depth for the requested minutes, honest section times and repetition, at most one pass and only significant findings, so lesson-reviewer checks eight points against the primary source and the teach skill reviews once and revises in place only on a serious finding.

## Major review

**Run:** bench/runs/c2-review/20261117-220943-agent-architecture-m30-r1

**Live tries:**

I tested the tutor using three prompts. These prompts covered context, memory and retrieval. I first asked why token costs increase across multiple tool calls. The tutor was able to give me a clear numerical example that showed how earlier context is repeatedly sent. This included the cumulative cost over five calls. This explanation was both accurate and useful, but it was a little longer than it needed to be.

I next gave it a misconception that a 1M token context window removed the need for persistent memory. The tutor corrected this misconception and explained how context capacity and persistent storage are different, and it highlighted the effects on cost and model reliability. It gave a RAM versus disk analogy that was helpful.

Third, I asked how a makerspace assistant should go about storing student training records and manuals. The tutor gave a recommendation for an authoritative database that could store exact student records and, in addition to this, retrieval over indexed manuals. It also explained why neither of these should be permanently in the context window. This practical application of the lesson's ideas was effective and concise.

Overall, the live responses were technically accurate and helpful. They provided good examples and direct explanations. The tutor still sometimes gave more detail than was necessary to answer the question, but the interactions generally matched my preferences better than the benchmark responses. Because c2-review did not modify the conversational tutor, the results can't establish that new reviewer subagents made its behavior better. 

### Lesson

#### Technical correctness and facts

Rating: 5/5

The lesson looks to be technically correct. The factual coverage rose from 0.83 in c1-skills to 1.00. The reviewer found several things that were omitted and corrected them. This included the missing cost comparison between loading an entire manual and retrieving smaller chunks. Additionally, it corrected the attribution of the 200,000 token claim and it gave a clarificaiton that the 1M token context window isn't available on every model. The worked example's token counts are consistent and none of the misconceptions were presented as fact.

#### Pedagogy

Rating: 4/5

The lesson gave the big picture of the concept before explaining in more bite-sized chunks. The reviewer subagent provided a few useful improvements by adding a worked example for retrieval, a practice question for BM25, and an exercise on updating a training record for a student. What this acheives is it requires the user to actually apply the material rather than just reading and memorizing explanations. Even though the lesson is a bit short compared to the duration it claims, but the content is more useful for learning than the c1-skills version.

#### Alignment with the learning goal

Rating: 5/5

The learning objective was O3, and the lesson covered it well. It included content on context windows, retrieval, persistent memory and token costs. The reviewer helped this by adding explanations on how notes get written and updated, and a comparison of costs for different retrieval strategies. The final practice exercises also makes the user apply these concepts to decide where different types of information should be stored. 

#### Overall quality

Rating: 4/5

The c2-review lesson has more complete content than c1-skills, and it doesn't introduce too much unnecessary repetition. The reviewer subagent found six issues total, with three of them being serious and three being minor. The review record shows that all six of these problems were addressed. The factual coverage rose from 0.83 to 1.00, and the length ratio rose from 0.56 to 0.65, which puts it in the benchmark's acceptable range. However, the lesson was still a bit short for the 30 minute intended duration. Additionally, the teach job was much more expensive, rising from 399k token to 1.33M tokens. The improvments are good, but the additional costs to achieve these results are significant.

### Quiz

#### Difficulty

Rating: 4/5

The quiz makes the user actually apply concepts to realistic scenarios instead of just memorizing definitions. Q5 asks the learner to decide how to change a pharmacy assistant after it skips a safety check that is critical. Q6 makes the student propose a new, more flexible architecture. This makes the questions harder than just simple multiple choice recognition questions. However, some of the questions were still fairly easy, especially with regards to Q1, where the sequence is explicity laid out in the question. 

#### Coverage of the lesson's core

Rating: 5/5

The main concepts of O4 are covered well by the quiz. This includes who controls the execution of steps, deciding when a fixed workflow is more appropriate, the cost implications of using an agent loop, and when model-directed decisions become useful. Q3 tests how cost predictability can be affected by number of model calls and the growth of context. Q5 tests how mandatory steps are enforced in code. Q6 tests adaptive tool use and the costs associated with that use. Because these questions, the coverage of the core is good, and unnecessary repetitions are avoided. 

#### Wording and possible misreadings

Rating: 4/5

The reviewer found a few wording issues with the initial draft, and it made corrections to fix them. One was in Q4, where the wording initially almost gave the answer away by saying the necessary checks could not be listed in advance. The fixed version has a scenario that involves previosly unseen failures. Q5 was also rewritten to make the user propose an architectural change themselves rather than being able to infer it from the question. The benchmark didn't find any ambiguous items or incorrect answer keys. On the other hand, Q4 still simplified the distinction a fair bit, as conditional workflows could still respond to previous results. 

#### Writing quality

Rating: 4/5

The questions were written clearly and they used a variety of practical scenarios. This included veterinary appointments, makerspace bookings, insurance processing, and hospital IT. The reviewer made the distractors in several questions less obvious, and it removed unsupported misconception IDs. The two short answer questions also break up some of the repetitiveness of the quiz. Some of the distractors used in the multiple choice questions were fairly easy to eliminate, but overall the writing was quite clear and it supported the learning objective.

#### Alignment with the learning goal

Rating: 5/5

The quiz fit O4's learning goal quite well, which was understanding when to use fixed workflows instead of agents. Q2 had the learner select a predictable and cheap design for a routine booking process, and Q4 tested when an unpredictable troubleshooting sequence makes a fixed design fit less well. Q5 and Q6 make the learner apply these principles to design decisions instead of just memorizing terminology or concepts. The answer key did not contradict the benchmark's solver, which keeps the 1.00 key agreement that existed in c1-skills. 

### Feedback

#### Useful

Rating: 5/5

The feedback was both accurate and useful. It found the specific misunderstandings in the student's work, and it gave corrections to address those issues. For example, s1 Q5 explains how the student described what happens to a tool result but didn't explain why it needs to get returned to the model. In s2 Q4, the feedback differentiated the right numerical answer from the incorrect reasoning about who executes the tools. The reviewer kept the 1.00 verdict agreements and misconception detection from c1-skills. 

#### Explains enough

Rating: 5/5

The feedback provides enough explanation but it doesn't get too lengthy without cause. The reviewer fixed s1 Q4 by quoting the part of the student's reasoning that wasn't quite right, and it referred back to misconception M4 rather than repeating the explanation from Q2. In s2 Q3, it was able to point out why the student may have chosen their reasoning before correcting the issues. Both of the review records have only minor issues, while the actual final feedback was still concise and explained what went wrong and how to fix it.

#### Personalized to how I like things explained

Rating: 5/5

My preferences requested brief, direct diagnostic explanations that didn't have too much encouragement or repetition. The feedback matches these preferences. The reviewer shortened some of the correct answer explanations and it made corrections that were specific to the student's reasoning. This can be seen in s2 Q6. It also changed the summary for s2 to focus on the underlying pattern and give a next step. These fixes made the feedback somewhat better, but since the original grading was already strong, the reviewers contribution was small. 

### Compared with the previous step

In comparison to c1-skills, c2-review made the lesson significantly better. The factual coverage rose from 0.83 to 1.00, and the length ratio rose from 0.56 to 0.65. This brings it above the benchmarks minimum of 0.60 for length. The lesson reviewer found six problems, with three of them being more serious and three of them being more minor. The final lesson fixed all six of these issues.

The quiz reviewer made some qualitative improvements as well. It fixed questions that gave away answers easily, improved some weaker distractors, and got rid of invalid misconception references from the answer key. The automated metrics for the quiz were already perfect, so these improvements were more visible in manual inspection rather than the scores from the benchmark.

The grade reviewer made some smaller improvements. It did this by shortening explanations that were repetitive, referencing the specific mistakes the student made, and giving more targeted feedback. The grading accuracy was already perfect from c1-skills. This means the reviewer did not improve the automated scores.

The biggest drawback was the cost. The total token consumption rose from 1.25M to 2.68M, which is about 2.1 times as much. Teach rose from 399k tokens to 1.33M tokens. Overall, the review loops made the generated output have higher quality, especially with the lesson, but the additional cost was significant. Out of the three reviewers, the grade reviewer had the least justified benefit relative to the cost. 

### What the next step should fix

The next step should focus on the teach job. While the reviewer was able to improve the factual coverage and lesson length, it now consumes 1.33M tokens, which is more than three times the c1-skills cost. The lesson is also still short compared to the requested duration of 30 minutes.

I want to test whether the extra subagents actually make the finished lesson better by enough to justify the overhead introduced by coordination. I also would like to keep the strengths the lesson already has, mainly with its technical correctness, practical examples and progression from the big picture to smaller details. The next step should be careful to not sacrifice these benefits just to reduce token consumption. 
