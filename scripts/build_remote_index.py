#!/usr/bin/env python3
"""Build the hash-pinned, static discovery index for GitHub Pages."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
index = json.loads((root / "index.json").read_text(encoding="utf-8"))
packages = []
for entry in index["patches"]:
    path = entry["path"]
    if not path.startswith("catalog/") or ".." in Path(path).parts or not path.endswith(".sdpatch.json"):
        raise ValueError(f"unsafe catalog path: {path}")
    data = (root / path).read_bytes()
    manifest = json.loads(data)
    target = manifest["target"]
    if manifest["id"] != entry["id"]:
        raise ValueError(f"index mismatch: {path}")
    if manifest["status"] == "deprecated" or manifest["kind"] not in {
        "compatibility", "presentation-layout", "input", "achievement"
    }:
        continue
    if not target.get("bundleVersions") or not target.get("executableSha256"):
        continue  # legacy weak matches must never be remotely distributed
    packages.append({
        "id": manifest["id"],
        "kind": manifest["kind"],
        "path": path,
        "bundleId": target["bundleId"],
        "bundleVersions": target["bundleVersions"],
        "executableSha256": [value.lower() for value in target["executableSha256"]],
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    })
packages.sort(key=lambda value: value["id"])
output = {"formatVersion": 1, "patches": packages}
(root / "remote-index.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(f"Indexed {len(packages)} exact-revision patches")
