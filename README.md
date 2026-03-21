# Universal File Utility Suite (Modular Starter)

Version: `0.5`

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
- Presets / Batch Jobs

This file is the combined **README + How-To** guide.

## 1) What The App Does

Universal File Utility Suite is designed as one desktop app with separate tools, instead of a single tangled converter view.

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

Workspace contains module tabs for each workflow category.

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
- Startup animation toggle + duration
- FFmpeg thread count (`0` = auto)
- Activity log line retention
- Update and backend prompt settings

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

Backends panel behavior:
- Detected backend path: click to open file location
- Missing backend: click to open install link

## 6) Update Manifest

Use `Settings -> Update manifest URL` for app update checks.

Example:

```json
{
  "latest_version": "0.5",
  "download_url": "https://example.com/UniversalFileUtilitySuite.exe",
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
- `dist\UniversalFileUtilitySuite.exe`
- `installer_output\UniversalFileUtilitySuite_Setup.exe`

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
- Check manifest URL
- Validate JSON keys and URL accessibility

## 11) Historical Snapshots / Backups

This repo includes automated historical snapshots:
- `tools/create_historical_snapshot.ps1`
- `.githooks/post-commit`

Snapshot location:
- `archive/history/v<version>/<timestamp>_<reason>/`

Build script also runs snapshots:
- pre-build source snapshot
- post-build source + artifacts snapshot

To enable local hooks in a clone:

```powershell
git config core.hooksPath .githooks
```

## 12) Important Paths

Settings file:
- `%LOCALAPPDATA%\UniversalFileUtilitySuite\settings.json`

Default output root:
- `%USERPROFILE%\Documents\Universal File Utility Suite Output`

## 13) Legal/Safety Notes

- Use lawful personal workflows.
- Test on a small sample before large batch jobs.
- Keep backups for destructive operations.

