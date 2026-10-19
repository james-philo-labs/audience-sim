import copy, importlib.util, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "observer",
    Path(__file__).resolve().parents[1] / "engine/native_perception/observer.py",
)
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)


def case(audio=False):
    return {
        "case_id": "sound-enabled" if audio else "silent-temporal",
        "duration_seconds": 12.5,
        "audio_enabled": audio,
    }


def response(c=None):
    c = c or case()
    return {
        "case_id": c["case_id"],
        "status": "descriptive_observations",
        "summary": "Two figures remain near one another.",
        "audio_assessment": "sounds_present" if c["audio_enabled"] else "not_supplied",
        "events": [
            {
                "start_seconds": 1,
                "end_seconds": 2,
                "channel": "audio" if c["audio_enabled"] else "visual",
                "kind": "observation",
                "description": "A short tone is audible."
                if c["audio_enabled"]
                else "One figure moves forward.",
                "uncertainty": "Fine detail is unclear.",
            }
        ],
        "limitations": ["Actual provider frame sample times are unknown."],
    }


def envelope(result, status="completed"):
    return {
        "id": "AUTHORED-TEST-FIXTURE",
        "model": "authored-test-fixture",
        "status": status,
        "steps": [
            {
                "type": "model_output",
                "content": [{"type": "text", "text": json.dumps(result)}],
            }
        ],
        "usage": None,
    }


class ObserverTests(unittest.TestCase):
    def test_valid_description(self):
        self.assertEqual(o.check_observations(response(), case()), [])

    def test_allowed_review_and_empty_events(self):
        r = response()
        r["status"] = "review_required"
        r["events"] = []
        o.check_observations(r, case())

    def test_audio_leak_rejected(self):
        r = response()
        r["events"][0]["channel"] = "audio"
        with self.assertRaises(ValueError):
            o.check_observations(r, case())

    def test_timestamp_outside_interval_and_reversed(self):
        for start, end in [(1, 13), (3, 2), (-1, 2), (float("nan"), 2)]:
            r = response()
            r["events"][0].update(start_seconds=start, end_seconds=end)
            with self.assertRaises(ValueError):
                o.check_observations(r, case())

    def test_claim_attribution_required(self):
        r = response()
        r["events"][0]["channel"] = "on_screen_text"
        with self.assertRaises(ValueError):
            o.check_observations(r, case())
        r["events"][0]["kind"] = "visible_label_claim"
        o.check_observations(r, case())

    def test_subjective_causal_language_flagged_not_hidden(self):
        r = response()
        r["events"][0]["description"] = (
            "The opponent is broken because the scheduler has a bug."
        )
        self.assertTrue(o.check_observations(r, case()))

    def test_sound_needs_audio_evidence_or_explicit_uncertainty(self):
        c = case(True)
        r = response(c)
        o.check_observations(r, c)
        r["events"][0]["channel"] = "visual"
        with self.assertRaises(ValueError):
            o.check_observations(r, c)
        r["audio_assessment"] = "uncertain"
        o.check_observations(r, c)

    def test_extra_audience_fields_rejected(self):
        r = response()
        r["interest_rating"] = 5
        with self.assertRaises(ValueError):
            o.check_observations(r, case())

    def test_incomplete_refused_malformed_preserved_as_failure(self):
        for raw in [
            envelope(response(), "incomplete"),
            {"status": "completed", "steps": []},
            {
                "status": "completed",
                "steps": [
                    {
                        "type": "model_output",
                        "content": [{"type": "text", "text": "bad-json"}],
                    }
                ],
            },
        ]:
            with self.assertRaises(ValueError):
                o.extract(raw)

    def test_fixture_cannot_claim_inference_or_semantic_acceptance(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            c = case()
            dest = root / c["case_id"]
            dest.mkdir()
            o.save(dest / "run.json", {"status": "prepared"})
            self.assertTrue(o.execute_case(root, c, None, envelope(response())))
            r = o.read(dest / "run.json")
            self.assertFalse(r["inference_ran"])
            self.assertEqual(r["status"], "fixture_validated")
            self.assertEqual(r["semantic_review_status"], "pending_source_review")
            self.assertFalse(r["persona_scoring_connected"])
            with self.assertRaises(ValueError):
                o.execute_case(root, c, None, envelope(response()))

    def test_transport_unknown_and_no_retry(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            c = case()
            dest = root / c["case_id"]
            dest.mkdir()
            o.save(dest / "run.json", {"status": "prepared"})
            o.save(dest / "request.json", {})
            with patch.object(
                o.urllib.request, "urlopen", side_effect=OSError("timeout")
            ) as send:
                self.assertFalse(o.execute_case(root, c, "TEST-ONLY-NOT-A-CREDENTIAL"))
                send.assert_called_once()
            r = o.read(dest / "run.json")
            self.assertIsNone(r["inference_ran"])
            self.assertEqual(r["status"], "failed")

    def test_paths_outside_root_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                o.within(Path(d), "../not-allowed")

    def test_missing_key_stops_before_network(self):
        with (
            tempfile.TemporaryDirectory() as d,
            patch.object(o, "verify_preparation", return_value={}),
            patch.dict(o.os.environ, {}, clear=True),
            patch.object(o.urllib.request, "urlopen") as send,
        ):
            with self.assertRaises(ValueError):
                o.run(Path(d), 1)
            send.assert_not_called()
            self.assertEqual(
                o.read(Path(d) / "status.json")["status"],
                "live_blocked_missing_gemini_environment_key",
            )

    def test_live_transport_mock_is_not_a_real_online_test(self):
        from io import BytesIO

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            c = case()
            dest = root / c["case_id"]
            dest.mkdir()
            o.save(dest / "run.json", {"status": "prepared"})
            o.save(dest / "request.json", {})
            with patch.object(
                o.urllib.request,
                "urlopen",
                return_value=BytesIO(json.dumps(envelope(response())).encode()),
            ):
                self.assertTrue(o.execute_case(root, c, "TEST-ONLY"))
            self.assertTrue(o.read(dest / "run.json")["inference_ran"])


if __name__ == "__main__":
    unittest.main()
