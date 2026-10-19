from pathlib import Path
import tempfile, json, unittest
import bundle, media


class BundleTests(unittest.TestCase):
    def article(self, root, blocks=None):
        p = root / "article.json"
        p.write_text(
            json.dumps(
                {
                    "id": "fixture",
                    "version": "v1",
                    "title": "<script>escaped source</script>",
                    "main_end_id": "closing",
                    "blocks": blocks
                    or [
                        {
                            "id": "closing",
                            "type": "paragraph",
                            "text": "Keep <script>untrusted text</script> escaped.",
                        }
                    ],
                }
            )
        )
        return p

    def test_source_is_escaped_and_sealed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            out = p / "bundle"
            bundle.freeze(self.article(p), out)
            html = (out / "site/index.html").read_text()
            self.assertNotIn("<script>", html)
            self.assertIn("&lt;script&gt;", html)
            media.validate_seal(out)

    def test_tamper_and_extra_file_fail_closed(self):
        for mutation in ["change", "extra"]:
            with tempfile.TemporaryDirectory() as d:
                p = Path(d)
                out = p / "bundle"
                bundle.freeze(self.article(p), out)
                if mutation == "change":
                    (out / "site/index.html").write_text("changed")
                else:
                    (out / "site/added.txt").write_text("unsealed")
                with self.assertRaises(ValueError):
                    media.validate_seal(out)

    def test_parent_path_cannot_become_bundled_media(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            article = self.article(
                p,
                [
                    {
                        "id": "outside",
                        "type": "image",
                        "text": "bad",
                        "asset": "../private.png",
                    },
                    {"id": "closing", "type": "paragraph", "text": "end"},
                ],
            )
            with self.assertRaisesRegex(ValueError, "outside"):
                bundle.freeze(article, p / "bundle")

    def test_unknown_or_missing_main_end_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            article = self.article(p)
            a = json.loads(article.read_text())
            a["main_end_id"] = "missing"
            article.write_text(json.dumps(a))
            with self.assertRaises(ValueError):
                bundle.freeze(article, p / "bundle")

    def test_existing_bundle_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            article = self.article(p)
            out = p / "bundle"
            bundle.freeze(article, out)
            with self.assertRaises(ValueError):
                bundle.freeze(article, out)
