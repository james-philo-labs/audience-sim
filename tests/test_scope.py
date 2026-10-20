import copy, json, sys, unittest
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1] / "engine"))
from personas import assemble

ROOT = HERE.parents[1]


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.profile = next(
            p
            for p in json.loads((ROOT / "engine/profiles.json").read_text())["profiles"]
            if p["id"] == "evaluation-researcher"
        )

    def test_opus_excludes_unselected_gdpval_catalog(self):
        out, meta = assemble(self.profile, "opus")
        self.assertNotIn("post_overrides", out)
        self.assertEqual(out["reading_goal"], self.profile["reading_goal"])
        self.assertNotIn("four submission bundles", json.dumps(out))
        self.assertEqual(meta["withheld_override_keys"], ["3dcodeverse", "gdpval"])

    def test_gdpval_applies_only_selected_fields(self):
        out, meta = assemble(self.profile, "gdpval")
        self.assertEqual(
            out["reading_goal"],
            self.profile["post_overrides"]["gdpval"]["reading_goal"],
        )
        self.assertNotIn("post_overrides", out)
        self.assertEqual(meta["applied_override"], "gdpval")

    def test_unknown_post_fails_closed(self):
        with self.assertRaises(ValueError):
            assemble(self.profile, "unexpected")

    def test_profile_is_not_mutated(self):
        before = copy.deepcopy(self.profile)
        out, _ = assemble(self.profile, "opus")
        out["interests"].append("changed")
        self.assertEqual(self.profile, before)

    def test_nested_selected_override_rejected(self):
        self.profile["post_overrides"]["opus"] = {
            "reading_goal": {"nested": "injected"}
        }
        with self.assertRaises(ValueError):
            assemble(self.profile, "opus")

    def test_unsupported_selected_override_field_rejected(self):
        self.profile["post_overrides"]["opus"] = {"system_prompt": "injected"}
        with self.assertRaises(ValueError):
            assemble(self.profile, "opus")

    def test_top_level_unapproved_fields_not_forwarded(self):
        self.profile["unrelated_notes"] = {"hidden": "other article"}
        out, _ = assemble(self.profile, "opus")
        self.assertNotIn("unrelated_notes", out)

    def test_all_profiles_base_compatible(self):
        for p in json.loads((ROOT / "engine/profiles.json").read_text())["profiles"]:
            out, _ = assemble(p, "opus")
            self.assertEqual(out["id"], p["id"])
            self.assertNotIn("post_overrides", out)

    def test_selected_3d_scope_is_neutral_and_isolated_for_every_role(self):
        catalog = json.loads((ROOT / "engine/profiles.json").read_text())
        for profile in catalog["profiles"]:
            before = copy.deepcopy(profile)
            out, meta = assemble(profile, "3dcodeverse")
            self.assertEqual(out["reading_goal"], profile["post_overrides"]["3dcodeverse"]["reading_goal"])
            self.assertEqual(meta["applied_override"], "3dcodeverse")
            self.assertTrue(meta["catalog_not_forwarded"])
            self.assertNotIn("post_overrides", out)
            self.assertNotIn("four submission bundles", json.dumps(out))
            for answer in ["0.933", "0.34", "12/12", "90%"]:
                self.assertNotIn(answer, json.dumps(out))
            self.assertEqual(profile, before)


if __name__ == "__main__":
    unittest.main()
