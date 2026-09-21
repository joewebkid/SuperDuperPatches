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
INPUT_BUTTONS = {
    "DPadLeft",
    "DPadUp",
    "DPadRight",
    "DPadDown",
    "Start",
    "Back",
    "A",
    "B",
    "X",
    "Y",
    "LeftStick",
    "RightStick",
    "LeftShoulder",
    "RightShoulder",
}
ACCELEROMETER_MODES = {"auto", "device", "gamepad", "off"}
STICK_SELECTIONS = {"auto", "none", "left", "right"}

# These IDs migrate behaviour that already shipped as bundle-ID branches.
# Do not add new entries: replace each one with exact hashes after acquiring
# the corresponding clean IPA revisions.
LEGACY_WEAK_ALLOWLIST = {"inotia1-present-flip"}


def fail(path: Path, message: str) -> None:
    raise ValueError(f"{path.relative_to(ROOT)}: {message}")


def is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_input_actions(path: Path, actions: object) -> None:
    if not isinstance(actions, dict) or not actions:
        fail(path, "actions.input must be a non-empty object")
    supported = {
        "touchRemap",
        "buttons",
        "dpadToTouch",
        "stickToTouch",
        "leftStickToTouch",
        "rightStickToTouch",
        "leftDeadzone",
        "rightDeadzone",
        "accelerometerMode",
        "tiltStick",
        "cursorStick",
        "cursorMode",
        "cursorClickButton",
        "portraitLayout",
        "landscapeLayout",
        "xTiltOffset",
        "yTiltOffset",
        "xTiltRange",
        "yTiltRange",
        "stabilizeVirtualCursor",
    }
    unknown = set(actions) - supported
    if unknown:
        fail(path, f"unsupported input actions: {', '.join(sorted(unknown))}")
    if not any(name != "buttons" or bool(value) for name, value in actions.items()):
        fail(path, "actions.input must contain at least one effective action")
    if "touchRemap" in actions and not isinstance(actions["touchRemap"], bool):
        fail(path, "actions.input.touchRemap must be a boolean")
    if "stickToTouch" in actions and "leftStickToTouch" in actions:
        fail(path, "stickToTouch and leftStickToTouch cannot be combined")

    buttons = actions.get("buttons", [])
    if not isinstance(buttons, list):
        fail(path, "actions.input.buttons must be an array")
    seen_buttons: set[str] = set()
    for binding in buttons:
        if not isinstance(binding, dict):
            fail(path, "input button bindings must be objects")
        button = binding.get("button")
        if button not in INPUT_BUTTONS:
            fail(path, f"unknown input button {button!r}")
        if button in seen_buttons:
            fail(path, f"input button {button} is mapped more than once")
        seen_buttons.add(button)
        for coordinate in ("x", "y"):
            value = binding.get(coordinate)
            if not is_number(value) or not 0 <= value <= 8192:
                fail(path, f"input button {button} has invalid {coordinate}")

    if "cursorMode" in actions and actions["cursorMode"] not in {"absolute", "relative"}:
        fail(path, "invalid cursor mode")
    click = actions.get("cursorClickButton")
    if "cursorClickButton" in actions and click not in {
        "A", "B", "X", "Y", "LeftStick", "RightStick", "LeftShoulder", "RightShoulder",
    }:
        fail(path, "invalid cursor click button")
    if click in seen_buttons:
        fail(path, "cursor click button also has a fixed touch binding")
    for key in ("portraitLayout", "landscapeLayout"):
        if key not in actions:
            continue
        layout = actions[key]
        allowed = {"buttons", "dpadToTouch", "leftStickToTouch", "rightStickToTouch"}
        if not isinstance(layout, dict) or set(layout) - allowed:
            fail(path, f"invalid {key}")
        validate_input_actions(path, layout)
        if any(binding.get("button") == click for binding in layout.get("buttons", [])):
            fail(path, "cursor click button also has an orientation touch binding")
        # Revalidate effective roles for this orientation, not just shared ones.
        effective = {k: v for k, v in actions.items()
                     if k not in {"portraitLayout", "landscapeLayout"}}
        effective.update(layout)
        validate_input_actions(path, effective)

    for area_name in (
        "dpadToTouch",
        "stickToTouch",
        "leftStickToTouch",
        "rightStickToTouch",
    ):
        area = actions.get(area_name)
        if area is None:
            continue
        if not isinstance(area, dict):
            fail(path, f"actions.input.{area_name} must be an object")
        for coordinate in ("x", "y", "width", "height"):
            value = area.get(coordinate)
            minimum = 0 if coordinate in {"x", "y"} else 0.000001
            if not is_number(value) or not minimum <= value <= 8192:
                fail(path, f"actions.input.{area_name}.{coordinate} is invalid")

    mode = actions.get("accelerometerMode")
    if mode is not None and mode not in ACCELEROMETER_MODES:
        fail(path, "actions.input.accelerometerMode is invalid")
    for name in ("leftDeadzone", "rightDeadzone"):
        value = actions.get(name)
        if value is not None and (not is_number(value) or not 0 <= value < 1):
            fail(path, f"actions.input.{name} is invalid")
    for name in ("tiltStick", "cursorStick"):
        value = actions.get(name)
        if value is not None and value not in STICK_SELECTIONS:
            fail(path, f"actions.input.{name} is invalid")
    for name in ("xTiltOffset", "yTiltOffset"):
        value = actions.get(name)
        if value is not None and (not is_number(value) or not -360 <= value <= 360):
            fail(path, f"actions.input.{name} is invalid")
    for name in ("xTiltRange", "yTiltRange"):
        value = actions.get(name)
        if value is not None and (not is_number(value) or not 0 <= value <= 360):
            fail(path, f"actions.input.{name} is invalid")
    stabilization = actions.get("stabilizeVirtualCursor")
    if stabilization is not None:
        if not isinstance(stabilization, dict) or set(stabilization) != {
            "smoothingStrength",
            "stickyRadius",
        }:
            fail(
                path,
                "actions.input.stabilizeVirtualCursor needs smoothingStrength and stickyRadius",
            )
        smoothing = stabilization.get("smoothingStrength")
        radius = stabilization.get("stickyRadius")
        if not is_number(smoothing) or smoothing < 0:
            fail(path, "actions.input.stabilizeVirtualCursor.smoothingStrength is invalid")
        if not is_number(radius) or radius < 0:
            fail(path, "actions.input.stabilizeVirtualCursor.stickyRadius is invalid")

    left_touch = "stickToTouch" in actions or "leftStickToTouch" in actions
    right_touch = "rightStickToTouch" in actions
    mode = actions.get("accelerometerMode", "auto")
    tilt_selection = actions.get("tiltStick", "auto")
    cursor_selection = actions.get("cursorStick", "auto")
    tilt_active = mode in {"auto", "gamepad"}
    explicit_tilt = tilt_selection if tilt_active and tilt_selection in {"left", "right"} else None
    explicit_cursor = cursor_selection if cursor_selection in {"left", "right"} else None
    if explicit_tilt == "left" and left_touch or explicit_tilt == "right" and right_touch:
        fail(path, "one stick cannot control both tilt and touch")
    if explicit_cursor == "left" and left_touch or explicit_cursor == "right" and right_touch:
        fail(path, "one stick cannot control both cursor and touch")
    if explicit_tilt is not None and explicit_tilt == explicit_cursor:
        fail(path, "one stick cannot control both tilt and cursor")
    resolved_tilt = explicit_tilt
    if (
        resolved_tilt is None
        and tilt_active
        and tilt_selection == "auto"
        and not left_touch
        and explicit_cursor != "left"
    ):
        resolved_tilt = "left"
    if mode == "gamepad" and resolved_tilt is None:
        fail(path, "gamepad accelerometer mode needs an unassigned tilt stick")


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
    allowed = required | {"$schema", "priority", "dependsOn", "conflictsWith"}
    unknown = manifest.keys() - allowed
    if unknown:
        fail(path, f"unknown top-level keys: {', '.join(sorted(unknown))}")
    missing = required - manifest.keys()
    if missing:
        fail(path, f"missing keys: {', '.join(sorted(missing))}")
    if manifest["formatVersion"] != 1:
        fail(path, "formatVersion must be 1")
    if not isinstance(manifest["name"], str) or not 1 <= len(manifest["name"]) <= 128:
        fail(path, "name must contain 1..128 characters")
    if manifest["status"] not in {"experimental", "verified", "deprecated"}:
        fail(path, "status is invalid")
    if not isinstance(manifest["defaultEnabled"], bool):
        fail(path, "defaultEnabled must be a boolean")
    if manifest["status"] == "deprecated" and manifest["defaultEnabled"]:
        fail(path, "deprecated patches cannot be enabled by default")
    priority = manifest.get("priority", 100)
    if not isinstance(priority, int) or isinstance(priority, bool) or not 0 <= priority <= 1000:
        fail(path, "priority must be an integer in 0..1000")

    patch_id = manifest["id"]
    if not isinstance(patch_id, str) or not ID_RE.fullmatch(patch_id):
        fail(path, "invalid patch id")
    if patch_id in seen_ids:
        fail(path, f"duplicate patch id {patch_id}")
    seen_ids.add(patch_id)
    if path.name != f"{patch_id}.sdpatch.json":
        fail(path, "file name must equal <id>.sdpatch.json")
    relations: set[str] = set()
    for relation_name in ("dependsOn", "conflictsWith"):
        related = manifest.get(relation_name, [])
        if not isinstance(related, list) or not all(
            isinstance(value, str) and ID_RE.fullmatch(value) for value in related
        ):
            fail(path, f"{relation_name} must contain valid patch IDs")
        if len(related) != len(set(related)):
            fail(path, f"{relation_name} contains duplicates")
        if patch_id in related:
            fail(path, f"{relation_name} cannot reference the patch itself")
        overlap = relations.intersection(related)
        if overlap:
            fail(path, f"a patch cannot both depend on and conflict with {sorted(overlap)[0]}")
        relations.update(related)

    target = manifest["target"]
    bundle_id = target.get("bundleId")
    versions = target.get("bundleVersions", [])
    hashes = target.get("executableSha256", [])
    weak = target.get("allowLegacyWeakMatch", False)
    if not isinstance(bundle_id, str) or not bundle_id.strip():
        fail(path, "target.bundleId must be non-empty")
    unknown_target = set(target) - {
        "bundleId",
        "bundleVersions",
        "executableSha256",
        "allowLegacyWeakMatch",
    }
    if unknown_target:
        fail(path, f"unknown target keys: {', '.join(sorted(unknown_target))}")
    if not isinstance(versions, list) or not all(isinstance(value, str) and value for value in versions):
        fail(path, "target.bundleVersions must contain non-empty strings")
    if len(versions) != len(set(versions)):
        fail(path, "target.bundleVersions contains duplicates")
    if not isinstance(hashes, list) or not all(
        isinstance(value, str) and SHA256_RE.fullmatch(value) for value in hashes
    ):
        fail(path, "target.executableSha256 contains an invalid hash")
    if len(hashes) != len({value.lower() for value in hashes}):
        fail(path, "target.executableSha256 contains duplicates")
    if weak and patch_id not in LEGACY_WEAK_ALLOWLIST:
        fail(path, "allowLegacyWeakMatch is prohibited for new patches")
    if not weak and (not hashes or not versions):
        fail(path, "community target needs both executableSha256 and exact bundleVersions")

    actions = manifest["actions"]
    if not isinstance(actions, dict) or not actions:
        fail(path, "actions must be a non-empty object")
    kind = manifest.get("kind")
    if kind == "compatibility":
        if not set(actions) <= {"presentation", "eagl", "gles", "input"}:
            fail(path, "compatibility patches may contain only presentation/EAGL/GLES/input actions")
        if not actions:
            fail(path, "compatibility patch needs at least one action namespace")
        presentation = actions.get("presentation", {})
        if not isinstance(presentation, dict):
            fail(path, "actions.presentation must be an object")
        compatibility_presentation_actions = {
            "presentFlipX",
            "presentRotate180",
            "correctLandscapeAutorotationLayout",
            "disablePresentRotation",
            "disableTouchRotation",
            "startupDeviceOrientation",
        }
        if not set(presentation) <= compatibility_presentation_actions:
            fail(path, "actions.presentation contains an unsupported compatibility action")
        orientation = presentation.get("startupDeviceOrientation")
        if orientation is not None and orientation not in {
            "portrait",
            "portrait-upside-down",
            "landscape-left",
            "landscape-right",
        }:
            fail(path, "presentation.startupDeviceOrientation is invalid")
        if "eagl" in actions:
            eagl = actions["eagl"]
            if not isinstance(eagl, dict) or not eagl:
                fail(path, "actions.eagl must be a non-empty object")
            supported_eagl_actions = {
                "recoverSharedRenderbufferStorage",
                "forceLandscapeRenderbuffer",
                "forceDirectPresent",
            }
            if not set(eagl) <= supported_eagl_actions or not all(
                isinstance(value, bool) for value in eagl.values()
            ):
                fail(path, "actions.eagl contains an unsupported action")
        if "gles" in actions:
            gles = actions["gles"]
            supported_gles_actions = {
                "disableInactiveVertexAttributes",
                "forceLandscapeViewport",
                "trimUnusedSamplerArrays",
            }
            if not isinstance(gles, dict) or not gles or not set(gles) <= supported_gles_actions or not all(
                isinstance(value, bool) for value in gles.values()
            ):
                fail(path, "actions.gles contains an unsupported action")
        if "input" in actions:
            validate_input_actions(path, actions["input"])
    elif kind == "input":
        if set(actions) != {"input"}:
            fail(path, "input patches must contain only input actions")
        validate_input_actions(path, actions["input"])
    elif kind == "presentation-layout":
        presentation = actions.get("presentation")
        if (
            set(actions) != {"presentation"}
            or not isinstance(presentation, dict)
            or not presentation
            or not set(presentation)
            <= {"outputFit", "virtualScreen", "forceVirtualScreenViewBounds"}
        ):
            fail(
                path,
                "presentation-layout patches must contain only "
                "outputFit/virtualScreen/forceVirtualScreenViewBounds",
            )
        if "outputFit" in presentation and presentation["outputFit"] not in {"aspect-fit", "stretch"}:
            fail(path, "presentation.outputFit is invalid")
        if "virtualScreen" in presentation and presentation["virtualScreen"] != "host-aspect":
            fail(path, "presentation.virtualScreen is invalid")
        if "forceVirtualScreenViewBounds" in presentation:
            if not isinstance(presentation["forceVirtualScreenViewBounds"], bool):
                fail(path, "presentation.forceVirtualScreenViewBounds must be boolean")
            if presentation.get("virtualScreen") != "host-aspect":
                fail(
                    path,
                    "presentation.forceVirtualScreenViewBounds requires "
                    "virtualScreen=host-aspect",
                )
    elif kind == "achievement":
        achievement = actions.get("achievements")
        if set(actions) != {"achievements"} or not isinstance(achievement, dict) or set(achievement) != {"setId", "iconManifest"}:
            fail(path, "achievement patches require only setId and iconManifest")
        if not isinstance(achievement["setId"], str) or not achievement["setId"].strip() or len(achievement["setId"]) > 96:
            fail(path, "achievements.setId must be a non-empty identifier")
        if not isinstance(achievement["iconManifest"], str) or not achievement["iconManifest"].startswith("https://"):
            fail(path, "achievements.iconManifest must use HTTPS")
    elif kind in {"resource-mod", "binary"}:
        fail(path, f"patch kind {kind} is reserved but not implemented")
    else:
        fail(path, f"unknown patch kind {kind!r}")
    return manifest


def validate_relations(manifests: dict[str, tuple[Path, dict[str, object]]]) -> None:
    for patch_id, (path, manifest) in manifests.items():
        target = manifest["target"]
        for relation_name in ("dependsOn", "conflictsWith"):
            for related_id in manifest.get(relation_name, []):
                related_entry = manifests.get(related_id)
                if related_entry is None:
                    fail(path, f"{relation_name} references unknown patch {related_id}")
                related = related_entry[1]
                if related["target"]["bundleId"] != target["bundleId"]:
                    fail(path, f"{relation_name} crosses bundle IDs via {related_id}")
                if relation_name == "dependsOn":
                    versions = set(target.get("bundleVersions", []))
                    related_versions = set(related["target"].get("bundleVersions", []))
                    hashes = {value.lower() for value in target.get("executableSha256", [])}
                    related_hashes = {
                        value.lower() for value in related["target"].get("executableSha256", [])
                    }
                    if versions and related_versions and not versions.intersection(related_versions):
                        fail(path, f"dependency {related_id} has no shared bundle version")
                    if hashes and related_hashes and not hashes.intersection(related_hashes):
                        fail(path, f"dependency {related_id} has no shared executable hash")

    visiting: set[str] = set()
    finished: set[str] = set()

    def visit(patch_id: str) -> None:
        if patch_id in finished:
            return
        if patch_id in visiting:
            fail(manifests[patch_id][0], f"dependency cycle contains {patch_id}")
        visiting.add(patch_id)
        for dependency in manifests[patch_id][1].get("dependsOn", []):
            visit(dependency)
        visiting.remove(patch_id)
        finished.add(patch_id)

    for patch_id in manifests:
        visit(patch_id)


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
        unknown = set(entry) - {"id", "path", "kind", "status", "defaultEnabled"}
        if unknown:
            fail(INDEX, f"patch index entry has unknown keys: {', '.join(sorted(unknown))}")
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
        validate_relations(manifests)
        validate_index(manifests)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"Validated {len(paths)} patch manifest(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
