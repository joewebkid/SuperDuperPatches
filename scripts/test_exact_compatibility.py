"""Exact-revision compatibility policies newly offered by the public catalog."""

import json
import tempfile
import unittest
from pathlib import Path

from validate_catalog import CATALOG, validate


class ExactCompatibilityTests(unittest.TestCase):
    def test_exact_audio_and_renderer_manifests_validate(self):
        for bundle, patch_id in (
            ("com.ea.mirrorsedge.bv", "mirrors-edge-157-wave-format"),
            ("com.ea.candcra.row", "red-alert-110-audio-queue"),
            ("com.gameloft.NOVA", "nova-sole-drawable-present"),
        ):
            path = CATALOG / bundle / f"{patch_id}.sdpatch.json"
            manifest = validate(path, set())
            self.assertEqual(manifest["target"]["bundleId"], bundle)
            self.assertEqual(manifest["status"], "experimental")
            self.assertFalse(manifest["defaultEnabled"])
            self.assertEqual(len(manifest["target"]["executableSha256"]), 1)

    def test_audio_policy_rejects_unsupported_or_non_boolean_values(self):
        source = CATALOG / "com.ea.candcra.row" / "red-alert-110-audio-queue.sdpatch.json"
        original = json.loads(source.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(dir=CATALOG) as directory:
            path = Path(directory) / source.name
            for audio in (
                {"legacyMp3PcmAudioQueue": "true"},
                {"arbitraryAudioOverride": True},
            ):
                modified = {**original, "actions": {"audio": audio}}
                path.write_text(json.dumps(modified), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "actions.audio contains an unsupported action"):
                    validate(path, set())


if __name__ == "__main__":
    unittest.main()
