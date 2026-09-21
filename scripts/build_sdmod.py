#!/usr/bin/env python3
"""Build a deterministic .sdmod archive from a manifest and local payload/."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from validate_sdmod import MANIFEST, validate_archive, validate_manifest


ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def archive_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    info.create_system = 3
    return info


def build_package(
    manifest_path: Path,
    output_path: Path,
    engine_version: str | None = None,
) -> str:
    if output_path.exists():
        raise ValueError(f"refusing to overwrite {output_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    resources = validate_manifest(manifest, engine_version)
    canonical_manifest = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        dir=output_path.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", allowZip64=True) as archive:
            archive.writestr(archive_info(MANIFEST), canonical_manifest)
            for resource in sorted(resources, key=lambda item: str(item["payloadPath"])):
                payload_path = str(resource["payloadPath"])
                source = manifest_path.parent / payload_path
                if not source.is_file():
                    raise ValueError(f"missing local payload {source}")
                with source.open("rb") as input_stream, archive.open(
                    archive_info(payload_path),
                    "w",
                    force_zip64=True,
                ) as output_stream:
                    shutil.copyfileobj(input_stream, output_stream, 1024 * 1024)
        package_hash = validate_archive(temporary, engine_version)
        temporary.replace(output_path)
        return package_hash
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--engine-version")
    arguments = parser.parse_args()
    try:
        package_hash = build_package(
            arguments.manifest,
            arguments.output,
            arguments.engine_version,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(f"Built {arguments.output} · SHA-256 {package_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
