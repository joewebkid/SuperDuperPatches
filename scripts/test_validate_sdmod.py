#!/usr/bin/env python3
"""Regression tests for the resource-mod package trust boundary."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path
from unittest import TestCase


sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_sdmod import validate_archive  # noqa: E402
from build_sdmod import build_package  # noqa: E402


PAYLOAD = b"safe-png-placeholder"


def manifest() -> dict[str, object]:
    digest = hashlib.sha256(PAYLOAD).hexdigest()
    return {
        "formatVersion": 1,
        "id": "com.example.game.hd",
        "name": "Example HD pack",
        "version": "1.0.0",
        "kind": "resource-mod",
        "priority": 100,
        "engine": {"resourceOverlayApi": 1, "minimumVersion": "0.2.3"},
        "target": {
            "bundleId": "com.example.game",
            "bundleVersions": ["1.0"],
            "executableSha256": ["a" * 64],
        },
        "budgets": {
            "payloadBytes": len(PAYLOAD),
            "maximumResidentBytes": len(PAYLOAD) * 4,
        },
        "license": {
            "redistributable": True,
            "name": "CC0-1.0",
            "attribution": "Test payload",
        },
        "dependsOn": [],
        "conflictsWith": [],
        "resources": [
            {
                "guestPath": "Textures/example.png",
                "sourceSha256": "b" * 64,
                "payloadPath": f"payload/{digest}.png",
                "replacementSha256": digest,
                "payloadBytes": len(PAYLOAD),
                "maximumResidentBytes": len(PAYLOAD) * 4,
                "mediaType": "image/png",
            }
        ],
    }


def package(path: Path, data: dict[str, object], payload: bytes = PAYLOAD) -> None:
    entries = data.get("resources", data.get("overlays"))
    payload_path = entries[0]["payloadPath"]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.sdmod.json", json.dumps(data))
        archive.writestr(payload_path, payload)


def overlay_manifest(payload: bytes) -> dict[str, object]:
    payload_digest = hashlib.sha256(payload).hexdigest()
    return {
        "formatVersion": 2,
        "id": "com.example.game.binary-fix",
        "name": "Example binary fix",
        "version": "1.0.0",
        "kind": "overlay-mod",
        "priority": 200,
        "engine": {"overlayApi": 2, "minimumVersion": "0.2.3"},
        "target": {
            "bundleId": "com.example.game",
            "bundleVersions": ["1.0"],
            "ipaSha256": ["c" * 64],
            "executableSha256": ["a" * 64],
        },
        "budgets": {
            "payloadBytes": len(payload),
            "maximumOutputBytes": 32,
            "maximumResidentBytes": 64,
        },
        "license": {
            "redistributable": True,
            "name": "Test-only",
            "attribution": "Generated test delta",
        },
        "dependsOn": [],
        "conflictsWith": [],
        "overlays": [
            {
                "type": "vcdiff",
                "targetClass": "macho",
                "guestPath": "ExampleGame",
                "sourceSha256": "a" * 64,
                "resultSha256": "b" * 64,
                "payloadPath": f"payload/{payload_digest}.vcdiff",
                "payloadSha256": payload_digest,
                "payloadBytes": len(payload),
                "resultBytes": 32,
                "maximumResidentBytes": 64,
                "vcdiffProfile": "rfc3284-xdelta3-no-extensions",
            }
        ],
    }


class ResourceModValidationTests(TestCase):
    def test_accepts_exact_bounded_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.sdmod"
            package(path, manifest())
            self.assertEqual(len(validate_archive(path, "0.2.3")), 64)

    def test_rejects_payload_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.sdmod"
            package(path, manifest(), b"tampered")
            with self.assertRaises(ValueError):
                validate_archive(path, "0.2.3")

    def test_rejects_unknown_manifest_fields_and_old_engine(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.sdmod"
            data = manifest()
            data["script"] = "host-command"
            package(path, data)
            with self.assertRaises(ValueError):
                validate_archive(path, "0.2.3")

            data = manifest()
            data["engine"]["minimumVersion"] = "9.0.0"
            package(path, data)
            with self.assertRaises(ValueError):
                validate_archive(path, "0.2.3")

    def test_rejects_macho_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.sdmod"
            data = deepcopy(manifest())
            payload = bytes.fromhex("feedface") + b"guest code"
            digest = hashlib.sha256(payload).hexdigest()
            resource = data["resources"][0]
            resource["payloadPath"] = f"payload/{digest}.bin"
            resource["replacementSha256"] = digest
            resource["payloadBytes"] = len(payload)
            data["budgets"]["payloadBytes"] = len(payload)
            package(path, data, payload)
            with self.assertRaises(ValueError):
                validate_archive(path, "0.2.3")

    def test_builder_creates_valid_deterministic_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = manifest()
            manifest_path = root / "manifest.sdmod.json"
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            payload_path = root / data["resources"][0]["payloadPath"]
            payload_path.parent.mkdir(parents=True)
            payload_path.write_bytes(PAYLOAD)
            first = root / "first.sdmod"
            second = root / "second.sdmod"
            first_hash = build_package(manifest_path, first, "0.2.3")
            second_hash = build_package(manifest_path, second, "0.2.3")
            self.assertEqual(first_hash, second_hash)
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_accepts_v2_vcdiff_envelope_and_rejects_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = bytes.fromhex("d6c3c40000") + b"test-vcdiff-body"
            valid = root / "valid.sdmod"
            package(valid, overlay_manifest(payload), payload)
            self.assertEqual(len(validate_archive(valid, "0.2.3")), 64)

            extended_payload = bytes.fromhex("d6c3c40004") + b"application-header"
            invalid = root / "invalid.sdmod"
            package(invalid, overlay_manifest(extended_payload), extended_payload)
            with self.assertRaises(ValueError):
                validate_archive(invalid, "0.2.3")

    def test_v2_requires_exact_ipa_and_disallows_full_macho(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = bytes.fromhex("d6c3c40000") + b"test-vcdiff-body"
            data = overlay_manifest(payload)
            del data["target"]["ipaSha256"]
            missing_ipa = root / "missing-ipa.sdmod"
            package(missing_ipa, data, payload)
            with self.assertRaises(ValueError):
                validate_archive(missing_ipa, "0.2.3")

            data = overlay_manifest(payload)
            overlay = data["overlays"][0]
            overlay["type"] = "replace"
            overlay.pop("vcdiffProfile")
            full_macho = root / "full-macho.sdmod"
            package(full_macho, data, payload)
            with self.assertRaises(ValueError):
                validate_archive(full_macho, "0.2.3")
