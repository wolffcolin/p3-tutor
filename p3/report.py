"""`p3 report`: Markdown tables of the scored runs, for pasting into EVAL.md.

    p3 report [--topic t] [--configs a,b,...] [--minutes M] [--quick] [--teach-only]
    p3 report --reviews

One row per config (and lesson length, when runs at several lengths exist) with each headline number
as the mean over its scored full runs and the range in brackets, then one cost table per job. A full
run ran every scenario: runs made with --only are left out, because a job they did not run would
count as zero tokens and minutes. --teach-only shows only the runs of the teach scenario alone (the
length study) instead, and --quick only the quick runs.

After those tables, in a report of the shared topic's full runs (the runs the major reviews review)
and once any review file in reviews/ holds a rating, comes "Your ratings": the 1 to 5 ratings of the
major reviews, one row per criterion grouped by job, one column per step, and a dash where there is
no rating. A report of a test topic, of quick runs or of teach-only runs leaves it out. --reviews
prints only that table.
"""

from __future__ import annotations

from pathlib import Path

from p3 import reviews, util
from p3.claude import COST_LABEL
from p3.util import P3Error

LADDER = ("c0-baseline", "c1-skills", "c2-review", "c3-split", "final")
QUALITY = (
    ("teach_facts_correct", "teach facts", "share"),
    ("teach_misconceptions", "teach misconc.", "count"),
    ("teach_length_ratio", "length ratio", "share"),
    ("teach_dead_links", "dead links", "count"),
    ("quiz_key_agreement", "key agreement", "share"),
    ("quiz_wrong_key", "wrong keys", "count"),
    ("quiz_ambiguous", "ambiguous items", "count"),
    ("grade_verdict_agreement", "verdict agreement", "share"),
    ("grade_false_wrong", "false wrong", "share"),
    ("grade_misconception_hit", "misconc. hit", "share"),
    ("tutor_leaks", "leaks", "count"),
    ("tutor_behavior_met", "behavior met", "share"),
)
COST = (
    ("tokens_total", "tokens", "tokens"),
    ("tokens_output", "output tokens", "tokens"),
    ("minutes", "minutes", "minutes"),
    ("subagents", "subagents", "count"),
    ("cost_usd_list", "list-price $", "usd"),
)
JOBS = ("teach", "quiz", "grade", "tutor")


def config_order(names) -> list[str]:
    """The ladder order: c0-baseline, c1-skills, c2-review, c3-split, final, final-minus-*, then the rest."""

    def key(name: str):
        if name in LADDER:
            return (0, LADDER.index(name), name)
        if name.startswith("final-minus-"):
            return (1, 0, name)
        return (2, 0, name)

    return sorted(set(names), key=key)


def _fmt(value: float, kind: str) -> str:
    if kind == "share":
        return f"{value:.2f}"
    if kind == "count":
        return f"{value:.1f}".removesuffix(".0")
    if kind == "tokens":
        if value >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        if value >= 1_000:
            return f"{value / 1_000:.1f}k"
        return f"{value:.0f}"
    if kind == "minutes":
        return f"{value:.1f}"
    if kind == "usd":
        return f"{value:.2f}"
    return str(value)


def cell(values: list, kind: str, runs: int) -> str:
    """mean (min-max) over the values that exist, with n= when fewer values than runs; "-" when none."""
    present = [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not present:
        return "-"
    mean = sum(present) / len(present)
    text = _fmt(mean, kind)
    lo, hi = min(present), max(present)
    extra = []
    if len(present) > 1 and _fmt(lo, kind) != _fmt(hi, kind):
        extra.append(f"{_fmt(lo, kind)}-{_fmt(hi, kind)}")
    if len(present) < runs:
        extra.append(f"n={len(present)}")
    return f"{text} ({', '.join(extra)})" if extra else text


def table(header: list[str], rows: list[list[str]], left: int = 1) -> str:
    """A Markdown table: the first `left` columns aligned left, the others right."""
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" if i < left else "---:" for i in range(len(header))) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def ratings_table(root: Path | None = None) -> str | None:
    """The "Your ratings" section as Markdown, or None while no review file holds a rating."""
    found = reviews.all_ratings(root)
    if not any(found.values()):
        return None
    rows = []
    for job, criteria in reviews.CRITERIA.items():
        for name in criteria:
            rows.append([job, name] + [str(found.get(step, {}).get((job, name), "-")) for step in reviews.STEPS])
    out = [
        "## Your ratings", "",
        "Your ratings from 1 to 5 in the major reviews (reviews/<step>.md), which review full runs on the shared topic; "
        "a dash means no rating there yet, one that p3 check does not accept, or a job that step does not review (Tutor in c2-review; Quiz, Feedback and Tutor in c3-split).", "",
        table(["job", "criterion", *reviews.STEPS], rows, left=2), "",
    ]  # fmt: skip
    return "\n".join(out)


def groups(topic_id: str, configs: list[str] | None, minutes: int | None, quick: bool, teach_only: bool = False) -> list[tuple[str, int, list]]:
    """(config, minutes, [RunRecord]) of the scored runs of one kind (full runs, or teach-only runs
    with `teach_only`), in ladder order then by minutes."""
    found: dict[tuple[str, int], list] = {}
    kind = util.TEACH_ONLY if teach_only else util.FULL
    for rec in util.list_runs(topic=topic_id, scored=True, quick=quick, minutes=minutes, kind=kind):
        name = rec.run.get("config")
        if configs and name not in configs:
            continue
        found.setdefault((name, int(rec.run.get("minutes") or 0)), []).append(rec)
    order = configs or config_order(name for name, _ in found)
    out = []
    for name in order:
        for (cname, mins), recs in sorted(found.items(), key=lambda kv: kv[0][1]):
            if cname == name:
                out.append((name, mins, recs))
    return out


def report_text(
    topic_id: str = util.SHARED_TOPIC, configs: list[str] | None = None, minutes: int | None = None, quick: bool = False, teach_only: bool = False,
    ratings: bool = True,
) -> str:
    """The report as Markdown, ending with "Your ratings" when `ratings`, the report is of the shared
    topic's full runs, and any review holds one."""
    rows_by = groups(topic_id, configs, minutes, quick, teach_only)
    runs_word = "teach-only runs" if teach_only else "full runs"
    what = f"quick {runs_word}" if quick else (runs_word if teach_only else "full runs (quick runs and --only runs left out)")
    if not rows_by:
        hint = ""
        quick_others = sorted({name for name, _, _ in groups(topic_id, configs, minutes, not quick, teach_only)})
        teach_others = sorted({name for name, _, _ in groups(topic_id, configs, minutes, quick, not teach_only)})
        if quick_others and not quick:
            hint = f"; only quick runs are scored so far ({', '.join(quick_others)}): add --quick to see them"
        elif teach_others and not teach_only:
            hint = f"; only teach-only runs are scored so far ({', '.join(teach_others)}): add --teach-only to see them"
        else:
            kind = util.TEACH_ONLY if teach_only else util.FULL
            unscored = [r for r in util.list_runs(topic=topic_id, scored=False, quick=quick, minutes=minutes, kind=kind) if not configs or r.config in configs]
            if unscored:
                one = len(unscored) == 1
                noun = runs_word[:-1] if one else runs_word
                hint = f"; {len(unscored)} {noun} {'is' if one else 'are'} not scored yet: score {'it' if one else 'each'} with p3 score {util.posix(unscored[-1].dir, util.repo_root())}"
        raise P3Error(f"no scored {what} on topic {topic_id}" + (f" for {', '.join(configs)}" if configs else "") + (hint or "; run p3 bench first"))
    several_lengths = len({m for _, m, _ in rows_by}) > 1
    out = [f"## Results on {topic_id}", "", f"Scored {what}; each cell is the mean over the runs, with the range in brackets.", ""]
    head = ["config"] + (["minutes"] if several_lengths else []) + ["runs"]
    columns = [q for q in QUALITY if q[0].startswith("teach_")] if teach_only else list(QUALITY)
    quality_rows = []
    for name, mins, recs in rows_by:
        summaries = [r.score.get("summary") or {} for r in recs]
        row = [f"`{name}`"] + ([str(mins)] if several_lengths else []) + [str(len(recs))]
        row += [cell([s.get(key) for s in summaries], kind, len(recs)) for key, _, kind in columns]
        quality_rows.append(row)
    out += ["### Quality", "", table(head + [label for _, label, _ in columns], quality_rows), ""]
    out += [
        "Teach facts, key agreement, verdict agreement, false wrong, misconception hit and behavior met are shares (0 to 1); "
        "misconceptions, dead links, wrong keys, ambiguous items and leaks are counts per run.",
        "A dash means no run could be scored on that check, and n= says how many of the runs could.",
        "A job that failed counts against the config: no lesson scores 0 teach facts, no quiz and key 0 key agreement, a missing grades file disagrees on every item, "
        "and a tutor scenario with no reply is not met; leaks need a reply to check, so such a scenario is left out of them.",
        "The length ratio is a rough reading-time estimate (visible words / 150) over the minutes requested; 0.6 to 1.5 counts as on length.",
        "",
    ]
    for job in JOBS + ("total",):
        cost_rows = []
        for name, mins, recs in rows_by:
            costs = [((r.score.get("summary") or {}).get("cost") or {}).get(job) or {} for r in recs]
            if not any(c.get("scenarios") for c in costs):
                continue
            row = [f"`{name}`"] + ([str(mins)] if several_lengths else []) + [str(len(recs))]
            row += [cell([c.get(key) for c in costs], kind, len(recs)) for key, _, kind in COST]
            cost_rows.append(row)
        if cost_rows:
            title = "Cost: all jobs" if job == "total" else f"Cost: {job}"
            out += [f"### {title}", "", table(head + [label for _, label, _ in COST], cost_rows), ""]
    out.append(f"Costs are per run, summed over the job's scenarios; list-price $ is the {COST_LABEL}.")
    yours = ratings_table() if ratings and topic_id == util.SHARED_TOPIC and not quick and not teach_only else None
    if yours:
        out += ["", yours.rstrip("\n")]
    return "\n".join(out) + "\n"


def main(args) -> int:
    """The p3 report command."""
    if getattr(args, "reviews", False):
        yours = ratings_table()
        if yours is None:
            raise P3Error(
                "no ratings in reviews/ yet: each criterion of a major review (reviews/<step>.md) holds a line Rating: N, "
                f"N a whole number from {reviews.RATING_MIN} to {reviews.RATING_MAX}; p3 check says what each review still needs"
            )
        print(yours, end="")
        return 0
    configs = [c.strip() for c in args.configs.split(",") if c.strip()] if args.configs else None
    print(report_text(args.topic, configs, args.minutes, args.quick, bool(getattr(args, "teach_only", False))), end="")
    return 0
