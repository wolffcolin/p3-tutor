"""`p3 bench`: run a config's tutor on a topic's scenarios, headless, and save everything it did.

    p3 bench --config <name>|live [--topic <id>] [--repeats N] [--quick] [--minutes M] [--jobs N]
             [--keep] [--no-score] [--offline] [--only <scenario-id,...>]

- The scenarios come from bench/scenarios.json: teach, quiz, one grade scenario per submission and
  one tutor scenario per probe of the topic. --quick runs teach, quiz, the first grade scenario and
  the first two tutor probes, once.
- Each scenario runs in its own fresh folder outside the repo (so the tutor cannot reach bench/),
  holding the config's files, the topic's workspace/ and bench/FORMATS.md as FORMATS.md. Every file
  the tutor writes or changes is copied to bench/runs/<config>/<run-id>/<scenario-id>/outputs/.
- Each scenario folder in the run also gets trace.jsonl.gz (the whole stream), result.json (the last
  result line) and stderr.txt (when claude wrote anything there); run.json records the config, the
  topic, the versions, and per scenario the time, turns, tokens, list-price cost, web use and subagents.
- The run is scored (p3 score) unless --no-score.
- A scenario that fails for a reason outside the tutor (a usage limit, a sign-in problem, an API
  outage; claude.infra_reason) stops the bench: the scenarios still running are killed, the repeat
  is moved to bench/runs/_live/_aborted/ without a run.json (it measures nothing), and the later
  repeats do not run. A failure like that while scoring leaves the run unscored.
- Before the first repeat it warns about a CLAUDE.md above the temporary folder (Claude Code would
  read it in every scenario), and on Windows about run folders too long for the path limit, and it
  removes scenario folders more than a day old that an earlier bench left behind.

Config "live" runs tutor/ as it is now, into bench/runs/_live/ (not committed; p3 check and p3 compare
use snapshots only).
"""

from __future__ import annotations

import gzip
import hashlib
import os
import platform
import re
import shutil
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import p3
from p3 import claude, config, topic, util
from p3.claude import COST_LABEL
from p3.util import P3Error

SCENARIOS_FILE = "bench/scenarios.json"
QUICK_PER = {"submission": 1, "probe": 2}
FIELD_RE = re.compile(r"\{([a-z_]+)\}")
INFRA_STATUS = "infra_error"  # a scenario stopped by a usage limit, sign-in or API problem; never saved in a run
ABORTED_DIR = "bench/runs/_live/_aborted"  # where a repeat stopped that way is set aside (git ignores _live/)
STALE_AFTER_S = 24 * 3600
MEMORY_FILES = ("CLAUDE.md", "CLAUDE.local.md")
WINDOWS_PATH_LIMIT = 259
OUTPUT_PATH_ALLOWANCE = 100  # a scenario folder, outputs/ and a long lesson name, beyond the run folder


@dataclass
class Scenario:
    """One expanded scenario: its id, job, prompt, limits, and the submission or probe it is for."""

    id: str
    job: str
    prompt: str
    timeout_s: int
    max_turns: int
    entry: str
    per: str | None = None
    subject: str | None = None


# ---- scenarios ----


def load_scenarios(root: Path | None = None) -> list[dict]:
    """The scenario templates of bench/scenarios.json. Raises P3Error when it is missing or malformed."""
    root = Path(root) if root else util.repo_root()
    data = util.read_json(root / SCENARIOS_FILE)
    templates = data.get("scenarios") if isinstance(data, dict) else None
    if not isinstance(templates, list) or not templates:
        raise P3Error(f"{SCENARIOS_FILE} has no scenarios list")
    for t in templates:
        if not isinstance(t, dict) or not all(k in t for k in ("id", "job", "prompt")):
            raise P3Error(f"{SCENARIOS_FILE}: every scenario needs an id, a job and a prompt")
        if t["job"] not in config.JOBS:
            raise P3Error(f"{SCENARIOS_FILE}: scenario {t['id']} has job {t['job']!r}; jobs are {', '.join(config.JOBS)}")
        if t.get("per") not in (None, "submission", "probe"):
            raise P3Error(f"{SCENARIOS_FILE}: scenario {t['id']} has per {t.get('per')!r}; use submission or probe")
    return templates


def fill(template: str, values: dict[str, str], where: str) -> str:
    """Replace each {field} in a template with its value; an unknown field is a P3Error."""

    def sub(match: re.Match) -> str:
        name = match.group(1)
        if name not in values:
            raise P3Error(f"{SCENARIOS_FILE}: {where} uses {{{name}}}, which is not a known field ({', '.join(sorted(values))})")
        return str(values[name])

    return FIELD_RE.sub(sub, template)


def expand(templates: list[dict], tp: topic.Topic, entries: dict[str, str], minutes: int) -> list[Scenario]:
    """Every scenario for a topic: each template once, or once per submission or per probe."""
    base = {
        "topic": tp.id,
        "topic_title": tp.title,
        "learner_summary": tp.learner_summary,
        "minutes": str(minutes),
        "teach_objective_id": tp.teach_objective,
        "teach_objective_text": tp.objective_text(tp.teach_objective),
        "quiz_objective_id": tp.quiz_objective,
        "quiz_objective_text": tp.objective_text(tp.quiz_objective),
        "graded_quiz": tp.graded_quiz,
    }
    out: list[Scenario] = []
    for t in templates:
        job = t["job"]
        values = {**base, "entry": entries.get(job, config.FALLBACK_ENTRY)}
        timeout_s = int(t.get("timeout_s") or 900)
        max_turns = int(t.get("max_turns") or 80)
        if t.get("per") == "submission":
            subjects = [(s, {"submission": s}) for s in tp.submissions]
        elif t.get("per") == "probe":
            subjects = [(p["id"], {"probe": p["id"], "probe_message": str(p.get("message") or "")}) for p in tp.probes]
        else:
            subjects = [(None, {})]
        for subject, extra in subjects:
            vals = {**values, **extra}
            sid = fill(str(t["id"]), vals, f"scenario {t['id']}")
            prompt = fill(str(t["prompt"]), vals, f"scenario {t['id']}")
            out.append(Scenario(sid, job, prompt, timeout_s, max_turns, values["entry"], t.get("per"), subject))
    ids = [s.id for s in out]
    if len(set(ids)) != len(ids):
        raise P3Error(f"{SCENARIOS_FILE} expands to the same scenario id twice: {ids}")
    return out


def quick_subset(scenarios: list[Scenario]) -> list[Scenario]:
    """The --quick subset: every scenario that is not per-something, the first grade scenario and
    the first two tutor probes."""
    seen: dict[str, int] = {}
    keep = []
    for s in scenarios:
        if s.per is None:
            keep.append(s)
            continue
        seen[s.per] = seen.get(s.per, 0) + 1
        if seen[s.per] <= QUICK_PER.get(s.per, 1):
            keep.append(s)
    return keep


def select(scenarios: list[Scenario], quick: bool, only: str | None) -> list[Scenario]:
    """Apply --quick and then --only (comma-separated scenario ids)."""
    chosen = quick_subset(scenarios) if quick else list(scenarios)
    if only:
        wanted = [w.strip() for w in only.split(",") if w.strip()]
        known = {s.id for s in scenarios}
        unknown = [w for w in wanted if w not in known]
        if unknown:
            raise P3Error(f"--only: no scenario {', '.join(unknown)}; the scenarios are {', '.join(s.id for s in scenarios)}")
        chosen = [s for s in chosen if s.id in wanted]
        if not chosen:
            raise P3Error("--only with --quick leaves no scenario; drop --quick to run any scenario by id")
    return chosen


# ---- one scenario ----


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stream_usage(events: list[dict]) -> dict:
    """Token totals from the assistant messages of a stream, for a scenario that ended without a
    result line (each message id counted once)."""
    tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    seen = set()
    for event in events:
        if event.get("type") != "assistant" or not isinstance(event.get("message"), dict):
            continue
        message = event["message"]
        mid = message.get("id")
        if mid in seen:
            continue
        if mid:
            seen.add(mid)
        usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
        tokens["input"] += int(usage.get("input_tokens") or 0)
        tokens["output"] += int(usage.get("output_tokens") or 0)
        tokens["cache_read"] += int(usage.get("cache_read_input_tokens") or 0)
        tokens["cache_write"] += int(usage.get("cache_creation_input_tokens") or 0)
    return tokens


def run_scenario(sc: Scenario, cfg: config.Config, tp: topic.Topic, formats: Path, run_dir: Path, claude_cmd: list[str], keep: bool) -> dict:
    """Run one scenario in a fresh folder and save its trace, result, stderr and outputs under
    run_dir/<scenario id>/; returns its run.json scenario entry."""
    out_dir = run_dir / sc.id
    out_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="p3-"))
    try:
        util.copy_files(cfg.folder, work, cfg.files)
        util.copy_files(tp.workspace, work, util.list_files(tp.workspace))
        shutil.copyfile(formats, work / "FORMATS.md")
        before = {rel: _digest(work / rel) for rel in util.list_files(work)}
        cmd = claude.bench_command(claude_cmd, sc.prompt, sc.max_turns, cfg.model, claude.bench_tools(cfg.allowed_tools))
        proc = claude.run_process(cmd, work, claude.child_env(), sc.timeout_s)
        outputs, changed = [], []
        after = util.list_files(work)
        for rel in after:
            if (work / rel).is_symlink():
                continue  # a link could pull in a file from anywhere on this computer
            if rel not in before:
                outputs.append(rel)
            elif _digest(work / rel) != before[rel]:
                outputs.append(rel)
                changed.append(rel)
        deleted = sorted(set(before) - set(after))
        copy_errors = []
        for rel in outputs:
            # one file at a time, so a file that cannot be copied (a path too long for Windows, a full
            # disk, a file a virus scanner holds) is recorded and the rest of the scenario's work is kept
            try:
                util.copy_files(work, out_dir / "outputs", [rel])
            except OSError as exc:
                copy_errors.append({"path": rel, "error": f"{exc.strerror or exc}"})
                print(f"  warning: {sc.id}: could not copy {rel} into the run ({exc.strerror or exc})", file=sys.stderr)
    finally:
        if keep:
            print(f"  kept the folder of {sc.id}: {work}")  # a later p3 bench removes it after a day
        else:
            util.remove_tree(work)
    stdout = proc.stdout.decode("utf-8", errors="replace")
    with gzip.GzipFile(out_dir / "trace.jsonl.gz", "wb", mtime=0) as gz:
        gz.write(stdout.replace("\r\n", "\n").encode("utf-8"))
    stderr = proc.stderr.decode("utf-8", errors="replace").replace("\r\n", "\n")
    if stderr.strip():
        util.write_text(out_dir / "stderr.txt", stderr)
    events = claude.stream_events(stdout)
    result = claude.last_result(events)
    infra = None if proc.timed_out else claude.infra_reason(result, stderr)
    if proc.timed_out:
        status = "timeout"
    elif infra:
        status = INFRA_STATUS
    elif result is not None and not result.get("is_error"):
        status = "ok"
    else:
        status = "error"
    if result is None:
        result_doc = {"type": "result", "is_error": True, "subtype": "timeout" if proc.timed_out else "no_result"}
    else:
        result_doc = result
    util.write_json(out_dir / "result.json", result_doc)
    tokens, cost, models = claude.usage_totals(result)
    estimated = False
    if result is None:
        tokens = _stream_usage(events)
        estimated = any(tokens.values())
    stats = claude.stream_stats(events, result)
    denials = result.get("permission_denials") if isinstance(result, dict) else None
    denied = [str(d.get("tool_name") or "?") if isinstance(d, dict) else str(d) for d in denials] if isinstance(denials, list) else []
    entry = {
        "id": sc.id,
        "job": sc.job,
        "entry": sc.entry,
        "status": status,
        "duration_ms": int(round(proc.seconds * 1000)),
        "num_turns": result.get("num_turns") if isinstance(result, dict) and isinstance(result.get("num_turns"), int) else None,
        "tokens": tokens,
        "cost_usd_list": cost,
        "web_searches": stats.web_searches,
        "web_fetches": stats.web_fetches,
        "subagents": stats.subagents,
        "permission_denials": denied,
        "outputs": outputs,
        "changed": changed,
        "deleted": deleted,
        "models": models,
        "search_queries": stats.search_queries,
        "fetch_urls": stats.fetch_urls,
        "exit_code": proc.returncode,
    }
    if sc.subject is not None:
        entry[sc.per] = sc.subject
    if estimated:
        entry["tokens_estimated"] = True
    version = claude.init_version(events)
    if version:
        entry["claude_version"] = version
    if copy_errors:
        entry["copy_errors"] = copy_errors
    if infra:
        entry["infra_reason"] = infra
    return entry


# ---- the command ----


def _run_id(topic_id: str, minutes: int, repeat: int, config_name: str, root: Path) -> tuple[str, Path]:
    while True:
        run_id = f"{util.stamp()}-{topic_id}-m{minutes}-r{repeat}"
        run_dir = util.runs_dir(config_name, root) / run_id
        if not run_dir.exists():
            return run_id, run_dir
        time.sleep(1)


def fmt_tokens(n: int | float | None) -> str:
    """1234 -> 1.2k, 1234567 -> 1.23M."""
    if n is None:
        return "-"
    n = float(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return f"{int(n)}"


def fmt_cost(c: float | None) -> str:
    return "-" if c is None else f"${c:.2f}"


def summary_table(run: dict) -> str:
    """A plain-text table of a run's scenarios: status, minutes, turns, tokens, output tokens,
    subagents and list-price cost, with a total line."""
    rows = [("scenario", "status", "minutes", "turns", "tokens", "output", "subagents", "list-price")]
    tot = {"ms": 0, "turns": 0, "tokens": 0, "output": 0, "sub": 0, "cost": 0.0}
    any_cost = False
    for s in run.get("scenarios", []):
        tk = s.get("tokens") or {}
        total = sum(int(v or 0) for v in tk.values())
        sub = int((s.get("subagents") or {}).get("spawned") or 0)
        tot["ms"] += int(s.get("duration_ms") or 0)
        tot["turns"] += int(s.get("num_turns") or 0)
        tot["tokens"] += total
        tot["output"] += int(tk.get("output") or 0)
        tot["sub"] += sub
        if s.get("cost_usd_list") is not None:
            tot["cost"] += s["cost_usd_list"]
            any_cost = True
        rows.append((
            s["id"], s["status"], f"{(s.get('duration_ms') or 0) / 60000:.1f}", str(s.get("num_turns") if s.get("num_turns") is not None else "-"),
            fmt_tokens(total) + ("~" if s.get("tokens_estimated") else ""), fmt_tokens(tk.get("output")), str(sub), fmt_cost(s.get("cost_usd_list")),
        ))  # fmt: skip
    rows.append(("total", "", f"{tot['ms'] / 60000:.1f}", str(tot["turns"]), fmt_tokens(tot["tokens"]), fmt_tokens(tot["output"]), str(tot["sub"]), fmt_cost(tot["cost"] if any_cost else None)))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    lines = ["  ".join(c.ljust(w) if i < 2 else c.rjust(w) for i, (c, w) in enumerate(zip(row, widths))).rstrip() for row in rows]
    lines.insert(1, "  ".join("-" * w for w in widths))
    lines.insert(-1, "  ".join("-" * w for w in widths))
    return "\n".join(lines) + f"\n(list-price: the {COST_LABEL}; ~ marks tokens counted from an unfinished trace)"


def run_repeat(
    scenarios: list[Scenario], cfg: config.Config, tp: topic.Topic, formats: Path, run_dir: Path,
    claude_cmd: list[str], keep: bool, jobs: int,
) -> list[dict]:
    """Run the scenarios of one repeat, up to `jobs` at a time, printing a line as each starts and
    ends; returns their run.json entries in scenario order. On Ctrl-C or an error the claude
    processes still running are killed and no new scenario starts. The first scenario that fails
    for a reason outside the tutor (claude.infra_reason) stops the repeat the same way, with a
    claude.InfraError naming it."""
    lock = threading.Lock()
    done = [0]
    infra: list[claude.InfraError] = []

    def one(sc: Scenario) -> dict:
        with lock:
            if infra or claude.stopping():
                raise claude.Stopped(f"{sc.id} was not started")
            print(f"  start  {sc.id}")
        entry = run_scenario(sc, cfg, tp, formats, run_dir, claude_cmd, keep)
        with lock:
            done[0] += 1
            tokens = fmt_tokens(sum(int(v or 0) for v in entry["tokens"].values()))
            n_turns, n_files = entry["num_turns"], len(entry["outputs"])
            turns = "- turns" if n_turns is None else f"{n_turns} turn{'s' if n_turns != 1 else ''}"
            files = f"{n_files} file{'s' if n_files != 1 else ''}"
            print(f"  [{done[0]}/{len(scenarios)}] {sc.id}: {entry['status']}, {entry['duration_ms'] / 60000:.1f} min, {turns}, {tokens} tokens, {files}")
            if entry["status"] == INFRA_STATUS and not infra:
                infra.append(claude.InfraError(entry.get("infra_reason") or "an error outside the tutor", f"scenario {sc.id}"))
        if infra:
            claude.kill_all()  # every other scenario would fail the same way
            raise infra[0]
        return entry

    pool = ThreadPoolExecutor(max_workers=jobs)
    try:
        futures = [pool.submit(one, sc) for sc in scenarios]
        return [f.result() for f in futures]
    except BaseException as exc:
        pool.shutdown(wait=False, cancel_futures=True)
        claude.kill_all()
        if infra and not isinstance(exc, KeyboardInterrupt):
            raise infra[0] from None
        raise
    finally:
        pool.shutdown(wait=True)


def clean_stale_folders(now: float | None = None) -> int:
    """Delete the scenario folders an earlier p3 bench left in the temporary folder more than a day
    ago (a p3-* folder holding FORMATS.md, as every scenario folder does, or an empty p3-score-*
    folder), such as those of a bench that was killed, or kept with --keep; returns how many."""
    base = Path(tempfile.gettempdir())
    now = time.time() if now is None else now
    removed = 0
    try:
        entries = list(base.iterdir())
    except OSError:
        return 0
    for folder in entries:
        try:
            if not folder.name.startswith("p3-") or folder.is_symlink() or not folder.is_dir():
                continue
            if now - folder.stat().st_mtime < STALE_AFTER_S:
                continue
            if (folder / "FORMATS.md").is_file() or (folder.name.startswith("p3-score-") and not any(folder.iterdir())):
                util.remove_tree(folder)
                removed += 1
        except OSError:
            continue
    return removed


def ancestor_memory(folder: Path) -> list[str]:
    """The CLAUDE.md and CLAUDE.local.md files in `folder` and every folder above it. Claude Code reads
    those of every folder above the one it starts in, so one above the temporary folder reaches every
    scenario (on Windows the temporary folder is inside your home folder)."""
    found = []
    try:
        folder = Path(folder).resolve()
    except OSError:
        return found
    for parent in (folder, *folder.parents):
        for name in MEMORY_FILES:
            try:
                if (parent / name).is_file():
                    found.append(str(parent / name))
            except OSError:
                continue
    return found


def set_aside(run_dir: Path, config_name: str, root: Path) -> Path:
    """Move a repeat stopped by a failure outside the tutor to bench/runs/_live/_aborted/<config>/, which
    git ignores, so it is never committed or counted; returns where it is now."""
    dest = root / ABORTED_DIR / config_name / run_dir.name
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(run_dir), str(dest))
    except OSError:
        return run_dir
    return dest


def long_path_warning(run_dir: Path) -> str | None:
    """On Windows: what to do when a run folder is so long that a scenario's files may pass the
    260-character path limit (and fail to copy, or to commit); None when it is short enough."""
    length = len(str(run_dir))
    if length + OUTPUT_PATH_ALLOWANCE <= WINDOWS_PATH_LIMIT:
        return None
    return (
        f"the run folders here are {length} characters long, so a scenario's files may pass Windows' {WINDOWS_PATH_LIMIT + 1}-character "
        "path limit and fail to copy or to commit; clone the repo to a shorter path (such as C:\\work\\p3-tutor) and run `git config core.longpaths true`"
    )


def _not_run(k: int, repeats: int) -> str:
    """'repeat 3' or 'repeats 2 to 3': the repeats after repeat k that did not run ('' when none)."""
    if k >= repeats:
        return ""
    return f"repeat {repeats}" if k + 1 == repeats else f"repeats {k + 1} to {repeats}"


def _version_number(text: str | None) -> str | None:
    match = re.search(r"\d+(?:\.\d+)+", text or "")
    return match.group(0) if match else None


def bench(args) -> int:
    """The p3 bench command (args: the argparse Namespace from p3.cli)."""
    root = util.repo_root()
    claude.reset_stop()
    cfg = config.resolve(args.config, root)
    folder, kind = topic.topic_dir(args.topic, root)
    check = topic.validate(folder, kind)
    rel_topic = util.posix(folder, root)
    if check.errors:
        raise P3Error(f"{rel_topic}/ is not a valid topic:\n  " + "\n  ".join(check.errors))
    if check.todos:
        raise P3Error(f"{rel_topic}/ still has TODO markers; fill them in first:\n  " + "\n  ".join(check.todos))
    if kind == topic.OWN and not util.path_clean_and_tracked(rel_topic, root):
        problem = util.git_problem(root)
        if problem:
            raise P3Error(
                f"{rel_topic}/ is a test topic, and the bench runs one only when git shows it committed and unchanged, "
                f"so its items are on record before any result; but {problem}."
            )
        raise P3Error(
            f"{rel_topic}/ must be committed and unchanged before it is run, so its items are on record before any result. "
            f"Commit it (git add {rel_topic} and git commit), check that `git status` shows nothing under it, and run the bench again."
        )
    tp = topic.load_folder(folder, kind)
    minutes = args.minutes if args.minutes is not None else tp.minutes
    if minutes <= 0:
        raise P3Error("--minutes must be a positive number of minutes")
    repeats = 1 if args.quick else max(1, int(args.repeats or 1))
    jobs = max(1, int(args.jobs or 1))
    formats = root / "bench" / "FORMATS.md"
    if not formats.is_file():
        raise P3Error("bench/FORMATS.md is missing")
    scenarios = select(expand(load_scenarios(root), tp, cfg.entries, minutes), args.quick, args.only)
    claude_cmd = claude.claude_command()
    version, problem = claude.version_check(claude_cmd)
    if version is None:
        raise P3Error(
            f"`claude --version` did not answer, so nothing was run. The command was {claude_cmd!r}, and it said: {problem}. "
            f"Check that Claude Code is installed and signed in (run claude once in a terminal), or set {claude.CLAUDE_ENV} to the full path "
            "of the claude program (a path with spaces needs no quotes)."
        )
    claude.child_env()  # says now, not mid-run, when an API key is set and will be left out
    topic_hash = tp.hash()
    topic_commit = util.rev_parse_head(root)
    memory = ancestor_memory(Path(tempfile.gettempdir()))
    print(f"p3 bench: config {cfg.name} ({cfg.hash[:19]}), topic {tp.id}, {minutes}-minute lesson, {len(scenarios)} scenarios x {repeats} repeat{'s' if repeats != 1 else ''}, model {cfg.model}")
    print(f"  claude {version}; each scenario is a claude -p session on your Claude subscription")
    if args.quick and (args.repeats or 1) > 1:
        print("  --quick runs once; --repeats is ignored")
    if cfg.live:
        print("  config live: results go to bench/runs/_live/, which is not committed; snapshot the tutor to keep a run")
    for path in memory:
        print(
            f"  warning: {path} sits in a folder above the scenario folders, so Claude Code reads it in every scenario and it shapes your results; "
            "move it or rename it before you make runs you will commit (run.json records it as ancestor_memory)",
            file=sys.stderr,
        )
    if clean_stale_folders():
        print("  removed scenario folders older than a day that an earlier p3 bench left in the temporary folder")
    if os.name == "nt":
        warning = long_path_warning(util.runs_dir(cfg.name, root) / f"{util.stamp()}-{tp.id}-m{minutes}-r{repeats}")
        if warning:
            print(f"  warning: {warning}", file=sys.stderr)
    run_dirs = []
    for k in range(1, repeats + 1):
        run_id, run_dir = _run_id(tp.id, minutes, k, cfg.name, root)
        run_dir.mkdir(parents=True)
        print(f"\nrepeat {k} of {repeats}: {util.posix(run_dir, root)}")
        record = {
            "run_id": run_id, "config": cfg.name, "config_hash": cfg.hash, "topic": tp.id, "topic_hash": topic_hash,
            "topic_commit": topic_commit, "repeat": k, "minutes": minutes, "quick": bool(args.quick),
            "started_at": util.iso_utc(), "finished_at": None, "claude_version": version, "p3_version": p3.__version__,
            "platform": platform.platform(), "model": cfg.model, "allowed_tools": claude.bench_tools(cfg.allowed_tools),
            "entries": cfg.entries, "only": [s.id for s in scenarios] if args.only else None,
            "ancestor_memory": memory, "scenarios": [],
        }  # fmt: skip
        try:
            record["scenarios"] = run_repeat(scenarios, cfg, tp, formats, run_dir, claude_cmd, args.keep, jobs)
        except claude.InfraError as exc:
            aside = set_aside(run_dir, cfg.name, root)
            lines = [
                f"{exc}.",
                f"Nothing in repeat {k} measures your tutor, so it was not saved as a run: its files are set aside in {util.posix(aside, root)}, which git ignores.",
            ]
            if _not_run(k, repeats):
                lines.append(f"{_not_run(k, repeats).capitalize()} did not run.")
            if run_dirs:
                lines.append("The repeats before it are complete and kept: " + ", ".join(util.posix(d, root) for d in run_dirs) + ".")
            lines.append("Wait until Claude works again (for a usage limit, /usage in Claude Code shows when it resets; for a sign-in problem, run claude once and sign in), then run the bench again.")
            raise P3Error("\n".join(lines)) from None
        except BaseException:
            print(f"\nStopped. {util.posix(run_dir, root)} is incomplete (no run.json); delete it.", file=sys.stderr)
            raise
        record["finished_at"] = util.iso_utc()
        versions = sorted({s["claude_version"] for s in record["scenarios"] if s.get("claude_version")})
        if versions:
            record["claude_versions"] = versions
            other = [v for v in versions if _version_number(v) != _version_number(version)]
            if other:
                print(f"  warning: Claude Code changed during this run: claude --version said {version}, and scenarios ran {', '.join(versions)}", file=sys.stderr)
        util.write_json(run_dir / "run.json", record)
        run_dirs.append(run_dir)
        print()
        print(summary_table(record))
        if not args.no_score:
            from p3 import score

            print("\nscoring...")
            try:
                result = score.score_run(run_dir, offline=args.offline)
            except (KeyboardInterrupt, claude.InfraError):
                rel = util.posix(run_dir, root)
                later = f" {_not_run(k, repeats).capitalize()} did not run." if _not_run(k, repeats) else ""
                print(f"\n{rel} has its run.json but is not scored.{later} Score it with: p3 score {rel}", file=sys.stderr)
                raise
            print(score.summary_text(result))
    if len(run_dirs) > 1:
        print("\nruns:\n  " + "\n  ".join(util.posix(d, root) for d in run_dirs))
    if args.no_score:
        print(f"\nnot scored; score with: p3 score {util.posix(run_dirs[-1], root)}")
    return 0
