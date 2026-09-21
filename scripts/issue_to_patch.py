#!/usr/bin/env python3
"""Turn one app-generated GitHub issue into a catalog patch and index entry."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from validate_catalog import validate_input_actions


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog"
INDEX = ROOT / "index.json"
START = "<!-- sdpatch-json:start -->"
END = "<!-- sdpatch-json:end -->"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,95}$")
BUNDLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
def extract_manifest(body: str) -> dict[str, object]:
    if body.count(START) != 1 or body.count(END) != 1:
        raise ValueError("issue must contain exactly one sdpatch JSON block")
    payload = body.split(START, 1)[1].split(END, 1)[0].strip()
    if len(payload.encode("utf-8")) > 64 * 1024:
        raise ValueError("patch manifest exceeds 64 KiB")
    try:
        manifest = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid patch JSON: {error}") from error
    if not isinstance(manifest, dict):
        raise ValueError("patch manifest must be a JSON object")
    return manifest


def validate_submission(manifest: dict[str, object]) -> tuple[str, str]:
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
    if required - manifest.keys():
        raise ValueError("patch manifest is missing required fields")
    if manifest.get("formatVersion") != 1:
        raise ValueError("only sdpatch formatVersion 1 is accepted")
    patch_id = manifest.get("id")
    if not isinstance(patch_id, str) or not ID_RE.fullmatch(patch_id):
        raise ValueError("invalid patch id")
    if manifest.get("status") != "experimental":
        raise ValueError("community submissions must start as experimental")
    if manifest.get("defaultEnabled") is not False:
        raise ValueError("community submissions must default to disabled")
    kind = manifest.get("kind")
    if kind not in {"compatibility", "presentation-layout", "input"}:
        raise ValueError("the v1 community flow accepts typed compatibility, presentation and input patches only")

    allowed_top_level = required | {
        "$schema",
        "priority",
        "dependsOn",
        "conflictsWith",
    }
    if set(manifest) - allowed_top_level:
        raise ValueError("patch manifest contains unknown fields")
    for relation_name in ("dependsOn", "conflictsWith"):
        relations = manifest.get(relation_name, [])
        if (
            not isinstance(relations, list)
            or len(relations) > 16
            or not all(isinstance(value, str) and ID_RE.fullmatch(value) for value in relations)
            or len(relations) != len(set(relations))
        ):
            raise ValueError(f"invalid {relation_name}")
        if patch_id in relations:
            raise ValueError("a patch cannot reference itself")
    if set(manifest.get("dependsOn", [])) & set(manifest.get("conflictsWith", [])):
        raise ValueError("one patch cannot be both dependency and conflict")

    target = manifest.get("target")
    if not isinstance(target, dict):
        raise ValueError("target must be an object")
    bundle_id = target.get("bundleId")
    if (
        not isinstance(bundle_id, str)
        or not BUNDLE_RE.fullmatch(bundle_id)
        or ".." in bundle_id
    ):
        raise ValueError("bundleId cannot be used as a safe catalog path")
    versions = target.get("bundleVersions")
    hashes = target.get("executableSha256")
    if not isinstance(versions, list) or not versions or not all(
        isinstance(version, str) and 0 < len(version) <= 128 for version in versions
    ):
        raise ValueError("at least one exact bundle version is required")
    if not isinstance(hashes, list) or not hashes or not all(
        isinstance(digest, str) and SHA256_RE.fullmatch(digest) for digest in hashes
    ):
        raise ValueError("at least one executable SHA-256 is required")
    if target.get("allowLegacyWeakMatch", False):
        raise ValueError("community patches cannot use allowLegacyWeakMatch")

    actions = manifest.get("actions")
    if kind == "compatibility":
        if not isinstance(actions, dict) or not actions or not set(actions) <= {
            "presentation",
            "eagl",
            "gles",
        }:
            raise ValueError("compatibility submissions may contain only presentation/EAGL/GLES actions")
        presentation = actions.get("presentation", {})
        if not isinstance(presentation, dict) or not set(presentation) <= {
            "presentFlipX",
            "presentRotate180",
            "correctLandscapeAutorotationLayout",
            "disablePresentRotation",
            "disableTouchRotation",
            "startupDeviceOrientation",
        }:
            raise ValueError("unsupported compatibility presentation action")
        bool_presentation = set(presentation) - {"startupDeviceOrientation"}
        if not all(isinstance(presentation[name], bool) for name in bool_presentation):
            raise ValueError("compatibility presentation switches must be boolean")
        if presentation.get("startupDeviceOrientation") not in {
            None,
            "portrait",
            "portrait-upside-down",
            "landscape-left",
            "landscape-right",
        }:
            raise ValueError("invalid startupDeviceOrientation")
        for namespace, supported in {
            "eagl": {
                "recoverSharedRenderbufferStorage",
                "forceLandscapeRenderbuffer",
                "forceDirectPresent",
            },
            "gles": {"disableInactiveVertexAttributes", "forceLandscapeViewport"},
        }.items():
            values = actions.get(namespace)
            if values is None:
                continue
            if (
                not isinstance(values, dict)
                or not values
                or not set(values) <= supported
                or not all(isinstance(value, bool) for value in values.values())
            ):
                raise ValueError(f"unsupported {namespace} action")
        if not any(isinstance(value, dict) and value for value in actions.values()):
            raise ValueError("compatibility actions cannot be empty")
    elif kind == "presentation-layout":
        if not isinstance(actions, dict) or set(actions) != {"presentation"}:
            raise ValueError("presentation-layout may contain only presentation actions")
        presentation = actions.get("presentation")
        if (
            not isinstance(presentation, dict)
            or not presentation
            or not set(presentation)
            <= {"outputFit", "virtualScreen", "forceVirtualScreenViewBounds"}
            or ("outputFit" in presentation and presentation["outputFit"] not in {"aspect-fit", "stretch"})
            or ("virtualScreen" in presentation and presentation["virtualScreen"] != "host-aspect")
            or (
                "forceVirtualScreenViewBounds" in presentation
                and not isinstance(presentation["forceVirtualScreenViewBounds"], bool)
            )
            or (
                "forceVirtualScreenViewBounds" in presentation
                and presentation.get("virtualScreen") != "host-aspect"
            )
        ):
            raise ValueError(
                "presentation-layout requires supported outputFit/virtualScreen/"
                "forceVirtualScreenViewBounds actions"
            )
    else:
        if not isinstance(actions, dict) or set(actions) != {"input"}:
            raise ValueError("input submissions may contain only typed input actions")
        # Reuse the exact semantic validator used by catalog CI so an issue
        # cannot pass the gateway workflow and then fail after materializing.
        validate_input_actions(
            ROOT / "community-submission.sdpatch.json",
            actions.get("input"),
        )
    return patch_id, bundle_id


def publish_to_worktree(manifest: dict[str, object]) -> tuple[str, str]:
    patch_id, bundle_id = validate_submission(manifest)
    destination = CATALOG / bundle_id / f"{patch_id}.sdpatch.json"
    if destination.exists():
        raise ValueError(f"patch id already exists: {patch_id}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    index = json.loads(INDEX.read_text(encoding="utf-8"))
    entries = index.get("patches")
    if not isinstance(entries, list):
        raise ValueError("catalog index is invalid")
    entries.append(
        {
            "id": patch_id,
            "path": destination.relative_to(ROOT).as_posix(),
            "kind": manifest["kind"],
            "status": manifest["status"],
            "defaultEnabled": manifest["defaultEnabled"],
        }
    )
    entries.sort(key=lambda entry: str(entry["id"]))
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return patch_id, destination.relative_to(ROOT).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--body-file", type=Path)
    args = parser.parse_args()
    body = (
        args.body_file.read_text(encoding="utf-8")
        if args.body_file
        else os.environ.get("ISSUE_BODY", "")
    )
    patch_id, relative_path = publish_to_worktree(extract_manifest(body))
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(f"patch_id={patch_id}\n")
            stream.write(f"relative_path={relative_path}\n")
    else:
        print(f"Prepared {relative_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
