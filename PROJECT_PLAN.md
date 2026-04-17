# Format Foundry - Project Plan

## Vision
Build one desktop app with modular tools instead of a single tangled interface.  
Each module should be independently testable, replaceable, and extensible.

## Architecture
- One app shell (`Tkinter` notebook with tool tabs)
- Shared backend/task engine for processing
- Module-specific tabs for workflows and UI
- Preset and batch system for repeatable operations
- External-backend detection at startup (FFmpeg, Pandoc, LibreOffice, 7-Zip, ImageMagick)

## Phases

### Phase 1 (Implemented in starter)
- `Convert`
- `Compress`
- `Extract`
- `Metadata`
- `Presets / Batch Jobs`

### Phase 2 (Starter tab + base workflow)
- `PDF / Documents`
- `Archives`
- `Rename / Organize`
- `Checksums / Integrity`
- `Subtitles`

### Phase 3 (Starter tab + analysis tools)
- `Duplicate Finder`
- `Storage Analyzer`
- Dedicated advanced modules for:
  - `Images`
  - `Audio`
  - `Video`

## Current Deliverables
- App entrypoint: `modular_file_utility_suite.py`
- Updater entrypoint: `suite_updater.py`
- Release builds:
  - `FormatFoundry.exe`
  - `FormatFoundry_Updater.exe`
  - `FormatFoundry_Setup.exe`
- Includes all requested module tabs:
  - Convert
  - Compress
  - Extract
  - Metadata
  - PDF / Documents
  - Images
  - Audio
  - Video
  - Archives
  - Rename / Organize
  - Duplicate Finder
  - Storage Analyzer
  - Checksums / Integrity
  - Subtitles
  - Presets / Batch Jobs

## Current Release Target
- Canonical coordinated release: `1.8.6`
- This milestone combines the Windows installer path, Linux packaging path, shared UX redesign work, and the cross-platform audit pass in one release line.
- App version, updater version, installer metadata, manifest version, and public install docs should stay aligned to the same release target.

## Next Recommended Upgrades
1. Add persistent job database (SQLite) for resumable queues.
2. Add plugin adapters for optional backends and per-module capability flags.
3. Add structured testing:
   - unit tests for conversion engines
   - smoke tests per module
   - backend integration tests
4. Add expanded packaging and distribution profiles:
   - Linux release packaging
   - code signing
   - automated release publishing
