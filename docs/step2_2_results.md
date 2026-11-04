# Step 2.2 — Results from a held-out NBA season

**Status:** Trained, tested and saved on the 2024–25 independent test season. These scores estimate **post-action home-team win probability**, not the causal impact of officiating decisions.

## Reproducible training protocol

- **Train:** 2021–22 and 2022–23; 2,448 games, 62,901 states.
- **Model selection:** first 738 game IDs from 2023–24; 18,898 states.
- **Probability calibration:** remaining 492 games in 2023–24, disjoint from selection; sigmoid Platt fit on a selected model's raw log odds.
- **Held-out testing:** all 1,229 valid 2024–25 games, 31,429 late-game states.

Model fitting, calibration and Brier evaluation use **per-game inverse-snapshot weights** to reduce domination by games with more recorded action states. An additional ordinary state-level score is also reported.

The model inputs are contemporaneous period, period clock, home/away score, their margin, elapsed time in period, combined score, and the margin–clock interaction. No outcome, final margin, test-season statistics or official L2M judgment is an input.

## Model selection on 2023–24 selection subset

| Candidate | Game-balanced Brier (lower is better) | ROC-AUC |
| --- | ---: | ---: |
| Histogram Gradient Boosting | **0.08700** | 0.94880 |
| Logistic Regression | 0.08713 | 0.94863 |

Histogram Gradient Boosting was selected **before seeing 2024–25 results**. The difference is small and does not demonstrate that boosting is universally superior.

## Held-out 2024–25 test metrics

| Model / treatment | State Brier ↓ | Game-balanced Brier ↓ | State Log Loss ↓ | ROC-AUC ↑ |
| --- | ---: | ---: | ---: | ---: |
| Constant training home-win frequency | 0.24843 | 0.24835 | 0.69001 | 0.5000 |
| Selected model, no Platt calibration | **0.08978** | **0.08518** | **0.28166** | 0.9504 |
| Selected model + Platt calibration | 0.09041 | 0.08564 | 0.28542 | 0.9504 |

AUC measures discrimination and is invariant to monotonic Platt scaling in this case. **Important negative finding:** The explicit Platt calibrator slightly worsened both Brier and Log Loss on this held-out season. This is reported as observed, not obscured. It suggests later calibration comparison/diagnostics, not permission to select an uncalibrated version by retrospectively optimizing the untouched test set.

The **game-balanced** calibrated log loss was 0.27077 compared with 0.26795 without calibration.

### Most relevant clutch subset

For fourth-quarter or overtime states with **120 seconds or fewer remaining** and a **margin of five points or fewer**, the calibrated model was evaluated on 1,667 states across 450 distinct games:

- State Brier: **0.13491**
- Game-balanced Brier: **0.09927**
- State log loss: **0.41485**
- ROC-AUC: **0.89486**

The smaller and harder clutch sample makes the score less favorable than overall Q4/OT metrics. This domain is especially important for downstream L2M counterfactual analysis and should receive further calibration scrutiny.

## Saved outputs

- `models/win_probability/wp_baseline.joblib`: sklearn boosting model and separately fitted Platt logistic calibrator. Loading joblib can execute code; load trusted bundles only.
- `models/win_probability/wp_model_report.json`: complete actual selection/test scores, split protocol and SHA-256 provenance.
- `models/win_probability/wp_test_predictions.csv`: predictions and labels for all 31,429 held-out states.
- `models/win_probability/wp_test_calibration.csv`: ten probability bins (mean predicted, actual win rate and sample size).
- `src/beyond_the_whistle/wp_model.py`: reproducible training and reporting code.

Reproduce with:

```bash
python -m pip install -e ".[dev,ml]"
pytest -q
ruff check .
python -m beyond_the_whistle.wp_model
```

## Interpretation and limitations

1. **Post-action, not pre-whistle.** The chosen model sees the score immediately after a PBP action. Counterfactual offending decisions will need precisely aligned pre-decision state reconstruction in Step 3, or score changes will be attributed incorrectly.
2. **Observation dependence.** State observations from one game are correlated. Game-balanced metrics are not independent-game confidence intervals. A game-cluster bootstrap is recommended before publication.
3. **Missing game-state variables.** Possession, expected free throws, bonus, timeouts and team strength can be material in the last two minutes. The high overall AUC does not establish adequate probability accuracy for unusual rulings.
4. **Calibration risk.** Platt scaling modestly degraded held-out Brier and log loss; class probability calibration for rare late-game situations requires additional research. Use the reliability CSV, not only AUC.
5. **Target sampling.** The Step 2.1 dataset chooses a late-game post-action snapshot per 30-second clock bin, not a uniformly spaced real-time series; late-game scoring/clock regime is consequently overrepresented relative to all possessions.
6. **No causal officiating result.** L2M labels were not used in training. This step does not quantify an incorrect-call harm or propose an empirically validated refereeing reform.

**Next step:** Compare reliability by remaining-time and margin strata; test temporally validated richer possession/timeout state features, and introduce independent uncertainty and two-sided corrected-state simulations only after event matching is verified.
