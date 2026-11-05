# Project 3 - Build a Tutoring Agent

**CSCI 498E / 598E - Coding with AI Agents**

| | |
|---|---|
| **Weight** | 20% of your final grade |
| **Points** | 200 on Canvas: 150 for this project and 50 for a video, handed in together in one discussion post |
| **Released** | Tuesday, November 3 (lecture 19) |
| **Due** | Tuesday, November 24, 11:59 pm, one deadline for everything |
| **Work** | Individual; 598E adds a rider (below) |

You hand in three things:

1. A **public GitHub repo** made from this template, whose URL you post in the Project 3 discussion on Canvas.
2. The **work inside it**: your tutor in `tutor/` with its skills and subagents, every snapshot on the architecture ladder in `configs/`, your bench runs in `bench/runs/` and your blind comparisons in `bench/compare/`, your two test topics in `bench/own/`, your reviews and the component inventory in `reviews/`, and `EVAL.md` written in your own words, plus `PREREG.md` for 598E or the length-study stretch.
3. A **5 to 10 minute video**, in the same discussion post.

---

## Start here

This README is the brief: what you hand in, the rules, and how I grade.
The walkthrough is the guide in `guide/`, part of this repo: for every step, what to do, in which window, and why the project asks for it.
Open `guide/index.html` in your browser: in VS Code, right-click it, choose "Reveal in File Explorer" (Windows) or "Reveal in Finder" (macOS), and double-click it; or, from a terminal in `work/p3-tutor`, run `start guide/index.html` (Windows, in Git Bash or PowerShell) or `open guide/index.html` (macOS).
If the guide and this brief ever disagree, the brief wins, and please tell me so I can fix it.

You work on P3 in one VS Code window with `work/p3-tutor` open as its own folder, through two Claude Code sessions with separate jobs, each in its own terminal started in `work/p3-tutor`.
The Guide, `claude --agent p3-guide`, explains each step and why it exists and names the one next thing to do, and it never changes a file; the Builder, plain `claude`, changes your tutor, one change per round, and runs the `p3` commands you ask for.
Full bench runs go in a third terminal with no Claude Code in it, a plain terminal, and `guide/02-two-windows.html` shows how to start each window and what to say to it.
Whenever you are unsure where you are, run `uv run p3 next`, or ask the Guide "What's next?": it prints where you are on the project's map, the one next thing to do and the guide page that explains it, and it changes nothing.

On the first day (`guide/01-setup.html` has each step in detail):

1. Click **Use this template** at the top of this repo, then **Create a new repository**; name it **`p3-tutor`** and make it **Public**.
2. Clone it into `work/`, your own space in the course repo, which git ignores: in a terminal at the course repo's root, run `gh repo clone <your-github-username>/p3-tutor work/p3-tutor`.
3. Open `work/p3-tutor` as its own VS Code window (File > Open Folder, or `code work/p3-tutor`), so every terminal and every Claude Code session starts in your P3 repo.
4. Check that `uv --version`, `claude --version` and `python --version` (`python3 --version` on macOS and Linux) each print a version.
5. In `p3.json`, set `section` to `"498E"` or `"598E"`; 598E also sets `stretch` to `"length-study"`, and 498E leaves it `null` until choosing one.
6. Run `uv run p3 check`: on a fresh copy it lists the items you have not done yet as work to do, which is not an error, and only a FAIL line means something is broken.
7. Commit and push, and wait for the `p3-check` run on your repo's **Actions** tab to go green; CI never calls a model, it checks the files you committed.
8. Start the Guide and the Builder (`guide/02-two-windows.html`); the first time, Claude Code asks whether you trust the folder with "No, exit" highlighted, so press the down arrow to "Yes, I trust this folder", then Enter.
9. Run the baseline once, quickly: `uv run p3 bench --config c0-baseline --quick`, five scenarios and their scoring, the first command that draws on your Claude plan.
   Then read what it made, `KNOWN-GAPS.md` and `reviews/README.md` (`guide/03-baseline.html`); the gaps in `KNOWN-GAPS.md` are starting points I saw, not a checklist.
10. Start the baseline's three full runs in a plain terminal: `uv run p3 bench --config c0-baseline --repeats 3`, 30 sessions plus their scoring, about 20 to 25 minutes in my pilot.

Please do all of this on the first day, because setup is the step with the most ways to go wrong, and you want it behind you while there is plenty of time.
There are no checkpoints; `guide/17-pace.html` has the pace I would keep, week by week, and my estimate of your own time: about 32 hours for 498E, plus 4 to 6 for a stretch, and about 40 to 42 for 598E.

A full bench run takes much longer than a quick one.
In my pilot one full run took about 6 minutes for the baseline and about 17 for a config with review loops, three repeats of a larger config can take an hour or more, and the teach scenario alone may run up to 45 minutes.
So you start full runs yourself, in a plain terminal in `work/p3-tutor`: they must not stop when a Claude Code window closes, and they run longer than Claude Code lets a command run in the foreground.

**When you learn with the tutor**, open a terminal in `work/p3-tutor/tutor` and start `claude` there; its learner files (`MISSION.md`, `NOTES.md`, `lessons/` and the rest) are created in `tutor/` as you go.
Claude Code also reads the `CLAUDE.md` of every folder above the one it starts in, so if a session there ever acts more like a course assistant than your tutor, that is why, and you can learn from a copy of `tutor/` outside the course repo instead.

---

## What this project is

You build a tutor that runs entirely inside Claude Code and does four jobs.

| Job | What it does |
|---|---|
| **Teach** | writes a comprehensive lesson of a requested length, such as 30 minutes or an hour: a plan, explanations, examples, figures and visualizations, and external references where they help |
| **Tutor** | a conversational helper the learner talks to on the go, personalized to how the learner likes to talk, with guardrails: it does not hand out quiz answers |
| **Quiz** | a quiz with an answer key, at the right difficulty, covering the core of the lesson, clearly worded and aligned with the learning goals |
| **Grade** | grades plus useful feedback: a verdict on each answer and enough explanation, in the way this learner likes things explained |

The template ships a tutor that already does all four, with one `teach` skill doing everything in one shot.
You build four skills of your own, then add agentic architecture in fixed steps, first review loops and then a split of the teach job, and you measure every step: what it gained in quality, and what it cost in tokens and time.

Much of a tutor's quality is personal fit, and no script can tell you whether a lesson works for you, so you are the judge.
At every step you read and try what your tutor made and write a review of it, and your reviews drive the next change.
Fixed objective checks catch what taste cannot: a wrong fact, a wrong answer key, a quiz answer given away.

The tutor is not the point; the engineering judgment is.
Lectures 18 and 19 asked when a fixed workflow beats an agent and whether more agents help.
Here you find out for one real system of your own: which machinery pays for itself, which does not, and how you know.
It uses what lectures 15 to 19 taught (skills, MCP, hooks, workflows and agents, multi-agent systems), and lectures 20 to 24 arrive while you work on it: the agent loop from scratch and the Agent SDK, construct validity, repeats with intervals, and judges.

I made four choices you should know about, because they shape the rest of this brief.
The baseline is competent on purpose.
It keeps the teach skill's pedagogy and meets the output contract, because a broken baseline makes every change look like a win, and the honest question is whether your machinery beats a good simpler system.
The steps are fixed and their design is yours.
Everyone builds the same kinds of architecture, so the class's results can be compared, and what each reviewer checks, how many passes a review loop may run and how you split the teach job are your decisions.
You review your tutor in the open at every step, and you judge it blind once or twice.
Only you can say what works for you, so your reviews carry the quality judgment as you build; but you built the later versions and you expect them to win, so at the end you compare `c0-baseline` with `final` without knowing which made what, and check how far your open reviews agree with your blind picks.
That is the one blind comparison everyone makes; 598E, and 498E with the length-study stretch, make a second one in the length study, and any other 498E student may add a second of their choice.
And every step is measured in cost as well as quality, because a review loop or a pipeline of subagents is never free, and a gain is only worth having at a price you can name.

### The repo, and who owns what

The rule behind the layout is simple: I own everything that runs the measurement, and you own everything that decides how the tutor behaves.

| Path | What it is | Whose |
|---|---|---|
| `tutor/` | the tutor: `CLAUDE.md`, `PREFERENCES.md`, `FORMATS.md` and `.claude/` (skills, agents, settings) | yours |
| `configs/` | snapshots of the tutor; `c0-baseline` ships, and you add the rest with `p3 snapshot` | yours, written by `p3` |
| `bench/FORMATS.md`, `bench/scenarios.json`, `bench/judge/`, `bench/topics/` | the output contract, the scenarios, the judge prompts and the shared topic | mine, hash-checked |
| `bench/own/` | your two test topics | yours |
| `bench/runs/`, `bench/compare/` | your committed runs and blind comparisons | written by `p3` |
| `reviews/` | your quick rounds and major reviews, your learning sessions, your test-topic reviews, and the component inventory | yours; the Builder writes only what it changed in each round and the inventory's factual fields |
| `p3/` | the runner, the scorer, the comparison tool, the check and `p3 next` | mine, hash-checked |
| `tests/` | the tests of `p3` and of the Guide's guard, and the place for your own guard's tests | mine, plus the tests you add |
| `EVAL.md`, `PREREG.md` | your write-up | yours |
| `KNOWN-GAPS.md` | failures I saw when I ran the baseline, each with the run that shows it | mine |
| `p3.json` | your section and your stretch | yours |
| `README.md` | this brief | mine |
| `guide/` | the guide: the walkthrough of every step, opened from `guide/index.html` | mine |
| `CLAUDE.md` | the two roles, and the Builder's rules for developing this repo, including what it must never write for you | mine |
| `.claude/` | the two roles' files: the Guide's instructions in `.claude/agents/p3-guide.md`, the guard that keeps it read-only in `.claude/hooks/`, and `.claude/settings.json` | mine |

**The tutor lives in `tutor/`, not at the root.**
You develop it from the root, in the Guide and the Builder, and you learn with it by starting Claude Code inside `tutor/`, so the tutor's `CLAUDE.md` is never the one you develop with.

**A config is `tutor/CLAUDE.md`, `tutor/PREFERENCES.md` and everything under `tutor/.claude/`.**
The learner's files (`MISSION.md`, `NOTES.md`, `lessons/`, `quizzes/`, `keys/`, `grades/`, `learning-records/`, `assets/`, `submissions/`) are never part of a config.
Neither is `tutor/.claude/settings.local.json`, the personal file Claude Code writes when you approve a tool in a session of your own, which git ignores, so anything the tutor needs goes in `tutor/.claude/settings.json`.
`uv run p3 snapshot <name>` copies the live config into `configs/<name>/` and records a hash of its files in `configs/<name>/SNAPSHOT.json`, and the bench runs any snapshot by name.
I use snapshots rather than git tags because git does not push tags by default, and a run must always point at a config I can read.

**Who the learner is splits in two.**
A topic says what the learner knows: on the shared topic that is a fixed novice, described in the topic's `MISSION.md` and `NOTES.md`.
`tutor/PREFERENCES.md` says how the learner likes to learn, and it is yours on every topic: how you like things explained, the examples you relate to, how long and dense you like it, how you like feedback.
That file is what makes your reviews and your blind comparison personal, so write it in the first week and mean it.

### The output contract

`bench/FORMATS.md` says exactly what the bench reads, with a complete example of each JSON file, and `tutor/FORMATS.md` is an identical copy for your tutor to follow.

| Output | File | In short |
|---|---|---|
| Lesson | `lessons/NNNN-<slug>.html` | a complete, self-contained HTML page with two meta tags, `p3-minutes` and `p3-objective`; CSS inline or under `assets/`, no remote scripts or stylesheets, ordinary links to outside references welcome |
| Quiz | `quizzes/NNNN.json` | the items: id, type `mcq`, `numeric` or `short`, the objective each one serves, the stem, and options for `mcq` |
| Key | `keys/NNNN.json` | for each item the answer, accepted forms, a rationale, and the misconception behind each wrong option |
| Grades | `grades/NNNN-sN.json` | for each item a verdict (`correct`, `partial` or `wrong`), the misconception id if one applies, and the feedback |
| Learning record | `learning-records/NNNN-<slug>.md` | what the learner learned, in the teach skill's format |

A new file takes the next four-digit number after the highest one in its folder.
Everything else about how your tutor works is yours, but these files must match the contract, because the contract is what lets one script score every student's tutor.

### The architecture ladder

| Config | What it adds | Full bench runs on the shared topic |
|---|---|---|
| `c0-baseline` | nothing, as shipped: one `teach` skill, one shot | 3 |
| `c1-skills` | the four skills `teach`, `tutor`, `quiz` and `grade`, plus any others you like; still one agent | 1 |
| `c2-review` | review loops on teach, quiz and grade, as subagents | 1 |
| `c3-split` | the teach job split across subagents (planner, designer, writer, visual designer, references, and so on) | 1 |
| `final` | what earned its place (a step that did not pay may be dropped), plus a guard hook keeping the answer keys from the tutor | 3 |
| `final-minus-<x>` | `final` with one component removed, the ablation | 1 |

Each step is measured against the one before it, in quality (your major review and the objective checks) and in cost (tokens, turns, subagents and time).
The ablation names what it removes, for example `final-minus-quiz-review` or `final-minus-planner`, and you need at least one.
Config names use lowercase letters, digits and hyphens.

**The same loop, at every step** (`guide/07-reviews.html` explains its reviews, and each step's page walks through it):

1. **Build the step in quick rounds** ("Your reviews" below says how): at least two for each of `c1-skills`, `c2-review` and `c3-split`, optional in `final`, one component per round.
2. **Snapshot it** when you are happy with it: `uv run p3 snapshot c1-skills`.
3. **Make its full run**, in a plain terminal: `uv run p3 bench --config c1-skills`.
4. **Write the step's major review** in `reviews/c1-skills.md`, criterion by criterion, on that run's outputs and your own live tries of the tutor.
5. **Write the step's section of `EVAL.md`:** paste the tables from `uv run p3 report --configs c0-baseline,c1-skills`, your ratings among them, and write what the step bought and what it cost.
6. **Add the step's new skills and subagents** to `reviews/components.md`.
7. **Commit** `configs/`, `bench/runs/` and `reviews/`.

A snapshot is frozen once it has runs.
`p3 snapshot` refuses to overwrite a name without `--force`, and overwriting one that has runs makes `p3 check` fail, because those runs no longer match their config; make a new name instead.

#### Step 1: four skills (`c1-skills`)

Write `tutor/.claude/skills/<job>/SKILL.md` for each of `teach`, `tutor`, `quiz` and `grade`, however you like, and any other skills you want, on any topic.
The four names are fixed so the bench can start each job with `/<job>`; a config without one of them routes that job to `/teach`, which is how `c0-baseline` does all four jobs with one skill.
This step is still one agent, so no quick round in it adds a subagent, and `p3 check` fails on a subagent in `configs/c1-skills/` or a round of Kind `new subagent` in `reviews/c1-skills.md`.
Add one new skill per round, so each round shows one job before and after its skill; with a round to rewrite `teach` itself, this step usually takes four rounds or more.
It is measured against `c0-baseline`, and its major review covers all four jobs; be specific in it, with the item ids and quotes a reviewer could check for, because what it finds becomes the checklists of your reviewers in step 2.
`c0-baseline` keeps the neutral `PREFERENCES.md` the template ships and `c1-skills` is the first config with yours, so this step, and `c0-baseline` against `final`, measures your skills and your preferences together; say so in `EVAL.md`, and say which differences you think came from which.
`guide/08-step1-skills.html` walks through the step, including how the bench starts each job.

#### Step 2: review loops (`c2-review`)

Add review loops on teach, quiz and grade, with the reviewers as subagents; the tutor gets none.
A review here is about quality, not agreement, and a reviewer that votes "looks good" is worth nothing.
Each job's reviews cover the same criteria as your own major reviews (the table in "Your reviews"): the quiz's five for quiz, the feedback's three for grade, and the lesson's four for teach, as separate reviews, each with its own checklist and its own findings, so a fact-check is never folded into a general impression.
How you build that is yours: four reviewer subagents, or one lesson reviewer whose checklist has four separate sections and reports on each; one reviewer per job, three in `c2-review`, is what the 498E example in "The component inventory" counts toward the minimum of five subagents.
Add the reviewers one per quick round, so each one's with-and-without is the run before and after its round; with a loop on each of teach, quiz and grade, that is at least three rounds, even though `p3 check` counts only the two every step needs.
It is measured against `c1-skills`, and its major review covers the lesson, the quiz and the feedback.
`guide/09-step2-review-loops.html` has my advice for building the loops: checklists drawn from your `c1-skills` review, a fresh context for each reviewer, a cap on the passes, a record of what each loop did, drafts kept out of the folders the bench reads, and what to do about permission denials.

#### Step 3: split up the teach job (`c3-split`)

Split the teach job only, across subagents with jobs of your design: course planning, design, material writing, a visual and figure designer, a references finder, and so on; tutor, quiz and grade are not split.
Subagents are Markdown files in `tutor/.claude/agents/`, and `tutor/.claude/agents/README.md` explains what goes in one and which frontmatter fields matter.
Add the pipeline's subagents one per quick round, as in step 2.
You measure this step on teach, against `c2-review`, and its major review covers the lesson only (`guide/10-step3-split.html`).

#### `final`, the guard, and the ablation

`final` is what earned its place: a step that did not pay for itself may be dropped, and saying so with the numbers behind it is a good result.
`final` also adds a guard: a PreToolUse hook in `tutor/.claude/settings.json` that keeps the answer keys in `keys/` away from the main conversation while the grader can still read them, because every scenario's workspace holds a quiz's key, and a tutor that can read the key can hand out the answer.
In `c0-baseline` there is no guard, because a single agent has to read the keys to grade.
The guard comes with its own tests, as in lecture 17's lab: a small unittest file, for example `tests/test_guard.py`, that runs your hook script with sample hook inputs on stdin and checks that it blocks what it should and allows what it should.
Then confirm once, with a `--config live` run and its trace, that the hook really runs in the bench, because a guard that fails to run looks exactly like no guard; `guide/12-final.html#guard` has the facts the guard rests on, so read them before you build it.
Which agents may read the keys is your decision, the grader and perhaps a quiz reviewer, and once the guard is on, grading has to happen in a subagent it allows; give such a new component a quick round in `reviews/final.md`, so its inventory entry has its with and without.

Then snapshot `final`, commit `tutor/` with it, and run it three times; make at least one `final-minus-<x>` by removing one component, snapshotting it and running it once, then bring `tutor/` back with `git restore tutor/`; and run `c0-baseline` and `final` once each on both test topics.
Every one of these runs uses a frozen snapshot, so their order does not matter as long as `tutor/` is restored before your learning sessions; `uv run p3 next` lists the three repeats of `final` first, then the ablation's snapshot and run, then the test topics' runs.
The major review of `final` covers all four jobs, on one of its three runs, and its live tries are your three learning sessions with `final` on one of your test topics, all held on `tutor/` as you snapshotted it: note what they make you want to change instead of changing it.
Write that review before you start the blind comparison, and commit it, so your open judgment is on record before your blind one.

---

## Your reviews

This is the part of the project that only you can do.
A script can count facts and check keys, but whether a lesson teaches, whether a quiz item can be misread, whether feedback helps and whether the tutor is good to talk to are things you find out by reading and trying, and then saying so in writing.
So you review your tutor at every step, and every review is recorded in `reviews/` and handed in.
`reviews/README.md` has the format and an example of each part, and `guide/07-reviews.html` explains every part and why it exists; this section is the requirements.

| File | What it holds |
|---|---|
| `reviews/c1-skills.md`, `reviews/c2-review.md`, `reviews/c3-split.md` | each step's quick rounds, then its major review |
| `reviews/final.md` | optional quick rounds, the major review of `final`, your three learning sessions, and your open review of the two test topics |
| `reviews/components.md` | the component inventory |

### Quick rounds, while you build

Each step is built in quick rounds: at least two for each of `c1-skills`, `c2-review` and `c3-split` (step 2 takes at least three, one per review loop), and as many as you like for `final`.
In each round you run the tutor as it stands, usually `uv run p3 bench --config live --quick`, or `--only` with the scenarios you are working on, which writes under `bench/runs/_live/`, a folder git ignores.
You read and try what it made, and write a few sentences of thoughts in the round: first whether the last change helped, then what worked, what did not, and what you want changed.
Then, in the Builder window, you say "Act on Round 2 of reviews/c1-skills.md." with your round and file, and it makes one change, by modifying a skill, building a new skill or building a subagent, and writes under your thoughts what it changed: the kind of change, the files, and why.
One new component per round keeps the evidence clean: the run before the round is the tutor without the component, and the run after it is the tutor with it, which is exactly what the component inventory asks you for.
Live runs are not committed, so quote what you saw in your thoughts.

### Major reviews, at the end of each step

When a step is done, you snapshot it, make its full run, and review it properly: that run's outputs, plus your own live tries of the tutor in `tutor/`, criterion by criterion.

| Job | Criteria | Reviewed in |
|---|---|---|
| Lesson | technical correctness and facts; pedagogy; alignment with the learning goal; overall quality | `c1-skills`, `c2-review`, `c3-split`, `final` |
| Quiz | difficulty; coverage of the lesson's core; wording and possible misreadings; writing quality; alignment with the learning goal | `c1-skills`, `c2-review`, `final` |
| Feedback | useful; explains enough; personalized to how I like things explained | `c1-skills`, `c2-review`, `final` |
| Tutor | guardrails; personalization | `c1-skills`, `final` |

Each criterion gets a rating from 1 (failing) to 5 (excellent) and written feedback that justifies it, with evidence: quotes, item ids, probe ids, sections of the lesson.
`reviews/README.md` says what each rating means, so a 4 means the same thing at every step.
Each major review ends by comparing the step with the one before it and saying what the next step should fix, or for `final`, what you would do next.
`uv run p3 report` gathers your ratings into one table, "Your ratings", with a row per criterion and a column per step, so you can see the ladder through your own eyes beside the objective checks and the cost.

### How I grade them

The reviews are 30 of the 150 points, the largest single part of the project.
I look for four things in them:

- **specific evidence**, such as quotes and item ids, so I can find what you saw;
- **ratings that your written feedback justifies**, because a 2 with a reason I can check is worth more than a 4 with none;
- **feedback that someone could act on**: "q2 never says better for what" can be fixed, and "the quiz could be clearer" cannot;
- **a visible trail** from each review, to the change it caused, to whether that change helped.

A step that made things worse is a fine result to report, as long as the trail shows it.

### Your part and the agent's part

You write the Run line and your thoughts in each round, the Run line and your live tries in each major review, every rating and its feedback, the comparisons with the previous step, what the next step should fix, your learning sessions, your test-topic reviews, and each component's purpose, review and whether `final` kept it.
The Builder writes only what it changed in each round, and it may fill in the inventory's factual fields: the kind, the step that added the component, and where its with-and-without evidence is.
It never writes or edits your parts, even to tidy them, and the root `CLAUDE.md`, which the Builder reads by itself because it starts in `work/p3-tutor`, tells it so.
Write your parts in the file, in the editor, and never type them into a chat for an agent to put there; add a new round yourself, by copying the last one with its marker lines, when you write its thoughts.
Your judgment is the measurement, and an agent's words in its place would measure the agent.

---

## The component inventory

`reviews/components.md` has an entry for every skill and every subagent you built anywhere on the ladder, kept or dropped.
It also replaces a separate design document: why each component exists is asked at the component, and `EVAL.md` holds the diagram of `final` as a whole; `guide/14-write-up.html` walks through an entry, with an example.
Each entry has the component's name as its heading (the skill's folder name, or the subagent's `name` from its frontmatter) and six fields:

- **Kind:** `skill` or `subagent`.
- **Step added:** the first of your snapshots that holds it, such as `c2-review`; `c1-skills` for `teach`, which ships with the baseline and which you rewrite in step 1.
- **Purpose:** why the tutor needs it, and why it is a skill or a subagent rather than the other.
- **With and without:** where the evidence is, usually the quick round that added it, whose run is the output without it while the next round's run is the output with it.
- **Review:** your short review of the output with it against without it, with evidence.
- **Kept in final:** `yes`, or `no, because` and the reason; a dropped component stays listed.

A component you tried in a round and took out before any snapshot gets an entry too, since it is often the best example of a change that did not pay; `p3 check` cannot see it, so keeping its entry is up to you, and it does not count toward the minimums.
The guard is a hook, not a skill or a subagent, so it has no entry; `EVAL.md` covers it, including why it is a hook.

**The minimums** are counted over what you built across the ladder, not over what `final` keeps, so dropping a component for a good reason never costs you.
A component counts when it appears in one of your snapshots, any folder under `configs/` other than `c0-baseline`, and a Markdown file under `.claude/agents/` counts as a subagent only when it has frontmatter with a `name`, which is also what Claude Code needs to load it.

| Section | Skills | Subagents |
|---|---|---|
| 498E | at least the four: `teach`, `tutor`, `quiz` and `grade` | at least five, for example three reviewers in `c2-review` and two roles in the `c3-split` pipeline |
| 598E | at least six: the four and two of your own | at least eight |

`uv run p3 check` compares the inventory with the skills and subagents in your snapshots, lists any component that has no entry, and counts them against your section's minimums.

---

## The bench

The bench runs every config through the same scenarios from the same starting state, scores the outputs with fixed checks, and records what each scenario cost; `guide/06-the-bench.html` explains every scenario, check and number in full.

### The topics

**The shared development topic is agent architecture**, a generic introduction I wrote for a fixed novice, an engineering junior who has used a chatbot and written some Python but never built an agent, so my knowledge is the ground truth, not the model's.
The bench teaches its objective O3 (context and memory), quizzes on O4 (workflows and agents), and grades two submissions of its six-item quiz `0001` on O1 and O2, and you tune your tutor on this topic and only this topic.

**You pick two test topics: one from another Mines course you have taken, and one life skill**, and write each one yourself in `bench/own/<id>/`, starting from `uv run p3 new-topic <id>`, as `bench/own/README.md` and `guide/11-test-topics.html` describe.
Commit a topic's items before its first run; the bench refuses to run a topic with uncommitted changes, and `p3 check --final` confirms from git history that every run used the items you committed.
When `final` is frozen, you run `c0-baseline` and `final` once each on both, the held-out check of whether the architecture still pays off where you never tuned it, and you review the two openly in `reviews/final.md`; there are no blind comparisons on the test topics.
Your three learning sessions with `final` are on one of the two topics, so choose it with both uses in mind: you write a topic's items from what you know well, and in the sessions you learn something you do not know yet.

### The scenarios and the objective checks

Each scenario runs headless, `claude -p` in a fresh folder outside your repo that holds the config, the topic's starting workspace and `FORMATS.md`, so every config faces the same test and no tutor can reach `bench/`.

| Scenario | The request | Objective checks (fixed) |
|---|---|---|
| `teach` | `/teach` a 30-minute lesson on objective O3 for this learner | self-contained HTML; the declared minutes and objective; length against the request; links that resolve; key facts present and correct, misconceptions asserted, and fit to the learner's level (the judge) |
| `quiz` | `/quiz` a six-question quiz with its key on objective O4 | the JSON follows the contract; every item tagged with an existing objective; two independent solvers answer without the key, which flags likely wrong keys and likely ambiguous items |
| `grade-s1`, `grade-s2` | `/grade` one learner submission for quiz `0001`, with feedback for each answer | verdicts against the true grades; how often a right answer is marked wrong; the misconception named when one applies; feedback present |
| `tutor-p01` to `tutor-p06` | one probe message through `/tutor` | quiz answers not given away (the key's answers searched for in the reply); the expected behavior (the judge) |
| cost | - | tokens (input, output, cache), turns, subagents, web searches and fetches, minutes, and the list-price equivalent, per scenario |

A full run is these ten scenarios; `--quick` runs `teach`, `quiz`, `grade-s1`, `tutor-p01` and `tutor-p02`, once.
Each scenario has a time and a turn limit, the same at every lesson length (`teach` 45 minutes and 200 turns, `quiz` and each `grade` 15 minutes and 80 turns, each tutor probe 10 minutes and 40 turns), and one that reaches its limit is recorded as a timeout or an error, which is a result about your tutor, so design review loops and pipelines to finish well inside them.
A job that failed counts against the config: a missing lesson scores 0 facts, a missing quiz or key 0 key agreement, a missing grades file disagrees on every answer, and a probe with no reply is not met.

The headline numbers that `p3 report` and the reveal use are `teach_facts_correct`, `teach_misconceptions`, `teach_length_ratio`, `teach_dead_links`, `quiz_key_agreement`, `quiz_wrong_key`, `quiz_ambiguous`, `grade_verdict_agreement`, `grade_false_wrong`, `grade_misconception_hit`, `tutor_leaks` and `tutor_behavior_met`, plus the cost: total tokens, output tokens, minutes, subagents and the list-price equivalent, per job and in total.
`guide/06-the-bench.html#headline-numbers` says what each one measures, and the same page explains the judge (a fixed prompt and the pinned model `claude-sonnet-5-5`), the two solvers and the length check, which is a rough reading-time estimate and a warning light, not a verdict.
After lecture 24 you check the judge against ten labels of your own and report how often you agree, because a judge you have not checked is a number you cannot lean on.

Commit your runs.
They are the evidence, and `p3 check` confirms each one points at a config whose hash still matches; `guide/06-the-bench.html#run-folder` says what a run folder holds and how to open each file.

### The blind comparison

`p3 compare` puts two configs' outputs for the same task side by side, without telling you which is which, and records your pick.
Your reviews are open, and you built the later configs and expect them to win, so at the end you judge `c0-baseline` against `final` with the labels hidden, and `EVAL.md` asks you to set your open reviews beside your blind picks.

| Comparison | Who | Jobs | Pairs |
|---|---|---|---|
| `c0-baseline` against `final`, on the shared topic | everyone; required | teach, quiz, grade, tutor | 3, 3, 36, 18 |
| a second comparison of your choice, on the shared topic | 498E; optional | your choice | from the runs you have |
| `c1-skills` against `final`, teach only, at 10, 30 and 60 minutes | 598E, and 498E with the length-study stretch; this is your second, and it is required | teach | 3 at each length |

That is the whole list: no comparison at each step, and none on the test topics, because your major reviews and your open test-topic reviews cover those.
The required comparison is the one `p3 check --final` looks for, and for the length study it also looks for the three teach comparisons.
The optional second comes from the runs you already have, such as `c1-skills` against `c2-review` on grade, and a blind comparison in the cheaper-tutor stretch counts as it.
Both configs need scored full runs on the topic at the same lesson length, and you run each session yourself, for example `uv run p3 compare c0-baseline final --job tutor`, because the picks must be yours.
Commit both files each session writes, and do not open its key file before you reveal.
Comparing costs time and no tokens, about an hour for the four sessions, and `guide/13-blind-comparison.html` takes you through a session, from the first pair to reading the reveal.

---

## Commands

Run each one in `work/p3-tutor` as `uv run p3 ...`, or without `uv` as `python -m p3 ...` (on macOS and Linux, `python3 -m p3 ...`), because `p3` uses only Python's standard library, from Python 3.11 on.
`uv run p3 <command> --help` lists a command's options, and `guide/18-commands-and-files.html` explains every option and file.

| Command | What it does |
|---|---|
| `p3 next` | where you are on the project's map, the one next thing to do, and the guide page for it; it changes nothing |
| `p3 check [--final]` | a checklist of the repo's state and of what is still to do in `reviews/`; it fails only when something is broken, and with `--final` also on anything not yet done |
| `p3 snapshot <name> [--force]` | copies the live config from `tutor/` into `configs/<name>/` with its hash; it refuses to overwrite a name without `--force` |
| `p3 bench --config <name>` | runs a snapshot's scenarios, scores them and prints a summary table; `--config live` runs `tutor/` as it stands, and `--quick`, `--only <ids>`, `--repeats N`, `--minutes M` and `--topic <id>` choose what runs |
| `p3 score <run-dir>` | scores a run, or scores it again |
| `p3 report [--configs a,b,...]` | the Markdown tables for `EVAL.md`: headline numbers and cost over the scored full runs, and "Your ratings" from your major reviews |
| `p3 compare <config-a> <config-b> --job <job>` | starts a blind comparison of two configs on `teach`, `quiz`, `grade` or `tutor` |
| `p3 compare --resume <session-id>` | continues a comparison you closed |
| `p3 compare --reveal <session-id>` | shows the result of a finished comparison, quality first and then cost |
| `p3 compare --list` | lists your comparison sessions |
| `p3 new-topic <id>` | writes a skeleton test topic in `bench/own/<id>/` |
| `p3 rehash` | mine, for when I change a fixed file; never run it in your repo |

---

## What the runs cost

Everything that runs `claude` draws on your own Claude plan: the scenarios, and the scoring calls after them (the judge, and the two solvers); comparing costs nothing, and neither does `p3 next`, `p3 check`, `p3 report` or `p3 snapshot`.
The dollar figure in `run.json` and in the reports is the list-price equivalent that Claude Code reports, not what you pay on a subscription; on your plan, the cost is your usage limit.

| The runs the project needs | Runs |
|---|---|
| The ladder, on the shared topic | `c0-baseline` 3, `c1-skills` 1, `c2-review` 1, `c3-split` 1, `final` 3, each `final-minus-<x>` 1: at least 10 full runs |
| The quick rounds | at least two in each of `c1-skills`, `c2-review` and `c3-split`, each a quick run or an `--only` run of `--config live`: with one new component per round, about 9 for 498E and about 14 for 598E |
| The test topics | `c0-baseline` and `final`, once each on both topics: 4 full runs |
| The length study (598E, or the stretch) | 18 teach-only runs |

**Plan for the cost.**
In my pilot, with Claude Code 2.1.314 and Sonnet, a full run of `c0-baseline` was about 1.85M tokens, and a full run of a review-loop config of my own (four skills, with reviewers on teach, quiz and grade, at most two passes each) about 7M.
Every `claude -p` call carries a fixed load of cached reads of Claude Code's own instructions and tools, and every subagent pays a share of it again, which is why fan-out is what drains a weekly limit and why the repeats are limited to `c0-baseline` and `final`.
If your `final` costs about what my review-loop config did, its three runs are about 21 million tokens, and with the ablation and the test topics' runs roughly 45 million go into week 3, so start `final`'s runs as early in that week as you can.
For 598E, a `final` with at least eight subagents may well take 10 to 15 million tokens per full run, three times over, on top of the ablation, the test topics and the length study's eighteen teach-only runs, three of them 60-minute lessons through your pipeline; so spread what can be spread: the baseline's runs in week 1, the length study's `c1-skills` runs in week 2 once `PREREG.md` is committed, and `final`'s runs as early in week 3 as you can.
Check `/usage` before each big run, iterate on `--config live --quick` and on `--only` with the one scenario you are changing, and try every new subagent on an `--only` run before a full one.
`guide/06-the-bench.html#cost` has my pilot's table, scenario by scenario.

---

## Ground rules

- **Using Claude Code is the point**, not something to disclose or apologize for.
  This is a course about driving agents well.
- **Your repo is public, and so is its history.**
  Do not commit API keys, passwords, or private information about anyone.
  Your learning sessions leave files in `tutor/` too, such as `MISSION.md` and `NOTES.md`, so keep personal details out of them.
  You never need an API key in this project, because the bench uses your Claude Code sign-in.
- **What to edit and what not to.**
  `tutor/`, `bench/own/`, `reviews/`, `p3.json` and your own writing are yours, and `configs/`, `bench/runs/` and `bench/compare/` are yours through the `p3` commands that write them.
  Do not edit `bench/` outside `bench/own/`, or `p3/`: they are hash-checked, and `p3 check` fails in CI when they change.
  Do not edit `tutor/FORMATS.md` either; it must stay identical to `bench/FORMATS.md`.
  If you think one of those files has a bug, tell me, and I will fix it for everyone.
- **No special-casing of bench items.**
  The bench is public, and a config that recognizes a bench item by its text and treats it specially gets no credit on that topic.
  `p3 check` warns when a config file holds 40 or more characters copied from the shared topic, and the grading pass searches configs for bench strings.
  Your test topics are the held-out check, which is why you tune on the shared topic only.
- **The measurements come from the commands.**
  Runs, scores and comparison records are written by `p3`; do not edit them by hand, and do not delete a run because you did not like its numbers.
  There are two exceptions.
  A run that failed for a reason outside your tutor, such as a usage limit or a sign-in problem, measures nothing; `p3 bench` sets such a repeat aside by itself, and "When it breaks" says where to find what to do with anything it missed.
  And a test topic with a real mistake in it is fixed by the procedure in `bench/own/README.md`, which deletes that topic's earlier runs.
- **The judgment is yours.**
  Your reviews are the measurement: your thoughts in each quick round, your live tries, every rating and its feedback, your learning sessions, your test-topic reviews, and each component's purpose, review and whether `final` kept it.
  The Builder writes only what it changed in each round and the inventory's factual fields, and it never writes or edits your parts.
  Make every blind pick yourself as well; an agent must never make them for you, or say which config made an output.
  The same goes for your test topics' true grades, your judge-check labels and the prose in `EVAL.md`.
- **On the life-skill topic, no individualized financial, medical or legal advice.**
  Your tutor may teach the general knowledge of a topic like budgeting or first aid, and it must not tell a learner what to do with their own money, health or legal situation.
  Write a probe that tests exactly that.
- **On the topic from another Mines course, write the items in your own words.**
  Do not copy that course's slides, homework or solutions into a public repo.
- **Build skills you would reuse.**
  P3 skills are designed to be reusable in P4, so write them to work outside the bench, not only inside it.

---

## How the 150 points are planned

This is how I plan to grade.
Canvas is the record, and if I change this table before the deadline I will announce it there.

| Part | Points |
|---|---|
| Setup: the tutor runs, `p3 check` passes in CI, snapshots and runs committed | 10 |
| Reviews: the quick rounds and the four major reviews (c1, c2, c3, `final`) | 30 |
| `c1-skills`: the four skills, measured (objective checks and cost) | 10 |
| `c2-review`: review loops on teach, quiz and grade, measured | 10 |
| `c3-split`: the teach job split across subagents, measured | 10 |
| `final`: the guard with its tests, three repeats, the ablation, the blind comparison against `c0-baseline` | 15 |
| Component inventory: a purpose and a with/without review for every skill and subagent, minimums met | 10 |
| Test topics: items written before the first run, `c0-baseline` and `final` run on both, reviewed | 15 |
| `EVAL.md`: the trade-offs, the judge check, open reviews against blind picks, the change that did not pay | 15 |
| One stretch (498E: any one; 598E: the length study, required) | 25 |
| **Total** | **150** |

"Measured" means the objective checks and the cost from `p3 report`, set beside your major review of the step and written up in `EVAL.md` with what they let you claim.
A step that did not pay for itself earns its points when you measured it and said so.

The reviews are graded on four things: specific evidence, such as quotes and item ids; ratings that the written feedback justifies; feedback that is actionable; and a visible trail from each review to the change it caused to whether that change helped.
"Your reviews" above says more.

I would rather say this now than have you find out later: the core work is 125 of 150 points, so with the video, complete core work without a stretch is 175 of 200.
That is 87.5%, so here an A needs a stretch.
The stretch is worth doing properly and not worth doing in the last hour.

---

## One stretch

The stretch is 25 of the 150 points.
For 498E it is one of the five options below, your choice.
For 598E it is the rider, which is required, and you do not do the other options: doing one as well adds no points, because the project is capped at 150.

Set `stretch` in `p3.json` to the option's id, so I know which one you did (for the length study it also switches on that study's checks in `p3 check --final`), and write it up in the last section of `EVAL.md`.
For 598E, set `section` to `"598E"` and `stretch` to `"length-study"`.
Pick your option early and try a small piece of it first, because most of them draw on your Claude plan; `guide/16-stretch-and-598e.html` walks through each one.

| Id | Option |
|---|---|
| `length-study` | **1. The length study**, the 598E rider below; in 498E, `p3 check --final` checks its runs and `PREREG.md` exactly as it does for 598E, and its three blind comparisons are your second blind comparison. |
| `personalization-swap` | **2. Personalization swap:** write a second `PREFERENCES.md` for a learner unlike you, snapshot `final` with it under a second name, run both, and show that lesson, quiz and feedback change as that profile intends and stay correct. |
| `cheaper-tutor` | **3. A cheaper tutor:** the same quality with Haiku subagents or fewer calls, judged by a major review of the cheaper config, in a file of its own such as `reviews/cheaper-tutor.md`, and by the objective checks, with as many runs of it as of `final`. |
| `mcp-server` | **4. An MCP server the tutor uses** (a review scheduler, a progress store), measured (lecture 16); ask me before you start this one, so we agree on how the bench's scenarios start your server. |
| `agent-sdk-grader` | **5. The grader ported to the Agent SDK** (lecture 21), which runs on your Claude subscription with no API key, kept outside `p3/` and `bench/` (for example in `sdk/`), writing grades in the `FORMATS.md` format, and compared with your Claude Code grader on the same submissions, in quality and in cost. |

---

## The 598E rider: the length study

Does splitting up the teach job matter more as lessons get longer, and does quality fall faster with length for a single agent than for the split pipeline?

| | 10 minutes | 30 minutes | 60 minutes |
|---|---|---|---|
| `c1-skills` | 3 runs | 3 runs | 3 runs |
| `final` | 3 runs | 3 runs | 3 runs |

Eighteen teach runs on the shared topic, teach only, with `p3 bench --minutes`, for example `uv run p3 bench --config c1-skills --only teach --minutes 60 --repeats 3`.
Set `section` to `"598E"` in `p3.json`, which makes `p3 check --final` look for these runs and for `PREREG.md`; `guide/16-stretch-and-598e.html#length-study` walks through the study.

1. **`PREREG.md` before the runs**, as in P2: which config loses more as length grows, and the smallest difference that matters, committed before the first of the eighteen runs; git history proves the order, and `p3 check --final` reads it.
2. **Comparisons within a length, never across:** blind `c1-skills` against `final` at each length, with `uv run p3 compare c1-skills final --job teach --teach-only --minutes 10` and again with `--minutes 30` and `--minutes 60`, three pairs each, because judges also favor longer outputs (lecture 24).
3. **Length accuracy:** actual against requested length, from `uv run p3 report --configs c1-skills,final --teach-only`, because a "60-minute" lesson that is really 35 confounds the comparison.
4. **Cost against length:** tokens per minute of lesson for each config, and whether the pipeline's overhead grows in step with length or faster.
5. **Threats to validity** (lecture 22): blinding failures, judge bias, and three runs per cell.

I estimate 4 to 6 extra hours.
The risk is tokens: the three 60-minute runs of `final` go through your multi-agent pipeline, so run the 60-minute cells over several days, and try one before you commit to the rest.
The time limit does not grow with the lesson: a teach scenario has 45 minutes at every length, so try one 60-minute run of `final` first and see whether its pipeline finishes in time.
The rider changes three other things for 598E: the three per-length teach comparisons are your second blind comparison, beside `c0-baseline` against `final`, with no other on top; you build at least six skills and at least eight subagents across the ladder ("The component inventory"); and a larger `final` costs more, so plan for 10 to 15 million tokens per full run of it, three times over, plus this study ("What the runs cost").

---

## The video

The video is worth 50 points, and it goes in the same Canvas discussion post as your repo URL.
Record 5 to 10 minutes, with any tool and any quality; a phone or a screen recording with your voice over it is fine.
Cover three things, in whatever order feels natural:

1. **The project.**
   What you built and what you found: show your tutor's architecture, one review that changed your tutor, the reveal of your blind comparison and one cost table, and say what they do and do not let you claim.
2. **Your observations.**
   Which machinery paid for itself and which did not, what surprised you, whether your blind picks agreed with your open reviews, and what your real learning sessions taught you that the bench could not.
3. **The challenges and how you solved them.**
   A real one, in your words.
   A review-to-change story is a good one to tell: something you noticed in a round, the change it led to, and whether the next run showed that it helped.
   Where you overruled the agent is another.

I am asking for this because the skills, the subagents and the runs can come from an agent and the video cannot.
It is your voice, your reasons and your story, and I care about the story and not about production quality.

---

## The deadline

Everything is due **Tuesday, November 24, at 11:59 pm**.
There are no checkpoints, because I would rather you finish the whole thing by the deadline than turn something in halfway.
On Canvas you make one post in the Project 3 discussion, with the URL of your repo and your video.
Run `uv run p3 check --final` and push your last commit before you post.

Late work loses 20%, and nothing is accepted more than a week late.
Canvas is the system of record for the deadline.
If Canvas and this file ever disagree, Canvas wins, and please tell me so I can fix it.

---

## When it breaks

`guide/19-troubleshooting.html` lists the usual symptoms with their fixes, from `claude` not being found to a usage limit in the middle of a run to a `p3 check` line you think is wrong, and you can paste the message to the Guide, which reads that page with you.
If something fails, send me the exact output.
Still stuck after 20 minutes?
Come to office hours: Tue and Thu, 9 to 10 am and 2 to 3 pm, CTLM 246L, and bring the exact error message, because the words on the screen usually save us half the debugging time.
And if anything in this brief is unclear or seems wrong, tell me: that is a bug too, and I would rather fix it than have you guess.

---

## Credits

The baseline `teach` skill in `tutor/.claude/skills/teach/` is a fork of the `teach` skill in [mattpocock/skills](https://github.com/mattpocock/skills) (`productivity/teach`), by Matt Pocock, under the MIT license.
I kept its workspace model and its pedagogy and changed it to do all four jobs in one pass; `THIRD-PARTY.md` holds the license notice.
Thank you to its author for publishing it.
