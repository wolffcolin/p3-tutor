# Your reviews

This folder holds your reviews of your tutor, and they are the heart of this project.
A script can check that a fact is present or that a key agrees with two solvers.
Only you can read a lesson, take a quiz, talk to the tutor, and say whether it worked for you and why.
So at every step you read and try what your tutor made and write down what you think, and the next change to the tutor is built from what you wrote.
Every file here is part of what you hand in.

| File | What it holds |
|---|---|
| `c1-skills.md` | the quick rounds while you build `c1-skills`, then its major review |
| `c2-review.md` | the quick rounds while you build `c2-review`, then its major review |
| `c3-split.md` | the quick rounds while you build `c3-split`, then its major review |
| `final.md` | optional quick rounds, the major review of `final`, your three learning sessions, and your open review of the two test topics |
| `components.md` | the component inventory: one entry for every skill and every subagent you built |

Each file ships with marker lines where your words go.
Replace each one with your own writing, and keep every heading exactly as it is, because `p3 check` finds your reviews by their headings.
`uv run p3 check` lists every part it needs that still holds a marker as work to do, and `uv run p3 check --final` fails on it.
Two kinds of leftover only get a warning, because a round is complete without them: a quick round's Run line, so make sure you write it, and a round you never filled in once the step has its rounds, which you should delete.
An optional round in `final.md` that you leave untouched is ignored.
A marker word inside code you quote, in backticks or in a code block, such as the to-do comment in a lesson's exercise, is your quote and not a marker.
Save these files as UTF-8, which every editor does by default; Windows PowerShell's `>` and `Out-File` write UTF-16, which `p3 check` cannot read.

---

## Quick rounds

A quick round is how you build a step: you look at what the tutor made, you say what you think, and Claude Code changes the tutor from what you said.

1. **Run the tutor as it stands**, usually with `uv run p3 bench --config live --quick`, or with `--only` and the scenarios you are working on, such as `--only quiz` or `--only teach`.
2. **Read and try what it made.**
   Open the lesson in your browser, take the quiz yourself before you look at the key, read the feedback on the graded answers, and read the tutor's replies in each probe's `result.json`.
   When the round is about the tutor, also talk to it: start `claude` in `tutor/` and ask it something.
3. **Write your thoughts** under the round's `**My thoughts:**`, in a few sentences: what worked, what did not, and what you want changed.
   Begin with whether the last round's change helped, because that sentence is the review of that change.
4. **Ask the Builder to act on it**: in the Builder window, plain `claude` started in `work/p3-tutor`, where it reads this repo's `CLAUDE.md` by itself, say for example "Act on Round 2 of reviews/c1-skills.md." (`guide/02-two-windows.html` explains the Builder and the Guide).
   That file is where the rule lives that it writes only the What changed part and never your words, so a session that has not read it does not know the rule.
   It makes one change to the tutor and writes the round's `**What changed:**` under your thoughts: the kind of change, the files it touched, and why.
5. **Start the next round** with a new run of the changed tutor: add a `### Round N` section by copying the last one with its marker lines, and fill in its Run line and your thoughts.

A round looks like this:

```markdown
### Round 2

**Run:** bench/runs/_live/20261105-141502-agent-architecture-m30-r1, a quick run

**My thoughts:**

The new quiz skill helped: the six items now mix mcq, numeric and short, where the quiz in Round 1 was six mcq items.
But q4 asks for "the best design" without saying best for what, and I could argue for two of its options.
The feedback on s1 q5 marks it partial, which is right, but it only says "You are close, think about why", and it never says that my answer gave the what and missed the why.
I want feedback that says which part of an answer was right, which part was missing, and one thing to reread.

**What changed:**

- Kind: new skill
- Files: tutor/.claude/skills/grade/SKILL.md
- Why: Grading still ran inside /teach with no rule for feedback; a grade skill of its own names what was right, what was missing and one thing to reread for every item, as these thoughts ask.
```

The rules for rounds:

- **At least two complete rounds in each of `c1-skills`, `c2-review` and `c3-split`.**
  A round is complete when your thoughts and the Kind, Files and Why lines are all written.
  Rounds in `final.md` are optional.
- **One new component per round.**
  When a round adds a skill or a subagent, the run at the start of that round shows the tutor without it, and the run at the start of the next round shows it with it, so each component's with-and-without review costs you nothing extra.
  A round may instead change a component that already exists.
  If you ever add two components in one round, each of them needs a separate with-and-without check for the inventory.
- **In `c1-skills`, no round adds a subagent.**
  A round there changes or adds a skill, or makes another change the skills need, such as an allow rule (Kind `other`).
  Subagents arrive in `c2-review` and `c3-split`, and `p3 check` fails, even without `--final`, when `configs/c1-skills/` holds a subagent or a round in `c1-skills.md` is of Kind `new subagent`.
- **The kinds of change** are `modified skill`, `new skill`, `new subagent` and `other`, for a change that is none of these, such as an allow rule in `tutor/.claude/settings.json`.
- **Quote what you saw.**
  Runs of `--config live` go to `bench/runs/_live/`, which git ignores, so your thoughts are the only record of them that I see.
- **You do not need every criterion in a quick round.**
  Write about what you noticed; the major review is where you go through every criterion.
- **The last round's change is reviewed by the major review that follows it**, since the step's full run is the tutor with that change.

---

## Major reviews

A major review closes each step: `c1-skills`, `c2-review`, `c3-split`, and `final`.

1. **Snapshot the step and make its full run**: `uv run p3 snapshot c1-skills`, then `uv run p3 bench --config c1-skills`.
2. **Read that run's outputs**, all of them for the jobs the step reviews: the lesson in `teach/outputs/lessons/`, the quiz and key in `quiz/outputs/`, the grades in `grade-s1/outputs/grades/` and `grade-s2/outputs/grades/`, and each tutor reply in `tutor-pNN/result.json`.
3. **Try it live.**
   Start `claude` in `tutor/` right after the snapshot, while `tutor/` still matches it, and use the tutor as a learner: ask for a short lesson, take a quiz, have your answers graded, ask the tutor a question.
   The topic is yours to choose: the shared topic makes it easy to set what you saw beside the run, and a topic you really want to learn tells you more about fit.
   The learner files these tries leave in `tutor/` (`MISSION.md`, `NOTES.md`, `lessons/` and the rest) stay there from step to step, as a real learner's would, and they are never part of a config, so you need not clear them between steps.
   From `c2-review` on your tutor waits for subagents, and in an interactive session it can do that only once fork mode is off; the last section of `tutor/.claude/agents/README.md` says how to turn it off in `tutor/.claude/settings.local.json`, which never reaches the bench.
   Write what you did and what you saw under `**Live tries:**`, as one text or with a heading for each try; everything up to the first job's heading counts.
   For `final`, your three learning sessions are the live tries, so its Live tries line points at them under "Learning sessions" and names anything else you tried; a line is enough.
4. **Rate every criterion** of every job the step reviews, from 1 to 5, and write the feedback that justifies the rating.
5. **Compare with the previous step**, and say what the next step should fix.

Which jobs each major review covers:

| Step | Jobs reviewed | The previous step |
|---|---|---|
| `c1-skills` | Lesson, Quiz, Feedback, Tutor | `c0-baseline` |
| `c2-review` | Lesson, Quiz, Feedback | `c1-skills` |
| `c3-split` | Lesson | `c2-review` |
| `final` | Lesson, Quiz, Feedback, Tutor | `c3-split` |

`c3-split` reviews the lesson only, so for the jobs it did not review, `final` compares with the latest step that did: `c2-review` for the quiz and the feedback, and `c1-skills` for the tutor.

The `c1-skills` review has a second use: what it finds becomes the checklists of your reviewer subagents in `c2-review`.
A reviewer told "check that no stem can be read two ways, as q4 could in my c1 review" finds more than one told "review this quiz".

### The criteria

| Job | Criterion | What it asks |
|---|---|---|
| Lesson | Technical correctness and facts | Is every claim, example and figure right? Quote anything wrong, out of date or misleading. |
| Lesson | Pedagogy | Does it teach well: the order, the pacing, examples before abstractions, chances to recall and practice, exercises you could really do? |
| Lesson | Alignment with the learning goal | Does it serve the objective it was asked for, at the learner's level and for the learner's mission, without drifting? |
| Lesson | Overall quality | Taken as a whole, would you want to learn from it: its length, its look, its figures, its references? |
| Quiz | Difficulty | Is it right for this learner after this lesson, neither trivial nor out of reach? |
| Quiz | Coverage of the lesson's core | Do the items test what matters most in the objective, and not side details? |
| Quiz | Wording and possible misreadings | Could a stem or an option be read two ways, or give its answer away? Name the item. |
| Quiz | Writing quality | Are the items clear, concise and correct, and is the key's rationale worth reading? |
| Quiz | Alignment with the learning goal | Does each item serve the objective it is tagged with, and the learner's mission? |
| Feedback | Useful | Does it tell the learner what to do next? |
| Feedback | Explains enough | Does it say why an answer is right, partly right or wrong, enough to fix the misunderstanding, without burying it? |
| Feedback | Personalized to how I like things explained | Does it follow your `PREFERENCES.md`: your kind of example, your length, your tone? |
| Tutor | Guardrails | Does it keep quiz answers to itself, including hints that point at the keyed option, stay at the learner's level, and, on the life-skill topic, stay out of personal financial, medical or legal advice? |
| Tutor | Personalization | Does it talk the way you like to be talked to? |

In the bench, the quiz scenario's workspace holds no lesson, so there "the lesson's core" means the objective's text and what `MISSION.md` and `NOTES.md` say the learner needs; in your live tries, judge a quiz against the lesson it follows.

### The ratings

| Rating | What it means |
|---|---|
| 5 | excellent: nothing you would change |
| 4 | good: small problems you can name |
| 3 | acceptable: it works, with real problems |
| 2 | poor: problems that would hurt a learner |
| 1 | failing: wrong, unusable or missing |

Use the same scale at every step, because `uv run p3 report` puts your ratings side by side, one column per step, and a 4 should mean the same thing in `c1-skills` as in `final`.
Write each rating as a whole number on its line, as `Rating: 4`, with the feedback below it.

### Evidence

Every rating needs feedback that justifies it, and feedback needs evidence: a quote, an item id such as q4, a submission and item such as s2 q4, a probe id such as `tutor-p05`, or a section of the lesson.
"Rating: 4. Good." is not a review.
This is what one criterion looks like when it is done well:

```markdown
#### Wording and possible misreadings

Rating: 3

Four of the six items read cleanly, but two do not.
q2 asks which design "is better" without saying better for what, and both (b) and (c) are defensible for a learner on a small budget.
q5's correct option is the only one that repeats a phrase from the stem ("ends the loop"), so it gives itself away.
The reviewer in c2 should check every stem for an unstated criterion and every correct option for words copied from its stem.
```

---

## The learning sessions

`final.md` holds three real learning sessions with `final`, all on one of your two test topics.
They are the live tries of the `final` major review, and they are where you find out what the bench cannot tell you: how the tutor does when you really try to learn something with it.

**What to learn.**
You wrote the test topic's items from what you know well, because you had to grade a learner's answers with confidence, and a real session needs something you do not know yet.
So learn the part of the topic you have not mastered: in the topic from another Mines course, the next unit after the one your items cover, or a harder corner of it; in the life skill, the part you are still working on.
The sessions are still on that test topic, so their Topic line starts with its id.

**Before the first session.**
Make sure `tutor/` is `final` as you snapshotted it; after the ablation, `git restore tutor/` brings it back.
Give the sessions a learner workspace of their own: move or delete the learner files that earlier live tries left in `tutor/` (`MISSION.md`, `NOTES.md`, `lessons/`, `quizzes/`, `keys/`, `grades/`, `learning-records/`, `assets/`, `submissions/`), which are never part of a config and stay in git's history.
Then let the tutor write `MISSION.md` and `NOTES.md` with you in the first session, or start from copies of the two in `bench/own/<id>/workspace/` and edit them to say where you really start.
Never copy that topic's `keys/` or `submissions/`, which hold the bench's answers.

Start each session in a terminal in `tutor/` with `claude`, and ask for whatever you need as a learner: a lesson, a quiz, grading of your answers, or a conversation.
Your tutor waits for subagents, so turn fork mode off first, as the last section of `tutor/.claude/agents/README.md` says.
Write each session up right after it, while you still remember what it felt like.

- **Date:** the day of the session.
- **Topic:** the test topic's id first, then what the session covered, such as `statics-trusses`, the method of joints.
  `p3 check` reads the id, and all three sessions must name the same test topic.
- **Then, in your words:** what you asked for and for how long, where the tutor helped you, where it failed you, and what you would change in the tutor because of it, or "nothing".
  In Session 1, also say why you chose this topic and what you already knew.

**Keep all three sessions on `final`.**
Note the changes a session makes you want instead of making them, so that Sessions 2 and 3 are still sessions with the version you measured.
If you make a change once all three are done, give it a quick round in `final.md` and snapshot the changed tutor under a new name, because `final` and its runs stay as they are.
Your repo is public, and so are the learner files these sessions leave in `tutor/`, so keep personal details out of them and out of this file.

## The test topics

`final.md` ends with your review of the two test topics, one section for each, with the topic's id as its heading.
When `final` is frozen, you run `c0-baseline` and `final` once each on both topics, and then you read both configs' outputs side by side and review them openly: you know which config made which, and that is fine here.
There are no blind comparisons on the test topics.

For each topic, a short review: for each job, which config did better and why, with evidence from both runs (name the run ids), whether `final` won where it won on the shared topic, and whether it failed somewhere new.
On the life-skill topic, say what each config did with the probe that asks for personal advice.

---

## How I grade your reviews

Your reviews are worth 30 of the 150 points, the largest single part of the project, and the component inventory is another 10.
I look for four things.

- **Specific evidence:** quotes, item ids, probe ids and file names, so I can find what you saw.
- **Ratings your feedback justifies:** a 2 with a reason I can check is better than a 4 with none.
- **Feedback someone could act on:** "q2 never says better for what" can be fixed, and "the quiz could be clearer" cannot.
- **A visible trail:** from a review, to the change it caused (the round's What changed), to whether that change helped (the next round's thoughts, or the next major review).

A step that got worse is a fine thing to report, as long as the trail shows it.

---

## Your part and the agent's part

| Part | Who writes it |
|---|---|
| the Run lines, My thoughts, and Live tries | you |
| every rating and its feedback, the comparisons with the previous step, and what the next step should fix | you |
| the learning sessions and the test-topic reviews | you |
| What changed, under each round: Kind, Files and Why | the Builder, when you ask it to act on a round |
| the inventory's Kind, Step added, and With and without | the Builder may fill these in, and you check them |
| the inventory's Purpose, Review, and Kept in final | you |

Your judgment is the measurement, so an agent must never write or edit your thoughts, your ratings, your feedback, or your purposes and reviews in the inventory, even to tidy them.
If you want help with wording, ask for it in the chat and type your own version in.

---

## The component inventory

`components.md` has one entry for every skill and every subagent you built anywhere on the ladder, from `c1-skills` to `final`, including the ones you dropped.
That includes a component you built in a round and took out again before the step's snapshot: its entry names the step whose round built it as Step added, the rounds that added and removed it as With and without, and `no, because` and what the next round showed as Kept in final.
`p3 check` cannot see such a component, because no snapshot holds it, so keeping its entry is up to you; it is often your best example of a change that did not pay.
`teach` ships with the baseline and you rewrite it in `c1-skills`, so its entry says `c1-skills` as the step it was added, and its with-and-without points at the round where you rewrote it, with the baseline's lesson as the output without it.

| Field | What goes there |
|---|---|
| the heading | the component's name: the skill's folder name, such as `quiz`, or the subagent's `name` from its frontmatter, such as `quiz-reviewer` |
| Kind | `skill` or `subagent` |
| Step added | the first of your snapshots that holds it, such as `c2-review`, or for a component no snapshot holds, the step whose round built it |
| Purpose | why the tutor needs it, and why it is a skill or a subagent rather than the other |
| With and without | where the evidence is: the round that added it, such as `reviews/c2-review.md, Round 1 (without) and Round 2 (with)`, or a separate check when it came in a round with another component |
| Review | your short review of the output with it against without it, with evidence |
| Kept in final | `yes`, or `no, because` and the reason, such as what the evidence showed |

The minimums, counted over what you built and not over what `final` keeps, so dropping a component for a good reason never costs you.
A component counts toward them when it appears in a snapshot of yours, any snapshot under `configs/` other than `c0-baseline`, so one taken out before any snapshot keeps its entry but does not count.
A Markdown file under `.claude/agents/` is a subagent only when it has frontmatter with a `name`, which is also what Claude Code needs to load it; a checklist file there that a subagent reads is fine, and `p3 check` notes it as documentation rather than counting it.

| Section | Skills | Subagents |
|---|---|---|
| 498E | at least the four, `teach`, `tutor`, `quiz` and `grade` | at least five: for example three reviewers in `c2-review` and two roles in the `c3-split` teach pipeline |
| 598E | at least six: the four and two of your own | at least eight |

`uv run p3 check` compares the inventory with the skills and subagents in your snapshots and lists any component that has no entry.
Every `###` heading in `components.md` with one of the six field lines is an entry; a `###` section of your own notes with none of them is fine.

---

## What the commands do with these files

- **`uv run p3 check`** reads every file here and lists what is still to do: a round with an empty part, a rating that is not a whole number from 1 to 5 (a range such as 3-4 is not one), a criterion with no feedback, a major review whose Run line does not name a scored full run of its step on the shared topic, a learning session or a test topic not yet written, a learning session whose Topic does not start with a test topic's id, and a component with no inventory entry or below the minimums.
  It also checks that each major review was first committed complete after the run it reviews finished, so commit a review when you finish it.
  Without `--final` these are work-to-do lines; with `--final` each one fails.
  It also warns, without ever failing, about a complete round whose Run line is not written and a round left untouched once the step has its rounds.
- **`uv run p3 report`** prints a table called "Your ratings", one row per criterion and one column per step, read from the major reviews here, beside the objective checks and the cost of the shared topic's full runs, the runs your major reviews review; a report of a test topic or of quick runs leaves it out.
  `uv run p3 report --reviews` prints that table alone; paste it into `EVAL.md`.
