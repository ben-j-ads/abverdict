"""Command-line interface: `abverdict plan` and `abverdict test`."""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .io import parse_arm, read_counts_csv, read_values_csv
from .planning import conversion_n_per_arm, continuous_n_per_arm, make_plan
from .report import plan_to_dict, render_plan, render_report, report_to_dict
from .verdict import analyze


def _pct(text: str) -> float:
    """Accept 0.05 or 5% for a rate."""
    text = text.strip()
    return float(text[:-1]) / 100 if text.endswith("%") else float(text)


def _split(text):
    if text is None:
        return None
    parts = [float(x) for x in text.replace(":", "/").split("/")]
    return parts


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="abverdict", description="Did your A/B test actually win?")
    p.add_argument("--version", action="version", version=f"abverdict {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    pl = sub.add_parser("plan", help="how many visitors and days does the test need?")
    pl.add_argument("--baseline", type=_pct, help="current conversion rate, e.g. 5%% or 0.05")
    pl.add_argument("--sd", type=float, help="standard deviation of a continuous metric (e.g. revenue per visitor)")
    pl.add_argument("--mde", required=True, help="smallest effect worth detecting. Conversion: relative, e.g. 10%% (use --absolute for points). Continuous: metric units")
    pl.add_argument("--absolute", action="store_true", help="treat a conversion --mde as absolute percentage points")
    pl.add_argument("--arms", type=int, default=2, help="including control (default 2)")
    pl.add_argument("--alpha", type=float, default=0.05)
    pl.add_argument("--power", type=float, default=0.8)
    pl.add_argument("--daily-traffic", type=float, help="total visitors per day across all arms")
    pl.add_argument("--json", action="store_true")

    ts = sub.add_parser("test", help="analyse results and get a verdict")
    ts.add_argument("--arm", action="append", default=[], metavar="NAME=CONV/N",
                    help="repeatable; the first is the control, e.g. --arm A=500/10000 --arm B=560/10000")
    ts.add_argument("--csv", help="counts CSV: variant,visitors,conversions[,date]; rows are summed per variant")
    ts.add_argument("--values-csv", help="values CSV: variant,value[,date]; one row per user or order")
    ts.add_argument("--control", help="control name when using a CSV (default: first variant in file)")
    ts.add_argument("--alpha", type=float, default=0.05)
    ts.add_argument("--planned-n", type=int, help="per-arm sample size you committed to (from `plan`)")
    ts.add_argument("--days", type=int, help="how long the test ran (taken from a date column if present)")
    ts.add_argument("--looks", type=int, default=1, help="how many times you've checked results, including now")
    ts.add_argument("--mde", help="smallest effect worth acting on (same units as `plan --mde`), enables NO MEANINGFUL DIFFERENCE")
    ts.add_argument("--absolute", action="store_true", help="treat a conversion --mde as absolute percentage points")
    ts.add_argument("--split", help="intended traffic split, e.g. 50/50 or 80/10/10 (default: equal)")
    ts.add_argument("--json", action="store_true")
    return p


def _cmd_plan(a) -> int:
    if (a.baseline is None) == (a.sd is None):
        raise ValueError("give exactly one of --baseline (conversion metric) or --sd (continuous metric)")
    comparisons = max(a.arms - 1, 1)
    if a.baseline is not None:
        mde = _pct(a.mde)
        n = conversion_n_per_arm(a.baseline, mde, relative=not a.absolute, alpha=a.alpha, power=a.power, comparisons=comparisons)
        kind = "conversion"
        text = f"baseline {a.baseline:.2%}, detect {'+' if not a.absolute else ''}{mde:.2%}{' points' if a.absolute else ' relative'}"
    else:
        n = continuous_n_per_arm(a.sd, float(a.mde), alpha=a.alpha, power=a.power, comparisons=comparisons)
        kind = "continuous"
        text = f"sd {a.sd:g}, detect a difference of {float(a.mde):g}"
    plan = make_plan(n, kind, a.arms, a.alpha, a.power, a.daily_traffic)
    print(json.dumps(plan_to_dict(plan), indent=2) if a.json else render_plan(plan, text))
    return 0


def _cmd_test(a) -> int:
    sources = [bool(a.arm), bool(a.csv), bool(a.values_csv)]
    if sum(sources) != 1:
        raise ValueError("give exactly one input: --arm (repeatable), --csv or --values-csv")
    days = a.days
    if a.arm:
        arms = [parse_arm(x) for x in a.arm]
    elif a.csv:
        arms, file_days = read_counts_csv(a.csv, a.control)
        days = days or file_days
    else:
        arms, file_days = read_values_csv(a.values_csv, a.control)
        days = days or file_days
    mde = None
    if a.mde is not None:
        if arms[0].conversions is None:
            mde = float(a.mde)  # metric units
        else:
            mde = _pct(a.mde) if a.absolute else _pct(a.mde) * arms[0].rate
    report = analyze(arms, alpha=a.alpha, planned_n=a.planned_n, days=days, looks=a.looks, mde=mde, split=_split(a.split))
    print(json.dumps(report_to_dict(report), indent=2) if a.json else render_report(report))
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _cmd_plan(args) if args.command == "plan" else _cmd_test(args)
    except (ValueError, OSError) as e:
        print(f"abverdict: error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
