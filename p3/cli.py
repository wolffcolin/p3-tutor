"""The `p3` command. `uv run p3 --help` (or `python -m p3 --help`) lists the commands;
`p3 COMMAND --help` lists a command's options.

    p3 snapshot   copy the tutor's config (tutor/) into configs/<name>/
    p3 bench      run a config on a topic's scenarios with claude -p, and score the run
    p3 score      score a run again (the objective checks and the model-scored ones)
    p3 report     Markdown tables of the scored runs, for EVAL.md
    p3 compare    blind side-by-side comparison of two configs' outputs, then the reveal
    p3 check      is everything in place and unchanged (CI runs this)
    p3 next       where you are on the project's map, and the one next thing to do
    p3 new-topic  a skeleton own topic in bench/own/<id>/
    p3 rehash     instructor only: rewrite p3/bench.sha256
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
from pathlib import Path

import p3
from p3 import util
from p3.util import P3Error

JOB_CHOICES = ("teach", "quiz", "grade", "tutor")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="p3", description="P3: build a tutoring agent in Claude Code, and measure what each piece of it is worth.")
    p.add_argument("--version", action="version", version=f"p3 {p3.__version__}")
    p.add_argument("--root", type=Path, help="the P3 repository (default: the nearest folder at or above this one with p3.json)")
    sub = p.add_subparsers(dest="command", metavar="COMMAND")

    sn = sub.add_parser("snapshot", help="copy the tutor's config (tutor/CLAUDE.md, PREFERENCES.md and .claude/) into configs/<name>/")
    sn.add_argument("name", help="the config's name, such as c1-skills (lowercase letters, digits and hyphens)")
    sn.add_argument("--force", action="store_true", help="replace an existing snapshot of that name")

    be = sub.add_parser("bench", help="run a config on a topic's scenarios with claude -p, then score the run")
    be.add_argument("--config", required=True, help="a snapshot under configs/, or live for tutor/ as it is now (not committed)")
    be.add_argument("--topic", default=util.SHARED_TOPIC, help=f"a topic in bench/topics/ or bench/own/ (default {util.SHARED_TOPIC})")
    be.add_argument("--repeats", type=int, default=1, metavar="N", help="run the whole bench N times, one after another (default 1)")
    be.add_argument("--quick", action="store_true", help="teach, quiz, the first grade scenario and the first two tutor probes, once")
    be.add_argument("--minutes", type=int, metavar="M", help="the lesson length to ask for (default: the topic's, 30 on the shared topic)")
    be.add_argument("--jobs", type=int, default=1, metavar="N", help="run up to N scenarios of a repeat at the same time (default 1)")
    be.add_argument("--keep", action="store_true", help="keep each scenario's working folder and print where it is")
    be.add_argument("--no-score", action="store_true", help="do not score the run (score it later with p3 score)")
    be.add_argument("--offline", action="store_true", help="score without checking the lesson's links")
    be.add_argument("--only", metavar="IDS", help="only these scenarios, comma-separated, such as teach or grade-s1,tutor-p01")

    sc = sub.add_parser("score", help="score a run (writes <run>/score.json)")
    sc.add_argument("run_dir", metavar="RUN", help="a run folder, such as bench/runs/c0-baseline/<run-id>, or a run id")
    sc.add_argument("--offline", action="store_true", help="skip the link checks")
    sc.add_argument("--no-model", action="store_true", help="skip the model-scored checks (the judge and the solvers); the deterministic checks still run")

    re_ = sub.add_parser("report", help="Markdown tables of the scored runs, for EVAL.md")
    re_.add_argument("--topic", default=util.SHARED_TOPIC, help=f"the topic (default {util.SHARED_TOPIC})")
    re_.add_argument("--configs", metavar="A,B,...", help="only these configs, in this order (default: every config with a scored run)")
    re_.add_argument("--minutes", type=int, metavar="M", help="only runs at this lesson length (default: every length, one row each)")
    re_.add_argument("--quick", action="store_true", help="report the quick runs instead of the full ones")
    re_.add_argument("--teach-only", action="store_true", help="report the runs of the teach scenario alone (p3 bench --only teach, the length study) instead of the full runs")
    re_.add_argument("--reviews", action="store_true", help="print only the table of your 1 to 5 ratings from the major reviews in reviews/ (the other options do not apply)")

    co = sub.add_parser("compare", help="blind side-by-side comparison of two configs' outputs on one job")
    co.add_argument("configs", nargs="*", metavar="CONFIG", help="the two configs to compare, such as c0-baseline final")
    co.add_argument("--job", choices=JOB_CHOICES, help="the job whose outputs to compare")
    co.add_argument("--topic", default=util.SHARED_TOPIC, help=f"the topic (default {util.SHARED_TOPIC}, where every blind comparison this project asks for is made; the test topics are reviewed openly)")
    co.add_argument("--minutes", type=int, metavar="M", help="pair only runs at this lesson length (default: the topic's, 30 on the shared topic)")
    co.add_argument("--quick", action="store_true", help="pair the quick runs instead of the full ones (for trying the tool out; p3 check counts only full-run sessions)")
    co.add_argument("--teach-only", action="store_true", help="with --job teach: pair the runs of the teach scenario alone (the length study) instead of the full runs")
    co.add_argument("--terminal", action="store_true", help="answer in the terminal; each pair is written as an HTML file to open")
    co.add_argument("--port", type=int, metavar="P", help="the local port for the comparison page (default: a free one)")
    co.add_argument("--reveal", metavar="SESSION", help="show which config won a finished session, then the cost")
    co.add_argument("--resume", metavar="SESSION", help="continue an unfinished session")
    co.add_argument("--list", action="store_true", help="list the comparison sessions")

    ch = sub.add_parser("check", help="is everything in place and unchanged (CI runs this)")
    ch.add_argument("--final", action="store_true", help="also check that everything the hand-in needs is there")

    sub.add_parser("next", help="where you are on the project's map, and the one next thing to do, with the guide page for it (it changes nothing)")

    nt = sub.add_parser("new-topic", help="write a skeleton own topic in bench/own/<id>/")
    nt.add_argument("topic_id", metavar="ID", help="the topic's id, such as statics-trusses (lowercase letters, digits and hyphens)")

    sub.add_parser("rehash", help="instructor only: rewrite p3/bench.sha256 from the fixed files")
    return p


# ---- commands ----


def cmd_snapshot(args) -> int:
    from p3 import config

    root = util.repo_root()
    data = config.snapshot(args.name, force=args.force, root=root)
    print(f"configs/{args.name}/: {len(data['files'])} config files, {data['hash']}")
    print(f"Run it with: p3 bench --config {args.name}")
    return 0


def cmd_bench(args) -> int:
    from p3 import runner

    return runner.bench(args)


def cmd_score(args) -> int:
    from p3 import score

    return score.main(args)


def cmd_report(args) -> int:
    from p3 import report

    return report.main(args)


def cmd_compare(args) -> int:
    from p3 import compare

    configs = list(args.configs or [])
    args.config_a = configs[0] if len(configs) > 0 else None
    args.config_b = configs[1] if len(configs) > 1 else None
    return compare.main(args)


def cmd_check(args) -> int:
    from p3 import check

    return check.main(args)


def cmd_next(args) -> int:
    from p3 import next as next_step

    return next_step.main(args)


def cmd_new_topic(args) -> int:
    from p3 import newtopic

    return newtopic.main(args)


def cmd_rehash(args) -> int:
    root = util.repo_root()
    hashes = util.rehash(root)
    print(f"wrote {util.HASH_FILE}: {len(hashes)} fixed files (instructor only; commit it with the change that needed it)")
    return 0


COMMANDS = {
    "snapshot": cmd_snapshot,
    "bench": cmd_bench,
    "score": cmd_score,
    "report": cmd_report,
    "compare": cmd_compare,
    "check": cmd_check,
    "next": cmd_next,
    "new-topic": cmd_new_topic,
    "rehash": cmd_rehash,
}


def _set_up_streams() -> None:
    """Print UTF-8 into a pipe or a file (Claude Code's Bash tool, `| tee`), where Python on Windows
    would otherwise write cp1252 and turn curly quotes and accents into "?", and line by line, so a
    bench running in the background shows its progress as it goes and its warnings in order; a
    console keeps its own encoding, with characters it cannot show replaced rather than crashing."""
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream.isatty():
                stream.reconfigure(errors="replace")
            else:
                stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except (AttributeError, ValueError, OSError):
            pass


def _flush() -> None:
    """Flush standard output before an error goes to standard error, so that in a pipe, where both
    land in one stream (Claude Code's Bash tool), the error comes after everything printed before it."""
    try:
        sys.stdout.flush()
    except (OSError, ValueError):
        pass


def _stop(signum, frame):
    raise KeyboardInterrupt


def _catch_stop_signals() -> dict:
    """On macOS and Linux, turn SIGTERM and SIGHUP (a closed terminal, a killed background task)
    into the same clean stop as Ctrl-C, so every claude process p3 started is killed with it.
    Returns the handlers it replaced, for _restore_signals."""
    saved = {}
    if os.name == "nt" or threading.current_thread() is not threading.main_thread():
        return saved
    for name in ("SIGTERM", "SIGHUP"):
        number = getattr(signal, name, None)
        if number is None:
            continue
        try:
            saved[number] = signal.signal(number, _stop)
        except (ValueError, OSError):
            pass
    return saved


def _restore_signals(saved: dict) -> None:
    for number, handler in saved.items():
        try:
            signal.signal(number, handler)
        except (ValueError, OSError, TypeError):
            pass


def main(argv: list[str] | None = None) -> int:
    _set_up_streams()
    args = parser().parse_args(argv)
    if not args.command:
        parser().print_help()
        return 2
    previous_root = os.environ.get(util.ROOT_ENV)
    if args.root:
        os.environ[util.ROOT_ENV] = str(Path(args.root).resolve())
    saved_signals = _catch_stop_signals()
    try:
        return int(COMMANDS[args.command](args) or 0)
    except P3Error as exc:
        _flush()
        print(f"p3 {args.command}: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        _flush()
        print("p3: stopped", file=sys.stderr)
        return 130
    except OSError as exc:
        # a full disk, a file another program holds, a path too long for Windows: say which, without a traceback
        _flush()
        where = f": {exc.filename}" if getattr(exc, "filename", None) else ""
        print(f"p3 {args.command}: {exc.strerror or exc}{where}", file=sys.stderr)
        return 1
    finally:
        _restore_signals(saved_signals)
        if args.root:
            if previous_root is None:
                os.environ.pop(util.ROOT_ENV, None)
            else:
                os.environ[util.ROOT_ENV] = previous_root
