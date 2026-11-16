# Step 3 video pilot

**Status:** Sampling, calibration materials, reviewer worksheets and scoring code
are ready. The official 2024–25 L2M index and verified play-by-play identify
the sample. Full-game replay access and two independent human reviews are
still required to measure officiating accuracy or reviewer agreement.

## Locked design

- **Question.** In these games, how do observed whistles and independently
  judged incorrect calls and missed calls differ between Q4 4:00–2:00 and
  2:00–0:00?
- **Selection.** Ten 2024–25 regular-season games have a six-point margin in the
  last recorded state strictly before 2:00. Five have an official L2M report and
  five do not. The builder selects five per stratum using deterministic SHA-256
  ranking with a fixed salt, omitting games in the calibration queue. Report
  availability is a retrospective sampling stratum. A report can qualify based
  on subsequent score movement, so this comparison cannot identify a causal
  effect of scrutiny. The sample targets this exact margin and is a feasibility
  sample.
- **Coverage.** Review 200 consecutive 12-game-clock-second segments, 20 per
  game and 100 per window. Play at exactly 2:00 belongs to the later window.
  A segment includes its starting clock and excludes its ending clock except
  the final segment, which includes 0:00. Include held-clock events only once,
  at their occurrence in the action sequence. Full games supply context and
  playback, with primary coding limited to the four-minute window.
- **Target.** Aim for 150–250 unique incidents over 10 games. Review all fixed
  segments and retain all eligible incidents, even if the total is outside the
  target. Record the deviation and reasons. The 200 segments and [224 exploratory PBP locators](../data/validated/step3/candidate_locators.csv)
  count different units from incident labels. The 224 locators include all
  recorded field-goal attempts plus 68 foul, turnover and violation rows.
  Some are duplicates of the same physical play and others may show no
  relevant contact. Uncalled incidents can occur away from any locator.

## Run the review

1. **Check replay access.** Open [games.csv](../data/validated/step3/games.csv) and
   use the NBA game links or find the full replay in League Pass by date and
   teams. Record the feed/version and use it for both reviewers where possible.
   Share [video segments](../data/validated/step3/video_segments.csv) and the
   appropriate segment log. Share clean worksheets without the report-status
   column, official grades, or prior model outputs. Game clock, score and
   commentary may remain visible. Log any inadvertent unmasking.
2. **Calibrate.** Give each reviewer
   [calibration locators](../data/validated/step3/calibration_locators.csv)
   and their own calibration label sheet. Reviewers use the game, clock and
   replay, independently entering first-pass labels. Several plays may share a
   displayed clock. If the intended incident cannot be isolated, mark
   `indeterminate` with a reason. Preserve first-pass answers. Only after
   submission may the coordinator open the
   [calibration key](../data/validated/step3/calibration_key.csv) and the
   [original queue](../data/validated/step1_review_queue_2025.csv) for discussion.
   Trial the codebook and log changes before seeing formal-sample results.
3. **Discover independently.** Each reviewer watches every assigned segment
   and logs elapsed review seconds, completion or unavailability, and how many
   new possessions begin in it. Work from video first. Use
   [the discovery template](../data/validated/step3/discovery_template.csv)
   for private notes. Register all visible referee whistles for on-court rulings,
   all potentially illegal unsanctioned actions material to play, and one
   unwhistled ordinary contact opportunity per observed possession when one is
   visible. Choose the first eligible ordinary contact in that possession in
   game order. Exclude administrative stops such as timeouts, substitutions,
   reviews that duplicate a ruling, and routine clock signals. Record player,
   court location and replay timestamp using neutral descriptions.
4. **Merge locators.** The coordinator takes the union of separately submitted
   locators. Deduplicate by game, physical incident and action order. Use clock
   only for navigation. Relate each incident to its containing segment and
   assign one ID in `incidents.csv`. Use one row per physical incident even if
   it has multiple PBP rows. The [PBP locator file](../data/validated/step3/pbp_locator.csv)
   is a supplementary completeness check after video discovery. Use this stage
   to resolve clip location while withholding proposed labels, source reports,
   and which reviewer nominated the incident.
5. **Rate the merged set.** Each reviewer fills their own label sheet with only
   the incident ID, label, locatability, replay timestamp, review time and reason.
   Record `video_timestamp` against the actual replay stream (HH:MM:SS or decimal
   seconds); the game clock is already in the incident roster. Record `no` for
   locatability if the physical incident cannot be found and explain why.
   For ambiguous or unavailable sequences, retain the explanation and video
   information that is actually known. Save independently before discussing
   disagreements. Never put a consensus result in either raw rater sheet.
6. **Adjudicate.** Keep all first-pass ratings. Record a final ruling and rule
   basis in `adjudication.csv` when raters disagree, and retain indeterminate
   outcomes where visibility is insufficient. Where independent possession
   counts disagree, reconcile in `possession_adjudication.csv` with a reason.
   The coordinator records whether a whistle occurred (`yes`, `no` or
   `uncertain`) independently of the correctness label, then records whether
   each event belongs to a possession that
   started in the same 2-minute window using `yes`, `no` or `uncertain`.
   Log reviewer pseudonyms, codebook version, replay source and timestamps of
   submitted files privately and retain original worksheets.

## Codebook

| Label | Apply when |
| --- | --- |
| CC | Whistle and resulting on-court ruling are supported by the rule and the visible action. |
| IC | Whistle is wrong, or the observed ruling such as possession award or foul attribution is wrong. |
| CNC | A specific plausible infraction was considered, and a no-call is supported. |
| INC | A material violation or foul warranted a whistle, and no whistle was issued for it. |
| normal_contact | Routine legal contact is visible and did not present a plausible infraction. This is a reference opportunity. |
| indeterminate | The angle, missing action or ambiguous rule application prevents a supported judgment. |

Team control starts with the inbound gaining control on the court, a defensive
rebound, a controlled steal, or equivalent clear team control after a restart.
Offensive rebounds and interrupted play with the same control are continuations.
Use context immediately before the window to identify carry-in control.
Free-throw sequences alone do not create new possessions. Code the underlying
ruling once and retain the possession that generated it. Whistles with no
associated established possession are logged but are excluded from the rate per
possession. Review the codebook against the [NBA rulebook](https://official.nba.com/rulebook/).

## Baseline and measurement

| Archive records | Q4 4:00–2:00 | Q4 2:00–0:00 |
| --- | ---: | ---: |
| Foul action rows | 17 | 32 |
| Turnover action rows | 9 | 10 |
| Violation action rows | 0 | 0 |
| Game-clock minutes | 20 | 20 |

These are raw action rows. Composite events can produce a foul and a turnover
row. Non-whistles and rule correctness need video. There are currently no
independent ratings, kappa, or measured review times.

The analysis reports raw agreement, the six-category Cohen’s kappa and the
confusion matrix from paired original labels. Kappa is undefined when expected
agreement is one or there are no pairs. Also report locatability per rater,
indeterminate fraction, adjudication counts, screening and labeling time, and
window-level correct/incorrect call and non-call rates. Report possession-based
rates only for whistles whose linked possession starts in the same window.
Report indeterminate cases separately and give each accuracy denominator.
Within-game differences use only games with two fully screened windows and
defined rates. Treat findings as descriptive, with small-sample and tactics
limitations. Coverage, label completeness, agreement and the final candidate
count should all be reported before interpreting differences.

## Reproduce

From the repository root:

```bash
curl -fL https://raw.githubusercontent.com/shufinskiy/nba_data/main/datasets/cdnnba_2024.tar.xz -o /tmp/cdnnba_2024.tar.xz
PYTHONPATH=src python -m beyond_the_whistle.step3_pilot build \
  --archive /tmp/cdnnba_2024.tar.xz --output /tmp/step3-review
PYTHONPATH=src python -m beyond_the_whistle.step3_pilot summarize \
  --input /tmp/step3-review --output /tmp/step3-summary.json
```

The builder checks the recorded archive fingerprint and requires an empty
output directory. Enter review results in a working copy, then run
`summarize` again. Empty inputs report an awaiting-review status and missing
rates. The [baseline JSON](../data/validated/step3/baseline.json) and
[per-game action counts](../data/validated/step3/pbp_counts.csv) come from the
verified source. Game URLs refer to the NBA game pages. Availability of the
full licensed replay is unverified.
