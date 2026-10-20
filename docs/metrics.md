# Audience simulation metric dictionary

The unit is one article × one authored role × one declared condition. Keep model judgments, executor accounting and human measurement separate. There is no composite engagement score.

## Session termination

**Origin:** Executor event and audit.

Finish, explicit abandon, action/time/wall/cost cap, or failure. Every assigned attempt remains in the denominator.

**Interpretation:** Finish requires closing exposure plus selected finish. Caps are censoring; errors are not disinterest.

**3DCodeVerse:** 9 finishes; 0 abandonments, caps or failed sessions.

## Early exit reason

**Origin:** Review annotation of explicit action/final rationale.

Goal satisfied, lost interest, confused, irrelevant, technical blocker, or unknown, when an actual early exit occurs. Preserve the raw termination separately.

**Interpretation:** Do not infer motives from dwell, a rejected action, or a model claim about position.

**3DCodeVerse:** No early exits. Reason is not applicable; human motives are unmeasured.

## Interest

**Origin:** Retrospective model self-rating, 1–5.

Shared anchors: 1 little relevance; 3 relevant but no clear next step; 5 a concrete research/workflow idea worth pursuing. Retain the cited rationale.

**Interpretation:** An authored rubric, not a calibrated audience score. A model self-range is not a confidence interval.

**3DCodeVerse:** Eight ratings of 5 and one of 4.5; weak differentiation at the ceiling.

## Section dwell

**Origin:** Derived simulated intervals and visible section IDs.

Allocate reading/playback to clearly identified sections; keep interaction overhead separate and subtract overlapping read/play time once. Ambiguous multi-section time stays unallocated.

**Interpretation:** Longer time may reflect interest, confusion or a policy choice. Exposure is not attention; zero section allocation does not prove a skip.

**3DCodeVerse:** One read/play overlap (4.049586 s), subtracted once. Multi-section dwell remains unallocated.

## Finish time

**Origin:** Simulated active clock, conditional on audited natural finish.

Read duration + playback advancement + authored interaction costs − overlapping read/play intervals. Partial reads receive no finish time. System wall time is a separate clock.

**Interpretation:** Not human reading time. Min–max across three contexts is descriptive model variation, not a confidence interval.

**3DCodeVerse:** 82.90–240.06 simulated seconds. All below the assumed text-only 333.6–500.4 s scenarios; no calibration factor applied.

## Reading path

**Origin:** Ordered executor observations and actions.

Record encountered section IDs, visible fragments, backtracks, skips and overlay transitions.

**Interpretation:** A viewport flash is not a completed paragraph. An overlay return does not automatically count as a backward revisit, reflection or confusion.

**3DCodeVerse:** Zero backward scrolls and zero seeks. Section paths are available for all nine sessions.

## Media use

**Origin:** Executed playback source intervals and sampled-frame timestamps.

Total playback counts repeated intervals; unique source coverage unions them. A seek changes position without adding watched duration. Record source identity and available modalities.

**Interpretation:** Browser mode is muted and supplies sampled frames, not continuous native video or audio. Do not claim listening or visual understanding.

**3DCodeVerse:** Only visual-agent sessions played robot-tabletop portions: 7.04, 4.01 and 8.06 unique source seconds. Other clips unplayed.

## Probability forecast

**Origin:** Elicited model estimate, not an executor outcome.

A session initial forecast uses only the first viewport; a separate whole-text forecast has broader access. Label those paths and conditions independently.

**Interpretation:** Not calculated by weighting text/video/audio consumption. No human calibration, population completion probability or causal comparison follows.

**3DCodeVerse:** Forecast probabilities are secondary and omitted from the default decision view. The primary results are audited terminations and cited feedback.

## Uncertainty

**Origin:** Repeated outputs, disagreements, evidence gaps and missing reference data.

Show every attempt, individual values, failures, caps and assumptions. Calibrated confidence_interval stays null; coverage unknown; calibration_status not_calibrated.

**Interpretation:** Model self-ranges and repeated contexts do not establish human confidence coverage. Same-model role variation cannot rank real audience segments.

**3DCodeVerse:** 3 repeats per role; 0 human outcomes; reader mismatches and prediction accuracy unavailable. No B or measured uplift.

[Study and all nine outcomes](3dcodeverse-study.md) · [Design changes](design-enhancements.md)
