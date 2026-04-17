# Format Foundry User Guide

This guide keeps the detailed install, build, workflow, backend, and archive notes that used to live in the repo front-page README.

Version: `1.8.12`

Changelog:
- `CHANGELOG.md` (full project history and release notes)
- `archive/ARCHIVE_INDEX.md` (archive map and external archive-root policy)

Canonical release line:
- `1.8.12` is the current Windows + Linux UX, packaging, and audit milestone.
- Version numbers are now coordinated per release target instead of following the older staged-major/staged-minor note that used to live in this file.

This is a modular desktop suite for practical file workflows:
- Convert
- Compress
- Extract
- Metadata
- PDF / Documents
- Images / Audio / Video
- Archives
- Rename / Organize
- Duplicate Finder
- Storage Analyzer
- Checksums / Integrity
- Subtitles
- Torrents
- Presets / Batch Jobs

Advanced media modules now include:
- Images: resize to fit, export to a chosen format, and optional sharpen pass
- Audio: format conversion, sample-rate conversion, mono/stereo control, loudness normalization, and silence trimming
- Video: remux, trim clips, stream-prep presets, and thumbnail-sheet generation

Image conversion coverage includes:
- Standard raster formats such as PNG, JPG, WEBP, BMP, GIF, TIFF, and ICO
- Modern Apple/HEIF-family formats such as HEIC, HEIF, and AVIF when the bundled `pillow-heif` plugin is available
- JPEG XL (`.jxl`) output plus common camera-raw inputs such as DNG, CR2/CR3, NEF, ARW, RAF, ORF, RW2, and PEF through the `ImageMagick` backend

This file is the combined **README + How-To** guide.

## 0) Install/Launch Safety

Installer behavior is configured to reduce duplicate installs and preserve upgrades:
- Reuses previous install directory automatically (`UsePreviousAppDir`)
- Hides directory chooser for upgrades (`DisableDirPage=auto`)
- Detects running app/updater instances via mutex and requests closing before install (`AppMutex`)
- Replaces existing installed files with the new version during upgrade

Runtime behavior:
- Main app is single-instance (one running copy at a time)
- Updater is also single-instance

Uninstall behavior:
- Windows installed builds now expose `File -> Uninstall...`, `Settings -> Uninstall App`, and a Start-menu shortcut named `Uninstall Format Foundry`
- Debian installs expose `File -> Uninstall...`, `Settings -> Uninstall App`, or the manual command:

```bash
sudo apt remove format-foundry
```

- AppImage copies are removed by deleting the `.AppImage` file
- Settings and output folders are not removed automatically

## 1) What The App Does

Format Foundry is designed as one desktop app with separate tools, instead of a single tangled converter view.

Core behavior:
- Queue-based processing for batch workflows
- Safe output conflict prompts (replace / rename / change location / cancel)
- Optional backend integrations for advanced formats
- Activity log for command/result visibility
- First-run setup, settings persistence, and update checks

## 2) UI Layout

Top tabs:
- Workspace
- Suite Plan
- Backends / Links
- Activity Log

Workspace now has a second navigation layer:
- Conversion
- Advanced
- Misc
- Aria2

Each of those category tabs contains the relevant module tabs for the current feature set.

The dedicated `Aria2` workspace category currently contains:
- `Downloads` for aria2-managed HTTP(S), FTP, SFTP, BitTorrent, magnet, and Metalink transfers
- `Torrents` for `.torrent` creation plus torrent download/extraction through `aria2c`

Linux note:
- If drag-and-drop is not available on a Linux build, the app now shows an explicit fallback message and the supported path remains `Add Files` / `Add Folder`.
- Linux CI now runs the built app and updater in headless `--smoke-test` mode after packaging, so the branch validates frozen runtime startup paths and settings-path resolution in addition to the raw build.

## 3) First Run + Settings

First launch opens setup wizard so you can configure:
- Output folder
- Theme and window mode
- Update checks
- Optional backend prompt behavior
- Update manifest URL

After that, use:
- `File -> Settings`

Settings page includes:
- Output path defaults
- Dark mode, fullscreen, borderless defaults
- Hover tooltip preference for advanced option explanations
  - Applies to Convert, Compress, Storage Analyzer, Duplicate Finder, and Backends / Links
- High contrast mode, interface scaling, and reduced-motion startup behavior for improved accessibility
- Startup animation toggle + duration
- FFmpeg thread count (`0` = auto)
- Activity log line retention
- Update and backend prompt settings
- Security controls:
  - confirm before opening external links
  - require HTTPS for backend/update links
  - require HTTPS for update manifest URLs
  - allow/block local manifest files
  - restrict update manifests/downloads to trusted hosts
- Support tools:
  - `Backends / Links` shows detected backend versions and the current environment support tier
  - `File -> Export Bug Report...` exports a JSON report with OS details, backend versions, settings, and recent logs

## 4) Quick Start

1. Open a module (example: Convert).
2. Add files or a folder.
3. Select valid options for the current queue type.
4. Confirm output path.
5. Run queue.
6. Review output and Activity Log.

Convert queue behavior:
- Queue is limited to one source extension at a time.
- Target format list updates to valid outputs for the current source type.

## 5) Optional Backends

Base app functions work without all backends, but advanced workflows improve when these are installed:
- FFmpeg + FFprobe
- Pandoc
- LibreOffice
- 7-Zip
- ImageMagick
- Aria2 (for torrent download / extraction)

Torrent note:
- Torrent file creation is built into the app through the bundled `torrentool` Python dependency.
- Torrent download and extraction requires the optional `Aria2` backend.
- The torrent workflow does not apply any download speed limit flags.

Backends panel behavior:
- Detected backend path: click to open file location
- Missing backend: click to open install link

## 6) Update Sources

Use `Settings -> Update manifest URL` for app update checks.
You can also use the standalone updater executable (`FormatFoundry_Updater.exe`), which supports:
- Manifest URL
- Local manifest JSON file
- GitHub repo URL (checks latest release metadata/tags)

Default updater source:
- `https://github.com/Pugmaster04/Format-Foundry`

Updater security options include:
- HTTPS-only manifest/download URLs
- optional confirmation before opening download URLs
- SHA256 verification policy for downloaded update files
- optional trusted-host allowlist enforcement for manifests and download URLs

Example:

```json
{
  "latest_version": "1.8.12",
  "download_url": "https://github.com/Pugmaster04/Format-Foundry/releases/download/v1.8.12/FormatFoundry_Setup.exe",
  "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "notes": "Release notes here",
  "compatibility": {
    "platforms": ["windows", "linux"],
    "architectures": ["x86_64", "amd64"],
    "minimum_os_versions": {
      "windows": "10",
      "linux:ubuntu": "24.04"
    },
    "minimum_backends": {
      "ffmpeg": "6.0"
    }
  }
}
```

Manual check:
- `Help -> Check for Updates`

## 7) Build And Run

### Run from source

```powershell
python modular_file_utility_suite.py
```

### Build one-file EXE + installer

```powershell
build_suite_release.bat
```

Outputs:
- `dist\FormatFoundry.exe`
- `dist\FormatFoundry_Updater.exe`
- `installer_output\FormatFoundry_Setup.exe`
- `release_bins\FormatFoundry.exe`
- `release_bins\FormatFoundry_Updater.exe`
- `release_bins\FormatFoundry_Setup.exe`

`release_bins` is the stable folder that always keeps the latest runnable app, updater, and installer binaries together.

### Linux build (preview)

```bash
chmod +x build_linux.sh
./build_linux.sh
```

Linux outputs:
- `dist/FormatFoundry`
- `dist/FormatFoundry_Updater`
- `release_bins/FormatFoundry`
- `release_bins/FormatFoundry_Updater`
- `release_bins/FormatFoundry_linux_<arch>.tar.gz`
- `release_bins/format-foundry_<version>_<deb-arch>.deb`
- `release_bins/FormatFoundry_linux_<arch>.AppImage`

Linux release packaging:
- `build_linux.sh` now stages raw Linux binaries, creates a release tarball named `FormatFoundry_linux_<arch>.tar.gz`, builds a Debian package named `format-foundry_<version>_<deb-arch>.deb`, and builds an AppImage named `FormatFoundry_linux_<arch>.AppImage`
- Debian package installs to `/opt/format-foundry` and exposes launchers:
  - `format-foundry`
  - `format-foundry-updater`
- The AppImage contains the app, bundled updater binary, desktop metadata, and icon resources so it can launch without the source tree.
- The updater branch logic now prefers Linux `.deb` assets on Debian-family systems, then `.AppImage`, then `.tar.gz`

Ubuntu 24.04 install from `.deb`:

```bash
sudo apt install ./format-foundry_<version>_<deb-arch>.deb
```

Launch after `.deb` install:

```bash
format-foundry
```

The Debian package installs a standalone app under `/opt/format-foundry`. It does not rely on the source checkout after install.

Ubuntu 24.04 install from AppImage:

```bash
chmod +x FormatFoundry_linux_<arch>.AppImage
./FormatFoundry_linux_<arch>.AppImage
```

The AppImage is also self-contained. You can move it anywhere you want after download.

Optional AppImage launcher install:

```bash
mkdir -p ~/Applications
cp FormatFoundry_linux_<arch>.AppImage ~/Applications/
chmod +x ~/Applications/FormatFoundry_linux_<arch>.AppImage
~/Applications/FormatFoundry_linux_<arch>.AppImage
```

Ubuntu 24.04 build-from-source prerequisites:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-tk tk-dev dpkg-dev curl
```

If `apt update` fails because of an unrelated third-party repository on your machine, fix or disable that repository first. That is outside this project's build logic.

Build from a clean clone:

```bash
chmod +x build_linux.sh
./build_linux.sh
```

`build_linux.sh` now creates and reuses a repo-local `.venv` automatically. Do not run a system-wide `pip install` for this project on Ubuntu 24.04.

GitHub Actions Linux workflow:
- `.github/workflows/linux-build-release.yml`
- Builds Linux artifacts on `ubuntu-latest`
- Uploads workflow artifacts for branch builds
- Validates the generated `.deb` layout in CI
- Smoke-tests the built AppImage in CI
- Uploads `FormatFoundry_linux_<arch>.tar.gz`, `format-foundry_<version>_<deb-arch>.deb`, and `FormatFoundry_linux_<arch>.AppImage` to tagged GitHub Releases

### Basic dependencies

For source development outside the Linux packaging flow:

```powershell
python -m pip install -r requirements.txt
```

## 8) Activity Log

The log tracks:
- Executed commands
- Workflow progress
- File output mapping
- Errors

Retention is configurable in Settings (`log_max_lines`) to avoid unbounded growth.

## 9) Performance Tips

- Use SSD output paths for faster batch writes.
- Install FFmpeg/FFprobe for media-heavy workflows.
- Tune FFmpeg threads in Settings:
  - `0` = backend default/auto
  - Higher values can increase speed and CPU usage
- Keep queues type-consistent.

## 10) Troubleshooting

Backend shows `Not found`:
- Install from Backends / Links tab
- Restart app
- Verify executable path exists

Wrong/limited conversion options:
- Queue may be extension-locked to a different source type
- Clear queue, add one known test file, then retry

No update results:
- Check manifest URL or GitHub repo URL
- Validate JSON keys and URL accessibility
- If using GitHub: publish a Release (recommended) or include `update_manifest.json` in the repo

## 11) Historical Snapshots / Backups

This repo uses automated historical snapshots:
- `tools/create_historical_snapshot.ps1`
- `.githooks/post-commit`

Default external snapshot location:
- `%USERPROFILE%\\Documents\\Universal File Utility Suite Output\\Format Foundry Archives\\history\\v<version>\\<timestamp>_<reason>\\`

Build script also runs snapshots:
- pre-build source snapshot
- post-build source + artifacts snapshot

Legacy imported archives are also stored in that external archive root, under:
- `legacy_universal_file_utility_suite`

Override location:
- Set environment variable `FORMAT_FOUNDRY_ARCHIVE_ROOT`

To enable local hooks in a clone:

```powershell
git config core.hooksPath .githooks
```

## 12) Important Paths

Windows settings file:
- `%LOCALAPPDATA%\FormatFoundry\settings.json`
- Legacy fallback: `%LOCALAPPDATA%\UniversalConversionHubHCB\settings.json`
- Legacy fallback: `%LOCALAPPDATA%\UniversalFileUtilitySuite\settings.json`
- Updater settings: `%LOCALAPPDATA%\FormatFoundry\updater_settings.json`
- Updater legacy fallback: `%LOCALAPPDATA%\UniversalConversionHubHCB\updater_settings.json`
- Updater legacy fallback: `%LOCALAPPDATA%\UniversalFileUtilitySuite\updater_settings.json`

Linux settings file:
- `$XDG_CONFIG_HOME/FormatFoundry/settings.json`
- Fallback: `~/.config/FormatFoundry/settings.json`
- Updater settings: `$XDG_CONFIG_HOME/FormatFoundry/updater_settings.json`
- Updater fallback: `~/.config/FormatFoundry/updater_settings.json`

Default output root:
- Windows: `%USERPROFILE%\Documents\Format Foundry Output`
- Linux: `~/Documents/Format Foundry Output`
- Linux fallback when `~/Documents` is absent: `~/Format Foundry Output`

Updater download folder default:
- Windows/Linux: `~/Downloads`
- Fallback when `~/Downloads` is absent: `~`

## 13) Legal/Safety Notes

- Use lawful personal workflows.
- Test on a small sample before large batch jobs.
- Keep backups for destructive operations.


