# Step 2.3 — Clutch Calibration and Game-Cluster Robustness

**Status:** Completed frozen-model, out-of-time diagnostics on the 2024–25 NBA test season. This is **diagnosis, not retraining or new model selection**.

## Motivation

Step 2.2's high ROC-AUC (0.9504) and overall Brier scores are not enough to show that the model is calibrated in decisive last-two-minute states. Game observations are also correlated, so standard bootstrap confidence intervals from randomly resampling individual rows would be misleading.

This stage audits the **exact Step 2.2 fitted Histogram Gradient Boosting model**, comparing its unchanged raw probabilities to the unchanged Platt-scaled probabilities. SHA-256 fingerprints of the fitted model and input dataset are checked against the published Step 2.2 manifest, and the original overall Brier scores are reproduced before any subgroup diagnostics run.

## Method

- **Sample:** 31,429 Q4/OT held-out post-action snapshots from 1,229 2024–25 NBA regular-season games.
- **Predictions:** Previously fitted model; **no additional model fitting, calibration fitting, or hyperparameter tuning**.
- **Calibration:** 10-bin reliability tables and Expected Calibration Error (ECE), both ordinary state-weighted and game-balanced (one unit of total weight per game *inside each stratum*).
- **Subgroups:** Q4, OT, clock ranges (≤30, 30–60, 60–120, 120–300, >300 seconds), absolute score-margin bands (0–2, 3–5, 6–10, >10 points), last 120 s with margin ≤5, last 30 s with margin ≤3, and last 120 s with margin >5.
- **Uncertainty:** 1,000 paired **game-cluster bootstrap** replicates (seed 226). Each complete game is resampled as a unit. Each sampled game contributes its mean snapshot Brier or log loss equally. 2.5th and 97.5th percentiles provide conditional 95% intervals. No CI is created for subgroups with fewer than 30 participating games.
- **Primary comparison:** Platt minus raw game-balanced Brier. Positive difference means Platt is *worse* in point estimate. Intervals spanning zero do not support a definitive direction.

We intentionally do **not** compare 95% CI for raw and calibrated performance as if independent. The **paired** difference is the correct bootstrap quantity because predictions share the same observations and games.

## Results: full test and clutch subgroup

| Subgroup | Games | States | Raw game Brier ↓ | Platt game Brier ↓ | Raw game ECE ↓ | Platt game ECE ↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| All Q4/OT | 1,229 | 31,429 | **0.08518** | 0.08564 | **0.00902** | 0.01659 |
| ≤120 s, margin ≤5 | 450 | 1,667 | **0.09852** | 0.09927 | **0.02475** | 0.03416 |
| ≤30 s, margin ≤3 | 214 | 243 | **0.07845** | 0.07951 | **0.02243** | 0.03546 |
| Overtime only | 60 | 704 | **0.16498** | 0.16820 | **0.04413** | 0.05549 |

*ECE uses 10 fixed probability bins; it is not itself a proper scoring rule, is resolution-sensitive and can be biased in small samples. The game-balanced ECE reweights participating games within each subgroup.*

### Paired game-cluster bootstrap, Platt minus raw

| Subgroup | Difference (game Brier) | 95% percentile interval |
| --- | ---: | ---: |
| All Q4/OT | +0.000466 | [−0.000748, +0.001623] |
| ≤120 s, margin ≤5 | +0.000750 | [−0.001235, +0.002700] |
| ≤30 s, margin ≤3 | +0.001056 | [−0.002399, +0.004250] |
| OT only | +0.003218 | [−0.004572, +0.011807] |

All four intervals include zero; the modest observed worsening is **not distinguishable from zero by these intervals**. No assertion of a globally harmful Platt transform is warranted on these results alone.

### Score margin is a major determinant of difficulty

| Absolute margin | Games | States | Raw game Brier | Platt game Brier |
| --- | ---: | ---: | ---: | ---: |
| 0–2 points | 536 | 4,624 | **0.21665** | 0.21803 |
| 3–5 points | 674 | 4,850 | 0.16121 | 0.16058 |
| 6–10 points | 830 | 6,773 | 0.11054 | 0.11204 |
| >10 points | 903 | 15,182 | 0.03862 | 0.03941 |

Importantly, **easy blowouts dominate apparent model accuracy** in the widest strata. The very low Brier score for the entire last 30 seconds is not proof that last-30-second *close games* are easy: conditioning on a narrow margin changes the difficulty and the case mix. The game-balanced score of 0.21665 at 0–2 points overall is the most prominent warning for Step 3 causal scenarios.

There are no multiple-testing corrections for the many descriptive subgroup comparisons. We should not promote any subgroup pattern into a statistically confirmed systematic effect without a separate registered test.

## Research interpretation

1. **Clutch model fitness is not yet proven.** The model omits possession, bonus/penalty state, pending free throws, timeouts, lineups and team effects. These become especially important in close, late-game situations.
2. **No post-hoc model switching.** We report both predictions without choosing a winner using the held-out season. Any alternative calibrator, score-only feature revision or hyperparameter choice must use earlier seasons (or genuinely new prospective data).
3. **Observed-versus-corrected worlds:** The model predicts *post-action* win probability; an officiating counterfactual requires consistent *pre-decision* snapshots. Neither a Brier score nor a change in post-action WP identifies causal referee harm.
4. **Uncertainty scope:** The cluster intervals quantify held-out game-sampling variability conditional on the **fixed fitted model**. They exclude model-fitting and calibration-estimation uncertainty and do not guarantee accuracy on playoffs, Play-In, or later seasons.
5. **Selection and estimand:** These snapshots are selected from bins with PBP events, rather than a uniform real-time clock. The subgroup ECE weights game appearances within each stratum; the population of officiating decisions may have a different state distribution.

## Output artifacts and reproduction

- [Source code](../src/beyond_the_whistle/wp_robustness.py)
- [Full per-stratum JSON audit](../models/win_probability/wp_robustness_report.json)
- [Concise subgroup score table](../models/win_probability/wp_strata_summary.csv)
- [Ten-bin reliability table](../models/win_probability/wp_strata_reliability.csv)

```bash
python -m pip install -e ".[dev,ml]"
pytest -q
ruff check .
python -m beyond_the_whistle.wp_robustness --bootstrap 1000
```

A successful CI run asserts the original 2024–25 Brier scores match their Step 2.2 records to numerical tolerance, and checks source/model fingerprints, group counts, confidence intervals and bin coverage.

## Publication-oriented next steps

1. Define a defensible **pre-decision** snapshot and a directly observed possession/penalty/timeout state, with independent event verification.
2. Compare improved models under **new**, preplanned chronological validation rather than tuning on the 2024–25 test set.
3. Add prospective-season or rolling-origin external validation, cluster-aware calibration assessment and uncertainty in the model-fitting process.
4. Only then explore incident-level **scenario-based corrected officiating states**. Do not report unique causal competitive loss without defining and justifying intervention and identification assumptions.

**Bottom line:** Step 2.3 does not show calibrated close-game impact is solved. It identifies exactly why the existing model needs more research before publishing officiating-related counterfactual estimates.
