# Reviews: c3-split

Your quick rounds while you split up the teach job, and then the major review of `c3-split`.
Add one subagent of the teach pipeline per round, so the run before it shows the lesson without it and the run after it shows the lesson with it.
The major review covers the lesson only, and its previous step is `c2-review`.
`reviews/README.md` says how to write each part.
You write your thoughts, ratings and feedback; Claude Code writes only the What changed part of each round.
Keep every heading as it is, because `p3 check` reads them, and add a round by copying the last one with its marker lines.

## Quick rounds

### Round 1

**Run:** bench/runs/c2-review/20261117-220943-agent-architecture-m30-r1

**My thoughts:**

The c2-review lesson did manage to cover the required material, and it did it correctly, but its length ratio was 0.65. This means it fell short of the requested 30 minutes. I think splitting lesson planning from writing could help fix this. I want to add a planner subagent that takes the lesson request, mission, notes, preferences, and existing learning records, then produces a structured outline for the writer. 

The plan should specify the learning goal, section order, examples, and a word budget for each section that is based on roughly 150 words per requested minute. I want the planner to allocate enough space for explanations and exercises, but I do not want it to introduce any repetitive filler. I'm also worried about cost, because the c2-review teach run already consumed 1.33M tokens, so the planner's output should be concise and structured instead of giving a full lesson draft. 

**What changed:**

- Kind: new subagent
- Files: tutor/.claude/agents/lesson-planner.md, tutor/.claude/skills/teach/SKILL.md
- Why: Your thoughts asked for a planner that turns the request and your files into a concise structured outline with word budgets of about 150 per minute, so lesson-planner writes a plan of at most about 700 words to drafts/plan.md (sections, minutes, budgets, one home per idea, facts, examples) and the teach skill writes the lesson to that plan and to its budgets, keeping the lesson reviewer as it was.

### Round 2

**Run:** bench/runs/_live/20261118-052513-agent-architecture-m30-r1

**My thoughts:**

The lesson planner subagent does seem to have helped. The length ratio increased from 0.65 to 0.70. The factual coverage stayed at 1.00 and token consumption was about the same. The planner created a useful outline that assigned all the required facts to sections, specific examples and exercises, and a 4,500 word budget was distributed across 30 minutes. The lesson followed most of that structure, including the worked token count example, without much obvious repetition. 

However, the actual produced lesson was only 3,131 words, which is far below the planned 4,500. The reviewer had to change the section timing and fix a few issues as well. I think the remaining problem is partially in the writing instead of in the planning. For Round 2, I want to add a writer subagent that receives the plan and creates the lesson content according to its section budgets. It should spend additional space on explanations, worked examples and practice instead of adding any filler. I also want to avoid significantly increasing costs, since the planner version already uses 1.30M tokens. 

**What changed:**

- Kind: new subagent
- Files: tutor/.claude/agents/lesson-writer.md, tutor/.claude/skills/teach/SKILL.md, tutor/.claude/scripts/wordcount.py, tutor/.claude/settings.json
- Why: Your thoughts found the lesson 3,131 words against a 4,500-word plan, so lesson-writer writes the lesson to the plan's section budgets and measures it with a small word-count script (allowed in settings.json) that counts as the bench does, then fills only the thin sections with the plan's examples and practice, at most two rounds, and the teach skill no longer writes the lesson itself.

### Round 3

**Run:** bench/runs/_live/20261118-054419-agent-architecture-m30-r1

**My thoughts:**

Adding the lesson writer improved the length ratio from 0.70 to 1.00. It maintained the full factual coverage and didn't detect any misconceptions or dead links. The additional length in the lesson appears to be useful rather than just being filler. The token counting example is more developed, and the CNC router example slowly gets rid of hints before having the learner calculate the token costs on their own. The reviewer was able to catch some repetition and missing guidance on retrieval, and these issues were fixed in the revisions.

There was an increase in cost, however. The token usage rose from 1.30M to 1.62M. The runtime rose from 4.3 to 5.6 minutes. The planner and writer did seem to work well in concert to improve the lessons and the length, but the reviewer did still have to adjust the section timing a bit. The lesson also had two diagrams that were fairly helpful, but the context window diagram could represent the relative token counts better.

The run also had a bash permission denial, with the reviewer reporting being unable to run the word counter script during revision. The benchmark still finished successfully, but I want to check that the writer and reviewer can use the permitted counting script without needing much broader bash access. 

For Round 3, I want to add a visual designer subagent that produces diagrams from the plan and the fully written lesson. It should have a focus on accurate, readable figures that make concepts more clear without acting as useless bloat. I want to keep the better length accuracy and avoid adding unneeded cost. 

**What changed:**

- Kind: new subagent
- Files: tutor/.claude/agents/visual-designer.md, tutor/.claude/agents/lesson-writer.md, tutor/.claude/agents/lesson-reviewer.md, tutor/.claude/skills/teach/SKILL.md, tutor/.claude/settings.json
- Why: Your thoughts asked for a visual designer that draws accurate, readable figures from the plan and the finished lesson without adding cost or length, so visual-designer fills figure slots the writer leaves, with SVG drawn to scale and short labels; and the Bash denial was the teach skill running the word count with a -I flag, so the allow rule now covers that form and the skill and the reviewer are told the one exact command.

### Round 4

**Run:** bench/runs/_live/20261118-060700-agent-architecture-m30-r1

**My thoughts:**

Adding the visual designer subagent didn't hurt the lesson length significantly, with the ratio changing from 1.00 to 0.99. The factual coverage stayed at 1.00. I think the figures are more useful than in the previous lesson. Figure 1 shows the context window components with proportional sizes. This addresses the scaling inaccuracy I saw earlier. Figure 2 shows how searching returns a small snippet list before loading the relevant page. This helps show why retrieval saves context. Both of these figures support the explanation instead of just filling space up. 

The cost was better than I expected. The total token consumption fell from 1.62M to 1.40M, although runtime increased a little bit, and the estimated cost rose from $1.21 to $1.25. The reviewer corrected a worked example that was contradictory. It also adjusted the section timing, and got rid of repetition, so the system is not perfect. The retrieval section seems to be overly dense for the time alloted to it. 

For Round 4, I want to add a references finder subagent that checks sources used to support important technical claims. The existing lesson does link to relevant documents, but I think stronger assurance that citations actually support the claims made is worth it. It should run after the planner but before the writer, so the writer gets the verified sources it needs rahter than having citations be checked only after the lesson is written. The pipeline should be planner, then references finder, then writer, then visual designer, and finally the lesson reviewer. It should return a concise set of sources and identify unsupported claims before the writer produces the lesson, instead of doing a whole extra lesson review. I want to avoid increasing the costs significantly, because the pipeline already uses four subagent calls. 

**What changed:**

- Kind: new subagent
- Files: tutor/.claude/agents/references-finder.md, tutor/.claude/agents/lesson-writer.md, tutor/.claude/skills/teach/SKILL.md
- Why: Your thoughts asked for a references finder between the planner and the writer that checks the key claims against their sources and returns a concise verified list, so references-finder checks at most ten claims with about eight fetches and writes drafts/sources.md with the wording for any unsupported claim, and the writer cites only from that file; the pipeline is now planner, finder, writer, visual designer, reviewer.

## Major review

**Run:** bench/runs/c3-split/20261118-070939-agent-architecture-m30-r1

**Live tries:**

I ran the tutor and asked for a 15 minute lesson on how multiple AI agents divide up a complex task, including a concrete software engineering example. All five of the teaching subagents completed successfully. The tutor produced a lesson with a payments API migration across 40 modules as the running example.

I liked the exercises, especially how they required me to apply the concepts rather than just memorizing definitions. The diagrams were useful in general. The diagram showing which steps could run in parallel and what needed to be run sequentially was clear. The lead-worker relationship diagram helped explain the overall architecture. I was less impressed with the diagram showing how only a summary passes from a subagents context. It did communicate the idea, the layout for the context of the main agent was sort of confusing at first glance. I appreciated the citations throughout the lesson, as it helped give the technical claims more credence, and the references listed at the end.

The lesson reviewer found several issues, including the missing details about the coordination limitations and a lack of evidence for the cost and speed tradeoffs. The tutor made revisions to address these issues, which implies the review stage was useful. However, the final lesson was about 2,858 words, which corresponds to roughly 19 minutes instead of the requested 15. Some of the revisions seemed to introduce duplicate explanations, but the tutor attempted to remove them afterward. Overall, I thought the lesson was well structured and the examples and exercises were useful. However, the length accuracy and final output verification could be improved upon.

### Lesson

#### Technical correctness and facts

Rating: 5/5

The lesson appears to be technically accurate and it covers the required contents, including context windows, token costs, persistant memory, retrieval and compaction. The benchmark said the factual coverage was 1.00, without any misconceptions or dead links. The references finder also created a report that checked 11 technical claims against sources. It marked all of these claims as supported. I liked how the lesson cited its sources throughout the explanations and at the end. The numerical examples were explained to be illustrative and not actual API measurements, avoiding misleading the learner. The reviewer did catch some issues with the arithmetic and wording, but these were fixed before the final lesson was created. 

#### Pedagogy

Rating: 4/5

I thought the lesson did a good job at making abstract ideas more concrete. I liked the Python code snippet it provided that showed how the program maintains conversation history and sends it back to the model on each iteration. This helped connect the explanation to something I could implement, making it more real for me. I also appreciated the worked example for token counting, and the diagrams included. 

I liked the practice checks especially. They were hard enough to require some thought, but not so hard to be discouraging, and they didn't expose the correct answer too quickly or easily. The lesson had practice that became less and less guided, which I think was more useful than just asking the learner to recall simple facts. One criticism I have is that some of the sections were a little too dense for the time allocated to them, especially the retrieval section. Some of the explanations were longer than necessary.

#### Alignment with the learning goal

Rating: 5/5

The lesson was well aligned with the goal of teaching students to decide what belongs in the context window versus what should be saved between sessions. It also taught what should be retrieved when needed. I think the makerspace assistant example was consistent with how it was used. The exercises required the learner to apply those decisions correctly rather than just memorizing definitions. The lesson also built on the earlier agent loop material without spending too much time reteaching it, which would be repetitive.

#### Overall quality

Rating: 4/5

Overall, I think this lesson was much improved over the earlier lessons. It had a clear structure, the examples and code snippets were useful, and the practice exercises felt like they had a purpose. The diagrams helped to explain the concepts, and the cited sources added credibility to the lesson as a whole. The lesson was also closer to the requested length, with a benchmark ratio of 1.01. There were still some weaknesses, however. Some of the sections were a bit dense, and the lesson reviewer needed to correct a few issues before the output was fully ready. The architecture did consume a lot more tokens, and it took longer to execute. Even with those issues, I think the lesson is good and the added components were useful in the improvements they brought.

### Compared with the previous step

The biggest improvement over the c2-review was the lesson length. The length ratio rose from 0.65 to 1.01, while the factual coverage stayed at 1.00. No misconceptions were detected. The new architecture separates the planning, source verificaiton, writing, visual design, and review into different subagents. This seemed to create a more complete and structured lesson.

The cost was fairly substantial though. The teach run token cost rose from 1.33M to 2.06M tokens. Runtime rose from 3.6 to 7.5 minutes. I think the better lesson quality justifies some increased cost, but the system is getting fairly expensive for just one lesson. The quiz and tutor benchmark results got worse even though those components were not changed. This could reflect run-to-run variation rather than being a real effect of the new teaching pipeline. 

### What the next step should fix

For the final architecture, I want to keep the improvements in the lesson length, worked examples, practice exercises, and source verification. The biggest lasting issue with the teaching is that some of the sections were dense relative to the alloted time. I would like the planner and reviewer to be more careful about whether the material can be completed in the alloted time, instead of just relying on word counts. The live try also produced a roughly 19 minute long lesson despite my request for 15 minutes, which suggests the length control still needs to be improved even though the full benchmark achieved a ratio of 1.01.

I also want to investigate why the quiz and tutor benchmark results got worse, and fix their reliability without increasing cost too much. The final architecture should keep the specialization introduced in c3-split that proved to be useful, but it shouldn't add more complexity than is needed. 
