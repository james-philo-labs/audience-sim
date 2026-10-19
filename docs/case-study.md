# Recorded article-treatment case study

This is a compact summary of recorded prototype outputs, not a new experiment. The [interactive replay](https://philo-audience-lab.vercel.app) provides the full articles, comparison and saved citations. The [machine-readable summary](../results/recorded-case-study.json) retains article hashes, conditions, status and ranges. Complete raw run archives are not included, so this repository alone cannot independently reconstruct the historical runs.

## Decision and treatments

A is frozen article v2. B is accepted candidate 0.3, which states a proposed check earlier, clarifies the transition into selected examples, trims repeated reproduce/revise/retest explanations and tightens the closing. Neither treatment establishes that the described game defects were repaired. Canonical A remains unchanged.

- [Read A](https://philo-audience-lab.vercel.app/reader.html?t=original)
- [Read B](https://philo-audience-lab.vercel.app/reader.html?t=candidate)
- [Inspect the eight edit groups](https://philo-audience-lab.vercel.app/compare.html)

One consequential passage separates enemy-response eligibility from collision and requires a matched retest. Inspect it [in A](https://philo-audience-lab.vercel.app/reader.html?t=original#block-015) and [in B](https://philo-audience-lab.vercel.app/reader.html?t=candidate#block-014). Citation presence establishes address integrity, not the underlying technical diagnosis.

## Full-text forecast study

Recorded on October 16, 2026, using the requested alias `gpt-6-luna`. Each eligible cell is one independent full-text output; media and layout were withheld. Interest and reading-time estimates are hypothetical. The displayed model identifier is not a claim of an immutable snapshot or of current account access.

| Authored persona | A: completion estimate [elicited range] | B: completion estimate [elicited range] | Study |
|---|---|---|---|
| Visual-agent researcher | 76% [58–88%] | 85% [69–94%] | Initial six-cell batch |
| Post-training engineer | 82% [68–92%] | 86% [68–95%] | Initial six-cell batch |
| Evaluation researcher | 82% [68–91%] | 82% [68–92%] | Separate scope-0.2 pair |

Coverage is unknown. These are not 95% confidence intervals, population estimates or measured treatment differences. The original six-cell batch contained two excluded evaluation cells; the later pair is a distinct study. Combining them into one six-cell “clean run” would conceal the failure.

## Disagreement with bounded sessions

A later fixed-budget comparison used the visual-agent persona and runtime 0.4, at a 1440×900 desktop viewport, muted, with motion activated on request. Both arms had a 48-action ceiling; neither hit it.

| Recorded trace | A | B |
|---|---|---|
| Executed actions | 27 | 19 |
| Termination | Finish | Abandon |
| Simulated active seconds | 123.892235 | 36.236695 |
| Action/time cap censored | No | No |
| Failed | No | No |
| Closing reached | Yes | No |

Those are simulated clocks, not measured human read times. B's shorter trace is not a reading-time saving. The arms revealed different content, and B's unvisited closing cannot support feedback from that session. A separate targeted closing inspection does not change what the session saw.

The first-viewport forecasts in these sessions were 72% for both arms, with different elicited ranges. They are distinct from the 76%/85% full-text forecasts above. A terminal interest rating or revision is retrospective feedback, not an advance forecast of that trace.

## Preserved failures

**Wrong persona scope.** An unrelated GDPval-specific override entered the evaluation persona for a visual-agent article. The output requested irrelevant rubric-audit submission bundles. Both initial evaluation cells were excluded. The fix projects only approved base fields plus the selected post's override. A separately predeclared fresh pair followed. Original outputs remain excluded; the public summary records the exclusion rather than copying private request archives.

**Unrevealed evidence reference.** A runtime-0.3 attempt selected an evidence ID that had not been revealed, after 21 executed actions. The arm failed before accepted terminal feedback, making that comparison inconclusive. Runtime 0.4 constrained action references to an enum of encountered IDs. The [regression test](../tests/test_session.py) uses a newly authored equivalent failure shape, not a disguised copy of the historical raw response.

**Temporal certainty.** Sparse native-media observations required bounds or attribution instead of exact transition or continuous-absence claims. Structural interval validation did not establish semantic accuracy. Sound-enabled use required an explicit listening review; muted browser sessions still received no audio.

## Bounded recommendation and next measurement

Keep B as the preferred editorial draft. That is an editorial choice. Measured real-reader outcomes remain **zero**; the current evidence does not establish that B increases completion, interest, comprehension or commercial value.

Propose 24 readers: eight in each of the three roles, randomized four per arm within role. Each reader sees one treatment, under the same declared device/media conditions and deadline. Before recruitment, agree an owner, consent, frozen versions, eligibility, exposure logging and a blind comprehension rubric. No person is assigned ownership by this proposal.

Record finish, voluntary exit, deadline censoring and missingness separately. Collect interest on a declared scale and blind-score comprehension: can the reader distinguish response eligibility from collision, and explain why a different encounter does not establish a repair? Preserve all assigned readers in the report. Compare observed outcomes with the corresponding forecasts without turning a small diagnostic into a powered trial or a calibration guarantee.

Reconsider the recommendation if real readers misunderstand the early check, if the proposed edit only improves a model's wording preference, or if media/access differences account for the apparent contrast.
