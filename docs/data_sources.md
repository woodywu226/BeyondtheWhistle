# Data sources and provenance (Step 0)

## 1. Official NBA Last Two Minute (L2M) reports

- NBA current reports: https://official.nba.com/2026-27-nba-officiating-last-two-minute-reports/
- NBA 2025–26 archive: https://official.nba.com/2025-26-nba-officiating-last-two-minute-reports/
- Change to eligibility rules in 2017: https://www.nba.com/news/nba-changes-last-two-minute-reports-2017-18

For recent seasons, NBA describes coverage as games that are within three points at **any point in the final two minutes of the fourth quarter**, including qualifying overtime situations. Reports evaluate whistles and **notable** non-whistles. Official definitions and eligible periods must be verified separately for each historical season.

Grading labels:
- CC: Correct Call
- IC: Incorrect Call
- CNC: Correct Non-Call (not every ordinary unwhistled possession)
- INC: Incorrect Non-Call

**Do not** interpret the observed grade proportion as an unbiased league-wide refereeing error rate. Reports are selectively eligible and notable non-calls are selected.

## 2. Community-maintained structured L2M data

- Repository: https://github.com/atlhawksfanatic/L2M
- Source file used by the optional Step 0 downloader:
  https://github.com/atlhawksfanatic/L2M/blob/master/1-tidy/L2M/L2M_stats_nba.csv

This is a convenient starting point, **not the NBA's certified analysis-ready table**. Field definitions and coverage require verification. Source may change upstream; audit metadata records retrieval time, source URL and SHA-256 hash. Files under `data/raw/` and `data/processed/` remain local and are gitignored.

## 3. NBA Play-by-play (planned: Step 1)

Play-by-play may support game-state reconstruction and event matching. It is **not yet ingested**. Source endpoints, request limits, field schemas, missing values, match quality, and permitted reuse will be documented before use.

## Step 0 validations versus later validation

Step 0 **does**:
- download or load source CSV;
- preserve unmodified source bytes;
- enforce essential columns `season` and `call_type`;
- report grade counts, season counts, missingness, unknown grades;
- record provenance and checksum.

Step 0 **does not**:
- independently confirm grading against NBA official reports;
- reconstruct exact eligibility for every season;
- guarantee event-level uniqueness or correct game IDs;
- match play-by-play or identify individual whistle-blowers;
- estimate error rates, fairness, or counterfactual win probabilities.

## Planned official validation protocol

1. Confirm season-level eligibility and identify report availability.
2. Stratify a sample of game reports by season and grade.
3. Cross-check event time, period, grading, violation type, team, and official notes.
4. Keep a discrepancy log with both original and corrected values.
5. Publish sample coverage and match quality before fitting any models.
