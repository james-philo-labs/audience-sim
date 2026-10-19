import copy, importlib.util, unittest
from pathlib import Path

S = importlib.util.spec_from_file_location(
    "rich_inspect", Path(__file__).resolve().parents[1] / "engine/inspection.py"
)
m = importlib.util.module_from_spec(S)
S.loader.exec_module(m)


def fixture():
    r = {
        "interest_rating": 3,
        "completion_likelihood": 0.6,
        "estimated_reading_time_minutes": 5,
        "reason": "Authored test only",
        "uncertainty": {"calibration_status": "not_calibrated"},
        "feedback": [],
        "editorial_ranking": [
            {"candidate": x, "reason": "Authored fixture"}
            for x in ["CHECK", "OPENING", "TOUR", "KEEP"]
        ],
        "access_limitations": ["No audio"],
    }
    for key, (low, high) in {
        "interest_rating": (2, 4),
        "completion_likelihood": (0.3, 0.8),
        "estimated_reading_time_minutes": (3, 7),
    }.items():
        r["uncertainty"][key] = {
            "low": low,
            "high": high,
            "confidence_interval": None,
            "coverage": "unknown",
        }
    for i, cat in enumerate(
        ["confusing_claim", "useful_takeaway", "suggested_revision"]
    ):
        r["feedback"].append(
            {
                "id": str(i),
                "category": cat,
                "claim": "Authored finding",
                "action_or_implication": "Review",
                "citations": [
                    {
                        "evidence_id": "b1",
                        "quote": "Caption alleges a bug.",
                        "start_seconds": None,
                        "end_seconds": None,
                        "model_validity": "supports",
                    }
                ],
            }
        )
    return r


def context():
    return {
        "evidence_catalog": {
            "b1": {
                "kind": "article_block",
                "exposed": True,
                "text": "Caption alleges a bug.",
            },
            "v1": {"kind": "video", "exposed": True, "duration_seconds": 8.01},
            "withheld": {"kind": "article_media", "exposed": False},
        }
    }


class InspectionTests(unittest.TestCase):
    def test_valid_quote_is_integrity_only(self):
        checks = m.check_feedback(fixture(), context())
        self.assertTrue(
            all(
                c["citation_integrity"] == "valid"
                and not c["eligible_for_decision"]
                and c["semantic_status"] == "pending_source_review"
                for c in checks
            )
        )

    def test_fake_quote_invalidates_finding(self):
        r = fixture()
        r["feedback"][0]["citations"][0]["quote"] = "A proven game bug"
        self.assertEqual(
            m.check_feedback(r, context())[0]["citation_integrity"], "invalid"
        )

    def test_unexposed_evidence_invalidates_finding(self):
        r = fixture()
        r["feedback"][0]["citations"][0].update(evidence_id="withheld", quote=None)
        self.assertIn(
            "media_withheld",
            m.check_feedback(r, context())[0]["citations"][0]["problems"],
        )

    def test_unknown_evidence_invalidates_finding(self):
        r = fixture()
        r["feedback"][0]["citations"][0]["evidence_id"] = "imaginary"
        self.assertEqual(
            m.check_feedback(r, context())[0]["citation_integrity"], "invalid"
        )

    def test_video_out_of_range_invalidates_finding(self):
        r = fixture()
        r["feedback"][0]["citations"][0].update(
            evidence_id="v1", quote=None, start_seconds=0, end_seconds=9
        )
        self.assertIn(
            "invalid_video_interval",
            m.check_feedback(r, context())[0]["citations"][0]["problems"],
        )

    def test_static_timing_rejected(self):
        r = fixture()
        r["feedback"][0]["citations"][0].update(start_seconds=0, end_seconds=1)
        self.assertIn(
            "interval_on_non_video",
            m.check_feedback(r, context())[0]["citations"][0]["problems"],
        )

    def test_missing_citation_ineligible(self):
        r = fixture()
        r["feedback"][0]["citations"] = []
        self.assertEqual(
            m.check_feedback(r, context())[0]["citation_integrity"], "invalid"
        )

    def test_calibration_claim_rejected(self):
        r = fixture()
        r["uncertainty"]["calibration_status"] = "calibrated"
        with self.assertRaises(ValueError):
            m.check_feedback(r, context())

    def test_outside_elicited_range_rejected(self):
        r = fixture()
        r["uncertainty"]["interest_rating"]["high"] = 2
        with self.assertRaises(ValueError):
            m.check_feedback(r, context())

    def test_duplicate_ranking_rejected(self):
        r = fixture()
        r["editorial_ranking"][0]["candidate"] = "KEEP"
        with self.assertRaises(ValueError):
            m.check_feedback(r, context())


if __name__ == "__main__":
    unittest.main()
