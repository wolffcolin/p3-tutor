"""The review files' parser (p3/reviews.py): complete files, files still TODO, layout it tolerates,
names it does not, bad ratings, missing sections, the inventory and the components of a config.
These tests read texts made here, never the real templates in reviews/ (test_template.py does)."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from p3 import reviews
from tests import component_md, components_md, review_md, write

RUN = "bench/runs/c1-skills/20261103-140000-agent-architecture-m30-r1"


def parse(text: str, step: str = "c1-skills") -> reviews.StepReview:
    return reviews.parse_step(text, step)


class CompleteFileTests(unittest.TestCase):
    def test_each_step_complete(self):
        for step in reviews.STEPS:
            r = parse(review_md(step, f"bench/runs/{step}/r1", topics=("cooking", "statics")), step)
            self.assertEqual(r.path, f"reviews/{step}.md")
            self.assertTrue(r.major.complete, (step, r.major.problems))
            self.assertEqual(r.major.run_id, "r1")
            self.assertEqual(len(r.rounds), reviews.MIN_ROUNDS[step])
            self.assertTrue(all(x.complete and x.touched for x in r.rounds), [x.problems for x in r.rounds])
            self.assertEqual({job for job, _ in r.major.ratings()}, set(reviews.STEP_JOBS[step]))
            self.assertEqual(len(r.major.ratings()), sum(len(reviews.CRITERIA[j]) for j in reviews.STEP_JOBS[step]))
            self.assertIsNone(r.rounds_problem)
            if step == "final":
                self.assertEqual([s.complete for s in r.sessions], [True, True, True])
                self.assertEqual([(t.topic, t.complete) for t in r.topics], [("cooking", True), ("statics", True)])
            else:
                self.assertEqual((r.sessions, r.topics), ([], []))

    def test_round_fields(self):
        (first, _second) = parse(review_md("c1-skills", RUN, kinds={1: "modified skill (quiz)"})).rounds
        self.assertEqual(first.title, "Round 1")
        self.assertEqual(first.run, "bench/runs/_live/round-1")
        self.assertEqual(first.kind_value, "modified skill")
        self.assertEqual(first.files, "tutor/.claude/skills/quiz/SKILL.md")
        self.assertIn("quiz 0002 q3", first.thoughts)
        self.assertFalse(first.optional)

    def test_ratings(self):
        r = parse(review_md("c2-review", "bench/runs/c2-review/r1", ratings={("Quiz", "Difficulty"): 2, ("Lesson", "Pedagogy"): "5 out of 5"}), "c2-review")
        self.assertEqual(r.major.ratings()[("Quiz", "Difficulty")], 2)
        self.assertEqual(r.major.ratings()[("Lesson", "Pedagogy")], 5)
        self.assertNotIn(("Tutor", "Guardrails"), r.major.ratings())

    def test_an_extra_job_is_read_but_not_required(self):
        text = review_md("c3-split", "bench/runs/c3-split/r1").replace(
            f"### {reviews.COMPARED}", "### Quiz\n\n#### Difficulty\n\nRating: 3\n\nToo easy.\n\n#### Writing quality\n\nRating: TODO\n\n" + f"### {reviews.COMPARED}"
        )
        r = parse(text, "c3-split")
        self.assertTrue(r.major.complete, r.major.problems)
        self.assertEqual(r.major.ratings()[("Quiz", "Difficulty")], 3)


class TemplateShapeTests(unittest.TestCase):
    """Every text TODO, as the template ships the files: nothing complete, nothing touched."""

    def test_todo_everywhere(self):
        for step in reviews.STEPS:
            r = parse(review_md(step, todo=True, optional=1 if step == "final" else 0), step)
            self.assertFalse(r.major.complete)
            self.assertFalse(r.major.touched, step)
            self.assertTrue(r.major.present)
            self.assertIsNone(r.major.run_id)
            self.assertIn("Major review: Run is still TODO; name the run you reviewed (bench/runs/" + step + "/<run-id>)", r.major.problems)
            self.assertTrue(all(not x.complete and not x.touched for x in r.rounds))
            self.assertEqual(r.major.ratings(), {})
            if step == "final":
                self.assertTrue(r.rounds[0].optional)
                self.assertEqual(r.rounds[0].title, "Round 1 (optional)")
                self.assertTrue(all(not s.touched for s in r.sessions))
                self.assertEqual([t.topic for t in r.topics], ["<topic-id>"])
                self.assertEqual(r.topics[0].problems, ["Test topics > <topic-id>: the text is still TODO"])

    def test_todo_round_problems(self):
        (first, _) = parse(review_md("c1-skills", todo=True)).rounds
        self.assertEqual(first.problems, [
            "Quick rounds > Round 1: My thoughts is still TODO",
            "Quick rounds > Round 1: Kind is still TODO",
            "Quick rounds > Round 1: Files is still TODO",
            "Quick rounds > Round 1: Why is still TODO",
        ])  # fmt: skip

    def test_a_placeholder_run(self):
        text = review_md("c1-skills", "bench/runs/c1-skills/<run-id>")
        self.assertIn(
            "Major review: Run is still the placeholder 'bench/runs/c1-skills/<run-id>'; name the run you reviewed (bench/runs/c1-skills/<run-id>)",
            parse(text).major.problems,
        )


class LayoutTests(unittest.TestCase):
    """Lenient about layout: line endings, spacing, bold, extra prose, comments and code."""

    def test_crlf_trailing_spaces_and_a_bom(self):
        text = review_md("c1-skills", RUN)
        messy = "\ufeff" + "\r\n".join(line + "   " for line in text.split("\n"))
        r = parse(messy)
        self.assertTrue(r.major.complete, r.major.problems)
        self.assertTrue(all(x.complete for x in r.rounds))
        self.assertEqual(r.major.run_id, RUN.rsplit("/", 1)[1])

    def test_extra_prose_comments_and_code_blocks(self):
        text = review_md("c1-skills", RUN)
        text = text.replace("## Major review\n", "## Major review\n\nI made this run on Tuesday.\n\n<!-- TODO: an old note to myself\n### Lesson\n-->\n")
        text = text.replace("#### Pedagogy\n\nRating: 4\n", "#### Pedagogy\n\nRating: 4\n\n```\n#### Pedagogy\nRating: TODO\n```\n")
        text += "\n## Notes\n\nAnything else I want to keep.\n"
        r = parse(text)
        self.assertTrue(r.major.complete, r.major.problems)
        self.assertEqual(r.major.ratings()[("Lesson", "Pedagogy")], 4)

    def test_names_ignore_case_spacing_marks_and_curly_apostrophes(self):
        text = review_md("c2-review", "bench/runs/c2-review/r1")
        text = text.replace("### Lesson\n", "###   **lesson** ###\n").replace("Coverage of the lesson's core", "Coverage of the lesson\u2019s  core")
        text = text.replace("**My thoughts:**", "**my thoughts**:").replace("- Kind: new skill", "* **Kind:** New skill").replace("Rating: 4", "**Rating:** 4", 1)
        r = parse(text, "c2-review")
        self.assertTrue(r.major.complete, r.major.problems)
        self.assertTrue(all(x.complete for x in r.rounds), [x.problems for x in r.rounds])
        self.assertIn(("Quiz", "Coverage of the lesson's core"), r.major.ratings())

    def test_a_field_on_the_next_line(self):
        text = review_md("c1-skills", RUN).replace(f"**Run:** {RUN}", f"**Run:**\n{RUN}").replace("Rating: 4", "Rating:\n3", 1)
        r = parse(text)
        self.assertTrue(r.major.complete, r.major.problems)
        self.assertEqual(r.major.ratings()[("Lesson", "Technical correctness and facts")], 3)

    def test_run_references(self):
        cases = {
            "bench/runs/c1-skills/r1": ("c1-skills", "r1"),
            "`bench/runs/c1-skills/r1/`": ("c1-skills", "r1"),
            "bench\\runs\\c1-skills\\r1": ("c1-skills", "r1"),
            "[the first run](bench/runs/c1-skills/r1) of the day": ("c1-skills", "r1"),
            "bench/runs/c0-baseline/r9": ("c0-baseline", "r9"),
            "against bench/runs/c0-baseline/b1, I reviewed bench/runs/c1-skills/r1": ("c1-skills", "r1"),
            "bench/runs/c1-skills/r1 (see <the lesson>)": ("c1-skills", "r1"),
            "bench/runs/c1-skills/<run-id>": None,
            "r1": ("c1-skills", "r1"),
            "`r1`": ("c1-skills", "r1"),
            "the one from Tuesday": None,
            "<run-id>": None,
            "": None,
        }
        for text, want in cases.items():
            self.assertEqual(reviews.run_ref(text, "c1-skills"), want, text)
        r = parse(review_md("c1-skills", "bench/runs/c0-baseline/r9"))
        self.assertIn("Major review: Run names a run of c0-baseline; the major review of c1-skills reviews a full run of c1-skills (bench/runs/c1-skills/<run-id>)", r.major.problems)
        self.assertIsNone(r.major.run_id)


class QuotedCodeTests(unittest.TestCase):
    """What a student quotes from a lesson, in code, is text: a TODO there is not a marker, a comment
    opener there opens no comment, and a line that starts with ```code``` opens no code block."""

    def test_todo_in_code_is_not_a_marker(self):
        self.assertFalse(reviews.has_todo("The exercise says `# TODO: write the loop`, which is fair."))
        self.assertFalse(reviews.has_todo("``a TODO with ` inside`` and more"))
        self.assertFalse(reviews.has_todo("```python\n# TODO: fill in\n```\nGood."))
        self.assertFalse(reviews.has_todo("```p3 bench --config live --only teach``` wrote `# TODO` into its lesson."))
        self.assertTrue(reviews.has_todo("TODO"))
        self.assertTrue(reviews.has_todo("A stray ` backtick, then TODO"))
        self.assertTrue(reviews.has_todo("`code` and then TODO"))
        text = review_md("c1-skills", RUN).replace(
            "#### Pedagogy\n\nRating: 4\n\nPedagogy:", "#### Pedagogy\n\nRating: 4\n\nThe exercise in section 3 is `# TODO: write the loop`, a fair scaffold. Pedagogy:"
        )
        self.assertTrue(parse(text).major.complete, parse(text).major.problems)

    def test_a_comment_opener_in_inline_code(self):
        text = review_md("c1-skills", RUN).replace(
            "#### Pedagogy\n\nRating: 4\n", "#### Pedagogy\n\nRating: 4\n\nThe lesson's HTML starts its notes with `<!--`, and the learner never sees them.\n"
        )
        r = parse(text)
        self.assertTrue(r.major.complete, r.major.problems)
        self.assertIn("`<!--`", r.major.criteria[("Lesson", "Pedagogy")].feedback)

    def test_comments_are_dropped_outside_code(self):
        text = review_md("c1-skills", RUN).replace("**Live tries:**\n\n", "**Live tries:**\n\n<!-- a note --> I tried it twice. <!-- and\n### Lesson\n-->Then once more.\n\n")
        text = text.replace("Rating: 4\n", "Rating: 4\n\n```html\n<!-- kept: this is code\n```\n", 1)
        r = parse(text)
        self.assertTrue(r.major.complete, r.major.problems)
        self.assertIn("I tried it twice.", r.major.live_tries)
        self.assertIn("Then once more.", r.major.live_tries)
        self.assertNotIn("a note", r.major.live_tries)
        self.assertNotIn("### Lesson", r.major.live_tries)

    def test_inline_triple_backticks_open_no_code_block(self):
        text = review_md("c1-skills", RUN).replace("**Live tries:**\n\n", "**Live tries:**\n\n```p3 bench --config live --only tutor-p01``` gave a hint.\n\n")
        r = parse(text)
        self.assertTrue(r.major.complete, r.major.problems)
        self.assertEqual(len(r.major.ratings()), 14)


class FieldLayoutTests(unittest.TestCase):
    def test_a_value_after_a_blank_line(self):
        text = review_md("c1-skills", RUN).replace(f"**Run:** {RUN}", f"**Run:**\n\n{RUN}").replace("Rating: 4", "Rating:\n\n3", 1)
        text = text.replace("**Run:** bench/runs/_live/round-1", "**Run:**\n\nbench/runs/_live/round-1")
        r = parse(text)
        self.assertTrue(r.major.complete, r.major.problems)
        self.assertEqual(r.major.ratings()[("Lesson", "Technical correctness and facts")], 3)
        self.assertEqual(r.rounds[0].run, "bench/runs/_live/round-1")
        final = review_md("final", "bench/runs/final/r1", topics=("cooking",)).replace("**Date:** 2026-11-21", "**Date:**\n\n2026-11-21")
        self.assertEqual(parse(final, "final").sessions[0].date, "2026-11-21")

    def test_an_empty_value_stays_empty(self):
        text = review_md("c1-skills", RUN).replace(f"**Run:** {RUN}", "**Run:**").replace("**Run:** bench/runs/_live/round-1", "**Run:**")
        r = parse(text)
        self.assertIn("Major review: Run is empty; name the run you reviewed (bench/runs/c1-skills/<run-id>)", r.major.problems)
        self.assertEqual(r.rounds[0].run, "", "the next line is the My thoughts label, not a value")
        self.assertFalse(r.rounds[0].run_written)
        self.assertTrue(r.rounds[0].complete, "a round's Run is not part of complete")
        text = review_md("c1-skills", RUN).replace("Rating: 4\n", "Rating:\n\n##### Not a value\n", 1)
        self.assertIn("Major review > Lesson > Technical correctness and facts: Rating is empty; write a whole number from 1 to 5", parse(text).major.problems)

    def test_live_tries_under_headings_of_their_own(self):
        tries = "**Live tries:**\n\n#### Try 1\n\nI asked for q3's answer; it gave a hint.\n\n### Live try 2\n\nA short lesson on memory.\n\n"
        text = review_md("c1-skills", RUN).replace("**Live tries:**\n\nI asked the tutor for q3's answer twice; it gave a hint.\n\n", tries)
        r = parse(text)
        self.assertTrue(r.major.complete, r.major.problems)
        self.assertIn("A short lesson on memory.", r.major.live_tries)
        self.assertNotIn("Pedagogy", r.major.live_tries, "Live tries ends at the first job")
        empty = text.replace("I asked for q3's answer; it gave a hint.", "").replace("A short lesson on memory.", "")
        self.assertIn("Major review: Live tries is empty", parse(empty).major.problems)


class RatingTests(unittest.TestCase):
    def test_ranges_and_pluses_are_not_ratings(self):
        for text in ("3-4", "3 - 4", "3 to 4", "3 or 4", "4 and 5", "3/4/5"):
            rating, problem = reviews.parse_rating(text)
            self.assertIsNone(rating, text)
            self.assertTrue(problem.endswith("pick one, a whole number from 1 to 5, not a range") or "out of 5" in problem, (text, problem))
        self.assertEqual(reviews.parse_rating("4+"), (None, "Rating is '4+'; write a whole number from 1 to 5, without the +"))
        self.assertEqual(reviews.parse_rating("3-4"), (None, "Rating is '3-4'; pick one, a whole number from 1 to 5, not a range"))
        self.assertEqual(reviews.parse_rating("**4**/5"), (4, None))

    def test_words_after_the_rating_are_feedback(self):
        self.assertEqual(reviews.rating_remark("4. Section 2 says X, which is wrong."), "Section 2 says X, which is wrong.")
        self.assertEqual(reviews.rating_remark("5 - the best so far"), "the best so far")
        self.assertEqual((reviews.rating_remark("4"), reviews.rating_remark("4/5"), reviews.rating_remark(None)), ("", "", ""))
        text = review_md("c1-skills", RUN).replace("Rating: 4\n\nPedagogy: section 2 of lesson 0001 says \"the program runs the tool\", which is right.", "Rating: 4. Section 2 says \"the program runs the tool\", which is right.")
        r = parse(text)
        self.assertTrue(r.major.complete, r.major.problems)
        self.assertEqual(r.major.criteria[("Lesson", "Pedagogy")].feedback, "Section 2 says \"the program runs the tool\", which is right.")

    def test_good_ratings(self):
        for text, want in {"4": 4, "1": 1, "5": 5, "4/5": 4, "4 / 5": 4, "3 out of 5": 3, "5 - the best so far": 5, "2.": 2, "**4**": 4, "4 (q3 aside)": 4}.items():
            self.assertEqual(reviews.parse_rating(text), (want, None), text)

    def test_bad_ratings(self):
        hint = "a whole number from 1 to 5"
        cases = {
            None: f"no Rating line (write Rating: N, N {hint})",
            "": f"Rating is empty; write {hint}",
            "TODO": f"Rating is still TODO; write {hint}",
            "0": f"Rating is 0; write {hint}",
            "6": f"Rating is 6; write {hint}",
            "3.5": f"Rating is 3.5; write {hint}",
            "3,5": f"Rating is 3,5; write {hint}",
            "four": f"Rating is 'four'; write {hint}",
            "4a": f"Rating is '4a'; write {hint}",
            "8/10": f"Rating is '8/10'; ratings are out of 5, so write {hint}",
        }
        for text, problem in cases.items():
            self.assertEqual(reviews.parse_rating(text), (None, problem), text)
        self.assertEqual(reviews.parse_rating("4", count=2), (None, "2 Rating lines; keep one"))

    def test_bad_ratings_in_a_file(self):
        text = review_md("c1-skills", RUN, ratings={("Quiz", "Difficulty"): 6, ("Tutor", "Guardrails"): "TODO"})
        text = text.replace("#### Pedagogy\n\nRating: 4\n", "#### Pedagogy\n\nRating: 4\nRating: 5\n")
        text = text.replace("#### Useful\n\nRating: 4\n", "#### Useful\n\n")
        r = parse(text)
        self.assertFalse(r.major.complete)
        self.assertEqual(r.major.problems, [
            "Major review > Lesson > Pedagogy: 2 Rating lines; keep one",
            "Major review > Quiz > Difficulty: Rating is 6; write a whole number from 1 to 5",
            "Major review > Feedback > Useful: no Rating line (write Rating: N, N a whole number from 1 to 5)",
            "Major review > Tutor > Guardrails: Rating is still TODO; write a whole number from 1 to 5",
        ])  # fmt: skip
        self.assertNotIn(("Quiz", "Difficulty"), r.major.ratings())
        self.assertEqual(r.major.ratings()[("Quiz", "Writing quality")], 4)


class MissingTests(unittest.TestCase):
    """Strict about names and levels, with messages that name the section and what is missing."""

    def test_missing_sections(self):
        text = review_md("c1-skills", RUN)
        r = parse(text.split("## Major review")[0])
        self.assertFalse(r.major.present)
        self.assertEqual(r.major.problems, ["## Major review is missing (the template's reviews/c1-skills.md has it; copy it back)"])
        r = parse(text.replace("## Quick rounds", "## Rounds"))
        self.assertEqual(r.rounds, [])
        self.assertEqual(r.rounds_problem, "## Quick rounds is missing (the template's reviews/c1-skills.md has it; copy it back)")
        r = parse(review_md("final", "bench/runs/final/r1").split("## Learning sessions")[0], "final")
        self.assertIsNone(r.rounds_problem, "rounds are optional in final")
        self.assertEqual(r.sessions_problem, "## Learning sessions is missing (the template's reviews/final.md has it; copy it back)")
        self.assertEqual(r.topics_problem, "## Test topics is missing (the template's reviews/final.md has it; copy it back)")

    def test_missing_jobs_criteria_and_closings(self):
        text = review_md("c1-skills", RUN)
        text = text.replace("### Tutor\n", "### The tutor\n").replace("#### Pedagogy", "#### Teaching").replace(f"### {reviews.NEXT_FIX}", "### Next")
        r = parse(text)
        self.assertEqual(r.major.problems, [
            "Major review > Lesson > Pedagogy: missing; add #### Pedagogy",
            "Major review > Tutor: missing; add ### Tutor with its 2 criteria",
            "Major review > What the next step should fix: missing; add ### What the next step should fix",
        ])  # fmt: skip

    def test_a_heading_at_the_wrong_level_gets_a_hint(self):
        text = review_md("c1-skills", RUN).replace("### Quiz\n", "## Quiz\n")
        problems = parse(text).major.problems
        self.assertTrue(problems[0].startswith("Major review > Quiz: missing; add ### Quiz with its 5 criteria (line "), problems)
        self.assertIn("has it as ## Quiz; make it ### Quiz, under ## Major review)", problems[0])

    def test_final_has_its_own_closing_section(self):
        text = review_md("final", "bench/runs/final/r1", topics=("cooking",)).replace(f"### {reviews.NEXT_DO}", f"### {reviews.NEXT_FIX}")
        self.assertEqual(parse(text, "final").major.problems, [f"Major review > {reviews.NEXT_DO}: missing; add ### {reviews.NEXT_DO}"])

    def test_field_names_are_strict(self):
        text = review_md("c1-skills", RUN).replace("**My thoughts:**", "**Thoughts:**", 1).replace("- Why:", "- Reason:", 1)
        first = parse(text).rounds[0]
        self.assertEqual(first.problems, ["Quick rounds > Round 1: no **My thoughts:** line", "Quick rounds > Round 1: no \"- Why:\" line under What changed"])
        self.assertTrue(first.touched)

    def test_a_round_without_what_changed_and_with_an_unknown_kind(self):
        text = review_md("c1-skills", RUN, kinds={2: "a hook"})
        text = text.replace("**What changed:**", "**Changes:**", 1)
        first, second = parse(text).rounds
        self.assertEqual(first.problems, ["Quick rounds > Round 1: no **What changed:** line (Kind, Files and Why go under it)"])
        self.assertEqual(second.problems, ["Quick rounds > Round 2: Kind is 'a hook'; write one of modified skill, new skill, new subagent, other"])
        self.assertIsNone(second.kind_value)

    def test_empty_texts(self):
        text = review_md("c1-skills", RUN).replace("I asked the tutor for q3's answer twice; it gave a hint.", "")
        text = text.replace("Split the teach job so the figures get their own pass.", "")
        problems = parse(text).major.problems
        self.assertEqual(problems, ["Major review: Live tries is empty", "Major review > What the next step should fix: the text is empty"])

    def test_sessions_and_topics(self):
        text = review_md("final", "bench/runs/final/r1", sessions=2, topics=("cooking",))
        text = text.replace("**Topic:** cooking", "**Topic:** TODO", 1).replace("Session 2: forty minutes on knife skills; quiz 0003 q2 was fair.", "")
        text = text.replace("On cooking, final's lesson had a worked example where c0-baseline's had none.", "")
        r = parse(text, "final")
        self.assertEqual([s.problems for s in r.sessions], [
            ["Learning sessions > Session 1: Topic is still TODO"],
            ["Learning sessions > Session 2: no text below Date and Topic (how the session went)"],
        ])  # fmt: skip
        self.assertEqual(r.topics[0].problems, ["Test topics > cooking: no text below the heading (how c0-baseline and final compare on it)"])
        self.assertEqual(parse(review_md("final", topics=("`statics` (Mines course)",)), "final").topics[0].topic, "statics")

    def test_steps(self):
        with self.assertRaises(ValueError):
            reviews.parse_step("# Reviews", "c0-baseline")


class ComponentsTests(unittest.TestCase):
    def test_complete_entries(self):
        text = components_md(component_md("teach"), component_md("lesson-reviewer", "subagent", "c2-review", "no, because it found nothing the judge missed"))
        teach, reviewer = reviews.parse_components(text)
        self.assertEqual((teach.key, teach.kind, teach.step, teach.kept, teach.problems), ("teach", "skill", "c1-skills", True, []))
        self.assertEqual((reviewer.key, reviewer.kind, reviewer.step, reviewer.kept, reviewer.problems), ("lesson-reviewer", "subagent", "c2-review", False, []))
        self.assertEqual(len(reviews.parse_components(components_md())), 0, "the example inside the HTML comment is not an entry")

    def test_the_template_entry(self):
        (entry,) = reviews.parse_components(components_md(component_md("<name>", todo=True)))
        self.assertEqual(entry.problems, [
            "<name>: give the entry its component's name (the skill's folder name, or the subagent's name)",
            "<name>: Kind is still TODO", "<name>: Step added is still TODO", "<name>: Purpose is still TODO",
            "<name>: With and without is still TODO", "<name>: Review is still TODO", "<name>: Kept in final is still TODO",
        ])  # fmt: skip

    def test_bad_values(self):
        text = components_md(
            component_md("quiz", kind="tool"),
            component_md("`grade`", kept="maybe").replace("- Purpose:", "- Goal:"),
            component_md("tutor", kept="no."),
        )
        quiz, grade, tutor = reviews.parse_components(text.replace("\n", "\r\n"))
        self.assertEqual(quiz.problems, ["quiz: Kind is 'tool'; write skill or subagent"])
        self.assertEqual(grade.key, "grade")
        self.assertEqual(grade.problems, ["`grade`: no \"- Purpose:\" line", "`grade`: Kept in final is 'maybe'; start it with yes or no (no, because ...)"])
        self.assertEqual(tutor.problems, ["tutor: Kept in final is no, with no reason; write no, because ..."])
        self.assertFalse(tutor.kept)

    def test_values_over_several_lines(self):
        text = component_md("teach").replace("- Review: Without it", "- Review:\n  Without it")
        (entry,) = reviews.parse_components(components_md(text))
        self.assertEqual(entry.problems, [])
        self.assertTrue(entry.values["Review"].startswith("Without it"))


class ConfigComponentsTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="p3-components-"))
        self.addCleanup(shutil.rmtree, self.folder, True)

    def test_skills_and_subagents(self):
        claude = self.folder / ".claude"
        write(claude / "skills" / "teach" / "SKILL.md", "---\nname: teach\n---\n")
        write(claude / "skills" / "notes" / "README.md", "not a skill: no SKILL.md\n")
        write(claude / "agents" / "reviewer.md", "---\nname: lesson-reviewer\ndescription: x\n---\n\nReview.\n")
        write(claude / "agents" / "quoted.md", "---\r\nname: \"quiz-checker\"\r\n---\r\n")
        write(claude / "agents" / "plain.md", "You have no frontmatter.\n")
        write(claude / "agents" / "split" / "figure.md", "---\ndescription: no name here\n---\n")
        write(claude / "agents" / "README.md", "# My subagents\n")
        write(claude / "agents" / "notes.txt", "not a subagent\n")
        self.assertEqual(reviews.skill_names(self.folder), ["teach"])
        write(claude / "agents" / "split" / "planner.md", "---\nname: lesson-planner\ndescription: x\n---\n")
        write(claude / "agents" / "checklists" / "quiz.md", "# What the quiz reviewer checks\n\n---\n\n- name: every stem\n")
        write(claude / "agents" / "open.md", "---\nname: never-closed\n")
        write(claude / "agents" / "late.md", "\n---\nname: late-frontmatter\n---\n")
        self.assertEqual(reviews.subagents(self.folder), {
            "quiz-checker": ".claude/agents/quoted.md", "lesson-reviewer": ".claude/agents/reviewer.md", "lesson-planner": ".claude/agents/split/planner.md",
        }, "only a file whose frontmatter, from its first line, has a name is a subagent, as Claude Code loads them")  # fmt: skip
        self.assertEqual(reviews.agent_docs(self.folder), [
            ".claude/agents/checklists/quiz.md", ".claude/agents/late.md", ".claude/agents/open.md", ".claude/agents/plain.md", ".claude/agents/split/figure.md",
        ])  # fmt: skip
        self.assertEqual((reviews.skill_names(self.folder / "none"), reviews.subagents(self.folder / "none"), reviews.agent_docs(self.folder / "none")), ([], {}, []))


if __name__ == "__main__":
    unittest.main()
