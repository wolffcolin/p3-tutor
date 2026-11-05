"""Configs: the tutor's setup, as files, and the snapshots the bench runs.

A config is CLAUDE.md, PREFERENCES.md and everything under .claude/ in a source folder: tutor/ for the
live tutor, configs/<name>/ for a snapshot. Learner files (MISSION.md, NOTES.md, lessons/, quizzes/,
keys/, grades/, learning-records/, assets/, submissions/) are never part of a config, and neither is
.claude/settings.local.json, the personal file Claude Code writes when you approve a tool in an
interactive session and keeps out of git.

- `p3 snapshot <name>` copies the live config into configs/<name>/ and writes SNAPSHOT.json
  {"name", "hash", "created_at", "files"}; the bench refuses a snapshot whose files no longer match it.
- Each job (teach, tutor, quiz, grade) starts at /<job> when the config has that skill
  (.claude/skills/<job>/SKILL.md), else at /teach.
- The tools a run may use without asking are the config's .claude/settings.json permissions.allow,
  passed to claude with --allowedTools (in claude -p, a fresh folder ignores the project's allow rules).
- The model is .claude/settings.json "model", else sonnet.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from p3 import util
from p3.util import (  # re-exported: config_files, config_hash, load_snapshot and list_configs live in util
    LIVE_CONFIG,
    NAME_RE,
    P3Error,
    config_dir,
    config_files,
    config_hash,
    list_configs,
    load_snapshot,
)

__all__ = [
    "JOBS", "DEFAULT_MODEL", "Config", "config_files", "config_hash", "config_dir", "load_snapshot", "list_configs",
    "check_name", "snapshot", "verify_snapshot", "settings", "entries", "allowed_tools", "model", "resolve",
]  # fmt: skip

JOBS = ("teach", "tutor", "quiz", "grade")
DEFAULT_MODEL = "sonnet"
FALLBACK_ENTRY = "/teach"


def check_name(name: str) -> str:
    """The name, when it is a valid config name (^[a-z0-9][a-z0-9-]{0,40}$ and not "live"); else P3Error."""
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise P3Error(f"{name!r} is not a valid config name: use lowercase letters, digits and hyphens, starting with a letter or digit, at most 41 characters (for example c1-skills)")
    if name == LIVE_CONFIG:
        raise P3Error('"live" names the tutor/ folder itself; pick another name for a snapshot')
    return name


def snapshot(name: str, force: bool = False, root: Path | None = None) -> dict:
    """Copy the live config (tutor/) into configs/<name>/ and write its SNAPSHOT.json; returns the
    SNAPSHOT.json data. Refuses an existing snapshot unless `force`, which replaces it entirely."""
    root = Path(root) if root else util.repo_root()
    check_name(name)
    source = root / "tutor"
    files = config_files(source)
    if not files:
        raise P3Error("tutor/ has no config files (CLAUDE.md, PREFERENCES.md or .claude/); there is nothing to snapshot")
    not_utf8 = util.non_utf8_files(source, files)
    if not_utf8:
        # p3 hashes such a file with its line endings as they are, while git stores it with LF, so the
        # snapshot would stop matching its own hash in a fresh checkout (and in CI)
        raise P3Error(f"tutor/{', tutor/'.join(not_utf8)} {'is' if len(not_utf8) == 1 else 'are'} not UTF-8 text; {util.NON_UTF8_HINT}, then snapshot again")
    dest = root / "configs" / name
    if dest.exists():
        if not force:
            raise P3Error(f"configs/{name}/ already exists; pick a new name, or add --force to replace it (runs made with the old snapshot will no longer match it)")
        util.remove_tree(dest)
    util.copy_files(source, dest, files)
    digest = config_hash(dest)
    if digest != config_hash(source):
        raise P3Error(f"the copy in configs/{name}/ does not match tutor/; was a file changing while it was copied?")
    data = {"name": name, "hash": digest, "created_at": util.iso_utc(), "files": files}
    util.write_json(dest / "SNAPSHOT.json", data)
    return data


def verify_snapshot(name: str, root: Path | None = None) -> tuple[bool, str, str]:
    """(matches, recorded hash, recomputed hash) for configs/<name>/. Raises P3Error when the config
    or its SNAPSHOT.json is missing."""
    data = load_snapshot(name, root)
    actual = config_hash(config_dir(name, root))
    return data["hash"] == actual, data["hash"], actual


def settings(folder: Path) -> dict:
    """The parsed .claude/settings.json of a source folder ({} when absent). Raises P3Error when it
    does not parse or is not an object."""
    path = Path(folder) / ".claude" / "settings.json"
    if not path.is_file():
        return {}
    data = util.read_json(path)
    if not isinstance(data, dict):
        raise P3Error(f"{path} must hold a JSON object")
    return data


def entries(folder: Path) -> dict[str, str]:
    """{job: entry} for teach, tutor, quiz and grade: "/<job>" when .claude/skills/<job>/SKILL.md
    exists in the folder, else "/teach"."""
    folder = Path(folder)
    return {job: f"/{job}" if (folder / ".claude" / "skills" / job / "SKILL.md").is_file() else FALLBACK_ENTRY for job in JOBS}


def allowed_tools(folder: Path) -> list[str]:
    """The config's permissions.allow list (strings only, order kept), or [] when there is none."""
    perms = settings(folder).get("permissions")
    allow = perms.get("allow") if isinstance(perms, dict) else None
    if not isinstance(allow, list):
        return []
    return [rule for rule in allow if isinstance(rule, str) and rule.strip()]


def model(folder: Path) -> str:
    """The config's model: .claude/settings.json "model" when it is a non-empty string, else sonnet."""
    value = settings(folder).get("model")
    return value.strip() if isinstance(value, str) and value.strip() else DEFAULT_MODEL


@dataclass
class Config:
    """A config ready to run: its name ("live" or a snapshot name), source folder, hash, entries,
    allowed tools and model."""

    name: str
    folder: Path
    hash: str
    files: list[str]
    entries: dict[str, str]
    allowed_tools: list[str]
    model: str

    @property
    def live(self) -> bool:
        return self.name == LIVE_CONFIG


def resolve(name: str, root: Path | None = None) -> Config:
    """The config to run: "live" is tutor/ as it is now; any other name must be a snapshot under
    configs/ whose SNAPSHOT.json hash matches its files. Raises P3Error otherwise."""
    root = Path(root) if root else util.repo_root()
    if name != LIVE_CONFIG:
        check_name(name)
        ok, recorded, actual = verify_snapshot(name, root)
        if not ok:
            raise P3Error(
                f"configs/{name}/ no longer matches its SNAPSHOT.json (recorded {recorded[:19]}..., now {actual[:19]}...). "
                f"A snapshot is a fixed record; change tutor/ instead and take a new snapshot, or replace this one with `p3 snapshot {name} --force`."
            )
    folder = config_dir(name, root)
    files = config_files(folder)
    if not files:
        raise P3Error(f"{util.posix(folder, root)}/ has no config files (CLAUDE.md, PREFERENCES.md or .claude/)")
    return Config(name, folder, config_hash(folder), files, entries(folder), allowed_tools(folder), model(folder))
