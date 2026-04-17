# Universal Conversion Hub (UCH)

Universal Conversion Hub is a cross-platform desktop toolkit for conversion, compression, extraction, media prep, downloads, archives, storage analysis, and repeatable batch workflows.

Canonical release target: `1.8.5`

## Install

[![Windows installer](https://img.shields.io/badge/Windows-Download%20Installer-19786B?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/Pugmaster04/Universal-File-Conversion/releases/latest/download/UniversalConversionHub_UCH_Setup.exe)
[![Ubuntu or Debian package](https://img.shields.io/badge/Ubuntu%20%2F%20Debian-Download%20.deb-19786B?style=for-the-badge&logo=ubuntu&logoColor=white)](https://github.com/Pugmaster04/Universal-File-Conversion/releases/latest/download/universal-conversion-hub-uch_latest_amd64.deb)

If you want the manual artifact list instead of the direct installer buttons, use the [latest release page](https://github.com/Pugmaster04/Universal-File-Conversion/releases/latest).

### Windows

1. Download `UniversalConversionHub_UCH_Setup.exe`.
2. Run the installer.
3. Launch `Universal Conversion Hub (UCH)` from Start or Desktop.

Uninstall:
- `File -> Uninstall...`
- `Settings -> Uninstall App`
- `Start -> Uninstall Universal Conversion Hub (UCH)`
- Windows `Apps & Features`

### Ubuntu 24.04 / Debian

Use the packaged app. Normal Linux installs do not require the source folder after installation.

Recommended `.deb` install:

```bash
sudo apt install ./universal-conversion-hub-uch_latest_amd64.deb
```

Launch:

```bash
universal-conversion-hub-uch
```

Portable AppImage fallback:

```bash
chmod +x UniversalConversionHub_UCH_linux_latest_x86_64.AppImage
./UniversalConversionHub_UCH_linux_latest_x86_64.AppImage
```

Uninstall:
- `File -> Uninstall...`
- `Settings -> Uninstall App`
- `sudo apt remove universal-conversion-hub-uch`

## What It Covers

- Convert
- Compress
- Extract
- PDF / Documents
- Images, Audio, and Video workflows
- Archives
- Rename / Organize
- Duplicate Finder
- Storage Analyzer
- Checksums / Integrity
- Subtitles
- Aria2 downloads and torrents
- Presets / Batch Jobs

## Optional Backends

The app can run without every backend, but wider format coverage improves when these are installed:

- FFmpeg + FFprobe
- Pandoc
- LibreOffice
- 7-Zip
- ImageMagick
- Aria2

Use the in-app `Backends / Links` tab to see what is detected and open the official install sources.

## Need More Detail?

- Full guide: [docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- Release notes: [CHANGELOG.md](CHANGELOG.md)
- Archive map: [archive/ARCHIVE_INDEX.md](archive/ARCHIVE_INDEX.md)

## From Source

Run from source:

```powershell
python modular_file_utility_suite.py
```

Windows build:

```powershell
build_suite_release.bat
```

Linux build:

```bash
chmod +x build_linux.sh
./build_linux.sh
```

`build_linux.sh` is for contributor/source builds. On Ubuntu/Debian it bootstraps a repo-local `.venv` automatically instead of expecting a pre-activated environment.
