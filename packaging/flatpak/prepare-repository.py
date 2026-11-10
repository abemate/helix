#!/usr/bin/env python3
"""Prepare a local ArkHost Flatpak repository; never upload or deploy it.

Signed example:
  ./prepare-repository.py HelixNotes.flatpak --output /tmp/arkhost-signed \
      --gpg-key FULL_OPENPGP_FINGERPRINT

For an update, add --previous-directory /path/to/previous/output. Its repository
is copied, preserving old commits and deltas; the previous output is untouched.
The output must be a fresh directory outside the previous directory.

Use --unsigned for local staging while a signing key is unavailable. Unsigned
staging produces no public-key files or installation descriptors. Prepare a new
signed output before distribution; never disable client signature verification.

Requires Python 3, Flatpak, OSTree (CLI or Python GObject bindings) and, for
signed output, GnuPG. Signing uses the normal
GPG agent/pinentry. Only the public key is exported. The input bundle should be
exported with collection ID com.arkhost.Flatpak and contain the canonical app's
x86_64/stable ref. No packages are installed and no network commands are run.
"""

import argparse
import base64
import configparser
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit


APP_ID = "com.helixnotes.HelixNotes"
APP_REF = f"app/{APP_ID}/x86_64/stable"
COLLECTION_ID = "com.arkhost.Flatpak"
RUNTIME_REPO = "https://dl.flathub.org/repo/flathub.flatpakrepo"
DEFAULT_URL = "https://repo.arkhost.com/flatpak/"


def run(*args, capture=False, binary=False):
    return subprocess.run(
        [str(arg) for arg in args],
        check=True,
        stdout=subprocess.PIPE if capture else None,
        text=not binary,
        env={**os.environ, "LC_ALL": "C"},
    ).stdout


def initialize_repository(repository):
    repository.mkdir(parents=True, exist_ok=False)
    if shutil.which("ostree"):
        run("ostree", f"--repo={repository}", "init", "--mode=archive-z2")
    else:
        # Fedora already supplies these native bindings with Flatpak. Keep the
        # fallback isolated so installations with the CLI do not require them.
        run(sys.executable, "-c", (
            "import sys, gi; gi.require_version('OSTree', '1.0'); "
            "from gi.repository import Gio, OSTree; "
            "repo = OSTree.Repo.new(Gio.File.new_for_path(sys.argv[1])); "
            "repo.create(OSTree.RepoMode.ARCHIVE_Z2, None)"
        ), repository)
    run("flatpak", "build-update-repo", "--no-update-appstream",
        f"--collection-id={COLLECTION_ID}", repository)


def validate_repository(repository):
    """Inspect Flatpak's summary and app metadata, not the bundle's binary format."""
    branches = run("flatpak", "repo", "--branches", repository, capture=True)
    refs = {
        line.split()[0]
        for line in branches.splitlines()
        if line.split() and line.split()[0].startswith(("app/", "runtime/"))
    }
    if refs != {APP_REF}:
        raise ValueError(f"Expected only {APP_REF}; found {sorted(refs)}")
    metadata = configparser.ConfigParser(interpolation=None)
    metadata.read_string(
        run("flatpak", "repo", f"--metadata={APP_REF}", repository, capture=True)
    )
    if metadata.get("Application", "name", fallback="") != APP_ID:
        raise ValueError("Imported application metadata has an unexpected ID")
    runtime = metadata.get("Application", "runtime", fallback="")
    if not runtime.startswith("org.gnome.Platform/x86_64/"):
        raise ValueError(f"Expected the GNOME x86_64 runtime; found {runtime!r}")


def write_descriptor(path, section, fields):
    descriptor = configparser.ConfigParser(interpolation=None)
    descriptor.optionxform = str
    descriptor[section] = fields
    with path.open("x", encoding="utf-8") as stream:
        descriptor.write(stream, space_around_delimiters=False)


def prepare(args):
    bundle = args.bundle.expanduser().resolve(strict=True)
    output = args.output.expanduser().absolute()
    if not bundle.is_file():
        raise ValueError("The bundle must be a regular file")
    if os.path.lexists(output):
        raise ValueError("Output already exists; choose a fresh staging directory")
    previous = None
    if args.previous_directory:
        previous = args.previous_directory.expanduser().resolve(strict=True)
        if output.resolve().is_relative_to(previous):
            raise ValueError("Output must be outside the previous directory")
        if not (previous / "repo").is_dir():
            raise ValueError("Previous directory must contain a repo directory")
        validate_repository(previous / "repo")
        old_fingerprint = previous / "gpg-fingerprint.txt"
        if args.gpg_key and not old_fingerprint.exists():
            raise ValueError("Signing an update requires a previous signed output; omit --previous-directory for the first signed publication")
        if args.gpg_key:
            if old_fingerprint.read_text().strip().upper() != args.gpg_key:
                raise ValueError("Previous repository uses another signing key; key rotation requires a separate plan")
    for command in ("flatpak", "gpg") if args.gpg_key else ("flatpak",):
        if shutil.which(command) is None:
            raise ValueError(f"Required command not found: {command}")
    homedir = []
    if args.gpg_homedir:
        keyring = args.gpg_homedir.expanduser().resolve(strict=True)
        if not keyring.is_dir():
            raise ValueError("GPG homedir must be an existing directory")
        homedir = [f"--gpg-homedir={keyring}"]

    output.mkdir(parents=True, exist_ok=False)
    incomplete = output / "INCOMPLETE.txt"
    incomplete.write_text("Local preparation has not completed. Do not publish this directory.\n")
    repository = output / "repo"
    # An empty temporary import makes it impossible for an old repo ref to mask
    # an input bundle with the wrong app, architecture or branch.
    with tempfile.TemporaryDirectory(prefix=".flatpak-import-", dir=output) as scratch:
        imported = Path(scratch) / "repo"
        initialize_repository(imported)
        print("Importing and checking the canonical application bundle", flush=True)
        run("flatpak", "build-import-bundle", "--no-update-summary", imported, bundle)
        # `flatpak repo` reads summary metadata, so create a private preflight
        # summary before inspecting the import. The signed summary comes later.
        run("flatpak", "build-update-repo", "--no-update-appstream", imported)
        validate_repository(imported)
        if previous:
            print("Copying the previous repository without pruning its history", flush=True)
            shutil.copytree(previous / "repo", repository, copy_function=shutil.copy2)
        else:
            initialize_repository(repository)
        # Recommit onto the hosted branch so each update descends from its last
        # published head and uses this repository's collection binding.
        run("flatpak", "build-commit-from", f"--src-repo={imported}",
            f"--src-ref={APP_REF}", "--no-update-summary", repository, APP_REF)

    signing = []
    public_key = None
    if args.gpg_key:
        public_key = output / "arkhost-flatpak.gpg"
        gpg_homedir = []
        if args.gpg_homedir:
            gpg_homedir = ["--homedir", str(keyring)]
        exported = run("gpg", "--batch", *gpg_homedir, "--export", args.gpg_key,
                       capture=True, binary=True)
        if not exported:
            raise ValueError("GPG exported no public key for the requested fingerprint")
        public_key.write_bytes(exported)
        signing = [f"--gpg-sign={args.gpg_key}", *homedir]
        print("Signing the application commit", flush=True)
        run("flatpak", "build-sign", "--arch=x86_64", *signing,
            repository, APP_ID, "stable")

    print("Updating AppStream, summary and static deltas", flush=True)
    run("flatpak", "build-update-repo", "--generate-static-deltas",
        "--default-branch=stable", f"--collection-id={COLLECTION_ID}",
        "--title=ArkHost Flatpak Repository", "--homepage=https://arkhost.com",
        *signing, *([f"--gpg-import={public_key}"] if public_key else []), repository)
    validate_repository(repository)

    if args.unsigned:
        (output / "UNSIGNED-STAGING.txt").write_text(
            "UNSIGNED LOCAL STAGING. Do not publish this repository.\n"
            "No installation descriptors or public-key files were generated.\n"
            "Prepare a fresh output with --gpg-key before distribution.\n"
        )
        print(f"Unsigned staging ready: {output}. No installation links generated.", flush=True)
    else:
        (output / "gpg-fingerprint.txt").write_text(args.gpg_key + "\n")
        encoded_key = base64.b64encode(exported).decode("ascii")
        repository_url = args.url.rstrip("/") + "/repo/"
        common = {"Url": repository_url, "GPGKey": encoded_key,
                  "DeploySideloadCollectionID": COLLECTION_ID}
        write_descriptor(output / "arkhost.flatpakrepo", "Flatpak Repo", {
            "Title": "ArkHost Flatpak Repository", "Homepage": "https://arkhost.com",
            "DefaultBranch": "stable", **common,
        })
        write_descriptor(output / "HelixNotes.flatpakref", "Flatpak Ref", {
            "Title": "HelixNotes", "Name": APP_ID, "Branch": "stable",
            "IsRuntime": "false", "SuggestRemoteName": "arkhost",
            "RuntimeRepo": RUNTIME_REPO,
            "Description": "Local Markdown notes by Yuri Karamian.", **common,
        })
        print(f"Signed repository and installation descriptors ready: {output}", flush=True)
    incomplete.unlink()
    print("Nothing was uploaded, deployed or installed.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("bundle", type=Path, help="Canonical HelixNotes x86_64/stable .flatpak bundle")
    parser.add_argument("--output", required=True, type=Path, help="Fresh output directory")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--gpg-key", help="Full signing-key fingerprint (40 or 64 hexadecimal characters)")
    mode.add_argument("--unsigned", action="store_true", help="Local staging only; generate no installation descriptors")
    parser.add_argument("--gpg-homedir", type=Path, help="Existing GPG home; otherwise use the normal keyring")
    parser.add_argument("--url", default=DEFAULT_URL, help="Public base URL, excluding the repo/ suffix")
    parser.add_argument("--previous-directory", type=Path, help="Previous prepared output whose repo/history must be retained")
    args = parser.parse_args()
    if args.gpg_key:
        args.gpg_key = args.gpg_key.upper()
        if not re.fullmatch(r"(?:[0-9A-F]{40}|[0-9A-F]{64})", args.gpg_key):
            parser.error("--gpg-key must be a complete hexadecimal fingerprint")
    if args.gpg_homedir and args.unsigned:
        parser.error("--gpg-homedir requires --gpg-key")
    url = urlsplit(args.url)
    if (url.scheme != "https" or not url.netloc or url.username or url.password
            or url.query or url.fragment or any(ord(c) < 33 for c in args.url)):
        parser.error("--url must be an absolute HTTPS base URL without credentials, query or fragment")
    try:
        prepare(args)
    except (OSError, ValueError, configparser.Error, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Preparation stopped: {error}\nAny partial output was preserved; choose a fresh output to retry.\n")


if __name__ == "__main__":
    main()
