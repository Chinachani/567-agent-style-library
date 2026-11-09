import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

SPEC = importlib.util.spec_from_file_location("sync", Path(__file__).resolve().parents[1] / "scripts/sync.py")
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)

MIT = "MIT License\nCopyright (c) 2026 Test\nPermission is hereby granted, free of charge\n"
REV = "a" * 40
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><rect fill="url(#paint)"/></svg>'


def template(key="legacy"):
    return {"kind": "design-system", "slug": key, "name": "Legacy", "category": "dev", "vibe": "dark", "blurb": "A style",
            "license": "MIT", "origin": {"upstream": "https://github.com/VoltAgent/awesome-design-md", "note": "Adapted from MIT content."},
            "resources": [sync.text_resource("DESIGN.md", "# Legacy", "spec"), sync.text_resource("theme.css", "@theme { --color-primary: #fff; }", "theme")]}


def style(key="editorial"):
    return {"slug": key, "name": "编辑杂志风", "nameEn": "Editorial", "description": "留白与杂志排版。", "descriptionEn": "Editorial spacing.",
            "category": "minimal", "colors": {"primary": "#111", "secondary": "#fff", "accent": ["#123456"]},
            "keywords": ["留白"], "cover": f"/styles/{key}.svg"}


def result(key, assets=None):
    entry = template(key)
    sync.add_notices(entry, sync.notice(entry, sync.VETTA), MIT)
    return {"templates": [entry], "assets": assets or {}, "license": MIT, "revision": REV, "metadataUrl": "https://example.com/catalog"}


def failed():
    raise sync.SyncError("offline")


class UpstreamContractTests(unittest.TestCase):
    def test_vetta_curated_rows_get_repository_provenance(self):
        entry = template()
        entry["origin"] = {"type": "curated", "sourceUrl": "https://example.com/reference"}

        def fetch(url, limit=sync.MAX_FILE):
            if url.endswith(".json"):
                return sync.json_bytes({"schemaVersion": 1, "templates": [entry]})
            return MIT.encode()

        data = sync.import_vetta(fetch, lambda _: REV)
        imported = data["templates"][0]
        self.assertEqual(imported["origin"]["upstream"], f"https://github.com/{sync.VETTA}")
        self.assertEqual(imported["origin"]["sourceUrl"], "https://example.com/reference")
        self.assertNotIn("upstream", entry["origin"])

    def test_vetta_mirrors_are_one_import_preserving_entry_license_and_origin(self):
        entry = template()
        entry["license"] = "CC-BY-4.0"
        entry["origin"] = {"upstream": "https://www.stylekit.top", "sourceUrl": "https://stylekit.top/styles/editorial", "note": "Previously adapted guide."}
        calls = []

        def fetch(url, limit=sync.MAX_FILE):
            calls.append(url)
            if "raw.githubusercontent.com/openvetta" in url and url.endswith(".json"):
                raise sync.SyncError("raw offline")
            if url.endswith(".json"):
                return sync.json_bytes({"schemaVersion": 1, "templates": [entry, entry]})
            return MIT.encode()

        data = sync.import_vetta(fetch, lambda _: REV)
        self.assertEqual(len(data["templates"]), 1)
        imported = data["templates"][0]
        self.assertEqual(imported["license"], "CC-BY-4.0")
        self.assertEqual(imported["origin"], entry["origin"])
        self.assertIn("Previously adapted guide", imported["attribution"])
        self.assertIn("https://creativecommons.org/licenses/by/4.0/", imported["attribution"])
        self.assertEqual(len([u for u in calls if u.endswith(".json")]), 2)

    def test_conflicting_duplicates_fail_instead_of_arbitrarily_overwriting(self):
        other = template()
        other["blurb"] = "Conflicting text"
        with self.assertRaises(sync.SyncError):
            sync.validate_templates([template(), other])

    def test_unknown_license_and_frontmatter_fail(self):
        for mutate in (lambda e: e.update(license="unknown"), lambda e: e["resources"][0].update(content="---\nsource: malicious\n---")):
            entry = template()
            mutate(entry)
            with self.assertRaises(sync.SyncError):
                sync.validate_templates([entry])

    def test_source_urls_cannot_inject_frontmatter_and_taglines_match_client_contract(self):
        entry = template()
        entry["origin"]["upstream"] = "https://example.com\nlicense: other"
        with self.assertRaises(sync.SyncError):
            sync.validate_templates([entry])
        entry = template()
        entry["tagline"] = {"zh": "只有中文"}
        with self.assertRaises(sync.SyncError):
            sync.validate_templates([entry])

    def test_stylekit_api_is_adapted_with_mirrored_cover_and_full_mit_notice(self):
        calls = []

        def fetch(url, limit=sync.MAX_FILE):
            calls.append(url)
            if url == sync.STYLEKIT_API:
                return sync.json_bytes({"total": 1, "styles": [style()]})
            if url.endswith(".svg"):
                return SVG
            return MIT.encode()

        data = sync.import_stylekit(fetch, lambda _: REV)
        entry = data["templates"][0]
        self.assertEqual(entry["slug"], "stylekit-editorial")
        self.assertEqual(entry["vibe"], "light")
        self.assertEqual(entry["tagline"]["zh"], style()["description"])
        self.assertEqual(entry["provenance"]["upstreamMetadata"], style())
        self.assertIn("assets/stylekit/editorial/cover.svg", data["assets"])
        self.assertTrue(any(r["content"] == MIT for r in entry["resources"] if r["path"] == "567-LICENSE.txt"))
        self.assertEqual(entry["resources"][2]["url"], "assets/stylekit/editorial/cover.svg")
        self.assertTrue(any(REV in u and u.endswith("public/styles/editorial.svg") for u in calls))

    def test_stylekit_api_failure_uses_literal_repo_metadata_without_evaluation(self):
        value = style()
        literal = 'export const stylesMeta: StyleMeta[] = ' + json.dumps([value], ensure_ascii=False) + ';'

        def fetch(url, limit=sync.MAX_FILE):
            if url == sync.STYLEKIT_API:
                raise sync.SyncError("API offline")
            if url.endswith("meta-registry.ts"):
                return literal.encode()
            return SVG if url.endswith(".svg") else MIT.encode()

        data = sync.import_stylekit(fetch, lambda _: REV)
        self.assertEqual(len(data["templates"]), 1)
        self.assertIn("meta-registry.ts", data["metadataUrl"])

    def test_jpeg_covers_are_mirrored_using_canonical_slug_path(self):
        value = style("wabi-sabi")
        value["cover"] = "/styles/wabi-sabi.jpg"
        jpeg = b"\xff\xd8\xff\xe0test"

        def fetch(url, limit=sync.MAX_FILE):
            if url == sync.STYLEKIT_API:
                return sync.json_bytes({"total": 1, "styles": [value]})
            return jpeg if url.endswith(".jpg") else MIT.encode()

        data = sync.import_stylekit(fetch, lambda _: REV)
        self.assertEqual(data["assets"]["assets/stylekit/wabi-sabi/cover.jpg"], jpeg)
        self.assertEqual(data["templates"][0]["resources"][2]["path"], "cover.jpg")
        with self.assertRaises(sync.SyncError):
            sync.validate_static(b'<html>error</html>', "cover.jpg")

    def test_invalid_stylekit_cover_is_skipped_without_dropping_style(self):
        value = style("unsafe-cover")
        invalid_svg = b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://evil.invalid/pixel"/></svg>'

        def fetch(url, limit=sync.MAX_FILE):
            if url == sync.STYLEKIT_API:
                return sync.json_bytes({"total": 1, "styles": [value]})
            return invalid_svg if url.endswith(".svg") else MIT.encode()

        data = sync.import_stylekit(fetch, lambda _: REV)
        self.assertEqual([entry["slug"] for entry in data["templates"]], ["stylekit-unsafe-cover"])
        self.assertEqual(data["assets"], {})
        self.assertFalse(any(resource.get("role") == "cover" for resource in data["templates"][0]["resources"]))
        self.assertIn("cover omitted", data["templates"][0]["origin"]["note"])

    def test_literal_parser_accepts_trailing_commas_comments_unicode_and_rejects_code(self):
        parsed = sync.literal_registry('export const stylesMeta: StyleMeta[] = [/* data */{slug: "编辑", colors: {accent: ["#fff",],},},]; // end')
        self.assertEqual(parsed["styles"][0]["slug"], "编辑")
        for expression in ('[fetch("https://evil.invalid")]', '[{slug: process.env.SECRET}]', '[...styles]', '[{}]; run()'):
            with self.assertRaises(sync.SyncError):
                sync.literal_registry('export const stylesMeta: StyleMeta[] = ' + expression)

    def test_incomplete_or_invalid_stylekit_catalog_is_rejected(self):
        bad = style()
        bad["colors"]["primary"] = "#fff; @import url(https://evil.invalid)"
        for body in ({"total": 2, "styles": [style()]}, {"total": 0, "styles": []}, {"total": 1, "styles": [bad]}):
            with self.assertRaises(sync.SyncError):
                sync.stylekit_catalog(body)

    def test_untrusted_style_names_do_not_enter_css(self):
        value = style()
        value["nameEn"] = "*/ @import url(https://evil.invalid); /*"
        entry = sync.stylekit_entry(value)
        css = next(r["content"] for r in entry["resources"] if r.get("role") == "theme")
        self.assertNotIn("evil.invalid", css)

    def test_rgba_palettes_preserve_transparency_and_reject_css_injection(self):
        value = style("glassmorphism")
        value["colors"].update(primary="rgba(255, 255, 255, 0.25)", secondary="rgba(255, 255, 255, 0.18)")
        entry = sync.stylekit_entry(value)
        css = entry["resources"][1]["content"]
        self.assertIn("rgba(255, 255, 255, 0.25)", css)
        for color in ("rgba(999,0,0,0.5)", "rgba(0,0,0,1.1)", "rgba(0,0,0,-1)", "rgba(0,0,0,.5); color:red", "var(--malicious)"):
            with self.assertRaises(sync.SyncError):
                sync.palette_color(color)

    def test_paths_and_binary_urls_cannot_escape_declared_source(self):
        for path in ("../escape.svg", "/absolute.svg", "a//b.svg", "a\\b.svg", "a/%2e%2e/b.svg", "a\nb.svg", "script.js", ".github/workflows/inject.yml"):
            with self.assertRaises(sync.SyncError):
                sync.safe_path(path)
        for url in ("https://evil.invalid/templates/test/cover.png", "https://raw.githubusercontent.com/other/repo/main/templates/cover.png", "templates/%2e%2e/cover.png"):
            with self.assertRaises(sync.SyncError):
                sync.canonical_binary(url, sync.VETTA, REV)
        self.assertIn(REV, sync.canonical_binary("templates/test/cover.png", sync.VETTA, REV))

    def test_svg_rejects_active_external_content_and_allows_local_paint_servers(self):
        self.assertEqual(sync.validate_static(SVG, "cover.svg"), SVG)
        for data in (b'<svg><script>alert(1)</script></svg>', b'<svg onload="alert(1)"/>', b'<svg><image href="https://evil.invalid/pixel"/></svg>', b'<svg><style>@import url(https://evil.invalid)</style></svg>', b'<!DOCTYPE svg><svg/>', b'<svg><foreignObject/></svg>'):
            with self.assertRaises(sync.SyncError):
                sync.validate_static(data, "cover.svg")

    def test_redirect_validation_rejects_non_public_or_unlisted_hosts(self):
        for url in ("http://stylekit.top", "https://127.0.0.1", "https://evil.invalid", "https://u:p@stylekit.top", "https://stylekit.top:8443"):
            with self.assertRaises(sync.SyncError):
                sync.validate_url(url)


class DownloadTests(unittest.TestCase):
    class Response:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, amount):
            return self.body[:amount]

    @patch.object(sync.time, "sleep")
    @patch.object(sync.urllib.request, "build_opener")
    def test_transient_download_failure_retries_with_bounded_backoff(self, opener, sleep):
        opener.return_value.open.side_effect = [URLError("offline"), URLError("offline"), self.Response(b"data")]
        self.assertEqual(sync.download("https://stylekit.top/api/styles"), b"data")
        self.assertEqual(opener.return_value.open.call_count, 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1, 2])

    @patch.object(sync.time, "sleep")
    @patch.object(sync.urllib.request, "build_opener")
    def test_permanent_http_failure_does_not_retry(self, opener, sleep):
        opener.return_value.open.side_effect = HTTPError("https://stylekit.top/api/styles", 404, "Not found", {}, None)
        with self.assertRaises(sync.SyncError):
            sync.download("https://stylekit.top/api/styles")
        self.assertEqual(opener.return_value.open.call_count, 1)
        sleep.assert_not_called()

    @patch.object(sync.urllib.request, "build_opener")
    def test_oversized_response_is_rejected(self, opener):
        opener.return_value.open.return_value = self.Response(b"too large")
        with self.assertRaises(sync.SyncError):
            sync.download("https://stylekit.top/api/styles", 4)


class SyncLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def run_sync(self, vetta=None, stylekit=None):
        return sync.sync(self.root, {"vetta": vetta or (lambda: result("legacy")), "stylekit": stylekit or (lambda: result("stylekit-editorial"))})

    def catalog(self):
        return json.loads((self.root / ".vetta/design-templates.json").read_bytes())

    def files(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def test_bootstrap_refresh_failure_and_recovery_keep_complete_aggregate(self):
        self.assertEqual(self.run_sync(), [])
        self.assertEqual([e["slug"] for e in self.catalog()["templates"]], ["legacy", "stylekit-editorial"])
        self.assertEqual(self.run_sync(vetta=failed, stylekit=lambda: result("stylekit-updated")), ["vetta"])
        self.assertEqual([e["slug"] for e in self.catalog()["templates"]], ["legacy", "stylekit-updated"])
        self.assertEqual(self.run_sync(vetta=lambda: result("new-legacy")), [])
        self.assertEqual([e["slug"] for e in self.catalog()["templates"]], ["new-legacy", "stylekit-editorial"])

    def test_bootstrap_one_source_failure_writes_nothing(self):
        self.assertEqual(self.run_sync(vetta=failed), ["vetta"])
        self.assertEqual(self.files(), {})

    def test_unchanged_import_and_unrelated_repo_revision_produce_no_file_changes(self):
        self.run_sync()
        before = self.files()
        mtimes = {p: p.stat().st_mtime_ns for p in self.root.rglob("*") if p.is_file()}
        updated = result("legacy")
        updated["revision"] = "b" * 40
        self.run_sync(vetta=lambda: updated)
        self.assertEqual(self.files(), before)
        self.assertTrue(all(p.stat().st_mtime_ns == stamp for p, stamp in mtimes.items()))

    def test_failed_source_retains_assets_while_removed_successful_assets_are_pruned(self):
        one = result("legacy", {"assets/vetta/legacy/cover.svg": SVG})
        two = result("stylekit-editorial", {"assets/stylekit/editorial/cover.svg": SVG})
        self.run_sync(lambda: one, lambda: two)
        self.run_sync(vetta=failed)
        self.assertTrue((self.root / "assets/vetta/legacy/cover.svg").exists())
        self.assertFalse((self.root / "assets/stylekit/editorial/cover.svg").exists())

    def test_all_sources_fail_preserving_bytes_and_catalog_version(self):
        self.run_sync()
        before = self.files()
        self.assertEqual(self.run_sync(failed, failed), ["vetta", "stylekit"])
        self.assertEqual(before, self.files())

    def test_cross_source_collision_never_changes_published_tree(self):
        self.run_sync()
        before = self.files()
        with self.assertRaises(sync.SyncError):
            self.run_sync(stylekit=lambda: result("legacy"))
        self.assertEqual(before, self.files())

    def test_offline_check_detects_modified_catalog_and_source_hashes(self):
        self.run_sync()
        sync.verify(self.root)
        path = self.root / ".vetta/design-templates.json"
        path.write_text('{}')
        with self.assertRaises(sync.SyncError):
            sync.verify(self.root)

    def test_corrupt_retained_asset_fails_without_publishing_partial_tree(self):
        one = result("legacy", {"assets/vetta/legacy/cover.svg": SVG})
        self.run_sync(vetta=lambda: one)
        (self.root / "assets/vetta/legacy/cover.svg").write_bytes(b"corrupt")
        before = self.files()
        with self.assertRaises(sync.SyncError):
            self.run_sync(vetta=failed)
        self.assertEqual(before, self.files())

    def test_output_symlinks_cannot_write_outside_repository(self):
        with tempfile.TemporaryDirectory() as external:
            (self.root / ".vetta").symlink_to(external, target_is_directory=True)
            with self.assertRaises(sync.SyncError):
                self.run_sync()
            self.assertEqual(list(Path(external).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
