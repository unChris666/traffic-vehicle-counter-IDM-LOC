"""Offline publisher guards: fixtures never upload or download remote assets."""
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("b_v3_publisher", ROOT / ".github/scripts/phase8_publish_b_v3.py")
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


def fixture():
    payload = {"source_commit": "d" * 40, "downloads": [
        {"video_id": video_id, "url": f"https://www.kaggleusercontent.com/synthetic/{video_id}.mp4?token=fixture"}
        for video_id in publisher.VIDEO_IDS]}
    frames = (9052, 9128, 9077, 9022, 9017, 9124, 9138, 9032)
    assets = []
    for video_id, count in zip(publisher.VIDEO_IDS, frames):
        day, period = video_id.split("_")
        assets.append({"video_id": video_id, "filename": f"TGDI-{day.upper()}-{period.upper()}-b-v3-annotated.mp4",
                       "size_bytes": 100, "sha256": "a" * 64, "frame_count": count,
                       "source_output_path": f"/kaggle/working/synthetic/{video_id}/annotated.mp4",
                       "operational_total": 5, "measured_total": 2, "inferred_total": 3})
    manifest = {"schema_version": "phase8_b_v3_delivery_v1", "repository": publisher.REPOSITORY,
                "source_commit": "e" * 40, "assets": assets, "source_bundle_binding_sha256": "a" * 64,
                "executed_configuration_files": [{"path": name, "sha256": "c" * 64}
                    for name in sorted(publisher.REQUIRED_CONFIGURATION_FILES)],
                "executed_source_files": [{"path": name, "sha256": "b" * 64}
                                          for name in sorted(publisher.REQUIRED_SOURCE_FILES)]}
    return payload, manifest


class ManifestGuards(unittest.TestCase):
    def reject(self, change):
        payload, manifest = fixture()
        change(payload, manifest)
        with self.assertRaises(publisher.PublicationError):
            publisher.validate_payload_manifest(payload, manifest)

    def test_delivery_commit_can_differ_from_executed_commit(self):
        payload, manifest = fixture()
        delivery, executed, plan = publisher.validate_payload_manifest(payload, manifest)
        self.assertNotEqual(delivery, executed)
        self.assertEqual(len(plan), 8)
        self.assertEqual(sum(row["frame_count"] for row in plan), 72590)

    def test_input_objects_not_modified(self):
        payload, manifest = fixture()
        original = deepcopy((payload, manifest))
        publisher.validate_payload_manifest(payload, manifest)
        self.assertEqual((payload, manifest), original)

    def test_wrong_repository_rejected(self):
        self.reject(lambda p, m: m.update(repository="other/repository"))

    def test_short_dispatch_sha_rejected(self):
        self.reject(lambda p, m: p.update(source_commit="abcdef0"))

    def test_mismatched_executed_commit_alias_rejected(self):
        self.reject(lambda p, m: m.update(executed_source_commit="f" * 40))

    def test_bad_mp4_sha_rejected(self):
        self.reject(lambda p, m: m["assets"][0].update(sha256="not-a-sha"))

    def test_unsafe_filename_rejected(self):
        self.reject(lambda p, m: m["assets"][0].update(filename="../../anything.mp4"))

    def test_missing_or_duplicate_video_rejected(self):
        self.reject(lambda p, m: p["downloads"].pop())
        self.reject(lambda p, m: m["assets"][1].update(video_id=m["assets"][0]["video_id"]))

    def test_operational_breakdown_must_reconcile(self):
        self.reject(lambda p, m: m["assets"][0].update(inferred_total=4))

    def test_boolean_is_not_a_frame_count(self):
        self.reject(lambda p, m: m["assets"][0].update(frame_count=True))

    def test_signed_url_cannot_enter_retained_manifest(self):
        self.reject(lambda p, m: m.update(unexpected_url=p["downloads"][0]["url"]))

    def test_executed_source_set_and_hashes_are_required(self):
        self.reject(lambda p, m: m["executed_source_files"].pop())
        self.reject(lambda p, m: m["executed_source_files"][0].update(sha256="c" * 63))

    def test_review_and_policy_configuration_bindings_are_required(self):
        self.reject(lambda p, m: m.pop("executed_configuration_files"))
        self.reject(lambda p, m: m["executed_configuration_files"].pop())
        self.reject(lambda p, m: m["executed_configuration_files"][0].update(path="results/other.json"))
        self.reject(lambda p, m: m["executed_configuration_files"][0].update(sha256="invalid"))

    def test_source_bundle_binding_is_required(self):
        self.reject(lambda p, m: m.pop("source_bundle_binding_sha256"))
        self.reject(lambda p, m: m.update(source_bundle_binding_sha256="not-a-source-binding"))

    def test_url_scope_and_transport_guards(self):
        for url in ("http://www.kaggleusercontent.com/a", "https://example.com/a",
                    "https://www.kaggleusercontent.com.evil.test/a",
                    "https://www.kaggleusercontent.com:443/a", "https://u:p@www.kaggleusercontent.com/a",
                    "https://www.kaggleusercontent.com/a#fragment", "https://www.kaggleusercontent.com/a\ncommand"):
            with self.subTest(url=url):
                with self.assertRaises(publisher.PublicationError):
                    publisher.validate_url(url)

    def test_urls_masked_before_use_and_percent_escaped(self):
        output = io.StringIO()
        with patch("sys.stdout", output):
            publisher.validate_url("https://www.kaggleusercontent.com/a?token=a%2Fb", mask=True)
        self.assertIn("::add-mask::https://www.kaggleusercontent.com/a?token=a%252Fb", output.getvalue())

    def test_http_redirects_never_followed(self):
        self.assertIsNone(publisher.NoRedirects().redirect_request(None, None, 302, "redirect", {}, "https://example.com"))


class SourceAndAssetGuards(unittest.TestCase):
    def test_publication_receipt_uses_final_urls_and_distinct_commit_bindings(self):
        payload, manifest = fixture()
        content = b"synthetic completed MP4"
        for asset in manifest["assets"]:
            asset.update(size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
        delivery, executed, plan = publisher.validate_payload_manifest(payload, manifest)
        state = {"created": False, "draft": True, "assets": {}, "target": None, "uploaded_receipt": None}
        lock = __import__("threading").Lock()
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            manifest_path = work / "source_manifest.json"
            publisher.write_json(manifest_path, manifest)

            def remote_snapshot():
                rows = []
                for record in state["assets"].values():
                    row = dict(record)
                    tag = "untagged-draft-fixture" if state["draft"] else publisher.TAG
                    row["browser_download_url"] = f"https://github.com/{publisher.REPOSITORY}/releases/download/{tag}/{row['name']}"
                    rows.append(row)
                return {"id": 123, "tag_name": publisher.TAG, "draft": state["draft"],
                        "target_commitish": state["target"], "assets": rows,
                        "html_url": f"https://github.com/{publisher.REPOSITORY}/releases/tag/{publisher.TAG}",
                        "published_at": None if state["draft"] else "2026-10-18T00:00:00Z"}

            def api(endpoint, *, method="GET", body=None, allow_missing=False):
                if "/releases?" in endpoint:
                    return []
                if "/releases/tags/" in endpoint or "/git/ref/tags/" in endpoint:
                    return None
                if endpoint.endswith("/commits/" + publisher.TAG):
                    return {"sha": executed}
                if endpoint.endswith("/releases") and method == "POST":
                    state.update(created=True, target=body["target_commitish"])
                    return remote_snapshot()
                if endpoint.endswith("/releases/123"):
                    if method == "PATCH":
                        state["draft"] = body["draft"]
                    return remote_snapshot()
                self.fail("Unexpected mocked endpoint")

            def command(arguments, **kwargs):
                self.assertEqual(arguments[:4], ["gh", "release", "upload", publisher.TAG])
                path = Path(arguments[4])
                with lock:
                    state["assets"][path.name] = {"id": len(state["assets"]) + 1, "name": path.name,
                        "state": "uploaded", "size": path.stat().st_size, "digest": "sha256:" + publisher.sha256(path)}
                    if path.name == "publication_receipt.json":
                        state["uploaded_receipt"] = json.loads(path.read_text())
                return ""

            def download(item, destination):
                (destination / item["filename"]).write_bytes(content)
                return {"video_id": item["video_id"], "filename": item["filename"], "size_bytes": len(content),
                        "sha256": hashlib.sha256(content).hexdigest(), "download_url_or_secret_retained": False}

            with patch.object(publisher, "api", side_effect=api), patch.object(publisher, "command", side_effect=command), \
                 patch.object(publisher, "download_one", side_effect=download), patch.dict("os.environ", {"GITHUB_RUN_ID": "99"}), \
                 patch("sys.stdout", io.StringIO()):
                publisher.publish(work, manifest_path, manifest, plan, delivery, executed, work,
                                  {"status": "UPLOAD_AUTHORIZATION_VERIFIED"})
            receipt = state["uploaded_receipt"]
            self.assertFalse(state["draft"])
            self.assertEqual(len(state["assets"]), 11)
            self.assertEqual(state["target"], executed)
            self.assertEqual(receipt["delivery_source_commit"], delivery)
            self.assertEqual(receipt["executed_source_commit"], executed)
            self.assertEqual(receipt["executed_configuration_files"], manifest["executed_configuration_files"])
            self.assertEqual(receipt["source_bundle_binding_sha256"], manifest["source_bundle_binding_sha256"])
            self.assertNotIn("untagged-", json.dumps(receipt))
            self.assertNotIn("kaggleusercontent", json.dumps(receipt))
            self.assertTrue(all("/download/" + publisher.TAG + "/" in row["browser_download_url"]
                                for row in receipt["assets"] + receipt["supplemental_assets"]))

    def test_distinct_delivery_commit_binds_unchanged_executed_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL).decode().strip()
            git("init")
            git("config", "user.name", "Synthetic test")
            git("config", "user.email", "synthetic@example.invalid")
            files, configurations = [], []
            for name in sorted(publisher.REQUIRED_SOURCE_FILES | publisher.REQUIRED_CONFIGURATION_FILES):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# synthetic source\n")
                target = files if name in publisher.REQUIRED_SOURCE_FILES else configurations
                target.append({"path": name, "sha256": publisher.sha256(path)})
            git("add", ".")
            git("commit", "-m", "Synthetic executed source")
            executed = git("rev-parse", "HEAD")
            (root / "delivery.txt").write_text("Later retained evidence\n")
            git("add", ".")
            git("commit", "-m", "Synthetic later delivery")
            delivery = git("rev-parse", "HEAD")
            with patch.object(publisher, "api", return_value={"sha": executed}):
                publisher.verify_source_binding(root, delivery, executed, {"executed_source_files": files, "executed_configuration_files": configurations})
            (root / files[0]["path"]).write_text("# changed after execution\n")
            with self.assertRaisesRegex(publisher.PublicationError, "source SHA differs"):
                publisher.verify_source_binding(root, delivery, executed, {"executed_source_files": files, "executed_configuration_files": configurations})

    def test_configuration_changed_after_execution_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Synthetic test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "synthetic@example.invalid"], check=True)
            files, configurations = [], []
            for name in sorted(publisher.REQUIRED_SOURCE_FILES | publisher.REQUIRED_CONFIGURATION_FILES):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("# synthetic source or configuration fixture\n")
                records = files if name in publisher.REQUIRED_SOURCE_FILES else configurations
                records.append({"path": name, "sha256": publisher.sha256(target)})
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-m", "Synthetic executed snapshot"], check=True, capture_output=True)
            executed = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"]).decode().strip()
            (root / configurations[0]["path"]).write_text("Changed reviewed decisions after execution\n")
            with self.assertRaisesRegex(publisher.PublicationError, "source SHA differs"):
                publisher.verify_source_binding(root, executed, executed,
                    {"executed_source_files": files, "executed_configuration_files": configurations})

    def test_existing_draft_rejected_before_any_upload(self):
        with patch.object(publisher, "api", return_value=[{"tag_name": publisher.TAG, "draft": True}]) as mocked:
            with self.assertRaisesRegex(publisher.PublicationError, "draft already exists"):
                publisher.require_unused_tag(publisher.TAG)
        self.assertEqual(mocked.call_count, 1)

    def test_server_digest_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "video.mp4"
            path.write_bytes(b"synthetic fixture")
            remote = {"name": path.name, "state": "uploaded", "size": path.stat().st_size,
                      "digest": "sha256:" + "0" * 64}
            with self.assertRaisesRegex(publisher.PublicationError, "asset SHA differs"):
                publisher.verify_remote_asset(remote, path)

    def test_successful_transport_record_never_retains_capability(self):
        data = b"synthetic MP4 delivery bytes"
        class Response(io.BytesIO):
            status = 200
            headers = {"Content-Length": str(len(data))}
            def geturl(self):
                return "https://www.kaggleusercontent.com/a?token=fixture"
        class Opener:
            def open(self, request, timeout):
                return Response(data)
        item = {"video_id": "weekday_pagi", "filename": "TGDI-WEEKDAY-PAGI-b-v3-annotated.mp4",
                "url": "https://www.kaggleusercontent.com/a?token=fixture", "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest()}
        with tempfile.TemporaryDirectory() as directory, patch.object(publisher, "build_opener", return_value=Opener()):
            record = publisher.download_one(item, Path(directory))
            self.assertEqual((Path(directory) / item["filename"]).read_bytes(), data)
        self.assertNotIn("token=fixture", json.dumps(record))
        self.assertNotIn("kaggleusercontent", json.dumps(record))


if __name__ == "__main__":
    unittest.main(verbosity=2)
