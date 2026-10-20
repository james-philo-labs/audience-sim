# 3DCodeVerse nine-run editorial diagnostic

Recorded October 20, 2026. **KEEP source-reconciled baseline A.** No new source-supported correction or recurring editorial issue warranted a candidate edit. No B was created, so no A/B improvement is estimated. High ratings and nine selected finishes are model outcomes, not human-reader accuracy or publication approval.

[Explore the study](https://philo-audience-lab.vercel.app/) · [Nine-row CSV](../results/3dcodeverse-2026-10-20/runs.csv) · [Public study JSON](../results/3dcodeverse-2026-10-20/study.json)

## Input and conditions

One frozen article, *From a Prompt to an Inspectable 3D Program*, pinned to the [34-page public arXiv v1](https://arxiv.org/abs/2610.22341v1). Baseline A contains 14 source corrections made before simulation. KEEP retains them; source review is not simulator-driven uplift. Article SHA-256: `996d6795caf316e053f60fc460fa3464ef05784c56e42e0b13d753a4840c3279`.

Three fresh contexts per authored role, using `gpt-6-luna`, low reasoning, 1440×900 desktop, muted audio and motion on request. No explicit seed or temperature, immutable model-weight snapshot or cross-session memory. Controlled layout preserves the cover, seven body images, three videos, paired inset, table and external comparison label; it is not a verified CMS replica.

Per-session limits: 48 decisions, 600 simulated active seconds, 900 wall seconds and $1 conservative usage guard. No automatic retries or replacement sessions. The separate live integration pilot and authored controls are excluded from study denominators.

## All nine assigned outcomes

| Role | Rep | Termination | Interest / 5 | Simulated active s | Rejected actions | Revision |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| visual-agent-researcher | 1 | finish | 4.5 | 142.54 | 0 | KEEP |
| visual-agent-researcher | 2 | finish | 5 | 225.21 | 0 | KEEP |
| visual-agent-researcher | 3 | finish | 5 | 240.06 | 0 | KEEP |
| post-training-engineer | 1 | finish | 5 | 82.90 | 1 | KEEP |
| post-training-engineer | 2 | finish | 5 | 112.90 | 0 | KEEP |
| post-training-engineer | 3 | finish | 5 | 236.90 | 0 | KEEP |
| evaluation-researcher | 1 | finish | 5 | 136.40 | 0 | KEEP |
| evaluation-researcher | 2 | finish | 5 | 196.90 | 0 | KEEP |
| evaluation-researcher | 3 | finish | 5 | 129.10 | 1 | KEEP |

Assigned / attempted / audited: **9 / 9 / 9**. Natural finishes: 9; abandonments: 0; caps: 0; failed or unaudited: 0; pending: 0. All nine recommend KEEP. No confusing claim or drop-off passage was nominated; absence of a report does not establish comprehension.

Interest is a retrospective model self-rating with shared 1/3/5 anchors, not a calibrated audience score. Finish requires closing exposure plus a selected finish action; it does not certify full reading. Eight ceiling ratings offer little differentiation. Repetitions are same-model variation, not sampled people.

## What changed the editorial decision

The review covered 18 cited findings and 62 citation references. Eight of nine takeaway citation sets reuse the closing paragraph about a bounded falsifiable brief, evidence retention and comparison including human work. KEEP rationales mostly reiterate existing result limits. No new source correction or recurring edit-worthy friction reached the two-of-three within-role review heuristic; the heuristic is not statistical confidence.

Compared with the three assistant-assisted concerns recorded before inference:

- **Next step and artifact access:** models identify a conceptual experiment from the closing. The broader concern is weakened; practical code/dataset discovery remains untested because off-site navigation was unavailable.
- **Mechanism and evidence distinctions:** useful checks/repair themes are retained. Some model rationales blur rendered comparisons into workflow results or call reported observations hypotheses. Preserve the draft's narrower qualifiers; do not reuse those loose rationales as verified claims.
- **Application/external-clip relevance:** no edit nominated. The three visual-agent sessions played only portions of the robot clip; butterfly and external poker clips were unplayed. Relevance and source comprehension remain untested.

Codex reviewed support; no independent human adjudication is claimed. Exact revealed-fragment integrity does not prove general truth, and some selected fragments need adjacent context for standalone reuse. Incremental editorial value beyond close review remains unproven.

## Clocks, paths and media

Simulated finish seconds range from 82.90 to 240.06. Per-role medians and min–max: visual 225.21 (142.54–240.06); post-training 112.90 (82.90–236.90); evaluation 136.40 (129.10–196.90). These are conditional model-clock summaries, not human confidence intervals.

The active clock sums elicited reading, source advancement and authored interaction costs, subtracting read/play overlap once. All nine values fall below 333.6–500.4 seconds from text-only scenarios at assumed 300–200 WPM. Those assumptions are not a measured reference; no correction factor is applied.

All nine paths show zero backward scrolls and zero seeks. Multi-section dwell remains unallocated; zero allocated time does not prove a skip. Visual-agent robot-clip unique advancement was 7.044475, 4.005730 and 8.058711 seconds. One inline read/play overlap of 4.049586 seconds is subtracted once. Models saw sampled frames, not continuous native video or audio. The study JSON and deployed run selector expose every path and section accounting record.

## Rejected actions and recovery

1. `a-posttraining-01`, action 14: close an absent overlay. Executor error: `Target not currently visible/available`; 0.5 s interaction, zero reading/playback. Next scroll succeeds in the original session.
2. `a-evaluation-03`, action 16: model says the closing was reached, executor state says otherwise. Error: `Closing main paragraph not reached`; 0.2 s interaction, zero reading/playback. The session continues to the actual closing and finishes.

Neither is dislike, abandonment or a missing article asset. No exact signature recurs across two sessions, so the declared recurring-blocker stop was not triggered. Both are policy state-tracking errors; executor state controls exposure and termination.

## Reader comparison and uncertainty

Independent human outcomes: **0**; collection excluded. Agreements, mismatches, comprehension and predictive accuracy are unavailable, not zero. `confidence_interval: null`, `coverage: unknown`, `calibration_status: not_calibrated`. Model self-ranges and repeated contexts do not establish human confidence coverage. First-viewport forecasts and whole-text forecasts have different access; neither becomes an observed completion rate. No new whole-text study or human collection was performed for this publication.

## Cost and effort

Main nine: 253 submissions, recorded published-rate estimate **$1.13577409**. Separate pilot: 29 submissions, **$0.1310512**. Total: 282 submissions, **$1.26682529**. Conservative guard estimate **$2.530242**, within the aggregate $20 ceiling. Returned usage is complete; no invoice was observed. Estimates exclude conversation/research tools and human labor.

Runtime: main nine 1,481.089 wall seconds (24.68 min), pilot 236.572 seconds (3.94 min). Source preparation, implementation, fixtures, inspection, audits, exception review and reporting add operating effort. Human active effort and complete operating cost are unknown. No time-saving or ROI claim. Publication adds zero inference calls.

## Bounded next decision

Retain A. Useful framing hypotheses are inspectable spatial representations for visual-agent research; code/check/repair records as candidate post-training material; and the distinction between a score, declared requirements and human acceptance for evaluation research. These are editorial interpretations, not measured audience preferences. Reconsider only for a concrete source error or specific new reader friction; do not expand the simulator merely to generate a more favorable score.

## Public provenance

The JSON/CSV are a deliberately selected derivative of sealed local assignments, executor audits, clock summaries and semantic review. They preserve all nine outcomes, rejected actions and exclusions. Full unpublished article/media, raw requests, workstation paths, session identifiers and private operational records are excluded. Hashes bind the declared article, but this public summary alone cannot independently reproduce or attest the original live calls. The [earlier Opus study](case-study.md) remains separate, including its exclusions and proposed reader study.

[Design enhancements](design-enhancements.md) · [Metric dictionary](metrics.md) · [Publication scope](publication-scope.md)
