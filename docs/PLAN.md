# Development plan

## Positioning
"A significance calculator that refuses to let you fool yourself." Audience:
marketers and growth people who have results from an ad platform, email tool or
landing-page builder and no data-science support.

## Principles
- Zero runtime dependencies (stdlib only) so `pipx install` just works.
- Verdicts, not just p-values. Every verdict lists the reasons that drove it.
- Defaults follow the evidence-based checklist: alpha 0.05 two-sided, power 0.8,
  at least 7 days, pre-registered sample size.
- Statistical code is small, readable and tested against published reference values.

## MVP (this PR): v0.1
| Area | Scope |
|---|---|
| `plan` | Sample size per arm and test duration for conversion or continuous metrics; multi-variant Bonferroni alpha; rounds duration to full weeks |
| `test` | Conversion counts (`--arm name=conv/n`, CSV) and raw values (CSV, Welch t-test) |
| Guards | SRM check; planned-sample gate; peeking handling (calls held until the planned sample; Pocock, else Bonferroni, when no plan is given); Holm for multiple variants; <7 day, low-conversion and heavy-tail warnings |
| Output | Plain-English text and `--json` |
| Quality | stdlib `unittest`, reference-value tests for the math, CLI tests, CI workflow |

## Out of scope for the MVP
Bayesian mode, sequential (always-valid) tests, CUPED variance reduction,
bootstrap CIs, ratio metrics, HTML report, web UI, direct integrations.

## Roadmap
- **v0.2** Bootstrap CI for revenue; always-valid sequential p-values (mSPRT) so peeking is allowed rather than merely corrected; HTML one-page report.
- **v0.3** Importers for common exports (Google Ads, Meta Ads, Mailchimp, Klaviyo, GA4); MCP server so assistants can call it.
- **v0.4** Bayesian view with expected loss; CUPED; experiment log (SQLite) to track pre-registered plans vs. outcomes.
- **Launch** Publish to PyPI, post "Show HN", write the "5 ways your A/B test lies to you" post using the guards as the hook, collect feedback on r/marketing, r/PPC, r/CRO (to be done by a human; Reddit posting is outward-facing).

## Risks
- Statistical correctness: mitigated by reference tests; request a statistician review before v1.0.
- Pocock table only covers alpha 0.05 and up to 10 looks, otherwise falls back to Bonferroni (conservative, documented).
- Crowded calculator space: differentiation is guards + verdict, so keep scope there.

## Validation of the idea
Success signals within 60 days of launch: 100+ GitHub stars, 5+ external issues
that describe real tests run through it, 1 integration PR from a user.
