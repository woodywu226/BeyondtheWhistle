# 2024–25 incorrect-call scenario review

The review covers all 66 official incorrect calls in the 2024–25 NBA Last Two
Minute reports. All 66 have a modeled observed-state win probability. Of the
30 cases open after the preceding review, 25 now have a conditional scenario
estimate and five are classified as unidentifiable with the available data
and models.

| Analysis scope | Cases |
| --- | ---: |
| One rule/context-supported modeled comparison | 25 |
| Range over specified scenarios | 18 |
| Fixed-clock sensitivity to observed points from awarded free throws | 18 |
| Corrected effect unidentifiable with available data and models | 5 |
| **Total** | **66** |

- [Final case table](../data/validated/ic_final_scenarios_2024_25.csv)
- [Final 30 reconstructed case inputs, including each modeled branch](../data/validated/ic_followup_cases_2024_25.json)
- [Original score-clock inputs and free-throw components](../data/validated/ic_review_2024_25.json)
- [Original possession inputs](../data/validated/ic_oob_possession_cases.json)

## Reading the table

Every probability is from the perspective of `affected_team`. A percentage-point
change is the alternative estimate minus its branch-specific reference. The score,
clock and possession refer to the specified comparison, often after the immediate
penalty was resolved or the first team gained control. The observed possession is
blank in older score-clock rows when it was not used. An empty alternative means
the corrected effect was not estimated. Ranges reflect specified makes, misses,
recoveries, or tip winners. They carry neither coverage guarantees nor scenario
weights. No model here identifies the causal effect of officiating.

For the 25 additional scored cases, one uses the frozen score-clock baseline
and the other 24 apply the regular-season out-of-bounds possession model as a
proxy. It does not encode the shot clock, inbound location, transition,
shooter skill, or lineup. Some follow-up cases transfer the proxy to live-ball
play, missed free throws, Play-In or playoff contexts. At most two minutes and
five points apart, the prior held-out report found Brier scores of 0.10977
(score-clock logistic) and 0.11001 (possession logistic) on 109 states.
The 2024–25 out-of-bounds holdout contained zero tied states with ten seconds
or fewer remaining. Interpret late tie extrapolations with particular care.

For #6287, the corrected Denver inbound is compared with both possible
jump-ball winners. The observed probability conditions on Denver actually
winning the tip. The comparison reference columns span the two tip branches.
There is no estimated probability of winning that tip. For #4657,
the corrected double lane violation produces a midcourt jump ball. The
two alternative probabilities vary which team obtains the tip.

## Five cases with no estimated correction

| Record | Reason |
| --- | --- |
| #67 | A no-call preserves Devin Booker’s eligibility after what was recorded as his sixth foul. Available models cannot value the lineup and continuation changes. |
| #1108 | A legal block with about one second remaining may send the game to overtime. Available possession estimates lack held-out support for that tied state. |
| #1109 | The foul moves from Jalen Suggs to Anthony Black. The made basket and penalty stay the same. A change due to individual foul counts and lineup response remains unresolved. |
| #2446 | The foul moves from Ivica Zubac to James Harden. The same shooter and penalty apply. Player-specific downstream effects remain unresolved. |
| #3846 | The foul moves from Kessler Edwards to Quentin Grimes. The same shooter and penalty apply. Player-specific downstream effects remain unresolved. |

## Evidence and reproduction

The final 30 records identify the official report and clip, archive or ESPN
source, relevant play IDs, rule sections, state assumptions and limits.
Selected clips were checked for specific details, including the dunk in #3130
and the score and clock in #6727. Independent film adjudication remains pending.
The regular-season and postseason archive fingerprints are recorded in
the [previous review inputs](../data/validated/ic_review_2024_25.json).

- [NBA official report index](https://official.nba.com/2024-25-nba-officiating-last-two-minute-reports/)
- [NBA Rules 6](https://official.nba.com/rule-no-6-putting-ball-in-play-live-dead-ball/), [9](https://official.nba.com/rule-no-9-free-throws-and-penalties/), [10](https://official.nba.com/rule-no-10-violations-and-penalties/) and [12](https://official.nba.com/rule-no-12-fouls-and-penalties/)
- [ESPN Play-In feed](https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401766459)

From the repository root, use the frozen assets and generate the CSV along
with a JSON containing every scored follow-up branch. This requires the model
dependencies from the repository’s `ml` extra.

```bash
python -m pip install -e ".[ml]"
python -m beyond_the_whistle.ic_followup \
  --baseline data/validated/ic_all_scenarios_2024_25.csv \
  --details /tmp/ic_followup_details.json \
  --output /tmp/ic_final_scenarios_2024_25.csv
cmp /tmp/ic_final_scenarios_2024_25.csv data/validated/ic_final_scenarios_2024_25.csv
```
