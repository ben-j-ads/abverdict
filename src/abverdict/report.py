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


def report_to_dict(r: Report) -> dict:
    return asdict(r)


def plan_to_dict(p: Plan) -> dict:
    return asdict(p)
