#!/usr/bin/env python3
"""Single-session reader harness. Python 3 standard library only; no implicit network."""

import argparse
import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
import uuid

HERE = Path(__file__).resolve().parent
VERSION = "0.2.0"
ENDPOINT = "https://api.openai.com/v1/responses"
ARTICLES = {"example": None, "opus": None, "gdpval": None, "omni": None, "3dcodeverse": None}
from personas import assemble


def obj(properties):
    return dict(
        type="object",
        properties=properties,
        required=list(properties),
        additionalProperties=False,
    )


def number(lo, hi):
    return dict(type="number", minimum=lo, maximum=hi)


def interval(lo, hi):
    return obj(
        {
            "low": number(lo, hi),
            "high": number(lo, hi),
            "confidence_interval": {"type": "null"},
            "coverage": {"type": "string", "enum": ["unknown"]},
        }
    )


QUOTE = obj(
    {
        "quote": {"type": "string", "minLength": 1},
        "reason": {"type": "string", "minLength": 1},
    }
)
SCHEMA = obj(
    {
        "interest_rating": number(1, 5),
        "completion_likelihood": number(0, 1),
        "estimated_reading_time_minutes": number(0, 10),
        "likely_drop_off_passage": {"anyOf": [QUOTE, {"type": "null"}]},
        "confusing_claims": {"type": "array", "items": QUOTE, "maxItems": 5},
        "useful_takeaway": {"type": "string", "minLength": 1},
        "suggested_revision": {"type": "string", "minLength": 1},
        "reason": {"type": "string", "minLength": 1},
        "uncertainty": obj(
            {
                "calibration_status": {"type": "string", "enum": ["not_calibrated"]},
                "interest_rating": interval(1, 5),
                "completion_likelihood": interval(0, 1),
                "estimated_reading_time_minutes": interval(0, 10),
            }
        ),
    }
)


def dump(path, value):
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    )


def sha(data):
    return hashlib.sha256(data).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def validate(value, schema, path="$"):
    """Validate the exact JSON Schema subset used by this harness, including finite numbers."""
    if "anyOf" in schema:
        for branch in schema["anyOf"]:
            try:
                validate(value, branch, path)
                return
            except ValueError:
                pass
        raise ValueError(path + ": no allowed type matched")
    kind = schema["type"]
    valid = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "null": value is None,
        "number": type(value) in (int, float) and math.isfinite(value),
    }
    if not valid[kind]:
        raise ValueError(path + ": invalid " + kind)
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(path + ": invalid enum")
    if kind == "object":
        if set(value) != set(schema["required"]):
            raise ValueError(path + ": missing or extra fields")
        for key, child in value.items():
            validate(child, schema["properties"][key], path + "." + key)
    elif kind == "array":
        if len(value) > schema.get("maxItems", float("inf")):
            raise ValueError(path + ": too many items")
        for i, child in enumerate(value):
            validate(child, schema["items"], path + "[" + str(i) + "]")
    elif kind == "string" and len(value.strip()) < schema.get("minLength", 0):
        raise ValueError(path + ": empty string")
    elif kind == "number" and not schema["minimum"] <= value <= schema["maximum"]:
        raise ValueError(path + ": outside range")


def check_response(result, article):
    validate(result, SCHEMA)
    passages = list(result["confusing_claims"])
    if result["likely_drop_off_passage"] is not None:
        passages.append(result["likely_drop_off_passage"])
    for passage in passages:
        if passage["quote"] not in article:
            raise ValueError("Passage quote does not occur verbatim in frozen article")
    for key in (
        "interest_rating",
        "completion_likelihood",
        "estimated_reading_time_minutes",
    ):
        bounds = result["uncertainty"][key]
        if not bounds["low"] <= result[key] <= bounds["high"]:
            raise ValueError(key + ": estimate outside elicited range")


def media_refs(text, parent):
    refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    refs += re.findall(r"\b(?:src|poster)=[\"\']([^\"\']+)", text)
    refs += [
        x
        for x in re.findall(r"\]\(([^)]+)\)", text)
        if re.search(r"\.(?:mp4|gif|png|jpe?g|webp|wav|mp3)(?:[#?]|$)", x, re.I)
    ]
    result = []
    for ref in dict.fromkeys(refs):
        local = None if "://" in ref else (parent / ref.split("#")[0]).resolve()
        result.append(
            {
                "reference": ref,
                "local_file_exists": local.is_file() if local else None,
                "submitted_as_media": False,
                "status": "not_observed",
            }
        )
    return result


def image_type(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise ValueError("Only PNG, JPEG or WebP still images are supported")


def prepare(args):
    article_path = Path(args.article).resolve()
    article_bytes = article_path.read_bytes()
    article = article_bytes.decode("utf-8")
    if len(article_bytes) > 200_000:
        raise ValueError("Article exceeds 200 KB cap")
    draft = args.article_version
    if not draft:
        raise ValueError("--article-version is required with --article")
    profiles = json.loads((HERE / "profiles.json").read_text())
    matches = [p for p in profiles["profiles"] if p["id"] == args.persona]
    if not matches:
        raise ValueError("Unknown persona")
    persona, scope = assemble(matches[0], args.post)
    override = scope["applied_override"]
    prompt = (HERE / "prompts/reader-v0.2.txt").read_text()
    instructions = prompt + "\nPERSONA:\n" + json.dumps(persona, ensure_ascii=False)
    refs = media_refs(article, article_path.parent)
    if len(args.image) > 4:
        raise ValueError("At most four stills per run")
    attachments = []
    for name in args.image:
        path = Path(name).resolve()
        data = path.read_bytes()
        if len(data) > 5_000_000:
            raise ValueError("Image exceeds 5 MB cap")
        mime = image_type(data)
        attachments.append((path, data, mime))
    media = {
        "condition": "text_plus_selected_stills" if attachments else "text_only",
        "article_references": refs,
        "attached_images": [],
        "video_accessible": False,
        "audio_accessible": False,
        "rendered_layout_accessible": False,
        "images_supplied_to_model": False,
        "full_visual_experience_validated": False,
        "meaning": "Accessible means bytes supplied in the model request, not proof of attention or understanding.",
    }
    for path, data, mime in attachments:
        media["attached_images"].append(
            {
                "source_path": str(path),
                "sha256": sha(data),
                "mime_type": mime,
                "status": "prepared_not_sent",
            }
        )
        for ref in refs:
            if (
                "://" not in ref["reference"]
                and (article_path.parent / ref["reference"]).resolve() == path
            ):
                ref["submitted_as_media"] = True
                ref["status"] = "prepared_not_sent"
    context = {
        "session": {
            "active_minutes_cap": 10,
            "device": "desktop",
            "sound": "off",
            "prior_exposure": False,
            "appendix": "optional and excluded from main completion",
        },
        "media": media,
        "article": article,
    }
    content = [{"type": "input_text", "text": json.dumps(context, ensure_ascii=False)}]
    for path, data, mime in attachments:
        content += [
            {"type": "input_text", "text": "Attached still image: " + path.name},
            {
                "type": "input_image",
                "detail": "auto",
                "image_url": "data:"
                + mime
                + ";base64,"
                + base64.b64encode(data).decode(),
            },
        ]
    request = {
        "model": args.model,
        "store": False,
        "instructions": instructions,
        "input": [{"role": "user", "content": content}],
        "max_output_tokens": args.max_output_tokens,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "reader_feedback_v02",
                "strict": True,
                "schema": SCHEMA,
            }
        },
    }
    if args.temperature is not None:
        request["temperature"] = args.temperature
    if args.reasoning_effort:
        request["reasoning"] = {"effort": args.reasoning_effort}
    dest = (
        Path(args.out).resolve()
        if args.out
        else HERE
        / "runs"
        / (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "-"
            + uuid.uuid4().hex[:8]
        )
    )
    dest.mkdir(parents=True, exist_ok=False)
    (dest / "article.md").write_bytes(article_bytes)
    (dest / "system-prompt.txt").write_text(instructions)
    dump(dest / "persona.json", persona)
    dump(dest / "response.schema.json", SCHEMA)
    for i, (path, data, mime) in enumerate(attachments):
        (dest / ("image-" + str(i) + path.suffix)).write_bytes(data)
    dump(dest / "request.json", request)
    record = {
        "persona_scope": scope,
        "harness_version": "public-0.1-text",
        "harness_sha256": sha(Path(__file__).read_bytes()),
        "created_at_utc": utc(),
        "decision_timestamp": args.decision_timestamp,
        "post_id": args.post,
        "article_version": draft,
        "article_source": str(article_path),
        "article_sha256": sha(article_bytes),
        "persona_id": args.persona,
        "persona_version": persona["version"],
        "persona_override": args.post if override else None,
        "persona_sha256": sha(json.dumps(persona, sort_keys=True).encode()),
        "prompt_version": "reader-v0.2",
        "prompt_sha256": sha(instructions.encode()),
        "requested_model": args.model,
        "returned_model": None,
        "settings": {
            k: v
            for k, v in request.items()
            if k in ("max_output_tokens", "temperature", "reasoning", "store")
        },
        "unspecified_settings": "Provider defaults; no seed, top_p or temperature inferred.",
        "endpoint": ENDPOINT,
        "timeout_seconds": 60,
        "automatic_retries": 0,
        "request_sha256": sha((dest / "request.json").read_bytes()),
        "media": media,
        "status": "prepared",
        "inference_ran": False,
        "calibration_status": "not_calibrated",
        "usage": None,
    }
    dump(dest / "run.json", record)
    return dest, request, record, article


def execute(dest, request, record, article, fixture=None):
    start = time.monotonic()
    try:
        if fixture:
            record["execution_mode"] = "authored_fixture"
            record["inference_ran"] = False
            raw = json.loads(Path(fixture).read_text())
        else:
            key = os.environ.get("OPENAI_API_KEY")
            if not key:
                raise ValueError(
                    "OPENAI_API_KEY is not configured; prepared request retained"
                )
            record["execution_mode"] = "live_api"
            req = urllib.request.Request(
                ENDPOINT,
                data=json.dumps(request).encode(),
                headers={
                    "Authorization": "Bearer " + key,
                    "Content-Type": "application/json",
                },
            )
            record["status"] = "request_attempted"
            record["inference_ran"] = None  # Unknown if transport fails after sending
            dump(dest / "run.json", record)
            with urllib.request.urlopen(req, timeout=60) as response:
                raw = json.load(response)
            record["inference_ran"] = True
        dump(dest / "provider-response.json", raw)
        record.update(
            returned_model=raw.get("model"),
            response_id=raw.get("id"),
            usage=raw.get("usage"),
        )
        if not fixture:
            record["media"]["images_supplied_to_model"] = bool(
                record["media"]["attached_images"]
            )
            for image in record["media"]["attached_images"]:
                image["status"] = "supplied_to_api"
            for ref in record["media"]["article_references"]:
                if ref["submitted_as_media"]:
                    ref["status"] = "supplied_to_api"
        if raw.get("status") != "completed":
            raise ValueError("Provider response not completed")
        texts = []
        for item in raw.get("output", []):
            if item.get("type") == "message":
                for block in item.get("content", []):
                    if block.get("type") == "refusal":
                        raise ValueError("Provider refused; retained raw response")
                    if block.get("type") == "output_text":
                        texts.append(block["text"])
        result = json.loads("".join(texts))
        check_response(result, article)
        dump(dest / "result.json", result)
        record["status"] = "fixture_validated" if fixture else "response_validated"
        record["review_status"] = "semantic_review_pending; human accuracy unvalidated"
        return True
    except urllib.error.HTTPError as error:
        record.update(
            status="failed", error="HTTP " + str(error.code), failure_stage="api"
        )
        return False
    except (ValueError, OSError, KeyError, TypeError) as error:
        record.update(
            status="failed", error=str(error), failure_stage="execution_or_validation"
        )
        return False
    finally:
        record["elapsed_seconds"] = round(time.monotonic() - start, 3)
        record["finished_at_utc"] = utc()
        dump(dest / "run.json", record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--post", choices=ARTICLES, required=True)
    parser.add_argument("--persona", required=True)
    parser.add_argument(
        "--model",
        required=True,
        help="Explicit provider model ID; use a snapshot if available",
    )
    parser.add_argument("--article", required=True)
    parser.add_argument("--article-version", required=True)
    parser.add_argument(
        "--decision-timestamp",
        required=True,
        help="ISO-8601 timestamp including timezone",
    )
    parser.add_argument("--image", action="append", default=[])
    parser.add_argument("--out")
    parser.add_argument("--temperature", type=float)
    parser.add_argument(
        "--reasoning-effort",
        choices=["none", "minimal", "low", "medium", "high", "xhigh"],
    )
    parser.add_argument("--max-output-tokens", type=int, default=2500)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--live", action="store_true", help="Make exactly one API request"
    )
    mode.add_argument(
        "--fixture", help="Authored provider response for offline pipeline testing"
    )
    args = parser.parse_args()
    try:
        stamp = datetime.fromisoformat(args.decision_timestamp.replace("Z", "+00:00"))
        if stamp.utcoffset() is None:
            raise ValueError("Decision timestamp must include timezone")
        if not 256 <= args.max_output_tokens <= 6000:
            raise ValueError("Output token cap must be 256–6000")
        if args.temperature is not None and not 0 <= args.temperature <= 2:
            raise ValueError("Temperature must be 0–2")
        dest, request, record, article = prepare(args)
        ok = (
            execute(dest, request, record, article, args.fixture)
            if args.live or args.fixture
            else True
        )
        print(json.dumps({"run_directory": str(dest), "status": record["status"]}))
        return 0 if ok else 1
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
