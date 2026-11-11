# Beyond the Whistle

**Studying NBA officiating under public scrutiny and its potential consequences**

The primary pilot compares whistle frequency and independently assessed accuracy around the final two minutes of regulation. The broader study asks how decisions vary across teams and players, whether comparable contact is officiated differently for stars, and how often verified errors imply a material change in modeled win probability. See the [research protocol](docs/research_protocol.md).

> **Status: Step 1 official L2M report reconciliation complete; Step 2.1 time-split dataset complete; Step 2.2 NBA win-probability model trained; Step 2.3 real-season clutch robustness and game-cluster uncertainty audit complete; Step 2.4 frozen, validated post-action inference interface implemented.** Independent event-level film adjudication and counterfactual causal modeling remain open. No measured officiating causal effects or policy effectiveness claims have been produced.

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
| Step 2 | Temporal WP dataset, model, robustness, safe frozen inference and handoff | **Complete as predictive baseline; NOT a causal officiating model** |
| Step 3 | Independent video pilot comparing matched Q4 windows before and after 2:00 | Planned |
| Step 4 | Opportunity-adjusted team, player and star-status comparisons | Planned |
| Step 5 | Rule-supported win-probability scenarios for verified errors | All 66 IC records reviewed against official reports. 20 scored under explicit assumptions. Independent video review pending |

The [48-case L2M queue](data/validated/step1_review_queue_2025.csv) is available for calibration. The formal pilot requires new, independently reviewed video from both sides of 2:00. Whistle frequency and accuracy are separate outcomes. A difference across the boundary alone cannot identify the effect of public scrutiny because tactics and game state also change late in games.

The [incorrect-call scenario tool](docs/incorrect_call_win_probability.md)
inventories the 66 official IC cases and compares user-supplied observed and
corrected score-clock states using the frozen Step 2 model. The
[batch results](data/validated/ic_wp_2024_25.csv) record an estimate or a
case-specific disposition for every official IC.

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

A successful Step 2.1 establishes a leakage-aware **model-ready dataset**, **not** a calibrated winning-probability model. **Step 2.2** has now trained and evaluated a WP baseline on the untouched 2024–25 season; see below.


## Step 2.2 — Calibrated win-probability baseline (trained)

**Completed with real 2024–25 held-out testing.** Models were trained on 2021–22 and 2022–23 games, selected on 738 games of 2023–24, probability-calibrated on a *different* 492 games of 2023–24, and tested on **31,429 states from 1,229 games** of 2024–25.

The selected **Histogram Gradient Boosting** baseline outperformed Logistic Regression slightly on the pre-specified game-balanced 2023–24 selection Brier metric. Final held-out results:

| 2024–25 test | Brier ↓ | Game-balanced Brier ↓ | Log Loss ↓ | ROC-AUC ↑ |
| --- | ---: | ---: | ---: | ---: |
| Constant training home-win frequency | 0.24843 | 0.24835 | 0.69001 | 0.5000 |
| Selected model, raw probabilities | **0.08978** | **0.08518** | **0.28166** | 0.9504 |
| Selected model, Platt-calibrated | 0.09041 | 0.08564 | 0.28542 | 0.9504 |

**Negative result worth reporting:** Platt calibration slightly **worsened** the held-out Brier and Log Loss. We retain both outputs and do not use the test season to reselect the model.

The crucial late-and-close subset (<=120 seconds remaining, score margin <=5) contained 1,667 states across 450 games; calibrated state Brier was **0.13491** and AUC **0.89486**. The model predicts **post-action** state win probability; using it to estimate a wrong call's effect still requires independent event verification and pre-decision state reconstruction.

See [Step 2.2 protocol](docs/step2_2_model.md), [actual results](docs/step2_2_results.md), [full metrics JSON](models/win_probability/wp_model_report.json), [2024–25 predictions](models/win_probability/wp_test_predictions.csv), [10-bin calibration data](models/win_probability/wp_test_calibration.csv) and [saved fitted model](models/win_probability/wp_baseline.joblib).

```bash
python -m pip install -e ".[dev,ml]"
pytest -q
ruff check .
python -m beyond_the_whistle.wp_model
```

**Step 2.3 completed:** See [real-game clutch reliability and bootstrap confidence intervals](docs/step2_3_results.md). Step 2.4 adds a frozen inference contract and research handoff; see below.


## Step 2.3 — Clutch calibration and game-cluster robustness

**Implemented and evaluated without refitting the frozen Step 2.2 model.** We independently audited the full 2024–25 held-out season with **1,000 paired, whole-game bootstrap resamples** (rather than treating 31,429 within-game states as independent).

| 2024–25 subgroup | Games | States | Raw game-balanced Brier ↓ | Platt game-balanced Brier ↓ |
| --- | ---: | ---: | ---: | ---: |
| All Q4 and OT | 1,229 | 31,429 | **0.08518** | 0.08564 |
| Final 120 seconds, margin ≤5 | 450 | 1,667 | **0.09852** | 0.09927 |
| Final 30 seconds, margin ≤3 | 214 | 243 | **0.07845** | 0.07951 |
| Overtime | 60 | 704 | **0.16498** | 0.16820 |
| Any clock, margin 0–2 | 536 | 4,624 | **0.21665** | 0.21803 |

The overall Platt-minus-raw game-balanced Brier difference was **+0.000466**, with paired game-cluster bootstrap 95% interval **[−0.000748, +0.001623]**. The interval spans zero, so we **cannot** establish that Platt scaling meaningfully worsens overall Brier despite its worse point estimate. In truly close games (margin ≤2), calibration and discrimination require more detailed model-state research. We do **not** tune models using held-out test subgroup results.

Audited artifacts: [full diagnostics, CIs and calibration](models/win_probability/wp_robustness_report.json), [summary scores](models/win_probability/wp_strata_summary.csv), [10-bin reliability by strata](models/win_probability/wp_strata_reliability.csv), [publication-oriented interpretation](docs/step2_3_results.md), [reproducible audit source](src/beyond_the_whistle/wp_robustness.py).

```bash
python -m pip install -e ".[dev,ml]"
python -m beyond_the_whistle.wp_robustness --bootstrap 1000
```

**Next:** recover trustworthy pre-decision possession, free-throw, timeout and bonus states, and verify individual L2M incidents against source video before considering causal counterfactual officiating harm.


## Step 2.4 — Frozen inference interface and Step 2 acceptance

**Step 2 is complete as a scientifically documented *post-action win-probability baseline*.** Model improvements for referee counterfactuals (especially possession, foul/bonus, timeouts and **pre-decision state alignment**) remain an explicit Step 3 prerequisite, not a falsely completed feature of the current model.

Predict a hypothetical Q4 game state with the unchanged trained model:

```bash
python -m pip install -e ".[dev,ml]"
python -m beyond_the_whistle.wp_inference \
  --period 4 --seconds-remaining 60 --home-score 105 --away-score 103
# Inspect uncalibrated model instead: add --probability-version raw
```

The CLI enforces period/clock/score/feature-schema sanity checks and emits post-action probabilities **clearly marked as noncausal**. It deliberately does not pretend to simulate the effects of correct referee decisions. Step 2 CI checks the unchanged historical dataset and model SHA-256 digests, earlier measured metrics, saved robustness artifacts and deterministic inference output.

See [Step 2 completion, model card and Step 3 go/no-go research gate](docs/step2_complete.md), [inference implementation](src/beyond_the_whistle/wp_inference.py), and [completion acceptance workflow](.github/workflows/step2_complete.yml).
