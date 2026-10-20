# Validation

An independent statistician hasn't reviewed abverdict. In place of that, every number it produces was
checked against reference libraries, and the whole decision pipeline was run through simulation.
Reproduce with `python validation/crosscheck.py` (needs `numpy scipy statsmodels`).
Reference versions on 2026-10-19: scipy 1.18.1, statsmodels 0.15.0, numpy 2.5.4. Simulations are
Monte Carlo (1,500 to 4,000 trials each), so rates carry about +/-0.5 to 1 point of noise.

## 1. Primitives match the references

| Function | Compared with | Max deviation |
|---|---|---|
| normal CDF / quantile | `scipy.stats.norm` | 1e-16 / 1e-14 |
| t CDF / quantile (df 1 to 1e5) | `scipy.stats.t` | 7e-12 / 3e-6 |
| chi-square survival | `scipy.stats.chi2` | 2e-15 |
| Holm adjustment | `statsmodels multipletests` | 0 |
| two-proportion z-test p-value (3,000 random tests) | `statsmodels proportions_ztest` | 2e-16 |
| difference-in-proportions interval | `statsmodels confint_proportions_2indep` (Wald) | 6e-17 |
| Welch t-test p-value and interval (300 random tests) | `scipy.stats.ttest_ind(equal_var=False)` | 5e-13 / 3e-13 |
| SRM chi-square p-value, uneven split | `scipy.stats.chisquare` | 4e-17 |

## 2. Sample size

Matches Evan Miller's published figure (31,234 per arm for 5% baseline, +10% relative, alpha .05, power .8)
exactly, and `statsmodels` (Cohen's h, a slightly different approximation) within 0.2% on four scenarios.
Continuous metric: 393 vs 392.4 (rounded up).

## 3. Pocock thresholds

The tabulated nominal levels for 2 to 10 looks were re-derived by Monte Carlo (400,000 simulated
experiments per row). All agree to within 0.0001, and the familywise rate at the table level is 0.050.

## 4. Operating characteristics of the verdict engine

Planned n = 31,234 per arm. "Called" means the engine returned WINNER or LOSER.

| Scenario | Result | Target |
|---|---|---|
| A/A, one look at planned n | 5.3% called | 5% |
| A/A, peek 5 times, call only at planned n | 5.8% called | 5% |
| A/A, 5 looks, stop at first significant, **no correction** | **15.3% called** | the problem being solved |
| A/A, 5 looks, stop at first significant, with correction | 4.4% called | 5% |
| +10% relative lift, one look at planned n | 80.1% power | 80% |
| +10% relative lift, 5 looks, call only at planned n | 79.3% power | 80% |
| A/A/A, A/A/A/A, six arms: any false call | 4.6%, 4.4%, 4.4% | at most 5% |

## 5. Robustness checks

Welch t-test on heavy-tailed (lognormal) revenue, A/A: false positives stay at or below 5% in every case
tried (2% to 5%), and interval coverage is 95% to 98%. The test is conservative here, not anti-conservative.
Wald interval coverage for the difference in proportions, down to 3 expected conversions per arm: 94% to 96%.

## Bugs this review found and fixed

1. **Double penalty for peeking.** The engine blocked early calls (waiting for the planned sample) and also
   tightened the threshold for extra looks. Peeking without calling is harmless, so a user who looked 4 times
   lost power (66% instead of 80%) for no benefit. Now the correction applies only when no planned sample is
   given, because early stopping can't be ruled out then.
2. **Confusing wording at the boundary.** The p-value uses pooled variance and the interval unpooled, so they
   can disagree right at the cut-off (about 0.6% of random tests). The engine already required both; it now says
   "borderline" and tells you to treat the result as unproven.

## What this does not cover

- Review by a human statistician. Treat the tool as well-checked, not certified.
- One-sided tests, ratio metrics, ratio-of-means, clustered data, CUPED. Not implemented.
- Heavy-tailed data under a real effect (only A/A was simulated), and skew that differs between arms.
- Sequential designs that allow stopping early at a planned look. Peeking is protected, but a group-sequential
  plan with early stopping isn't supported (roadmap: always-valid sequential tests).
- Users who keep running past the planned sample after seeing a significant result (optional continuation).
- Non-independence between visitors (the same person counted twice), novelty effects, or tracking bugs.
  Only the traffic split is checked.
