"""Topic folders: loading them and checking that they hang together.

Shared topics live in bench/topics/<id>/ (fixed and hashed), own topics in bench/own/<id>/ (yours).
Both have the same shape:

    topic.json      metadata, objectives, facts and misconceptions
    grading.json    the true grades of the workspace submissions
    probes.json     the messages the tutor scenarios send
    workspace/      copied into every scenario folder: MISSION.md, NOTES.md, learning-records/,
                    quizzes/<graded quiz>.json, keys/<graded quiz>.json, submissions/<s>.json

`validate(folder)` returns the errors and the TODO markers it finds; p3 bench, p3 check and
p3 new-topic all use it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from p3 import util
from p3.util import P3Error

SHARED = "shared"
OWN = "own"
VERDICTS = ("correct", "partial", "wrong")
ITEM_TYPES = ("mcq", "numeric", "short")
CONFIG_NAMES = ("CLAUDE.md", "PREFERENCES.md", ".claude", "FORMATS.md")
MIN_FACTS = {SHARED: 4, OWN: 3}
MIN_PROBES = {SHARED: 6, OWN: 4}
MIN_SUBMISSIONS = {SHARED: 1, OWN: 1}
TODO = "TODO"
# Probe, submission, quiz item and graded quiz ids become parts of folder and file names (tutor-<probe>/,
# grade-<submission>/, submissions/<id>.json, grades/NNNN-<id>.json), so they must be safe on every system.
FILE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
FILE_ID_RULE = "letters, digits, - and _ only, starting with a letter or digit"


def topic_dir(topic_id: str, root: Path | None = None) -> tuple[Path, str]:
    """(folder, kind) of a topic: bench/topics/<id>/ ("shared") first, then bench/own/<id>/ ("own").
    Raises P3Error naming both places when neither exists."""
    root = Path(root) if root else util.repo_root()
    if not isinstance(topic_id, str) or not util.NAME_RE.match(topic_id):
        raise P3Error(f"{topic_id!r} is not a valid topic id: use lowercase letters, digits and hyphens")
    shared = root / "bench" / "topics" / topic_id
    if (shared / "topic.json").is_file():
        return shared, SHARED
    own = root / "bench" / "own" / topic_id
    if (own / "topic.json").is_file():
        return own, OWN
    raise P3Error(f"there is no topic {topic_id!r}: looked for bench/topics/{topic_id}/topic.json and bench/own/{topic_id}/topic.json")


def list_topics(root: Path | None = None) -> list[tuple[str, str, Path]]:
    """(id, kind, folder) of every folder under bench/topics/ and bench/own/ with a topic.json."""
    root = Path(root) if root else util.repo_root()
    found = []
    for kind, base in ((SHARED, root / "bench" / "topics"), (OWN, root / "bench" / "own")):
        if base.is_dir():
            for folder in sorted(p for p in base.iterdir() if p.is_dir() and (p / "topic.json").is_file()):
                found.append((folder.name, kind, folder))
    return found


@dataclass
class Topic:
    """A loaded topic: its id, kind (shared or own), folder and the parsed topic.json, grading.json
    and probes.json, with accessors for what the bench and the scorer need."""

    id: str
    kind: str
    path: Path
    meta: dict
    grading: dict
    probes: list[dict]

    @property
    def workspace(self) -> Path:
        return self.path / "workspace"

    @property
    def title(self) -> str:
        return str(self.meta.get("title") or self.id)

    @property
    def minutes(self) -> int:
        return int(self.meta.get("minutes") or 30)

    @property
    def learner_summary(self) -> str:
        return str(self.meta.get("learner_summary") or "")

    @property
    def teach_objective(self) -> str:
        return str(self.meta.get("teach_objective") or "")

    @property
    def quiz_objective(self) -> str:
        return str(self.meta.get("quiz_objective") or "")

    @property
    def graded_quiz(self) -> str:
        return str(self.meta.get("graded_quiz") or "")

    @property
    def submissions(self) -> list[str]:
        return [str(s) for s in self.meta.get("submissions") or []]

    @property
    def objectives(self) -> dict[str, str]:
        return {o["id"]: str(o.get("text") or "") for o in self.meta.get("objectives") or [] if isinstance(o, dict) and "id" in o}

    @property
    def misconceptions(self) -> list[dict]:
        return [m for m in self.meta.get("misconceptions") or [] if isinstance(m, dict)]

    def objective_text(self, objective_id: str) -> str:
        return self.objectives.get(objective_id, "")

    def facts_for(self, objective_id: str) -> list[dict]:
        return [f for f in self.meta.get("facts") or [] if isinstance(f, dict) and f.get("objective") == objective_id]

    def quiz(self, quiz_id: str) -> dict:
        return util.read_json(self.workspace / "quizzes" / f"{quiz_id}.json")

    def key(self, quiz_id: str) -> dict:
        return util.read_json(self.workspace / "keys" / f"{quiz_id}.json")

    def submission(self, submission_id: str) -> dict:
        return util.read_json(self.workspace / "submissions" / f"{submission_id}.json")

    def true_grades(self, submission_id: str) -> list[dict]:
        subs = self.grading.get("submissions") if isinstance(self.grading.get("submissions"), dict) else {}
        return [g for g in subs.get(submission_id) or [] if isinstance(g, dict)]

    def probe(self, probe_id: str) -> dict | None:
        return next((p for p in self.probes if p.get("id") == probe_id), None)

    def hash(self) -> str:
        return util.hash_tree(self.path)

    def rel_path(self, root: Path | None = None) -> str:
        root = Path(root) if root else util.repo_root()
        return util.posix(self.path, root)


def load(topic_id: str, root: Path | None = None) -> Topic:
    """Find and load a topic by id. Raises P3Error when it is missing or one of its three JSON files
    is missing or does not parse (validate() says what else is wrong)."""
    folder, kind = topic_dir(topic_id, root)
    return load_folder(folder, kind)


def load_folder(folder: Path, kind: str | None = None) -> Topic:
    """Load the topic in a folder (kind from its parent folder's name when not given)."""
    folder = Path(folder)
    kind = kind or (OWN if folder.parent.name == "own" else SHARED)
    meta = util.read_json(folder / "topic.json")
    grading = util.read_json(folder / "grading.json")
    probes = util.read_json(folder / "probes.json")
    if not isinstance(meta, dict) or not isinstance(grading, dict) or not isinstance(probes, dict):
        raise P3Error(f"{folder}: topic.json, grading.json and probes.json must each hold a JSON object")
    probe_list = [p for p in probes.get("probes") or [] if isinstance(p, dict)]
    return Topic(folder.name, kind, folder, meta, grading, probe_list)


# ---- validation ----


@dataclass
class Validation:
    """What validate() found: errors (the topic cannot be used as it is) and todos (TODO markers left)."""

    errors: list[str] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)

    def ok(self, allow_todo: bool = True) -> bool:
        return not self.errors and (allow_todo or not self.todos)

    def lines(self) -> list[str]:
        return [f"error: {e}" for e in self.errors] + [f"todo: {t}" for t in self.todos]


def _str(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _id_list(items, where: str, errors: list[str], required=("id",)) -> list[dict]:
    """The dict entries of a list, with an error for each non-dict, missing field or duplicate id."""
    if not isinstance(items, list):
        errors.append(f"{where} must be a list")
        return []
    good, seen = [], set()
    for n, item in enumerate(items, 1):
        if not isinstance(item, dict):
            errors.append(f"{where} entry {n} must be an object")
            continue
        missing = [k for k in required if k not in item or item[k] is None or (isinstance(item[k], str) and not item[k].strip())]
        if missing:
            errors.append(f"{where} entry {n} has no {', '.join(missing)}")
            continue
        if not isinstance(item["id"], str):
            errors.append(f"{where} entry {n}: id must be a string")
            continue
        if item["id"] in seen:
            errors.append(f"{where}: id {item['id']} is used twice")
            continue
        seen.add(item["id"])
        good.append(item)
    return good


def _load(folder: Path, rel: str, errors: list[str]):
    path = folder / rel
    if not path.is_file():
        errors.append(f"{rel} is missing")
        return None
    try:
        return util.read_json(path)
    except P3Error as exc:
        errors.append(f"{rel}: {str(exc).split(': ', 1)[-1]}")
        return None


def validate(folder: Path, kind: str | None = None) -> Validation:
    """Check a topic folder against the shape above and bench/FORMATS.md, and list its TODO markers.

    Errors: a missing or unparseable file; duplicate ids; a fact or quiz item whose objective does not
    exist; a teach or quiz objective that does not exist; a graded quiz, key or submission that is
    missing or does not agree with the others on item ids; a misconception id that does not exist;
    a probe whose leak check names a quiz item that does not exist; a probe, submission, quiz item or
    graded quiz id that is not safe in a file name; a text file that is not UTF-8; and too few facts
    for the teach objective, probes or submissions (shared topics: 4 facts and 6 probes; own topics:
    3 facts, 1 submission and 4 probes)."""
    folder = Path(folder)
    kind = kind or (OWN if folder.parent.name == "own" else SHARED)
    v = Validation()
    errors = v.errors
    for rel in util.list_files(folder):
        try:
            data = (folder / rel).read_bytes()
        except OSError:
            continue
        if util.is_non_utf8_text(data):
            errors.append(f"{rel} is not UTF-8 text, so its hash would differ between your checkout and the commit; {util.NON_UTF8_HINT}")
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        count = text.count(TODO)
        if count:
            v.todos.append(f"{rel}: {count} TODO marker{'s' if count != 1 else ''} to fill in")
    meta = _load(folder, "topic.json", errors)
    grading = _load(folder, "grading.json", errors)
    probes_doc = _load(folder, "probes.json", errors)
    workspace = folder / "workspace"
    if not workspace.is_dir():
        errors.append("workspace/ is missing")
    else:
        for name in ("MISSION.md", "NOTES.md"):
            if not (workspace / name).is_file():
                errors.append(f"workspace/{name} is missing")
        for name in CONFIG_NAMES:
            if (workspace / name).exists():
                errors.append(f"workspace/{name} must not exist: the config and FORMATS.md are copied in by the bench")
    if not isinstance(meta, dict):
        if meta is not None:
            errors.append("topic.json must hold a JSON object")
        return v

    # topic.json
    if meta.get("id") != folder.name:
        errors.append(f"topic.json: id must be {folder.name!r}, the folder's name (it is {meta.get('id')!r})")
    for key in ("title", "learner_summary"):
        if not _str(meta.get(key)):
            errors.append(f"topic.json: {key} must be a non-empty string")
    minutes = meta.get("minutes")
    if not (isinstance(minutes, int) and not isinstance(minutes, bool) and minutes > 0):
        errors.append("topic.json: minutes must be a positive whole number")
    objectives = _id_list(meta.get("objectives"), "topic.json objectives", errors, ("id", "text"))
    objective_ids = {o["id"] for o in objectives}
    facts = _id_list(meta.get("facts"), "topic.json facts", errors, ("id", "objective", "text"))
    for fact in facts:
        if fact["objective"] not in objective_ids:
            errors.append(f"topic.json: fact {fact['id']} names objective {fact['objective']}, which does not exist")
    misconceptions = _id_list(meta.get("misconceptions"), "topic.json misconceptions", errors, ("id", "text", "correction"))
    misconception_ids = {m["id"] for m in misconceptions}
    for key in ("teach_objective", "quiz_objective"):
        if meta.get(key) not in objective_ids:
            errors.append(f"topic.json: {key} {meta.get(key)!r} is not one of the objectives")
    teach_facts = [f for f in facts if f["objective"] == meta.get("teach_objective")]
    if len(teach_facts) < MIN_FACTS[kind]:
        errors.append(f"topic.json: the teach objective needs at least {MIN_FACTS[kind]} facts ({len(teach_facts)} now)")
    submissions = meta.get("submissions")
    if not isinstance(submissions, list) or not all(_str(s) for s in submissions):
        errors.append("topic.json: submissions must be a list of submission ids such as [\"s1\", \"s2\"]")
        submissions = []
    elif len(set(submissions)) != len(submissions):
        errors.append("topic.json: a submission id is listed twice")
    if len(submissions) < MIN_SUBMISSIONS[kind]:
        errors.append(f"topic.json: at least {MIN_SUBMISSIONS[kind]} submission is needed")
    for sid in submissions:
        if not FILE_ID_RE.match(sid):
            errors.append(f"topic.json: submission id {sid!r} becomes a file name, so use {FILE_ID_RULE}")
    graded = meta.get("graded_quiz")
    if not _str(graded):
        errors.append("topic.json: graded_quiz must name a quiz id such as \"0001\"")
        graded = None
    elif not FILE_ID_RE.match(graded):
        errors.append(f"topic.json: graded_quiz {graded!r} becomes a file name, so use {FILE_ID_RULE}")
        graded = None

    # the graded quiz, its key and the submissions
    item_ids: list[str] | None = None
    quiz_items: dict[str, dict] = {}
    if graded:
        quiz = _load(folder, f"workspace/quizzes/{graded}.json", errors)
        if isinstance(quiz, dict):
            if quiz.get("id") != graded:
                errors.append(f"workspace/quizzes/{graded}.json: id must be {graded!r}")
            items = _id_list(quiz.get("items"), f"workspace/quizzes/{graded}.json items", errors, ("id", "type", "objective", "stem"))
            for item in items:
                where = f"workspace/quizzes/{graded}.json item {item['id']}"
                if not FILE_ID_RE.match(item["id"]):
                    errors.append(f"{where}: the item id becomes part of names the bench uses, so use {FILE_ID_RULE}")
                if item["type"] not in ITEM_TYPES:
                    errors.append(f"{where}: type must be one of {', '.join(ITEM_TYPES)}")
                if item["objective"] not in objective_ids:
                    errors.append(f"{where}: objective {item['objective']} does not exist")
                if item["type"] == "mcq":
                    options = _id_list(item.get("options"), f"{where} options", errors, ("id", "text"))
                    if len(options) < 2:
                        errors.append(f"{where}: an mcq item needs at least two options")
                quiz_items[item["id"]] = item
            item_ids = [i["id"] for i in items]
        key = _load(folder, f"workspace/keys/{graded}.json", errors)
        if isinstance(key, dict) and item_ids is not None:
            if key.get("id") != graded:
                errors.append(f"workspace/keys/{graded}.json: id must be {graded!r}")
            key_items = _id_list(key.get("items"), f"workspace/keys/{graded}.json items", errors, ("id",))
            if sorted(k["id"] for k in key_items) != sorted(item_ids):
                errors.append(f"workspace/keys/{graded}.json: its item ids {sorted(k['id'] for k in key_items)} differ from the quiz's {sorted(item_ids)}")
            for k in key_items:
                where = f"workspace/keys/{graded}.json item {k['id']}"
                item = quiz_items.get(k["id"])
                if "answer" not in k:
                    errors.append(f"{where}: no answer")
                    continue
                if item is None:
                    continue
                option_ids = {o.get("id") for o in item.get("options") or [] if isinstance(o, dict)}
                if item["type"] == "mcq" and k["answer"] not in option_ids:
                    errors.append(f"{where}: the answer {k['answer']!r} is not one of the item's option ids")
                if item["type"] == "numeric" and not _number(k["answer"]):
                    errors.append(f"{where}: a numeric item's answer must be a number")
                if item["type"] == "short" and not _str(k["answer"]):
                    errors.append(f"{where}: a short item's answer must be a non-empty string")
                if "tolerance" in k and not (_number(k["tolerance"]) and k["tolerance"] >= 0):
                    errors.append(f"{where}: tolerance must be a number of zero or more")
                if "accepted" in k and not (isinstance(k["accepted"], list) and all(isinstance(a, str) for a in k["accepted"])):
                    errors.append(f"{where}: accepted must be a list of strings")
                distractors = k.get("distractors")
                if distractors is not None:
                    if not isinstance(distractors, dict):
                        errors.append(f"{where}: distractors must map option ids to misconception ids")
                    else:
                        for option, mid in distractors.items():
                            if item["type"] == "mcq" and option not in option_ids:
                                errors.append(f"{where}: distractor {option!r} is not one of the item's option ids")
                            if mid not in misconception_ids:
                                errors.append(f"{where}: distractor {option!r} names misconception {mid!r}, which does not exist")
        for sid in submissions:
            if not FILE_ID_RE.match(sid):
                continue  # reported above
            sub = _load(folder, f"workspace/submissions/{sid}.json", errors)
            if not isinstance(sub, dict) or item_ids is None:
                continue
            if sub.get("quiz") != graded:
                errors.append(f"workspace/submissions/{sid}.json: quiz must be {graded!r}")
            answers = _id_list(sub.get("answers"), f"workspace/submissions/{sid}.json answers", errors, ("id",))
            if sorted(a["id"] for a in answers) != sorted(item_ids):
                errors.append(f"workspace/submissions/{sid}.json: its answer ids {sorted(a['id'] for a in answers)} differ from the quiz's item ids {sorted(item_ids)}")

    # grading.json
    if isinstance(grading, dict):
        if graded and grading.get("quiz") != graded:
            errors.append(f"grading.json: quiz must be {graded!r}, the graded quiz")
        graded_subs = grading.get("submissions")
        if not isinstance(graded_subs, dict):
            errors.append("grading.json: submissions must map each submission id to its true grades")
        else:
            if sorted(graded_subs) != sorted(submissions):
                errors.append(f"grading.json: it grades {sorted(graded_subs)} but topic.json lists the submissions {sorted(submissions)}")
            for sid, grades in graded_subs.items():
                where = f"grading.json {sid}"
                good = _id_list(grades, where, errors, ("id", "verdict"))
                if item_ids is not None and sorted(g["id"] for g in good) != sorted(item_ids):
                    errors.append(f"{where}: its item ids {sorted(g['id'] for g in good)} differ from the quiz's {sorted(item_ids)}")
                for g in good:
                    if g["verdict"] not in VERDICTS:
                        errors.append(f"{where} item {g['id']}: verdict must be one of {', '.join(VERDICTS)}")
                    mid = g.get("misconception")
                    if mid is not None and mid not in misconception_ids:
                        errors.append(f"{where} item {g['id']}: misconception {mid!r} does not exist")
                    if not _str(g.get("why")):
                        errors.append(f"{where} item {g['id']}: why must say why the verdict is right")
    elif grading is not None:
        errors.append("grading.json must hold a JSON object")

    # probes.json
    if isinstance(probes_doc, dict):
        probes = _id_list(probes_doc.get("probes"), "probes.json probes", errors, ("id", "message", "expected"))
        if len(probes) < MIN_PROBES[kind]:
            errors.append(f"probes.json: at least {MIN_PROBES[kind]} probes are needed ({len(probes)} now)")
        for probe in probes:
            if not FILE_ID_RE.match(probe["id"]):
                errors.append(f"probes.json: probe id {probe['id']!r} becomes a folder name (tutor-<id>/), so use {FILE_ID_RULE}")
            leak = probe.get("leak_check")
            if leak is None:
                continue
            where = f"probes.json probe {probe['id']}"
            if not isinstance(leak, dict) or not _str(leak.get("quiz")) or not _str(leak.get("item")):
                errors.append(f"{where}: leak_check must be null or {{\"quiz\": \"0001\", \"item\": \"q3\"}}")
                continue
            qpath = workspace / "quizzes" / f"{leak['quiz']}.json"
            kpath = workspace / "keys" / f"{leak['quiz']}.json"
            if not qpath.is_file() or not kpath.is_file():
                errors.append(f"{where}: leak_check names quiz {leak['quiz']}, but workspace/quizzes/{leak['quiz']}.json or its key is missing")
                continue
            try:
                quiz = util.read_json(qpath)
                key = util.read_json(kpath)
            except P3Error:
                continue  # reported above for the graded quiz; another quiz's parse errors show here
            ids_q = {i.get("id") for i in (quiz.get("items") or []) if isinstance(i, dict)} if isinstance(quiz, dict) else set()
            ids_k = {i.get("id") for i in (key.get("items") or []) if isinstance(i, dict)} if isinstance(key, dict) else set()
            if leak["item"] not in ids_q or leak["item"] not in ids_k:
                errors.append(f"{where}: leak_check names item {leak['item']}, which is not in quiz {leak['quiz']} and its key")
    elif probes_doc is not None:
        errors.append("probes.json must hold a JSON object")
    return v
