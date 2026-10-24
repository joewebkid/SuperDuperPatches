import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from validate_catalog import ROOT, validate


class BundleWideTargetTests(unittest.TestCase):
    def test_orions_manifests_are_remotely_discoverable_by_bundle(self):
        index = json.loads((ROOT / "remote-index.json").read_text(encoding="utf-8"))
        entries = {entry["id"]: entry for entry in index["patches"]}
        for patch_id in ("controller-com-chillingo-orions-c5f88dd5", "orions2-100-force-composition"):
            entry = entries[patch_id]
            self.assertEqual(entry["bundleVersions"], [])
            self.assertEqual(entry["executableSha256"], [])
            data = (ROOT / entry["path"]).read_bytes().replace(b"\r\n", b"\n")
            self.assertEqual(entry["bytes"], len(data))
            self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())

    def check(self, kind, actions, enabled=False, target=None):
        patch_id = "test-bundle-wide"
        manifest = {
            "formatVersion": 1,
            "id": patch_id,
            "name": "Bundle-wide test",
            "kind": kind,
            "status": "experimental",
            "defaultEnabled": enabled,
            "target": target or {"bundleId": "test.bundle"},
            "actions": actions,
        }
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            path = Path(temp) / f"{patch_id}.sdpatch.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            return validate(path, set())

    def test_optional_cursor_can_match_all_bundle_versions(self):
        result = self.check("input", {"input": {"cursorMode": "relative", "cursorClickButton": "A"}})
        self.assertEqual(result["target"], {"bundleId": "test.bundle"})

    def test_force_composition_can_match_all_bundle_versions(self):
        result = self.check("compatibility", {"presentation": {"forceComposition": True}}, enabled=True)
        self.assertEqual(result["target"], {"bundleId": "test.bundle"})

    def test_other_actions_and_partial_constraints_are_rejected(self):
        cases = [
            ("input", {"input": {"cursorMode": "relative", "cursorClickButton": "A"}}, True, None),
            ("compatibility", {"eagl": {"forceDirectPresent": True}}, False, None),
            ("compatibility", {"presentation": {"forceComposition": True}}, True,
             {"bundleId": "test.bundle", "bundleVersions": ["1.0"]}),
        ]
        for kind, actions, enabled, target in cases:
            with self.subTest(kind=kind, actions=actions, target=target):
                with self.assertRaisesRegex(ValueError, "community target needs both"):
                    self.check(kind, actions, enabled, target)


if __name__ == "__main__":
    unittest.main()
