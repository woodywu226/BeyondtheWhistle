# Step 1: Real NBA L2M–play-by-play integration results

**Status:** 2024–25 full regular-season/playoff game-level integration complete; missing play-in games and manual event-level verification remain open.

## Independent public data sources

1. [atlhawksfanatic/L2M](https://github.com/atlhawksfanatic/L2M/blob/master/1-tidy/L2M/L2M_stats_nba.csv): community-structured NBA L2M adjudications, with `decision` (CC/CNC/IC/INC), game ID, clock, period, date and teams. Not independently audited against every official report.
2. [shufinskiy/nba_data](https://github.com/shufinskiy/nba_data): 2024–25 regular-season `cdnnba_2024.tar.xz` and playoff `cdnnba_po_2024.tar.xz`, derived from NBA CDN play-by-play. They contain action number, clock, type, game ID, team and score.
3. [NBA official L2M archive](https://official.nba.com/2024-25-nba-officiating-last-two-minute-reports/): primary definition and source for future per-event spot checks.

Source URLs and SHA256 checksums are saved in the audit JSON, allowing exact provenance checks even if upstream data changes.

## Actual 2024–25 data results

| Property | Observed |
| --- | ---: |
| PBP games across regular season and playoffs | 1,314 |
| L2M report games | 423 |
| L2M records | 7,165 |
| Game ID, local ET game date, home/away agreement | 421 games (99.53%) |
| Games unavailable from chosen PBP archives | 2 |
| Unmatched records from these games | 53 |
| CC / CNC / IC / INC | 2,033 / 4,801 / 66 / 263 |
| Ungraded | 2 |
| Unique time-and-type candidates (not definitive) | 1,599 |
| Multiple compatible candidates | 156 |
| No compatible candidate | 329 |
| Documented noncalls requiring separate review | 5,026 |

The two uncovered games are **NBA Play-In** games: `0052400121` and `0052400201`. They are not included in the regular-season and playoff archives used for this build. The missing games do not invalidate the 421 game-level metadata matches; they do prevent a claim of 100% L2M game coverage.

## Definition of a candidate match

For each **called** L2M record (CC or IC), we require:
- identical normalized 10-digit game ID;
- identical quarter or overtime period;
- compatible PBP action category (foul or turnover/violation);
- period clock difference no greater than one second;
- source game date and home/away team consistency.

Exactly one compatible event yields `unique_clock_type_candidate_unverified`. Zero or multiple compatible events are not treated as matched. We do **not** claim confirmed identical player involvement, exact violation subtype, correct possession, or full official-report verification for these candidate links.

For **CNC** and **INC**, the play was not whistled by definition. Play-by-play generally lacks an identifiable officiating action for such events, so the status remains `noncall_not_in_pbp`; these cannot be inferred to be correctly or incorrectly *matched* by temporal proximity.

## Scientific limitations

- Historical NBA L2M reports select only qualifying close games and notable noncalls. The sample cannot represent all NBA refereeing.
- The official `decision` label describes the league's retrospective assessment, but scraping and transformations can introduce errors.
- Some game periods may contain multiple actions at the same timestamp. Clock-only matches are insufficient.
- PBP event categories can differ from the nuanced report violation subtype.
- 123 duplicated *reduced* record-key combinations do **not** necessarily indicate duplicate original source rows; several legitimate actions can share clock/type.
- No individual-official blame or error rate is identified.
- No win probability model, counterfactual correction, or policy-effect estimate has been fitted.

## Minimum additional work before Step 2

1. Acquire missing play-in games or explicitly exclude them from the primary cohort.
2. Manually validate a stratified sample of CC, IC, CNC and INC against current official L2M reports and accessible game footage, recording discrepancies.
3. For called events, use player/team and detailed violation text to disambiguate same-clock cases; do not automatically assume high match confidence.
4. Resolve matchup and possession state with explicit error labels; distinguish corrected calls from corrected noncalls.
5. Publish event-match precision from a **manually adjudicated reference sample**, not from automated candidate counts.

**Interpretation:** Step 1 demonstrates extensive real-data acquisition and metadata consistency (421/423 L2M games), but it is **not** a complete verified event-level linkage.
