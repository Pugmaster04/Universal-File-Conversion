# Universal Conversion Hub (UCH) - Project Plan

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
  - `UniversalConversionHub_UCH.exe`
  - `UniversalConversionHub_UCH_Updater.exe`
  - `UniversalConversionHub_UCH_Setup.exe`
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

## Release Versioning Policy
- Major releases use `X.0`
- Secondary feature releases use `X.Y`
- Patch releases use `X.Y.Z`
- Practical examples:
  - `1.0` = major milestone
  - `1.1` to `1.9` = secondary feature updates within that major line
  - `1.1.1` to `1.9.99` = patch/hotfix updates within a secondary release
- Future release bumps should follow this structure for app version, updater version, installer version, manifest version, README version, and changelog entries.

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

