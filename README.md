# Beyond the Whistle

**Quantifying avoidable win-probability harm from NBA officiating errors**

Research question: *How much competitive harm is attributable to confirmed officiating errors in close NBA games, and which interventions could reduce that harm without substantially disrupting game flow?*

> **Status: Step 1 complete at official-label/game level; Step 2.1 historical win-probability state dataset built and validated. Event-level film adjudication and win-probability model training remain open.** No win-probability model, counterfactual causal result or policy effectiveness claim has been produced.

## Verified 2024–25 data

| Metric | Result |
| --- | ---: |
| NBA L2M-eligible games | **423** |
| Historical L2M decisions | **7,165** |
| Public PBP games (regular + play-in + postseason) | **1,316** |
| L2M games agreeing on ID, date, home and away across PBP | **423/423** |
| Individual NBA official L2M JSON reports independently obtained | **423/423** |
| Report records matching official period, time, call type and grade | **7,165/7,165** |

Decision counts: **CC: 2,033 · CNC: 4,801 · IC: 66 · INC: 263 · ungraded: 2.**

The historical dataset was reconciled directly against the NBA's current official report JSON. Six apparent discrepancies were only missing-value formatting differences (`NA` versus `N/A` or empty); no official decision-label conflict remained. Raw source values are retained unchanged. Full evidence and limitations are documented in [Step 1 results](docs/step1_results.md).

**Two Play-In games successfully added:** `0052400121` (Grizzlies @ Warriors), `0052400201` (Heat @ Hawks), using independently available ESPN play-by-play. This closes the earlier 421/423 coverage gap.

### Important: what the 100% figure does *not* mean

- The official L2M decision grades have been confirmed against the NBA's own official JSON. This is not a new, independently conducted video adjudication.
- Play-by-play has no reliable whistle event for **CNC** and **INC** by definition. They must not be assigned a fabricated PBP event number.
- A clock-and-type candidate for CC/IC is not necessarily the same incident; automated candidate links still require independent video or additional event evidence.
- The source covers qualifying *late-game* contests and selectively recorded notable non-calls. A raw CC/CNC/IC/INC ratio is **not** a league-wide referee error rate.
- Referee crew membership alone does not identify the specific official making a decision.

## Reproduce the full Step 1 pipeline

Requires Python **3.10+** and Internet access to the data providers:

```bash
git clone https://github.com/woodywu226/BeyondtheWhistle.git
cd BeyondtheWhistle
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
ruff check .
python -m beyond_the_whistle.finalize_step1 --official-workers 4
```

The last command downloads the historical L2M CSV, NBA CDN regular-season/playoff archives, two ESPN Play-In summaries and all 423 official NBA L2M JSON reports. A source outage or access restriction is treated as an error and reported, not silently filled with invented data.

The generated, versioned research outputs are:

- [L2M–PBP candidate keys](data/validated/l2m_pbp_2025_candidates.csv)
- [Source / event mapping audit JSON](data/validated/l2m_pbp_2025_audit.json)
- [Official comparison for all 423 games](data/validated/l2m_2025_official_comparison.json)
- [Data validation methodology and limitations](docs/step1_results.md)

Original large source downloads are not redistributed. The audit includes source URLs and SHA-256 identifiers for provenance.

## Research workflow

| Stage | Goal | Status |
| --- | --- | --- |
| Step 0 | Research protocol, source inventory, package setup, unit tests | Implemented |
| Step 1 | Real L2M / PBP source integration and official report reconciliation | **Complete at game-level and official-label level** |
| Step 1 research QA | Video-confirmed same-event matching and reviewer agreement | **Not yet done** |
| Step 2 | Temporal, calibrated game-state win-probability baseline | Planned |
| Step 3 | Counterfactual corrected-event simulation with uncertainty | Planned |
| Step 4 | Context-adjusted officiating error patterns and fairness | Planned |
| Step 5 | Scenario-based low-disruption intervention optimization | Planned |

The study initially focuses on official L2M reports. Extending the analysis to **the final five minutes of Q4 with a margin of ten points or fewer** would require newly annotated video, because NBA's L2M reports do not label that full window.

## Project structure

```text
src/beyond_the_whistle/
  prepare_l2m.py             # upstream CSV schema and provenance checks
  build_archive_dataset.py   # historical NBA CDN action archive parsing
  build_real_dataset.py      # score-clock, match-key and metadata audits
  finalize_step1.py          # official NBA report reconciliation and play-in backfill
  ingest_pbp.py              # alternative NBA play-by-play JSON ingestion
  match_events.py            # conservative temporal candidates
tests/                       # deterministic unit tests
data/validated/              # limited derived data and source-reconciliation results
docs/                        # study protocol, sources and validation notes
.github/workflows/           # test and data-reconciliation CI
```

## References and data rights

- [NBA's official 2024–25 L2M reports](https://official.nba.com/2024-25-nba-officiating-last-two-minute-reports/)
- [Historical L2M project (atlhawksfanatic)](https://github.com/atlhawksfanatic/L2M)
- [NBA play-by-play archives (shufinskiy)](https://github.com/shufinskiy/nba_data)
- [Pelechrinis (2023): implicit officiating biases](https://doi.org/10.1038/s41598-023-31799-y)
- [Duma & Benaharon (2026): Referee Impact Metric](https://arxiv.org/abs/2605.17845)

This is an independent research project in progress. The published labels are NBA retrospectives; no changes to NBA officiating practice or causal effects have been experimentally demonstrated.

## Step 2.1 — Leakage-safe win-probability dataset

**Status: Implemented and tested on real NBA play-by-play.** Dataset construction, **not** model fitting or calibration.

Four NBA **regular-season** archives (2021–22 through 2024–25) yielded **125,812** post-action Q4/OT states across **4,907** valid games. The 30-second clock-bucket sampler selects at most one latest recorded state in each game/period/bucket. The target `home_win` is determined from a separately verified terminal game-end score.

| Partition | Seasons | Games | States |
| --- | --- | ---: | ---: |
| Train | 2021–22, 2022–23 | 2,448 | 62,901 |
| Validation | 2023–24 | 1,230 | 31,482 |
| Test | 2024–25 | 1,229 | 31,429 |

**13 games excluded** for missing terminal game-end markers (12 from 2021–22 and one from 2024–25); they are not assigned unverified final outcomes. The training-only feature whitelist is `period`, `seconds_remaining`, `home_score`, `away_score`, `home_margin`, `seconds_into_period`. Game IDs and splits are metadata, **not predictors**.

Artifacts: [full Q4 state table](data/win_probability/wp_q4_states_2021_2024.csv), [provenance and split audit](data/win_probability/wp_q4_manifest.json), [dataset construction and leakage methodology](docs/step2_1_dataset.md).

```bash
python -m pip install -e ".[dev]"
pytest -q
ruff check .
python -m beyond_the_whistle.wp_dataset
```

A successful Step 2.1 establishes a leakage-aware **model-ready dataset**, **not** a calibrated winning-probability model. **Step 2.2** will train and evaluate the WP baseline using validation data for model selection and holding out the 2024–25 test season.
