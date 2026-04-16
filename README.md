# Universal Conversion Hub (UCH)

Version: `0.7.3`

Changelog:
- `CHANGELOG.md` (full project history and release notes)
- `archive/ARCHIVE_INDEX.md` (archive map and external archive-root policy)

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

## 1) What The App Does

Universal Conversion Hub (UCH) is designed as one desktop app with separate tools, instead of a single tangled converter view.

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

Each of those category tabs contains the relevant module tabs for the current feature set.

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
You can also use the standalone updater executable (`UniversalConversionHub_UCH_Updater.exe`), which supports:
- Manifest URL
- Local manifest JSON file
- GitHub repo URL (checks latest release metadata/tags)

Default updater source:
- `https://github.com/Pugmaster04/Universal-File-Conversion`

Updater security options include:
- HTTPS-only manifest/download URLs
- optional confirmation before opening download URLs
- SHA256 verification policy for downloaded update files

Example:

```json
{
  "latest_version": "0.7.3",
  "download_url": "https://example.com/UniversalConversionHub_UCH.exe",
  "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "notes": "Release notes here"
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
- `dist\UniversalConversionHub_UCH.exe`
- `dist\UniversalConversionHub_UCH_Updater.exe`
- `installer_output\UniversalConversionHub_UCH_Setup.exe`
- `release_bins\UniversalConversionHub_UCH.exe`
- `release_bins\UniversalConversionHub_UCH_Updater.exe`
- `release_bins\UniversalConversionHub_UCH_Setup.exe`

`release_bins` is the stable folder that always keeps the latest runnable app, updater, and installer binaries together.

### Linux build (preview)

```bash
chmod +x build_linux.sh
./build_linux.sh
```

Linux outputs:
- `dist/UniversalConversionHub_UCH`
- `dist/UniversalConversionHub_UCH_Updater`
- `release_bins/UniversalConversionHub_UCH`
- `release_bins/UniversalConversionHub_UCH_Updater`
- `release_bins/UniversalConversionHub_UCH_linux_<arch>.tar.gz`

Linux release packaging:
- `build_linux.sh` now stages raw Linux binaries and creates a release tarball named `UniversalConversionHub_UCH_linux_<arch>.tar.gz`
- The updater branch logic prefers Linux `.AppImage` or `.tar.gz` assets on Linux instead of Windows `.exe` assets

GitHub Actions Linux workflow:
- `.github/workflows/linux-build-release.yml`
- Builds Linux artifacts on `ubuntu-latest`
- Uploads workflow artifacts for branch builds
- Uploads `UniversalConversionHub_UCH_linux_<arch>.tar.gz` to tagged GitHub Releases

### Basic dependencies

Install Python dependencies:

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
- `%USERPROFILE%\\Documents\\Universal File Utility Suite Output\\Universal Conversion Hub Archives\\history\\v<version>\\<timestamp>_<reason>\\`

Build script also runs snapshots:
- pre-build source snapshot
- post-build source + artifacts snapshot

Legacy imported archives are also stored in that external archive root, under:
- `legacy_universal_file_utility_suite`

Override location:
- Set environment variable `UCH_ARCHIVE_ROOT`

To enable local hooks in a clone:

```powershell
git config core.hooksPath .githooks
```

## 12) Important Paths

Windows settings file:
- `%LOCALAPPDATA%\UniversalConversionHubUCH\settings.json`
- Legacy fallback: `%LOCALAPPDATA%\UniversalConversionHubHCB\settings.json`
- Legacy fallback: `%LOCALAPPDATA%\UniversalFileUtilitySuite\settings.json`
- Updater settings: `%LOCALAPPDATA%\UniversalConversionHubUCH\updater_settings.json`
- Updater legacy fallback: `%LOCALAPPDATA%\UniversalConversionHubHCB\updater_settings.json`
- Updater legacy fallback: `%LOCALAPPDATA%\UniversalFileUtilitySuite\updater_settings.json`

Linux settings file:
- `$XDG_CONFIG_HOME/UniversalConversionHubUCH/settings.json`
- Fallback: `~/.config/UniversalConversionHubUCH/settings.json`
- Updater settings: `$XDG_CONFIG_HOME/UniversalConversionHubUCH/updater_settings.json`
- Updater fallback: `~/.config/UniversalConversionHubUCH/updater_settings.json`

Default output root:
- Windows: `%USERPROFILE%\Documents\Universal Conversion Hub Output`
- Linux: `~/Documents/Universal Conversion Hub Output`
- Linux fallback when `~/Documents` is absent: `~/Universal Conversion Hub Output`

Updater download folder default:
- Windows/Linux: `~/Downloads`
- Fallback when `~/Downloads` is absent: `~`

## 13) Legal/Safety Notes

- Use lawful personal workflows.
- Test on a small sample before large batch jobs.
- Keep backups for destructive operations.

