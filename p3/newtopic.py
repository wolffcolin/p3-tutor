"""`p3 new-topic <id>`: a skeleton own topic in bench/own/<id>/, every file present.

Each placeholder is marked TODO, and each JSON file holds a short example of its shape (three quiz
items, one submission, four probes), which is the least an own topic needs. Fill in every TODO,
check it with `p3 check`, and commit it before its first bench run: the bench refuses an own topic
that is not committed and unchanged.
"""

from __future__ import annotations

from pathlib import Path

from p3 import topic, util
from p3.util import P3Error


def skeleton(topic_id: str) -> dict[str, object]:
    """{relative path: content} of a new own topic: dicts become JSON files, strings Markdown files."""
    todo_objective = "TODO: what the learner can do after this objective, as one sentence"
    return {
        "topic.json": {
            "id": topic_id,
            "title": "TODO: the topic's title",
            "learner_summary": "TODO: who the learner is and what they already know, in two or three sentences",
            "minutes": 30,
            "teach_objective": "O2",
            "quiz_objective": "O3",
            "graded_quiz": "0001",
            "submissions": ["s1"],
            "objectives": [
                {"id": "O1", "text": f"{todo_objective} (the graded quiz covers it)"},
                {"id": "O2", "text": f"{todo_objective} (the bench teaches it)"},
                {"id": "O3", "text": f"{todo_objective} (the bench writes a quiz on it)"},
            ],
            "facts": [
                {"id": f"F2.{n}", "objective": "O2", "text": "TODO: one checkable statement a lesson on O2 must get right"}
                for n in (1, 2, 3)
            ],
            "misconceptions": [
                {"id": f"M{n}", "text": "TODO: a mistaken belief a learner may hold", "correction": "TODO: what is true instead"}
                for n in (1, 2)
            ],
        },
        "grading.json": {
            "quiz": "0001",
            "submissions": {
                "s1": [
                    {"id": "q1", "verdict": "wrong", "misconception": "M1", "why": "TODO: why this verdict is the right one"},
                    {"id": "q2", "verdict": "correct", "misconception": None, "why": "TODO: why this verdict is the right one"},
                    {"id": "q3", "verdict": "partial", "misconception": None, "why": "TODO: why this verdict is the right one"},
                ]
            },
        },
        "probes.json": {
            "probes": [
                {"id": "p01", "message": "TODO: the learner asks outright for the answer to quiz 0001 question q1", "expected": "TODO: what a good tutor does instead", "leak_check": {"quiz": "0001", "item": "q1"}},
                {"id": "p02", "message": "TODO: the learner states one of the misconceptions as fact", "expected": "TODO: what a good tutor does", "leak_check": None},
                {"id": "p03", "message": "TODO: a question built on a false premise", "expected": "TODO: what a good tutor does", "leak_check": None},
                {"id": "p04", "message": "TODO: a question far above the learner's level", "expected": "TODO: what a good tutor does", "leak_check": None},
            ]
        },
        "workspace/MISSION.md": (
            "# Mission\n\n"
            "TODO: Why the learner wants to learn this topic, in their own words.\n"
            "TODO: What they want to be able to do when they are done.\n"
        ),
        "workspace/NOTES.md": (
            "# Notes\n\n"
            "TODO: What the learner already knows.\n"
            "TODO: What they do not know yet, and where they tend to get stuck.\n"
        ),
        "workspace/learning-records/0001-first-session.md": (
            "# 0001 - First session\n\n"
            "TODO: What the learner learned in an earlier session, in the teach skill's learning-record format.\n"
        ),
        "workspace/quizzes/0001.json": {
            "id": "0001",
            "objective": "O1",
            "title": "TODO: the quiz's title",
            "items": [
                {"id": "q1", "type": "mcq", "objective": "O1", "stem": "TODO: a multiple-choice question", "options": [{"id": "a", "text": "TODO: a wrong option tied to M1"}, {"id": "b", "text": "TODO: the right option"}, {"id": "c", "text": "TODO: a wrong option tied to M2"}]},
                {"id": "q2", "type": "numeric", "objective": "O1", "stem": "TODO: a question with a number for its answer", "unit": "TODO: the unit"},
                {"id": "q3", "type": "short", "objective": "O1", "stem": "TODO: a question with a short written answer"},
            ],
        },
        "workspace/keys/0001.json": {
            "id": "0001",
            "items": [
                {"id": "q1", "answer": "b", "rationale": "TODO: why b is right", "distractors": {"a": "M1", "c": "M2"}},
                {"id": "q2", "answer": 0, "tolerance": 0.5, "rationale": "TODO: the right number, and how to get it"},
                {"id": "q3", "answer": "TODO: the reference answer", "accepted": ["TODO: another form that counts as right"], "rationale": "TODO: what a right answer must say"},
            ],
        },
        "workspace/submissions/s1.json": {
            "quiz": "0001",
            "learner": "TODO: the learner's name",
            "answers": [
                {"id": "q1", "response": "a"},
                {"id": "q2", "response": "TODO: the learner's number"},
                {"id": "q3", "response": "TODO: the learner's answer, partly right"},
            ],
        },
    }


def create(topic_id: str, root: Path | None = None) -> Path:
    """Write the skeleton to bench/own/<id>/ and return the folder. Refuses an id that is not valid or
    that a shared or own topic already uses."""
    root = Path(root) if root else util.repo_root()
    if not util.NAME_RE.match(topic_id or ""):
        raise P3Error(f"{topic_id!r} is not a valid topic id: use lowercase letters, digits and hyphens, starting with a letter or digit (for example statics-trusses)")
    if (root / "bench" / "topics" / topic_id).exists():
        raise P3Error(f"{topic_id} is a shared topic (bench/topics/{topic_id}/); pick another id")
    folder = root / "bench" / "own" / topic_id
    if folder.exists():
        raise P3Error(f"bench/own/{topic_id}/ already exists; edit it, or delete it to start over")
    for rel, content in skeleton(topic_id).items():
        if isinstance(content, str):
            util.write_text(folder / rel, content)
        else:
            util.write_json(folder / rel, content)
    return folder


def main(args) -> int:
    """The p3 new-topic command."""
    root = util.repo_root()
    folder = create(args.topic_id, root)
    rel = util.posix(folder, root)
    v = topic.validate(folder, topic.OWN)
    print(f"wrote {rel}/ with {len(util.list_files(folder))} files")
    if v.errors:
        print("problems:\n  " + "\n  ".join(v.errors))
    print(f"{len(v.todos)} files hold TODO markers to fill in; p3 check lists them.")
    print("Then commit the topic before its first run: the bench runs an own topic only when it is committed and unchanged.")
    return 0
