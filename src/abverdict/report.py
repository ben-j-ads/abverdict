"""Render reports and plans as plain text or JSON-ready dicts."""
from __future__ import annotations

from dataclasses import asdict

from .planning import Plan
from .verdict import Report, fmt_p


def _fmt(report: Report, x: float) -> str:
    return f"{x * 100:+.2f} pts" if report.metric == "conversion" else f"{x:+,.3f}"


def render_report(r: Report) -> str:
    lines = [r.headline, ""]
    for a in r.arms:
        if r.metric == "conversion":
            lines.append(f"  {a.name:<14} {a.conversions:>9,} / {a.n:<10,} = {a.rate:.2%}")
        else:
            lines.append(f"  {a.name:<14} n={a.n:<9,} mean={a.mean:,.3f}  sd={a.sd:,.3f}")
    lines.append("")
    for c in r.comparisons:
        rel = f" ({c.relative_effect:+.1%} relative)" if c.relative_effect is not None else ""
        lines.append(f"{c.variant} vs {c.control}: {c.verdict}")
        lines.append(f"  effect {_fmt(r, c.effect)}{rel}, {r.ci_level:.1%} CI [{_fmt(r, c.ci[0])}, {_fmt(r, c.ci[1])}]")
        lines.append(f"  p={c.p_value:.3g} (adjusted {c.p_adjusted:.3g}, threshold {r.alpha_effective:.3g})")
        lines.extend(f"  - {reason}" for reason in c.reasons)
        lines.append("")
    lines.append(f"Traffic split check (SRM): p={fmt_p(r.srm_p)}" + ("  <-- PROBLEM" if r.overall == "INVALID" else "  ok"))
    if r.warnings:
        lines.append("")
        lines.append("Heads up:")
        lines.extend(f"  ! {w}" for w in r.warnings)
    return "\n".join(lines)


def render_plan(p: Plan, baseline_text: str) -> str:
    lines = [
        f"Plan ({p.metric}): {baseline_text}",
        f"  Visitors needed per arm: {p.n_per_arm:,}",
        f"  Arms: {p.arms}  ->  total {p.total:,}",
        f"  alpha {p.alpha} ({p.alpha_per_comparison:.4g} per comparison), power {p.power:.0%}",
    ]
    if p.days is not None:
        lines.append(f"  Run for {p.days} days (needs {p.raw_days}; rounded up to whole weeks, minimum 7)")
    lines += ["", f"Pre-register this: pass --planned-n {p.n_per_arm} when you analyse, and don't stop early."]
    return "\n".join(lines)


def build_checks(r: Report) -> list:
    """The guards, as pass / fail / note rows (used by the web UI and --json)."""
    from .verdict import EARLY_FRACTION, MIN_DAYS, SRM_THRESHOLD
    checks = []
    bad = r.srm_p < SRM_THRESHOLD
    checks.append({"name": "traffic split", "status": "fail" if bad else "pass",
                   "detail": f"SRM p={fmt_p(r.srm_p)}. " + ("The split does not match the plan, so the test is broken." if bad else "The split matches the plan.")})
    if r.planned_n is None:
        checks.append({"name": "planned sample", "status": "note", "detail": "No planned sample given, so stopping early can't be detected."})
    else:
        have = min(a.n for a in r.arms)
        ok = have >= EARLY_FRACTION * r.planned_n
        checks.append({"name": "planned sample", "status": "pass" if ok else "fail",
                       "detail": f"{have:,} of {r.planned_n:,} per arm ({100 * have / r.planned_n:.0f}%)."})
    if r.days is None:
        checks.append({"name": "run length", "status": "note", "detail": "Days not given."})
    else:
        checks.append({"name": "run length", "status": "pass" if r.days >= MIN_DAYS else "fail",
                       "detail": f"{r.days} day(s). Aim for at least {MIN_DAYS} to cover a weekly cycle."})
    checks.append({"name": "peeking", "status": "pass" if r.looks == 1 else "note",
                   "detail": "One look." if r.looks == 1 else f"{r.looks} looks, threshold tightened from {r.alpha} to {r.alpha_effective:.4g}."})
    m = len(r.comparisons)
    checks.append({"name": "variants", "status": "pass" if m == 1 else "note",
                   "detail": "One comparison." if m == 1 else f"{m} comparisons, p-values Holm-adjusted."})
    return checks


def report_to_dict(r: Report) -> dict:
    d = asdict(r)
    d["checks"] = build_checks(r)
    return d


def plan_to_dict(p: Plan) -> dict:
    return asdict(p)
