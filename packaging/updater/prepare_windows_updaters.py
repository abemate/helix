#!/usr/bin/env python3
"""Wrap existing signed Windows installers for Tauri's legacy ZIP updater.

Tauri updater 2.10 builds zip with default-features=false. Only ZIP_STORED
entries work; Python's ability to extract Deflate does not prove compatibility.
"""
import argparse
import hashlib
from pathlib import Path
import re
import zipfile


def validate_archive(archive: Path, installer: Path) -> None:
    with zipfile.ZipFile(archive) as wrapper:
        entries = wrapper.infolist()
        if len(entries) != 1 or entries[0].filename != installer.name:
            raise ValueError("Updater ZIP must contain exactly one root-level installer")
        if entries[0].compress_type != zipfile.ZIP_STORED or entries[0].flag_bits & 1:
            raise ValueError("Tauri requires unencrypted ZIP_STORED installer entries")
        if hashlib.sha256(wrapper.read(entries[0])).digest() != hashlib.sha256(installer.read_bytes()).digest():
            raise ValueError("Wrapped installer differs from the tested original")


def build_archive(installer: Path, archive: Path) -> None:
    if not installer.is_file() or installer.suffix.lower() not in {".exe", ".msi"}:
        raise ValueError("Expected an existing Windows EXE or MSI installer")
    archive.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive.with_name(archive.name + ".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as wrapper:
            wrapper.write(installer, arcname=installer.name, compress_type=zipfile.ZIP_STORED)
        validate_archive(temporary, installer)
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--installers", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", args.version):
        parser.error("Invalid release version")
    prefix = "HelixNotes_" + args.version
    for source, target in [(prefix + "_x64-setup.exe", prefix + "_x64-setup.nsis.zip"),
                           (prefix + "_x64_en-US.msi", prefix + "_x64_en-US.msi.zip")]:
        build_archive(args.installers / source, args.output / target)
        print("Validated ZIP_STORED:", target)


if __name__ == "__main__":
    main()
