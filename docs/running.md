# Run and inspect

All commands run from the repository root. Python uses the standard library. The only Node dependency is the pinned Playwright package. Install FFmpeg/FFprobe through your operating system's normal package manager. Node 22+ and Python 3.10+ are the supported public-package targets.

## Offline paths

The [README](../README.md) contains the text and browser quick starts. `npm test` exercises schemas, quotation checks, persona scoping, forecast origin, clocks and error handling with authored/mocked responses. `npm run test:browser` creates a fresh temporary bundle, runs real browser probes and an audited scripted trace, without submitting provider requests.

The example article JSON has `id`, `version`, `title`, `main_end_id` and ordered `blocks`. Blocks are `heading`, `paragraph`, `image`, `animation`, `video`, `details`, `image_group`, `table` or `callout`, with unique simple IDs. Paragraphs and captions may carry escaped inline `strong`, `em` and HTTPS-link annotations whose concatenated text must match the declared plain text exactly. Paired images share a caption; table cells have individual citation IDs. A labelled callout can contain paragraphs and local media. `cover_block_id` puts an opening image before the title. Section metadata is private summary input; it is not an inventory supplied to the session reader. Media references must resolve inside the article directory. Text is escaped; arbitrary HTML, JavaScript and remote embeds are not accepted. The main-end ID must identify a paragraph. Optional methods follow it.

Use `examples/article-b.json` for a second authored treatment. Both examples are unrelated to the recorded historical article: their media are test patterns and their numerical fixture values are arbitrary.

## A prepared run is inspectable and has no inference

```sh
python3 engine/reader.py --post example --persona evaluation-researcher \
  --article examples/article-b.md --article-version b-v1 \
  --model "$OPENAI_MODEL" --decision-timestamp 2026-10-18T12:00:00-07:00 \
  --out runs/prepared-text-b
```

No `--live` means no submission. Up to four explicit `--image path/to/still.png` arguments create a text-plus-selected-stills condition. Linked media remain references. Inspect `article.md`, `persona.json`, `system-prompt.txt`, `request.json`, `response.schema.json` and `run.json` before choosing to submit an independent fresh run.

## Live requests are an explicit, separate opt-in

No live calls were made for this publication. Configure an API key only in the execution environment; never commit it. Select a model available to your account, preferably an immutable snapshot when available. `OPENAI_MODEL` and `GEMINI_MODEL` are model IDs, not credentials. Account compatibility is not established by these offline tests.

For one text request, use the prepare command with a fresh `--out` and add `--live`. For native probes:

```sh
python3 engine/native_perception/observer.py prepare \
  --bundle runs/bundle-a --model "$GEMINI_MODEL" --out runs/native-probes \
  --input-rate "$INPUT_USD_PER_MILLION" --output-rate "$OUTPUT_AND_THOUGHT_USD_PER_MILLION"
python3 engine/native_perception/observer.py verify --prepared runs/native-probes
# Explicitly opt in only after inspecting the preparation:
python3 engine/native_perception/observer.py run \
  --prepared runs/native-probes --max-estimated-usd 1
```

The rates must come from current provider pricing, including thought-token accounting. Omitted rates allow preparation with labeled placeholders but block live native submission. The observer uses the Gemini Interactions API shape inherited from the prototype. Requested video sampling is 2 FPS; actual provider sample timestamps remain unknown. Validate model/API compatibility before authorizing new live probes. There are no automatic retries or model fallbacks.

For a live browser session, prepare a fresh run with explicit `--model`, `--input-rate`, `--output-rate` and optional `--max-decisions` (1–48). Then use `run` and `audit.py`:

```sh
python3 engine/session/session_reader.py prepare \
  --bundle runs/bundle-a --out runs/live-session-a --model "$OPENAI_MODEL" \
  --input-rate "$INPUT_USD_PER_MILLION" --output-rate "$OUTPUT_USD_PER_MILLION" \
  --max-decisions 24
# Only after inspection and authorization for provider usage:
python3 engine/session/session_reader.py run --out runs/live-session-a
python3 engine/session/audit.py --out runs/live-session-a
```

The session's estimate guard defaults to $1, with 600 simulated active seconds, 900 wall seconds, 1,500 output tokens per action and 2,500 for terminal feedback. Its conservative preflight reserve assumes 200,000 input tokens per request; this is an estimate, not a tokenizer or billing guarantee. A 20 MB serialized-request cap is enforced before submission. Actual usage is retained. Provider errors and unknown billing are not silently retried. Preparation is sealed: change a configuration by preparing a fresh run, not editing it in place.

## Important artifacts

| Artifact | Purpose |
|---|---|
| Bundle manifest / seal | Exact article, media identity and frozen file set |
| Config, persona scope, prompts and schemas | Declared conditions and input projection |
| `turns/*/request.json` | Exact allowed model input at each checkpoint |
| Raw response / output / error | Preserve received output and failures |
| Observations / captures / actions | Actual executor exposure and action history |
| Initial forecast | First viewport before first action |
| Feedback IDs / quote derivation | Model-selected IDs and locally attached text |
| Trace / validation / output seal | Clock replay, censoring, integrity and audit status |

Generated directories are ignored by Git. They can contain your article and media even when inference is disabled. Do not publish them by default. The auditor reconstructs the recorded projection; it is not a cryptographic attestation of the operating system or a substitute for source-semantic review.

## Browser configuration

Playwright's normal installed Chromium is used by default. `BUNDLE_CHROMIUM_PATH` can explicitly select a local Chromium executable. `NODE_BINARY` can select Node; `AUDIENCE_NODE_MODULES` can select a dependency directory. None is hard-coded to a workstation path. Native browser tests need permission to launch Chromium and bind a local-only server.

If a command fails, retain the output and its status, resolve the cause, then use a new directory. A fixture success is never a provider integration test or a calibrated reader prediction.

## Scoped sessions and trace summaries

Select the post explicitly with `--post 3dcodeverse` (or another supported post) and `--persona visual-agent-researcher`, `post-training-engineer` or `evaluation-researcher`. Only the selected post's approved role goal, knowledge and interests are projected. Inspect `persona-scope.json`; other post overrides are withheld. Article-specific media and text belong in your local bundle, not this public package.

After auditing all assigned runs, including failures and censored attempts, generate a separate read-only report:

```sh
python3 engine/session/summary.py --runs runs/session-a runs/session-b --out runs/summary-v1
```

The JSON and CSV files retain assigned denominators, raw terminations, technical events, section visits and backtracking, read/play overlap, interaction time and sampled source intervals. Multi-section time stays unallocated when attribution is ambiguous. An absent assigned path remains an unknown/missing row. Replays add playback time but unique source coverage uses interval union. A browser source interval does not mean the model watched every frame or heard audio.

The summary does not infer disinterest from failures, reflection from a long dwell, or a population completion probability from a few role traces. Interest is an uncalibrated retrospective rubric: 1 = little relevance to the role's goal, 3 = relevant without a clear next step, 5 = a concrete research or workflow idea worth pursuing. A supported KEEP is acceptable. An audited live natural finish alone receives a simulated conditional finish time. Authored clocks and ratings remain labelled software test data; cap censoring never becomes abandonment or a finish.

## Recorded 3DCodeVerse study view

`site/` contains the public study UI and selected JSON/CSV, with no inference backend. Preview it with `python3 -m http.server 4173 --directory site`, then open `http://localhost:4173`. The hosted `/opus.html` route belongs to the separately preserved historical app; its article/media payload is not vendored here.

Run `npm run test:study` after installing Chromium. Like the executor, the UI test accepts `BUNDLE_CHROMIUM_PATH` for an explicitly selected local executable. Set `STUDY_URL` to check a deployed site and `STUDY_REPORT_DIR` for screenshots/report output outside the public inventory. No provider credentials are required.
