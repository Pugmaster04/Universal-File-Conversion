UNIVERSAL FILE CONVERTER HUB

What this package includes
- universal_converter_hub.py
- requirements.txt
- build_windows.bat
- README_build.txt
- THIRD_PARTY_NOTICES.txt

What this build is trying to do
This is a broader "conversion hub" rather than a fake every-format converter.
It combines built-in Python converters with optional external tools.
The app detects what is installed on the Windows machine and only enables the output choices that have a real backend behind them.

Built-in Python backends in this package
- Pillow for common raster image conversion
- imageio-ffmpeg for audio/video conversion through FFmpeg
- PyYAML + xmltodict + tomli-w for structured text/data conversion
- py7zr + Python's zip/tar libraries for archive conversion

Optional external tools the app can use if they are installed on the Windows PC
- ImageMagick: rare image formats and extra raster conversions
- Pandoc: text/markup document conversions
- LibreOffice: office document conversions and many PDF exports from office docs
- Inkscape: vector/page graphics conversion
- calibre (ebook-convert): ebook conversions
- 7-Zip: extra archive input formats like RAR/CAB/ISO/WIM

Main tabs and expanded format coverage
1. Images
   Built-in outputs: PNG, JPG, WEBP, BMP, GIF, TIFF, ICO, PPM
   Extra outputs when ImageMagick is installed: PBM, PGM, PNM, PCX, TGA, XBM, XPM, JP2, JXL, AVIF, HEIC, MIFF
   Extra image inputs also become more realistic with ImageMagick available.

2. Audio
   Inputs: many audio formats plus video files for audio extraction
   Outputs: MP3, WAV, FLAC, AAC, M4A, OGG, OPUS, AIFF, AC3, AU, CAF, WMA, MP2

3. Video
   Inputs: MP4, MOV, MKV, AVI, WEBM, M4V, MTS, M2TS, TS, OGV, FLV, 3GP, WMV, ASF, VOB
   Outputs: MP4, MKV, MOV, AVI, WEBM, OGV, TS, M2TS, FLV

4. Data
   Inputs/outputs: JSON, NDJSON, YAML, CSV, TSV, TOML, INI, PROPERTIES, XML

5. Documents
   Pandoc-oriented text/markup conversions: MD, HTML, DOCX, ODT, EPUB, RST, TEX, RTF, TXT
   LibreOffice-oriented office conversions: PDF, DOCX, ODT, RTF, TXT, HTML, XLSX, ODS, CSV, PPTX, ODP

6. Vector
   Inputs: SVG, SVGZ, PDF, EPS, PS, AI
   Outputs: PNG, PDF, EPS, PS, SVG, JPG, WEBP, TIFF

7. Ebooks
   Inputs include many ebook formats such as EPUB, MOBI, AZW3, FB2, CHM, DJVU, DOCX, ODT, PDF, RTF, TXT and more
   Outputs: EPUB, AZW3, MOBI, FB2, DOCX, ODT, PDF, RTF, TXT, HTMLZ

8. Archives
   Built-in: ZIP, TAR, TAR.GZ, TAR.BZ2, TAR.XZ, 7Z
   Extra input-only formats with 7-Zip installed: RAR, CAB, ISO, WIM, ARJ, LZH

Important limits
- This is still not literally every file format in existence.
- It does not promise perfect fidelity for proprietary or highly specialized formats.
- Some conversions are container changes plus re-encoding, not lossless transformations.
- Document and ebook conversions may have layout differences depending on source complexity.
- DRM-protected ebooks are outside scope.
- For archive conversions, the app extracts and repacks the archive.

How the restrictions work
- If a backend is not detected on the machine, that tab exposes fewer output choices.
- The app will still reject impossible conversion pairs instead of pretending they work.
- The top of the app shows which backends are actually available on that PC.

How to build the EXE on Windows 11
1. Install Python 3.13 64-bit.
2. Extract this zip.
3. Double-click build_windows.bat
4. Find the finished EXE in:
   dist\UniversalFileConverterHub.exe

How to run without building
Open Command Prompt in this folder and run:
py universal_converter_hub.py

Suggested optional installs for broader coverage
- ImageMagick
- Pandoc
- LibreOffice
- Inkscape
- calibre
- 7-Zip

Good next upgrades
- drag-and-drop queueing
- overwrite/skip/auto-number options
- metadata preservation options
- hardware-accelerated FFmpeg presets
- a plugin screen that lets you browse every backend-supported format pair dynamically
