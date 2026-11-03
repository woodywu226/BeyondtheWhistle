# Research protocol — draft (Step 0)

## Primary estimand

For selected **officially confirmed incorrect decisions** with reconstructable consequences, estimate the difference between (a) the modeled winning probability under observed game state and (b) the modeled expected winning probability under a corrected decision. This is a **model-dependent counterfactual**, not a verified causal effect or a claim that the winner would change.

## Cohort

Primary: NBA games with an official L2M report under the **season-specific** report eligibility rules. L2M does not cover all Q4 games with score margin <= 10 during the final five minutes.

Future extension: Q4 final five minutes and margin <= 10, **only after additional independent video labeling**. No unreviewed earlier events will be labeled correct.

## Outcomes and bias safeguards

- Stratify by call versus non-call and violation category.
- Report grade counts but do not compute a universal officiating error rate from selected CNC events.
- Do not assign an error to an individual official based solely on crew membership.
- Split train/test chronologically for future probability models.
- Compare baseline model calibration and uncertainty in clutch conditions.
- Treat policy-intervention effectiveness as assumptions until externally validated.
- Consider official report revisions, selection mechanisms and missingness.

## Milestones

- **Step 0:** source registry, package setup, reproducible downloader, schema QA, README, tests.
- **Step 1:** season-level NBA L2M report audit and play-by-play ingest/matching.
- **Step 2:** calibrated win-probability baseline.
- **Step 3:** reconstructable counterfactuals and uncertainty analysis.
- **Step 4:** contextual fairness/descriptive crew-level patterns.
- **Step 5:** scenario-based low-disruption intervention evaluation.

No model or empirical research findings are claimed in Step 0.
