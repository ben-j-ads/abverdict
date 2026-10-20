# PR: visual interface (`abverdict serve`) — `feat/web-ui` → `feat/mvp`

Stacked on the MVP PR (ben-j-ads/abverdict#1). Merge that first, then retarget this at `main`.

Try it:

```bash
cd /Users/ben/Desktop/Jarvis/Projects/abverdict
PYTHONPATH=src python3 -m abverdict serve
```

Use "example: looks like a win" to see the guard that matters most.

## What's in it (2 commits)

1. **Server + API.** `abverdict serve` runs a stdlib `ThreadingHTTPServer` on 127.0.0.1 with `POST /api/plan` and `POST /api/test`, wrapping the same functions as the CLI. Reports gain a `checks` list (also in `--json`) and the `mde` used. CSV parsing accepts pasted text.
2. **UI.** One page, vanilla JS, no build step, no CDN.
   - **plan** tab: sample size, total, days (whole weeks), and "use this in the test".
   - **test** tab: variant rows or pasted CSV, a "discipline" section (planned n, days, looks, smallest lift, split), then the verdict as one big word with the highlighter, an interval chart, per-comparison reasons and a pass/fail list of the guards.
   - Night shift toggle, mobile layout, reduced-motion respected, focus rings, labelled inputs.

## Brand (ben.j.ads kit, offline copy)

Tokens, fonts (Bricolage Grotesque ExtraBold Condensed, Archivo; SIL OFL) and wordmarks are copied from `IDC/design-system/benjads`. Rules followed: paper ground; lime only as the highlighter on the conclusion (one per screen), chart data points (with 1.5px ink outline) and the footnote tag; condensed lowercase display; square corners; no shadows; no icons (× and → are typed characters); hover adds a lime highlighter; deadpan copy, "I" voice, no em dashes, none of the banned words. Wordmark in the header, footnote lockup in the footer. IDC marks are not used.

## Testing

- 41 tests (8 new for the server: static serving, path traversal, foreign Host rejected, API happy paths, bad input returns JSON errors, wrong content type). Pass on Python 3.9.6 and 3.14.8.
- Clean `pip install .` includes the web assets.
- Checked by eye in the in-app browser: test result (light and night shift), plan result, 375px mobile. The mobile interval chart was too small on the first pass; fixed by sizing the SVG to the viewport.
- **Not verified:** other browsers (Safari, Firefox), screen reader behaviour, the `INVALID`, `WINNER` and values-CSV renderings by eye (covered by API tests only).

## Review focus

- Security of the local server (`server.py`): localhost bind, Host check, path whitelist, 1 MB body cap. No auth, by design, since it is local.
- Whether the highlighter should mark the verdict word for every outcome (currently yes) or only for good news.
- Copy in `web/index.html` and `web/app.js` against the voice guide.
- Fonts are bundled (about 330 KB). Fine for a private repo; OFL allows redistribution if you open-source it.

## Not in this PR

Hosted version, CSV file upload by drag and drop, saving past tests, shareable result links, PNG export of the verdict card for posts (good fit for a ben.j.ads carousel slide later).
