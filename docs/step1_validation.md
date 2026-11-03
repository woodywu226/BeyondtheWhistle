# Step 1 — L2M and NBA Play-by-Play integration

## Verified upstream schemas

The community [atlhawksfanatic/L2M README](https://github.com/atlhawksfanatic/L2M) explicitly documents:
- `call_type`: kind of violation, **NOT** the correct/incorrect grade.
- `decision`: CC/CNC/IC/INC or blank for ungradable decisions.
- `gid`, `GAME_ID`, `GameId`: candidate NBA game identifiers.
- `time` and `period`: period clock and quarter.

The [nba_api V3 schema](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/playbyplayv3.md) documents `gameId`, `period`, `clock`, `actionId`, `actionType`, and `description`.

## Running Step 1

After `python -m pip install -e ".[dev]"`, run:
```bash
python -m beyond_the_whistle.prepare_l2m
python -m beyond_the_whistle.ingest_pbp --game-id 0022400001
python -m beyond_the_whistle.match_events --pbp data/processed/pbp/0022400001.csv
```

**Note:** NBA Stats may block automated requests or limit access; the scripts fail clearly instead of emitting fabricated results. An already downloaded NBA-format play-by-play JSON can be supplied with:
```bash
python -m beyond_the_whistle.ingest_pbp --game-id 0022400001 --input-json /path/to/pbp.json
```
For the match script, the `--pbp` argument accepts one normalized PBP CSV. The L2M input may cover multiple games; rows for other games are retained as having no candidate. Bulk fetching is deliberately not implemented until access/permissions, retries and rate limits are resolved.

## Interpretation of matching statuses

- `unique_temporal_candidate_unverified`: exactly one PBP event within ±2s; **NOT a verified same-play link**.
- `ambiguous_temporal_candidates`: multiple events; needs manual review.
- `no_temporal_candidate`: none within window, possibly an off-ball event.
- `noncall_requires_video_review`: an INC/CNC should never be automatically matched merely by clock proximity.
- `missing_game_id`, `invalid_period_or_clock`, `ungraded_or_unknown_decision`: insufficient or non-gradable source data.

No success rates or real-game match statistics are asserted until real data has been fetched and audited.

## Required next validations

1. Run on actual L2M source CSV, inspect header, grade frequencies and game IDs.
2. Fetch several actual, documented L2M games with valid PBP responses.
3. Stratify a manual comparison to official NBA report event times/descriptions.
4. Account for missing/noncall events and distinguish event alignment from judgment validity.
5. Add score, foul-category and possession consistency checks where available.
6. Publish a machine-readable audit with provenance, SHA hashes, reviewed samples and discrepancies.

## Research integrity

Closeness in time cannot identify whether an event was the *same foul*. Two events can share the same timestamp. Non-calls frequently have no PBP action. Crew-level attribution is not individual-referee identification. Historical reporting/selection rules differ by season. No causal inference or verified error impact is included in Step 1.
