# Step 1 — 2024–25 NBA L2M and play-by-play validation

**Status:** All 2024–25 L2M reports have been independently reconciled against the NBA's official JSON; game-level PBP coverage is complete. **Individual-event PBP links have not undergone independent film adjudication.**

## Sources

- Official NBA L2M: `https://official.nba.com/l2m/json/{game_id}.json`, referenced from [NBA 2024–25 L2M index](https://official.nba.com/2024-25-nba-officiating-last-two-minute-reports/).
- Historical structured L2M: [atlhawksfanatic/L2M](https://github.com/atlhawksfanatic/L2M), `1-tidy/L2M/L2M_stats_nba.csv`.
- Regular-season and playoff play-by-play: [shufinskiy/nba_data](https://github.com/shufinskiy/nba_data), `cdnnba_2024.tar.xz` and `cdnnba_po_2024.tar.xz`.
- Two missing 2025 play-in games: ESPN event `401766459` (MEM @ GSW, April 15), and `401766462` (MIA @ ATL, April 18).

All downloaded source files are identified by SHA-256 in `data/validated/l2m_pbp_2025_audit.json`.

## Reproducible results

| Validation | Actual result |
| --- | ---: |
| L2M games | 423 |
| L2M graded/ungraded records | 7,165 |
| Available PBP games: regular season + play-in + playoffs | 1,316 |
| Games with matching Game ID, Eastern game date, home/away | **423 / 423 (100%)** |
| Official L2M JSON reports independently retrieved | **423 / 423 (100%)** |
| Official vs historical report multiset matching, by game | **423 / 423** |
| Official vs historical records matching period, clock, type, grade | **7,165 / 7,165** |
| CC / CNC / IC / INC / ungraded | 2,033 / 4,801 / 66 / 263 / 2 |

The comparison preserves duplicate event keys as a **multiset**, rather than deduplicating events sharing a timestamp. It compares normalized period, period clock (tenth of a second), category text, and decision label. Six early false mismatches were caused solely by equivalent missing-value encodings: `NA` vs `N/A` in four call types and `NA` vs empty decision in two entries. No actual official grade disagreement remained. The upstream CSV was **not modified**.

## PBP linking — statuses are candidates, NOT certified matches

The derived `l2m_pbp_2025_candidates.csv` records the outcome for each L2M item. Candidate logic requires matching Game ID, period, one-second clock proximity, and compatible *broad* event type. We do **not** claim that the same player or incident was established by these checks.

- `unique_clock_type_candidate_unverified`: exactly one plausible PBP event, not independently video confirmed.
- `multiple_clock_type_candidates`: several plausible events; ambiguous.
- `no_clock_type_candidate`: no compatible recorded event; may be semantic/time discrepancy.
- `noncall_not_in_pbp`: CNC/INC; there is normally no corresponding whistle for PBP to join.
- `ungraded`: neither a correct nor incorrect ruling label.

**The 4,801 CNC and 263 INC instances are official rulings, not PBP whistle records.** Their error impact cannot be inferred simply by selecting the nearest recorded play. Nothing in this project computes a comprehensive league-wide referee error percentage.

See `data/validated/l2m_pbp_2025_audit.json` for the precise candidate distribution after all data sources were integrated.

## Research boundary

**Completed:** Public data acquisition; official L2M consistency and game metadata validation; source provenance; conservative PBP candidate mapping; reproducible unit tests and CI.

**Still requiring separate human research:** Stratified, independent video review of event-level candidate matches, including player/possession/violation verification, error logging, and at least two reviewers for agreement assessment. Official-label matching does **not** substitute for independent video-based confirmation or for a causal counterfactual.

Step 2 can proceed on play-by-play game states to train win probabilities. Step 3 **must gate counterfactual officiating analyses** on independently checked events and clearly declared assumptions.
