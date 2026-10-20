# PR: abverdict MVP (v0.1) — `feat/mvp` → `main`

Review locally:

```bash
cd /Users/ben/Desktop/Jarvis/Projects/abverdict
git log --oneline main..feat/mvp
git diff main...feat/mvp
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m abverdict test --csv examples/daily_counts.csv --planned-n 30000 --mde 5%
```

## What this is

An open-source, zero-dependency Python CLI + library that answers "did my A/B
test actually win?" with a guarded, plain-English verdict instead of a bare
p-value. Built for marketers with results from an ad platform, email tool or
landing-page builder and no data-science support.

## Why this problem

See [docs/RESEARCH.md](docs/RESEARCH.md). Short version: Cross Validated has
repeated, heavily viewed questions on which test to use and how big the sample
must be (one at ~78k views), HN rewards posts on A/B pitfalls, and marketing
guides teach a checklist (pre-set thresholds, sample size, no peeking, full
cycles) that no open tool enforces. Existing OSS is either a bare calculator or
a full platform needing self-hosting.

**Caveat:** Reddit was blocked from every access path in this session, so there
is no Reddit evidence. Demand evidence comes from Stack Exchange, HN, GitHub and
marketing sources. Validating on r/marketing, r/PPC and r/CRO is a follow-up.

## What's in the PR (4 commits)

1. **Research, plan, stats primitives**: normal/t/chi-square/incomplete-beta/Holm from the stdlib, tested against published reference values.
2. **Planning + verdict engine + CLI**: `abverdict plan` and `abverdict test`.
3. **Example data + CI** (3.9 / 3.12 / 3.13).
4. **README** with usage and an honest limitations section.

### Guards implemented

- Planned-sample gate (`KEEP RUNNING` unless 95% of planned n is reached)
- Peeking correction via `--looks` (Pocock for alpha .05, up to 10 looks; Bonferroni otherwise)
- Sample ratio mismatch (chi-square, p < 0.001 → `INVALID`), custom `--split`
- Multi-variant Holm-adjusted p-values with Bonferroni-wide intervals
- Conversion: two-proportion z-test. Continuous: Welch t-test
- `NO MEANINGFUL DIFFERENCE` only when the CI excludes `--mde`
- Warnings: <7 days, <100 conversions, <30 observations, heavy tails, no planned n

## Testing

- 33 tests, stdlib `unittest`; pass on Python 3.9.6 and 3.14.8 (run locally).
- `plan` reproduces the published 31,234-per-arm figure (5% baseline, +10% relative, α .05, power .8).
- A simulation test runs 400 A/A experiments with 4 looks each and asserts the false-positive rate stays under 8% with correction on.
- Clean `pip install .` into a fresh venv and CLI run verified.
- **Not verified:** GitHub Actions workflow has never run (no remote); results have not been cross-checked against R/scipy or reviewed by a statistician.

## Review focus

- `src/abverdict/verdict.py`: decision order (INVALID → incomplete → significant → no-difference/inconclusive) and wording.
- Is mixing Holm p-values with Bonferroni intervals acceptable, or should intervals be simplified?
- Pocock applied whenever `--looks > 1`, even at the final planned look. Conservative by design; say if you'd prefer otherwise.
- CLI ergonomics (`--arm name=conv/n`, `--mde` semantics).
- Name `abverdict` (check PyPI/GitHub availability before publishing).

## Not in this PR (see docs/PLAN.md roadmap)

Bootstrap CIs, always-valid sequential tests, Bayesian view, CUPED, HTML report, platform importers, MCP server.

## Before publishing

Nothing has been pushed anywhere. To publish: create the GitHub repo, push `main` and `feat/mvp`, open the PR there, and have a statistician sanity-check the maths.
