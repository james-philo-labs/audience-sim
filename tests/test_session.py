import importlib.util, copy, json, tempfile, unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "session_reader",
    Path(__file__).resolve().parents[1] / "engine/session/session_reader.py",
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def state(text="Only revealed text."):
    return {
        "texts": [{"block_id": "block-001", "text": text}],
        "screenshot": {"path": "test.png", "sha256": "authored_fixture"},
        "targets": [],
        "scroll": {"x": 0, "y": 0},
        "viewport": {"width": 1440, "height": 900},
        "closing_main_reached": False,
        "overlay": False,
    }


def session():
    s = m.Session("sessionA", {"max_decisions": 24, "max_simulated_seconds": 600})
    s.ingest(state())
    return s


def action(name="read"):
    return {
        "action": name,
        "target": None,
        "seconds": 5 if name == "read" else 0,
        "source_seconds": None,
        "reason": "Authored test",
        "evidence_refs": ["obs-000-text-000"],
        "initial_forecast": {
            "completion_likelihood": 0.5,
            "plausible_low": 0.2,
            "plausible_high": 0.8,
            "confidence_interval": None,
            "coverage": "unknown",
            "calibration_status": "not_calibrated",
            "reason": "First viewport only",
        },
    }


class SessionTests(unittest.TestCase):
    def test_cross_session_state_is_empty(self):
        a = session()
        a.evidence["secret"] = {"kind": "visible_text", "text": "sessionA-only"}
        b = m.Session("sessionB", a.config)
        self.assertEqual(b.evidence, {})
        self.assertEqual(b.history, [])
        self.assertEqual(b.clock.elapsed, 0)

    def test_future_content_is_not_in_payload(self):
        s = session()
        s.config["private_article"] = "FUTURE_SENTINEL"
        self.assertNotIn("FUTURE_SENTINEL", json.dumps(s.payload()))

    def test_unrevealed_citation_rejected(self):
        a = action()
        a["evidence_refs"] = ["future"]
        with self.assertRaisesRegex(ValueError, "unrevealed"):
            session().check_action(a)

    def test_only_initial_checkpoint_forecast(self):
        s = session()
        a = action()
        s.check_action(a)
        s.history = [{}]
        with self.assertRaisesRegex(ValueError, "origin"):
            s.check_action(a)

    def test_negative_read_rejected(self):
        a = action()
        a["seconds"] = -1
        with self.assertRaises(ValueError):
            session().check_action(a)

    def test_playback_bound(self):
        a = action("play")
        a.update(target="player", seconds=5)
        with self.assertRaisesRegex(ValueError, "Playback duration"):
            session().check_action(a)

    def test_time_cap_is_checked_before_execution(self):
        s = session()
        s.clock.elapsed = 599
        with self.assertRaisesRegex(ValueError, "time cap"):
            s.check_action(action())

    def test_seek_does_not_charge_skipped_source_time(self):
        c = m.Clock()
        e = c.add("seek", 0, 0, True)
        self.assertEqual(e["active_union_seconds"], 1)
        self.assertEqual(c.elapsed, 1)

    def test_overlap_is_union(self):
        c = m.Clock()
        e = c.add("read_while_playing", 4, 4, True)
        self.assertEqual(e["active_union_seconds"], 4.3)
        self.assertEqual(e["overlap_seconds"], 4)

    def test_failed_action_charges_no_read_or_playback(self):
        c = m.Clock()
        e = c.add("play", 4, 4, False)
        self.assertEqual(e["playback_seconds"], 0)
        self.assertEqual(c.elapsed, 0.3)

    def test_union_handles_disjoint_overlapping_intervals(self):
        self.assertEqual(m.union_length([[0, 3], [2, 5], [8, 9]]), 6)

    def test_action_prompt_has_no_outcome_memory(self):
        self.assertNotIn("CHECK first", m.PROMPT)
        self.assertNotIn("source-107", m.PROMPT)

    def test_empty_memory_not_replaced_with_zero_forecast(self):
        a = action()
        a["initial_forecast"] = None
        with self.assertRaisesRegex(ValueError, "forecast missing"):
            session().check_action(a)


if __name__ == "__main__":
    unittest.main()


class EvidenceBoundaryTests(unittest.TestCase):
    def feedback(self):
        c = {"evidence_id": "obs-000-text-000", "quote": "Only revealed text."}
        return {
            "interest_rating": 3,
            "interest_low": 2,
            "interest_high": 4,
            "reason": "Authored fixture",
            "likely_drop_off": None,
            "confusing_claims": [],
            "useful_takeaway": {"text": "Test takeaway", "citations": [c.copy()]},
            "suggested_revision": {
                "text": "Test revision",
                "citations": [c.copy()],
                "status": "hypothesis_not_measured",
            },
            "confidence_interval": None,
            "coverage": "unknown",
            "calibration_status": "not_calibrated",
        }

    def test_feedback_cannot_quote_future(self):
        s = session()
        f = self.feedback()
        f["useful_takeaway"]["citations"][0]["quote"] = "Unseen closing recommendation"
        with self.assertRaisesRegex(ValueError, "not exposed"):
            s.check_feedback(f)

    def test_feedback_cannot_cite_other_session(self):
        f = self.feedback()
        f["useful_takeaway"]["citations"][0]["evidence_id"] = "other-session-evidence"
        with self.assertRaisesRegex(ValueError, "unrevealed"):
            session().check_feedback(f)

    def test_nullable_dropoff_is_valid_without_manufacturing_passage(self):
        self.assertEqual(len(session().check_feedback(self.feedback())), 2)

    def test_request_does_not_include_private_article_or_previous_context(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t)
            (p / "test.png").write_bytes(b"authored image fixture")
            (p / "action-prompt.txt").write_text(m.PROMPT)
            s = session()
            s.observations[-1]["images"][0]["sha256"] = m.sha(p / "test.png")
            s.evidence["obs-000-viewport"]["screenshot"]["sha256"] = m.sha(
                p / "test.png"
            )
            s.config["article"] = "SECRET_FUTURE_CONTENT"
            r = m.request_for(s, s.observations[-1], p)
            self.assertNotIn("SECRET_FUTURE_CONTENT", json.dumps(r))
            self.assertNotIn("previous_response_id", r)
            self.assertIs(r["store"], False)


class RejectionRegressionTests(unittest.TestCase):
    def test_visible_close_control_target_is_accepted(self):
        a = action("close_media")
        a["target"] = "viewer-close"
        session().check_action(a)

    def test_invalid_parameter_is_recoverable_rejection(self):
        a = action()
        a["target"] = "unnecessary-target"
        with self.assertRaises(m.ActionRejected):
            session().check_action(a)

    def test_failed_read_charges_interaction_budget(self):
        c = m.Clock()
        c.add("read", 60, None, False)
        self.assertEqual(c.elapsed, 0.2)


class ForecastSchemaTests(unittest.TestCase):
    def test_first_turn_requires_forecast_object(self):
        s = session()
        schema = m.action_schema_for(s)
        m.v.validate(action(), schema)
        a = action()
        a["initial_forecast"] = None
        with self.assertRaises(ValueError):
            m.v.validate(a, schema)

    def test_later_turn_requires_null_and_rejects_replayed_forecast(self):
        s = session()
        s.history = [{}]
        schema = m.action_schema_for(s)
        with self.assertRaises(ValueError):
            m.v.validate(action(), schema)
        a = action()
        a["initial_forecast"] = None
        m.v.validate(a, schema)
        s.check_action(a)

    def test_schemas_do_not_mutate_base_or_other_sessions(self):
        base = copy.deepcopy(m.ACTION_SCHEMA)
        a = session()
        b = session()
        a.history = [{}]
        m.action_schema_for(a)["properties"]["reason"] = {"type": "null"}
        self.assertEqual(m.ACTION_SCHEMA, base)
        self.assertEqual(
            m.action_schema_for(b)["properties"]["initial_forecast"], m.FORECAST
        )

    def test_actual_request_switches_schema_only_at_forecast_origin(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t)
            (p / "test.png").write_bytes(b"fixture")
            (p / "action-prompt.txt").write_text(m.PROMPT)
            s = session()
            s.observations[-1]["images"][0]["sha256"] = m.sha(p / "test.png")
            first = m.request_for(s, s.observations[-1], p)
            self.assertEqual(
                first["text"]["format"]["schema"]["properties"]["initial_forecast"],
                m.FORECAST,
            )
            s.history = [{}]
            later = m.request_for(s, s.observations[-1], p)
            self.assertEqual(
                later["text"]["format"]["schema"]["properties"]["initial_forecast"],
                {"type": "null"},
            )
            self.assertEqual(first["instructions"], later["instructions"])
            self.assertEqual(first["reasoning"], later["reasoning"])


class CitationAddressingTests(unittest.TestCase):
    def raw(self):
        f = EvidenceBoundaryTests().feedback()
        for field in ["useful_takeaway", "suggested_revision"]:
            for c in f[field]["citations"]:
                c.pop("quote")
        return f

    def test_exact_fragment_derived_without_mutation(self):
        f = self.raw()
        before = copy.deepcopy(f)
        s = session()
        out = m.derive_feedback(f, s.evidence)
        self.assertEqual(
            out["useful_takeaway"]["citations"][0]["quote"], "Only revealed text."
        )
        self.assertEqual(f, before)
        s.check_feedback(out)

    def test_unknown_or_other_session_id_rejected(self):
        f = self.raw()
        f["useful_takeaway"]["citations"][0]["evidence_id"] = "other-session"
        with self.assertRaisesRegex(ValueError, "unrevealed"):
            m.derive_feedback(f, session().evidence)

    def test_generated_quote_field_is_rejected(self):
        f = self.raw()
        f["useful_takeaway"]["citations"][0]["quote"] = "injected"
        with self.assertRaises(ValueError):
            m.derive_feedback(f, session().evidence)

    def test_media_quote_is_null(self):
        f = self.raw()
        s = session()
        f["confusing_claims"] = [
            {
                "claim": "image hypothesis",
                "citation": {"evidence_id": "obs-000-viewport"},
            }
        ]
        self.assertIsNone(
            m.derive_feedback(f, s.evidence)["confusing_claims"][0]["citation"]["quote"]
        )

    def test_dropoff_requires_text(self):
        f = self.raw()
        f["likely_drop_off"] = {"evidence_id": "obs-000-viewport", "reason": "fixture"}
        with self.assertRaisesRegex(ValueError, "visible text"):
            m.derive_feedback(f, session().evidence)

    def test_dropoff_text_and_abstention(self):
        f = self.raw()
        s = session()
        self.assertIsNone(m.derive_feedback(f, s.evidence)["likely_drop_off"])
        f["likely_drop_off"] = {"evidence_id": "obs-000-text-000", "reason": "fixture"}
        self.assertEqual(
            m.derive_feedback(f, s.evidence)["likely_drop_off"]["quote"],
            "Only revealed text.",
        )

    def test_derived_quote_does_not_join_neighbor_or_private_source(self):
        s = session()
        s.evidence["next"] = {"kind": "visible_text", "text": "Neighbor not selected."}
        s.config["private_article"] = "future"
        f = self.raw()
        out = m.derive_feedback(f, s.evidence)
        self.assertNotIn("Neighbor", json.dumps(out))
        self.assertNotIn("future", json.dumps(out))

    def test_tampered_derived_quote_still_rejected(self):
        s = session()
        out = m.derive_feedback(self.raw(), s.evidence)
        out["useful_takeaway"]["citations"][0]["quote"] = "wrong"
        with self.assertRaisesRegex(ValueError, "not exposed"):
            s.check_feedback(out)

    def test_terminal_request_uses_id_only_provider_schema(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t)
            (p / "test.png").write_bytes(b"fixture")
            (p / "feedback-prompt.txt").write_text(m.FINAL_PROMPT)
            s = session()
            s.observations[-1]["images"][0]["sha256"] = m.sha(p / "test.png")
            r = m.request_for(s, s.observations[-1], p, True)
            self.assertEqual(r["text"]["format"]["schema"], m.FEEDBACK_IDS_SCHEMA)
            self.assertNotIn(
                "quote",
                m.FEEDBACK_IDS_SCHEMA["properties"]["useful_takeaway"]["properties"][
                    "citations"
                ]["items"]["properties"],
            )


class ActionEvidenceSelectionTests(unittest.TestCase):
    def test_only_revealed_ids_in_enum(self):
        s = session()
        self.assertEqual(
            m.action_schema_for(s)["properties"]["evidence_refs"]["items"]["enum"],
            sorted(s.evidence),
        )

    def test_unknown_future_and_other_session_refs_rejected(self):
        s = session()
        for ref in ["obs-016-frame-0", "future", "other-session"]:
            a = action()
            a["evidence_refs"] = [ref]
            with self.assertRaises(ValueError):
                m.v.validate(a, m.action_schema_for(s))

    def test_known_text_viewport_and_frame_accepted(self):
        s = session()
        s.evidence["frame"] = {"kind": "sampled_playback_frame"}
        a = action()
        a["evidence_refs"] = sorted(s.evidence)
        m.v.validate(a, m.action_schema_for(s))

    def test_empty_refs_remain_valid_and_max_five_preserved(self):
        s = session()
        a = action()
        a["evidence_refs"] = []
        m.v.validate(a, m.action_schema_for(s))
        a["evidence_refs"] = ["obs-000-text-000"] * 6
        with self.assertRaises(ValueError):
            m.v.validate(a, m.action_schema_for(s))

    def test_enum_updates_without_mutating_old_schema(self):
        s = session()
        before = m.action_schema_for(s)
        s.evidence["new-frame"] = {"kind": "sampled_playback_frame"}
        after = m.action_schema_for(s)
        self.assertNotIn(
            "new-frame", before["properties"]["evidence_refs"]["items"]["enum"]
        )
        self.assertIn(
            "new-frame", after["properties"]["evidence_refs"]["items"]["enum"]
        )

    def test_empty_preparation_fixture_allows_no_ids(self):
        s = m.Session("empty", {})
        a = action()
        a["evidence_refs"] = []
        m.v.validate(a, m.action_schema_for(s))
        a["evidence_refs"] = ["invented"]
        with self.assertRaises(ValueError):
            m.v.validate(a, m.action_schema_for(s))

    def test_schema_enum_limits_fail_closed_not_truncate(self):
        s = session()
        s.evidence = {str(i): {} for i in range(1000)}
        with self.assertRaisesRegex(ValueError, "enum count"):
            m.action_schema_for(s)
        s.evidence = {("x" * 61) + str(i): {} for i in range(251)}
        with self.assertRaisesRegex(ValueError, "string limit"):
            m.action_schema_for(s)

    def test_private_config_and_other_session_not_in_choices(self):
        a = session()
        a.config["future_id"] = "FUTURE"
        b = session()
        b.evidence["other-session"] = {}
        self.assertNotIn("FUTURE", json.dumps(m.action_schema_for(a)))
        self.assertNotIn("other-session", json.dumps(m.action_schema_for(a)))

    def test_regression_unknown_historical_style_id_rejected(self):
        s = session()
        s.history = [{}]
        bad = action()
        bad["initial_forecast"] = None
        bad["evidence_refs"] = ["obs-999-text-001"]
        with self.assertRaises(ValueError):
            m.v.validate(bad, m.action_schema_for(s))
