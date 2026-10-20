"""Pre-test planning: how many people (and days) does the test need?"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .stats import norm_ppf


@dataclass
class Plan:
    metric: str  # "conversion" or "continuous"
    n_per_arm: int
    arms: int
    alpha: float
    alpha_per_comparison: float
    power: float
    total: int
    raw_days: Optional[int] = None
    days: Optional[int] = None  # raw_days rounded up to whole weeks, minimum 7


def _z_values(alpha: float, power: float, comparisons: int):
    if not 0 < alpha < 1 or not 0 < power < 1:
        raise ValueError("alpha and power must be between 0 and 1")
    a = alpha / comparisons
    return a, norm_ppf(1 - a / 2), norm_ppf(power)


def conversion_n_per_arm(
    baseline: float,
    mde: float,
    relative: bool = True,
    alpha: float = 0.05,
    power: float = 0.8,
    comparisons: int = 1,
) -> int:
    if not 0 < baseline < 1:
        raise ValueError("baseline rate must be between 0 and 1 (e.g. 0.05 for 5%)")
    if mde <= 0:
        raise ValueError("minimum detectable effect must be positive")
    p1 = baseline
    p2 = baseline * (1 + mde) if relative else baseline + mde
    if not 0 < p2 < 1:
        raise ValueError("baseline plus effect must stay between 0 and 1")
    _, za, zb = _z_values(alpha, power, comparisons)
    pbar = (p1 + p2) / 2
    num = (za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    return math.ceil(num / (p2 - p1) ** 2)


def continuous_n_per_arm(
    sd: float, mde: float, alpha: float = 0.05, power: float = 0.8, comparisons: int = 1
) -> int:
    if sd <= 0 or mde <= 0:
        raise ValueError("sd and minimum detectable effect must be positive")
    _, za, zb = _z_values(alpha, power, comparisons)
    return math.ceil(2 * ((za + zb) * sd / mde) ** 2)


def make_plan(
    n_per_arm: int,
    metric: str,
    arms: int = 2,
    alpha: float = 0.05,
    power: float = 0.8,
    daily_traffic: Optional[float] = None,
) -> Plan:
    comparisons = max(arms - 1, 1)
    plan = Plan(
        metric=metric,
        n_per_arm=n_per_arm,
        arms=arms,
        alpha=alpha,
        alpha_per_comparison=alpha / comparisons,
        power=power,
        total=n_per_arm * arms,
    )
    if daily_traffic:
        plan.raw_days = math.ceil(plan.total / daily_traffic)
        plan.days = max(7, math.ceil(plan.raw_days / 7) * 7)
    return plan
