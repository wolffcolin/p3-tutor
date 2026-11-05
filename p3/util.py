"""Shared helpers for every p3 command: the repo root, JSON files, hashing, run listing and git.

Everything here is standard library and works the same on Windows, macOS and Linux.
Paths inside the repo are always handled as POSIX relative strings ("bench/FORMATS.md"), so a hash or
a record written on one system matches the same files on another.

Hashing:

- `normalized_bytes(path)`: a text file (one that decodes as UTF-8) with every CRLF turned into LF;
  any other file as it is. Every hash in p3 is computed over these bytes, so a checkout with Windows
  line endings hashes the same as one with Unix line endings.
- `hash_files(root, rel_paths)`: "sha256:<hex>" over, for each path in sorted order, the path, a NUL
  byte, the normalized content and a NUL byte. `hash_tree(folder)` is the same over every file in a
  folder, and `config_hash(folder)` over a config's files.
- `file_digest(path)`: the plain hex sha256 of one file's normalized bytes, as `p3/bench.sha256`
  lists them (`<hex>  <posix path>` lines).

Junk files that operating systems drop into folders (`.DS_Store`, `Thumbs.db`, `desktop.ini`) and
Python caches (`__pycache__/`, `*.pyc`) are never listed, copied or hashed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, NamedTuple

ROOT_ENV = "P3_ROOT"
JUNK_NAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})
JUNK_DIRS = frozenset({"__pycache__", ".git"})
JUNK_SUFFIXES = (".pyc", ".pyo")
HASH_FILE = "p3/bench.sha256"
SHARED_TOPIC = "agent-architecture"
LIVE_CONFIG = "live"
LIVE_RUNS_DIR = "_live"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")


class P3Error(Exception):
    """A problem the person running p3 can fix; the command prints the message and exits non-zero."""


# ---- paths ----


def repo_root() -> Path:
    """The P3 repository: $P3_ROOT when set, else the nearest folder at or above the current one that
    holds p3.json or bench/scenarios.json, else the folder that holds this p3 package."""
    env = os.environ.get(ROOT_ENV)
    if env:
        return Path(env).resolve()
    here = Path.cwd().resolve()
    for folder in (here, *here.parents):
        if (folder / "p3.json").is_file() or (folder / "bench" / "scenarios.json").is_file():
            return folder
    return Path(__file__).resolve().parent.parent


def posix(path: Path | str, root: Path | None = None) -> str:
    """A path as a POSIX string, relative to `root` when given."""
    p = Path(path)
    if root is not None:
        p = p.resolve().relative_to(Path(root).resolve())
    return p.as_posix()


def is_junk(rel_path: str) -> bool:
    """True for operating-system junk files and Python caches, which p3 never copies or hashes."""
    parts = rel_path.split("/")
    return parts[-1] in JUNK_NAMES or parts[-1].endswith(JUNK_SUFFIXES) or any(part in JUNK_DIRS for part in parts[:-1])


def list_files(folder: Path) -> list[str]:
    """Every file under `folder`, recursively, as sorted POSIX paths relative to it (junk left out).
    A missing folder has no files."""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    found = []
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = [d for d in dirnames if d not in JUNK_DIRS]
        base = Path(dirpath)
        for name in filenames:
            rel = (base / name).relative_to(folder).as_posix()
            if not is_junk(rel):
                found.append(rel)
    return sorted(found)


def copy_files(src: Path, dest: Path, rel_paths: Iterable[str]) -> None:
    """Copy each relative path from `src` to the same relative path under `dest`, making folders."""
    for rel in rel_paths:
        target = Path(dest) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(src) / rel, target)


def remove_tree(folder: Path) -> None:
    """Delete a folder and everything in it, read-only files included (as git leaves them on Windows);
    a file another program still holds is left behind rather than failing the command."""

    def retry(func, path, _exc):
        try:
            os.chmod(path, 0o700)
            func(path)
        except OSError:
            pass

    if not Path(folder).exists():
        return
    if sys.version_info >= (3, 12):
        shutil.rmtree(folder, onexc=retry)
    else:
        shutil.rmtree(folder, onerror=retry)


# ---- JSON and text ----


def read_json(path: Path) -> Any:
    """Parse a UTF-8 JSON file (a byte-order mark is allowed). Raises P3Error naming the file when it
    is missing or does not parse."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise P3Error(f"{path} does not exist") from None
    except UnicodeDecodeError as exc:
        raise P3Error(f"{path} is not UTF-8 text: {exc}") from None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise P3Error(f"{path} is not valid JSON: {exc}") from None


def write_json(path: Path, data: Any) -> None:
    """Write `data` as UTF-8 JSON, indented two spaces, with LF line endings and a final newline;
    folders are made as needed."""
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def write_text(path: Path, text: str) -> None:
    """Write UTF-8 text with LF line endings, making folders as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def replace_json(path: Path, data: Any) -> None:
    """write_json through a temporary file beside `path` that then replaces it, so a reader, or a
    crash halfway, never sees half a file. Retries briefly when another program (a virus scanner on
    Windows) holds the file for a moment."""
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    write_json(tmp, data)
    attempts = 30  # about six seconds in all, which outlasts a scanner's or OneDrive's usual hold
    for attempt in range(attempts):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == attempts - 1:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(min(0.25, 0.02 * (attempt + 1)))


def read_text(path: Path) -> str:
    """Read a UTF-8 text file with any line endings turned into LF (undecodable bytes replaced)."""
    return Path(path).read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")


# ---- hashing ----


def normalize(data: bytes) -> bytes:
    """Bytes as p3 hashes them: CRLF turned into LF when the bytes decode as UTF-8, else unchanged."""
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    return data.replace(b"\r\n", b"\n")


def is_non_utf8_text(data: bytes) -> bool:
    """True for bytes that look like text (no NUL byte) but do not decode as UTF-8, such as a file
    saved in a Windows "ANSI" encoding. p3 hashes such a file as it is, with its CRLF line endings,
    while git stores it with LF, so its hash would differ between a checkout and the commit."""
    if b"\0" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def non_utf8_files(folder: Path, rel_paths: Iterable[str]) -> list[str]:
    """The paths among `rel_paths` (under `folder`) of text files that are not UTF-8 (see is_non_utf8_text)."""
    found = []
    for rel in rel_paths:
        try:
            if is_non_utf8_text((Path(folder) / rel).read_bytes()):
                found.append(rel)
        except OSError:
            continue
    return found


NON_UTF8_HINT = "save it as UTF-8 (in VS Code: Reopen with Encoding, then Save with Encoding, UTF-8)"


def utf8_problem(path: Path) -> str | None:
    """Why a text file a person writes is not UTF-8, in words for them, or None when it is (or cannot
    be read): UTF-16, which Windows PowerShell 5.1 writes with > and Out-File, or another encoding,
    such as a Windows "ANSI" code page. Either one hides headings and letters from a reader of UTF-8."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    if data.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\0" in data:
        return "it is saved as UTF-16 (as Windows PowerShell's > and Out-File write files), not UTF-8"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return "it is not saved as UTF-8 (a Windows \"ANSI\" encoding, perhaps)"
    return None


def normalized_bytes(path: Path) -> bytes:
    """A file's bytes as p3 hashes them (see normalize)."""
    return normalize(Path(path).read_bytes())


def file_digest(path: Path) -> str:
    """The plain hex sha256 of one file's normalized bytes (the form p3/bench.sha256 lists)."""
    return hashlib.sha256(normalized_bytes(path)).hexdigest()


def hash_entries(entries: Iterable[tuple[str, bytes]]) -> str:
    """"sha256:<hex>" over (relative path, raw content) pairs, in sorted path order, each as the path,
    a NUL byte, the normalized content and a NUL byte. hash_files and hash_tree use this; so can a
    caller hashing files read from git (git_show_bytes)."""
    h = hashlib.sha256()
    for rel, data in sorted(entries, key=lambda e: e[0]):
        h.update(rel.encode("utf-8") + b"\0" + normalize(data) + b"\0")
    return "sha256:" + h.hexdigest()


def hash_files(root: Path, rel_paths: Iterable[str]) -> str:
    """"sha256:<hex>" over the given files under `root` (POSIX relative paths), in sorted order."""
    root = Path(root)
    return hash_entries((rel, (root / rel).read_bytes()) for rel in rel_paths)


def hash_tree(folder: Path) -> str:
    """"sha256:<hex>" over every file in a folder (junk left out), as hash_files does it."""
    return hash_files(folder, list_files(folder))


# ---- configs (config.py re-exports these) ----

CONFIG_TOP_FILES = ("CLAUDE.md", "PREFERENCES.md")
CONFIG_DIR = ".claude"
# Claude Code writes .claude/settings.local.json when you approve a tool in an interactive session
# and tells git to ignore it, so a snapshot holding it would never match its committed copy (and it
# holds personal settings): it is never part of a config.
CONFIG_EXCLUDED = frozenset({".claude/settings.local.json"})


def config_files(folder: Path) -> list[str]:
    """The config files of a source folder (tutor/ or configs/<name>/), as sorted POSIX relative paths:
    CLAUDE.md and PREFERENCES.md when present, and every file under .claude/ (junk left out) except
    .claude/settings.local.json, which is personal and not committed. Learner files and SNAPSHOT.json
    are never part of a config."""
    folder = Path(folder)
    files = [name for name in CONFIG_TOP_FILES if (folder / name).is_file()]
    files += [f"{CONFIG_DIR}/{rel}" for rel in list_files(folder / CONFIG_DIR) if f"{CONFIG_DIR}/{rel}" not in CONFIG_EXCLUDED]
    return sorted(files)


def config_hash(folder: Path) -> str:
    """The config hash of a source folder: hash_files over config_files(folder)."""
    return hash_files(folder, config_files(folder))


def config_dir(name: str, root: Path | None = None) -> Path:
    """The source folder of a config: tutor/ for "live", else configs/<name>/."""
    root = Path(root) if root else repo_root()
    return root / "tutor" if name == LIVE_CONFIG else root / "configs" / name


def load_snapshot(name: str, root: Path | None = None) -> dict:
    """The parsed configs/<name>/SNAPSHOT.json ({"name", "hash", "created_at", "files"}).
    Raises P3Error when the config or its SNAPSHOT.json is missing or broken."""
    root = Path(root) if root else repo_root()
    folder = root / "configs" / name
    if not folder.is_dir():
        raise P3Error(f"there is no config named {name!r} (no folder configs/{name}/); make one with `p3 snapshot {name}`")
    data = read_json(folder / "SNAPSHOT.json")
    if not isinstance(data, dict) or not isinstance(data.get("hash"), str):
        raise P3Error(f"configs/{name}/SNAPSHOT.json has no hash; make the snapshot again with `p3 snapshot {name} --force`")
    return data


def list_configs(root: Path | None = None) -> list[str]:
    """The names of every folder under configs/ that holds a SNAPSHOT.json, sorted."""
    root = Path(root) if root else repo_root()
    base = root / "configs"
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir() and (p / "SNAPSHOT.json").is_file())


# ---- runs ----


class RunRecord(NamedTuple):
    """One run folder under bench/runs/: its folder, the parsed run.json, and the parsed score.json
    (None when the run has not been scored). It unpacks as (dir, run, score), and record["run"],
    record.run, record.path and record.run_id all work."""

    dir: Path
    run: dict
    score: dict | None

    def __getitem__(self, key):  # type: ignore[override]
        if isinstance(key, str):
            return getattr(self, key)
        return tuple.__getitem__(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    @property
    def path(self) -> Path:
        return self.dir

    @property
    def run_id(self) -> str:
        return self.run.get("run_id") or self.dir.name

    @property
    def config(self) -> str:
        return self.run.get("config") or ""

    @property
    def scored(self) -> bool:
        return self.score is not None


def runs_dir(config: str, root: Path | None = None) -> Path:
    """bench/runs/<config>/, or bench/runs/_live/ for the live config."""
    root = Path(root) if root else repo_root()
    return root / "bench" / "runs" / (LIVE_RUNS_DIR if config == LIVE_CONFIG else config)


FULL, TEACH_ONLY, PARTIAL = "full", "teach-only", "partial"


def run_kind(run: dict) -> str:
    """What a run ran: "full" (every scenario; no --only), "teach-only" (--only with the teach job
    alone, as the length study runs it) or "partial" (any other --only run, such as one made while
    iterating on a single scenario)."""
    if not run.get("only"):
        return FULL
    jobs = [s.get("job") for s in run.get("scenarios") or [] if isinstance(s, dict)]
    return TEACH_ONLY if jobs and all(j == "teach" for j in jobs) else PARTIAL


def list_runs(
    config: str | None = None, topic: str | None = None, *, scored: bool | None = None,
    minutes: int | None = None, quick: bool | None = None, kind: str | None = None,
    include_live: bool = False, root: Path | None = None,
) -> list[RunRecord]:
    """Every run under bench/runs/<config>/<run-id>/ that has a parseable run.json, oldest first
    (by started_at, then run id), as RunRecord(dir, run, score).

    Filters: `config` (a name, or "live" for bench/runs/_live/), `topic` (run.json "topic"),
    `scored` (True: only runs with a parseable score.json; False: only unscored), `minutes` and
    `quick` (run.json fields), and `kind` (run_kind: "full", "teach-only" or "partial"). Live runs
    are left out unless config="live" or include_live=True. A run.json or score.json that does not
    parse is skipped (score: treated as unscored); p3 check reports broken JSON files itself."""
    root = Path(root) if root else repo_root()
    base = root / "bench" / "runs"
    if not base.is_dir():
        return []
    if config is not None:
        folders = [runs_dir(config, root)]
    else:
        folders = sorted(p for p in base.iterdir() if p.is_dir() and (include_live or p.name != LIVE_RUNS_DIR))
    records = []
    for folder in folders:
        if not folder.is_dir():
            continue
        for run_dir in sorted(p for p in folder.iterdir() if p.is_dir()):
            try:
                run = read_json(run_dir / "run.json")
            except P3Error:
                continue
            if not isinstance(run, dict):
                continue
            score = None
            if (run_dir / "score.json").is_file():
                try:
                    score = read_json(run_dir / "score.json")
                except P3Error:
                    score = None
                if not isinstance(score, dict):
                    score = None
            if topic is not None and run.get("topic") != topic:
                continue
            if scored is not None and (score is not None) != scored:
                continue
            if minutes is not None and run.get("minutes") != minutes:
                continue
            if quick is not None and bool(run.get("quick")) != quick:
                continue
            if kind is not None and run_kind(run) != kind:
                continue
            records.append(RunRecord(run_dir, run, score))
    records.sort(key=lambda r: (str(r.run.get("started_at") or ""), r.run_id))
    return records


# ---- the fixed files and p3/bench.sha256 ----

HASH_FILE_HEADER = """\
# sha256 of every fixed file: bench/FORMATS.md, bench/scenarios.json, bench/judge/, bench/topics/ and p3/*.py.
# Text files are hashed with CRLF turned into LF, so the hashes hold on every operating system.
# p3 check compares the files with this list. Instructor only: `python -m p3 rehash` rewrites it.
"""


def fixed_files(root: Path | None = None) -> list[str]:
    """The fixed set as sorted POSIX paths relative to the repo: bench/FORMATS.md, bench/scenarios.json,
    every file under bench/judge/ and bench/topics/, and every .py file under p3/ (those that exist)."""
    root = Path(root) if root else repo_root()
    files = [rel for rel in ("bench/FORMATS.md", "bench/scenarios.json") if (root / rel).is_file()]
    for folder in ("bench/judge", "bench/topics"):
        files += [f"{folder}/{rel}" for rel in list_files(root / folder)]
    files += [f"p3/{rel}" for rel in list_files(root / "p3") if rel.endswith(".py")]
    return sorted(files)


def fixed_hashes(root: Path | None = None) -> dict[str, str]:
    """{posix path: hex digest} of the fixed set as it is on disk now."""
    root = Path(root) if root else repo_root()
    return {rel: file_digest(root / rel) for rel in fixed_files(root)}


def read_hash_file(path: Path) -> dict[str, str]:
    """{posix path: hex digest} from a `<hex>  <path>` file such as p3/bench.sha256 ("#" lines and
    blank lines skipped; a "sha256:" prefix on a digest is accepted)."""
    entries = {}
    for line in read_text(path).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        digest, _, name = line.strip().partition("  ")
        if not name:
            digest, _, name = line.strip().partition(" ")
        entries[name.strip()] = digest.strip().removeprefix("sha256:")
    return entries


def render_hash_file(hashes: dict[str, str]) -> str:
    """The text of p3/bench.sha256 for these {path: digest} entries."""
    return HASH_FILE_HEADER + "".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items()))


def rehash(root: Path | None = None) -> dict[str, str]:
    """Rewrite p3/bench.sha256 from the fixed files on disk (instructor only) and return the entries."""
    root = Path(root) if root else repo_root()
    hashes = fixed_hashes(root)
    write_text(root / HASH_FILE, render_hash_file(hashes))
    return hashes


def verify_fixed(root: Path | None = None) -> dict[str, list[str]]:
    """Compare the fixed files with p3/bench.sha256: {"missing": listed but absent, "changed": present
    with another hash, "extra": present but not listed}. Raises P3Error when the hash file is missing."""
    root = Path(root) if root else repo_root()
    if not (root / HASH_FILE).is_file():
        raise P3Error(f"{HASH_FILE} is missing")
    expected = read_hash_file(root / HASH_FILE)
    actual = fixed_hashes(root)
    return {
        "missing": sorted(p for p in expected if p not in actual),
        "changed": sorted(p for p in expected if p in actual and actual[p] != expected[p]),
        "extra": sorted(p for p in actual if p not in expected),
    }


# ---- time ----


def utc_now() -> datetime:
    """The current time in UTC, to the second."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_utc(when: datetime | None = None) -> str:
    """ISO 8601 UTC with a Z, such as 2026-11-03T14:05:09Z."""
    when = (when or utc_now()).astimezone(timezone.utc).replace(microsecond=0)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp(when: datetime | None = None) -> str:
    """The yyyymmdd-hhmmss UTC stamp that starts run and session ids."""
    return (when or utc_now()).astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S")


def parse_iso(text: str | None) -> datetime | None:
    """Parse an ISO 8601 time (a trailing Z allowed) into an aware datetime; None when it does not parse."""
    if not text:
        return None
    try:
        when = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


# ---- git ----


def _git(args: list[str], root: Path | None = None, binary: bool = False, stdin: bytes | None = None):
    """Run git in the repo, with `stdin` as its input (binary); the CompletedProcess, or None when git
    is missing or cannot start."""
    git = shutil.which("git")
    if not git:
        return None
    root = Path(root) if root else repo_root()
    try:
        return subprocess.run(
            [git, "-C", str(root), *args], capture_output=True, timeout=60, input=stdin,
            **({} if binary else {"text": True, "encoding": "utf-8", "errors": "replace"}),
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return None


def git_available(root: Path | None = None) -> bool:
    """True when git is installed and the repo root is the top of a git work tree."""
    root = Path(root) if root else repo_root()
    done = _git(["rev-parse", "--show-toplevel"], root)
    if done is None or done.returncode != 0 or not done.stdout.strip():
        return False
    top = Path(done.stdout.strip())
    return os.path.normcase(str(top.resolve())) == os.path.normcase(str(root.resolve()))


def git_problem(root: Path | None = None) -> str | None:
    """Why git cannot be used on the repo here, said for the person running p3, or None when it can:
    git is missing, git refuses the folder (its own message, which for a repo owned by another
    account names the `git config --global --add safe.directory` fix), or the folder is not the top
    of its own repository (a downloaded zip inside another repo)."""
    if not shutil.which("git"):
        return "git is not installed or not on your PATH (install it, or open a terminal where `git --version` works)"
    root = Path(root) if root else repo_root()
    done = _git(["rev-parse", "--show-toplevel"], root)
    if done is None:
        return "git could not be started"
    if done.returncode != 0 or not done.stdout.strip():
        detail = " ".join((done.stderr or "").split())
        return f"git cannot use this folder as a repository: {detail or 'git rev-parse failed'}"
    top = Path(done.stdout.strip())
    if os.path.normcase(str(top.resolve())) != os.path.normcase(str(root.resolve())):
        return f"this folder is not its own git repository (git's top folder here is {top}; was it downloaded as a zip?): clone your repo with git and work in the clone"
    return None


def rev_parse_head(root: Path | None = None) -> str | None:
    """The commit HEAD points at (full hex), or None outside a git repo or before the first commit."""
    if not git_available(root):
        return None
    done = _git(["rev-parse", "HEAD"], root)
    if done is None or done.returncode != 0:
        return None
    return done.stdout.strip() or None


def git_show_bytes(commit: str, path: str, root: Path | None = None) -> bytes | None:
    """The bytes of `path` (POSIX, relative to the repo) as committed in `commit`, or None when the
    file is not in that commit or git is not available."""
    if not git_available(root):
        return None
    return _show_bytes(commit, path, root)


def _show_bytes(commit: str, path: str, root: Path | None = None) -> bytes | None:
    """git_show_bytes once git is known to work on the repo."""
    done = _git(["show", f"{commit}:{path}"], root, binary=True)
    if done is None or done.returncode != 0:
        return None
    return done.stdout


def git_ls_files_at(commit: str, folder: str, root: Path | None = None) -> list[str] | None:
    """The files under `folder` (POSIX, relative to the repo) in `commit`, as sorted POSIX paths
    relative to that folder (junk left out); None when git is not available or the commit is unknown."""
    if not git_available(root):
        return None
    folder = folder.strip("/")
    done = _git(["ls-tree", "-r", "--name-only", "-z", commit, "--", folder + "/"], root)
    if done is None or done.returncode != 0:
        return None
    files = []
    for name in done.stdout.split("\0"):
        if name.startswith(folder + "/"):
            rel = name[len(folder) + 1:]
            if rel and not is_junk(rel):
                files.append(rel)
    return sorted(files)


def hash_tree_at_commit(commit: str, folder: str, root: Path | None = None) -> str | None:
    """hash_tree of `folder` as it was in `commit` (read with git), or None when git is not available,
    the commit is unknown or the folder is not in it."""
    files = git_ls_files_at(commit, folder, root)
    if not files:
        return None
    entries = []
    for rel in files:
        data = _show_bytes(commit, f"{folder.strip('/')}/{rel}", root)  # git works: it listed the files
        if data is None:
            return None
        entries.append((rel, data))
    return hash_entries(entries)


def path_clean_and_tracked(path: str, root: Path | None = None) -> bool:
    """True when git tracks files under `path` (POSIX, relative to the repo) and `git status
    --porcelain` shows nothing for it: committed and unchanged. False outside a git repo."""
    if not git_available(root):
        return False
    tracked = _git(["ls-files", "--", path], root)
    if tracked is None or tracked.returncode != 0 or not tracked.stdout.strip():
        return False
    status = _git(["status", "--porcelain", "--untracked-files=all", "--", path], root)
    return status is not None and status.returncode == 0 and not status.stdout.strip()


def first_commit_time(path: str, root: Path | None = None) -> datetime | None:
    """The committer time (aware, UTC) of the first commit that contains `path` (POSIX, relative to
    the repo), or None when it was never committed or git is not available."""
    if not git_available(root):
        return None
    done = _git(["log", "--format=%cI", "--reverse", "--", path], root)
    if done is None or done.returncode != 0:
        return None
    lines = [line for line in done.stdout.splitlines() if line.strip()]
    if not lines:
        return None
    when = parse_iso(lines[0].strip())
    return when.astimezone(timezone.utc) if when else None


def git_log_path(path: str, root: Path | None = None) -> list[tuple[str, datetime]]:
    """(commit, committer time in UTC) of every commit that changed `path` (POSIX, relative to the
    repo), oldest first; [] when it was never committed or git is not available."""
    if not git_available(root):
        return []
    done = _git(["log", "--format=%H %cI", "--reverse", "--", path], root)
    if done is None or done.returncode != 0:
        return []
    commits = []
    for line in done.stdout.splitlines():
        commit, _, text = line.strip().partition(" ")
        when = parse_iso(text.strip())
        if commit and when:
            commits.append((commit, when.astimezone(timezone.utc)))
    return commits


def git_file_versions(path: str, root: Path | None = None) -> Iterator[tuple[str, datetime, bytes | None]]:
    """(commit, committer time in UTC, the file's bytes in that commit) for every commit that changed
    `path` (POSIX, relative to the repo), oldest first; the bytes are None in a commit that deleted
    the file. Nothing when git is not available. Every version is read by one git process (git
    cat-file --batch), since a process per version costs tens of milliseconds each on Windows."""
    commits = git_log_path(path, root)
    if not commits:
        return
    blobs = _cat_files([f"{commit}:{path}" for commit, _ in commits], root)
    if blobs is None:  # git could not read them in one go: one process each, as a fallback
        blobs = [_show_bytes(commit, path, root) for commit, _ in commits]
    for (commit, when), data in zip(commits, blobs):
        yield commit, when, data


def _cat_files(specs: list[str], root: Path | None = None) -> list[bytes | None] | None:
    """The contents of each `<commit>:<path>` in `specs`, read with one git cat-file --batch (None for
    one that does not exist, such as a file deleted in that commit); None when git fails."""
    done = _git(["cat-file", "--batch"], root, binary=True, stdin="".join(f"{s}\n" for s in specs).encode("utf-8"))
    if done is None or done.returncode != 0:
        return None
    out, data, pos = [], done.stdout, 0
    for _ in specs:
        end = data.find(b"\n", pos)
        if end < 0:
            return None
        header = data[pos:end].split()
        pos = end + 1
        if len(header) == 3 and header[2].isdigit():
            size = int(header[2])
            out.append(data[pos:pos + size] if header[1] == b"blob" else None)
            pos += size + 1  # the content, then a newline
        else:
            out.append(None)  # "<spec> missing", or "ambiguous"
    return out
