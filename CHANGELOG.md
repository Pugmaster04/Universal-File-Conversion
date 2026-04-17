# Changelog

All notable changes to this project are documented in this file.

This changelog includes:
- Legacy `0.4.x` milestones (pre-canonical-repo binary iterations)
- Full `0.5` and `0.6.x` feature/fix/security/build history
- Rapid revision trails captured in archive snapshots

## [Unreleased]

## [1.8.12] - 2026-04-17

### Fixed
- The app-level `Check Updates` actions now launch the same updater flow used by `FormatFoundry_Updater`, instead of using a separate in-app manifest check path with different behavior.
- The app now syncs shared update security settings into `updater_settings.json` before launching the updater, so the in-app button and standalone updater use the same source and host policy.
- The updater now accepts GitHub release asset SHA256 digests published by the GitHub API, so strict checksum verification works without a separate manifest checksum file when checking the canonical release repo.
- Legacy updater source URLs pointing at `Pugmaster04/Universal-File-Conversion` are now normalized to the canonical `Format-Foundry` repo.
- Linux startup animation now uses a safer splash-window mode instead of the Windows-only borderless/topmost path that could fail to appear on Linux desktops.
- Linux packaging validation now runs AppStream in offline mode, so a transient upstream `502` from a referenced URL can no longer block Debian/AppImage release builds.

## [1.8.9] - 2026-04-17

### Fixed
- The top overview and quick-action shell can now be collapsed and restored from a top-level `Overview` control, reducing wasted vertical space on both Windows and Linux.
- The native menu bar is now organized as `File`, `Edit`, `Settings`, `Overview`, and `Help`, so the overview toggle sits next to the main app controls instead of being buried in the shell.

## [1.8.8] - 2026-04-16

### Added
- Backends / Links now shows detected backend versions plus an environment/support summary with trusted update-host status.
- `File -> Export Bug Report...` now writes a structured JSON report with OS details, backend versions, security/update settings, and a recent activity-log tail.
- Added a GitHub bug-report template that asks users to attach the exported environment report.

### Fixed
- Linux module screens now scale more readably on common desktop sizes, use Linux-friendly fonts, and keep bottom-of-window controls reachable through a scrollable module shell.

### Changed
- Update manifests can now include compatibility metadata so the app/updater can avoid surfacing releases that do not target the current platform, architecture, or backend baseline.
- The app and updater now support a trusted-host allowlist for update manifests and download URLs in addition to the existing HTTPS and SHA256 controls.
- Headless `--smoke-test` output now includes environment/support details instead of only path existence checks.

## [1.8.7] - 2026-04-16

### Fixed
- Linux first-run setup now keeps its action buttons visible by using a scrollable content area with a fixed footer, plus keyboard shortcuts to continue or close the wizard.
- Linux AppStream metadata now validates cleanly and includes richer store details such as release notes, screenshot data, content rating, and license-status links.

## [1.8.6] - 2026-04-16

### Fixed
- Linux packaged startup no longer risks attaching the first-run setup wizard to a hidden root window, which could leave the process running without a visible window on fresh installs.
- Startup splash focus-loss minimization is now Windows-only, preventing Linux windowed launches from being hidden without a visible recovery path while the singleton lock remains held.

## [1.8.5] - 2026-04-16

### Added
- New `Torrents` workspace tab for creating `.torrent` files in-app and downloading/extracting torrent contents through the optional `Aria2` backend.
- New dedicated `Aria2` workspace category with a `Downloads` tab for direct aria2-managed HTTP(S), FTP, SFTP, BitTorrent, magnet, and Metalink transfers.
- Torrent sources opened in `Torrents` now expose file-level selection with search, select-all/select-none, toggle controls, and a per-torrent progress view with individual file progress bars.
- `Aria2 -> Downloads` and `Aria2 -> Torrents` now include inline pause/resume/stop controls plus state badges so active transfer state is visible without adding more modal workflow interruptions.
- Linux packaging now emits stable “latest” aliases for the Debian package and AppImage so the repo front page can link directly to the current installer assets.
- The app now exposes a clear uninstall flow through `File -> Uninstall...` and `Settings -> Uninstall App`, with platform-specific actions for Windows uninstallers, Debian package removal, AppImage cleanup guidance, and portable/source copies.
- Windows GitHub Actions now build the app, updater, and installer on tagged releases so the Windows installer link on the repo front page is tied to an automated release path instead of manual drift.
- Install-surface validation now checks that documented public installer filenames are present in the build outputs before release staging completes.

### Changed
- Ubuntu/Linux packaging guidance now clearly separates packaged installs (`.deb` or AppImage) from contributor source builds, and documents that packaged installs do not depend on the source tree after installation.
- The front-page `README.md` is now a shorter GitHub-facing install and overview page, while the detailed instructions moved to `docs/USER_GUIDE.md`.
- Workspace modules now render with a stronger shared shell, including a premium module header, clearer hierarchy, and animated accent treatment on tab focus without changing the underlying workflows.
- The shared theme has been reworked around a more deliberate cross-platform palette and clearer visual hierarchy so the app reads less like a utility scaffold and more like a finished desktop tool.
- Startup loading now uses a more polished branded sequence instead of the earlier simple geometric loader, while keeping the existing reduced-motion and focus-loss behaviors intact.
- The standalone updater now uses the same visual language as the main app and no longer assumes Windows `.exe` output when saving Linux `.deb`, AppImage, or tarball updates.
- Linux port groundwork now uses XDG-style config paths for app and updater settings instead of assuming `%LOCALAPPDATA%`.
- Backend install guidance now chooses platform-appropriate commands, including Linux package-manager suggestions where supported.
- Backend detection now checks common Linux binary locations for FFmpeg, Pandoc, LibreOffice, 7-Zip, and ImageMagick.
- Backend detection/install guidance now also includes `Aria2` for torrent download workflows.
- `Torrents` now lives under the dedicated `Aria2` workspace category instead of `Misc`.
- Linux build packaging now creates a release tarball named `FormatFoundry_linux_<arch>.tar.gz`.
- Linux build packaging now also creates a Debian package named `format-foundry_<version>_<deb-arch>.deb` for lower-friction installs on Debian-family systems.
- Linux build packaging now also creates `FormatFoundry_linux_<arch>.AppImage` so Ubuntu users can run the app without unpacking the source tree or the raw PyInstaller bundle.
- Updater release-asset selection now prefers Linux `.deb` assets on Debian-family systems, then `.AppImage` or `.tar.gz`, instead of selecting Windows `.exe` downloads.
- GitHub Actions now includes a Linux build/release workflow that can upload Linux tarball assets to tagged releases.
- GitHub Actions Linux builds now validate the generated Debian package layout, smoke-test the AppImage, and upload `.deb` and `.AppImage` assets alongside the tarball on tagged releases.
- Linux singleton lock files now use user-scoped XDG runtime/cache paths instead of a shared `/tmp` fallback path, reducing false “already running” conflicts and silent startup failures.
- Linux packaged windows now have PNG icon fallback wiring, and packaged update-manifest discovery now also checks bundled resources so self-contained Linux builds do not depend on the source tree.
- Linux builds now show an explicit in-app fallback message when drag-and-drop is unavailable, directing users to the existing Add Files / Add Folder controls.
- App and updater entrypoints now expose `--version` and `--smoke-test` CLI modes so Linux CI can validate the frozen binaries headlessly after build.
- The `Torrents` tab now shows a persistent safety disclaimer warning users to only download trusted content and clarifying that the app does not accept responsibility for damage caused by torrent sources or downloaded data.
- Version surfaces are now aligned to the coordinated `1.8.5` release target across the app, updater, installer metadata, manifest example, and public docs.
- Startup loading now minimizes itself if the splash loses focus; fullscreen launches restore automatically when loading finishes, while windowed launches stay minimized and flash the taskbar instead of stealing focus.
- Windowed drag strips now derive their top-bar color from the dominant color in the current Windows wallpaper, so the custom title area matches the desktop more closely.
- `build_linux.sh` now self-bootstraps a repo-local virtual environment on Ubuntu/Debian, reuses an already active venv when present, and fails fast with the exact prerequisite install command instead of falling into PEP 668 system-pip errors.
- Windows installer builds now add a Start-menu uninstall shortcut so installed copies have a standard OS-level removal entry in addition to the in-app uninstall action.

## [0.7.3] - 2026-04-05

### Fixed
- `PDF / Documents` now routes image and camera-raw inputs to image-to-PDF conversion instead of sending them through office/document backends that can hang or stall on those files.
- Windows command-line backend processes now run hidden across the app and updater instead of spawning visible console windows.

## [0.7.2] - 2026-03-27

### Added
- Image conversion compatibility now also includes JPEG XL output plus common camera-raw inputs through the `ImageMagick` backend.

### Changed
- Convert and Images workflows now accept camera-raw inputs such as DNG, CR2/CR3, NEF, ARW, RAF, ORF, RW2, and PEF, routing them through ImageMagick when Pillow is not the right engine.
- `0.7.2` is now the active app, updater, installer, README, and update-manifest version.

## [0.7.1] - 2026-03-25

### Added
- Image conversion compatibility now includes HEIC, HEIF, and AVIF through the `pillow-heif` Pillow plugin.
- `pillow-heif` is now part of the app dependency set and release build, so modern HEIF-family image support ships with the current package set.

### Changed
- Image pipeline output choices now surface HEIC/HEIF/AVIF where that plugin is available.
- JPEG export still flattens alpha, while alpha-capable outputs such as WEBP, HEIC/HEIF, and AVIF no longer take the same forced RGB path.
- `0.7.1` is now the active app, updater, installer, README, and update-manifest version.

## [0.7] - 2026-03-23

### Added
- Advanced `Images`, `Audio`, and `Video` workspace modules are finalized as first-class tabs instead of roadmap placeholders.
- Tooltip-toggle coverage now extends beyond Convert/Compress into Storage Analyzer, Duplicate Finder, Backends / Links, and backend status affordances in the shell.
- Storage Analyzer now includes categorized workspace placement, visible numeric progress, and a pie-chart view with tabbed comparisons for top-level items, largest files, and largest folders.

### Changed
- Workspace categorization is finalized under `Conversion`, `Advanced`, and `Misc`, with `Subtitles` now placed under `Misc`.
- Main shell layout was tightened for readability: compact header, reduced action-panel height, simplified top controls, and backend status condensed into a corner entry instead of a full-width shell panel.
- Window/help controls were moved into Settings so the top shell stays focused on core workspace actions.
- Startup window flow was cleaned up to avoid the pre-splash flash before the loading popup.
- Advanced media option labels and helper text are clearer, including plain-language guidance for video CRF, video presets, audio bitrate, and ZIP compression level.
- Drag-and-drop intake remains active across workflow tabs while the Extract workflow now rejects archive misuse cleanly instead of crashing.
- `0.7` is now the active app, updater, installer, README, and update-manifest version.

### Fixed
- Image conversion exports now map JPEG and TIFF format names correctly in the Convert workflow instead of passing unsupported Pillow format identifiers.

### Archive
- `0.6.5`, `0.6.2`, `0.6`, `0.5`, and the imported legacy `0.4.x` line remain preserved under the external archive root.

## [0.6.5] - 2026-03-22

### Added
- Accessibility settings for:
  - high contrast mode
  - interface scale presets
  - reduced-motion startup behavior
- Advanced `Images` tab with batch resize/export/sharpen controls.
- Advanced `Audio` tab with format conversion, sample-rate conversion, channel selection, loudness normalization, and silence trimming controls.
- Advanced `Video` tab with remux, trim, stream-prep presets, and thumbnail-sheet workflows.
- Legacy `0.4.x` release archives imported into the canonical repo archive from the earlier `Universal File Utility Suite` source tree.
- Canonical archive import script: `tools/import_legacy_release_archives.ps1`.
- Canonical archive index: `archive/ARCHIVE_INDEX.md`.

### Changed
- Theme and widget styling now scale with the configured interface size instead of assuming a fixed 100% layout.
- Tooltip text now follows the app font scaling for better readability.
- Treeviews, buttons, tab spacing, badges, and other shell controls now use scaled sizing and spacing for better visibility on larger displays.
- Startup splash now respects reduced-motion preference and skips animation when that mode is enabled.
- Storage Analyzer chart labels and splash content now scale correctly with the selected interface size.
- Presets / Batch Jobs now recognize `Images`, `Audio`, and `Video` as first-class batchable modules.
- Historical snapshots and imported legacy archives now default to an external archive root outside the Git repo.
- Workspace navigation now groups modules into `Conversion`, `Advanced`, and `Misc` tabs beneath the main `Workspace` tab.

### Archive
- `0.6.2` history remains preserved under the external archive root in `history/v0.6.2`.
- Imported legacy versions are now preserved under the external archive root in `legacy_universal_file_utility_suite`.

## [0.6.2] - 2026-03-22

### Added
- Updater now supports GitHub repo update checks (repo URL input), with detection flow:
  - latest GitHub Release metadata (preferred)
  - repo manifest fallback (`update_manifest.json` / `update_manifest.example.json`)
  - latest tag fallback
- Updater now persists source and output folder in updater settings.
- Product rename to **Format Foundry** across app UI, updater UI, installer metadata, and build artifacts.
- New artifact names:
  - `FormatFoundry.exe`
  - `FormatFoundry_Updater.exe`
  - `FormatFoundry_Setup.exe`
- Backward-compatible settings resolution for existing `%LOCALAPPDATA%\UniversalConversionHubHCB` and `%LOCALAPPDATA%\UniversalFileUtilitySuite` users.
- Linux build script scaffold: `build_linux.sh`.
- Settings toggle for hover tooltips, with Convert/Compress helper text able to switch between inline guidance and hover-only explanations.
- Hover guidance extended into Storage Analyzer, Duplicate Finder, and Backends / Links controls.

### Changed
- Updater default source now points to the project GitHub repository.
- Updater "Open Download Link" now opens release page fallback when no direct asset URL is available.
- Single-instance control now has POSIX lock-file fallback for Linux/non-Windows runs.
- Dark mode readability improved with higher-contrast text, stronger typography, and broader widget theming coverage.
- Historical snapshot artifact capture now follows the renamed `FormatFoundry*` outputs while retaining legacy fallback support for older snapshots.
- Release cleanup and installer mutex handling now remove or recognize both prior `HCB` artifacts and older `UniversalFileUtilitySuite` artifacts during builds and upgrades.
- Repository line-ending policy is now explicit by file type to reduce noisy diffs across Windows and cross-platform scripts.
- Canonical build config filenames now match the shipped product name, and `build_windows.bat` now delegates to the maintained release pipeline.
- Main shell layout reworked for clearer hierarchy: grouped action panels, cleaner header/session card, and a less cluttered workspace surface.
- Storage Analyzer layout reworked around chart-first presentation with dedicated analysis/progress cards and a cleaner split between visualization and table data.
- Extract tab now reroutes dropped archive files to the Archives workflow instead of treating them like media inputs.
- Startup regression fixed where Compress tab button wiring referenced Extract-only helpers and crashed app initialization.
- Backend corner tab now participates in the hover tooltip system for quick backend status guidance.
- Storage Analyzer and Backends / Links now hide their inline helper text when hover-tooltips mode is enabled, while keeping interaction hints available on hover.

### Removed
- Obsolete `UniversalFileConverterHub` prototype build config and source entrypoint from the canonical repo. Historical snapshots remain the fallback for that legacy branch.

## [0.5.0] - 2026-03-21

### Added
- Modular desktop suite layout with dedicated workflow tabs:
  - Convert, Compress, Extract, Metadata
  - PDF / Documents, Images, Audio, Video, Archives
  - Rename / Organize, Duplicate Finder, Storage Analyzer
  - Checksums / Integrity, Subtitles, Presets / Batch Jobs
- First-run setup wizard for initial configuration.
- Standalone updater executable (now shipped as `FormatFoundry_Updater.exe`; the legacy name existed earlier in the 0.5 cycle).
- Installer build output plus stable `release_bins` staging folder for app + updater + setup binaries.
- Custom app icon and branded startup logo animation.
- Dark mode toggle, fullscreen toggle, and borderless/window-mode controls.
- Dedicated top-level tabs for:
  - Workspace
  - Suite Plan
  - Backends / Links
  - Activity Log
- Backend links panel with interactive behavior:
  - Detected backend entry opens local file location
  - Missing backend entry opens install/download link
- Backend install assistant prompt on startup for optional tools.
- Backend hover/tool-tip details for missing dependency guidance.
- Output conflict flow before writes with options to:
  - Replace
  - Rename
  - Change output location
  - Cancel
- Help integration for in-app How-To/README content.
- User settings page for performance/security/runtime defaults.
- Update security options in updater:
  - HTTPS requirements
  - SHA256 enforcement
  - external link confirmation
  - accept-all security option

### Changed
- UI restyled from bare-bones prototype to production-style layout with clearer tab/readability behavior.
- Queue behavior updated to clear completed items after processing.
- Conversion target-format dropdown now constrained to valid outputs for the active source type.
- Queue now enforces a single source file type at a time (prevents mixed-type conversion queue mistakes).
- Backend row path rendering shortened/truncated for readability with full-path access on interaction.
- Startup animation duration/pace tuned (longer/slower option support).
- Main app window default open behavior centered on screen.
- README and HOW-TO documentation combined into a single maintained source.
- Build/release flow updated to keep current deliverables in primary folders and historical snapshots in archive folders.

### Fixed
- Launch crash: unhandled exception (`expected integer but got "UI"`).
- Backend detection regressions (including 7-Zip detection mismatch and path-link breakages after UI updates).
- Hidden/off-screen activity log panel issue by moving log into its own top tab.
- Conversion percent/value visibility issues in settings controls.
- Progress indicator behavior where the bar appeared hollow/empty and jumped to 100%.
- Update popup visibility flow so prompts can hide main app while awaiting confirmation.
- Updater/app multi-instance conflicts and duplicate warning window behavior.
- Startup sequencing bugs causing too many windows or overlapping startup/update dialogs.
- Startup/open-mode prompt flow so the main app is not shown prematurely.

### Security
- Added/expanded controls for:
  - requiring HTTPS for update manifest URL
  - requiring HTTPS for update download URL
  - requiring SHA256 checksum validation
  - confirming external link opens
- Added single-instance protections:
  - app single-instance runtime control
  - updater single-instance runtime control
- Installer protections to reduce duplicate installs and improve upgrade behavior:
  - reuse/replace old install path during upgrade
  - avoid side-by-side duplicate installs by default
  - enforce close-running-instance behavior through installer mutex settings

### Build / Release / Archive
- EXE, updater EXE, and installer generation unified under `build_suite_release.bat`.
- Added automated pre-build and post-build historical snapshot creation.
- Added commit-time snapshot automation support (`.githooks/post-commit` + tools scripts).
- Added archive history structure under:
  - external archive root `history/v0.5/<timestamp>_<reason>/`
- Added release smoke-test workflow for generated binaries.

### Documentation
- Added/expanded in-depth user documentation for:
  - installation
  - startup/setup
  - backend usage
  - update manifest setup
  - build and release usage
  - troubleshooting and performance tuning
- Consolidated duplicate docs into canonical `README.md`.

### Internal Snapshot Trail (v0.5 Rapid Revisions)
- `2026-03-21 18:03:24` - `duplicate-finder-progress-cancel`
- `2026-03-21 18:06:58` - `startup-splash-block-center-window`
- `2026-03-21 18:11:23` - `updater-mutex-and-hidden-update-popup`
- `2026-03-21 18:13:09` - `update-popup-ok-hidden-main-and-updater-lock-fix`
- `2026-03-21 18:17:56` - `single-window-startup-sequence`
- `2026-03-21 18:22:23` - `startup-sequence-and-updater-single-window`
- `2026-03-21 18:29:14` - `startup-popup-wording-install-updates-open-normally`
- `2026-03-21 18:45:39` - latest release build snapshot (includes splash-before-open-mode flow refinement)

## [0.4.10] - 2026-03-20

### Legacy Milestone (Pre-v0.5 Refactor)
- Final `0.4.x` binary before major `0.5` suite hardening.
- Included early modular app executable and setup executable outputs.
- Served as migration point for:
  - archive/release structure cleanup
  - version bump to `0.5`
  - automation and snapshot policy introduction

## [0.4.9] - 2026-03-20
## [0.4.8] - 2026-03-20
## [0.4.7] - 2026-03-20
## [0.4.6] - 2026-03-20
## [0.4.5] - 2026-03-20
## [0.4.4] - 2026-03-20
## [0.4.3] - 2026-03-20

### Legacy Patch Line Notes
- Rapid binary iteration cycle in Downloads workspace while core UI/packaging foundations were being established.
- Artifacts from this stage were later archived and superseded by the canonical `v0.5` source/build process in:
  - `C:\Users\Pugma\Documents\Universal File Utility Suite Output\Universal-File-Conversion`


