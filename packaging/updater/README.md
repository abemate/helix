# Windows updater packaging

Tauri updater 2.10 accepts a signed NSIS executable directly. The public Windows
feed uses `HelixNotes_<version>_x64-setup.exe` and its matching `.exe.sig`.

Legacy ZIP updater archives must contain exactly one installer at their root,
with **ZIP_STORED** entries. The updater's `zip` dependency disables default
features and has no Deflate decoder. A ZIP opening successfully in Python,
Explorer or 7-Zip does not prove that the updater can extract it.

Prepare compatibility archives from the already-tested installers:

```sh
python3 packaging/updater/prepare_windows_updaters.py \
  --version 1.3.8 --installers /path/to/installers --output /path/to/staging
pnpm test:updater-packaging
```

Sign each final archive with the existing Tauri updater identity. Verify every
signature against the public key embedded in the app. Never reuse an installer's
signature for its ZIP wrapper. Regenerate release checksums after signing.

Before publication, test the actual previous Windows release's **Download &
Install** flow against the final payload and signature. Verify that the upgraded
app reports the target version and preserves synthetic notes. Keep personal
profiles backed up and restore them after QA.

## 1.3.8 correction

The initial compatibility ZIPs incorrectly used Deflate. This reproduced
`unsupported Zip archive: Compression method not supported` in the native
1.3.7 Windows app. The feed was changed to the existing signed native EXE and
an actual 1.3.7-to-1.3.8 in-app update passed. Both compatibility ZIPs were
repacked as Stored and re-signed; installer binaries were not changed.
