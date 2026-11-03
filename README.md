# Beyond the Whistle

**Quantifying Avoidable Win-Probability Harm from NBA Officiating Errors**

> **Status: Step 0 — research design and data preparation scaffolding.** No NBA records have been independently validated in this repository; no win-probability model or empirical error-impact result is claimed.

## Research question

How much competitive harm might be attributable to **confirmed** officiating errors in close NBA games, and which interventions could reduce that harm without substantially disrupting game flow?

This project distinguishes an ordinary win-probability change following a whistle from the **counterfactual impact of an incorrect officiating decision**.

## Scope and important limitations

**Primary sample:** games with official NBA Last Two Minute (L2M) reports, under the eligibility rules applicable to each season. Recent NBA reports cover games within **three points at any point in the final two minutes of Q4**, including applicable overtime. These reports assess whistles and **notable**, not exhaustive, non-whistles.

The original broader proposal — **last five minutes of Q4, within ten points** — is a *future extension* requiring additional video annotation; the official L2M dataset cannot label those first three minutes.

Grades: **CC** (Correct Call), **CNC** (Correct Non-Call), **IC** (Incorrect Call), **INC** (Incorrect Non-Call). Counts of CNC are selected, so simple incorrect / all-graded ratios should **not** be presented as comprehensive officiating error rates. A crew listing does not identify the specific referee responsible.

## Step 0: data preparation

This repository currently contains a reproducible **source preparation and QA utility**, not a validated dataset. The historical source is the community-maintained [atlhawksfanatic/L2M dataset](https://github.com/atlhawksfanatic/L2M), cross-referenced against the [NBA's official L2M archive](https://official.nba.com/2025-26-nba-officiating-last-two-minute-reports/). Please review [data provenance](docs/data_sources.md) before analysis.

### Quick start

Requires **Python 3.10+**.

```bash
git clone https://github.com/woodywu226/BeyondtheWhistle.git
cd BeyondtheWhistle
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
python -m pip install -e ".[dev]"
pytest -q
python -m beyond_the_whistle.prepare_l2m
```

The last command attempts to download the upstream historical CSV (network access required). For an existing local copy:

```bash
python -m beyond_the_whistle.prepare_l2m --input /path/to/L2M_stats_nba.csv
```

Outputs, created only **after successful execution**:
- `data/raw/l2m_source.csv` — preserved original source bytes (gitignored)
- `data/processed/l2m_audit.json` — URL/path, retrieval UTC timestamp, SHA-256, source schema, grade/season counts, missing values, warnings (gitignored)

The script **does not** fabricate missing seasons, fill in ungraded events, download play-by-play, or claim NBA-official validation. Upstream file/column changes can cause the downloader to fail; inspect the error and source before adapting.

### Project structure

```text
src/beyond_the_whistle/prepare_l2m.py  # source download + schema audit
tests/test_prepare_l2m.py              # synthetic-data unit tests
docs/data_sources.md                   # URLs, eligibility, provenance, limits
docs/research_protocol.md              # study design and milestones
data/raw/                               # local inputs (ignored)
data/processed/                         # local QA outputs (ignored)
pyproject.toml                          # Python package configuration
```

## Planned methods (not yet implemented)

1. **Step 1:** validate source records against official reports; ingest and match NBA play-by-play events; assess coverage.
2. **Step 2:** train and calibrate temporally validated game-state win-probability models.
3. **Step 3:** reconstruct corrected game states for a *restricted set of interpretable errors*, then simulate downstream outcomes and quantify uncertainty.
4. **Step 4:** evaluate contextual error patterns with appropriate denominators, avoiding unsupported individual-referee attribution.
5. **Step 5:** compare **hypothetical** replay/training strategies under interruption-time constraints; do not describe simulations as field-proven policy impacts.

## Methodological distinction

For an affected team's winning probability, the intended target for a reconstructable event is:

```text
Estimated effect = WP(observed state)
                 - E[WP(corrected state) | pre-decision information, assumptions]
```

The expectation must integrate multiple possible corrected outcomes (e.g., free throws and ensuing possession). It should carry uncertainty, and is **not identifiable purely from a single observed play** without modeling assumptions.

## References

- [NBA 2025–26 official L2M reports](https://official.nba.com/2025-26-nba-officiating-last-two-minute-reports/)
- [NBA 2017 eligibility change announcement](https://www.nba.com/news/nba-changes-last-two-minute-reports-2017-18)
- [atlhawksfanatic/L2M historical dataset](https://github.com/atlhawksfanatic/L2M)
- [Pelechrinis (2023), implicit biases in refereeing](https://doi.org/10.1038/s41598-023-31799-y)
- [Duma & Benaharon (2026), Referee Impact Metric](https://arxiv.org/abs/2605.17845)

## Research integrity

This is an independent, in-progress research project. Analysis, statistics, academic publication and real-world officiating improvements are **not** claimed until reproduced and independently evaluated. Data rights and NBA site access conditions must be respected.
