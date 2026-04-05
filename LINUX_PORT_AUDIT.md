# Linux Port Audit

Date: 2026-04-05
Branch: `codex/linux-port`

## Recommendation

Use the current repository for the Linux port. The codebase is already mostly shared Python/Tk code, so the Linux work should stay in this repo and be isolated by branch until the platform layer is stable.

## Current Linux-Ready Pieces

- `build_linux.sh` already exists and builds the app and updater with PyInstaller.
- Single-instance handling already has a POSIX lock-file fallback in both the app and updater.
- Non-Windows path opening already falls back to `xdg-open`.
- `requirements.txt` already limits `windnd` to Windows only.

## Primary Blockers

### 1. Backend discovery is heavily Windows-biased

Files:
- `modular_file_utility_suite.py`

Issues:
- FFmpeg, Pandoc, 7-Zip, LibreOffice, and ImageMagick discovery includes many `Program Files`, `LOCALAPPDATA`, and WinGet-specific paths.
- Install commands in the backend metadata are `winget` only.

Linux work needed:
- Add Linux detection paths and binary names where needed.
- Prefer `shutil.which(...)` first, then common Linux install locations.
- Replace single install command strings with per-platform install guidance.

### 2. Settings and output paths are Windows-centric

Files:
- `modular_file_utility_suite.py`
- `suite_updater.py`

Issues:
- App state roots default to `%LOCALAPPDATA%`.
- Default output paths assume `~/Documents/...`.

Linux work needed:
- Move app settings to XDG locations:
  - config: `$XDG_CONFIG_HOME` or `~/.config`
  - state/cache where appropriate
- Keep output folder configurable, but use a Linux-safe default if `Documents` is absent.

### 3. Drag and drop is Windows-only

Files:
- `modular_file_utility_suite.py`
- `requirements.txt`

Issues:
- Drag/drop currently depends on `windnd`.
- Linux builds will start without drag/drop.

Linux work needed:
- Add a Linux-capable drag/drop backend for Tk, or accept that Linux launches initially without drag/drop and track it as a follow-up.

### 4. File reveal behavior is incomplete on Linux

Files:
- `modular_file_utility_suite.py`
- `suite_updater.py`

Issues:
- Windows uses `explorer /select,`.
- Linux falls back to opening the parent folder with `xdg-open`, which is acceptable but not equivalent to “reveal selected file”.

Linux work needed:
- Keep parent-folder fallback as baseline.
- Optionally add file-manager-specific reveal support later.

### 5. Build and packaging are not Linux-release complete

Files:
- `build_linux.sh`
- `build_suite_release.bat`
- `installer/UniversalConversionHub_UCH.iss`

Issues:
- Windows has a full release pipeline with installer and archive snapshots.
- Linux currently only builds raw PyInstaller binaries.
- There is no Linux packaging target such as AppImage, `.tar.gz`, `.deb`, or `.rpm`.

Linux work needed:
- Decide on first Linux artifact:
  - recommended first target: `.tar.gz` or AppImage
- Add Linux artifact staging to match GitHub Releases.
- Extend archive/snapshot tooling to include Linux outputs.

### 6. Updater asset selection is not platform-aware

Files:
- `suite_updater.py`

Issues:
- GitHub release asset selection currently looks for generic release assets, but it does not choose assets by OS/platform in a structured way.
- Once Linux builds are attached to releases, the updater needs to avoid downloading Windows `.exe` assets on Linux.

Linux work needed:
- Add platform-aware asset selection logic for:
  - Windows app
  - Windows updater
  - Windows installer
  - Linux app package(s)

### 7. Documentation is still Windows-first

Files:
- `README.md`

Issues:
- Build, path, updater, and install guidance are mostly Windows-focused.

Linux work needed:
- Split docs into platform sections where needed.
- Add backend installation examples for major Linux package managers.

## Existing Code That Is Already Cross-Platform Enough

- Core file conversion engine is mostly platform-agnostic.
- FFmpeg/Pandoc/LibreOffice/ImageMagick process execution is portable.
- POSIX single-instance fallback is already present.
- `xdg-open` fallback is already implemented.

## Recommended Implementation Order

1. Backend detection and install metadata abstraction
2. XDG config/state/output path support
3. Updater platform-aware asset selection
4. Linux release packaging target
5. Drag/drop on Linux
6. Linux documentation and release process polish

## Recommended First Deliverable

The first Linux milestone should be:

- app runs on Linux from source
- app builds with `build_linux.sh`
- backend detection works for Linux-installed tools
- settings are stored in XDG-compatible locations
- GitHub Releases can publish and distinguish Linux artifacts

That is the minimum useful Linux version. Drag/drop and native packaging can follow if they slow down the first stable port.
