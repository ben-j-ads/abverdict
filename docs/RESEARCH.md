# Research: why abverdict

## The problem

Marketers run A/B tests (ads, emails, landing pages, subject lines) and then
have to answer "did it win?" Most reach for a significance calculator, which
answers a narrower question ("is p < 0.05 right now?") and silently allows the
three mistakes that evidence-based marketing warns about most:

1. **Peeking / early stopping.** Checking results repeatedly and stopping at the
   first significant reading inflates false positives well above 5%.
2. **Underpowered tests.** Small samples produce lifts that evaporate on rollout.
3. **Invalid experiments.** Unequal traffic splits (sample ratio mismatch) mean the
   test is broken and the p-value is meaningless, but calculators never check.

Plus: multiple variants without correction, revenue metrics analysed with a
conversion-rate test, and "not significant" misread as "no effect".

## Evidence of demand

Reddit could not be accessed in this session (the search tool, `curl` and the
in-app browser all block it), so this research uses other sources. A Reddit
pass is a listed follow-up.

- **Stack Exchange (Cross Validated)**, sorted by votes for "ab test sample size":
  - "A/B tests: z-test vs t-test vs chi square vs fisher exact test": ~78,500 views, score 61
  - "AB test sample size calculation by hand": ~29,500 views
  - "Calculating significance and uplift on Revenue A/B Tests": ~5,800 views
  - "Calculate sample size based on Conversion Rate, MDE, power and significance level": ~4,800 views
  People repeatedly ask which test to use, how big the sample must be, and how
  to handle revenue metrics.
- **Hacker News** (points/comments at time of search):
  - Netflix Tech Blog, "Interpreting A/B test results: false positives and statistical significance" (76 pts)
  - "How to determine if your A/B test is statistically significant" (87 pts)
  - "Launch HN: ... Price A/B Testing for Shopify" (107 pts, 98 comments)
  - "Attribution is dying, clicks are dying" (261 pts, 243 comments), showing marketers
    are moving toward experiments because attribution is unreliable.
- **Marketing sources** (HubSpot, GoStellar, Disruptive Advertising and others) all
  teach the same checklist: set thresholds before the test, estimate sample size
  up front, use confidence intervals, don't stop early, run at least a full
  business cycle. The checklist exists as prose; no tool enforces it.

## Existing open-source landscape (GitHub search, 2026-10-19)

- `lari-pellini/ab-test-significance` (JS, 2 stars): calculator + CLI. Significance and sample size only.
- `ACSanders/abtestwise` (Python, 1 star): frequentist/Bayesian tests for proportions.
- ABTestCalculator.com (Matt Mazur, 2015): explains results in plain English, no SRM or peeking handling.
- GrowthBook / PostHog: full experimentation platforms. Need self-hosting and
  instrumentation, which is too heavy for "I have two numbers from Mailchimp."

**Gap:** nothing open-source takes plain results from any channel and returns a
guarded verdict that checks validity, power, peeking and multiplicity.

## Decision

Build `abverdict`: zero-dependency Python CLI + library that returns one of
WINNER / LOSER / KEEP RUNNING / NO MEANINGFUL DIFFERENCE / INCONCLUSIVE /
INVALID, with the reasons in plain English.
