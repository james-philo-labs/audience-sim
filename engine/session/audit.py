#!/usr/bin/env python3
"""Replay saved request/action exposure and clocks before permitting a simulated-read label."""

import argparse, json, re
from pathlib import Path
import session_reader as m


def require(x, msg):
    m.require(x, msg)


def provider_output(path):
    raw = m.read(path)
    require(raw.get("status") == "completed", "Incomplete response in trace")
    texts = [
        p.get("text", "")
        for x in raw.get("output", [])
        if x.get("type") == "message"
        for p in x.get("content", [])
        if p.get("type") == "output_text"
    ]
    require(bool(texts), "Missing raw response text")
    return json.loads("".join(texts))


def validate(out):
    out = Path(out).resolve()
    config = m.verify_preparation(out)
    if (out / "raw-output-seal.json").exists():
        for rel, h in m.read(out / "raw-output-seal.json")["files"].items():
            require(
                m.sha(m.observer.within(out, rel)) == h,
                "Previously audited output changed: " + rel,
            )
    require(
        m.sha(Path(m.__file__)) == m.sha(out / "session_reader.py"),
        "Runtime changed since preparation; use frozen implementation for audit",
    )
    require(
        m.sha(Path(m.__file__).parent / "browser_rpc.cjs")
        == m.sha(out / "browser_rpc.cjs"),
        "Browser executor changed since preparation",
    )
    status = m.read(out / "status.json")
    require(status.get("error") is None, "Failed run is not a verified simulated read")
    trace = m.read(out / "trace.json")
    replay = m.Session(config["session_id"], config)
    blocks = {
        b["block_id"]: b for b in m.read(Path(config["bundle"]) / "block-map.json")
    }
    all_requests = []
    counts = {
        "visible_text_fragments": 0,
        "viewport_images": 0,
        "sampled_media_frames": 0,
    }
    call_cost = 0

    def visible_state(state):
        require(
            state["viewport"] == {"width": 1440, "height": 900}, "Unexpected viewport"
        )
        for t in state["texts"]:
            require(
                bool(t.get("visible_rects")), "Visible fragment lacks rectangle proof"
            )
            for r in t["visible_rects"]:
                require(
                    r["x"] >= -0.1
                    and r["y"] >= -0.1
                    and r["x"] + r["width"] <= 1440.1
                    and r["y"] + r["height"] <= 900.1,
                    "Offscreen characters included",
                )
            b = blocks.get(t["block_id"])
            if b:
                require(
                    t["text"] in b["text"], "Text fragment does not match source block"
                )
            else:
                require(
                    t["text"]
                    in [
                        "Play one silent animation cycle",
                        "Media inspection — return to article when finished",
                    ],
                    "Unknown authored text",
                )
        require(
            m.sha(out / state["screenshot"]["path"]) == state["screenshot"]["sha256"],
            "Viewport image changed",
        )

    initial = m.read(out / "observations/000.json")
    visible_state(initial["state"])
    replay.ingest(initial["state"])
    require(initial == replay.observations[-1], "Initial observation mismatch")
    action_files = sorted((out / "actions").glob("*.json"))
    for i, p in enumerate(action_files):
        turn = out / "turns" / f"{i:03d}"
        request = m.read(turn / "request.json")
        expected = m.request_for(replay, replay.observations[-1], out)
        require(
            request == expected,
            "Future/other-session evidence or wrong request interface at turn "
            + str(i),
        )
        require(
            request["store"] is False
            and not any(
                k in request for k in ["previous_response_id", "conversation", "tools"]
            ),
            "Persistent context/tools not allowed",
        )
        all_requests.append(turn / "request.json")
        action = provider_output(turn / "provider-response.json")
        require(
            action == m.read(turn / "output.json"),
            "Raw action differs from saved action",
        )
        m.v.validate(action, expected["text"]["format"]["schema"])
        record = m.read(turn / "run.json")
        require(
            record["request_sha256"] == m.sha(turn / "request.json"),
            "Request lineage mismatch",
        )
        call_cost += record["estimated_cost_usd"]
        rejection = None
        try:
            replay.check_action(action)
        except m.ActionRejected as e:
            rejection = str(e)
        saved = m.read(p)
        require(saved["proposed"] == action, "Proposed action mismatch")
        result = saved["execution"]
        if rejection:
            require(
                not result["success"]
                and result["error"] == "Rejected parameters: " + rejection,
                "Rejected action was executed",
            )
        require(result["before"] == replay.state, "Executor before-state mismatch")
        visible_state(result["after"])
        target = next(
            (t for t in replay.state["targets"] if t["id"] == action["target"]), None
        )
        if result["success"] and action["action"] in [
            "expand",
            "collapse",
            "inspect_image",
            "open_media",
            "open_gif",
            "play",
            "read_while_playing",
            "seek",
            "pause",
            "close_media",
        ]:
            require(target is not None, "Executed hidden action")
        if action["action"] == "finish" and result["success"]:
            require(
                replay.state["closing_main_reached"],
                "Finish before reaching closing paragraph",
            )
        pb = result.get("playback")
        if not pb:
            require(
                not result.get("frames"),
                "Playback frames without measured source interval",
            )
        if pb:
            require(
                pb["muted"] is True
                and target is not None
                and 0 <= pb["start"] <= pb["end"] <= target["duration"] + 0.05,
                "Bad source-media interval",
            )
            require(
                pb["advanced_seconds"] <= action["seconds"] + 1,
                "Playback exceeded requested interval tolerance",
            )
            require(
                abs(pb["advanced_seconds"] - (pb["end"] - pb["start"])) < 1e-5,
                "Source clock mismatch",
            )
            require(
                all(
                    pb["start"] <= f["source_time"] <= pb["end"] + 0.05
                    for f in result["frames"]
                ),
                "Frame outside played interval",
            )
        replay.apply(action, result)
        require(saved["event"] == replay.history[-1], "Action/clock replay mismatch")
        require(
            m.read(out / "observations" / f"{i + 1:03d}.json")
            == replay.observations[-1],
            "Observation/exposure mismatch",
        )
    # Cap events are distinct from completion and may prevent a proposed next action.
    term = trace["termination"]
    if term == "action_cap":
        require(len(action_files) == config["max_decisions"], "Premature action cap")
    if term == "time_cap" and (out / "time-cap-rejection.json").exists():
        rejected = m.read(out / "time-cap-rejection.json")
        turn = out / "turns" / f"{rejected['turn']:03d}"
        require(
            m.read(turn / "request.json")
            == m.request_for(replay, replay.observations[-1], out),
            "Bad cap checkpoint",
        )
        require(
            provider_output(turn / "provider-response.json") == rejected["proposed"],
            "Cap proposal not raw model output",
        )
        try:
            replay.check_action(rejected["proposed"])
        except ValueError as e:
            require("time cap" in str(e), "Unexpected cap rejection")
        else:
            raise ValueError("Unjustified time cap")
        all_requests.append(turn / "request.json")
        call_cost += m.read(turn / "run.json")["estimated_cost_usd"]
    if term in ["finish", "abandon"]:
        require(replay.termination == term, "Termination action not executed")
    else:
        require(
            term in ["action_cap", "time_cap", "wall_cap", "cost_cap"],
            "Unknown termination",
        )
    replay.termination = term
    require(replay.clock.summary() == trace["clock"], "Final clock mismatch")
    require(
        replay.evidence == trace["evidence"] and replay.history == trace["actions"],
        "Cross-session evidence/action contamination",
    )
    require(
        replay.clock.elapsed <= config["max_simulated_seconds"]
        and len(action_files) <= config["max_decisions"],
        "Session budget exceeded",
    )
    forecast = m.read(out / "initial-forecast.json")
    first = provider_output(out / "turns/000/provider-response.json")
    initial_evidence = initial["evidence_ids"]
    require(first["initial_forecast"] is not None, "Missing initial forecast")
    m.v.validate(first["initial_forecast"], m.FORECAST)
    require(
        forecast["forecast"] == first["initial_forecast"]
        and forecast["evidence_ids"] == initial_evidence,
        "Forecast has hindsight evidence",
    )
    final = out / "turns/final"
    require(
        m.read(final / "request.json")
        == m.request_for(replay, replay.observations[-1], out, True),
        "Final feedback includes unrevealed material",
    )
    raw_ids = provider_output(final / "provider-response.json")
    require(
        raw_ids == m.read(final / "output.json") == m.read(out / "feedback-ids.json"),
        "Raw ID feedback changed",
    )
    output = m.derive_feedback(raw_ids, replay.evidence)
    require(
        output == m.read(out / "feedback.json"), "Executor-derived feedback changed"
    )
    derivation = m.read(out / "quote-derivation.json")
    require(
        derivation["input_sha256"] == m.sha(out / "feedback-ids.json"),
        "Quote derivation lineage changed",
    )
    validity = replay.check_feedback(output)
    require(
        validity == m.read(out / "feedback-validity.json"), "Feedback validity changed"
    )
    all_requests.append(final / "request.json")
    call_cost += m.read(final / "run.json")["estimated_cost_usd"]
    require(len(all_requests) <= config["max_decisions"] + 1, "Call budget exceeded")
    require(
        abs(call_cost - status["estimated_cost_usd"]) < 1e-7, "Cost accounting mismatch"
    )
    for e in replay.evidence.values():
        if e["kind"] == "visible_text":
            counts["visible_text_fragments"] += 1
        elif e["kind"] == "viewport":
            counts["viewport_images"] += 1
        else:
            counts["sampled_media_frames"] += 1
    fixture = status.get("execution_mode") == "authored_fixture"
    summary = {
        "execution_mode": status.get("execution_mode"),
        "provider_calls": 0 if fixture else len(all_requests),
        "status": "verified_authored_trace_not_a_simulated_read"
        if fixture
        else "verified_simulated_read_with_limits",
        "session_id": config["session_id"],
        "condition": config["condition"],
        "termination": term,
        "completed_main": term == "finish",
        "cap_censored": term.endswith("_cap"),
        "simulated_clock": replay.clock.summary(),
        "system_wall_seconds": status["system_wall_seconds"],
        "model_calls": 0 if fixture else len(all_requests),
        "contract_turns": len(all_requests),
        "cost_usd_estimate": call_cost,
        "exposure": counts,
        "future_content_withholding": "request_reconstruction_and_visible_rectangle_checks_passed",
        "cross_session_memory": "fresh_state_and_independent_client_requests_only",
        "initial_forecast_pre_action": True,
        "feedback_citations_valid": len(validity),
        "semantics": "requires_source_review_not_ground_truth",
        "calibration_status": "not_calibrated",
    }
    m.save(out / "validation.json", summary)
    output_files = {
        str(p.relative_to(out)): m.sha(p)
        for p in out.rglob("*")
        if p.is_file() and p.name not in ["status.json", "raw-output-seal.json"]
    }
    m.save(out / "raw-output-seal.json", {"files": output_files})
    status.update(
        status=summary["status"],
        simulated_read_label_allowed=not fixture,
        validation="validation.json",
    )
    m.save(out / "status.json", status)
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    print(json.dumps(validate(p.parse_args().out), indent=2))
