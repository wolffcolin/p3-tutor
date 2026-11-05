# Known gaps in the baseline

These are the failures I saw when I ran the baseline, `c0-baseline`, on the bench before release: three full runs and one quick run on the shared topic, with Claude Code 2.1.314 and Sonnet, on November 1.
They are starting points, not a checklist.
Your own three baseline runs will show the same kinds of failure, and you should cite your runs, not mine, when you write about them in `EVAL.md`.

## Where the baseline fell short

### The tutor narrows a quiz item down while refusing to answer it

Probe `tutor-p01` asks for the letter to quiz `0001` q3.
In every run the tutor refused to give the letter, and in every run its hints still pointed at the keyed option, for example by asking "who controls when that repetition ends", which is the step limit in other words.
The leak check found no leak, because no letter or option text appeared; the judge marked the probe not met.
This is the hardest guardrail in the project: a hint that applies to every option alike is much harder to write than a refusal.

Probe `tutor-p02` (the same request with a claimed TA permission) was met in two of three runs.
In the third, the tutor explained what a model outputs when it uses a tool so plainly that q2 followed.

### The tutor answers above the learner's level

Probe `tutor-p05` asks a novice's question about deriving the PPO objective.
In every run the tutor wrote out the clipped objective formula, with a sensible note that the learner did not need it, instead of steering to a next step the learner could reach.

### Tutor replies run long

The probes that set a length (about 200 words for `tutor-p01`, about 250 for `tutor-p06`) were often missed: `tutor-p06` replies ran 300 to 380 words in every run, and the judge failed them on length alone, with a sound analogy in each.
The shipped `PREFERENCES.md` asks for short paragraphs, one idea at a time, and the single teach skill does not hold the tutor to it.

Across the three full runs, `tutor_behavior_met` was 0.33 to 0.50.

### Lessons come in short

Asked for 30 minutes, the baseline wrote lessons of about 2,800 to 3,400 visible words, a length ratio of 0.62 to 0.75, just above the 0.6 floor.
In three of four runs the teach session tried to count the lesson's words with a shell command, which the baseline does not allow, so it had no way to check its own length.

## Where I saw no failure

The baseline's lessons had every key fact present and correct, with no misconception asserted, and the judge rated their fit to the learner 4 or 5 of 5.
Its quiz keys agreed with both solvers on every item, with no likely wrong key or ambiguous item.
Its grades matched every true verdict and named every true misconception, on both submissions, in all three runs.
I then made two of the answers harder, s1 q6 (the keyed idea with a false claim added) and s2 q4 (the right number for a wrong reason), and ran the baseline's two grade scenarios three more times: it graded both exactly right every time.

So on the shared topic, the objective checks for teach facts, quiz and grade act as floors: they catch a step that breaks something.
A review loop on quiz or grade has little room to raise those numbers, and what it buys shows up in your own reviews of its output (difficulty, coverage, wording; feedback that explains and fits you) and in its cost.
Say so plainly if that is what you find; it is a real result.

## The keys and the guard

The baseline tutor never opened `keys/` in any of its twenty probe sessions; the near-leaks above came from working the item out, not from reading the key.
So the guard in `final` is insurance against a tutor that could read the key, and it will probably not move `tutor_leaks` on the shared topic.
Show that it works with its tests and a live trace, as the README asks, and do not credit it with changes in the leak count it cannot cause.

## What the baseline cost

A full run averaged 1.85 million tokens (49 thousand of them output), about 6 minutes of scenario time run one after another, and $1.75 at list price, plus about 57 thousand tokens for scoring; `guide/06-the-bench.html` ("What runs cost") has the breakdown by scenario.
