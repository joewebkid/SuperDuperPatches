"""Regression tests for the untrusted issue-to-draft-PR boundary."""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path
from unittest import TestCase


sys.path.insert(0, str(Path(__file__).resolve().parent))

from issue_to_patch import validate_submission  # noqa: E402


def input_manifest() -> dict[str, object]:
    return {
        "formatVersion": 1,
        "id": "sample-controller",
        "name": "Sample controller layout",
        "kind": "input",
        "status": "experimental",
        "defaultEnabled": False,
        "priority": 100,
        "target": {
            "bundleId": "com.example.game",
            "bundleVersions": ["1.0"],
            "executableSha256": ["a" * 64],
            "allowLegacyWeakMatch": False,
        },
        "actions": {
            "input": {
                "buttons": [
                    {"button": "A", "x": 420, "y": 280},
                    {"button": "RightShoulder", "x": 455, "y": 220},
                ],
                "leftDeadzone": 0.1,
                "rightDeadzone": 0.15,
                "accelerometerMode": "gamepad",
                "tiltStick": "left",
                "cursorStick": "right",
            }
        },
    }


class IssueToPatchValidationTests(TestCase):
    def test_accepts_half_turn_and_rejects_non_boolean_action(self):
        manifest = input_manifest()
        manifest["kind"] = "compatibility"
        manifest["actions"] = {"presentation": {"presentRotate180": True}}
        validate_submission(manifest)
        manifest["actions"]["presentation"]["presentRotate180"] = 180
        with self.assertRaises(ValueError):
            validate_submission(manifest)

    def test_accepts_current_android_input_contract(self) -> None:
        patch_id, bundle_id = validate_submission(input_manifest())
        self.assertEqual(patch_id, "sample-controller")
        self.assertEqual(bundle_id, "com.example.game")

    def test_rejects_touch_and_tilt_on_the_same_stick(self) -> None:
        manifest = deepcopy(input_manifest())
        manifest["actions"]["input"]["leftStickToTouch"] = {
            "x": 20,
            "y": 180,
            "width": 100,
            "height": 110,
        }
        with self.assertRaises(ValueError):
            validate_submission(manifest)

    def test_rejects_unimplemented_resource_mod_submission(self) -> None:
        manifest = input_manifest()
        manifest["kind"] = "resource-mod"
        with self.assertRaises(ValueError):
            validate_submission(manifest)

    def test_accepts_current_typed_compatibility_contract(self) -> None:
        manifest = input_manifest()
        manifest["kind"] = "compatibility"
        manifest["actions"] = {
            "presentation": {"disableTouchRotation": True},
            "eagl": {"forceLandscapeRenderbuffer": True},
            "gles": {"forceLandscapeViewport": True},
        }
        validate_submission(manifest)

    def test_accepts_presentation_layout_contract(self) -> None:
        manifest = input_manifest()
        manifest["kind"] = "presentation-layout"
        manifest["actions"] = {"presentation": {"outputFit": "stretch"}}
        validate_submission(manifest)

    def test_rejects_arbitrary_compatibility_keys(self) -> None:
        manifest = input_manifest()
        manifest["kind"] = "compatibility"
        manifest["actions"] = {"gles": {"shaderSource": "host code"}}
        with self.assertRaises(ValueError):
            validate_submission(manifest)

    def test_native_aspect_is_a_typed_layout_not_arbitrary_dimensions(self) -> None:
        manifest = input_manifest()
        manifest["kind"] = "presentation-layout"
        manifest["actions"] = {"presentation": {"virtualScreen": "host-aspect"}}
        validate_submission(manifest)
        for value in ("shader-widen", "320x712", True, None):
            manifest["actions"]["presentation"]["virtualScreen"] = value
            with self.assertRaises(ValueError):
                validate_submission(manifest)
