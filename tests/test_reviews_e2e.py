"""A student's whole project, end to end, against the review files and p3 check --final.

The shipped template is copied into a temporary git repository and the project is replayed in the
order the README sets out: the baseline's runs; for each step of the ladder its quick rounds (a live
run, the student's thoughts, the agent's one change to tutor/ and its What changed lines), the
snapshot, the full run and the major review, each committed as it is done; then final with its
guard, its repeats and its ablation, the two test topics and their runs, the learning sessions, the
major review of final, the blind comparison, the test-topic reviews, the inventory and EVAL.md.
tests/fake_claude.py stands in for claude, so no model is called.

p3 check must stay free of failures all along, and p3 check --final must pass at the end. Then each
rule is broken in turn, on top of the finished project, and p3 check must fail with a message that
names the file and says what to do: a missing rating, a rating of 7, one quick round only, a
subagent in c1-skills, a component missing from the inventory, the 598E minimums, and a major review
committed before the run it reviews.

The review files are filled in by editing the shipped templates in place, the way a student does,
so a template whose headings or placeholders p3 check cannot read fails here.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from p3 import check, cli, compare, reviews, util
from tests import ENV_KEYS, REPO, fake_command, git, git_init, has_git, write
from tests.test_template import copy_template

TOPICS = ("statics-trusses", "knife-skills")  # one from another Mines course, one life skill
SESSION_TOPIC = TOPICS[1]
REVIEWERS = ("quiz-reviewer", "lesson-reviewer", "feedback-reviewer")
SPLIT = ("lesson-planner", "figure-designer")
DROPPED = "feedback-reviewer"  # built in c2-review, left out of final
ABLATION = "final-minus-figure-designer"

# ---- what the student and the agent write ----

PREFERENCES = """# How I like to learn

- An example from something I have built first, then the idea behind it.
- Short sections, a figure when a process has steps, and a question to try every few minutes.
- Feedback that says what I got right, what I missed, and one thing to reread.
"""

C1_ROUNDS = [
    ("The baseline's lesson on O3 reads well, but it opens with three paragraphs of definitions before the first example, and I learn from an example first.\n"
     "Section 2's diagram of the context window has no labels, so I could not tell the system prompt from the history.\n"
     "I want every section to start from a concrete example, such as a chatbot that forgets my name between sessions.",
     "modified skill", "tutor/.claude/skills/teach/SKILL.md",
     "The teach skill now opens every section with a worked example before the definition and labels every part of a figure, as these thoughts ask."),
    ("The example-first change helped: section 1 now opens with a chatbot that forgets my name, and I got the point before the definition.\n"
     "The quiz still comes from /teach, and q2 and q5 both ask me to recall a definition; q4 asks for \"the best design\" without saying best for what.\n"
     "I want a quiz that makes me apply the idea, with every stem naming its criterion.",
     "new skill", "tutor/.claude/skills/quiz/SKILL.md",
     "A quiz skill of its own writes items that apply the objective and states the criterion in every stem, which /teach never did."),
    ("The quiz skill helped: four of the six items now ask me to apply the idea, and every stem names its criterion.\n"
     "The feedback on s1 q5 marks it partial, which is right, but it only says \"You are close, think about why\".\n"
     "I want feedback that says which part was right, which part was missing, and one thing to reread.",
     "new skill", "tutor/.claude/skills/grade/SKILL.md",
     "A grade skill names what was right, what was missing and one thing to reread for every answer, as these thoughts ask."),
    ("The grade skill helped: s1 q5's feedback now says I gave the what and missed the why, and points me to section 3.\n"
     "In tutor-p01 the tutor still starts its hint with \"the answer is (b) because\", which gives the item away.\n"
     "I want a tutor that asks me a question back before it hints, and never names an option.",
     "new skill", "tutor/.claude/skills/tutor/SKILL.md",
     "A tutor skill asks a question back before any hint and never names a keyed option, so p01 and p02 get a hint and not the answer."),
]
C2_ROUNDS = [
    ("My c1-skills review found two quiz items that could be read two ways (q2 and q4) and a correct option that repeats its stem (q5).\n"
     "In this quick run q3 repeats \"ends the loop\" from its stem in the right option, the same fault as q5 before.\n"
     "I want a reviewer that checks every stem and option against those faults before the quiz is saved.",
     "new subagent", "tutor/.claude/agents/quiz-reviewer.md, tutor/.claude/skills/quiz/SKILL.md",
     "A quiz reviewer with a fresh context checks each stem for an unstated criterion and each right option for words copied from its stem, the checklist from the c1 review."),
    ("The quiz reviewer helped: its record flagged q3 and the revised q3 no longer repeats the stem.\n"
     "The lesson still says \"the model remembers what you told it yesterday\" in section 4, which is the misconception the lesson is meant to correct.\n"
     "I want a fact check of the lesson before it is saved.",
     "new subagent", "tutor/.claude/agents/lesson-reviewer.md, tutor/.claude/skills/teach/SKILL.md",
     "A lesson reviewer checks every claim against the objective's facts and the misconceptions, and sends back any sentence that asserts one."),
    ("The lesson reviewer helped: section 4 now says the program sends the history again on every call.\n"
     "The feedback on s2 q4 is right but long, eleven sentences for a two-line answer, and it never uses an example of mine.\n"
     "I want feedback checked for length and for an example from my preferences.",
     "new subagent", "tutor/.claude/agents/feedback-reviewer.md, tutor/.claude/skills/grade/SKILL.md",
     "A feedback reviewer checks each answer's feedback against PREFERENCES.md for length and for an example, and returns the ones that miss."),
]
C3_ROUNDS = [
    ("My c2-review review said the lesson's order wanders: section 3 uses retrieval before section 4 explains it.\n"
     "In this quick run the same thing happens with notes files.\n"
     "I want a plan of the sections, in the order the ideas depend on each other, before anything is written.",
     "new subagent", "tutor/.claude/agents/lesson-planner.md, tutor/.claude/skills/teach/SKILL.md",
     "A planner subagent writes the section plan, ordered by what depends on what, and the writer follows it."),
    ("The planner helped: retrieval now comes after notes files, and each section names what it builds on.\n"
     "The figures are still boxes with arrows and no labels, and the one on the context window is the same as in c1.\n"
     "I want one figure per process, with every part labelled.",
     "new subagent", "tutor/.claude/agents/figure-designer.md, tutor/.claude/skills/teach/SKILL.md",
     "A figure designer draws one labelled SVG figure for each process in the plan, so figures stop being an afterthought of the writer."),
]
FINAL_ROUNDS = [
    ("In my c3-split review I asked the tutor for quiz 0001 q1 and it read keys/0001.json before it answered, even though it did not give the answer away.\n"
     "I want the main conversation kept out of keys/ entirely.",
     "other", "tutor/.claude/settings.json, tutor/.claude/hooks/guard.py",
     "A PreToolUse hook blocks Read, Grep, Glob, Bash and PowerShell on keys/ in the main conversation and lets the grader through."),
    ("The guard held: in my live try the tutor's read of keys/0001.json came back with the hook's message.\n"
     "The feedback reviewer cost about 0.3M tokens per grade scenario in c2-review, and in my c2 review its changes were only shorter sentences.\n"
     "I want to drop it from final and see whether I miss it.",
     "other", "tutor/.claude/agents/feedback-reviewer.md, tutor/.claude/skills/grade/SKILL.md",
     "The feedback reviewer is removed and the grade skill keeps its length rule, as these thoughts ask."),
]

FEEDBACK = {
    "Technical correctness and facts": "Every claim I checked against my own notes holds; section 4 now says \"the program sends the whole history again on every call\".\nOne small slip: the figure in section 2 calls the system prompt \"memory\", which a learner could take literally.",
    "Pedagogy": "Each section opens with an example before the idea, as I asked, and there is a recall question every few minutes.\nThe exercise in section 5 asks me to design a memory for my project but gives no starting point, so I stalled.",
    "Alignment with the learning goal": "It stays on O3 throughout and ties every idea back to the assistant in MISSION.md.\nThe aside on embeddings in section 4 drifts past what O3 asks for.",
    "Overall quality": "I would learn from this lesson: about 30 minutes, a clear look, two labelled figures and two references that resolve.\nThe last section repeats the summary of section 1 almost word for word.",
    "Difficulty": "Right for this learner after the lesson: q1 and q2 are warm-ups and q4 to q6 make me apply the idea.\nq6 needs a cost model the lesson never gave, so it is a step too far.",
    "Coverage of the lesson's core": "Five of the six items test the workflow-or-agent choice itself.\nq3 tests a side detail, the name of a pattern, which matters less than when to use it.",
    "Wording and possible misreadings": "q2 now names its criterion (\"for a task whose steps are known\"), which fixes my c1 complaint.\nq5's option (c) can still be read as right if \"loop\" means any repeated call.",
    "Writing quality": "The stems are short and plain, and the key's rationales are worth reading.\nq4's rationale is one word, \"control\", which explains nothing.",
    "Personalized to how I like things explained": "The feedback on s1 q5 uses my senior design project as its example, as PREFERENCES.md asks.\nThe feedback on s2 q2 is generic and could be for anyone.",
    "Useful": "Each answer's feedback ends with one thing to reread, such as \"section 3, the second example\" for s1 q1.\nFor the right answers it only says \"Right\", which tells me nothing to do next.",
    "Explains enough": "s2 q3 gets two sentences on why the answer is partly right and what was missing, which fixed my misunderstanding.\ns1 q1 names misconception M1 but never says what is true instead.",
    "Guardrails": "In tutor-p01 and tutor-p02 the tutor asks what I think first and never names an option, and in my live try it refused to read keys/.\nIn tutor-p05 it starts a proof before it scales down to my level.",
    "Personalization": "It talks like a TA I would ask again: short replies, a question back, an example from my project.\nIn tutor-p06 the analogy is about a restaurant, which PREFERENCES.md says I find too cute.",
}
RATINGS = {"c1-skills": 3, "c2-review": 4, "c3-split": 4, "final": 4}
COMPARED = {
    "c1-skills": "Against c0-baseline the lesson now opens with examples and the quiz makes me apply the idea; the feedback says what to reread, which the baseline's never did.",
    "c2-review": "Against c1-skills, q2 and q4 no longer read two ways and section 4 no longer asserts M2; the feedback got shorter but not more personal.",
    "c3-split": "Against c2-review the lesson's order now follows what depends on what, and the figures are labelled; it took about twice the tokens.",
    "final": "Against c3-split the guard keeps the tutor out of keys/ and nothing I rated got worse without the feedback reviewer.",
}
NEXT = {
    "c1-skills": "c2-review should check every stem for an unstated criterion (q4) and every right option for words from its stem (q5), and fact-check section 4.",
    "c2-review": "c3-split should plan the lesson's order before writing it, because section 3 still uses retrieval before section 4 explains it.",
    "c3-split": "final should keep the main conversation out of keys/ and drop whatever I cannot see paying off, the feedback reviewer first.",
    "final": "I would give the quiz reviewer the lesson itself in my own sessions, and try the figure designer on Haiku to see whether it holds up for less.",
}
SESSIONS = [
    ("2026-11-19", f"`{SESSION_TOPIC}`, the claw grip and the rocking cut",
     "I chose knife skills because I cook every day and have never been taught; I knew how to hold a knife and nothing about cuts.\n"
     "Forty minutes: a 20-minute lesson, then a quiz of five items, then practice with an onion.\n"
     "The lesson's figure of the claw grip helped; the quiz's q3 asked for a cut the lesson never named, so I changed nothing yet and noted it."),
    ("2026-11-20", f"{SESSION_TOPIC}: dicing an onion",
     "Thirty minutes, mostly talking to the tutor while I diced.\n"
     "It asked me what I thought the root end was for before it explained, which is how I like it, and it never told me what to buy."),
    ("2026-11-22", f"{SESSION_TOPIC} - julienne, and the quiz on all three sessions",
     "Twenty-five minutes: a short lesson on julienne and a six-item quiz on everything so far.\n"
     "The grading of my q4 answer was right and said which half I missed; the tutor would not tell me q2 before I answered it."),
]
TOPIC_REVIEWS = {
    "statics-trusses": "On statics-trusses final's lesson works one truss by the method of joints before stating the method, where c0-baseline's states it and never works one.\n"
    "final's quiz q4 gives its answer away in the figure's label, a new failure the shared topic never showed.\n"
    "Grading: both got s1 right; final's feedback on s1 q2 names the sign error, c0-baseline's says only \"wrong\".",
    "knife-skills": "On knife-skills both lessons are safe and general; final's has a labelled figure of the claw grip and c0-baseline's has none.\n"
    "On tutor-p04, which asks which knife I should buy with my own budget, both stayed general, and final also said why it would not pick for me.\n"
    "final won where it won on the shared topic, in the lesson and the feedback; the quiz was a tie.",
}

SKILL = """---
name: {name}
description: {description}
---

{body}
"""
SUBAGENT = """---
name: {name}
description: {description}
tools: Read, Write
---

{body}
"""
GUARD = """import json
import sys

event = json.load(sys.stdin)
if "keys/" in json.dumps(event.get("tool_input") or {}) and not event.get("agent_type"):
    print("keys/ is for the grader only", file=sys.stderr)
    sys.exit(2)
"""


def thoughts_for(step: str, n: int) -> tuple[str, str, str, str]:
    rounds = {"c1-skills": C1_ROUNDS, "c2-review": C2_ROUNDS, "c3-split": C3_ROUNDS, "final": FINAL_ROUNDS}[step]
    return rounds[n - 1]


# ---- editing the shipped templates, as the student and the agent do ----


def span(text: str, *headings: str) -> tuple[int, int]:
    """(start, end) of the section under the last heading, each found within the one before: from
    its heading line to the next heading at its level or above. A heading inside an HTML comment,
    such as the example entry of reviews/components.md, is not one."""
    comments = [(m.start(), m.end()) for m in re.finditer(r"<!--.*?-->", text, re.S)]

    def first(pattern: re.Pattern, a: int, b: int) -> re.Match | None:
        return next((m for m in pattern.finditer(text, a, b) if not any(c0 <= m.start() < c1 for c0, c1 in comments)), None)

    start, end = 0, len(text)
    for heading in headings:
        level = len(heading.split(" ", 1)[0])
        m = first(re.compile(r"^" + re.escape(heading) + r"[ \t]*$", re.M), start, end)
        if m is None:
            raise AssertionError(f"no {heading!r} in {text[start:end][:200]!r}")
        nxt = first(re.compile(r"^#{1,%d} " % level, re.M), m.end(), end)
        start, end = m.start(), (nxt.start() if nxt else end)
    return start, end


def edit(text: str, headings: tuple[str, ...], old: str, new: str) -> str:
    """Replace the first `old` in the section under `headings`; the template must have it there."""
    a, b = span(text, *headings)
    part = text[a:b]
    if old not in part:
        raise AssertionError(f"no {old!r} under {' > '.join(headings)}")
    return text[:a] + part.replace(old, new, 1) + text[b:]


def drop(text: str, *headings: str) -> str:
    a, b = span(text, *headings)
    return text[:a] + text[b:]


class Project:
    """The temporary repository and what a student does in it."""

    def __init__(self, root: Path):
        self.root = root
        shipped = self.read(reviews.step_file("c1-skills"))
        a, b = span(shipped, "## Quick rounds", "### Round 1")
        self.template_round = shipped[a:b]  # what the agent copies to add a round

    # files

    def read(self, rel: str) -> str:
        return util.read_text(self.root / rel)

    def write(self, rel: str, text: str) -> None:
        write(self.root / rel, text)

    def change(self, rel: str, fn) -> None:
        self.write(rel, fn(self.read(rel)))

    # commands

    def p3(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def must(self, *argv: str) -> str:
        code, out, err = self.p3(*argv)
        if code != 0:
            raise AssertionError(f"p3 {' '.join(argv)} exited {code}:\n{out}\n{err}")
        return out

    def bench(self, cfg: str, *extra: str) -> str:
        """A bench run of `cfg`; returns the run folder, relative to the repo."""
        base = util.runs_dir(cfg, self.root)
        before = {p.name for p in base.iterdir()} if base.is_dir() else set()
        self.must("bench", "--config", cfg, "--offline", "--jobs", "4", *extra)
        made = sorted(p.name for p in base.iterdir() if p.name not in before and (p / "run.json").is_file())
        return util.posix(base / made[-1], self.root)

    def commit(self, message: str, when: str | None = None) -> None:
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", message, when=when)

    def check(self, final: bool = False) -> check.Checklist:
        return check.run_checks(self.root, final)

    # the tutor, changed by the agent

    def skill(self, name: str, body: str) -> None:
        self.write(f"tutor/.claude/skills/{name}/SKILL.md", SKILL.format(name=name, description=f"The {name} job of my tutor.", body=body))

    def subagent(self, name: str) -> None:
        self.write(f"tutor/.claude/agents/{name}.md", SUBAGENT.format(name=name, description=f"The {name} of my tutor, with a fresh context.", body=f"You are the {name}. Return a short list of findings, each with the line it is about."))

    # the review files

    def round_heading(self, step: str, n: int) -> str:
        return f"### Round {n}" + (" (optional)" if step == "final" else "")

    def student_round(self, step: str, n: int, run: str) -> None:
        """The student's part of round n: the run and the thoughts (the agent adds an empty round
        when the file has none left, as CLAUDE.md lets it)."""
        rel = reviews.step_file(step)
        heading = self.round_heading(step, n)
        if heading not in self.read(rel):
            skeleton = self.template_round.replace("### Round 1", heading)
            self.change(rel, lambda t: t.replace(f"\n## {reviews.MAJOR_REVIEW}", f"\n{skeleton}## {reviews.MAJOR_REVIEW}", 1))
        thoughts = thoughts_for(step, n)[0]
        self.change(rel, lambda t: edit(t, ("## Quick rounds", heading), "**Run:** TODO", f"**Run:** {run}, a quick run"))
        self.change(rel, lambda t: edit(t, ("## Quick rounds", heading), "**My thoughts:**\n\nTODO", f"**My thoughts:**\n\n{thoughts}"))

    def agent_round(self, step: str, n: int) -> None:
        """The agent's part of round n: What changed."""
        _thoughts, kind, files, why = thoughts_for(step, n)
        heading = self.round_heading(step, n)
        rel = reviews.step_file(step)
        for name, value in (("Kind", kind), ("Files", files), ("Why", why)):
            self.change(rel, lambda t, name=name, value=value: edit(t, ("## Quick rounds", heading), f"- {name}: TODO", f"- {name}: {value}"))

    def major_review(self, step: str, run: str) -> None:
        """The student's major review of `run`, every placeholder of the template's replaced."""
        rel = reviews.step_file(step)
        live = (
            f"My three learning sessions below, all on {SESSION_TOPIC}, are my live tries of final."
            if step == "final"
            else "Right after the snapshot I asked tutor/ for a 10-minute lesson on notes files, took its quiz, had my answers graded and asked it for quiz 0001 q3; it gave a hint and not the answer."
        )
        self.change(rel, lambda t: edit(t, ("## Major review",), f"**Run:** bench/runs/{step}/TODO", f"**Run:** {run}"))
        self.change(rel, lambda t: edit(t, ("## Major review",), "**Live tries:**\n\nTODO", f"**Live tries:**\n\n{live}"))
        for job in reviews.STEP_JOBS[step]:
            for name in reviews.CRITERIA[job]:
                where = ("## Major review", f"### {job}", f"#### {name}")
                self.change(rel, lambda t, where=where: edit(t, where, "Rating: TODO", f"Rating: {RATINGS[step]}"))
                self.change(rel, lambda t, where=where, name=name: edit(t, where, "\nTODO", "\n" + FEEDBACK[name]))
        compared, nxt = reviews.closing_sections(step)
        self.change(rel, lambda t: edit(t, ("## Major review", f"### {compared}"), "TODO", COMPARED[step]))
        self.change(rel, lambda t: edit(t, ("## Major review", f"### {nxt}"), "TODO", NEXT[step]))

    def component(self, name: str, kind: str, step: str, round_ref: str) -> None:
        """The agent's factual fields of a new inventory entry; the student's stay TODO."""
        entry = f"### {name}\n\n- Kind: {kind}\n- Step added: {step}\n- Purpose: TODO\n- With and without: {round_ref}\n- Review: TODO\n- Kept in final: TODO\n"
        empty = "### TODO: the component's name"
        text = self.read(reviews.COMPONENTS_PATH)
        if empty in text:
            text = text[: text.index(empty)] + entry
        else:
            text = text.rstrip("\n") + "\n\n" + entry
        self.write(reviews.COMPONENTS_PATH, text)

    def student_component(self, name: str, purpose: str, review: str, kept: str) -> None:
        for field_name, value in (("Purpose", purpose), ("Review", review), ("Kept in final", kept)):
            self.change(reviews.COMPONENTS_PATH, lambda t, f=field_name, v=value: edit(t, (f"### {name}",), f"- {f}: TODO", f"- {f}: {v}"))


def fill_topic(folder: Path, title: str) -> None:
    """The student's items for a test topic made with p3 new-topic: every TODO replaced."""

    def fill(value):
        if isinstance(value, dict):
            return {k: fill(v) for k, v in value.items()}
        if isinstance(value, list):
            return [fill(v) for v in value]
        if isinstance(value, str) and "TODO" in value:
            return f"{title}: " + value.replace("TODO: ", "").replace("TODO", "")
        return value

    for rel in util.list_files(folder):
        path = folder / rel
        if rel.endswith(".json"):
            data = fill(util.read_json(path))
            if rel == "workspace/submissions/s1.json":
                for answer in data["answers"]:
                    answer["response"] = {"q1": "a", "q2": "0.2", "q3": "the part that matters, and not why"}[answer["id"]]
            if rel == "workspace/keys/0001.json":
                data["items"][2]["accepted"] = ["the part that matters and why"]
            util.write_json(path, data)
        else:
            util.write_text(path, util.read_text(path).replace("TODO: ", f"{title}: ").replace("TODO", title))


@unittest.skipUnless(has_git(), "needs git")
class ReviewWorkflowTests(unittest.TestCase):
    """The project is built once; each test starts from it and git puts it back afterwards."""

    project: Project
    good: str

    @classmethod
    def setUpClass(cls):
        cls._saved = {k: os.environ.get(k) for k in ENV_KEYS}
        for k in ENV_KEYS:
            os.environ.pop(k, None)
        cls._tmp = Path(tempfile.mkdtemp(prefix="p3-e2e-"))
        try:
            root = copy_template(cls._tmp / "repo")
            for name in (".gitignore", ".gitattributes"):
                shutil.copyfile(REPO / name, root / name)
            os.environ["P3_ROOT"] = str(root)
            os.environ["P3_CLAUDE"] = fake_command()
            util.rehash(root)  # p3/ may be mid-edit here; the committed hash file is CI's business
            cls.project = Project(root)
            cls.build(cls.project)
            cls.good = util.rev_parse_head(root)
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        for k, v in cls._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        util.remove_tree(cls._tmp)  # git leaves its objects read-only on Windows

    def tearDown(self):
        root = self.project.root
        git(root, "checkout", "-q", "-f", "main")
        git(root, "reset", "-q", "--hard", self.good)
        git(root, "clean", "-q", "-fd")

    # ---- the project, in the order a student works ----

    @classmethod
    def build(cls, p: Project) -> None:
        def no_failure(when: str) -> None:
            r = p.check()
            if r.failures():
                raise AssertionError(f"p3 check fails {when}:\n{r.text()}")

        git_init(p.root)
        git(p.root, "symbolic-ref", "HEAD", "refs/heads/main")  # the branch the tests come back to, whatever git names its first
        p.commit("Start from the template")
        no_failure("on the fresh template")

        # week 1: the baseline, then the four skills in quick rounds
        p.bench("c0-baseline", "--quick")
        p.bench("c0-baseline", "--repeats", "3")
        p.commit("Baseline: a quick run and three full runs")
        p.write("tutor/PREFERENCES.md", PREFERENCES)
        p.commit("My preferences")
        for n in range(1, len(C1_ROUNDS) + 1):
            run = p.bench("live", "--quick")
            p.student_round("c1-skills", n, run)
            p.commit(f"c1-skills: round {n}, my thoughts")
            if n == 1:
                teach = p.read("tutor/.claude/skills/teach/SKILL.md")
                p.write("tutor/.claude/skills/teach/SKILL.md", teach + "\n## Example first\n\nOpen every section with a worked example from the learner's mission, then the idea, and label every part of every figure.\n")
                p.component("teach", "skill", "c1-skills", "reviews/c1-skills.md, Round 1 (without) and Round 2 (with)")
            else:
                name = thoughts_for("c1-skills", n)[2].split("/")[-2]
                p.skill(name, f"Do the {name} job for the learner in MISSION.md, following PREFERENCES.md and FORMATS.md.")
                p.component(name, "skill", "c1-skills", f"reviews/c1-skills.md, Round {n} (without) and " + (f"Round {n + 1} (with)" if n < len(C1_ROUNDS) else "the major review's run (with)"))
            p.agent_round("c1-skills", n)
            p.commit(f"c1-skills: round {n}, what changed")
        p.must("snapshot", "c1-skills")
        run = p.bench("c1-skills")
        p.commit("c1-skills: snapshot and full run")
        p.major_review("c1-skills", run)
        p.commit("c1-skills: major review")
        no_failure("after c1-skills")

        # week 2: the reviewers, one per round, then the teach split
        for step, rounds, agents, only in (("c2-review", C2_ROUNDS, REVIEWERS, ("quiz", "teach", "grade-s1")), ("c3-split", C3_ROUNDS, SPLIT, ("teach", "teach"))):
            for n in range(1, len(rounds) + 1):
                run = p.bench("live", "--only", only[n - 1])
                p.student_round(step, n, run)
                p.subagent(agents[n - 1])
                after = f"Round {n + 1} (with)" if n < len(rounds) else "the major review's run (with)"
                p.component(agents[n - 1], "subagent", step, f"reviews/{step}.md, Round {n} (without) and {after}")
                p.agent_round(step, n)
                p.commit(f"{step}: round {n}")
            p.must("snapshot", step)
            run = p.bench(step)
            p.commit(f"{step}: snapshot and full run")
            p.major_review(step, run)
            p.commit(f"{step}: major review")
            no_failure(f"after {step}")

        # the test topics' items, written and committed before any run on them
        for tid, title in zip(TOPICS, ("Statics", "Knife skills")):
            p.must("new-topic", tid)
            fill_topic(p.root / "bench" / "own" / tid, title)
        p.commit("Test topics: items, before any run")

        # week 3: final with the guard, minus the feedback reviewer
        run = p.bench("live", "--quick")
        p.student_round("final", 1, run)
        settings = json.loads(p.read("tutor/.claude/settings.json"))
        settings["hooks"] = {"PreToolUse": [{"matcher": "Read|Grep|Glob|Bash|PowerShell", "hooks": [{"type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/guard.py\""}]}]}
        p.write("tutor/.claude/settings.json", json.dumps(settings, indent=2) + "\n")
        p.write("tutor/.claude/hooks/guard.py", GUARD)
        p.agent_round("final", 1)
        p.commit("final: round 1, the guard")
        run = p.bench("live", "--only", "grade-s1")
        p.student_round("final", 2, run)
        (p.root / "tutor" / ".claude" / "agents" / f"{DROPPED}.md").unlink()
        p.agent_round("final", 2)
        p.commit("final: round 2, without the feedback reviewer")
        p.must("snapshot", "final")
        p.bench("final", "--repeats", "3")
        final_runs = sorted(util.posix(d, p.root) for d in util.runs_dir("final", p.root).iterdir())
        p.commit("final: snapshot and three full runs")
        (p.root / "tutor" / ".claude" / "agents" / "figure-designer.md").unlink()
        p.must("snapshot", ABLATION)
        git(p.root, "restore", "tutor/")
        p.bench(ABLATION)
        p.commit("Ablation: final without the figure designer")
        for tid in TOPICS:
            for cfg in ("c0-baseline", "final"):
                p.bench(cfg, "--topic", tid)
        p.commit("Test topics: c0-baseline and final on both")
        no_failure("after the runs")

        # the learning sessions are the live tries of final's major review, written before the blind comparison
        for n, (date, topic_line, text) in enumerate(SESSIONS, 1):
            where = ("## Learning sessions", f"### Session {n}")
            p.change(reviews.step_file("final"), lambda t, w=where, d=date: edit(t, w, "**Date:** TODO", f"**Date:** {d}"))
            p.change(reviews.step_file("final"), lambda t, w=where, tl=topic_line: edit(t, w, "**Topic:** TODO", f"**Topic:** {tl}"))
            p.change(reviews.step_file("final"), lambda t, w=where, x=text: edit(t, w, "\nTODO", "\n" + x))
        p.major_review("final", final_runs[1])
        p.commit("final: learning sessions and major review")

        # the blind comparison, picks made in the terminal flow p3 compare --terminal uses
        cls.sessions = {}
        for job in check.BLIND_COMPARE_JOBS:
            record = compare.new_session("c0-baseline", "final", job, root=p.root)
            s = compare.Session(record["session"], p.root)
            answers = iter(["r", "It starts from an example, as I like.", "n", "l", "Shorter, and it asks me back.", "y", "t", "Both fine for me.", "n"] * len(s.pairs))
            with contextlib.redirect_stdout(io.StringIO()):
                code = compare.terminal(s, ask=lambda _prompt, a=answers: next(a), folder=cls._tmp / "pairs" / job)
            if code != 0:
                raise AssertionError(f"the {job} comparison did not finish")
            p.must("compare", "--reveal", record["session"])
            cls.sessions[job] = (record["session"], len(record["pairs"]))
        p.commit("Blind comparison: c0-baseline against final, all four jobs")

        # the open reviews of the test topics, the inventory's own fields, EVAL.md
        final_md = p.read(reviews.step_file("final"))
        for placeholder, tid in zip(("### TODO: your first test topic's id", "### TODO: your second test topic's id"), TOPICS):
            final_md = edit(final_md.replace(placeholder, f"### {tid}"), ("## Test topics", f"### {tid}"), "\nTODO", "\n" + TOPIC_REVIEWS[tid])
        p.write(reviews.step_file("final"), final_md)
        for name in ("teach", "quiz", "grade", "tutor", *REVIEWERS, *SPLIT):
            kept = f"no, because my c2-review review found its only change was shorter sentences, and final without it scored the same on feedback for {0.3}M fewer tokens per grade scenario" if name == DROPPED else "yes"
            p.student_component(
                name,
                f"The tutor needs {name} because my review before it showed a gap only it closes; it is a {'skill' if name in check.SKILLS else 'subagent with a fresh context'} because of how it must see the draft.",
                f"Without {name} the round's run showed the gap I quoted in its round; with it the next run did not, at a cost I name in EVAL.md.",
                kept,
            )
        eval_md = p.read("EVAL.md")
        p.write("EVAL.md", "\n".join("My own words on this, with the run ids and session ids." if "TODO" in line else line for line in eval_md.split("\n")))
        p.commit("Test-topic reviews, the inventory and EVAL.md")

    # ---- the finished project passes ----

    def test_the_finished_project_passes_check_final(self):
        p = self.project
        code, out, _err = p.p3("check", "--final")
        self.assertEqual(code, 0, out)
        self.assertIn("ready to hand in", out)
        self.assertNotRegex(out, r"\n  (TODO|FAIL) ", "every item is done")
        for step in reviews.STEPS:
            self.assertRegex(out, rf"\n  OK    reviews/{step}\.md, major review: complete, of bench/runs/{step}/\S+-agent-architecture-m30-r\d\n")
            self.assertRegex(out, rf"\n  OK    reviews/{step}\.md, major review: first committed complete at \S+ \([0-9a-f]{{12}}\), after bench/runs/{step}/\S+ finished \(\S+\)\n")
        for line in (
            "reviews/c1-skills.md, quick rounds: 4 complete (2 needed)",
            "reviews/c2-review.md, quick rounds: 3 complete (2 needed)",
            "reviews/c3-split.md, quick rounds: 2 complete (2 needed)",
            "reviews/final.md, quick rounds (optional): 2 complete",
            f"reviews/final.md, learning sessions: 3 complete (3 needed), on {SESSION_TOPIC}",
            f"reviews/final.md, test topics: a complete review of each ({', '.join(sorted(TOPICS))})",
            "reviews/components.md: a complete entry for every skill and subagent in your snapshots (4 skills and 5 subagents)",
            "components built: 4 skills and 5 subagents across your snapshots other than c0-baseline (498E needs at least 4 skills, teach, tutor, quiz and grade among them, and 5 subagents)",
            "c1-skills: skills only (no subagent in configs/c1-skills/, and no quick round that adds one)",
        ):  # fmt: skip
            self.assertIn(f"\n  OK    {line}\n", out)
        for job, (sid, _n) in self.sessions.items():
            self.assertIn(f"\n  OK    compare c0-baseline / final, {job} on agent-architecture: complete ({sid})\n", out)
        self.assertEqual({job: n for job, (_sid, n) in self.sessions.items()}, {"teach": 3, "quiz": 3, "grade": 36, "tutor": 18}, "the pairs the README promises")

    def test_the_ratings_table(self):
        p = self.project
        code, out, err = p.p3("report", "--reviews")
        self.assertEqual(code, 0, err)
        self.assertTrue(out.startswith("## Your ratings\n"), out)
        self.assertIn("| job | criterion | c1-skills | c2-review | c3-split | final |", out)
        self.assertIn("| Lesson | Pedagogy | 3 | 4 | 4 | 4 |", out)
        self.assertIn("| Quiz | Difficulty | 3 | 4 | - | 4 |", out)
        self.assertIn("| Tutor | Guardrails | 3 | - | - | 4 |", out)
        self.assertEqual(out.count("\n| "), 1 + sum(len(c) for c in reviews.CRITERIA.values()), "a header and one row per criterion")
        code, out, err = p.p3("report", "--configs", "c0-baseline,c1-skills")
        self.assertEqual(code, 0, err)
        self.assertLess(out.index("### Cost: all jobs"), out.index("## Your ratings"), "the ratings come after the other tables")

    # ---- each rule, broken on top of the finished project ----

    def failing(self, needle: str, final: bool = True) -> tuple[check.Item, check.Checklist]:
        """The one item whose text holds `needle`, which must be a FAIL that makes the check exit 1."""
        r = self.project.check(final)
        found = [i for i in r.items() if needle in i.text]
        self.assertEqual(len(found), 1, f"{needle!r} in:\n{r.text()}")
        self.assertEqual(found[0].status, check.FAIL, r.text())
        self.assertEqual(r.exit_code(), 1)
        return found[0], r

    def test_a_missing_rating(self):
        self.project.change("reviews/c2-review.md", lambda t: edit(t, ("## Major review", "### Quiz", "#### Difficulty"), "Rating: 4\n", ""))
        item, r = self.failing("reviews/c2-review.md, major review: not complete yet (1 problem)")
        self.assertEqual(item.details, ["Major review > Quiz > Difficulty: no Rating line (write Rating: N, N a whole number from 1 to 5)"])
        self.assertEqual(len(r.failures()), 1, "nothing else fails")
        self.assertFalse([i for i in r.items() if i.text.startswith("reviews/c2-review.md, major review: first committed")], "an incomplete review has no commit-order item")

    def test_a_rating_of_7(self):
        p = self.project
        p.change("reviews/final.md", lambda t: edit(t, ("## Major review", "### Lesson", "#### Pedagogy"), "Rating: 4", "Rating: 7"))
        item, r = self.failing("reviews/final.md, major review: not complete yet (1 problem)")
        self.assertEqual(item.details, ["Major review > Lesson > Pedagogy: Rating is 7; write a whole number from 1 to 5"])
        self.assertEqual(len(r.failures()), 1)
        _code, out, _err = p.p3("report", "--reviews")
        self.assertIn("| Lesson | Pedagogy | 3 | 4 | 4 | - |", out, "a rating p3 check does not accept shows as a dash")

    def test_one_quick_round_only(self):
        self.project.change("reviews/c3-split.md", lambda t: drop(t, "## Quick rounds", "### Round 2"))
        item, r = self.failing("reviews/c3-split.md, quick rounds: 1 of the 2 complete rounds needed")
        self.assertEqual(item.details, ["Quick rounds: 1 round; add a ### Round section for each round, 2 at least"])
        self.assertEqual(len(r.failures()), 1)
        loose = self.project.check()
        self.assertEqual(([i.status for i in loose.items() if "reviews/c3-split.md, quick rounds" in i.text], loose.exit_code()), ([check.TODO], 0), "without --final it is work to do")

    def test_a_c1_round_that_adds_a_subagent(self):
        self.project.change("reviews/c1-skills.md", lambda t: edit(t, ("## Quick rounds", "### Round 3"), "- Kind: new skill", "- Kind: new subagent"))
        item, r = self.failing("c1-skills adds a subagent", final=False)
        self.assertEqual(item.text, "c1-skills adds a subagent, but c1 is still one agent (subagents arrive in c2-review and c3-split)")
        self.assertEqual(item.details, ["reviews/c1-skills.md, Quick rounds > Round 3: Kind is new subagent; a quick round of c1-skills changes or adds a skill, or makes another change (Kind other)"])
        self.assertIn(item, r.items(check.INTEGRITY), "a rule, so it fails even without --final")

    def test_a_subagent_in_the_c1_snapshot(self):
        """The student adds a subagent to the tutor of c1-skills and snapshots c1-skills again, over its run."""
        p = self.project
        for agent in (p.root / "tutor" / ".claude" / "agents").glob("*-*.md"):
            agent.unlink()  # tutor/ back to the subagents c1-skills had: none
        p.subagent("early-checker")
        p.must("snapshot", "c1-skills", "--force")
        item, r = self.failing("c1-skills adds a subagent", final=False)
        self.assertEqual(item.details, ["configs/c1-skills/.claude/agents/early-checker.md: the subagent early-checker; take it out of tutor/, snapshot c1-skills again (p3 snapshot c1-skills --force) and make its runs again"])
        (runs,) = [i for i in r.failures() if i.text.startswith("bench/runs/c1-skills/")]
        self.assertIn("was made with another version of c1-skills than configs/c1-skills/ holds", runs.details[0])
        (inventory,) = [i for i in r.items() if i.text.startswith("reviews/components.md")]
        self.assertEqual((inventory.status, inventory.details), (check.TODO, ["early-checker (subagent, in configs/c1-skills/): no entry; add ### early-checker with its six fields"]))

    def test_a_component_missing_from_the_inventory(self):
        self.project.change(reviews.COMPONENTS_PATH, lambda t: drop(t, "### quiz-reviewer"))
        item, r = self.failing("reviews/components.md: not complete (1 problem)")
        self.assertEqual(item.text, "reviews/components.md: not complete (1 problem); every skill and subagent in a snapshot other than c0-baseline needs a complete entry")
        self.assertEqual(item.details, ["quiz-reviewer (subagent, in configs/c2-review/): no entry; add ### quiz-reviewer with its six fields"])
        self.assertEqual(len(r.failures()), 1)

    def test_the_598e_minimums(self):
        self.project.write("p3.json", json.dumps({"section": "598E", "stretch": None}) + "\n")
        item, r = self.failing("components built: ")
        self.assertEqual(item.text, "components built: 4 skills and 5 subagents across your snapshots other than c0-baseline (598E needs at least 6 skills, teach, tutor, quiz and grade among them, and 8 subagents)")
        self.assertEqual(item.details, ["skills: grade, quiz, teach, tutor", f"subagents: {', '.join(sorted(REVIEWERS + SPLIT))}"])
        failed = {i.text for i in r.failures()}
        for m in check.STUDY_MINUTES:
            self.assertIn(f"length study, compare c1-skills / final at {m} minutes: no complete teach-only session yet (p3 compare c1-skills final --job teach --teach-only --minutes {m})", failed)
        self.assertIn("PREREG.md: no commit has sections 1 to 4 filled in yet; commit them before the first length-study run", failed)

    def test_a_major_review_committed_before_its_run(self):
        """The final review squashed into a commit dated before the run it names, as a rebase with
        --committer-date-is-author-date can leave it."""
        p, root = self.project, self.project.root
        rel = reviews.step_file("final")
        reviewed = next(c for c, _when, data in util.git_file_versions(rel, root) if b"Rating: 4" in (data or b""))
        run = reviews.read_step("final", root).major.run_id
        finished = util.parse_iso(util.read_json(root / "bench" / "runs" / "final" / run / "run.json")["finished_at"])
        git(root, "checkout", "-q", "-b", "squashed", f"{reviewed}~1")
        git(root, "checkout", "-q", "main", "--", ".")
        p.commit("final, with its review squashed in", when=util.iso_utc(finished - timedelta(hours=1)))
        item, r = self.failing("reviews/final.md, major review: first committed complete at")
        self.assertRegex(item.text, rf"^reviews/final\.md, major review: first committed complete at \S+ \([0-9a-f]{{12}}\), before bench/runs/final/{re.escape(run)} finished \(\S+\); a major review is written after the run it reviews$")
        self.assertEqual(len(r.failures()), 1, "the other steps' reviews were committed after their runs")


if __name__ == "__main__":
    unittest.main()
