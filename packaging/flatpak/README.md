# Flatpak

This builds the Git revision pinned in the manifest inside the GNOME 51 SDK. Rust
and Node dependencies are pinned by the existing lockfiles and downloaded before
the sandboxed, offline build. The shared-modules submodule supplies the Ayatana
tray libraries.

## ArkHost repository

HelixNotes can be distributed through ArkHost's own signed Flatpak repository.
The proposed public base URL is `https://repo.arkhost.com/flatpak/`. It is not
published by these commands.

The application ID is `com.helixnotes.HelixNotes`; the repository collection ID is
`com.arkhost.Flatpak`. Keep both stable so installed applications receive future
updates from the same repository.

`prepare-repository.py` imports a built bundle, prepares AppStream metadata and
static deltas, and signs the application and repository metadata with an OpenPGP
key. It exports only the public key. The signing key stays in the local keyring.
Back up that permanent signing identity offline before first publication.

After building the bundle, prepare a fresh signed output:

```sh
python3 packaging/flatpak/prepare-repository.py \
  src-tauri/target/flatpak/HelixNotes_1.3.7_x86_64.flatpak \
  --output /path/to/arkhost-flatpak-1.3.7 \
  --gpg-key FULL_OPENPGP_FINGERPRINT
```

The script uses the `ostree` command when available, or the system's OSTree
GObject bindings to initialize repositories. This Fedora workstation already
has those bindings. For subsequent releases, add
`--previous-directory /path/to/previous-output` to preserve the publication
history. Always choose a new output directory.

If the signing identity is not ready, `--unsigned` can replace `--gpg-key` for a
local preview. The output will be visibly marked as unsigned and will contain no
install descriptors.

The signed output contains:

```text
repo/                    Application repository and update metadata
arkhost.flatpakrepo      Adds the ArkHost remote
HelixNotes.flatpakref    Adds the remote and installs HelixNotes
```

Unsigned staging omits install links and is not a publishable repository. Keep
the previous signed output when preparing an update so repository history and
delta updates are retained.

Publish the prepared public files under
`/srv/www/repo.arkhost.com/flatpak/` on Shiny using the existing repository
deployment workflow. The publisher prepares local files; it does not connect to
Shiny or change its web configuration. Serve the tree over HTTPS with HTTP
keep-alive enabled. Keep repository summaries and install descriptors fresh in
any HTTP cache; content-addressed objects can be cached longer.

HelixNotes and its updates come from ArkHost. The shared GNOME runtime continues
to come from its existing upstream repository. Users install through
`HelixNotes.flatpakref` and receive updates through Discover, GNOME Software or
`flatpak update`.

## Build

Run from the repository root:

```sh
git submodule update --init packaging/flatpak/shared-modules
flatpak install --user flathub org.flatpak.Builder org.gnome.Platform//51 org.gnome.Sdk//51 org.freedesktop.Sdk.Extension.node24//26.08 org.freedesktop.Sdk.Extension.rust-stable//26.08
flatpak run org.flatpak.Builder --user --force-clean --collection-id=com.arkhost.Flatpak --state-dir=src-tauri/target/flatpak/state --repo=src-tauri/target/flatpak/arkhost-origin src-tauri/target/flatpak/build packaging/flatpak/com.helixnotes.HelixNotes.yml
flatpak build-bundle src-tauri/target/flatpak/arkhost-origin src-tauri/target/flatpak/HelixNotes_1.3.7_x86_64.flatpak com.helixnotes.HelixNotes stable --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo
```

The commands require a user-local Flathub remote. If only a system remote exists,
add the user remote first:

```sh
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
```

## Install and run

```sh
flatpak install --user src-tauri/target/flatpak/HelixNotes_1.3.7_x86_64.flatpak
flatpak run com.helixnotes.HelixNotes
```

Choose vault folders using the folder picker. Flatpak grants access to the chosen
folders through its document portal; the package does not request access to the
whole home directory. Its settings are separate from native installations.
The document portal does not forward external file-change notifications, so this
build checks visible notes and notebooks about every two seconds in small vaults.
The interval grows with scan cost in larger vaults to limit background CPU use.
It compares file size and precise modification/change timestamps, including changes made
while preserving a note's modification time. Attachments and hidden app data are
excluded from these scans; note contents are read only when a change is detected.

The build sets `HELIXNOTES_INSTALL_TYPE=flatpak`, which suppresses the in-app
updater. Install a newer bundle to update this local package. Automatic Flatpak
updates require a hosted repository or a Flathub release; neither is published by
these build commands. The bundle references Flathub for its runtime, which is
installed separately.

## Refresh dependencies

Regenerate both source lists whenever their lockfiles change. The initial lists
were generated with flatpak-builder-tools commit
`9d86d336a39b9af38b86f114b6ce5820fe260f91`:

```sh
uv run --project /path/to/flatpak-builder-tools/node python -m flatpak_node_generator --no-requests-cache --pnpm-store-version v11 --node-sdk-extension org.freedesktop.Sdk.Extension.node24//26.08 -o packaging/flatpak/node-sources.json pnpm pnpm-lock.yaml
uv run /path/to/flatpak-builder-tools/cargo/flatpak-cargo-generator.py -o packaging/flatpak/cargo-sources.json src-tauri/Cargo.lock
```

Keep the pinned pnpm archive/version in the manifest in step with
`package.json`'s `packageManager`. pnpm 11 uses the v11 store; the generator's
default v10 store does not work with it.

The offline install uses `--trust-lockfile` for this reviewed, pinned lockfile.
Flatpak verifies the downloaded sources against the generated checksums. This
keeps pnpm from querying registry metadata and attestations during the offline
build; it does not grant network access to the build sandbox.

The store developer is Yuri Karamian. The Flatpak build overrides Tauri's
identifier only for this package; native packages retain their existing ID.

Version 1.3.7 has stable package metadata dated 2026-11-10. This describes the
prepared release package; publication and the public release tag are separate
steps. Keep the manifest pinned to the source revision containing that metadata.

The prepared submission targets x86_64. The existing local bundle in Nextcloud
uses the earlier `com.helixnotes.app` ID; it has not been rebuilt or replaced by
this preparation. The new ID has a separate Flatpak profile. Users can select the
same notes folder through the system picker.

No builds, tests or Flathub linter checks were run for this submission preparation.
Flathub requires those checks before a submission can be treated as ready. See the
[submission guide](https://docs.flathub.org/docs/for-app-authors/submission) and
[current requirements](https://docs.flathub.org/docs/for-app-authors/requirements).

## Optional Flathub submission

The Flathub repository needs these files at its root:

- `com.helixnotes.HelixNotes.yml`
- `cargo-sources.json`
- `node-sources.json`
- `flathub.json`
- The `shared-modules` Git submodule, pinned to
  `6be1f986ac28a2b7d745e5ff45a3f8a2d3345083`

Desktop, icon and MetaInfo files are installed from the pinned application source.
The source currently includes the packaging metadata and the Flatpak watcher fix.
It is a preparation revision, not a published v1.3.7 release tag.

Use a branch based on `flathub/flathub`'s `new-pr` branch. Preserve the upstream
submission template. Author the submission description and any review replies
yourself, following Flathub's current requirements. This preparation does not
create a GitHub pull request or publish an application.
