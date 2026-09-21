#!/usr/bin/env python3
"""Create the strict RFC 3284/xdelta3 payload accepted by sdmod v2."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
from pathlib import Path


MAGIC = bytes.fromhex("d6c3c40000")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def make_delta(source: Path, target: Path, output: Path, executable: str = "xdelta3") -> None:
    if output.exists():
        raise ValueError(f"refusing to overwrite {output}")
    if not source.is_file() or not target.is_file():
        raise ValueError("source and target must be regular files")
    resolved = shutil.which(executable)
    if resolved is None:
        raise ValueError(f"xdelta3 executable not found: {executable}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.unlink(missing_ok=True)
    try:
        # -S: no secondary compressor, -A: no application header,
        # -n: no Adler32 window extension, -a: no 3.2 armor header.
        subprocess.run(
            [resolved, "-S", "-A", "-n", "-a", "-e", "-s", str(source), str(target), str(temporary)],
            check=True,
        )
        if temporary.read_bytes()[:5] != MAGIC:
            raise ValueError("xdelta3 produced an extended/non-RFC3284 header")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="unmodified file from the exact IPA")
    parser.add_argument("target", type=Path, help="locally modified result")
    parser.add_argument("output", type=Path, help="new .vcdiff payload")
    parser.add_argument("--xdelta3", default="xdelta3")
    args = parser.parse_args()
    try:
        make_delta(args.source, args.target, args.output, args.xdelta3)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    print(f"sourceSha256={sha256(args.source)}")
    print(f"resultSha256={sha256(args.target)}")
    print(f"payloadSha256={sha256(args.output)}")
    print(f"payloadBytes={args.output.stat().st_size}")
    print(f"resultBytes={args.target.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
