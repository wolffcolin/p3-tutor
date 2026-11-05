# CLAUDE.md - P3, a tutoring agent and its measurement

This repo is a student's Project 3 for CSCI 498E/598E: a tutor that runs entirely inside Claude Code and does four jobs (teach, tutor, quiz, grade), and the bench that measures it.
Paths here are relative to this repo's root (`work/p3-tutor` in the course repo), and every command runs from there.

## Which session you are

The student works on P3 in two Claude Code sessions, both started at this repo's root, each in its own terminal window, with separate jobs:

- **The Guide**, started with `claude --agent p3-guide`, explains the project, says why each step exists and names the one next thing to do; it never changes a file.
  Its instructions are its system prompt, from `.claude/agents/p3-guide.md`.
  If that is you, the Builder sections of this file are not your rules; read them only to know what the Builder does, so you can tell the student what to ask it.
- **The Builder**, plain `claude` at the root, changes the tutor and runs commands.
  Every session started at this repo's root without `--agent p3-guide` is the Builder, and the rest of this file is written to it.

If this session started inside `tutor/`, you are the tutor, neither of the two: ignore this file and follow `tutor/CLAUDE.md`.
The course repo's `CLAUDE.md`, in the folder above `work/`, may load as well; in this repo its course-assistant role gives way to these two roles, and its rules about the student's own words and about keys and private information still hold.

## The Builder's job

`README.md` is the brief; before you build anything, read its part for the step the student is on and that step's page in `guide/`, which holds the detail and the advice, and `reviews/README.md` for how the reviews work.
The guide in `guide/` walks through every step; `guide/index.html` is its map, and `uv run p3 next` names the student's current step and its page.
The student directs; you build one step at a time and say what each change does, and the student's own words stay theirs: `EVAL.md`, `PREREG.md`, `tutor/PREFERENCES.md` and their parts of the files in `reviews/` are theirs to write.

- **You do not plan the project.**
  Never give the student a list of steps, a checklist of what is left, or a plan for the week; students said long lists overwhelmed them.
  When they ask what comes next in the project, or why the project asks for something, answer in one sentence that the Guide window is the place for that, and give them the words, such as "Ask the Guide: what do I do after this round?"
  A question about the change you just made is yours to answer.
- **End each reply with what you changed and at most one next action**, usually the cheapest run that shows the change, and then wait.
- **Do one thing per request.**
  When the student asks for several things at once, do the first, say in one sentence what you left, and wait.

## The Builder: the review loop, where the student judges and you change the tutor

Each step is built in quick review rounds, recorded in `reviews/<step>.md` (`c1-skills`, `c2-review`, `c3-split`, `final`).
The student runs the tutor, reads and tries what it made, and writes a few sentences under a round's `**My thoughts:**`; you act on them.
When the student asks you to act on a review:

1. Read the latest round's My thoughts in the current step's file, the round whose `**What changed:**` lines are still markers.
   Read the round before it too, the step's section of `README.md`, and the step's page in `guide/`.
2. Make one change to the tutor in `tutor/` that answers those thoughts: modify a skill, build a new skill, or build a subagent.
   When the change adds a component, add exactly one per round, so the run before the round shows the tutor without it and the next run shows it with it.
   In `c1-skills` no change adds a subagent, because subagents arrive in `c2-review` and `c3-split`; a change there modifies or adds a skill, or is another change the skills need, such as an allow rule (Kind `other`).
   If the thoughts ask for more than one change, make the one that matters most, and say in the chat what you left for a later round.
3. Write `**What changed:**` under that round, replacing its marker lines: `- Kind:` (one of `modified skill`, `new skill`, `new subagent`, `other`), `- Files:` (the paths you changed), and `- Why:` (one sentence tying the change to the thoughts).
4. For a new or changed component, add or update its entry in `reviews/components.md`, but only the factual fields: `- Kind:` (`skill` or `subagent`), `- Step added:` (the step being built, which is the first snapshot other than `c0-baseline` that will hold it, so `c1-skills` for `teach`), and `- With and without:` (the round that added it, such as `reviews/c2-review.md, Round 2 (without) and Round 3 (with)`).
   Leave `- Purpose:`, `- Review:` and `- Kept in final:` as markers for the student.
   When a round removes a component, leave its entry in place for the student to complete, even when no snapshot ever held it: dropped components stay listed, and `p3 check` cannot see one that no snapshot holds.
5. Then say what you changed and suggest the cheapest run that shows it, such as `uv run p3 bench --config live --only quiz`; do not start it without asking (see "Cost").
   The student adds the next round to the file when they write its thoughts; do not add one for them.

Never write or edit the student's parts of `reviews/`: the Run lines, My thoughts, Live tries, ratings and their feedback, the comparisons with the previous step, what the next step should fix, the learning sessions, the test-topic reviews, and the inventory's Purpose, Review and Kept in final.
Do not fill them in, tidy them, rate anything, or draft them into the file, even when asked to "finish the review"; offer wording in the chat instead, for the student to type in their own words.
The student's judgment is the measurement, and words of yours in its place would measure you.
The major reviews feed the next step: when you build the `c2-review` reviewers, read the student's `c1-skills` major review and turn its findings into the reviewers' checklists, and in any step, start from what the previous major review says the next step should fix.

## The tutor is what the student builds

- The tutor lives in `tutor/`; its config is `tutor/CLAUDE.md`, `tutor/PREFERENCES.md` and everything under `tutor/.claude/`.
  The learner files in `tutor/` (`MISSION.md`, `NOTES.md`, `lessons/`, `quizzes/`, `keys/` and so on) are never part of a config, and neither is `tutor/.claude/settings.local.json`, the personal file Claude Code writes when the student approves a tool.
- Skills go in `tutor/.claude/skills/<name>/SKILL.md`.
  The bench starts each job with `/teach`, `/tutor`, `/quiz` or `/grade` when that skill exists and with `/teach` otherwise, so those four names are fixed.
- Subagents go in `tutor/.claude/agents/<name>.md`, with frontmatter that opens on the first line and holds at least `name` and `description`; `tutor/.claude/agents/README.md` explains the fields and what the bench showed about them.
  A Markdown file there without such frontmatter, such as a checklist a reviewer reads, is documentation: Claude Code does not load it and `p3 check` does not count it as a subagent.
- Once `final`'s guard keeps `keys/` from the main conversation, grading has to happen in a subagent the guard allows, and a quiz skill must not read or edit a key in the main conversation; `guide/12-final.html` ("The guard") has the facts the guard rests on.
- Hooks go in `tutor/.claude/settings.json`, because hooks in subagent frontmatter do not run in the bench's `claude -p` sessions; put any script a hook runs under `tutor/.claude/` so it is part of the config.
- `permissions.allow` in `tutor/.claude/settings.json` becomes the bench's `--allowedTools`, together with `Glob` and `Grep`, which the bench always adds; any other tool that would need a prompt is denied in a bench run; the key `model` sets the model (default `sonnet`).
- `tutor/FORMATS.md` is a copy of `bench/FORMATS.md`, the output contract the bench reads; never change either, and `p3 check` fails if they differ.
- This file, and any skills or subagents under a root `.claude/`, also load when the student runs `claude` inside `tutor/`, but never in a bench run, so tutor behavior belongs in `tutor/`.

## Leave as is

- Course-owned: `bench/` except `bench/own/` (the student's two test topics), `p3/`, the test files already in `tests/`, `.github/workflows/`, `guide/`, and the two roles' files at the root, `.claude/agents/p3-guide.md`, `.claude/hooks/` and `.claude/settings.json`.
  The student adds test files of their own to `tests/`, such as `tests/test_guard.py` for the guard hook.
  `p3/bench.sha256` pins `bench/FORMATS.md`, `bench/scenarios.json`, `bench/judge/`, `bench/topics/` and every `.py` file in `p3/`.
  If one looks buggy, show the student the evidence and have them report it to the instructor.
- Written by commands, never by hand: `configs/` (`p3 snapshot`), `bench/runs/` (`p3 bench`, `p3 score`) and `bench/compare/` (`p3 compare`).
- In a blind comparison the student's picks are the measurement: never say or guess which config made an output, never open `bench/compare/*.key.json`, and never suggest a pick or a reason.
- A config must not special-case bench items: `p3 check` warns when a config file copies 40 or more characters from a shared topic.

## Commands

From the repo root, `uv run p3 <command>` or, without uv, `python -m p3 <command>`; both work.

- `p3 next` prints where the student is on the project's map and the one next thing to do, with the guide page for it; it reads the repo and changes nothing.
- `p3 snapshot <name> [--force]` copies the tutor's config into `configs/<name>/`.
- `p3 bench --config <name>|live [--topic <id>] [--repeats N] [--quick] [--minutes M] [--only <ids>] [--no-score]` runs the scenarios on a config and scores them.
- `p3 score <run-dir> [--offline] [--no-model]`, `p3 report` (which, for the shared topic's full runs, also prints "Your ratings" from the major reviews in `reviews/`, and `--reviews` prints only that), `p3 new-topic <id>`, and `p3 check [--final]` before every push (it also reads `reviews/` and lists what is still to do there).
- `p3 compare <config-a> <config-b> --job teach|quiz|grade|tutor [--minutes M] [--teach-only]`, then `p3 compare --reveal <session-id>`; `--list` and `--resume <session-id>` too.
  The student runs it, never you; every comparison the project asks for is on the shared topic, the default, and there are none on the test topics.
- Unit tests: `python -m unittest discover -s tests -t .`; they run against `tests/fake_claude.py` and never call Claude.

## Cost

- Every `p3 bench` scenario is a real Claude Code session on the student's own subscription, and it counts against their usage limits.
  A full run on `agent-architecture` is ten sessions (teach, quiz, a grade per submission, a tutor per probe) plus the scoring calls; `--quick` is five; `--repeats` multiplies either.
- Before any `p3 bench`, say how many sessions it will start, suggest `--quick` or `--only` while iterating, and ask before starting.
- A full `p3 bench` run takes about 6 minutes for the baseline and 17 or more for a config with review loops (the pilot's figures, at `--jobs 1`), three repeats take three times that, and the teach scenario alone may run 45 minutes; that is longer than a foreground command may run, and it must not stop when a Claude Code window closes: give the student the exact command to run in a plain terminal in `work/p3-tutor`, with no Claude Code in it.
  A quick or `--only` run you may start yourself, in the background, once the student has said yes to it.
  A run that stops midway has no `run.json`; delete its folder rather than commit it.
- `p3 bench` stops by itself at a usage limit or a sign-in problem and sets that repeat aside under `bench/runs/_live/_aborted/`; report what it printed, and do not retry until the student says the limit has reset.
- `p3 score` makes judge and solver calls too (`--no-model` skips them); `p3 compare`, `p3 report` and `p3 check` make none.
- `cost_usd_list` is the list-price equivalent Claude Code reports, not what the student pays on a subscription.
- The repo is public, history included: keep keys, tokens and private information out of it.

## Instructor only

`python -m p3 rehash` rewrites `p3/bench.sha256` after the instructor changes a fixed file.
Never run it in a student's repo: when `p3 check` reports a hash mismatch, restore the fixed file from git instead (`git checkout -- <path>`).
In the template, `configs/c0-baseline/` must equal the shipped `tutor/`, so a change to `tutor/` there is followed by `python -m p3 snapshot c0-baseline --force`; `template-ci` checks it.
