#!/usr/bin/env python3
"""Validate one distributable Super Duper .sdmod package without extracting it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath


MANIFEST = "manifest.sdmod.json"
MAX_ARCHIVE_BYTES = 4 * 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_FILES = 4096
MAX_VCDIFF_BYTES = 256 * 1024 * 1024
ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,95}$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
VERSION_RE = re.compile(r"[0-9]+(?:\.[0-9]+)+")
MACH_O_MAGICS = {
    bytes.fromhex(value)
    for value in (
        "feedface", "cefaedfe", "feedfacf", "cffaedfe",
        "cafebabe", "bebafeca", "cafebabf", "bfbafeca",
    )
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def require_object(
    value: object,
    required: set[str],
    optional: set[str],
    label: str,
) -> dict[str, object]:
    require(isinstance(value, dict), f"{label} must be an object")
    keys = set(value)
    require(required <= keys, f"{label} is missing: {', '.join(sorted(required - keys))}")
    require(keys <= required | optional, f"{label} has unknown keys: {', '.join(sorted(keys - required - optional))}")
    return value


def safe_path(value: object, label: str) -> str:
    require(isinstance(value, str) and 0 < len(value) <= 1024, f"{label} is invalid")
    require("\\" not in value and "\x00" not in value, f"{label} is unsafe")
    path = PurePosixPath(value)
    require(not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts), f"{label} is unsafe")
    return value


def string_array(value: object, label: str, pattern: re.Pattern[str] | None = None) -> list[str]:
    require(isinstance(value, list), f"{label} must be an array")
    require(all(isinstance(item, str) and item for item in value), f"{label} contains an invalid value")
    values = list(value)
    require(len(values) == len(set(values)), f"{label} contains duplicates")
    if pattern is not None:
        require(all(pattern.fullmatch(item) for item in values), f"{label} contains an invalid value")
    return values


def version_parts(value: str) -> tuple[int, ...]:
    match = VERSION_RE.search(value)
    require(match is not None, f"invalid engine version {value!r}")
    return tuple(int(part) for part in match.group().split("."))


def compare_versions(left: str, right: str) -> int:
    a, b = version_parts(left), version_parts(right)
    size = max(len(a), len(b))
    padded_a = a + (0,) * (size - len(a))
    padded_b = b + (0,) * (size - len(b))
    return (padded_a > padded_b) - (padded_a < padded_b)


def validate_manifest(manifest: object, engine_version: str | None) -> list[dict[str, object]]:
    if isinstance(manifest, dict) and manifest.get("formatVersion") == 2:
        return validate_manifest_v2(manifest, engine_version)
    manifest = require_object(
        manifest,
        {
            "formatVersion", "id", "name", "version", "kind", "engine",
            "target", "budgets", "license", "resources",
        },
        {"$schema", "priority", "dependsOn", "conflictsWith"},
        "manifest",
    )
    require(manifest["formatVersion"] == 1, "formatVersion must be 1")
    require(manifest["kind"] == "resource-mod", "kind must be resource-mod")
    require(isinstance(manifest["id"], str) and ID_RE.fullmatch(manifest["id"]), "invalid package id")
    require(isinstance(manifest["name"], str) and 1 <= len(manifest["name"]) <= 128, "invalid package name")
    require(isinstance(manifest["version"], str) and SEMVER_RE.fullmatch(manifest["version"]), "invalid package version")
    priority = manifest.get("priority", 100)
    require(isinstance(priority, int) and not isinstance(priority, bool) and 0 <= priority <= 1000, "invalid priority")

    engine = require_object(manifest["engine"], {"resourceOverlayApi", "minimumVersion"}, {"maximumVersion"}, "engine")
    require(engine["resourceOverlayApi"] == 1, "unsupported resourceOverlayApi")
    require(isinstance(engine["minimumVersion"], str) and engine["minimumVersion"], "invalid minimumVersion")
    maximum = engine.get("maximumVersion")
    require(maximum is None or isinstance(maximum, str) and maximum, "invalid maximumVersion")
    if engine_version:
        require(compare_versions(engine_version, engine["minimumVersion"]) >= 0, "package needs a newer engine")
        require(maximum is None or compare_versions(engine_version, maximum) <= 0, "package excludes this engine version")

    target = require_object(manifest["target"], {"bundleId", "bundleVersions", "executableSha256"}, set(), "target")
    require(isinstance(target["bundleId"], str) and 0 < len(target["bundleId"]) <= 200, "invalid bundleId")
    require(string_array(target["bundleVersions"], "bundleVersions"), "bundleVersions cannot be empty")
    require(string_array(target["executableSha256"], "executableSha256", SHA256_RE), "executableSha256 cannot be empty")

    license_data = require_object(
        manifest["license"],
        {"redistributable", "name", "attribution"},
        {"spdx", "sourceUrl"},
        "license",
    )
    require(license_data["redistributable"] is True, "payload must be redistributable")
    require(isinstance(license_data["name"], str) and license_data["name"], "license name is required")
    require(isinstance(license_data["attribution"], str) and license_data["attribution"], "attribution is required")

    depends_on = string_array(manifest.get("dependsOn", []), "dependsOn", ID_RE)
    conflicts_with = string_array(manifest.get("conflictsWith", []), "conflictsWith", ID_RE)
    require(manifest["id"] not in depends_on + conflicts_with, "package cannot reference itself")
    require(not set(depends_on) & set(conflicts_with), "one package cannot be both dependency and conflict")

    budgets = require_object(manifest["budgets"], {"payloadBytes", "maximumResidentBytes"}, set(), "budgets")
    payload_budget = budgets["payloadBytes"]
    resident_budget = budgets["maximumResidentBytes"]
    require(isinstance(payload_budget, int) and not isinstance(payload_budget, bool) and 0 <= payload_budget <= MAX_ARCHIVE_BYTES, "invalid payload budget")
    require(isinstance(resident_budget, int) and not isinstance(resident_budget, bool) and 0 <= resident_budget <= MAX_ARCHIVE_BYTES, "invalid resident budget")

    resources = manifest["resources"]
    require(isinstance(resources, list) and 1 <= len(resources) <= MAX_FILES, "resources must contain 1..4096 entries")
    parsed: list[dict[str, object]] = []
    guest_paths: set[str] = set()
    payload_paths: set[str] = set()
    total_payload = 0
    total_resident = 0
    for index, raw in enumerate(resources):
        item = require_object(
            raw,
            {"guestPath", "sourceSha256", "payloadPath", "replacementSha256", "payloadBytes", "maximumResidentBytes"},
            {"mediaType"},
            f"resources[{index}]",
        )
        guest_path = safe_path(item["guestPath"], f"resources[{index}].guestPath")
        payload_path = safe_path(item["payloadPath"], f"resources[{index}].payloadPath")
        require(guest_path.lower() != "info.plist", "Info.plist needs a typed patch")
        require(payload_path.startswith("payload/"), "payloadPath must be inside payload/")
        require(guest_path not in guest_paths, f"duplicate guestPath {guest_path}")
        require(payload_path not in payload_paths, f"duplicate payloadPath {payload_path}")
        guest_paths.add(guest_path)
        payload_paths.add(payload_path)
        for name in ("sourceSha256", "replacementSha256"):
            require(isinstance(item[name], str) and SHA256_RE.fullmatch(item[name]), f"invalid {name} for {guest_path}")
        payload_bytes = item["payloadBytes"]
        resident_bytes = item["maximumResidentBytes"]
        require(isinstance(payload_bytes, int) and not isinstance(payload_bytes, bool) and 0 <= payload_bytes <= 1024 ** 3, f"invalid payloadBytes for {guest_path}")
        require(isinstance(resident_bytes, int) and not isinstance(resident_bytes, bool) and 0 <= resident_bytes <= 2 * 1024 ** 3, f"invalid maximumResidentBytes for {guest_path}")
        total_payload += payload_bytes
        total_resident += resident_bytes
        require(total_payload <= payload_budget, "resources exceed payload budget")
        require(total_resident <= resident_budget, "resources exceed resident budget")
        normalized = dict(item)
        normalized.update({
            "type": "replace",
            "targetClass": "resource",
            "payloadSha256": item["replacementSha256"],
            "resultSha256": item["replacementSha256"],
            "resultBytes": item["payloadBytes"],
        })
        parsed.append(normalized)
    require(total_payload == payload_budget, "payloadBytes budget must equal the resource sum")
    return parsed


def validate_manifest_v2(
    manifest: dict[str, object],
    engine_version: str | None,
) -> list[dict[str, object]]:
    manifest = require_object(
        manifest,
        {
            "formatVersion", "id", "name", "version", "kind", "engine",
            "target", "budgets", "license", "overlays",
        },
        {"$schema", "priority", "dependsOn", "conflictsWith"},
        "manifest",
    )
    require(manifest["formatVersion"] == 2, "formatVersion must be 2")
    require(manifest["kind"] == "overlay-mod", "kind must be overlay-mod")
    require(isinstance(manifest["id"], str) and ID_RE.fullmatch(manifest["id"]), "invalid package id")
    require(isinstance(manifest["name"], str) and 1 <= len(manifest["name"]) <= 128, "invalid package name")
    require(isinstance(manifest["version"], str) and SEMVER_RE.fullmatch(manifest["version"]), "invalid package version")
    priority = manifest.get("priority", 100)
    require(isinstance(priority, int) and not isinstance(priority, bool) and 0 <= priority <= 1000, "invalid priority")

    engine = require_object(manifest["engine"], {"overlayApi", "minimumVersion"}, {"maximumVersion"}, "engine")
    require(engine["overlayApi"] == 2, "unsupported overlayApi")
    require(isinstance(engine["minimumVersion"], str) and engine["minimumVersion"], "invalid minimumVersion")
    maximum = engine.get("maximumVersion")
    require(maximum is None or isinstance(maximum, str) and maximum, "invalid maximumVersion")
    if engine_version:
        require(compare_versions(engine_version, engine["minimumVersion"]) >= 0, "package needs a newer engine")
        require(maximum is None or compare_versions(engine_version, maximum) <= 0, "package excludes this engine version")

    target = require_object(
        manifest["target"],
        {"bundleId", "bundleVersions", "ipaSha256", "executableSha256"},
        set(),
        "target",
    )
    require(isinstance(target["bundleId"], str) and 0 < len(target["bundleId"]) <= 200, "invalid bundleId")
    require(string_array(target["bundleVersions"], "bundleVersions"), "bundleVersions cannot be empty")
    require(string_array(target["ipaSha256"], "ipaSha256", SHA256_RE), "ipaSha256 cannot be empty")
    require(string_array(target["executableSha256"], "executableSha256", SHA256_RE), "executableSha256 cannot be empty")

    license_data = require_object(
        manifest["license"],
        {"redistributable", "name", "attribution"},
        {"spdx", "sourceUrl"},
        "license",
    )
    require(license_data["redistributable"] is True, "payload must be redistributable")
    require(isinstance(license_data["name"], str) and license_data["name"], "license name is required")
    require(isinstance(license_data["attribution"], str) and license_data["attribution"], "attribution is required")

    depends_on = string_array(manifest.get("dependsOn", []), "dependsOn", ID_RE)
    conflicts_with = string_array(manifest.get("conflictsWith", []), "conflictsWith", ID_RE)
    require(manifest["id"] not in depends_on + conflicts_with, "package cannot reference itself")
    require(not set(depends_on) & set(conflicts_with), "one package cannot be both dependency and conflict")

    budgets = require_object(
        manifest["budgets"],
        {"payloadBytes", "maximumOutputBytes", "maximumResidentBytes"},
        set(),
        "budgets",
    )
    for name in ("payloadBytes", "maximumOutputBytes", "maximumResidentBytes"):
        value = budgets[name]
        require(isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_ARCHIVE_BYTES, f"invalid {name} budget")

    overlays = manifest["overlays"]
    require(isinstance(overlays, list) and 1 <= len(overlays) <= MAX_FILES, "overlays must contain 1..4096 entries")
    parsed: list[dict[str, object]] = []
    guest_paths: set[str] = set()
    payload_paths: set[str] = set()
    total_payload = 0
    total_output = 0
    total_resident = 0
    common_required = {
        "type", "targetClass", "guestPath", "sourceSha256", "resultSha256",
        "payloadPath", "payloadSha256", "payloadBytes", "resultBytes",
        "maximumResidentBytes",
    }
    for index, raw in enumerate(overlays):
        require(isinstance(raw, dict), f"overlays[{index}] must be an object")
        operation = raw.get("type")
        optional = {"mediaType"} if operation == "replace" else {"mediaType", "vcdiffProfile"}
        item = require_object(raw, common_required, optional, f"overlays[{index}]")
        require(operation in {"replace", "vcdiff"}, f"overlays[{index}].type is unsupported")
        target_class = item["targetClass"]
        require(target_class in {"resource", "macho"}, f"overlays[{index}].targetClass is unsupported")
        require(operation != "replace" or target_class == "resource", "Mach-O may only be distributed as VCDIFF")
        if operation == "vcdiff":
            require(
                item.get("vcdiffProfile") == "rfc3284-xdelta3-no-extensions",
                f"overlays[{index}] uses an unsupported VCDIFF profile",
            )
        guest_path = safe_path(item["guestPath"], f"overlays[{index}].guestPath")
        payload_path = safe_path(item["payloadPath"], f"overlays[{index}].payloadPath")
        require(guest_path.lower() != "info.plist", "Info.plist needs a typed patch")
        require(payload_path.startswith("payload/"), "payloadPath must be inside payload/")
        require(guest_path not in guest_paths, f"duplicate guestPath {guest_path}")
        require(payload_path not in payload_paths, f"duplicate payloadPath {payload_path}")
        guest_paths.add(guest_path)
        payload_paths.add(payload_path)
        for name in ("sourceSha256", "resultSha256", "payloadSha256"):
            require(isinstance(item[name], str) and SHA256_RE.fullmatch(item[name]), f"invalid {name} for {guest_path}")
        payload_bytes = item["payloadBytes"]
        result_bytes = item["resultBytes"]
        resident_bytes = item["maximumResidentBytes"]
        require(isinstance(payload_bytes, int) and not isinstance(payload_bytes, bool) and 0 < payload_bytes <= 1024 ** 3, f"invalid payloadBytes for {guest_path}")
        require(isinstance(result_bytes, int) and not isinstance(result_bytes, bool) and 0 < result_bytes <= 1024 ** 3, f"invalid resultBytes for {guest_path}")
        require(isinstance(resident_bytes, int) and not isinstance(resident_bytes, bool) and 0 <= resident_bytes <= 2 * 1024 ** 3, f"invalid maximumResidentBytes for {guest_path}")
        if operation == "replace":
            require(item["payloadSha256"].lower() == item["resultSha256"].lower(), "replace payload hash must equal result hash")
            require(payload_bytes == result_bytes, "replace payload size must equal result size")
        else:
            require(payload_bytes <= MAX_VCDIFF_BYTES, "VCDIFF payload exceeds the 256 MiB runtime limit")
            require(result_bytes <= MAX_VCDIFF_BYTES, "VCDIFF result exceeds the 256 MiB runtime limit")
            require(resident_bytes >= payload_bytes + result_bytes, "VCDIFF resident budget cannot hold payload and result")
            require(resident_bytes <= 512 * 1024 ** 2, "VCDIFF resident budget exceeds the 512 MiB runtime limit")
        total_payload += payload_bytes
        total_output += result_bytes
        total_resident += resident_bytes
        require(total_payload <= budgets["payloadBytes"], "overlays exceed payload budget")
        require(total_output <= budgets["maximumOutputBytes"], "overlays exceed output budget")
        require(total_resident <= budgets["maximumResidentBytes"], "overlays exceed resident budget")
        parsed.append(item)
    require(total_payload == budgets["payloadBytes"], "payloadBytes budget must equal the overlay sum")
    require(total_output == budgets["maximumOutputBytes"], "maximumOutputBytes budget must equal the overlay sum")
    return parsed


def validate_archive(path: Path, engine_version: str | None) -> str:
    require(path.is_file(), f"package does not exist: {path}")
    require(path.stat().st_size <= MAX_ARCHIVE_BYTES, "package exceeds 4 GiB")
    package_digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            package_digest.update(chunk)
    package_hash = package_digest.hexdigest()
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        require(len(entries) <= MAX_FILES + 64, "archive contains too many entries")
        normalized = [entry.filename.replace("\\", "/").rstrip("/") for entry in entries]
        require(len(normalized) == len(set(normalized)), "archive contains duplicate paths")
        by_name = {entry.filename.replace("\\", "/"): entry for entry in entries}
        require(MANIFEST in by_name, f"archive is missing {MANIFEST}")
        manifest_info = by_name[MANIFEST]
        require(0 < manifest_info.file_size <= MAX_MANIFEST_BYTES, "manifest size is invalid")
        manifest = json.loads(archive.read(manifest_info).decode("utf-8"))
        resources = validate_manifest(manifest, engine_version)
        payloads = {str(resource["payloadPath"]): resource for resource in resources}
        declared_directories = {"payload"}
        for payload in payloads:
            parts = payload.split("/")[:-1]
            declared_directories.update("/".join(parts[:index]) for index in range(1, len(parts) + 1))
        for entry in entries:
            require("\\" not in entry.filename, f"backslash is prohibited: {entry.filename}")
            name = entry.filename.replace("\\", "/")
            normalized_name = name.rstrip("/")
            safe_path(normalized_name, f"archive entry {name!r}")
            mode = entry.external_attr >> 16
            require(not stat.S_ISLNK(mode), f"symlink is prohibited: {name}")
            require(not entry.flag_bits & 1, f"encrypted entry is prohibited: {name}")
            if entry.is_dir():
                require(normalized_name in declared_directories, f"undeclared directory: {name}")
            else:
                require(name == MANIFEST or name in payloads, f"undeclared file: {name}")
        for payload_path, resource in payloads.items():
            require(payload_path in by_name and not by_name[payload_path].is_dir(), f"missing payload: {payload_path}")
            expected_size = int(resource["payloadBytes"])
            require(by_name[payload_path].file_size == expected_size, f"size mismatch: {payload_path}")
            digest = hashlib.sha256()
            prefix = b""
            total = 0
            with archive.open(by_name[payload_path]) as stream:
                while chunk := stream.read(256 * 1024):
                    if not prefix:
                        prefix = chunk[:4]
                    total += len(chunk)
                    require(total <= expected_size, f"payload exceeds declared size: {payload_path}")
                    digest.update(chunk)
            require(total == expected_size, f"size mismatch: {payload_path}")
            require(digest.hexdigest().lower() == str(resource["payloadSha256"]).lower(), f"SHA-256 mismatch: {payload_path}")
            require(prefix not in MACH_O_MAGICS, f"Mach-O payload is prohibited: {payload_path}")
            if resource["type"] == "vcdiff":
                with archive.open(by_name[payload_path]) as stream:
                    header = stream.read(5)
                require(
                    header == bytes.fromhex("d6c3c40000"),
                    f"VCDIFF must use the RFC 3284 no-extensions profile: {payload_path}",
                )
    return package_hash


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--engine-version")
    arguments = parser.parse_args()
    try:
        package_hash = validate_archive(arguments.package, arguments.engine_version)
    except (OSError, ValueError, zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as error:
        print(f"Invalid sdmod: {error}", file=sys.stderr)
        return 1
    print(f"Valid sdmod · SHA-256 {package_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
