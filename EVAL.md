# Evaluation report

This is the report on what each step of your architecture bought and what it cost.
I read it for one thing above all: whether each claim matches its evidence, including the steps that did not pay.
A step you measured carefully and then dropped is as good a result as a step that won.

Three kinds of material go here.
The tables are pasted from commands: `uv run p3 report --configs a,b` for the objective checks, the cost and your ratings, and `uv run p3 compare --reveal <session-id>` for each blind comparison.
Paste them as they are, and name the session id or the run ids next to each one, so I can find them in `bench/compare/` and `bench/runs/`.
The evidence from your reviews stays in `reviews/`, and here you point at it: name the round, such as `c2-review` Round 3, or the criterion, such as the `c1-skills` review's Wording and possible misreadings, so I can follow the trail.
The prose is yours.

Each section ends with a marker line.
Replace that line with your own writing; `uv run p3 check --final` fails while one is left.

Words used below.
**Your ratings** is the table `p3 report` prints from your major reviews, one row per criterion and one column per step, from 1 to 5.
A **round** is a quick round in one of your step files in `reviews/`, and its **What changed** is the change Claude Code made from your thoughts in it.
A **pass** is one revise-and-review iteration inside one of your tutor's review loops, so a loop capped at two passes reviews a draft at most twice.
A **tally** is the wins for each config and the ties in one blind comparison, and the **p-value** is the reveal's two-sided sign test on the picks that were not ties: with 10 such picks, 8 for one config is suggestive and 9 is strong.
**Could tell** is the share of pairs where you said you could tell which config made which.
The objective checks use the names `p3 report` prints, such as `teach_facts_correct`, `quiz_key_agreement`, `grade_false_wrong` and `tutor_leaks`, the README's section "The scenarios and the objective checks" lists them, and `guide/06-the-bench.html` ("The headline numbers") says what each one measures.
**Cost** is tokens, output tokens, minutes and subagents per scenario, and the list-price equivalent, which is not what you pay on a subscription.

---

## 1. The baseline, `c0-baseline`

Paste the `p3 report` table for `c0-baseline` (three full runs on the shared topic).

## Results on agent-architecture

Scored full runs (quick runs and --only runs left out); each cell is the mean over the runs, with the range in brackets.

### Quality

| config | runs | teach facts | teach misconc. | length ratio | dead links | key agreement | wrong keys | ambiguous items | verdict agreement | false wrong | misconc. hit | leaks | behavior met |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `c0-baseline` | 3 | 1.00 | 0 | 0.65 (0.62-0.72) | 0 | 1.00 | 0 | 0 | 1.00 | 0.00 | 1.00 | 0 | 0.56 (0.50-0.67) |

Teach facts, key agreement, verdict agreement, false wrong, misconception hit and behavior met are shares (0 to 1); misconceptions, dead links, wrong keys, ambiguous items and leaks are counts per run.
A dash means no run could be scored on that check, and n= says how many of the runs could.
A job that failed counts against the config: no lesson scores 0 teach facts, no quiz and key 0 key agreement, a missing grades file disagrees on every item, and a tutor scenario with no reply is not met; leaks need a reply to check, so such a scenario is left out of them.
The length ratio is a rough reading-time estimate (visible words / 150) over the minutes requested; 0.6 to 1.5 counts as on length.

### Cost: teach

| config | runs | tokens | output tokens | minutes | subagents | list-price $ |
|---|---:|---:|---:|---:|---:|---:|
| `c0-baseline` | 3 | 798.2k (676.2k-951.2k) | 27.2k (24.6k-29.6k) | 2.7 (2.3-2.9) | 0 | 0.59 (0.55-0.62) |

### Cost: quiz

| config | runs | tokens | output tokens | minutes | subagents | list-price $ |
|---|---:|---:|---:|---:|---:|---:|
| `c0-baseline` | 3 | 160.2k (133.5k-177.6k) | 5.6k (5.0k-6.6k) | 0.7 | 0 | 0.18 |

### Cost: grade

| config | runs | tokens | output tokens | minutes | subagents | list-price $ |
|---|---:|---:|---:|---:|---:|---:|
| `c0-baseline` | 3 | 263.3k (261.5k-265.4k) | 6.5k (6.2k-6.7k) | 0.7 (0.7-0.8) | 0 | 0.31 (0.30-0.31) |

### Cost: tutor

| config | runs | tokens | output tokens | minutes | subagents | list-price $ |
|---|---:|---:|---:|---:|---:|---:|
| `c0-baseline` | 3 | 528.3k (487.3k-573.4k) | 9.0k (8.0k-10.1k) | 1.3 (1.2-1.4) | 0 | 0.65 (0.63-0.68) |

### Cost: all jobs

| config | runs | tokens | output tokens | minutes | subagents | list-price $ |
|---|---:|---:|---:|---:|---:|---:|
| `c0-baseline` | 3 | 1.75M (1.64M-1.96M) | 48.2k (46.9k-49.1k) | 5.4 (5.1-5.5) | 0 | 1.72 (1.69-1.74) |

Costs are per run, summed over the job's scenarios; list-price $ is the list-price equivalent, not what you pay on a subscription.

20261117-023351-agent-architecture-m30-r1
20261117-023926-agent-architecture-m30-r2
20261117-024503-agent-architecture-m30-r3

What did the baseline do well, and where did it fall short, for each of the four jobs?
Read its outputs as you will read your own steps', because your `c1-skills` review compares against it.
Which of the gaps in `KNOWN-GAPS.md` did you see in your own runs, and did you find one that is not listed?
Which number moved the most from one run to the next, and what does that spread mean for a step measured on a single run?

The baseline's performance was good on technical correctness and accuracy. In three runs, the lesson factual coverage was 1.00, the quiz key agreement and grading verdict agreement was 1.00. There weren't any incorrect quiz keys, ambiguous items detected by benchmark, or answer leaks by the tutor. Two failures in KNOWN-GAPS.md match my observations. The lessons were shorter than they should have been and the tutor's responses were longer than they have been. I did not independently verify the more specific failures mentioned that involved quiz answer hints and overly advanced PPO explanations. I did not find another clear failure specific to the baseline.

The baseline did have some weaknesses, though. The lessons were usually shorter than what was asked for, with an average length ratio of 0.65. In earlier reviews, I saw that some of the quiz questions had obvious answers and the conversational responses were sometimes very generic or verbose. The expected behavior score for the tutor was 0.56.

The biggest variation in the quality scores was the tutor expected behavior. It ranged from 0.50 to 0.67. This could mean the conversational performance is a little inconsistent, and small differences between different configurations in this metric might not be meaningful, especially with later configurations only using one run. 

---

## 2. Step 1: `c1-skills` against `c0-baseline`

### What changed

Name the rounds that built this step, such as `c1-skills` Rounds 1 to 4, and the inventory entries of the skills they added; the trail from thoughts to change to outcome is already in `reviews/` and `reviews/components.md`, so do not retell it here.
Then what you put in `PREFERENCES.md`, and anything about how the four skills work together that no single inventory entry says.

I documented the changes in this stage in reviews/c1-skills.md. This includes Rounds 1-5, and the entries for tutor, quiz, grade, and teach in reviews/components.md. Rounds 1 and 2 added and refined the tutor skill. Round 3 added the quiz skill, Round 4 added the grade skill, and Round 5 revised the teach skill. I also introduced my preferences for explanantions being concise and direct, and introducing the big picture before working through smaller, bite-sized chunks. I also wanted useful examples and minimal unnecessary repetition. 

The main change to the architecture was separating the four different jobs into dedicated skills instead of having it all be in one big teaching skill. A four jobs still run through the main agent, with their own instructions and responsibilities. This allows their behavior to be refined independent from one another.

### Your review, the objective checks and the cost

Paste `uv run p3 report --configs c0-baseline,c1-skills`: the objective checks, the cost per job, and your ratings.

## Results on agent-architecture

Scored full runs (quick runs and --only runs left out); each cell is the mean over the runs, with the range in brackets.

### Quality

| config | runs | teach facts | teach misconc. | length ratio | dead links | key agreement | wrong keys | ambiguous items | verdict agreement | false wrong | misconc. hit | leaks | behavior met |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `c0-baseline` | 3 | 1.00 | 0 | 0.65 (0.62-0.72) | 0 | 1.00 | 0 | 0 | 1.00 | 0.00 | 1.00 | 0 | 0.56 (0.50-0.67) |
| `c1-skills` | 1 | 0.83 | 0 | 0.56 | 0 | 1.00 | 0 | 0 | 1.00 | 0.00 | 1.00 | 0 | 0.50 |

Teach facts, key agreement, verdict agreement, false wrong, misconception hit and behavior met are shares (0 to 1); misconceptions, dead links, wrong keys, ambiguous items and leaks are counts per run.
A dash means no run could be scored on that check, and n= says how many of the runs could.
A job that failed counts against the config: no lesson scores 0 teach facts, no quiz and key 0 key agreement, a missing grades file disagrees on every item, and a tutor scenario with no reply is not met; leaks need a reply to check, so such a scenario is left out of them.
The length ratio is a rough reading-time estimate (visible words / 150) over the minutes requested; 0.6 to 1.5 counts as on length.

### Cost: teach

| config | runs | tokens | output tokens | minutes | subagents | list-price $ |
|---|---:|---:|---:|---:|---:|---:|
| `c0-baseline` | 3 | 798.2k (676.2k-951.2k) | 27.2k (24.6k-29.6k) | 2.7 (2.3-2.9) | 0 | 0.59 (0.55-0.62) |
| `c1-skills` | 1 | 399.0k | 23.5k | 2.3 | 0 | 0.48 |

### Cost: quiz

| config | runs | tokens | output tokens | minutes | subagents | list-price $ |
|---|---:|---:|---:|---:|---:|---:|
| `c0-baseline` | 3 | 160.2k (133.5k-177.6k) | 5.6k (5.0k-6.6k) | 0.7 | 0 | 0.18 |
| `c1-skills` | 1 | 134.9k | 10.2k | 1.4 | 0 | 0.24 |

### Cost: grade

| config | runs | tokens | output tokens | minutes | subagents | list-price $ |
|---|---:|---:|---:|---:|---:|---:|
| `c0-baseline` | 3 | 263.3k (261.5k-265.4k) | 6.5k (6.2k-6.7k) | 0.7 (0.7-0.8) | 0 | 0.31 (0.30-0.31) |
| `c1-skills` | 1 | 283.1k | 7.1k | 0.8 | 0 | 0.31 |

### Cost: tutor

| config | runs | tokens | output tokens | minutes | subagents | list-price $ |
|---|---:|---:|---:|---:|---:|---:|
| `c0-baseline` | 3 | 528.3k (487.3k-573.4k) | 9.0k (8.0k-10.1k) | 1.3 (1.2-1.4) | 0 | 0.65 (0.63-0.68) |
| `c1-skills` | 1 | 435.5k | 4.9k | 0.8 | 0 | 0.47 |

### Cost: all jobs

| config | runs | tokens | output tokens | minutes | subagents | list-price $ |
|---|---:|---:|---:|---:|---:|---:|
| `c0-baseline` | 3 | 1.75M (1.64M-1.96M) | 48.2k (46.9k-49.1k) | 5.4 (5.1-5.5) | 0 | 1.72 (1.69-1.74) |
| `c1-skills` | 1 | 1.25M | 45.8k | 5.4 | 0 | 1.50 |

Costs are per run, summed over the job's scenarios; list-price $ is the list-price equivalent, not what you pay on a subscription.

## Your ratings

Your ratings from 1 to 5 in the major reviews (reviews/<step>.md), which review full runs on the shared topic; a dash means no rating there yet, one that p3 check does not accept, or a job that step does not review (Tutor in c2-review; Quiz, Feedback and Tutor in c3-split).

| job | criterion | c1-skills | c2-review | c3-split | final |
|---|---|---:|---:|---:|---:|
| Lesson | Technical correctness and facts | 4 | - | - | - |
| Lesson | Pedagogy | 4 | - | - | - |
| Lesson | Alignment with the learning goal | 4 | - | - | - |
| Lesson | Overall quality | 3 | - | - | - |
| Quiz | Difficulty | 4 | - | - | - |
| Quiz | Coverage of the lesson's core | 4 | - | - | - |
| Quiz | Wording and possible misreadings | 3 | - | - | - |
| Quiz | Writing quality | 4 | - | - | - |
| Quiz | Alignment with the learning goal | 4 | - | - | - |
| Feedback | Useful | 5 | - | - | - |
| Feedback | Explains enough | 4 | - | - | - |
| Feedback | Personalized to how I like things explained | 4 | - | - | - |
| Tutor | Guardrails | 4 | - | - | - |
| Tutor | Personalization | 3 | - | - | - |

20261117-061050-agent-architecture-m30-r1

### What the step bought and what it cost

For each job: what did your major review find against `c0-baseline`, and did the objective checks agree?
Where they disagree, which do you believe, and why?
`c1-skills` is also the first config with your `PREFERENCES.md`, while `c0-baseline` keeps the neutral one: which of the differences could come from your preferences rather than the skills?
What did the step cost per scenario, and was the gain worth it?
Say what one run of `c1-skills` against three of `c0-baseline` lets you claim, and what it does not.

The results were mixed for c1-skills. While the lesson was structured properly and it matched my preferences for worked examples and bite-sized explanations, its factual coverage went from 1.00 to 0.83, and the length ratio went from 0.65 to 0.56. This means the rewrite favored conciseness over total completeness.

The quiz was better in the variety of scenarios and the need to truly apply concepts instead of just memorizing definitions. However, both configurations already had perfect key agreement, meaning this improvement wasn't actually captured by the automated checks. The estimated cost for the quiz increased from $0.18 to $0.24 per run. Grading still had perfect verdict agreement and misconception detection, and the feedback was more concise and direct without increasing cost. 

The tutor generally matched my preferences better and it was more concise. The estimated cost for the tutor fell from $0.65 to $0.47, and answer leaks were still zero. On the other hand, the expected behavior fell slightly from 0.56 to 0.50, meaning the objective checks didn't show an improvement. My live interactions seemed more positive than this score implied, but they did show some questionable decisions about when and what to save in persistent memory. 

The total token usage fell from 1.75M to 1.25M, and the cost estimate went from $1.72 to $1.50. The total runtime was constant at 5.4 minutes. I think the clearer separation of responsbilities and the lower cost make the skills worth it. However, these results don't demonstrate an overall improvement in the quality of the benchmark. 

Since the baseline used the original baseline preferences, it is possible that some of the improvements seen are attributed to my PREFERENCES.md instead of the skills. In addition to this, c1-skills was evaluated using only one full run instead of the three baseline runs, so small differences should not be interpreted as reliable performance changes. 

---

## 3. Step 2: `c2-review` against `c1-skills`

### What changed

Name the rounds that built this step and the inventory entries of the reviewers they added, as in step 1.
Then the loops' design, for each of teach, quiz and grade: who reviews, what is on each reviewer's checklist and which items came from your `c1-skills` major review, how each reviewer gets a fresh context, how many passes a loop may run and what ends it early, and what each loop records.
Then one design choice you could have made the other way, such as one reviewer against several, a cap of one pass against three, or a reviewer that edits against one that only reports, and why you chose as you did.

I documented the changes in reviews/c2-review.md, in Round 1-3, and I added the quiz reviewer, grade reviewer and lesson reviewer to reviews/components.md. Each of these reviewers is a subagent that checks the output of the corresponding skill independently with a fresh context. 

The quiz subagent looks for ambiguous wording, any obvious distractors, incorrect answer keys and questions that don't test the objective well enough. I felt this was needed because of the ambiguous Q3 I saw in c1-skills. The grade reviewer looks at the feedback to determine if it explains mistakes, differentiates correct answers from incorrect reasoning, finds missing details, and keeps the whole thing as concise as possible. The lesson reviewer checks a lesson for factual completeness, content depth, timing, repetition, and if it gives ample opportunities for the learner to practice. It primarily focuses on the factual coverage and the lesson length issues that were seen in c1-skills. 

Each of these loops only allows one review pass, to prevent excessive token costs. The reviewer reports what issues it finds, and the main agent then decides if any changes are required. The quiz and grade skills create drafts before writing the actual final outputs, and the teach skill just edits the lesson in place. All of the loops create review records explaining what was found and what was changed. 

I decided to use different reviewers instead of one that covers all responsbilities because of the differing requirements of the three jobs. I also added the one pass limit to reduce the overall token cost. While more passes could have potentially improved the quality more, it would make the already very expensive review process harder to justify. 

### The loops as they ran

For teach, quiz and grade: how many review passes ran in your bench run, what the reviewers flagged, and whether the revisions moved anything you can point at, a fact corrected, an ambiguous item rewritten, feedback that changed.
The loop records in the run's outputs are the evidence; name the files.

All three of the loops completed successfully in the c2-review benchmark, and each had one review pass for each generated artifact. The records are in the run folder, in teach/outputs/review-records/, quiz/outputs/review-records, and the grade-s1 and grade-s2 review-records/ directories.

The lesson reviewer found three serious and three minor issues in 0001-teach.md. The problems it found included missing explanations for retrieval costs and persistant notes, and not enough practice for retrieval. The changes added a cost comparison, an example for retrieval, a practice question covering BM25, and an exercise on updating a student's training record. There were also two statements that could have misleaded the learner, and the review and revision pass corrected these. The result was that the factual coverage of the lesson rose from 0.83 to 1.00 and the length ratio rose from 0.56 to 0.65. 

There were two issues the quiz reviewer found in 0002-quiz.md. In Q4, the correct answer was made too obvious. In Q5, the intended change to the architecture was also basically given away by the question. Both of these questions were rewritten, and a few smaller changes were made to fix some question wording issues and distractors that were too obvious. There was a misconception ID that didn't exist in the workspace, and this was removed. The final quiz maintained its 1.00 key agreement and there weren't any detected ambiguous items or incorrect keys. The improvement was mostly qualitative instead of being measurable with the automated checks. 

The grade reviewer looked at two submissions. It saved its findings in 0001-s1-grade.md and 0001-s1-grade.md. Both of these reviews returned KEEP, but they had a few minor suggested changes. These minor suggestions were to shorten some of the repeated explanations, being more direct when referring to a student's reasoning, and making the summary more actionable for the learner. As an example, s1 Q4 now quotes the student in their incorrect claim that the model runs tools, and s2 Q6 addresses the student heavily relying on tool names. None of the actual grading verdicts or misconception IDs changed. These were fairly small changes, even if they were useful. 

### Your review, the objective checks and the cost

Paste `uv run p3 report --configs c1-skills,c2-review`.

## Results on agent-architecture

Scored full runs (quick runs and --only runs left out); each cell is the mean over the runs, with the range in brackets.

### Quality

| config | runs | teach facts | teach misconc. | length ratio | dead links | key agreement | wrong keys | ambiguous items | verdict agreement | false wrong | misconc. hit | leaks | behavior met |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `c1-skills` | 1 | 0.83 | 0 | 0.56 | 0 | 1.00 | 0 | 0 | 1.00 | 0.00 | 1.00 | 0 | 0.50 |
| `c2-review` | 1 | 1.00 | 0 | 0.65 | 0 | 1.00 | 0 | 0 | 1.00 | 0.00 | 1.00 | 0 | 0.50 |

Teach facts, key agreement, verdict agreement, false wrong, misconception hit and behavior met are shares (0 to 1); misconceptions, dead links, wrong keys, ambiguous items and leaks are counts per run.
A dash means no run could be scored on that check, and n= says how many of the runs could.
A job that failed counts against the config: no lesson scores 0 teach facts, no quiz and key 0 key agreement, a missing grades file disagrees on every item, and a tutor scenario with no reply is not met; leaks need a reply to check, so such a scenario is left out of them.
The length ratio is a rough reading-time estimate (visible words / 150) over the minutes requested; 0.6 to 1.5 counts as on length.

### Cost: teach

| config | runs | tokens | output tokens | minutes | subagents | list-price $ |
|---|---:|---:|---:|---:|---:|---:|
| `c1-skills` | 1 | 399.0k | 23.5k | 2.3 | 0 | 0.48 |
| `c2-review` | 1 | 1.33M | 39.9k | 3.6 | 1 | 0.89 |

### Cost: quiz

| config | runs | tokens | output tokens | minutes | subagents | list-price $ |
|---|---:|---:|---:|---:|---:|---:|
| `c1-skills` | 1 | 134.9k | 10.2k | 1.4 | 0 | 0.24 |
| `c2-review` | 1 | 335.0k | 22.1k | 3.0 | 1 | 0.46 |

### Cost: grade

| config | runs | tokens | output tokens | minutes | subagents | list-price $ |
|---|---:|---:|---:|---:|---:|---:|
| `c1-skills` | 1 | 283.1k | 7.1k | 0.8 | 0 | 0.31 |
| `c2-review` | 1 | 574.9k | 13.1k | 1.5 | 2 | 0.49 |

### Cost: tutor

| config | runs | tokens | output tokens | minutes | subagents | list-price $ |
|---|---:|---:|---:|---:|---:|---:|
| `c1-skills` | 1 | 435.5k | 4.9k | 0.8 | 0 | 0.47 |
| `c2-review` | 1 | 441.4k | 5.6k | 0.8 | 0 | 0.50 |

### Cost: all jobs

| config | runs | tokens | output tokens | minutes | subagents | list-price $ |
|---|---:|---:|---:|---:|---:|---:|
| `c1-skills` | 1 | 1.25M | 45.8k | 5.4 | 0 | 1.50 |
| `c2-review` | 1 | 2.68M | 80.7k | 8.9 | 4 | 2.34 |

Costs are per run, summed over the job's scenarios; list-price $ is the list-price equivalent, not what you pay on a subscription.

## Your ratings

Your ratings from 1 to 5 in the major reviews (reviews/<step>.md), which review full runs on the shared topic; a dash means no rating there yet, one that p3 check does not accept, or a job that step does not review (Tutor in c2-review; Quiz, Feedback and Tutor in c3-split).

| job | criterion | c1-skills | c2-review | c3-split | final |
|---|---|---:|---:|---:|---:|
| Lesson | Technical correctness and facts | 4 | 5 | - | - |
| Lesson | Pedagogy | 4 | 4 | - | - |
| Lesson | Alignment with the learning goal | 4 | 5 | - | - |
| Lesson | Overall quality | 3 | 4 | - | - |
| Quiz | Difficulty | 4 | 4 | - | - |
| Quiz | Coverage of the lesson's core | 4 | 5 | - | - |
| Quiz | Wording and possible misreadings | 3 | 4 | - | - |
| Quiz | Writing quality | 4 | 4 | - | - |
| Quiz | Alignment with the learning goal | 4 | 5 | - | - |
| Feedback | Useful | 5 | 5 | - | - |
| Feedback | Explains enough | 4 | 5 | - | - |
| Feedback | Personalized to how I like things explained | 4 | 5 | - | - |
| Tutor | Guardrails | 4 | - | - | - |
| Tutor | Personalization | 3 | - | - | - |

### What the step bought and what it cost

Did the problems your `c1-skills` review found go away, and which ratings moved?
Which loop earned its cost and which did not?
If a loop ran several passes and the final output was no better than the first draft, say so, because that is the finding.

The results show that lesson quality did improve. However they are mixed in terms of the cost of these improvements. The lesson reviewer fixed a few of the problems found in c1-skills. Factual coverage rose from 0.83 to 1.00, and the length ratio increased from 0.56 to 0.65, which meets the benchmarks length ratio requirements. My ratings for technical correctness and alignment rose from 4 to 5, and the overall lesson quality increased from 3 to 4. Pedagogy stayed at 4, because the lesson is still short to take 30 minutes. 

The quiz reviewer did have a positive effect on the questions. My ratings for coverage and alignment increased from 4 to 5. Wording improved from 3 to 4. The automated scores were perfect in both versions, but the reviewer caught some issues the checks didn't, especially for questions that made the answer sort of obvious. The grade reviewer made some useful improvements for feedback, but they were still fairly minor. My ratings for explanation quality and personalization rose from 4 to 5, even though grading accuracy was already perfect. 

The biggest problem with these reviewers was the cost increase. The total token count went from 1.25M to 2.68M, and the cost estimate increased from $1.50 to $2.34. The tokens used for teach rose from 399k to 1.33M, quiz tokens rose from 135k to 335k, and grading tokens from 283k to 575k. Additionally, the total runtime increased from 5.4 to 8.9 minutes.

I think the lesson reviewer's cost is most justified. It found fairly significant omissions and it improved both the objective scores and my personal quality assessment. The quiz reviewer was useful, especially in the realm of question wording, but the cost increase was harder to justify with the automated results. The grade reviewer was the least worth it of the three because the feedback without it was already good, and as expected the revisions offered were pretty small.

Overall, the c2-review did create better learning materials, but the improvements required much higher token consumption. Since both configurations only have a single full run, I can't be confident that the observed improvements would continue across further repeats. The next step should look at splitting lesson generation into more specialized, specific tasks that keep the improvements without adding to the already high overhead. 

---

## 4. Step 3: `c3-split` against `c2-review`

### What changed

Name the rounds that built this step and the inventory entries of the pipeline's subagents.
Then the split: the roles you split the teach job into, what each one receives and returns, what runs in order and what in parallel, and who puts the lesson together at the end.
Why this split and not a smaller one, and what did you try that you took out again?

TODO: the rounds and entries, and the design of your teach split.

### Your review, the objective checks and the cost

Paste `uv run p3 report --configs c2-review,c3-split`.

TODO: paste the report tables.

### What the step bought and what it cost

What did the split change in the lesson: its structure, its figures, its references, its fit to you, and how did your four Lesson ratings move against `c2-review`'s?
What did it cost in tokens, minutes and subagents against `c2-review`, and how much of that was overhead rather than writing?
Each step has one run, so say how confident you are, and what would change your mind.

TODO: your judgment of step 3.

---

## 5. `final` against `c0-baseline`, with repeats

### What went into `final`

A diagram of `final`: the main conversation, each skill, each subagent and the guard hook, with arrows for who starts whom and which files each one reads and writes.
ASCII art in a code block or a Mermaid block are both fine; for example:

```
/quiz (skill, main conversation)  writes drafts/0002.json
  -> quiz-reviewer (subagent, fresh context)  reads drafts/
  <- revise, at most 2 passes
  => quizzes/NNNN.json, keys/NNNN.json, review-records/NNNN-quiz.md
```

Draw yours, all four jobs, and delete the example.

TODO: your diagram.

What did you keep from each step, what did you drop, and why?
Point at the inventory entries in `reviews/components.md` rather than repeating them.
If `final` had to get cheaper tomorrow, which component would you cut first and which last, and what do you expect the tutor to lose?

TODO: what `final` is made of, and what you would cut first.

### Your review, the objective checks and the cost

Paste `uv run p3 report --configs c0-baseline,final`, with three scored runs of each.

TODO: paste the report tables.

### What the repeats let you claim

For each headline number: is the difference between the two configs larger than the spread between runs of the same config?
Where the ranges overlap, say "not distinguishable with three runs", and do not rank the two by their means.
Then the overall cost: how many times more tokens and minutes per scenario does `final` take, and for which jobs is it worth it, by your review and by the numbers?

TODO: your reading of `final` against the baseline.

---

## 6. The ablation

Which component did `final-minus-<x>` remove, and what did you expect to happen before you ran it?
Paste `uv run p3 report --configs final,final-minus-<x>`.
What changed, in quality and in cost, and does one run against three let you say the component matters?
If you looked at its outputs, what did you see that the numbers do not show?

TODO: your ablation, its prediction, its table and your reading.

---

## 7. The guard

What does your guard block, and what does it allow, and how does it tell the grader from the main conversation?
Why is it a PreToolUse hook in `tutor/.claude/settings.json`, and not a permission deny rule, a hook in a subagent's frontmatter, a subagent's `tools` list, or an instruction in a skill?
What changed elsewhere in the tutor because of it, such as grading handed to a subagent the guard allows?
Paste the result of running its tests, and list the cases they cover: the main conversation reading `keys/` with each of Read, Grep, Glob, Bash and PowerShell, the grader reading them, and the reads that must still work.
Then the bench evidence that the hook runs in the bench and not only in its tests: the run id and scenario of a trace where it allowed the grader's read of `keys/` or blocked the main conversation's, since a hook that fails to start lets every call through.
Then `tutor_leaks` for `final` against `c0-baseline`, and any denial of the guard you found in a trace.
Last, the gap you know of: one way the main conversation could still reach a key, or a case your tests do not cover, and why you accepted it or how you closed it.

TODO: the guard, its tests and the evidence.

---

## 8. The blind comparison

### `c0-baseline` against `final`

Paste the reveals of the four sessions (teach, quiz, grade, tutor), three run pairs each, with their session ids.

TODO: paste the four reveals with their session ids.

### Your open reviews against your blind picks

This is the check on your own bias, as lecture 24 checks a model judge's.
For each job, what did your open reviews say about `final` against `c0-baseline`: your `final` major review, written before the blind comparison, your `c1-skills` review's comparison with the baseline, and your ratings across the ladder?
Then, for each job, did the blind tally and your reasons agree with them?
Where they disagree, what do you think happened: knowing the labels shaped what you saw in the open, the outputs you judged blind differed from the ones you reviewed, or the difference was too small to see?
Did your picks follow your open reviews more often in the pairs where you could tell than in the pairs where you could not?
Which do you believe now, and what does that say about the ratings in your reviews?

TODO: your open reviews against your blind picks.

### A second blind comparison

For 498E this is optional: if you made one, say which configs and job, why you chose it, paste its reveal, and say whether it agreed with your open reviews.
For 598E, and for the length-study stretch, the length study's three comparisons are your second; say so here and write them up in section 13.
If you made no second comparison, say so in one line.

TODO: your second blind comparison, or why there is none.

---

## 9. The test topics

### The two topics

Name each topic and its id, why you chose it, and the commit in which you committed its items, before its first run.
If you fixed a real mistake in a topic after its runs, as `bench/own/README.md` describes, list the run ids you deleted, what you changed and why.

TODO: your two topics and their commits.

### Results

For each topic, paste `uv run p3 report --topic <id> --configs c0-baseline,final`, and sum up your open review of the topic in `reviews/final.md` in two or three sentences.

TODO: paste the tables for both topics, with your summaries.

### Did the architecture still pay off?

Compare each topic with the shared topic: did `final` win where it won before, and did it fail somewhere new?
Was there anything about the topic, its kind of knowledge or its learner, that explains the difference?
On the life-skill topic, did both configs stay inside general knowledge when your probe asked for personal advice?

TODO: your reading of the test topics.

### Your learning sessions against the bench

Your three learning sessions are in `reviews/final.md`.
Did the bench predict what you saw in them?
Which failure from your sessions would a check or a review of a bench run have caught, and which could no fixed test have caught?
Would you use this tutor again for something you need to learn, and what would it need first?

TODO: the bench against your sessions.

---

## 10. The judge check

Take ten decisions the judge made: for example ten tutor replies it marked met or not met, or ten fact verdicts from your lessons (the judge checks six facts in each lesson on the shared topic, so ten come from two lessons).
Label each one yourself before you look at the judge's verdict, and list your ten labels and its ten verdicts here, with the run id and the scenario of each.
How many of ten did you agree on?
Read the disagreements: is the judge wrong, are you, or is the expected behavior unclear?
What does that agreement mean for the judge numbers you reported above?

TODO: your ten labels, the agreement, and what it means.

---

## 11. A change that did not pay off

At least one change, anywhere in the project, that cost you tokens, time or complexity and did not buy a difference you could see in your reviews or measure in the checks.
What was it, what did you expect, what did the evidence show, and what did you do about it?
Name the round or the inventory entry where it shows.

TODO: the change that did not pay off.

---

## 12. The trade-offs

Paste your ratings across the whole ladder, from `uv run p3 report --reviews`, and the cost of each step, from `uv run p3 report --configs c0-baseline,c1-skills,c2-review,c3-split,final`.

TODO: paste the ratings and cost tables for the whole ladder.

Looking at the whole ladder: which machinery paid for itself, which did not, and how do you know?
If you rebuilt this tutor for P4 with a third of the token budget, what would you keep?
Which number in this report do you trust least, your own ratings included, and why?

TODO: your trade-offs.

---

## 13. The stretch

For 598E this is the rider, and its write-up goes here, with `PREREG.md` beside it.
Cover five things:

1. the option's name;
2. what you did, and the files that hold it;
3. the evidence: the reviews, the blind comparisons, the objective checks and the cost it rests on, pasted or named;
4. what that evidence lets you claim, and what it does not;
5. one thing you would do next, and what result would tell you it worked.

TODO: your stretch.
