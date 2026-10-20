# abverdict

**Did your A/B test actually win?** A significance calculator that refuses to let you fool yourself.

Most calculators answer "is p < 0.05 right now?" `abverdict` answers the question you actually have, and
checks the mistakes that quietly invalidate marketing tests:

| Guard | What it catches |
|---|---|
| **Planned-sample gate** | Calling a test early because it "looks significant" |
| **Peeking correction** | Checking results repeatedly (Pocock thresholds, Bonferroni fallback) |
| **Sample ratio mismatch** | Broken traffic splits that make every p-value meaningless |
| **Multiple variants** | A/B/C/D tests with Holm-adjusted p-values and widened intervals |
| **Right test for the metric** | Two-proportion z-test for conversions, Welch t-test for revenue-like values |
| **"No effect" vs "no evidence"** | `NO MEANINGFUL DIFFERENCE` only when the interval rules out your minimum effect |
| **Run-length and data warnings** | Under 7 days, under 100 conversions, heavy-tailed revenue |

Zero dependencies. Python 3.9+.

## Install

```bash
pipx install .          # or: pip install .
```

## 1. Plan before you launch

```console
$ abverdict plan --baseline 5% --mde 10% --daily-traffic 2000
Plan (conversion): baseline 5.00%, detect +10.00% relative
  Visitors needed per arm: 31,234
  Arms: 2  ->  total 62,468
  alpha 0.05 (0.05 per comparison), power 80%
  Run for 35 days (needs 32; rounded up to whole weeks, minimum 7)
```

Continuous metric (e.g. revenue per visitor): `abverdict plan --sd 20 --mde 2`.

## 2. Get a verdict

```console
$ abverdict test --arm control=500/10000 --arm new=580/10000 --planned-n 31234 --days 5
KEEP RUNNING: the planned sample hasn't been reached, so it's too early to call.
...
  - It looks significant now, but stopping a fixed-sample test early inflates false positives.
```

From an export (rows are summed per variant, a `date` column sets the run length):

```bash
abverdict test --csv examples/daily_counts.csv --planned-n 30000 --mde 5%
abverdict test --values-csv orders.csv --control A     # columns: variant,value
abverdict test --csv results.csv --looks 3             # you checked 3 times
abverdict test --arm A=800/80000 --arm B=210/20000 --split 80/20
abverdict test ... --json                              # machine-readable
```

Verdicts: `WINNER`, `LOSER`, `KEEP RUNNING`, `NO MEANINGFUL DIFFERENCE`, `INCONCLUSIVE`, `INVALID`.

## Visual interface

```bash
abverdict serve        # opens http://localhost:8765 in your browser
```

Two tabs: **plan** (how big a test do I need?) and **test** (type in counts or paste a CSV). The verdict
comes back as one big word, an interval chart per variant, and a pass / fail list of every guard.
Night shift (dark) is a toggle. It runs entirely on your machine: the server binds to localhost only,
rejects other `Host` headers, and nothing is sent anywhere.

The UI uses the ben.j.ads design system (paper ground, lime as a highlighter only, condensed lowercase
display, square corners). Bricolage Grotesque and Archivo are SIL OFL 1.1 licensed.

## Honest limitations (v0.1)

- Higher is assumed better. Two-sided tests only.
- Conversion intervals use the normal approximation; the tool warns under 100 conversions per arm.
- Revenue uses Welch's t-test on means. Heavy tails are flagged but not bootstrapped yet.
- Multi-variant intervals are Bonferroni-wide while p-values use Holm; this is conservative.
- Pocock thresholds are tabulated for alpha 0.05 and up to 10 looks, otherwise Bonferroni.
- Statistical review by an independent statistician is a to-do before 1.0.

See [docs/PLAN.md](docs/PLAN.md) for the roadmap and [docs/RESEARCH.md](docs/RESEARCH.md) for why this exists.

## Develop

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

MIT licensed.
