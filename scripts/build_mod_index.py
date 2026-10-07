#!/usr/bin/env python3
"""Build the exact-target, hash-pinned mod index served by GitHub Pages."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path

from validate_sdmod import ID_RE, MANIFEST, SEMVER_RE, validate_archive


BUNDLE_RE = re.compile(r"[A-Za-z0-9._-]+")


def build_index(root: Path) -> dict:
    mods = []
    if (root / "mods").is_symlink():
        raise ValueError("mods directory may not be a symlink")
    for package in sorted((root / "mods").rglob("*.sdmod")):
        relative = package.relative_to(root)
        if (len(relative.parts) != 3 or relative.parts[0] != "mods"
                or package.is_symlink() or package.parent.is_symlink()):
            raise ValueError(f"unsafe package path: {relative}")
        bundle = relative.parts[1]
        if bundle in {".", ".."} or not BUNDLE_RE.fullmatch(bundle):
            raise ValueError(f"unsafe bundle ID: {bundle}")
        digest = validate_archive(package, None)
        with zipfile.ZipFile(package) as archive:
            manifest = json.loads(archive.read(MANIFEST))
        if manifest["formatVersion"] != 2:
            raise ValueError(f"remote mods require exact IPA targeting: {relative}")
        mod_id, version = manifest["id"], manifest["version"]
        if (not ID_RE.fullmatch(mod_id) or not SEMVER_RE.fullmatch(version)
                or bundle != manifest["target"]["bundleId"]
                or relative.name != f"{mod_id}-{version}.sdmod"):
            raise ValueError(f"index path does not match package identity: {relative}")
        target = manifest["target"]
        mods.append({
            "id": mod_id,
            "name": manifest["name"],
            "version": version,
            "path": relative.as_posix(),
            "bundleId": bundle,
            "bundleVersions": target["bundleVersions"],
            "ipaSha256": [value.lower() for value in target["ipaSha256"]],
            "executableSha256": [value.lower() for value in target["executableSha256"]],
            "bytes": package.stat().st_size,
            "sha256": digest,
        })
    if len(mods) > 256:
        raise ValueError("remote mod catalog exceeds the Android 256-entry limit")
    result = {"formatVersion": 1, "mods": mods}
    if len((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")) > 256 * 1024:
        raise ValueError("remote mod catalog exceeds the Android 256 KiB limit")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    index = build_index(args.root)
    output = args.root / "mods-index.json"
    if args.check:
        if json.loads(output.read_text(encoding="utf-8")) != index:
            parser.error("mods-index.json is stale; run scripts/build_mod_index.py")
    else:
        output.write_bytes((json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(f"Indexed {len(index['mods'])} mod packages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
