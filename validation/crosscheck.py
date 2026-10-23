"""Cross-check abverdict against scipy / statsmodels / Monte Carlo.

Run from the repo root in an environment with numpy, scipy and statsmodels:
    pip install numpy scipy statsmodels
    python validation/crosscheck.py
Results from the last run are summarised in docs/VALIDATION.md.
"""
import random
import sys

import numpy as np
from scipy import stats as ss
from statsmodels.stats import proportion as sp
from statsmodels.stats.power import NormalIndPower

import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from abverdict import stats, planning, verdict
from abverdict.verdict import Arm

rng = np.random.default_rng(1)
worst = {}


def track(name, d):
    worst[name] = max(worst.get(name, 0), d)


# 1. distributions on a grid
for x in np.linspace(-6, 6, 49):
    track("norm_cdf", abs(stats.norm_cdf(x) - ss.norm.cdf(x)))
for p in (1e-6, 0.001, 0.025, 0.2, 0.5, 0.975, 0.999):
    track("norm_ppf", abs(stats.norm_ppf(p) - ss.norm.ppf(p)))
for df in (1, 2, 5, 17.3, 60, 500, 1e5):
    for t in (-8, -3, -1.1, 0, 0.4, 2.5, 9):
        track("t_cdf", abs(stats.t_cdf(t, df) - ss.t.cdf(t, df)))
    for p in (0.005, 0.025, 0.5, 0.975, 0.995):
        track("t_ppf", abs(stats.t_ppf(p, df) - ss.t.ppf(p, df)) / max(1, abs(ss.t.ppf(p, df))))
for df in (1, 2, 3, 7, 12):
    for x in (0.01, 0.5, 2.7, 9.1, 25, 60):
        track("chi2_sf", abs(stats.chi2_sf(x, df) - ss.chi2.sf(x, df)))
for _ in range(10):
    p = rng.uniform(0, 0.3, 5)
    from statsmodels.stats.multitest import multipletests
    mine = stats.holm_adjust(list(p))
    ref = multipletests(p, method="holm")[1]
    track("holm", float(np.max(np.abs(np.array(mine) - ref))))

# 2. two-proportion test vs statsmodels (pooled z-test) and CI vs Wald
mism_ci_vs_p = 0
total = 0
for _ in range(3000):
    n1, n2 = int(rng.integers(200, 40000)), int(rng.integers(200, 40000))
    p0 = rng.uniform(0.01, 0.4)
    c1, c2 = int(rng.binomial(n1, p0)), int(rng.binomial(n2, p0 * rng.uniform(0.9, 1.15)))
    if min(c1, c2) == 0:
        continue
    r = verdict.analyze([Arm("A", n1, conversions=c1), Arm("B", n2, conversions=c2)])
    ref_p = sp.test_proportions_2indep(c2, n2, c1, n1, method="score", compare="diff").pvalue
    ref_z = sp.proportions_ztest([c2, c1], [n2, n1])[1]
    track("2prop_p_vs_statsmodels_ztest", abs(r.comparisons[0].p_value - ref_z))
    ci = sp.confint_proportions_2indep(c2, n2, c1, n1, method="wald", compare="diff", alpha=0.05)
    track("2prop_ci_vs_wald", max(abs(r.comparisons[0].ci[0] - ci[0]), abs(r.comparisons[0].ci[1] - ci[1])))
    total += 1
    sig_p = r.comparisons[0].p_value < 0.05
    sig_ci = r.comparisons[0].ci[0] > 0 or r.comparisons[0].ci[1] < 0
    mism_ci_vs_p += sig_p != sig_ci

# 3. Welch vs scipy
for _ in range(300):
    n1, n2 = int(rng.integers(5, 400)), int(rng.integers(5, 400))
    a = rng.lognormal(3, 0.6, n1)
    b = rng.lognormal(3.05, 0.9, n2)
    arms = [Arm("A", n1, mean=a.mean(), sd=a.std(ddof=1)), Arm("B", n2, mean=b.mean(), sd=b.std(ddof=1))]
    r = verdict.analyze(arms)
    t = ss.ttest_ind(b, a, equal_var=False)
    track("welch_p", abs(r.comparisons[0].p_value - t.pvalue))
    ci = t.confidence_interval(0.95)
    track("welch_ci", max(abs(r.comparisons[0].ci[0] - ci.low), abs(r.comparisons[0].ci[1] - ci.high)))

# 4. SRM vs scipy chisquare
for _ in range(200):
    ns = [int(x) for x in rng.integers(1000, 50000, 3)]
    w = [0.5, 0.3, 0.2]
    exp = [sum(ns) * x for x in w]
    track("srm", abs(verdict.srm_pvalue(ns, w) - ss.chisquare(ns, exp).pvalue))

# 5. sample size vs statsmodels (unpooled normal approximation) and Evan Miller reference
for base, mde in [(0.05, 0.1), (0.02, 0.2), (0.2, 0.05), (0.1, 0.15)]:
    mine = planning.conversion_n_per_arm(base, mde)
    p2 = base * (1 + mde)
    eff = sp.proportion_effectsize(p2, base)
    ref = NormalIndPower().solve_power(eff, alpha=0.05, power=0.8, ratio=1)
    print(f"sample size base={base} mde={mde}: mine={mine}  statsmodels(Cohen h)={ref:.0f}  diff={100*(mine-ref)/ref:+.2f}%")
sd, d = 10, 2
print("continuous:", planning.continuous_n_per_arm(sd, d), NormalIndPower().solve_power(d / sd, alpha=.05, power=.8))

print("\nmax abs deviations:")
for k, v in worst.items():
    print(f"  {k:32s} {v:.3g}")
print(f"\nCI-excludes-zero vs p<.05 disagreement: {mism_ci_vs_p}/{total} ({100*mism_ci_vs_p/total:.2f}%)")

# 6. Pocock constants: Monte Carlo of equally spaced looks, find nominal two-sided alpha per look
print("\nPocock nominal alpha per look (alpha=.05) [table vs Monte Carlo]")
M = 400000
for K in (2, 3, 4, 5, 8, 10):
    inc = rng.standard_normal((M, K))
    S = np.cumsum(inc, axis=1) / np.sqrt(np.arange(1, K + 1))
    mx = np.abs(S).max(axis=1)
    c = np.quantile(mx, 0.95)
    nominal = 2 * (1 - ss.norm.cdf(c))
    print(f"  K={K}: table={verdict._POCOCK_05[K]:.4f}  MC={nominal:.4f}  overall FWER at table level = "
          f"{(mx > ss.norm.ppf(1 - verdict._POCOCK_05[K] / 2)).mean():.4f}")

# 7. End-to-end operating characteristics through the real verdict engine.
# WINNER is the upper half of a two-sided test, so a nominal 5% two-sided test gives ~2.5% WINNER on A/A.
def sim(p_a, p_b, n, looks, trials, planned_n, stop_early):
    """stop_early=True: the user calls the first significant look (no planned sample).
    stop_early=False: the user peeks but only calls at the planned sample."""
    wins = 0
    for _ in range(trials):
        ca = cb = 0
        called = False
        step = n // looks
        for k in range(1, looks + 1):
            ca += int(rng.binomial(step, p_a)); cb += int(rng.binomial(step, p_b))
            r = verdict.analyze([Arm("A", step * k, conversions=ca), Arm("B", step * k, conversions=cb)],
                                looks=looks, planned_n=None if stop_early else planned_n)
            if r.overall in (verdict.WINNER, verdict.LOSER):
                called = True
                if stop_early:
                    break
        wins += called
    return wins / trials

n = planning.conversion_n_per_arm(0.05, 0.10)
print(f"\nplanned n={n}  (two-sided rates; target false positives 0.05, power 0.80)")
print("A/A, one look at planned n:                         ", sim(.05, .05, n, 1, 4000, n, False))
print("A/A, 5 looks, only call at planned n (peeking):      ", sim(.05, .05, n, 5, 1500, n, False))
print("A/A, 5 looks, stop at first significant, NO fix:     ", end=" ")
# naive: same stopping rule but alpha not adjusted (looks=1 passed to analyze)
def naive(trials=1500, looks=5):
    hit = 0
    for _ in range(trials):
        ca = cb = 0; step = n // looks
        for k in range(1, looks + 1):
            ca += int(rng.binomial(step, .05)); cb += int(rng.binomial(step, .05))
            r = verdict.analyze([Arm("A", step * k, conversions=ca), Arm("B", step * k, conversions=cb)])
            if r.overall in (verdict.WINNER, verdict.LOSER):
                hit += 1; break
    return hit / trials
print(naive())
print("A/A, 5 looks, stop at first significant, with fix:   ", sim(.05, .05, n, 5, 1500, n, True))
print("power at +10% relative, one look at planned n:       ", sim(.05, .055, n, 1, 4000, n, False))
print("power at +10% relative, 5 looks, call only at end:   ", sim(.05, .055, n, 5, 1500, n, False))

# 8. Several variants: familywise false-positive rate with Holm
def fwer(k, trials=1500, n=5000, p=0.05):
    hit = 0
    for _ in range(trials):
        arms = [Arm(str(i), n, conversions=int(rng.binomial(n, p))) for i in range(k)]
        r = verdict.analyze(arms, planned_n=n)
        hit += any(c.verdict in (verdict.WINNER, verdict.LOSER) for c in r.comparisons)
    return hit / trials
print("\nFamilywise false-positive rate (target <= 0.05):")
for k in (3, 4, 6):
    print(f"  {k} arms (A/A/A...): {fwer(k):.3f}")

# 9. Welch on heavy-tailed (lognormal) revenue: false positives and CI coverage
def welch_fpr(n, sigma, trials=3000):
    hit = cover = 0
    true_diff = 0.0
    for _ in range(trials):
        a = rng.lognormal(3, sigma, n); b = rng.lognormal(3, sigma, n)
        arms = [Arm("A", n, mean=a.mean(), sd=a.std(ddof=1)), Arm("B", n, mean=b.mean(), sd=b.std(ddof=1))]
        r = verdict.analyze(arms, planned_n=n)
        hit += r.overall in (verdict.WINNER, verdict.LOSER)
        lo, hi = r.comparisons[0].ci
        cover += lo <= true_diff <= hi
    return hit / trials, cover / trials
print("\nWelch on lognormal revenue, A/A (target false positive 0.05, coverage 0.95):")
for n, sg in ((30, 0.5), (30, 1.5), (200, 1.5), (1000, 1.5), (200, 2.5)):
    fp, cv = welch_fpr(n, sg)
    print(f"  n={n:<5} sigma={sg}: false-positive {fp:.3f}, coverage {cv:.3f}")

# 10. Wald interval coverage for the difference in proportions at low conversion counts
def wald_cov(n, p, trials=4000):
    cover = 0
    for _ in range(trials):
        arms = [Arm("A", n, conversions=int(rng.binomial(n, p))), Arm("B", n, conversions=int(rng.binomial(n, p)))]
        lo, hi = verdict.analyze(arms).comparisons[0].ci
        cover += lo <= 0 <= hi
    return cover / trials
print("\nWald 95% interval coverage for difference in proportions (true difference 0):")
for n, p in ((20000, 0.05), (2000, 0.05), (1000, 0.02), (500, 0.01), (300, 0.01)):
    print(f"  n={n:<6} p={p}: expected conversions/arm={n*p:>5.0f}, coverage {wald_cov(n, p):.3f}")
