"""The verdict engine: statistics plus the guards that stop people fooling themselves."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

from .stats import chi2_sf, holm_adjust, norm_cdf, norm_ppf, t_cdf, t_ppf

WINNER = "WINNER"
LOSER = "LOSER"
KEEP_RUNNING = "KEEP RUNNING"
NO_DIFFERENCE = "NO MEANINGFUL DIFFERENCE"
INCONCLUSIVE = "INCONCLUSIVE"
INVALID = "INVALID"

SRM_THRESHOLD = 0.001  # conventional cut-off for sample ratio mismatch
EARLY_FRACTION = 0.95  # must reach this share of the planned sample to call it
MIN_DAYS = 7

# Pocock constant nominal levels for two-sided alpha = 0.05, by number of looks.
_POCOCK_05 = {1: 0.05, 2: 0.0294, 3: 0.0221, 4: 0.0182, 5: 0.0158,
              6: 0.0142, 7: 0.0130, 8: 0.0120, 9: 0.0112, 10: 0.0106}


@dataclass
class Arm:
    """One experiment arm. Conversion arms set `conversions`; value arms set `mean`/`sd`."""
    name: str
    n: int
    conversions: Optional[int] = None
    mean: Optional[float] = None
    sd: Optional[float] = None
    skew: Optional[float] = None

    @property
    def rate(self) -> float:
        return self.conversions / self.n


@dataclass
class Comparison:
    variant: str
    control: str
    effect: float  # variant minus control (rate points or metric units)
    ci: tuple
    relative_effect: Optional[float]
    relative_ci: Optional[tuple]
    p_value: float
    p_adjusted: float
    verdict: str
    reasons: list = field(default_factory=list)


@dataclass
class Report:
    metric: str
    arms: list
    comparisons: list
    alpha: float
    alpha_effective: float
    ci_level: float
    looks: int
    planned_n: Optional[int]
    days: Optional[int]
    srm_p: float
    overall: str
    headline: str
    warnings: list = field(default_factory=list)
    mde: Optional[float] = None


def fmt_p(p: float) -> str:
    return "<0.0001" if p < 1e-4 else f"{p:.3g}"


def effective_alpha(alpha: float, looks: int) -> float:
    """Per-look alpha: Pocock where tabulated, Bonferroni otherwise (conservative)."""
    if looks <= 1:
        return alpha
    if alpha == 0.05 and looks in _POCOCK_05:
        return _POCOCK_05[looks]
    return alpha / looks


def srm_pvalue(ns: Sequence[int], split: Optional[Sequence[float]] = None) -> float:
    k = len(ns)
    weights = list(split) if split else [1.0] * k
    if len(weights) != k or any(w <= 0 for w in weights):
        raise ValueError("split must have one positive weight per arm")
    total, wsum = sum(ns), sum(weights)
    stat = sum((n - total * w / wsum) ** 2 / (total * w / wsum) for n, w in zip(ns, weights))
    return chi2_sf(stat, k - 1)


def _validate(arms: Sequence[Arm]):
    if len(arms) < 2:
        raise ValueError("need a control and at least one variant")
    names = [a.name for a in arms]
    if len(set(names)) != len(names):
        raise ValueError("arm names must be unique")
    for a in arms:
        if a.n <= 0:
            raise ValueError(f"arm '{a.name}' has no visitors")
        if a.conversions is not None and not 0 <= a.conversions <= a.n:
            raise ValueError(f"arm '{a.name}': conversions must be between 0 and visitors")


def _two_prop(c: Arm, v: Arm, ci_level: float):
    p1, p2 = c.rate, v.rate
    pooled = (c.conversions + v.conversions) / (c.n + v.n)
    se0 = math.sqrt(pooled * (1 - pooled) * (1 / c.n + 1 / v.n))
    diff = p2 - p1
    p = 1.0 if se0 == 0 else 2 * norm_cdf(-abs(diff) / se0)
    se = math.sqrt(p1 * (1 - p1) / c.n + p2 * (1 - p2) / v.n)
    z = norm_ppf(1 - (1 - ci_level) / 2)
    return diff, (diff - z * se, diff + z * se), p


def _welch(c: Arm, v: Arm, ci_level: float):
    v1, v2 = c.sd ** 2 / c.n, v.sd ** 2 / v.n
    se = math.sqrt(v1 + v2)
    diff = v.mean - c.mean
    if se == 0:
        return diff, (diff, diff), 1.0 if diff == 0 else 0.0
    df = (v1 + v2) ** 2 / (v1 ** 2 / (c.n - 1) + v2 ** 2 / (v.n - 1))
    p = min(1.0, 2 * t_cdf(-abs(diff / se), df))
    crit = t_ppf(1 - (1 - ci_level) / 2, df)
    return diff, (diff - crit * se, diff + crit * se), p


def analyze(
    arms: Sequence[Arm],
    alpha: float = 0.05,
    planned_n: Optional[int] = None,
    days: Optional[int] = None,
    looks: int = 1,
    mde: Optional[float] = None,
    split: Optional[Sequence[float]] = None,
) -> Report:
    """Analyse arms[0] (control) against every other arm.

    `mde` is the smallest effect worth acting on, in the metric's own units
    (rate points for conversion tests). It lets a non-significant result with a
    tight interval be reported as "no meaningful difference" rather than just
    "inconclusive".
    """
    _validate(arms)
    is_conv = arms[0].conversions is not None
    if any((a.conversions is not None) != is_conv for a in arms):
        raise ValueError("cannot mix conversion and value arms")
    if looks < 1:
        raise ValueError("looks must be at least 1")

    control, variants = arms[0], list(arms[1:])
    m = len(variants)
    alpha_eff = effective_alpha(alpha, looks)
    ci_level = 1 - alpha_eff / m
    srm_p = srm_pvalue([a.n for a in arms], split)
    invalid = srm_p < SRM_THRESHOLD

    raw = [(_two_prop if is_conv else _welch)(control, v, ci_level) for v in variants]
    p_adj = holm_adjust([r[2] for r in raw])
    min_n = min(a.n for a in arms)
    incomplete = planned_n is not None and min_n < EARLY_FRACTION * planned_n

    comparisons = []
    for v, (diff, ci, p), pa in zip(variants, raw, p_adj):
        reasons = []
        base = control.rate if is_conv else control.mean
        rel = diff / base if base else None
        rel_ci = (ci[0] / base, ci[1] / base) if base else None
        significant = pa < alpha_eff and (ci[0] > 0 or ci[1] < 0)
        if invalid:
            verdict = INVALID
            reasons.append(f"Traffic split is off (SRM p={fmt_p(srm_p)}); the test is broken, so no result can be trusted.")
        elif incomplete:
            verdict = KEEP_RUNNING
            done = 100 * min_n / planned_n
            reasons.append(f"Only {done:.0f}% of the planned sample ({min_n:,} of {planned_n:,} per arm).")
            if significant:
                reasons.append("It looks significant now, but stopping a fixed-sample test early inflates false positives. Wait for the planned sample.")
        elif significant:
            verdict = WINNER if diff > 0 else LOSER
            reasons.append(f"Adjusted p={pa:.3g} is below the threshold of {alpha_eff:.3g} and the interval excludes zero.")
        else:
            if mde is not None and ci[0] > -mde and ci[1] < mde:
                verdict = NO_DIFFERENCE
                reasons.append("The interval rules out any effect as large as the minimum worth acting on.")
            else:
                verdict = INCONCLUSIVE
                reasons.append(f"Adjusted p={pa:.3g}; the data can't distinguish this from no effect, and can't rule out a meaningful one.")
                reasons.append("Not significant is not the same as no effect.")
        comparisons.append(Comparison(v.name, control.name, diff, ci, rel, rel_ci, p, pa, verdict, reasons))

    warnings = _warnings(arms, is_conv, planned_n, days, looks, alpha, alpha_eff, m)
    overall, headline = _overall(comparisons, srm_p)
    return Report("conversion" if is_conv else "continuous", list(arms), comparisons, alpha, alpha_eff,
                  ci_level, looks, planned_n, days, srm_p, overall, headline, warnings, mde)


def _warnings(arms, is_conv, planned_n, days, looks, alpha, alpha_eff, m):
    out = []
    if planned_n is None:
        out.append("No planned sample size given, so stopping early can't be detected. Run `abverdict plan` before your next test and pass --planned-n.")
    if days is not None and days < MIN_DAYS:
        out.append(f"Test ran {days} day(s). Run at least {MIN_DAYS} to cover a full weekly cycle.")
    if looks > 1:
        out.append(f"You looked {looks} times, so the threshold was tightened from {alpha} to {alpha_eff:.4g} per look to keep false positives near {alpha:.0%}.")
    if m > 1:
        out.append(f"{m} variants compared with control: p-values are Holm-adjusted and intervals widened (Bonferroni).")
    if is_conv:
        low = [a.name for a in arms if a.conversions < 100]
        if low:
            out.append(f"Fewer than 100 conversions in: {', '.join(low)}. Normal approximations get shaky; treat the result as directional.")
    else:
        small = [a.name for a in arms if a.n < 30]
        if small:
            out.append(f"Fewer than 30 observations in: {', '.join(small)}. Welch's t-test needs more data.")
        heavy = [a.name for a in arms if a.skew is not None and abs(a.skew) > 2]
        if heavy:
            out.append(f"Heavy-tailed data in: {', '.join(heavy)} (typical of revenue). A few large values can dominate the mean; be cautious with small samples.")
    return out


def _overall(comparisons, srm_p):
    verdicts = [c.verdict for c in comparisons]
    if INVALID in verdicts:
        return INVALID, f"INVALID: the traffic split doesn't match what was intended (SRM p={fmt_p(srm_p)}). Fix the experiment setup and rerun."
    winners = [c for c in comparisons if c.verdict == WINNER]
    if winners:
        best = max(winners, key=lambda c: c.effect)
        rel = f" ({best.relative_effect:+.1%} relative)" if best.relative_effect is not None else ""
        return WINNER, f"WINNER: '{best.variant}' beats '{best.control}'{rel}."
    if KEEP_RUNNING in verdicts:
        return KEEP_RUNNING, "KEEP RUNNING: the planned sample hasn't been reached, so it's too early to call."
    if all(v == LOSER for v in verdicts):
        return LOSER, "LOSER: every variant is worse than control. Keep the control."
    if all(v == NO_DIFFERENCE for v in verdicts):
        return NO_DIFFERENCE, "NO MEANINGFUL DIFFERENCE: ship whichever is cheaper or simpler."
    return INCONCLUSIVE, "INCONCLUSIVE: not enough evidence either way. Keep the control unless you can collect more data."
