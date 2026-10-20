"""Small, dependency-free statistical primitives.

Algorithms follow standard references (Numerical Recipes for the incomplete
beta/gamma functions). Tests check them against published reference values.
"""
from __future__ import annotations

import math

_EPS = 3e-14
_FPMIN = 1e-300


def norm_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2))


def norm_ppf(p: float) -> float:
    if not 0 < p < 1:
        raise ValueError("p must be in (0, 1)")
    return _bisect(norm_cdf, p, -40.0, 40.0)


def _bisect(cdf, target: float, lo: float, hi: float) -> float:
    for _ in range(200):
        mid = (lo + hi) / 2
        if cdf(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _betacf(a: float, b: float, x: float) -> float:
    qab, qap, qam = a + b, a + 1, a - 1
    c = 1.0
    d = 1 - qab * x / qap
    d = 1 / (d if abs(d) > _FPMIN else _FPMIN)
    h = d
    for m in range(1, 500):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > _FPMIN else _FPMIN)
        c = 1 + aa / c
        c = c if abs(c) > _FPMIN else _FPMIN
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > _FPMIN else _FPMIN)
        c = 1 + aa / c
        c = c if abs(c) > _FPMIN else _FPMIN
        delta = d * c
        h *= delta
        if abs(delta - 1) < _EPS:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log(1 - x)
    )
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1 - bt * _betacf(b, a, 1 - x) / b


def t_cdf(t: float, df: float) -> float:
    x = df / (df + t * t)
    tail = 0.5 * betainc(df / 2, 0.5, x)
    return 1 - tail if t > 0 else tail


def t_ppf(p: float, df: float) -> float:
    return _bisect(lambda v: t_cdf(v, df), p, -1e3, 1e3)


def gammainc_lower(a: float, x: float) -> float:
    """Regularized lower incomplete gamma P(a, x)."""
    if x <= 0:
        return 0.0
    log_prefix = -x + a * math.log(x) - math.lgamma(a)
    if x < a + 1:
        ap, s = a, 1 / a
        d = s
        for _ in range(1000):
            ap += 1
            d *= x / ap
            s += d
            if abs(d) < abs(s) * _EPS:
                break
        return s * math.exp(log_prefix)
    b = x + 1 - a
    c = 1 / _FPMIN
    d = 1 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = d if abs(d) > _FPMIN else _FPMIN
        c = b + an / c
        c = c if abs(c) > _FPMIN else _FPMIN
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < _EPS:
            break
    return 1 - math.exp(log_prefix) * h


def chi2_sf(x: float, df: int) -> float:
    """Survival function (upper tail) of the chi-square distribution."""
    return 1 - gammainc_lower(df / 2, x / 2)


def holm_adjust(pvals: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values, returned in the input order."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adjusted[i] = running
    return adjusted
