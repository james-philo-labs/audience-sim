#!/usr/bin/env python3
"""Three native-media probes, without persona scoring. Standard-library-only CLI."""

import argparse, base64, copy, hashlib, importlib.util, json, math, os
from pathlib import Path
import re, shutil, subprocess, time
from datetime import datetime, timezone
import urllib.request, urllib.error

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_BUNDLE = None
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
MODEL = os.environ.get("GEMINI_MODEL", "explicit-model-required")
VERSION = "native-perception-0.1.0"
RATES = {
    "input_per_million_usd": 1.0,
    "output_and_thought_per_million_usd": 1.0,
    "status": "authored placeholders; replace with current provider pricing before live use",
    "not_billing_guarantee": True,
}


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    Path(path).write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )


def read(path):
    return json.loads(Path(path).read_text())


def cmd(args):
    p = subprocess.run(args, text=True, capture_output=True, timeout=180)
    if p.returncode:
        raise ValueError(f"{args[0]} failed; exit {p.returncode}")
    return p.stdout


def ffprobe(path, frames=False):
    args = ["ffprobe", "-v", "error"]
    if frames:
        args += ["-select_streams", "v:0", "-show_frames"]
    args += [
        "-show_entries",
        "frame=best_effort_timestamp_time"
        if frames
        else "format=duration:stream=codec_type,codec_name,nb_frames,width,height",
        "-of",
        "json",
        str(path),
    ]
    return json.loads(cmd(args))


def validate_seal(bundle):
    seal = read(bundle / "seal.json")
    files = seal["files"]
    actual = {
        str(p.relative_to(bundle))
        for p in bundle.rglob("*")
        if p.is_file() and p.name != "seal.json"
    }
    if actual != set(files):
        raise ValueError("Frozen bundle file set changed")
    for rel, digest in files.items():
        path = within(bundle, rel)
        if sha(path) != digest:
            raise ValueError("Frozen bundle hash mismatch: " + rel)
    return sha(bundle / "seal.json")


def within(root, relative):
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        raise ValueError("Path outside run/bundle")
    return path


def obj(props):
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


def text():
    return {"type": "string", "minLength": 1}


def enum(values):
    return {"type": "string", "enum": values}


def schema(case):
    event = obj(
        {
            "start_seconds": {
                "type": "number",
                "minimum": 0,
                "maximum": case["duration_seconds"],
            },
            "end_seconds": {
                "type": "number",
                "minimum": 0,
                "maximum": case["duration_seconds"],
            },
            "channel": enum(["visual", "on_screen_text", "audio"]),
            "kind": enum(["observation", "visible_label_claim", "spoken_claim"]),
            "description": text(),
            "uncertainty": {"type": "string"},
        }
    )
    return obj(
        {
            "case_id": enum([case["case_id"]]),
            "status": enum(["descriptive_observations", "review_required"]),
            "summary": text(),
            "audio_assessment": enum(
                ["sounds_present", "no_audible_content_detected", "uncertain"]
                if case["audio_enabled"]
                else ["not_supplied"]
            ),
            "events": {"type": "array", "items": event, "maxItems": 12},
            "limitations": {"type": "array", "items": text(), "maxItems": 10},
        }
    )


# Reuse the tested validator's exact subset; preserve its implementation hash in every preparation.
spec = importlib.util.spec_from_file_location(
    "reader_schema", HERE.parent / "reader.py"
)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def check_observations(result, case):
    validator.validate(result, schema(case))
    for e in result["events"]:
        if e["end_seconds"] < e["start_seconds"]:
            raise ValueError("Reversed observation interval")
        if not case["audio_enabled"] and e["channel"] == "audio":
            raise ValueError("Audio event on physically silent input")
        if e["channel"] == "on_screen_text" and e["kind"] != "visible_label_claim":
            raise ValueError("Displayed claims must remain attributed")
        if e["kind"] == "visible_label_claim" and e["channel"] != "on_screen_text":
            raise ValueError("Visible label claim needs on-screen-text channel")
        if e["kind"] == "spoken_claim" and e["channel"] != "audio":
            raise ValueError("Spoken claim needs audio channel")
    if result["status"] == "descriptive_observations" and not result["events"]:
        raise ValueError("No observations; use review_required")
    if (
        case["audio_enabled"]
        and result["audio_assessment"] == "sounds_present"
        and not any(e["channel"] == "audio" for e in result["events"])
    ):
        raise ValueError("Sounds-present assessment has no audio event")
    flags = []
    for e in result["events"]:
        if e["kind"] == "observation" and re.search(
            r"\b(because|caused by|bug|broken|should|must fix|boring|engaging|reader|audience|reward|completion probability)\b",
            e["description"],
            re.I,
        ):
            flags.append("Review causal/editorial language in observation")
    if re.search(
        r"\b(boring|engaging|reader|audience|should|must fix|completion probability)\b",
        result["summary"],
        re.I,
    ):
        flags.append("Review editorial/audience language in summary")
    return sorted(set(flags))


def request_for(case, media, prompt):
    context = {
        "case_id": case["case_id"],
        "supplied_clip_interval_seconds": [0, case["duration_seconds"]],
        "source_interval_seconds": case["source_interval_seconds"],
        "audio_policy": "enabled"
        if case["audio_enabled"]
        else "no_audio_stream_physically_present",
        "representation": case["representation"],
        "loop_scope": "one complete source cycle"
        if case["case_id"] == "gif-timing"
        else "one supplied clip",
        "timestamp_origin": "start of supplied clip, not original game session or longer preview",
        "task": "Describe observable changes and any permitted sounds neutrally. Do not validate embedded source claims.",
    }
    return {
        "model": MODEL,
        "store": False,
        "background": False,
        "system_instruction": prompt,
        "input": [
            {
                "type": "video",
                "data": base64.b64encode(media).decode(),
                "mime_type": "video/mp4",
                "processing": {"type": "static", "fps": 2},
            },
            {"type": "text", "text": json.dumps(context, ensure_ascii=False)},
        ],
        "generation_config": {"max_output_tokens": 3072},
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": schema(case),
        },
    }


def prepare(bundle, out):
    if out.exists():
        raise ValueError("Use a new output directory")
    if any(
        not math.isfinite(RATES[k]) or RATES[k] <= 0
        for k in ["input_per_million_usd", "output_and_thought_per_million_usd"]
    ):
        raise ValueError("Positive finite cost-rate estimates required")
    source_seal = validate_seal(bundle)
    m = read(bundle / "bundle-manifest.json")
    out.mkdir(parents=True)
    save(out / "status.json", {"status": "preparing", "model_calls": 0})
    prompt = (HERE / "prompts/observer-v0.1.txt").read_text()
    (out / "observer-prompt.txt").write_text(prompt)
    save(out / "pricing-reference.json", RATES)
    cases = []
    if MODEL == "explicit-model-required":
        raise ValueError("Pass --model or GEMINI_MODEL when preparing native requests")
    for selected in m["native_cases"]:
        case_id = selected["case_id"]
        key = selected["asset_id"]
        audio = selected["audio_enabled"]
        dest = out / case_id
        dest.mkdir()
        asset = next(a for a in m["assets"] if a["asset_id"] == key)
        original = bundle / asset["frozen_path"]
        # GIF-cycle derivative comes from the verified timing-preserving first increment.
        source = original
        native = dest / "native-input.mp4"
        options = [
            "-map",
            "0:v:0",
            "-c:v",
            "libx264",
            "-crf",
            "23",
            "-preset",
            "medium",
            "-pix_fmt",
            "yuv420p",
            "-threads",
            "1",
            "-fps_mode",
            "passthrough",
            "-enc_time_base",
            "demux",
            "-map_metadata",
            "-1",
            "-flags:v",
            "+bitexact",
            "-video_track_timescale",
            "10000",
        ]
        options += ["-map", "0:a:0", "-c:a", "copy"] if audio else ["-an"]
        args = [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-threads",
            "1",
            "-fflags",
            "+bitexact",
            "-i",
            str(source),
            *options,
            "-movflags",
            "+faststart",
            str(native),
        ]
        cmd(args)
        repeat = dest / "repeat.mp4"
        cmd(args[:-1] + [str(repeat)])
        if sha(native) != sha(repeat):
            raise ValueError("Non-repeatable native derivative")
        repeat.unlink()
        cmd(
            [
                "ffmpeg",
                "-v",
                "error",
                "-threads",
                "1",
                "-i",
                str(native),
                "-f",
                "null",
                "-",
            ]
        )
        src_probe = ffprobe(source)
        probe = ffprobe(native)
        present = any(s["codec_type"] == "audio" for s in probe["streams"])
        if present != audio:
            raise ValueError("Prepared stream contradicts audio policy")
        duration = float(probe["format"]["duration"])
        src_duration = float(src_probe["format"]["duration"])
        src_pts = [
            float(f["best_effort_timestamp_time"])
            for f in ffprobe(source, True)["frames"]
        ]
        dst_pts = [
            float(f["best_effort_timestamp_time"])
            for f in ffprobe(native, True)["frames"]
        ]
        if len(src_pts) != len(dst_pts):
            raise ValueError("Native transformation changed frame count")
        max_delta = max(abs(a - b) for a, b in zip(src_pts, dst_pts))
        if max_delta > 0.011 or abs(duration - src_duration) > 0.03:
            raise ValueError("Native transformation changed temporal mapping")
        timing = {
            "source_pts_seconds": src_pts,
            "native_pts_seconds": dst_pts,
            "frame_count": len(dst_pts),
            "max_pts_delta_seconds": max_delta,
            "source_duration_seconds": src_duration,
            "native_duration_seconds": duration,
        }
        if audio:

            def pcmhash(p):
                return cmd(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-i",
                        str(p),
                        "-map",
                        "0:a:0",
                        "-vn",
                        "-f",
                        "hash",
                        "-hash",
                        "sha256",
                        "-",
                    ]
                ).strip()

            timing["source_decoded_audio_hash"] = pcmhash(source)
            timing["native_decoded_audio_hash"] = pcmhash(native)
            if (
                timing["source_decoded_audio_hash"]
                != timing["native_decoded_audio_hash"]
            ):
                raise ValueError("Sound-enabled audio samples changed")
        save(dest / "timing.json", timing)
        c = {
            "case_id": case_id,
            "source_asset_id": asset["asset_id"],
            "original_asset_sha256": asset["source_sha256"],
            "transformation_input": str(source),
            "transformation_input_sha256": sha(source),
            "command": args,
            "native_input_sha256": sha(native),
            "native_input_path": case_id + "/native-input.mp4",
            "duration_seconds": duration,
            "source_interval_seconds": [0, src_duration],
            "audio_enabled": audio,
            "audio_stream_present": present,
            "representation": "lossy_native_video; original GIF cycle converted first"
            if case_id == "gif-timing"
            else "lossy_native_video_with_original_audio_copied"
            if audio
            else "lossy_native_video_no_audio",
            "source_frame_count": len(src_pts),
            "native_frame_count": len(dst_pts),
            "requested_sampling_fps": 2,
            "actual_provider_sample_timestamps": "unknown",
            "repeat_sha256_equal": True,
            "source_labels_present": "may contain authored editorial/QA labels; attribution required",
            "actual_human_or_model_observation": False,
        }
        req = request_for(c, native.read_bytes(), prompt)
        body = json.dumps(req, ensure_ascii=False).encode()
        if len(body) > 20_000_000:
            raise ValueError("Native inline request exceeds conservative 20 MB cap")
        save(dest / "case.json", c)
        save(dest / "schema.json", schema(c))
        (dest / "request.json").write_bytes(body)
        save(
            dest / "run.json",
            {
                "case_id": case_id,
                "status": "prepared",
                "execution_mode": "not_run",
                "inference_ran": False,
                "persona_scoring_connected": False,
                "requested_model": MODEL,
                "returned_model": None,
                "endpoint": ENDPOINT,
                "request_sha256": sha(dest / "request.json"),
                "created_at_utc": utc(),
                "usage": None,
                "semantic_review_status": "not_run",
                "neutrality_status": "not_reviewed",
                "automatic_retries": 0,
            },
        )
        cases.append(c)
    manifest = {
        "version": VERSION,
        "created_at_utc": utc(),
        "bundle_path": str(bundle),
        "bundle_seal_sha256": source_seal,
        "article_sha256": m["article_sha256"],
        "model": MODEL,
        "endpoint": ENDPOINT,
        "case_order": [c["case_id"] for c in cases],
        "cases": cases,
        "settings": {
            "processing": "static",
            "fps": 2,
            "max_output_tokens": 3072,
            "store": False,
            "background": False,
            "other_settings": "provider defaults; not assumed",
        },
        "cost_estimate": {
            "conservative_input_token_allowance_per_case": 50000,
            "assumed_output_and_thought_token_allowance_per_case": 10000,
            "estimated_suite_usd_with_2x_margin": round(
                3
                * (
                    50000 * RATES["input_per_million_usd"]
                    + 10000 * RATES["output_and_thought_per_million_usd"]
                )
                / 1e6
                * 2,
                4,
            ),
            "estimate_not_provider_billing_cap": True,
        },
        "persona_scoring_connected": False,
    }
    save(out / "preparation.json", manifest)
    (out / "implementation").mkdir()
    shutil.copyfile(__file__, out / "implementation/observer.py")
    shutil.copyfile(
        HERE.parent / "reader.py", out / "implementation/reader-schema-validator.py"
    )
    protected = [
        p
        for p in out.rglob("*")
        if p.is_file() and p.name not in ["run.json", "status.json"]
    ]
    save(
        out / "preparation-seal.json",
        {"files": {str(p.relative_to(out)): sha(p) for p in protected}},
    )
    save(
        out / "status.json",
        {
            "status": "prepared_three_probes",
            "model_calls": 0,
            "live_semantic_verification": "pending",
            "persona_scoring_connected": False,
        },
    )
    return manifest


def verify_preparation(out):
    for rel, digest in read(out / "preparation-seal.json")["files"].items():
        if sha(within(out, rel)) != digest:
            raise ValueError("Prepared artifact changed: " + rel)
    manifest = read(out / "preparation.json")
    if validate_seal(Path(manifest["bundle_path"])) != manifest["bundle_seal_sha256"]:
        raise ValueError("Bundle seal changed")
    for c in manifest["cases"]:
        d = out / c["case_id"]
        r = read(d / "request.json")
        if (
            r["model"] != manifest["model"]
            or r.get("store") is not False
            or r.get("tools")
            or r.get("previous_interaction_id")
        ):
            raise ValueError("Unexpected request configuration")
        videos = [x for x in r["input"] if x["type"] == "video"]
        if len(videos) != 1:
            raise ValueError("One video only per probe")
        data = base64.b64decode(videos[0]["data"], validate=True)
        if hashlib.sha256(data).hexdigest() != c["native_input_sha256"]:
            raise ValueError("Native request media substitution")
        p = ffprobe(d / "native-input.mp4")
        present = any(x["codec_type"] == "audio" for x in p["streams"])
        if present != c["audio_enabled"]:
            raise ValueError("Audio policy mismatch before network")
    return manifest


def extract(raw):
    if raw.get("status") != "completed":
        raise ValueError("Provider did not complete interaction")
    texts = []
    for step in raw.get("steps", []):
        if step.get("type") == "model_output":
            for part in step.get("content", []):
                if part.get("type") == "text":
                    texts.append(part.get("text", ""))
    if not texts:
        raise ValueError(
            "No model-output text; unsupported or refused response retained"
        )
    return json.loads("".join(texts))


def execute_case(out, case, key, fixture=None):
    dest = out / case["case_id"]
    record = read(dest / "run.json")
    if record["status"] != "prepared":
        raise ValueError(
            "Case already attempted; use a new preparation for a new attempt"
        )
    record["execution_mode"] = (
        "authored_fixture" if fixture is not None else "live_native_api"
    )
    record["started_at_utc"] = utc()
    start = time.monotonic()
    try:
        if fixture is None:
            record["status"] = "request_attempted"
            record["inference_ran"] = None
            save(dest / "run.json", record)
            req = urllib.request.Request(
                ENDPOINT,
                data=(dest / "request.json").read_bytes(),
                headers={"Content-Type": "application/json", "x-goog-api-key": key},
            )
            with urllib.request.urlopen(req, timeout=60) as response:
                raw = json.load(response)
            record["inference_ran"] = True
        else:
            raw = fixture
            record["inference_ran"] = False
        save(dest / "provider-response.json", raw)
        record.update(
            returned_model=raw.get("model"),
            interaction_id=raw.get("id"),
            usage=raw.get("usage"),
            provider_status=raw.get("status"),
        )
        result = extract(raw)
        flags = check_observations(result, case)
        save(dest / "observations.json", result)
        record.update(
            status="fixture_validated"
            if fixture is not None
            else "response_structurally_validated",
            semantic_review_status="pending_source_review",
            neutrality_status="needs_review"
            if flags
            else "lexical_screen_passed_semantic_review_pending",
            review_flags=flags,
            persona_scoring_connected=False,
        )
        usage = raw.get("usage") or {}
        if fixture is None and all(
            k in usage
            for k in [
                "total_input_tokens",
                "total_output_tokens",
                "total_thought_tokens",
            ]
        ):
            record["estimated_usage_cost_usd"] = round(
                (
                    usage["total_input_tokens"] * RATES["input_per_million_usd"]
                    + (usage["total_output_tokens"] + usage["total_thought_tokens"])
                    * RATES["output_and_thought_per_million_usd"]
                )
                / 1e6,
                6,
            )
        else:
            record["estimated_usage_cost_usd"] = None
        return True
    except urllib.error.HTTPError as error:
        # No key or response body is printed; preserve uncertain execution and known HTTP code.
        record.update(
            status="failed", error=f"HTTP {error.code}", failure_stage="provider"
        )
        return False
    except (ValueError, OSError, KeyError, TypeError) as error:
        record.update(
            status="failed", error=str(error), failure_stage="transport_or_validation"
        )
        return False
    finally:
        record["elapsed_seconds"] = round(time.monotonic() - start, 3)
        record["finished_at_utc"] = utc()
        save(dest / "run.json", record)


def run(out, max_estimated_usd):
    if not math.isfinite(max_estimated_usd) or max_estimated_usd <= 0:
        raise ValueError("Choose a positive finite estimate ceiling")
    manifest = verify_preparation(out)
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        save(
            out / "status.json",
            {
                "status": "live_blocked_missing_gemini_environment_key",
                "model_calls": 0,
                "persona_scoring_connected": False,
            },
        )
        raise ValueError(
            "GEMINI_API_KEY or GOOGLE_API_KEY is unavailable in this process; prepared inputs retained"
        )
    global RATES
    RATES = read(out / "pricing-reference.json")
    if RATES["status"] != "user_supplied":
        raise ValueError(
            "Prepare with current --input-rate and --output-rate before live use"
        )
    if (
        manifest["cost_estimate"]["estimated_suite_usd_with_2x_margin"]
        > max_estimated_usd
    ):
        raise ValueError("Suite estimate exceeds selected ceiling")
    attempted = 0
    spent = 0.0
    per_case_reserve = (
        manifest["cost_estimate"]["estimated_suite_usd_with_2x_margin"] / 3
    )
    for case in manifest["cases"]:
        if spent + per_case_reserve > max_estimated_usd:
            save(
                out / "status.json",
                {
                    "status": "stopped_estimate_ceiling",
                    "requests_attempted_this_invocation": attempted,
                    "estimated_cost_of_received_responses_usd": spent,
                    "persona_scoring_connected": False,
                },
            )
            return False
        attempted += 1
        ok = execute_case(out, case, key)
        if not ok:
            save(
                out / "status.json",
                {
                    "status": "stopped_after_failed_probe",
                    "requests_attempted_this_invocation": attempted,
                    "persona_scoring_connected": False,
                },
            )
            return False
        record = read(out / case["case_id"] / "run.json")
        if record["estimated_usage_cost_usd"] is None:
            save(
                out / "status.json",
                {
                    "status": "stopped_usage_unknown",
                    "requests_attempted_this_invocation": attempted,
                    "persona_scoring_connected": False,
                },
            )
            return False
        spent += record["estimated_usage_cost_usd"]
    save(
        out / "status.json",
        {
            "status": "three_native_responses_received_semantic_review_pending",
            "model_calls": attempted,
            "persona_scoring_connected": False,
        },
    )
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="op", required=True)
    a = sub.add_parser("prepare")
    a.add_argument("--bundle", type=Path, required=True)
    a.add_argument("--model")
    a.add_argument("--input-rate", type=float)
    a.add_argument("--output-rate", type=float)
    a.add_argument("--out", type=Path, required=True)
    a = sub.add_parser("run")
    a.add_argument("--prepared", type=Path, required=True)
    a.add_argument("--max-estimated-usd", type=float, default=1.0)
    a = sub.add_parser("verify")
    a.add_argument("--prepared", type=Path, required=True)
    args = p.parse_args()
    global MODEL
    if args.op == "prepare":
        MODEL = args.model or MODEL
        if args.input_rate is not None:
            RATES["input_per_million_usd"] = args.input_rate
        if args.output_rate is not None:
            RATES["output_and_thought_per_million_usd"] = args.output_rate
        RATES["status"] = (
            "user_supplied"
            if args.input_rate is not None and args.output_rate is not None
            else RATES["status"]
        )
    try:
        if args.op == "prepare":
            r = prepare(args.bundle.resolve(), args.out.resolve())
            print(
                json.dumps(
                    {
                        "status": "prepared",
                        "cases": r["case_order"],
                        "estimated_suite_usd": r["cost_estimate"][
                            "estimated_suite_usd_with_2x_margin"
                        ],
                    }
                )
            )
        elif args.op == "verify":
            r = verify_preparation(args.prepared.resolve())
            print(
                json.dumps(
                    {
                        "prepared_cases_verified": len(r["cases"]),
                        "audio_and_hash_checks": "passed",
                        "model_calls": 0,
                    }
                )
            )
        else:
            return 0 if run(args.prepared.resolve(), args.max_estimated_usd) else 1
        return 0
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        p.exit(1, str(error) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
