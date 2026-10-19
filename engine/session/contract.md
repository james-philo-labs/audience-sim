# Bounded browser reading contract — public 0.1

Derived from session runtime 0.4. A run is one scoped authored persona, one frozen article bundle and one fresh browser context. The condition is desktop 1440×900, muted, with motion activated on request. No live model requests occur during preparation, fixture execution or CI.

## Inputs and exposure

Freeze the article/media identities, persona projection, prompt, schema, implementation, settings and caps before execution. First request: first viewport only. Subsequent requests: this session's encountered fragments, viewport images, sampled rendered playback frames and executed history. No whole article, source HTML, future headings, hidden disclosures, unvisited media description, full asset inventory, previous-response ID, conversation ID or other-session output is supplied to the reader.

Source strings are untrusted evidence. The model returns structured actions; it cannot execute code or navigate external sites. The executor admits only currently available targets. Network requests outside the isolated local origin are blocked.

## Actions

`read` requests 2–60 simulated seconds. `scroll_next`, `scroll_back` and `skip` move 720 pixels. Disclosures can expand/collapse; visible images/media can open, play, seek, pause and close. Playback requests are 0.5–4 seconds. `read_while_playing` is admitted only for an inline player with the article available. Source playback is measured, then paused before the next decision. A seek charges authored interaction time; skipped footage is not observed duration.

GIFs start as first-frame posters. Activation opens one lossy silent H264 cycle, preserving source frame count and timestamp differences within 0.011 seconds. Padding can add a single right/bottom pixel. This differs from native GIF autoplay. No native video or audio input is supplied to the session model.

## Budgets and clocks

Default: 24 action decisions (explicit preparation supports 1–48), 600 simulated active seconds, 900 system wall seconds, 1,500 action output tokens and 2,500 terminal-feedback output tokens. Wall admission reserves time for feedback. Cost rates must be supplied for live execution; the estimate guard and request reserve are not provider billing guarantees. No automatic retry, resume or fallback is allowed. Failed and rejected actions remain recorded and consume their declared budget.

Simulated active time is the union of read/play intervals plus authored interaction costs. Source-media time, simulated active time and system wall time remain separate. Model latency does not add media exposure. These clocks are not measured human attention.

## Forecast and feedback

The initial schema requires a first-viewport forecast. Later schemas require null. Ranges have unknown coverage, null confidence interval and `not_calibrated` status. Terminal interest/takeaway/revision is retrospective. It may cite encountered evidence IDs only. The executor attaches the complete supplied text fragment, or null for image/frame evidence. An ID cannot authorize quoting a neighboring or unseen paragraph. Citation integrity leaves semantic support pending source review.

## Stop rules and allowed labels

Finish requires the declared main closing paragraph to have reached the visibility threshold. It does not require optional methods/all media and does not establish comprehension. Explicit abandon is distinct from cap censoring and failure. Unfinished sessions have no observed conditional time to finish. Neither cap nor error can be relabeled completion.

The auditor reconstructs model-facing requests, raw action equality, source-fragment/rectangle checks, hashes, target availability, clock intervals, forecast origin, quote derivation and censoring. Only a successful audit of a live policy trace permits `verified_simulated_read_with_limits`. Authored policy traces receive `verified_authored_trace_not_a_simulated_read`, with zero provider/model calls. Failed or unaudited traces receive neither label.

A passing audit supports mechanical validity under the recorded assumptions. Human predictive accuracy, semantic support, operating value and causal editorial effects require separate evidence.
