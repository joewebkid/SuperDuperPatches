#!/usr/bin/env python3
"""Semantic checks for the Super Duper patch catalog (stdlib only)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog"
INDEX = ROOT / "index.json"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")

# These IDs migrate behaviour that already shipped as bundle-ID branches.
# Do not add new entries: replace each one with exact hashes after acquiring
# the corresponding clean IPA revisions.
LEGACY_WEAK_ALLOWLIST = {"inotia1-present-flip"}


def fail(path: Path, message: str) -> None:
    raise ValueError(f"{path.relative_to(ROOT)}: {message}")


def validate(path: Path, seen_ids: set[str]) -> dict[str, object]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(path, f"invalid JSON: {error}")

    required = {
        "formatVersion",
        "id",
        "name",
        "kind",
        "status",
        "defaultEnabled",
        "target",
        "actions",
    }
    missing = required - manifest.keys()
    if missing:
        fail(path, f"missing keys: {', '.join(sorted(missing))}")
    if manifest["formatVersion"] != 1:
        fail(path, "formatVersion must be 1")
    if not isinstance(manifest["defaultEnabled"], bool):
        fail(path, "defaultEnabled must be a boolean")

    patch_id = manifest["id"]
    if not isinstance(patch_id, str) or not ID_RE.fullmatch(patch_id):
        fail(path, "invalid patch id")
    if patch_id in seen_ids:
        fail(path, f"duplicate patch id {patch_id}")
    seen_ids.add(patch_id)
    if path.name != f"{patch_id}.sdpatch.json":
        fail(path, "file name must equal <id>.sdpatch.json")

    target = manifest["target"]
    bundle_id = target.get("bundleId")
    versions = target.get("bundleVersions", [])
    hashes = target.get("executableSha256", [])
    weak = target.get("allowLegacyWeakMatch", False)
    if not isinstance(bundle_id, str) or not bundle_id.strip():
        fail(path, "target.bundleId must be non-empty")
    if not isinstance(versions, list) or not all(isinstance(value, str) and value for value in versions):
        fail(path, "target.bundleVersions must contain non-empty strings")
    if not isinstance(hashes, list) or not all(
        isinstance(value, str) and SHA256_RE.fullmatch(value) for value in hashes
    ):
        fail(path, "target.executableSha256 contains an invalid hash")
    if weak and patch_id not in LEGACY_WEAK_ALLOWLIST:
        fail(path, "allowLegacyWeakMatch is prohibited for new patches")
    if not weak and (not hashes or not versions):
        fail(path, "community target needs both executableSha256 and exact bundleVersions")

    if not isinstance(manifest["actions"], dict) or not manifest["actions"]:
        fail(path, "actions must be a non-empty object")
    return manifest


def validate_index(manifests: dict[str, tuple[Path, dict[str, object]]]) -> None:
    try:
        index = json.loads(INDEX.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(INDEX, f"invalid JSON: {error}")
    if index.get("formatVersion") != 1 or not isinstance(index.get("patches"), list):
        fail(INDEX, "requires formatVersion 1 and a patches array")

    indexed_ids: set[str] = set()
    for entry in index["patches"]:
        if not isinstance(entry, dict):
            fail(INDEX, "patch entries must be objects")
        patch_id = entry.get("id")
        if not isinstance(patch_id, str):
            fail(INDEX, "every patch entry needs a string id")
        if patch_id in indexed_ids:
            fail(INDEX, f"duplicate index entry {patch_id}")
        indexed_ids.add(patch_id)
        if patch_id not in manifests:
            fail(INDEX, f"entry {patch_id} has no catalog manifest")
        path, manifest = manifests[patch_id]
        expected_path = path.relative_to(ROOT).as_posix()
        if entry.get("path") != expected_path:
            fail(INDEX, f"entry {patch_id} path must be {expected_path}")
        for key in ("kind", "status", "defaultEnabled"):
            if entry.get(key) != manifest.get(key):
                fail(INDEX, f"entry {patch_id} has stale {key} metadata")

    missing = manifests.keys() - indexed_ids
    if missing:
        fail(INDEX, f"missing catalog entries: {', '.join(sorted(missing))}")


def main() -> int:
    paths = sorted(CATALOG.rglob("*.sdpatch.json"))
    if not paths:
        print("No patch manifests found", file=sys.stderr)
        return 1
    seen_ids: set[str] = set()
    manifests: dict[str, tuple[Path, dict[str, object]]] = {}
    try:
        for path in paths:
            manifest = validate(path, seen_ids)
            manifests[str(manifest["id"])] = path, manifest
        validate_index(manifests)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"Validated {len(paths)} patch manifest(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
