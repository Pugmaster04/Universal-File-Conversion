import csv
import glob
import hashlib
import json
import math
import os
import queue
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import END, SINGLE, BooleanVar, IntVar, StringVar, filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

try:
    from PIL import Image, UnidentifiedImageError
except Exception:
    Image = None
    UnidentifiedImageError = Exception

try:
    import yaml
except Exception:
    yaml = None

try:
    import imageio_ffmpeg
except Exception:
    imageio_ffmpeg = None


APP_TITLE = "Universal File Utility Suite - Modular Starter"
APP_SLUG = "UniversalFileUtilitySuite"
APP_VERSION = "0.4.10"
DEFAULT_UPDATE_MANIFEST_URL = ""

IMAGE_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
    ".ico",
}

AUDIO_EXTS = {
    ".mp3",
    ".wav",
    ".flac",
    ".ogg",
    ".opus",
    ".m4a",
    ".aac",
    ".aiff",
    ".wma",
}

VIDEO_EXTS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".m4v",
    ".flv",
    ".wmv",
    ".ts",
    ".m2ts",
}

MEDIA_EXTS = AUDIO_EXTS | VIDEO_EXTS

DATA_EXTS = {
    ".json",
    ".yaml",
    ".yml",
    ".csv",
    ".tsv",
}

TEXT_EXTS = {
    ".txt",
    ".md",
    ".markdown",
    ".html",
    ".htm",
    ".rst",
    ".ini",
    ".xml",
    ".toml",
}

SUBTITLE_EXTS = {
    ".srt",
    ".vtt",
    ".ass",
    ".ssa",
}

IMAGE_FORMATS = ["png", "jpg", "webp", "bmp", "gif", "tiff", "ico"]
MEDIA_FORMATS = ["mp4", "mkv", "mov", "webm", "mp3", "wav", "flac", "ogg", "m4a"]
DATA_FORMATS = ["json", "yaml", "csv", "tsv"]
DOC_FORMATS = ["pdf", "docx", "odt", "html", "md", "txt", "epub", "rtf"]
ARCHIVE_FORMATS = ["zip", "tar", "tar.gz", "tar.bz2", "tar.xz"]

BACKEND_LINKS: dict[str, dict[str, str]] = {
    "FFmpeg": {
        "homepage": "https://ffmpeg.org/",
        "docs": "https://ffmpeg.org/documentation.html",
        "download": "https://www.gyan.dev/ffmpeg/builds/",
        "install_cmd": "winget install --id Gyan.FFmpeg -e",
    },
    "FFprobe": {
        "homepage": "https://ffmpeg.org/ffprobe.html",
        "docs": "https://ffmpeg.org/ffprobe.html",
        "download": "https://www.gyan.dev/ffmpeg/builds/",
        "install_cmd": "winget install --id Gyan.FFmpeg -e",
    },
    "Pandoc": {
        "homepage": "https://pandoc.org/",
        "docs": "https://pandoc.org/MANUAL.html",
        "download": "https://pandoc.org/installing.html",
        "install_cmd": "winget install --id JohnMacFarlane.Pandoc -e",
    },
    "LibreOffice": {
        "homepage": "https://www.libreoffice.org/",
        "docs": "https://help.libreoffice.org/latest/en-US/text/shared/guide/start_center.html",
        "download": "https://www.libreoffice.org/download/download-libreoffice/",
        "install_cmd": "winget install --id TheDocumentFoundation.LibreOffice -e",
    },
    "7-Zip": {
        "homepage": "https://www.7-zip.org/",
        "docs": "https://7-zip.org/7z.html",
        "download": "https://www.7-zip.org/download.html",
        "install_cmd": "winget install --id 7zip.7zip -e",
    },
    "ImageMagick": {
        "homepage": "https://imagemagick.org/",
        "docs": "https://imagemagick.org/script/command-line-tools.php",
        "download": "https://imagemagick.org/script/download.php",
        "install_cmd": "winget install --id ImageMagick.ImageMagick -e",
    },
}

BACKEND_DESCRIPTIONS: dict[str, str] = {
    "FFmpeg": "Core media engine for video/audio convert, compress, and extract workflows.",
    "FFprobe": "Media inspection tool used for stream/format metadata readout.",
    "Pandoc": "Document conversion backend for formats like Markdown, DOCX, HTML, and PDF.",
    "LibreOffice": "Fallback document conversion engine for office file formats.",
    "7-Zip": "Archive utility backend for broader archive format support.",
    "ImageMagick": "Image processing backend for advanced transform and format workflows.",
}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def quote_cmd(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def human_size(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.2f} {unit}" if unit != "B" else f"{int(amount)} {unit}"
        amount /= 1024
    return f"{value} B"


def version_tuple(value: str) -> tuple[int, ...]:
    parts = re.split(r"[^0-9]+", value.strip())
    return tuple(int(part) for part in parts if part.isdigit())


def is_version_newer(candidate: str, current: str) -> bool:
    c = version_tuple(candidate)
    k = version_tuple(current)
    if not c:
        return False
    width = max(len(c), len(k))
    c = c + (0,) * (width - len(c))
    k = k + (0,) * (width - len(k))
    return c > k


def hash_file(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_structured(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".json":
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    if suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML is not installed; cannot read YAML.")
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    if suffix in {".csv", ".tsv"}:
        delimiter = "," if suffix == ".csv" else "\t"
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            rows = list(reader)
        return rows
    raise ValueError(f"Unsupported data input format: {suffix}")


def write_structured(data: Any, path: Path, fmt: str) -> None:
    fmt = fmt.lower()
    if fmt == "json":
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
        return
    if fmt == "yaml":
        if yaml is None:
            raise RuntimeError("PyYAML is not installed; cannot write YAML.")
        with path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
        return
    if fmt in {"csv", "tsv"}:
        delimiter = "," if fmt == "csv" else "\t"
        with path.open("w", encoding="utf-8", newline="") as handle:
            if isinstance(data, list) and data and isinstance(data[0], dict):
                fieldnames = list({key for row in data for key in row.keys()})
                writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=delimiter)
                writer.writeheader()
                for row in data:
                    writer.writerow(row)
            elif isinstance(data, dict):
                writer = csv.writer(handle, delimiter=delimiter)
                writer.writerow(["key", "value"])
                for key, value in data.items():
                    writer.writerow([key, value])
            elif isinstance(data, list):
                writer = csv.writer(handle, delimiter=delimiter)
                writer.writerow(["value"])
                for value in data:
                    writer.writerow([value])
            else:
                writer = csv.writer(handle, delimiter=delimiter)
                writer.writerow(["value"])
                writer.writerow([data])
        return
    raise ValueError(f"Unsupported data output format: {fmt}")


def srt_to_vtt(text: str) -> str:
    output = ["WEBVTT", ""]
    time_pattern = re.compile(r"^(\d{2}:\d{2}:\d{2}),(\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}),(\d{3})$")
    for line in text.splitlines():
        line = line.rstrip("\n")
        match = time_pattern.match(line.strip())
        if match:
            start = f"{match.group(1)}.{match.group(2)}"
            end = f"{match.group(3)}.{match.group(4)}"
            output.append(f"{start} --> {end}")
            continue
        if line.strip().isdigit():
            continue
        output.append(line)
    return "\n".join(output).strip() + "\n"


def vtt_to_srt(text: str) -> str:
    cleaned = []
    index = 1
    block: list[str] = []
    time_pattern = re.compile(r"^(\d{2}:\d{2}:\d{2})\.(\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2})\.(\d{3}).*$")
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if line.strip().upper() == "WEBVTT":
            continue
        if not line.strip():
            if block:
                cleaned.append(str(index))
                cleaned.extend(block)
                cleaned.append("")
                index += 1
                block = []
            continue
        match = time_pattern.match(line.strip())
        if match:
            start = f"{match.group(1)},{match.group(2)}"
            end = f"{match.group(3)},{match.group(4)}"
            block.append(f"{start} --> {end}")
            continue
        block.append(line)

    if block:
        cleaned.append(str(index))
        cleaned.extend(block)
        cleaned.append("")

    return "\n".join(cleaned).strip() + "\n"


class HoverCard:
    def __init__(self, widget: tk.Widget, text_provider, dark_mode_provider=None, delay_ms: int = 320):
        self.widget = widget
        self.text_provider = text_provider
        self.dark_mode_provider = dark_mode_provider
        self.delay_ms = delay_ms
        self.tip_window: tk.Toplevel | None = None
        self.after_id: str | None = None
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")
        widget.bind("<Motion>", self._on_motion, add="+")

    def _on_enter(self, _event=None) -> None:
        self._schedule()

    def _on_leave(self, _event=None) -> None:
        self._cancel()
        self._hide()

    def _on_motion(self, _event=None) -> None:
        if self.tip_window and self.tip_window.winfo_exists():
            x = self.widget.winfo_pointerx() + 14
            y = self.widget.winfo_pointery() + 16
            self.tip_window.geometry(f"+{x}+{y}")

    def _schedule(self) -> None:
        self._cancel()
        self.after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel(self) -> None:
        if self.after_id:
            try:
                self.widget.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

    def _show(self) -> None:
        self.after_id = None
        if self.tip_window and self.tip_window.winfo_exists():
            return
        text = str(self.text_provider() or "").strip()
        if not text:
            return
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.overrideredirect(True)
        self.tip_window.attributes("-topmost", True)

        dark_mode = bool(self.dark_mode_provider()) if self.dark_mode_provider else False
        bg = "#1B212A" if dark_mode else "#FFFDF4"
        fg = "#E8F1FF" if dark_mode else "#1A3555"
        border = "#3B4553" if dark_mode else "#D4DCE8"

        frame = tk.Frame(self.tip_window, bg=bg, bd=1, relief="solid", highlightthickness=1, highlightbackground=border)
        frame.pack(fill="both", expand=True)
        label = tk.Label(
            frame,
            text=text,
            bg=bg,
            fg=fg,
            justify="left",
            anchor="w",
            wraplength=470,
            padx=10,
            pady=8,
            font=("Segoe UI", 9),
        )
        label.pack(fill="both", expand=True)

        x = self.widget.winfo_pointerx() + 14
        y = self.widget.winfo_pointery() + 16
        self.tip_window.geometry(f"+{x}+{y}")

    def _hide(self) -> None:
        if self.tip_window and self.tip_window.winfo_exists():
            self.tip_window.destroy()
        self.tip_window = None


@dataclass
class BackendRegistry:
    ffmpeg: str | None
    ffprobe: str | None
    pandoc: str | None
    libreoffice: str | None
    sevenzip: str | None
    imagemagick: str | None

    @classmethod
    def detect(cls) -> "BackendRegistry":
        def existing(path_str: str | None) -> str | None:
            if not path_str:
                return None
            try:
                path_obj = Path(path_str)
                if path_obj.exists():
                    return str(path_obj)
            except Exception:
                return None
            return None

        def first_existing(candidates: list[Path]) -> str | None:
            for candidate in candidates:
                if str(candidate):
                    try:
                        if candidate.exists():
                            return str(candidate)
                    except Exception:
                        continue
            return None

        def first_glob(base_patterns: list[str]) -> str | None:
            for pattern in base_patterns:
                try:
                    matches = sorted(glob.glob(pattern, recursive=True))
                except Exception:
                    matches = []
                for match in matches:
                    match_path = Path(match)
                    if match_path.exists():
                        return str(match_path)
            return None

        imageio_ffmpeg_path = None
        if imageio_ffmpeg is not None:
            try:
                imageio_ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                imageio_ffmpeg_path = None

        ffmpeg_path = existing(shutil.which("ffmpeg") or shutil.which("ffmpeg.exe"))
        if not ffmpeg_path:
            ffmpeg_path = first_existing(
                [
                    Path(os.environ.get("ProgramFiles", "")) / "ffmpeg" / "bin" / "ffmpeg.exe",
                    Path(os.environ.get("ProgramFiles(x86)", "")) / "ffmpeg" / "bin" / "ffmpeg.exe",
                    Path(os.environ.get("ProgramW6432", "")) / "ffmpeg" / "bin" / "ffmpeg.exe",
                ]
            )
        if not ffmpeg_path:
            ffmpeg_path = first_glob(
                [
                    str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg_Microsoft.Winget.Source_*" / "**" / "ffmpeg.exe"),
                    str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" / "FFmpeg.*_Microsoft.Winget.Source_*" / "**" / "ffmpeg.exe"),
                ]
            )
        if not ffmpeg_path:
            ffmpeg_path = existing(imageio_ffmpeg_path)

        ffprobe_path = existing(shutil.which("ffprobe") or shutil.which("ffprobe.exe"))
        if not ffprobe_path and ffmpeg_path:
            ffprobe_path = first_existing([Path(ffmpeg_path).with_name("ffprobe.exe"), Path(ffmpeg_path).with_name("ffprobe")])
        if not ffprobe_path:
            ffprobe_path = first_glob(
                [
                    str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg_Microsoft.Winget.Source_*" / "**" / "ffprobe.exe"),
                    str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" / "FFmpeg.*_Microsoft.Winget.Source_*" / "**" / "ffprobe.exe"),
                ]
            )

        pandoc = existing(shutil.which("pandoc") or shutil.which("pandoc.exe"))
        if not pandoc:
            pandoc = first_existing(
                [
                    Path(os.environ.get("ProgramFiles", "")) / "Pandoc" / "pandoc.exe",
                    Path(os.environ.get("ProgramFiles(x86)", "")) / "Pandoc" / "pandoc.exe",
                    Path(os.environ.get("LOCALAPPDATA", "")) / "Pandoc" / "pandoc.exe",
                    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Pandoc" / "pandoc.exe",
                ]
            )
        if not pandoc:
            pandoc = first_glob(
                [
                    str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" / "JohnMacFarlane.Pandoc_Microsoft.Winget.Source_*" / "**" / "pandoc.exe"),
                ]
            )

        libreoffice = existing(shutil.which("soffice") or shutil.which("soffice.exe"))
        if not libreoffice:
            libreoffice = first_existing(
                [
                    Path(os.environ.get("ProgramFiles", "")) / "LibreOffice" / "program" / "soffice.exe",
                    Path(os.environ.get("ProgramFiles(x86)", "")) / "LibreOffice" / "program" / "soffice.exe",
                ]
            )

        sevenzip = existing(shutil.which("7z") or shutil.which("7z.exe"))
        if not sevenzip:
            sevenzip = first_existing(
                [
                    Path(os.environ.get("ProgramFiles", "")) / "7-Zip" / "7z.exe",
                    Path(os.environ.get("ProgramFiles(x86)", "")) / "7-Zip" / "7z.exe",
                    Path(os.environ.get("ProgramW6432", "")) / "7-Zip" / "7z.exe",
                    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "7-Zip" / "7z.exe",
                ]
            )

        imagemagick = existing(shutil.which("magick") or shutil.which("magick.exe"))
        if not imagemagick:
            imagemagick = first_glob(
                [
                    str(Path(os.environ.get("ProgramFiles", "")) / "ImageMagick*" / "magick.exe"),
                    str(Path(os.environ.get("ProgramFiles(x86)", "")) / "ImageMagick*" / "magick.exe"),
                    str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "ImageMagick*" / "magick.exe"),
                    str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" / "ImageMagick.ImageMagick_Microsoft.Winget.Source_*" / "**" / "magick.exe"),
                ]
            )

        return cls(
            ffmpeg=ffmpeg_path,
            ffprobe=ffprobe_path,
            pandoc=pandoc,
            libreoffice=libreoffice,
            sevenzip=sevenzip,
            imagemagick=imagemagick,
        )

    def as_rows(self) -> list[tuple[str, str]]:
        return [
            ("FFmpeg", self.ffmpeg or "Not found"),
            ("FFprobe", self.ffprobe or "Not found"),
            ("Pandoc", self.pandoc or "Not found"),
            ("LibreOffice", self.libreoffice or "Not found"),
            ("7-Zip", self.sevenzip or "Not found"),
            ("ImageMagick", self.imagemagick or "Not found"),
        ]


class TaskEngine:
    def __init__(self, app: "SuiteApp"):
        self.app = app

    def _prepare_output_path(self, target_path: Path, context: str) -> Path:
        resolved = self.app.resolve_output_path(target_path, context=context)
        if resolved is None:
            raise RuntimeError("Operation canceled by user.")
        return resolved

    def convert_file(self, source: Path, output_dir: Path, target_format: str, options: dict[str, Any]) -> Path:
        target_format = target_format.lower()
        ensure_dir(output_dir)
        out_path = output_dir / f"{source.stem}.{target_format}"
        suffix = source.suffix.lower()

        if suffix in IMAGE_EXTS and target_format in IMAGE_FORMATS:
            if Image is None:
                raise RuntimeError("Pillow is not installed; cannot convert image files.")
            out_path = self._prepare_output_path(out_path, f"Converted file for {source.name}")
            quality = int(options.get("image_quality", 92))
            with Image.open(source) as image:
                save_kwargs: dict[str, Any] = {}
                if target_format in {"jpg", "jpeg", "webp"}:
                    if image.mode in {"RGBA", "P"}:
                        image = image.convert("RGB")
                    save_kwargs["quality"] = quality
                    save_kwargs["optimize"] = True
                if target_format == "png":
                    save_kwargs["optimize"] = True
                image.save(out_path, format=target_format.upper(), **save_kwargs)
            return out_path

        if suffix in DATA_EXTS and target_format in DATA_FORMATS:
            out_path = self._prepare_output_path(out_path, f"Converted file for {source.name}")
            data = read_structured(source)
            write_structured(data, out_path, target_format)
            return out_path

        if target_format in MEDIA_FORMATS:
            ffmpeg = self.app.backends.ffmpeg
            if not ffmpeg:
                raise RuntimeError("FFmpeg is required for media conversion and was not detected.")
            out_path = self._prepare_output_path(out_path, f"Converted file for {source.name}")
            cmd = [ffmpeg, "-y", "-i", str(source)]
            if target_format in {"mp3", "wav", "flac", "ogg", "m4a"}:
                bitrate = str(options.get("audio_bitrate", "192k"))
                cmd += ["-vn", "-b:a", bitrate]
            else:
                preset = str(options.get("video_preset", "medium"))
                crf = str(options.get("video_crf", 23))
                cmd += ["-c:v", "libx264", "-preset", preset, "-crf", crf, "-c:a", "aac", "-b:a", "160k"]
            cmd.append(str(out_path))
            self.app.run_process(cmd)
            return out_path

        if suffix in TEXT_EXTS and target_format in {"txt", "md", "html"}:
            out_path = self._prepare_output_path(out_path, f"Converted file for {source.name}")
            content = source.read_text(encoding="utf-8", errors="replace")
            out_path.write_text(content, encoding="utf-8")
            return out_path

        raise RuntimeError(f"Unsupported conversion: {source.suffix} -> .{target_format}")

    def compress_file(self, source: Path, output_dir: Path, mode_key: str, options: dict[str, Any]) -> Path:
        ensure_dir(output_dir)
        suffix = source.suffix.lower()
        if mode_key == "image_quality":
            if suffix not in IMAGE_EXTS:
                raise RuntimeError("Image compression mode requires image files.")
            if Image is None:
                raise RuntimeError("Pillow is not installed; cannot compress image files.")
            quality = int(options.get("quality", 82))
            out_path = output_dir / f"{source.stem}_compressed{source.suffix.lower()}"
            out_path = self._prepare_output_path(out_path, f"Compressed file for {source.name}")
            with Image.open(source) as image:
                save_kwargs: dict[str, Any] = {"optimize": True}
                if suffix in {".jpg", ".jpeg", ".webp"}:
                    save_kwargs["quality"] = quality
                    if image.mode in {"RGBA", "P"}:
                        image = image.convert("RGB")
                if suffix == ".png":
                    png_level = max(0, min(9, 9 - int(quality / 12)))
                    save_kwargs["compress_level"] = png_level
                image.save(out_path, **save_kwargs)
            return out_path

        ffmpeg = self.app.backends.ffmpeg
        if not ffmpeg:
            raise RuntimeError("FFmpeg is required for media compression and was not detected.")

        if mode_key == "video_crf":
            out_path = output_dir / f"{source.stem}_compressed.mp4"
            out_path = self._prepare_output_path(out_path, f"Compressed file for {source.name}")
            crf = str(options.get("crf", 28))
            preset = str(options.get("video_preset", "medium"))
            cmd = [
                ffmpeg,
                "-y",
                "-i",
                str(source),
                "-c:v",
                "libx264",
                "-preset",
                preset,
                "-crf",
                crf,
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                str(out_path),
            ]
            self.app.run_process(cmd)
            return out_path

        if mode_key == "audio_bitrate":
            out_path = output_dir / f"{source.stem}_compressed.mp3"
            out_path = self._prepare_output_path(out_path, f"Compressed file for {source.name}")
            bitrate = str(options.get("audio_bitrate", "128k"))
            cmd = [ffmpeg, "-y", "-i", str(source), "-vn", "-b:a", bitrate, str(out_path)]
            self.app.run_process(cmd)
            return out_path

        raise RuntimeError(f"Unknown compression mode: {mode_key}")

    def create_zip_archive(self, files: list[Path], output_dir: Path, level: int = 6) -> Path:
        ensure_dir(output_dir)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        archive = output_dir / f"compressed_batch_{stamp}.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=level) as bundle:
            for source in files:
                if source.is_file():
                    bundle.write(source, arcname=source.name)
                elif source.is_dir():
                    for candidate in source.rglob("*"):
                        if candidate.is_file():
                            arcname = str(Path(source.name) / candidate.relative_to(source))
                            bundle.write(candidate, arcname=arcname)
        return archive

    def extract_from_media(self, source: Path, output_dir: Path, operation_key: str, options: dict[str, Any]) -> Path:
        ffmpeg = self.app.backends.ffmpeg
        if not ffmpeg:
            raise RuntimeError("FFmpeg is required for extract operations and was not detected.")
        ensure_dir(output_dir)

        if operation_key == "audio_from_video":
            audio_fmt = str(options.get("audio_format", "mp3")).lower()
            out_path = output_dir / f"{source.stem}_audio.{audio_fmt}"
            out_path = self._prepare_output_path(out_path, f"Extracted file for {source.name}")
            cmd = [ffmpeg, "-y", "-i", str(source), "-vn", str(out_path)]
            self.app.run_process(cmd)
            return out_path

        if operation_key == "frames_from_video":
            fps = str(options.get("fps", "1"))
            frame_dir = output_dir / f"{source.stem}_frames"
            ensure_dir(frame_dir)
            pattern = frame_dir / "frame_%05d.png"
            cmd = [ffmpeg, "-y", "-i", str(source), "-vf", f"fps={fps}", str(pattern)]
            self.app.run_process(cmd)
            return frame_dir

        if operation_key == "subtitles_from_video":
            subtitle_index = int(options.get("subtitle_index", 0))
            out_path = output_dir / f"{source.stem}.srt"
            out_path = self._prepare_output_path(out_path, f"Extracted file for {source.name}")
            cmd = [
                ffmpeg,
                "-y",
                "-i",
                str(source),
                "-map",
                f"0:s:{subtitle_index}",
                "-c:s",
                "srt",
                str(out_path),
            ]
            self.app.run_process(cmd)
            return out_path

        if operation_key == "cover_art_from_audio":
            out_path = output_dir / f"{source.stem}_cover.jpg"
            out_path = self._prepare_output_path(out_path, f"Extracted file for {source.name}")
            cmd = [ffmpeg, "-y", "-i", str(source), "-an", "-vcodec", "copy", str(out_path)]
            self.app.run_process(cmd)
            return out_path

        raise RuntimeError(f"Unknown extract operation: {operation_key}")

    def inspect_metadata(self, source: Path) -> dict[str, Any]:
        info: dict[str, Any] = {
            "path": str(source),
            "size_bytes": source.stat().st_size,
            "size_human": human_size(source.stat().st_size),
            "suffix": source.suffix.lower(),
        }

        if self.app.backends.ffprobe and source.suffix.lower() in MEDIA_EXTS:
            cmd = [
                self.app.backends.ffprobe,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(source),
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                info["ffprobe"] = json.loads(result.stdout)
            except Exception as exc:
                info["ffprobe_error"] = str(exc)

        if Image is not None and source.suffix.lower() in IMAGE_EXTS:
            try:
                with Image.open(source) as image:
                    info["image"] = {
                        "mode": image.mode,
                        "width": image.width,
                        "height": image.height,
                        "format": image.format,
                    }
                    exif = image.getexif()
                    if exif:
                        pretty = {}
                        for key, value in exif.items():
                            label = str(key)
                            pretty[label] = str(value)
                        info["exif"] = pretty
            except UnidentifiedImageError:
                info["image_error"] = "File extension looks like image but data is not recognized."
            except Exception as exc:
                info["image_error"] = str(exc)

        return info

    def apply_metadata(self, source: Path, output_dir: Path, key: str, value: str) -> Path:
        ensure_dir(output_dir)
        suffix = source.suffix.lower()
        if self.app.backends.ffmpeg and suffix in MEDIA_EXTS:
            out_path = output_dir / f"{source.stem}_meta{source.suffix.lower()}"
            out_path = self._prepare_output_path(out_path, f"Metadata output for {source.name}")
            cmd = [
                self.app.backends.ffmpeg,
                "-y",
                "-i",
                str(source),
                "-map_metadata",
                "0",
                "-metadata",
                f"{key}={value}",
                "-codec",
                "copy",
                str(out_path),
            ]
            self.app.run_process(cmd)
            return out_path

        sidecar = output_dir / f"{source.name}.metadata.json"
        payload = {"source": str(source), "metadata": {key: value}}
        if sidecar.exists():
            try:
                current = json.loads(sidecar.read_text(encoding="utf-8"))
                if isinstance(current, dict):
                    merged = current.get("metadata", {})
                    if isinstance(merged, dict):
                        merged[key] = value
                        current["metadata"] = merged
                        payload = current
            except Exception:
                pass
        sidecar.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return sidecar

    def convert_document(self, source: Path, output_dir: Path, target_format: str) -> Path:
        ensure_dir(output_dir)
        target_format = target_format.lower()
        out_path = output_dir / f"{source.stem}.{target_format}"
        final_path = self._prepare_output_path(out_path, f"Converted document for {source.name}")

        if self.app.backends.pandoc:
            cmd = [self.app.backends.pandoc, str(source), "-o", str(final_path)]
            self.app.run_process(cmd)
            return final_path

        if self.app.backends.libreoffice:
            cmd = [
                self.app.backends.libreoffice,
                "--headless",
                "--convert-to",
                target_format,
                "--outdir",
                str(final_path.parent),
                str(source),
            ]
            self.app.run_process(cmd)
            produced = final_path.parent / f"{source.stem}.{target_format}"
            if not produced.exists():
                fallback_matches = list(final_path.parent.glob(f"{source.stem}.*"))
                produced = fallback_matches[0] if fallback_matches else None
            if produced and produced != final_path:
                if final_path.exists():
                    final_path = self._prepare_output_path(final_path, f"Converted document for {source.name}")
                ensure_dir(final_path.parent)
                shutil.move(str(produced), str(final_path))
                return final_path
            if produced and produced.exists():
                return produced
            fallback_matches = list(final_path.parent.glob(f"{source.stem}.*"))
            if fallback_matches:
                return fallback_matches[0]

        if source.suffix.lower() in TEXT_EXTS and target_format in {"txt", "md", "html"}:
            content = source.read_text(encoding="utf-8", errors="replace")
            final_path.write_text(content, encoding="utf-8")
            return final_path

        raise RuntimeError(
            "No compatible document backend found. Install Pandoc or LibreOffice for broader document conversion."
        )

    def create_archive(self, inputs: list[Path], out_path: Path, archive_format: str) -> Path:
        archive_format = archive_format.lower()
        out_path = self._prepare_output_path(out_path, "Archive output file")
        ensure_dir(out_path.parent)

        if archive_format == "zip":
            with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                for entry in inputs:
                    if entry.is_file():
                        bundle.write(entry, arcname=entry.name)
                    elif entry.is_dir():
                        for child in entry.rglob("*"):
                            if child.is_file():
                                arcname = str(Path(entry.name) / child.relative_to(entry))
                                bundle.write(child, arcname=arcname)
            return out_path

        mode_lookup = {
            "tar": "w",
            "tar.gz": "w:gz",
            "tar.bz2": "w:bz2",
            "tar.xz": "w:xz",
        }
        if archive_format not in mode_lookup:
            raise RuntimeError(f"Unsupported archive format: {archive_format}")

        with tarfile.open(out_path, mode_lookup[archive_format]) as archive:
            for entry in inputs:
                archive.add(entry, arcname=entry.name)
        return out_path

    def extract_archive(self, archive_path: Path, destination: Path) -> Path:
        ensure_dir(destination)
        suffix = archive_path.suffix.lower()
        lower_name = archive_path.name.lower()
        if suffix == ".zip":
            with zipfile.ZipFile(archive_path, "r") as archive:
                archive.extractall(destination)
            return destination
        if suffix in {".tar", ".gz", ".bz2", ".xz"} or lower_name.endswith((".tar.gz", ".tar.bz2", ".tar.xz")):
            with tarfile.open(archive_path, "r:*") as archive:
                archive.extractall(destination)
            return destination
        shutil.unpack_archive(str(archive_path), str(destination))
        return destination


class SuiteApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1380x920")
        self.root.minsize(1180, 780)
        self.root.protocol("WM_DELETE_WINDOW", self._request_close)

        self.main_thread = threading.current_thread()
        self.ui_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.script_dir = Path(__file__).resolve().parent
        self.resource_dir = Path(getattr(sys, "_MEIPASS", self.script_dir))
        self.runtime_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else self.script_dir
        self.appdata_dir = Path(os.environ.get("LOCALAPPDATA", str(self.runtime_dir))) / APP_SLUG
        ensure_dir(self.appdata_dir)

        self.settings_path = self.appdata_dir / "settings.json"
        self.settings = self._load_settings()
        self._refresh_paths_from_settings()

        self.status_left_var = StringVar(value="Ready.")
        self.status_right_var = StringVar(value="")
        self.dark_mode_var = BooleanVar(value=bool(self.settings.get("dark_mode", False)))
        self.fullscreen_var = BooleanVar(value=bool(self.settings.get("fullscreen", False)))
        self.borderless_max_var = BooleanVar(value=bool(self.settings.get("borderless_maximized", False)))
        self.tabs: dict[str, ttk.Frame] = {}
        self.backend_hover_cards: list[HoverCard] = []
        self._normal_geometry = self.root.geometry()
        self._normal_zoomed = False
        self._window_mode_state = "normal"
        self.root.bind("<F11>", self._on_f11_toggle)
        self.root.bind("<F10>", self._on_f10_toggle_borderless)
        self.root.bind("<Escape>", self._on_escape_exit_fullscreen)

        self.backends = BackendRegistry.detect()
        self.engine = TaskEngine(self)

        if not self.settings.get("first_run_done", False):
            self._run_first_run_setup_wizard()

        self.root.withdraw()
        self._apply_window_icon()
        self._configure_styles()
        self._build_menu()
        self._build_ui()
        if bool(self.fullscreen_var.get()) and bool(self.borderless_max_var.get()):
            self.borderless_max_var.set(False)
        self._apply_window_mode_state()
        self._set_backend_summary_status()
        self.root.after(100, self._poll_ui_queue)
        try:
            self._show_startup_logo_animation()
        except Exception:
            self.root.deiconify()
        if self.settings.get("check_updates_on_startup", True):
            self.root.after(1200, lambda: self._check_updates_in_background(interactive=False))
        self.root.after(1800, self._prompt_install_missing_backends_on_startup)

    def _default_settings(self) -> dict[str, Any]:
        default_output = Path.home() / "Documents" / "Universal File Utility Suite Output"
        return {
            "first_run_done": False,
            "dark_mode": False,
            "fullscreen": False,
            "borderless_maximized": False,
            "output_folder": str(default_output),
            "check_updates_on_startup": True,
            "prompt_backend_install_on_startup": True,
            "update_manifest_url": DEFAULT_UPDATE_MANIFEST_URL,
            "last_update_check": "",
        }

    def _load_settings(self) -> dict[str, Any]:
        defaults = self._default_settings()
        if not self.settings_path.exists():
            return defaults
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return defaults
            merged = dict(defaults)
            merged.update(data)
            return merged
        except Exception:
            return defaults

    def _save_settings(self) -> None:
        ensure_dir(self.settings_path.parent)
        self.settings_path.write_text(json.dumps(self.settings, indent=2, ensure_ascii=False), encoding="utf-8")

    def _refresh_paths_from_settings(self) -> None:
        output_folder = str(self.settings.get("output_folder", "")).strip()
        if output_folder:
            self.default_output_root = Path(output_folder)
        else:
            self.default_output_root = self.runtime_dir / "suite_output"
        ensure_dir(self.default_output_root)

    def _run_first_run_setup_wizard(self) -> None:
        wizard = tk.Toplevel(self.root)
        wizard.title("First Run Setup")
        wizard.geometry("680x460")
        wizard.resizable(False, False)
        wizard.transient(self.root)
        wizard.grab_set()

        output_var = StringVar(value=str(self.default_output_root))
        dark_mode_var = BooleanVar(value=bool(self.settings.get("dark_mode", False)))
        fullscreen_var = BooleanVar(value=bool(self.settings.get("fullscreen", False)))
        borderless_var = BooleanVar(value=bool(self.settings.get("borderless_maximized", False)))
        update_check_var = BooleanVar(value=bool(self.settings.get("check_updates_on_startup", True)))
        backend_prompt_var = BooleanVar(value=bool(self.settings.get("prompt_backend_install_on_startup", True)))
        update_url_var = StringVar(value=str(self.settings.get("update_manifest_url", "")))
        finished = {"done": False}

        outer = ttk.Frame(wizard, padding=14)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Welcome to Universal File Utility Suite", font=("Segoe UI Semibold", 14)).pack(anchor="w")
        ttk.Label(
            outer,
            text="Set your defaults now. You can change them later from File -> Run First-Run Setup Wizard.",
            foreground="#475A72",
            wraplength=590,
        ).pack(anchor="w", pady=(4, 12))

        row1 = ttk.Frame(outer)
        row1.pack(fill="x", pady=(0, 10))
        ttk.Label(row1, text="Default output folder:").pack(side="left")
        ttk.Entry(row1, textvariable=output_var).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(row1, text="Browse", command=lambda: self._browse_into_var(output_var, "Choose default output folder")).pack(side="left")

        row2 = ttk.Frame(outer)
        row2.pack(fill="x", pady=(0, 10))
        ttk.Checkbutton(row2, text="Enable dark mode", variable=dark_mode_var).pack(anchor="w")
        ttk.Checkbutton(row2, text="Start in fullscreen mode", variable=fullscreen_var).pack(anchor="w")
        ttk.Checkbutton(row2, text="Start in borderless maximized mode", variable=borderless_var).pack(anchor="w")
        ttk.Checkbutton(row2, text="Check for updates on startup", variable=update_check_var).pack(anchor="w")
        ttk.Checkbutton(
            row2,
            text="Prompt to install missing backends on startup (recommended)",
            variable=backend_prompt_var,
        ).pack(anchor="w")
        ttk.Button(row2, text="Review Missing Backends Now", command=self._open_backend_install_assistant).pack(anchor="w", pady=(6, 0))

        row3 = ttk.Frame(outer)
        row3.pack(fill="x", pady=(0, 10))
        ttk.Label(row3, text="Update manifest URL (optional):").pack(anchor="w")
        ttk.Entry(row3, textvariable=update_url_var).pack(fill="x", pady=(4, 0))

        ttk.Label(
            outer,
            text='Manifest example: {"latest_version":"0.5.0","download_url":"https://example.com/app.exe","notes":"Release notes"}',
            foreground="#57687F",
            wraplength=590,
            justify="left",
        ).pack(anchor="w", pady=(2, 12))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", side="bottom")

        def finish() -> None:
            self.settings["output_folder"] = output_var.get().strip() or str(self.default_output_root)
            self.settings["dark_mode"] = bool(dark_mode_var.get())
            self.settings["fullscreen"] = bool(fullscreen_var.get())
            self.settings["borderless_maximized"] = bool(borderless_var.get())
            if self.settings["fullscreen"] and self.settings["borderless_maximized"]:
                self.settings["borderless_maximized"] = False
            self.settings["check_updates_on_startup"] = bool(update_check_var.get())
            self.settings["prompt_backend_install_on_startup"] = bool(backend_prompt_var.get())
            self.settings["update_manifest_url"] = update_url_var.get().strip()
            self.settings["first_run_done"] = True
            self._refresh_paths_from_settings()
            self.dark_mode_var.set(bool(self.settings["dark_mode"]))
            self.fullscreen_var.set(bool(self.settings["fullscreen"]))
            self.borderless_max_var.set(bool(self.settings["borderless_maximized"]))
            self._save_settings()
            finished["done"] = True
            wizard.destroy()

        ttk.Button(buttons, text="Use Defaults", command=finish).pack(side="right")
        ttk.Button(buttons, text="Save and Continue", command=finish).pack(side="right", padx=(0, 8))

        wizard.protocol("WM_DELETE_WINDOW", finish)
        self.root.wait_window(wizard)
        if not finished["done"]:
            self.settings["first_run_done"] = True
            self._save_settings()

    def _browse_into_var(self, variable: StringVar, title: str) -> None:
        raw = filedialog.askdirectory(title=title)
        if raw:
            variable.set(raw)

    def _apply_window_icon_to(self, window: tk.Misc) -> None:
        candidates = [
            self.resource_dir / "assets" / "universal_file_utility_suite.ico",
            self.runtime_dir / "assets" / "universal_file_utility_suite.ico",
            self.script_dir / "assets" / "universal_file_utility_suite.ico",
        ]
        for candidate in candidates:
            if candidate.exists():
                try:
                    window.iconbitmap(default=str(candidate))
                    return
                except Exception:
                    continue

    def _apply_window_icon(self) -> None:
        self._apply_window_icon_to(self.root)

    def _configure_styles(self) -> None:
        self.root.option_add("*Font", "{Segoe UI} 10")
        self.style = ttk.Style(self.root)
        themes = set(self.style.theme_names())
        if "clam" in themes:
            self.style.theme_use("clam")

        self.style.configure(".", font=("Segoe UI", 10))
        self.style.configure("App.TButton", padding=(10, 6), font=("Segoe UI Semibold", 9))
        self.style.configure("App.TNotebook", borderwidth=0, tabmargins=(0, 0, 0, 0))
        try:
            self.style.configure("App.TNotebook", tabposition="n")
        except tk.TclError:
            # Some Tk builds do not support tabposition.
            pass
        self.style.configure(
            "App.TNotebook.Tab",
            padding=(16, 11),
            font=("Segoe UI Semibold", 10),
            background="#DCE5F1",
            foreground="#17304F",
            borderwidth=1,
        )
        self.style.configure("TopTabs.TNotebook", borderwidth=0, tabmargins=(0, 0, 0, 0))
        self.style.configure(
            "TopTabs.TNotebook.Tab",
            padding=(14, 8),
            font=("Segoe UI Semibold", 10),
            background="#DCE5F1",
            foreground="#17304F",
            borderwidth=1,
        )
        self._apply_theme(bool(self.dark_mode_var.get()))

    def _theme_palette(self, dark_mode: bool) -> dict[str, str]:
        if dark_mode:
            return {
                "window_bg": "#1E232A",
                "card_bg": "#272D35",
                "card_border": "#3B4450",
                "title_fg": "#F5F8FF",
                "subtitle_fg": "#BAC6D8",
                "meta_fg": "#D3DEEE",
                "status_bg": "#1B2026",
                "status_fg": "#C9D6E8",
                "button_active": "#334055",
                "button_press": "#2B3548",
                "notebook_bg": "#1E232A",
                "tab_bg": "#313A46",
                "tab_fg": "#CAD6E8",
                "tab_sel_bg": "#3D4A5E",
                "tab_sel_fg": "#FFFFFF",
                "tab_active_bg": "#3A4555",
                "tab_active_fg": "#FFFFFF",
                "log_bg": "#12161B",
                "log_fg": "#E6EEF9",
                "log_border": "#3A4350",
                "backend_detected_fg": "#79BFFF",
                "backend_missing_fg": "#FFB178",
            }
        return {
            "window_bg": "#EEF2F8",
            "card_bg": "#FFFFFF",
            "card_border": "#CFD8E6",
            "title_fg": "#0B2440",
            "subtitle_fg": "#405368",
            "meta_fg": "#1A3555",
            "status_bg": "#DCE4EF",
            "status_fg": "#163150",
            "button_active": "#E8EEF8",
            "button_press": "#DDE6F4",
            "notebook_bg": "#EEF2F8",
            "tab_bg": "#DCE5F1",
            "tab_fg": "#17304F",
            "tab_sel_bg": "#FFFFFF",
            "tab_sel_fg": "#0B2440",
            "tab_active_bg": "#E8EEF8",
            "tab_active_fg": "#163150",
            "log_bg": "#F8FAFD",
            "log_fg": "#142840",
            "log_border": "#CFD8E6",
            "backend_detected_fg": "#005A9E",
            "backend_missing_fg": "#B42318",
        }

    def _apply_theme(self, dark_mode: bool) -> None:
        palette = self._theme_palette(dark_mode)
        self.root.configure(bg=palette["window_bg"])
        self.style.configure("App.TFrame", background=palette["window_bg"])
        self.style.configure("Card.TFrame", background=palette["card_bg"])
        self.style.configure("HeaderCard.TFrame", background=palette["card_bg"])
        self.style.configure("Card.TLabelframe", background=palette["card_bg"], borderwidth=1, relief="solid")
        self.style.configure("Card.TLabelframe.Label", background=palette["card_bg"], foreground=palette["meta_fg"], font=("Segoe UI Semibold", 10))
        self.style.configure("HeaderTitle.TLabel", background=palette["card_bg"], foreground=palette["title_fg"], font=("Segoe UI Semibold", 20))
        self.style.configure("HeaderSubtitle.TLabel", background=palette["card_bg"], foreground=palette["subtitle_fg"], font=("Segoe UI", 10))
        self.style.configure("HeaderMeta.TLabel", background=palette["card_bg"], foreground=palette["meta_fg"], font=("Segoe UI Semibold", 9))
        self.style.configure(
            "BackendDetectedLink.TLabel",
            background=palette["card_bg"],
            foreground=palette["backend_detected_fg"],
            font=("Segoe UI", 9, "underline"),
        )
        self.style.configure(
            "BackendMissingLink.TLabel",
            background=palette["card_bg"],
            foreground=palette["backend_missing_fg"],
            font=("Segoe UI", 9, "underline"),
        )
        self.style.configure("StatusBar.TFrame", background=palette["status_bg"])
        self.style.configure("StatusLeft.TLabel", background=palette["status_bg"], foreground=palette["status_fg"], font=("Segoe UI", 9))
        self.style.configure("StatusRight.TLabel", background=palette["status_bg"], foreground=palette["status_fg"], font=("Segoe UI", 9))
        self.style.map("App.TButton", background=[("active", palette["button_active"]), ("pressed", palette["button_press"])])
        self.style.configure("App.TNotebook", background=palette["notebook_bg"])
        self.style.configure("App.TNotebook.Tab", background=palette["tab_bg"], foreground=palette["tab_fg"])
        self.style.map(
            "App.TNotebook.Tab",
            background=[("selected", palette["tab_sel_bg"]), ("active", palette["tab_active_bg"])],
            foreground=[("selected", palette["tab_sel_fg"]), ("active", palette["tab_active_fg"])],
        )
        self.style.configure("TopTabs.TNotebook", background=palette["notebook_bg"])
        self.style.configure("TopTabs.TNotebook.Tab", background=palette["tab_bg"], foreground=palette["tab_fg"])
        self.style.map(
            "TopTabs.TNotebook.Tab",
            background=[("selected", palette["tab_sel_bg"]), ("active", palette["tab_active_bg"])],
            foreground=[("selected", palette["tab_sel_fg"]), ("active", palette["tab_active_fg"])],
        )
        if hasattr(self, "log_box"):
            self.log_box.configure(
                bg=palette["log_bg"],
                fg=palette["log_fg"],
                insertbackground=palette["log_fg"],
                highlightbackground=palette["log_border"],
                highlightcolor=palette["log_border"],
            )

    def _on_dark_mode_changed(self) -> None:
        value = bool(self.dark_mode_var.get())
        self.settings["dark_mode"] = value
        self._save_settings()
        self._apply_theme(value)
        self.log(f"Theme changed to {'Dark' if value else 'Light'} mode.")

    def _toggle_dark_mode_button(self) -> None:
        self.dark_mode_var.set(not bool(self.dark_mode_var.get()))
        self._on_dark_mode_changed()

    def _capture_normal_window_state(self) -> None:
        if self._window_mode_state != "normal":
            return
        try:
            current_state = str(self.root.state())
            self._normal_zoomed = current_state == "zoomed"
            if not self._normal_zoomed:
                self._normal_geometry = self.root.geometry()
        except Exception:
            pass

    def _apply_window_mode_state(self) -> None:
        fullscreen = bool(self.fullscreen_var.get())
        borderless = bool(self.borderless_max_var.get())
        if fullscreen and borderless:
            borderless = False
            self.borderless_max_var.set(False)

        if fullscreen:
            self._capture_normal_window_state()
            try:
                self.root.overrideredirect(False)
            except Exception:
                pass
            try:
                self.root.attributes("-fullscreen", True)
            except Exception:
                pass
            self._window_mode_state = "fullscreen"
            return

        try:
            self.root.attributes("-fullscreen", False)
        except Exception:
            pass

        if borderless:
            self._capture_normal_window_state()
            try:
                self.root.overrideredirect(False)
            except Exception:
                pass
            self.root.update_idletasks()
            width = self.root.winfo_screenwidth()
            height = self.root.winfo_screenheight()
            try:
                self.root.overrideredirect(True)
            except Exception:
                pass
            self.root.geometry(f"{width}x{height}+0+0")
            self.root.lift()
            self._window_mode_state = "borderless"
            return

        try:
            self.root.overrideredirect(False)
        except Exception:
            pass
        try:
            if self._normal_zoomed:
                self.root.state("zoomed")
            else:
                self.root.state("normal")
                if self._normal_geometry:
                    self.root.geometry(self._normal_geometry)
        except Exception:
            pass
        self._window_mode_state = "normal"

    def _persist_window_mode_settings(self) -> None:
        self.settings["fullscreen"] = bool(self.fullscreen_var.get())
        self.settings["borderless_maximized"] = bool(self.borderless_max_var.get())
        self._save_settings()

    def _on_fullscreen_changed(self) -> None:
        value = bool(self.fullscreen_var.get())
        if value:
            self.borderless_max_var.set(False)
        self._persist_window_mode_settings()
        self._apply_window_mode_state()
        self.status_left_var.set("Fullscreen enabled." if value else "Fullscreen disabled.")

    def _on_borderless_changed(self) -> None:
        value = bool(self.borderless_max_var.get())
        if value:
            self.fullscreen_var.set(False)
        self._persist_window_mode_settings()
        self._apply_window_mode_state()
        self.status_left_var.set("Borderless maximized enabled." if value else "Borderless maximized disabled.")

    def _toggle_fullscreen_button(self) -> None:
        self.fullscreen_var.set(not bool(self.fullscreen_var.get()))
        self._on_fullscreen_changed()

    def _toggle_borderless_button(self) -> None:
        self.borderless_max_var.set(not bool(self.borderless_max_var.get()))
        self._on_borderless_changed()

    def _on_f11_toggle(self, _event=None):
        self._toggle_fullscreen_button()
        return "break"

    def _on_f10_toggle_borderless(self, _event=None):
        self._toggle_borderless_button()
        return "break"

    def _on_escape_exit_fullscreen(self, _event=None):
        if bool(self.fullscreen_var.get()) or bool(self.borderless_max_var.get()):
            self.fullscreen_var.set(False)
            self.borderless_max_var.set(False)
            self._persist_window_mode_settings()
            self._apply_window_mode_state()
            self.status_left_var.set("Window mode reset to normal.")
            return "break"
        return None

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)

        file_menu = tk.Menu(menu, tearoff=0)
        file_menu.add_command(label="Open Output Folder", command=self._open_output_folder)
        file_menu.add_command(label="Open Program Folder", command=lambda: self._open_path(self.runtime_dir))
        file_menu.add_separator()
        file_menu.add_command(label="Run First-Run Setup Wizard", command=self._rerun_setup_wizard)
        file_menu.add_command(label="Install Missing Backends", command=self._open_backend_install_assistant)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._request_close)
        menu.add_cascade(label="File", menu=file_menu)

        view_menu = tk.Menu(menu, tearoff=0)
        view_menu.add_command(label="Go To Backends / Links", command=lambda: self.select_tab("Backends / Links"))
        view_menu.add_separator()
        view_menu.add_command(label="Go To Convert", command=lambda: self.select_tab("Convert"))
        view_menu.add_command(label="Go To Compress", command=lambda: self.select_tab("Compress"))
        view_menu.add_command(label="Go To Extract", command=lambda: self.select_tab("Extract"))
        view_menu.add_command(label="Go To Presets / Batch Jobs", command=lambda: self.select_tab("Presets / Batch Jobs"))
        view_menu.add_separator()
        view_menu.add_checkbutton(
            label="Borderless Maximized (F10)",
            variable=self.borderless_max_var,
            command=self._on_borderless_changed,
        )
        view_menu.add_checkbutton(label="Fullscreen (F11)", variable=self.fullscreen_var, command=self._on_fullscreen_changed)
        view_menu.add_checkbutton(label="Dark Mode", variable=self.dark_mode_var, command=self._on_dark_mode_changed)
        menu.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menu, tearoff=0)
        help_menu.add_command(label="Check for Updates", command=lambda: self._check_updates_in_background(interactive=True))
        help_menu.add_command(label="About", command=self._show_about)
        menu.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menu)

    def _build_ui(self) -> None:
        root_frame = ttk.Frame(self.root, style="App.TFrame", padding=12)
        root_frame.pack(fill="both", expand=True)

        header_card = ttk.Frame(root_frame, style="HeaderCard.TFrame", padding=(16, 12))
        header_card.pack(fill="x")

        title_row = ttk.Frame(header_card, style="HeaderCard.TFrame")
        title_row.pack(fill="x")
        ttk.Label(title_row, text=APP_TITLE, style="HeaderTitle.TLabel").pack(side="left", anchor="w")
        ttk.Label(title_row, text=f"v{APP_VERSION}", style="HeaderMeta.TLabel").pack(side="right", anchor="e", pady=(6, 0))

        ttk.Label(
            header_card,
            text=(
                "Modular file utility suite with production-style layout. "
                "Use left-side module tabs for all workflows, with queue-based operations and backend-aware processing."
            ),
            style="HeaderSubtitle.TLabel",
            wraplength=1250,
        ).pack(anchor="w", pady=(6, 10))

        quick_row = ttk.Frame(header_card, style="HeaderCard.TFrame")
        quick_row.pack(fill="x")
        ttk.Button(quick_row, text="Open Output Folder", style="App.TButton", command=self._open_output_folder).pack(side="left")
        ttk.Button(quick_row, text="Toggle Dark Mode", style="App.TButton", command=self._toggle_dark_mode_button).pack(side="left", padx=(8, 0))
        ttk.Button(quick_row, text="Toggle Borderless", style="App.TButton", command=self._toggle_borderless_button).pack(side="left", padx=(8, 0))
        ttk.Button(quick_row, text="Toggle Fullscreen", style="App.TButton", command=self._toggle_fullscreen_button).pack(side="left", padx=(8, 0))
        ttk.Button(quick_row, text="Check Updates", style="App.TButton", command=lambda: self._check_updates_in_background(interactive=True)).pack(side="left", padx=(8, 0))
        ttk.Button(quick_row, text="About", style="App.TButton", command=self._show_about).pack(side="left", padx=(8, 0))

        backend_box = ttk.LabelFrame(root_frame, text="Detected Backends", style="Card.TLabelframe")
        backend_box.pack(fill="x", pady=(10, 10))
        backend_rows = ttk.Frame(backend_box, style="Card.TFrame")
        backend_rows.pack(fill="x", padx=10, pady=10)
        self.backend_hover_cards = []
        backends_per_row = 3
        for index, (name, value) in enumerate(self.backends.as_rows()):
            row = index // backends_per_row
            base_col = (index % backends_per_row) * 2
            ttk.Label(backend_rows, text=f"{name}:", style="HeaderMeta.TLabel", width=11).grid(
                row=row,
                column=base_col,
                sticky="w",
                padx=(0, 6),
                pady=2,
            )
            is_detected = value != "Not found"
            style_name = "BackendDetectedLink.TLabel" if is_detected else "BackendMissingLink.TLabel"
            visible_value = self._backend_summary_display_text(value, max_chars=34)
            value_label = ttk.Label(backend_rows, text=visible_value, style=style_name, cursor="hand2")
            value_label.grid(
                row=row,
                column=base_col + 1,
                sticky="w",
                padx=(0, 20),
                pady=2,
            )
            value_label.bind(
                "<Button-1>",
                lambda _event, backend_name=name, backend_value=value: self._on_backend_summary_clicked(backend_name, backend_value),
            )
            self.backend_hover_cards.append(
                HoverCard(
                    value_label,
                    text_provider=lambda backend_name=name, backend_value=value: self._backend_hover_text(backend_name, backend_value),
                    dark_mode_provider=lambda: bool(self.dark_mode_var.get()),
                )
            )

        content_frame = ttk.Frame(root_frame, style="App.TFrame")
        content_frame.pack(fill="both", expand=True)

        top_notebook = ttk.Notebook(content_frame, style="TopTabs.TNotebook")
        top_notebook.pack(fill="both", expand=True)
        top_notebook.enable_traversal()
        self.top_notebook = top_notebook

        workspace_tab = ttk.Frame(top_notebook, style="App.TFrame")
        top_notebook.add(workspace_tab, text="Workspace")

        suite_plan_tab = SuitePlanTab(top_notebook, self)
        self.tabs["Suite Plan"] = suite_plan_tab
        top_notebook.add(suite_plan_tab, text="Suite Plan")

        backend_links_tab = BackendLinksTab(top_notebook, self)
        self.tabs["Backends / Links"] = backend_links_tab
        top_notebook.add(backend_links_tab, text="Backends / Links")

        activity_log_tab = ttk.Frame(top_notebook, style="App.TFrame")
        top_notebook.add(activity_log_tab, text="Activity Log")

        self.notebook = ttk.Notebook(workspace_tab, style="App.TNotebook")
        self.notebook.pack(fill="both", expand=True)
        self.notebook.enable_traversal()

        tab_specs = [
            ("Convert", ConvertTab),
            ("Compress", CompressTab),
            ("Extract", ExtractTab),
            ("Metadata", MetadataTab),
            ("PDF / Documents", DocumentsTab),
            ("Images", ImagesRoadmapTab),
            ("Audio", AudioRoadmapTab),
            ("Video", VideoRoadmapTab),
            ("Archives", ArchivesTab),
            ("Rename / Organize", RenameOrganizeTab),
            ("Duplicate Finder", DuplicateFinderTab),
            ("Storage Analyzer", StorageAnalyzerTab),
            ("Checksums / Integrity", ChecksumsTab),
            ("Subtitles", SubtitlesTab),
            ("Presets / Batch Jobs", PresetsBatchTab),
        ]

        for name, tab_class in tab_specs:
            tab = tab_class(self.notebook, self)
            self.tabs[name] = tab
            self.notebook.add(tab, text=name)

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        top_notebook.bind("<<NotebookTabChanged>>", self._on_top_tab_changed)

        log_frame = ttk.LabelFrame(activity_log_tab, text="Recent Operations", style="Card.TLabelframe")
        log_frame.pack(fill="both", expand=True)
        self.log_box = ScrolledText(log_frame, height=10, wrap="word")
        self.log_box.configure(relief="flat", highlightthickness=1)
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)
        self._apply_theme(bool(self.dark_mode_var.get()))

        status_bar = ttk.Frame(root_frame, style="StatusBar.TFrame")
        status_bar.pack(fill="x", pady=(10, 0))
        ttk.Label(status_bar, textvariable=self.status_left_var, style="StatusLeft.TLabel").pack(side="left", padx=(10, 0), pady=4)
        ttk.Label(status_bar, textvariable=self.status_right_var, style="StatusRight.TLabel").pack(side="right", padx=(0, 10), pady=4)

        self.log("Suite ready.")

    def _open_path(self, path: Path) -> None:
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(path))
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Failed to open path:\n{exc}")

    def _open_file_location(self, path: Path) -> None:
        target = path.resolve()
        if not target.exists():
            raise FileNotFoundError(str(target))
        try:
            if os.name == "nt":
                if target.is_file():
                    subprocess.Popen(["explorer", "/select,", str(target)])
                    return
                subprocess.Popen(["explorer", str(target)])
                return
        except Exception:
            pass
        self._open_path(target.parent if target.is_file() else target)

    def _next_available_path(self, target_path: Path) -> Path:
        suffix = "".join(target_path.suffixes)
        base = target_path.name[: -len(suffix)] if suffix else target_path.name
        for index in range(1, 10000):
            candidate = target_path.with_name(f"{base} ({index}){suffix}")
            if not candidate.exists():
                return candidate
        return target_path.with_name(f"{base}_{int(time.time())}{suffix}")

    def _show_output_conflict_dialog(self, target_path: Path, context: str, exists: bool) -> str:
        dialog = tk.Toplevel(self.root)
        dialog.title(APP_TITLE)
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()
        self._apply_window_icon_to(dialog)

        result = {"choice": "cancel"}

        def choose(value: str) -> None:
            result["choice"] = value
            try:
                dialog.grab_release()
            except Exception:
                pass
            dialog.destroy()

        container = ttk.Frame(dialog, padding=14)
        container.pack(fill="both", expand=True)
        header = f"{context} already exists:" if exists else f"{context} is ready to save:"
        ttk.Label(container, text=header, justify="left").pack(anchor="w")
        ttk.Label(container, text=str(target_path), justify="left", wraplength=560).pack(anchor="w", pady=(4, 10))
        ttk.Label(container, text="Choose what to do for this file:").pack(anchor="w")

        buttons = ttk.Frame(container)
        buttons.pack(fill="x", pady=(12, 0))
        primary_label = "Replace" if exists else "Use This Name"
        ttk.Button(buttons, text=primary_label, style="App.TButton", command=lambda: choose("replace")).pack(side="left")
        ttk.Button(buttons, text="Rename", style="App.TButton", command=lambda: choose("rename")).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Change Location", style="App.TButton", command=lambda: choose("relocate")).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Cancel", style="App.TButton", command=lambda: choose("cancel")).pack(side="right")

        dialog.protocol("WM_DELETE_WINDOW", lambda: choose("cancel"))
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - dialog.winfo_width()) // 2)
        y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - dialog.winfo_height()) // 2)
        dialog.geometry(f"+{x}+{y}")
        self.root.wait_window(dialog)
        return str(result["choice"])

    def _choose_alternate_output_path(self, target_path: Path, context: str) -> Path | None:
        chosen = filedialog.asksaveasfilename(
            title=f"{context} - Choose New Location",
            initialdir=str(target_path.parent),
            initialfile=target_path.name,
            defaultextension=target_path.suffix,
            filetypes=[("All Files", "*.*")],
        )
        if not chosen:
            return None
        return Path(chosen)

    def _resolve_output_path_ui(self, target_path: Path, context: str) -> Path | None:
        candidate = Path(target_path)
        ensure_dir(candidate.parent)
        while True:
            exists = candidate.exists()
            choice = self._show_output_conflict_dialog(candidate, context, exists=exists)
            if choice == "replace":
                return candidate
            if choice == "rename":
                return self._next_available_path(candidate)
            if choice == "relocate":
                relocated = self._choose_alternate_output_path(candidate, context)
                if relocated is None:
                    return None
                candidate = Path(relocated)
                ensure_dir(candidate.parent)
                continue
            return None

    def resolve_output_path(self, target_path: Path, context: str = "Output file") -> Path | None:
        if threading.current_thread() is self.main_thread:
            return self._resolve_output_path_ui(target_path, context)
        return self.call_ui_sync(lambda: self._resolve_output_path_ui(target_path, context))

    def _backend_install_link(self, backend_name: str) -> str:
        links = BACKEND_LINKS.get(backend_name, {})
        return str(links.get("download") or links.get("homepage") or links.get("docs") or "").strip()

    def _backend_install_command(self, backend_name: str) -> str:
        links = BACKEND_LINKS.get(backend_name, {})
        return str(links.get("install_cmd") or "").strip()

    def _missing_backend_names(self) -> list[str]:
        return [name for name, value in self.backends.as_rows() if value == "Not found"]

    def _ellipsize_middle(self, text: str, max_chars: int) -> str:
        value = str(text)
        if max_chars <= 0 or len(value) <= max_chars:
            return value
        if max_chars <= 6:
            return value[:max_chars]
        head = max(2, (max_chars - 3) // 2)
        tail = max_chars - 3 - head
        return f"{value[:head]}...{value[-tail:]}"

    def _backend_summary_display_text(self, detected_value: str, max_chars: int = 34) -> str:
        value = str(detected_value).strip()
        if not value or value == "Not found":
            return "Not found"
        normalized = value.replace("/", "\\")
        path_obj = Path(normalized)
        file_name = path_obj.name
        parent_name = path_obj.parent.name
        if file_name and parent_name:
            compact = f"...\\{parent_name}\\{file_name}"
            if len(compact) <= max_chars:
                return compact
        if file_name and len(file_name) <= max_chars:
            return file_name
        return self._ellipsize_middle(normalized, max_chars)

    def _backend_hover_text(self, backend_name: str, detected_value: str) -> str:
        description = BACKEND_DESCRIPTIONS.get(backend_name, "Optional backend used for advanced processing.")
        value = str(detected_value).strip()
        if value and value != "Not found":
            return (
                f"{backend_name}\n"
                "Status: Detected\n"
                f"{description}\n\n"
                f"Path: {value}\n"
                "Click to open this backend location."
            )
        install_cmd = self._backend_install_command(backend_name) or "No command configured"
        install_link = self._backend_install_link(backend_name) or "No link configured"
        return (
            f"{backend_name}\n"
            "Status: Not detected\n"
            f"{description}\n\n"
            "Not required for base app, but recommended for complex actions.\n"
            f"Install command: {install_cmd}\n"
            f"Install link: {install_link}\n"
            "Click to open the install page."
        )

    def _open_backend_install_links(self, backend_names: list[str]) -> int:
        opened = 0
        for backend_name in backend_names:
            install_link = self._backend_install_link(backend_name)
            if install_link:
                webbrowser.open(install_link)
                opened += 1
        return opened

    def _copy_backend_install_commands(self, backend_names: list[str], interactive: bool = False) -> int:
        blocks: list[str] = []
        for backend_name in backend_names:
            cmd = self._backend_install_command(backend_name)
            if cmd:
                blocks.append(cmd)
        if not blocks:
            if interactive:
                messagebox.showwarning(APP_TITLE, "No install commands are configured for the selected backends.")
            return 0
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(blocks))
        if interactive:
            messagebox.showinfo(APP_TITLE, "Install commands were copied to clipboard in terminal-ready format.")
        return len(blocks)

    def _open_backend_install_assistant(self, backend_names: list[str] | None = None) -> None:
        self.backends = BackendRegistry.detect()
        missing = self._missing_backend_names()
        targets = list(backend_names) if backend_names is not None else missing
        targets = [name for name in targets if name in BACKEND_LINKS]
        if not targets:
            messagebox.showinfo(
                APP_TITLE,
                "All optional backends are currently detected.\n\n"
                "Backends are not required for the base app, but recommended for complex actions.",
            )
            return

        panel = tk.Toplevel(self.root)
        panel.title("Backend Install Assistant")
        panel.geometry("780x460")
        panel.minsize(700, 420)
        panel.transient(self.root)
        panel.grab_set()

        outer = ttk.Frame(panel, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text=(
                "Optional backends improve advanced workflows.\n"
                "They are not required for the base app, but recommended for complex actions."
            ),
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        rows_box = ttk.LabelFrame(outer, text="Missing / Selected Backends")
        rows_box.pack(fill="both", expand=True)

        row_host = ttk.Frame(rows_box, padding=8)
        row_host.pack(fill="both", expand=True)

        selected: dict[str, BooleanVar] = {}
        for index, backend_name in enumerate(targets):
            selected[backend_name] = BooleanVar(value=True)
            row = ttk.Frame(row_host)
            row.grid(row=index, column=0, sticky="ew", pady=(0, 8))
            row.columnconfigure(1, weight=1)

            ttk.Checkbutton(row, text=backend_name, variable=selected[backend_name]).grid(row=0, column=0, sticky="w", padx=(0, 10))
            ttk.Label(
                row,
                text=BACKEND_DESCRIPTIONS.get(backend_name, "Optional backend used for advanced processing."),
                wraplength=420,
            ).grid(row=0, column=1, sticky="w")
            ttk.Button(row, text="Open Link", command=lambda name=backend_name: self._open_backend_install_links([name])).grid(row=0, column=2, padx=(10, 6))
            ttk.Button(
                row,
                text="Copy Cmd",
                command=lambda name=backend_name: self._copy_backend_install_commands([name], interactive=True),
            ).grid(row=0, column=3)

        action_bar = ttk.Frame(outer)
        action_bar.pack(fill="x", pady=(10, 0))

        def chosen() -> list[str]:
            return [name for name, var in selected.items() if bool(var.get())]

        def open_selected() -> None:
            names = chosen()
            if not names:
                messagebox.showwarning(APP_TITLE, "Select at least one backend.")
                return
            opened = self._open_backend_install_links(names)
            if opened:
                self.log(f"Opened install links for {opened} backend(s).")
            else:
                messagebox.showwarning(APP_TITLE, "No install links are configured for the selected backends.")

        def copy_selected() -> None:
            names = chosen()
            if not names:
                messagebox.showwarning(APP_TITLE, "Select at least one backend.")
                return
            copied = self._copy_backend_install_commands(names, interactive=False)
            if copied:
                messagebox.showinfo(APP_TITLE, "Selected backend install commands copied to clipboard.")
            else:
                messagebox.showwarning(APP_TITLE, "No install commands are configured for the selected backends.")

        ttk.Button(action_bar, text="Open Selected Install Links", command=open_selected).pack(side="left")
        ttk.Button(action_bar, text="Copy Selected Install Commands", command=copy_selected).pack(side="left", padx=(8, 0))
        ttk.Button(action_bar, text="Close", command=panel.destroy).pack(side="right")

    def _prompt_install_missing_backends_on_startup(self) -> None:
        if not bool(self.settings.get("prompt_backend_install_on_startup", True)):
            return
        self.backends = BackendRegistry.detect()
        missing = self._missing_backend_names()
        if not missing:
            return
        prompt = (
            "Optional backends are missing:\n\n"
            f"{', '.join(missing)}\n\n"
            "These are not required for the base app, but recommended for complex actions.\n\n"
            "Would you like to review install options now?"
        )
        if messagebox.askyesno(APP_TITLE, prompt):
            self._open_backend_install_assistant(missing)

    def _on_backend_summary_clicked(self, backend_name: str, detected_value: str) -> None:
        value = str(detected_value).strip()
        if value and value != "Not found":
            try:
                self._open_file_location(Path(value))
                return
            except Exception:
                self.log(f"Backend path is unavailable for {backend_name}: {value}")
        install_link = self._backend_install_link(backend_name)
        if install_link:
            webbrowser.open(install_link)
            self.log(f"Opened install page for {backend_name}: {install_link}")
            return
        messagebox.showwarning(APP_TITLE, f"No install link is configured for {backend_name}.")

    def _open_output_folder(self) -> None:
        ensure_dir(self.default_output_root)
        self._open_path(self.default_output_root)

    def _rerun_setup_wizard(self) -> None:
        self._run_first_run_setup_wizard()
        self.dark_mode_var.set(bool(self.settings.get("dark_mode", False)))
        self.fullscreen_var.set(bool(self.settings.get("fullscreen", False)))
        self.borderless_max_var.set(bool(self.settings.get("borderless_maximized", False)))
        self._apply_theme(bool(self.dark_mode_var.get()))
        self._apply_window_mode_state()
        self._set_backend_summary_status()
        self.log("Setup wizard completed and settings were updated.")

    def _show_about(self) -> None:
        available = sum(1 for _, value in self.backends.as_rows() if value != "Not found")
        total = len(self.backends.as_rows())
        messagebox.showinfo(
            APP_TITLE,
            f"{APP_TITLE}\nVersion {APP_VERSION}\n\n"
            f"Modules: {len(self.tabs)}\n"
            f"Backends detected: {available}/{total}\n"
            f"Settings file: {self.settings_path}\n"
            f"Output folder: {self.default_output_root}",
        )

    def _active_task_labels(self) -> list[str]:
        labels: list[str] = []
        for name, tab in self.tabs.items():
            worker = getattr(tab, "worker", None)
            if worker and worker.is_alive():
                labels.append(name)
        if hasattr(self, "_update_thread") and self._update_thread and self._update_thread.is_alive():
            labels.append("Update Check")
        return labels

    def _request_close(self) -> None:
        running = self._active_task_labels()
        if running:
            preview = ", ".join(running[:3])
            remainder = len(running) - 3
            if remainder > 0:
                preview = f"{preview}, +{remainder} more"
            should_close = messagebox.askyesno(
                APP_TITLE,
                "Background work is still running.\n\n"
                f"Active: {preview}\n\n"
                "Close anyway? Running tasks will be interrupted.",
            )
            if not should_close:
                return
        self.root.destroy()

    def _show_startup_logo_animation(self) -> None:
        splash = tk.Toplevel(self.root)
        splash.overrideredirect(True)
        splash.attributes("-topmost", True)
        splash.configure(bg="#0E1726")
        self._apply_window_icon_to(splash)

        width, height = 560, 320
        x = (splash.winfo_screenwidth() - width) // 2
        y = (splash.winfo_screenheight() - height) // 2
        splash.geometry(f"{width}x{height}+{x}+{y}")

        container = tk.Frame(splash, bg="#0E1726")
        container.pack(fill="both", expand=True, padx=24, pady=20)

        logo = tk.Canvas(container, width=140, height=120, bg="#0E1726", highlightthickness=0, bd=0)
        logo.pack(pady=(6, 8))
        logo.create_rectangle(30, 20, 90, 100, fill="#3DA4FF", outline="#70C8FF", width=2)
        logo.create_polygon(90, 20, 110, 20, 110, 40, 90, 40, fill="#70C8FF", outline="#70C8FF")
        line_a = logo.create_line(38, 58, 106, 58, fill="#DDF0FF", width=5, arrow="last", arrowshape=(10, 12, 5))
        line_b = logo.create_line(106, 78, 38, 78, fill="#9FD6FF", width=5, arrow="last", arrowshape=(10, 12, 5))
        orbit = logo.create_oval(64, 14, 74, 24, fill="#FDEB7C", outline="")

        tk.Label(
            container,
            text="Universal File Utility Suite",
            bg="#0E1726",
            fg="#EAF4FF",
            font=("Segoe UI Semibold", 15),
        ).pack()
        tk.Label(
            container,
            text="Preparing modules, backends, and workspace...",
            bg="#0E1726",
            fg="#A5C3E6",
            font=("Segoe UI", 10),
        ).pack(pady=(4, 12))

        progress = ttk.Progressbar(container, mode="determinate", maximum=100, length=440)
        progress.pack(pady=(0, 8))
        state_label = tk.Label(container, text="Loading UI...", bg="#0E1726", fg="#B9D4F1", font=("Segoe UI", 9))
        state_label.pack()

        start = time.perf_counter()
        duration = 4.6
        spin_cycles = 1.6
        pulse_cycles = 1.2

        def tick() -> None:
            if not splash.winfo_exists():
                return
            ratio = min((time.perf_counter() - start) / duration, 1.0)
            progress.configure(value=ratio * 100.0)
            state_label.configure(text=f"Loading UI... {int(ratio * 100):d}%")
            angle = ratio * math.tau * spin_cycles
            cx = 69 + 28 * math.cos(angle)
            cy = 59 + 28 * math.sin(angle)
            logo.coords(orbit, cx - 5, cy - 5, cx + 5, cy + 5)
            shift = 4 * math.sin(ratio * math.tau * pulse_cycles)
            logo.coords(line_a, 38 + shift, 58, 106 + shift, 58)
            logo.coords(line_b, 106 - shift, 78, 38 - shift, 78)
            if ratio < 1.0:
                splash.after(16, tick)
                return
            splash.destroy()
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()

        splash.after(20, tick)

    def _set_backend_summary_status(self) -> None:
        available = sum(1 for _, value in self.backends.as_rows() if value != "Not found")
        total = len(self.backends.as_rows())
        self.status_right_var.set(f"Backends {available}/{total}")

    def _check_updates_in_background(self, interactive: bool) -> None:
        if hasattr(self, "_update_thread") and self._update_thread and self._update_thread.is_alive():
            if interactive:
                messagebox.showinfo(APP_TITLE, "Update check is already running.")
            return

        def worker() -> None:
            manifest_url = str(self.settings.get("update_manifest_url", "")).strip()
            self.settings["last_update_check"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self._save_settings()

            if not manifest_url:
                local_candidates = [
                    self.runtime_dir / "update_manifest.json",
                    self.runtime_dir / "update_manifest.example.json",
                    self.script_dir / "update_manifest.json",
                    self.script_dir / "update_manifest.example.json",
                ]
                found = next((candidate for candidate in local_candidates if candidate.exists()), None)
                if found:
                    manifest_url = found.as_uri()
                elif interactive:
                    self.call_ui(self._prompt_configure_updates)
                    return
                else:
                    return

            try:
                with urllib.request.urlopen(manifest_url, timeout=12) as response:
                    payload = response.read().decode("utf-8", errors="replace")
                data = json.loads(payload)
                latest = str(data.get("latest_version") or data.get("version") or "").strip()
                download_url = str(data.get("download_url") or data.get("url") or "").strip()
                notes = str(data.get("notes") or "").strip()

                if latest and is_version_newer(latest, APP_VERSION):
                    self.call_ui(lambda: self._show_update_available(latest, download_url, notes))
                elif interactive:
                    self.info(f"You are up to date. Current version: {APP_VERSION}")
            except urllib.error.URLError as exc:
                if interactive:
                    self.error(f"Update check failed:\n{exc}")
            except Exception as exc:
                if interactive:
                    self.error(f"Update check failed:\n{exc}")

        self._update_thread = threading.Thread(target=worker, daemon=True)
        self._update_thread.start()

    def _prompt_configure_updates(self) -> None:
        answer = messagebox.askyesno(
            APP_TITLE,
            "No update manifest is configured.\n\nOpen setup wizard now to configure update settings?",
        )
        if answer:
            self._rerun_setup_wizard()

    def _show_update_available(self, latest: str, download_url: str, notes: str) -> None:
        details = notes if notes else "No release notes provided."
        prompt = (
            f"Update available.\n\nCurrent version: {APP_VERSION}\nLatest version: {latest}\n\n"
            f"{details}\n\nOpen download page now?"
        )
        if download_url and messagebox.askyesno(APP_TITLE, prompt):
            webbrowser.open(download_url)
        elif not download_url:
            messagebox.showinfo(APP_TITLE, f"Update {latest} is available, but no download URL was provided.")

    def _on_tab_changed(self, _event=None) -> None:
        current = self.notebook.tab(self.notebook.select(), "text")
        self.status_left_var.set(f"Module: {current}")

    def _on_top_tab_changed(self, _event=None) -> None:
        current_top = self.top_notebook.tab(self.top_notebook.select(), "text")
        if current_top == "Workspace":
            self._on_tab_changed()
            return
        if current_top == "Activity Log":
            self.status_left_var.set("Activity Log")
            return
        self.status_left_var.set(f"Module: {current_top}")

    def select_tab(self, name: str) -> None:
        workspace_index = None
        for top_index, top_id in enumerate(self.top_notebook.tabs()):
            if self.top_notebook.tab(top_id, "text") == "Workspace":
                workspace_index = top_index
                break
        for index, tab_id in enumerate(self.notebook.tabs()):
            if self.notebook.tab(tab_id, "text") == name:
                if workspace_index is not None:
                    self.top_notebook.select(workspace_index)
                self.notebook.select(index)
                self.status_left_var.set(f"Module: {name}")
                return
        for top_index, top_id in enumerate(self.top_notebook.tabs()):
            if self.top_notebook.tab(top_id, "text") == name:
                self.top_notebook.select(top_index)
                self._on_top_tab_changed()
                return

    def _append_log(self, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_box.insert(END, f"[{stamp}] {message}\n")
        self.log_box.see(END)
        self.status_left_var.set(message[:120])

    def log(self, message: str) -> None:
        if threading.current_thread() is self.main_thread:
            self._append_log(message)
        else:
            self.ui_queue.put(("log", message))

    def call_ui(self, callback) -> None:
        self.ui_queue.put(("call", callback))

    def call_ui_sync(self, callback, timeout: float | None = None):
        if threading.current_thread() is self.main_thread:
            return callback()
        result_queue: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

        def wrapped() -> None:
            try:
                result_queue.put((True, callback()))
            except Exception as exc:
                result_queue.put((False, exc))

        self.ui_queue.put(("call", wrapped))
        try:
            ok, payload = result_queue.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError("Timed out waiting for UI response.") from exc
        if not ok:
            raise payload
        return payload

    def info(self, message: str) -> None:
        self.call_ui(lambda: messagebox.showinfo(APP_TITLE, message))

    def error(self, message: str) -> None:
        self.call_ui(lambda: messagebox.showerror(APP_TITLE, message))

    def _poll_ui_queue(self) -> None:
        try:
            while True:
                action, payload = self.ui_queue.get_nowait()
                if action == "log":
                    self._append_log(payload)
                elif action == "call":
                    payload()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_ui_queue)

    def run_process(self, cmd: list[str], cwd: Path | None = None) -> None:
        self.log(f"$ {quote_cmd(cmd)}")
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
        )
        tail: list[str] = []
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            line = raw_line.strip()
            if not line:
                continue
            tail.append(line)
            if len(tail) > 30:
                tail.pop(0)
            lowered = line.lower()
            if any(key in lowered for key in ("error", "fail", "invalid", "warning")):
                self.log(line)
        code = proc.wait()
        if code != 0:
            detail = tail[-1] if tail else f"Process exited with code {code}"
            raise RuntimeError(detail)


class ModuleTab(ttk.Frame):
    tab_name = "Module"

    def __init__(self, master, app: SuiteApp):
        super().__init__(master)
        self.app = app
        self.worker: threading.Thread | None = None

    def log(self, message: str) -> None:
        self.app.log(f"{self.tab_name}: {message}")

    def run_async(self, action, done_message: str | None = None) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(APP_TITLE, f"{self.tab_name} is already running.")
            return

        def runner() -> None:
            try:
                action()
                if done_message:
                    self.app.info(done_message)
            except Exception as exc:
                self.log(f"Error: {exc}")
                self.app.error(f"{self.tab_name} failed:\n{exc}")

        self.worker = threading.Thread(target=runner, daemon=True)
        self.worker.start()

    def add_files_to_queue(self, files: list[Path], listbox: tk.Listbox, title: str = "Select files") -> None:
        chosen = filedialog.askopenfilenames(title=title)
        for raw in chosen:
            path = Path(raw)
            if path not in files:
                files.append(path)
                listbox.insert(END, str(path))

    def add_folder_to_queue(self, files: list[Path], listbox: tk.Listbox, title: str = "Select folder") -> None:
        raw = filedialog.askdirectory(title=title)
        if not raw:
            return
        folder = Path(raw)
        for path in folder.rglob("*"):
            if path.is_file() and path not in files:
                files.append(path)
                listbox.insert(END, str(path))

    def remove_selected(self, files: list[Path], listbox: tk.Listbox) -> None:
        selected = list(listbox.curselection())
        selected.reverse()
        for index in selected:
            listbox.delete(index)
            files.pop(index)

    def clear_queue(self, files: list[Path], listbox: tk.Listbox) -> None:
        files.clear()
        listbox.delete(0, END)

    def remove_path_from_queue(self, files: list[Path], listbox: tk.Listbox, target: Path) -> None:
        for index, item in enumerate(list(files)):
            if item == target:
                files.pop(index)
                listbox.delete(index)
                return
        target_str = str(target)
        for index in range(listbox.size()):
            if listbox.get(index) == target_str:
                listbox.delete(index)
                return

    def choose_output_dir(self, variable: StringVar, title: str) -> None:
        raw = filedialog.askdirectory(title=title)
        if raw:
            variable.set(raw)


class SuitePlanTab(ModuleTab):
    tab_name = "Suite Plan"

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self._build()

    def _build(self) -> None:
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)

        plan_text = (
            "Project Structure\n"
            "- One desktop app with module tabs.\n"
            "- Shared task engine keeps conversion logic centralized.\n"
            "- Each module can grow independently without creating a tangled monolith.\n\n"
            "Phase 1 (Implemented)\n"
            "- Convert\n"
            "- Compress\n"
            "- Extract\n"
            "- Metadata\n"
            "- Presets / Batch Jobs\n\n"
            "Phase 2 (Starter Included)\n"
            "- PDF / Documents\n"
            "- Archives\n"
            "- Rename / Organize\n"
            "- Checksums / Integrity\n"
            "- Subtitles\n\n"
            "Phase 3 (Starter Included)\n"
            "- Duplicate Finder\n"
            "- Storage Analyzer\n"
            "- Media-focused image/audio/video modules with richer workflows\n\n"
            "Notes\n"
            "- External tools improve coverage (FFmpeg, Pandoc, LibreOffice, 7-Zip, ImageMagick).\n"
            "- Built-in Python handlers still provide useful fallback for many operations.\n"
            "- The architecture here is designed so new modules can be added without refactoring the whole app."
        )
        text = ScrolledText(body, wrap="word")
        text.insert("1.0", plan_text)
        text.configure(state="disabled")
        text.pack(fill="both", expand=True)


class BackendLinksTab(ModuleTab):
    tab_name = "Backends / Links"

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.backend_data: dict[str, dict[str, str]] = {}
        self.homepage_var = StringVar(value="")
        self.docs_var = StringVar(value="")
        self.download_var = StringVar(value="")
        self.install_cmd_var = StringVar(value="")
        self.detected_path_var = StringVar(value="")
        self.status_var = StringVar(value="Select a backend to view links.")
        self._build()
        self._populate()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text=(
                "Backend links tab: official homepage, documentation, download page, and install command "
                "for each backend used by the suite."
            ),
            wraplength=1180,
        ).pack(anchor="w", pady=(0, 8))

        top_controls = ttk.Frame(outer)
        top_controls.pack(fill="x", pady=(0, 8))
        ttk.Button(top_controls, text="Refresh Detection", command=self._populate).pack(side="left")
        ttk.Button(top_controls, text="Open Homepage", command=lambda: self._open_url(self.homepage_var.get())).pack(side="left", padx=(8, 0))
        ttk.Button(top_controls, text="Open Docs", command=lambda: self._open_url(self.docs_var.get())).pack(side="left", padx=(8, 0))
        ttk.Button(top_controls, text="Open Download", command=lambda: self._open_url(self.download_var.get())).pack(side="left", padx=(8, 0))
        ttk.Button(top_controls, text="Copy Install Command", command=self._copy_install_command).pack(side="left", padx=(8, 0))
        ttk.Button(top_controls, text="Open Detected Path", command=self._open_detected_path).pack(side="left", padx=(8, 0))

        split = ttk.Panedwindow(outer, orient="horizontal")
        split.pack(fill="both", expand=True)

        left = ttk.Labelframe(split, text="Backends")
        right = ttk.Labelframe(split, text="Links")
        split.add(left, weight=2)
        split.add(right, weight=3)

        self.tree = ttk.Treeview(left, columns=("backend", "status", "path"), show="headings")
        self.tree.heading("backend", text="Backend")
        self.tree.heading("status", text="Status")
        self.tree.heading("path", text="Detected Path")
        self.tree.column("backend", width=150)
        self.tree.column("status", width=110)
        self.tree.column("path", width=520)
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        form = ttk.Frame(right, padding=10)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Homepage").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        ttk.Entry(form, textvariable=self.homepage_var).grid(row=0, column=1, sticky="ew", pady=(0, 8))

        ttk.Label(form, text="Docs").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        ttk.Entry(form, textvariable=self.docs_var).grid(row=1, column=1, sticky="ew", pady=(0, 8))

        ttk.Label(form, text="Download").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        ttk.Entry(form, textvariable=self.download_var).grid(row=2, column=1, sticky="ew", pady=(0, 8))

        ttk.Label(form, text="Install Command").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        ttk.Entry(form, textvariable=self.install_cmd_var).grid(row=3, column=1, sticky="ew", pady=(0, 8))

        ttk.Label(form, text="Detected Path").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        ttk.Entry(form, textvariable=self.detected_path_var).grid(row=4, column=1, sticky="ew", pady=(0, 8))
        form.columnconfigure(1, weight=1)

        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(8, 0))

    def _populate(self) -> None:
        self.app.backends = BackendRegistry.detect()
        rows = self.app.backends.as_rows()
        self.backend_data.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        for backend_name, path_value in rows:
            status = "Detected" if path_value != "Not found" else "Missing"
            self.tree.insert("", "end", values=(backend_name, status, path_value))
            links = BACKEND_LINKS.get(backend_name, {})
            self.backend_data[backend_name] = {
                "homepage": links.get("homepage", ""),
                "docs": links.get("docs", ""),
                "download": links.get("download", ""),
                "install_cmd": links.get("install_cmd", ""),
                "detected_path": path_value if path_value != "Not found" else "",
            }
        if self.tree.get_children():
            first = self.tree.get_children()[0]
            self.tree.selection_set(first)
            self.tree.focus(first)
            self._on_select()
        available = sum(1 for _, value in rows if value != "Not found")
        self.status_var.set(f"Detected {available}/{len(rows)} backends.")

    def _on_select(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        backend_name = str(self.tree.item(selected[0], "values")[0])
        data = self.backend_data.get(backend_name, {})
        self.homepage_var.set(data.get("homepage", ""))
        self.docs_var.set(data.get("docs", ""))
        self.download_var.set(data.get("download", ""))
        self.install_cmd_var.set(data.get("install_cmd", ""))
        self.detected_path_var.set(data.get("detected_path", ""))
        self.status_var.set(f"Selected backend: {backend_name}")

    def _open_url(self, url: str) -> None:
        url = url.strip()
        if not url:
            messagebox.showwarning(APP_TITLE, "No URL available for this backend.")
            return
        webbrowser.open(url)

    def _copy_install_command(self) -> None:
        cmd = self.install_cmd_var.get().strip()
        if not cmd:
            messagebox.showwarning(APP_TITLE, "No install command available for this backend.")
            return
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(cmd)
        self.status_var.set("Install command copied to clipboard.")

    def _open_detected_path(self) -> None:
        path_value = self.detected_path_var.get().strip()
        if not path_value:
            messagebox.showwarning(APP_TITLE, "This backend is not currently detected.")
            return
        path = Path(path_value)
        if not path.exists():
            messagebox.showwarning(APP_TITLE, "Detected path is no longer available.")
            return
        try:
            self.app._open_file_location(path)
        except Exception as exc:
            messagebox.showwarning(APP_TITLE, f"Failed to open detected path:\n{exc}")


class ConvertTab(ModuleTab):
    tab_name = "Convert"
    _SUFFIX_ALIASES = {
        ".jpeg": ".jpg",
        ".tif": ".tiff",
        ".yml": ".yaml",
        ".htm": ".html",
        ".markdown": ".md",
    }
    _AUDIO_TARGETS = ["mp3", "wav", "flac", "ogg", "m4a"]
    _VIDEO_TARGETS = ["mp4", "mkv", "mov", "webm"]

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.files: list[Path] = []
        self.target_format = StringVar(value="")
        self.output_dir = StringVar(value=str(self.app.default_output_root / "convert"))
        self.image_quality = IntVar(value=92)
        self.image_quality_text = StringVar(value=str(self.image_quality.get()))
        self.image_quality_display = StringVar(value=f"{self.image_quality.get()}%")
        self.audio_bitrate = StringVar(value="192k")
        self.video_preset = StringVar(value="medium")
        self.video_crf = IntVar(value=23)
        self.video_crf_display = StringVar(value=str(self.video_crf.get()))
        self.status_var = StringVar(value="Ready.")
        self.progress_percent_var = StringVar(value="0%")
        self._progress_anim_after: str | None = None
        self._progress_total_files = 1
        self._progress_value = 0.0
        self._progress_target = 0.0
        self.source_ext_lock: str | None = None
        self.target_format_combo: ttk.Combobox | None = None
        self.image_quality.trace_add("write", self._on_image_quality_var_changed)
        self.video_crf.trace_add("write", self._on_video_crf_var_changed)
        self._build()
        self._on_image_quality_var_changed()
        self._on_video_crf_var_changed()
        self._refresh_target_formats()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        queue_controls = ttk.Frame(outer)
        queue_controls.pack(fill="x")
        ttk.Button(queue_controls, text="Add Files", command=self._add_files_filtered).pack(side="left")
        ttk.Button(queue_controls, text="Add Folder", command=self._add_folder_filtered).pack(side="left", padx=6)
        ttk.Button(queue_controls, text="Remove Selected", command=self._remove_selected_filtered).pack(side="left")
        ttk.Button(queue_controls, text="Clear", command=self._clear_queue_filtered).pack(side="left", padx=6)

        list_frame = ttk.Frame(outer)
        list_frame.pack(fill="both", expand=True, pady=(8, 8))
        self.listbox = tk.Listbox(list_frame, selectmode=SINGLE)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scroll.set)

        options = ttk.LabelFrame(outer, text="Conversion Settings")
        options.pack(fill="x")

        ttk.Label(options, text="Target format").grid(row=0, column=0, sticky="w", padx=(10, 6), pady=(10, 6))
        self.target_format_combo = ttk.Combobox(
            options,
            textvariable=self.target_format,
            values=[],
            state="disabled",
            width=18,
        )
        self.target_format_combo.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(10, 6))

        ttk.Label(options, text="Image quality").grid(row=0, column=2, sticky="w", padx=(12, 6), pady=(10, 6))
        ttk.Scale(
            options,
            from_=1,
            to=100,
            variable=self.image_quality,
            orient="horizontal",
            command=self._on_image_quality_scale_changed,
        ).grid(
            row=0, column=3, sticky="ew", padx=(0, 10), pady=(10, 6)
        )
        quality_input = ttk.Entry(options, textvariable=self.image_quality_text, width=6)
        quality_input.grid(row=0, column=4, sticky="w", padx=(0, 4), pady=(10, 6))
        quality_input.bind("<Return>", self._commit_image_quality_text)
        quality_input.bind("<FocusOut>", self._commit_image_quality_text)
        ttk.Label(options, text="%(1-100)").grid(row=0, column=5, sticky="w", padx=(0, 8), pady=(10, 6))
        ttk.Label(options, textvariable=self.image_quality_display, width=6).grid(
            row=0, column=6, sticky="w", padx=(0, 10), pady=(10, 6)
        )

        ttk.Label(options, text="Audio bitrate").grid(row=1, column=0, sticky="w", padx=(10, 6), pady=(6, 10))
        ttk.Combobox(
            options,
            textvariable=self.audio_bitrate,
            values=["96k", "128k", "160k", "192k", "256k", "320k"],
            state="readonly",
            width=18,
        ).grid(row=1, column=1, sticky="w", padx=(0, 12), pady=(6, 10))

        ttk.Label(options, text="Video preset").grid(row=1, column=2, sticky="w", padx=(12, 6), pady=(6, 10))
        ttk.Combobox(
            options,
            textvariable=self.video_preset,
            values=["ultrafast", "veryfast", "medium", "slow"],
            state="readonly",
            width=12,
        ).grid(row=1, column=3, sticky="w", padx=(0, 10), pady=(6, 10))

        ttk.Label(options, text="Video CRF").grid(row=1, column=4, sticky="w", padx=(8, 6), pady=(6, 10))
        ttk.Scale(
            options,
            from_=18,
            to=35,
            variable=self.video_crf,
            orient="horizontal",
            command=self._on_video_crf_scale_changed,
        ).grid(
            row=1, column=5, sticky="ew", padx=(0, 10), pady=(6, 10)
        )
        ttk.Label(options, textvariable=self.video_crf_display, width=4).grid(row=1, column=6, sticky="w", padx=(0, 10), pady=(6, 10))
        options.columnconfigure(3, weight=1)
        options.columnconfigure(5, weight=1)

        out_row = ttk.Frame(outer)
        out_row.pack(fill="x", pady=(10, 4))
        ttk.Label(out_row, text="Output folder:").pack(side="left")
        ttk.Entry(out_row, textvariable=self.output_dir).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(out_row, text="Browse", command=lambda: self.choose_output_dir(self.output_dir, "Choose output folder")).pack(side="left")

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(4, 0))
        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(bottom, textvariable=self.progress_percent_var, width=6).pack(side="left", padx=(0, 10))
        ttk.Button(bottom, text="Convert Queue", command=self.convert_queue).pack(side="right")

        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))

    def export_preset(self) -> dict[str, Any]:
        return {
            "target_format": self.target_format.get(),
            "image_quality": self.image_quality.get(),
            "audio_bitrate": self.audio_bitrate.get(),
            "video_preset": self.video_preset.get(),
            "video_crf": self.video_crf.get(),
        }

    def _normalize_source_suffix(self, value: Path | str) -> str:
        raw = value.suffix if isinstance(value, Path) else str(value)
        suffix = raw.strip().lower()
        if suffix and not suffix.startswith("."):
            suffix = f".{suffix}"
        return self._SUFFIX_ALIASES.get(suffix, suffix)

    def _supported_source_suffix(self, suffix: str) -> bool:
        return suffix in (IMAGE_EXTS | DATA_EXTS | TEXT_EXTS | MEDIA_EXTS)

    def _targets_for_source_suffix(self, source_suffix: str) -> list[str]:
        suffix = self._normalize_source_suffix(source_suffix)
        if suffix in IMAGE_EXTS:
            targets = list(IMAGE_FORMATS)
        elif suffix in DATA_EXTS:
            targets = list(DATA_FORMATS)
        elif suffix in TEXT_EXTS:
            targets = ["txt", "md", "html"]
        elif suffix in AUDIO_EXTS:
            targets = list(self._AUDIO_TARGETS)
        elif suffix in VIDEO_EXTS:
            targets = list(self._VIDEO_TARGETS + self._AUDIO_TARGETS)
        else:
            return []

        source_fmt = suffix.lstrip(".")
        if source_fmt in {"jpeg"}:
            source_fmt = "jpg"
        if source_fmt in {"tif"}:
            source_fmt = "tiff"
        if source_fmt in {"yml"}:
            source_fmt = "yaml"
        if source_fmt in {"htm"}:
            source_fmt = "html"
        if source_fmt in {"markdown"}:
            source_fmt = "md"
        return [fmt for fmt in targets if fmt != source_fmt]

    def _refresh_target_formats(self) -> None:
        if not self.target_format_combo:
            return
        if self.files and not self.source_ext_lock:
            self.source_ext_lock = self._normalize_source_suffix(self.files[0])
        if not self.source_ext_lock:
            self.target_format_combo.configure(state="disabled")
            self.target_format_combo["values"] = ()
            self.target_format.set("")
            return

        targets = self._targets_for_source_suffix(self.source_ext_lock)
        self.target_format_combo["values"] = tuple(targets)
        if not targets:
            self.target_format_combo.configure(state="disabled")
            self.target_format.set("")
            return

        current = self.target_format.get().strip().lower()
        if current not in targets:
            self.target_format.set(targets[0])
        self.target_format_combo.configure(state="readonly")

    def _enqueue_candidates(self, candidates: list[Path]) -> None:
        if not candidates:
            return

        lock = self.source_ext_lock
        added = 0
        skipped_mismatch = 0
        skipped_unsupported = 0
        skipped_duplicate = 0

        for candidate in candidates:
            if not candidate.is_file():
                continue
            suffix = self._normalize_source_suffix(candidate)
            if not self._supported_source_suffix(suffix):
                skipped_unsupported += 1
                continue
            if lock is None:
                lock = suffix
            if suffix != lock:
                skipped_mismatch += 1
                continue
            if candidate in self.files:
                skipped_duplicate += 1
                continue
            self.files.append(candidate)
            self.listbox.insert(END, str(candidate))
            added += 1

        self.source_ext_lock = lock if self.files else None
        self._refresh_target_formats()

        if added and self.source_ext_lock:
            self.status_var.set(
                f"Queue locked to {self.source_ext_lock} files. Added {added} file(s)."
            )

        skipped_parts = []
        if skipped_mismatch:
            skipped_parts.append(f"{skipped_mismatch} mismatched type")
        if skipped_unsupported:
            skipped_parts.append(f"{skipped_unsupported} unsupported type")
        if skipped_duplicate:
            skipped_parts.append(f"{skipped_duplicate} duplicate")
        if skipped_parts:
            lock_text = self.source_ext_lock or "a single type"
            messagebox.showwarning(
                APP_TITLE,
                f"Queue accepts one source file type at a time ({lock_text}).\n\n"
                f"Skipped: {', '.join(skipped_parts)}.",
            )

    def _add_files_filtered(self) -> None:
        chosen = filedialog.askopenfilenames(title="Select files")
        self._enqueue_candidates([Path(raw) for raw in chosen])

    def _add_folder_filtered(self) -> None:
        raw = filedialog.askdirectory(title="Select folder")
        if not raw:
            return
        folder = Path(raw)
        self._enqueue_candidates([path for path in folder.rglob("*") if path.is_file()])

    def _remove_selected_filtered(self) -> None:
        self.remove_selected(self.files, self.listbox)
        if not self.files:
            self.source_ext_lock = None
        self._refresh_target_formats()

    def _clear_queue_filtered(self) -> None:
        self.clear_queue(self.files, self.listbox)
        self.source_ext_lock = None
        self._refresh_target_formats()

    def _remove_path_from_queue_filtered(self, target: Path) -> None:
        self.remove_path_from_queue(self.files, self.listbox, target)
        if not self.files:
            self.source_ext_lock = None
        self._refresh_target_formats()

    def _on_image_quality_var_changed(self, *_args) -> None:
        try:
            current = int(self.image_quality.get())
        except Exception:
            current = 92
        clamped = max(1, min(100, current))
        if clamped != current:
            self.image_quality.set(clamped)
            return
        self.image_quality_text.set(str(clamped))
        self.image_quality_display.set(f"{clamped}%")

    def _on_image_quality_scale_changed(self, raw_value: str) -> None:
        try:
            rounded = int(round(float(raw_value)))
        except Exception:
            return
        clamped = max(1, min(100, rounded))
        if clamped != int(self.image_quality.get()):
            self.image_quality.set(clamped)

    def _commit_image_quality_text(self, _event=None) -> None:
        raw = self.image_quality_text.get().strip().replace("%", "")
        if not raw:
            self.image_quality_text.set(str(self.image_quality.get()))
            return
        try:
            parsed = int(round(float(raw)))
        except Exception:
            self.image_quality_text.set(str(self.image_quality.get()))
            return
        self.image_quality.set(max(1, min(100, parsed)))

    def _on_video_crf_var_changed(self, *_args) -> None:
        try:
            current = int(self.video_crf.get())
        except Exception:
            current = 23
        clamped = max(18, min(35, current))
        if clamped != current:
            self.video_crf.set(clamped)
            return
        self.video_crf_display.set(str(clamped))

    def _on_video_crf_scale_changed(self, raw_value: str) -> None:
        try:
            rounded = int(round(float(raw_value)))
        except Exception:
            return
        clamped = max(18, min(35, rounded))
        if clamped != int(self.video_crf.get()):
            self.video_crf.set(clamped)

    def _cancel_progress_animation(self) -> None:
        if self._progress_anim_after:
            try:
                self.after_cancel(self._progress_anim_after)
            except Exception:
                pass
            self._progress_anim_after = None

    def _apply_progress_value(self) -> None:
        total_files = max(1, int(self._progress_total_files))
        self._progress_value = max(0.0, min(float(total_files), float(self._progress_value)))
        self.progress.configure(mode="determinate", maximum=total_files, value=self._progress_value)
        percent = int(round((self._progress_value / total_files) * 100))
        self.progress_percent_var.set(f"{percent}%")

    def _queue_progress_reset(self, total_files: int) -> None:
        self._cancel_progress_animation()
        self._progress_total_files = max(1, int(total_files))
        self._progress_value = 0.0
        self._progress_target = 0.0
        self._apply_progress_value()

    def _queue_progress_set_target(self, target: float, immediate: bool = False) -> None:
        total_files = float(max(1, int(self._progress_total_files)))
        self._progress_target = max(0.0, min(total_files, float(target)))
        if immediate:
            self._cancel_progress_animation()
            self._progress_value = self._progress_target
            self._apply_progress_value()
            return
        if self._progress_value + 1e-6 >= self._progress_target:
            self._apply_progress_value()
            return
        if self._progress_anim_after is None:
            self._progress_anim_after = self.after(33, self._animate_progress_step)

    def _animate_progress_step(self) -> None:
        self._progress_anim_after = None
        delta = self._progress_target - self._progress_value
        if delta <= 0:
            self._apply_progress_value()
            return
        step = max(0.02, delta * 0.22)
        self._progress_value = min(self._progress_target, self._progress_value + step)
        self._apply_progress_value()
        if (self._progress_target - self._progress_value) > 1e-6:
            self._progress_anim_after = self.after(33, self._animate_progress_step)

    def apply_preset(self, payload: dict[str, Any]) -> None:
        if "target_format" in payload:
            self.target_format.set(str(payload["target_format"]))
        if "image_quality" in payload:
            self.image_quality.set(int(payload["image_quality"]))
        if "audio_bitrate" in payload:
            self.audio_bitrate.set(str(payload["audio_bitrate"]))
        if "video_preset" in payload:
            self.video_preset.set(str(payload["video_preset"]))
        if "video_crf" in payload:
            self.video_crf.set(int(payload["video_crf"]))
        self._refresh_target_formats()

    def convert_queue(self) -> None:
        if not self.files:
            messagebox.showwarning(APP_TITLE, "Add files before converting.")
            return
        if not self.source_ext_lock:
            self.source_ext_lock = self._normalize_source_suffix(self.files[0])
            self._refresh_target_formats()
        allowed_targets = self._targets_for_source_suffix(self.source_ext_lock or "")
        if not allowed_targets:
            messagebox.showwarning(APP_TITLE, f"Unsupported source type for convert queue: {self.source_ext_lock}")
            return
        selected_target = self.target_format.get().strip().lower()
        if selected_target not in allowed_targets:
            messagebox.showwarning(
                APP_TITLE,
                "Choose a valid target format for the current queue type before converting.",
            )
            self._refresh_target_formats()
            return
        out_dir = Path(self.output_dir.get().strip())
        ensure_dir(out_dir)
        options = self.export_preset()
        total = len(self.files)

        def work() -> None:
            failures = []
            self.app.call_ui(
                lambda total_files=total: (
                    self._queue_progress_reset(total_files),
                    self.status_var.set(f"Processing 0/{total_files}..."),
                )
            )
            for index, file_path in enumerate(list(self.files), start=1):
                self.app.call_ui(
                    lambda i=index, total_files=total, current=file_path.name: (
                        self._queue_progress_set_target((i - 1) + 0.9, immediate=False),
                        self.status_var.set(f"Processing {i}/{total_files}: {current}"),
                    )
                )
                try:
                    result = self.app.engine.convert_file(file_path, out_dir, self.target_format.get(), options)
                    self.log(f"{file_path.name} -> {result.name}")
                except Exception as exc:
                    failures.append(f"{file_path.name}: {exc}")
                percent = int((index / total) * 100) if total else 0
                self.app.call_ui(
                    lambda i=index, total_files=total, current=file_path.name, p=percent: (
                        self._queue_progress_set_target(i, immediate=True),
                        self.progress_percent_var.set(f"{p}%"),
                        self.status_var.set(f"Completed {i}/{total_files}: {current}"),
                    )
                )
                self.app.call_ui(lambda p=file_path: self._remove_path_from_queue_filtered(p))
            if failures:
                raise RuntimeError(f"{len(failures)} file(s) failed. First issue: {failures[0]}")
            self.app.call_ui(
                lambda total_files=total: (
                    self._queue_progress_set_target(total_files, immediate=True),
                    self.progress_percent_var.set("100%"),
                    self.status_var.set(f"Completed {total_files} conversions."),
                )
            )

        self.run_async(work, done_message=f"Convert module completed {total} file(s).")


class CompressTab(ModuleTab):
    tab_name = "Compress"

    MODE_MAP = {
        "Images (quality)": "image_quality",
        "Video (CRF)": "video_crf",
        "Audio (bitrate)": "audio_bitrate",
        "Create ZIP (batch)": "zip_batch",
    }

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.files: list[Path] = []
        self.mode_var = StringVar(value="Images (quality)")
        self.output_dir = StringVar(value=str(self.app.default_output_root / "compress"))
        self.quality_var = IntVar(value=82)
        self.crf_var = IntVar(value=28)
        self.bitrate_var = StringVar(value="128k")
        self.video_preset_var = StringVar(value="medium")
        self.zip_level_var = IntVar(value=6)
        self.status_var = StringVar(value="Ready.")
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        controls = ttk.Frame(outer)
        controls.pack(fill="x")
        ttk.Button(controls, text="Add Files", command=lambda: self.add_files_to_queue(self.files, self.listbox)).pack(side="left")
        ttk.Button(controls, text="Add Folder", command=lambda: self.add_folder_to_queue(self.files, self.listbox)).pack(side="left", padx=6)
        ttk.Button(controls, text="Remove Selected", command=lambda: self.remove_selected(self.files, self.listbox)).pack(side="left")
        ttk.Button(controls, text="Clear", command=lambda: self.clear_queue(self.files, self.listbox)).pack(side="left", padx=6)

        queue = ttk.Frame(outer)
        queue.pack(fill="both", expand=True, pady=(8, 8))
        self.listbox = tk.Listbox(queue, selectmode=SINGLE)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(queue, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scroll.set)

        options = ttk.LabelFrame(outer, text="Compression Settings")
        options.pack(fill="x")

        ttk.Label(options, text="Mode").grid(row=0, column=0, sticky="w", padx=(10, 6), pady=(10, 6))
        ttk.Combobox(options, textvariable=self.mode_var, values=list(self.MODE_MAP.keys()), state="readonly", width=22).grid(
            row=0, column=1, sticky="w", padx=(0, 12), pady=(10, 6)
        )

        ttk.Label(options, text="Image quality").grid(row=0, column=2, sticky="w", padx=(10, 6), pady=(10, 6))
        ttk.Scale(options, from_=10, to=100, variable=self.quality_var, orient="horizontal").grid(
            row=0, column=3, sticky="ew", padx=(0, 10), pady=(10, 6)
        )
        ttk.Label(options, text="Video CRF").grid(row=0, column=4, sticky="w", padx=(8, 6), pady=(10, 6))
        ttk.Scale(options, from_=18, to=35, variable=self.crf_var, orient="horizontal").grid(
            row=0, column=5, sticky="ew", padx=(0, 10), pady=(10, 6)
        )

        ttk.Label(options, text="Audio bitrate").grid(row=1, column=0, sticky="w", padx=(10, 6), pady=(6, 10))
        ttk.Combobox(
            options,
            textvariable=self.bitrate_var,
            values=["96k", "128k", "160k", "192k", "256k", "320k"],
            state="readonly",
            width=12,
        ).grid(row=1, column=1, sticky="w", padx=(0, 12), pady=(6, 10))

        ttk.Label(options, text="Video preset").grid(row=1, column=2, sticky="w", padx=(10, 6), pady=(6, 10))
        ttk.Combobox(
            options,
            textvariable=self.video_preset_var,
            values=["ultrafast", "veryfast", "medium", "slow"],
            state="readonly",
            width=12,
        ).grid(row=1, column=3, sticky="w", padx=(0, 12), pady=(6, 10))

        ttk.Label(options, text="ZIP level").grid(row=1, column=4, sticky="w", padx=(10, 6), pady=(6, 10))
        ttk.Scale(options, from_=1, to=9, variable=self.zip_level_var, orient="horizontal").grid(
            row=1, column=5, sticky="ew", padx=(0, 10), pady=(6, 10)
        )
        options.columnconfigure(3, weight=1)
        options.columnconfigure(5, weight=1)

        out_row = ttk.Frame(outer)
        out_row.pack(fill="x", pady=(10, 4))
        ttk.Label(out_row, text="Output folder:").pack(side="left")
        ttk.Entry(out_row, textvariable=self.output_dir).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(out_row, text="Browse", command=lambda: self.choose_output_dir(self.output_dir, "Choose output folder")).pack(side="left")

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(4, 0))
        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(bottom, text="Run Compression", command=self.run_compress).pack(side="right")
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))

    def export_preset(self) -> dict[str, Any]:
        return {
            "mode_name": self.mode_var.get(),
            "mode_key": self.MODE_MAP[self.mode_var.get()],
            "quality": self.quality_var.get(),
            "crf": self.crf_var.get(),
            "audio_bitrate": self.bitrate_var.get(),
            "video_preset": self.video_preset_var.get(),
            "zip_level": self.zip_level_var.get(),
        }

    def apply_preset(self, payload: dict[str, Any]) -> None:
        if "mode_name" in payload and payload["mode_name"] in self.MODE_MAP:
            self.mode_var.set(str(payload["mode_name"]))
        if "quality" in payload:
            self.quality_var.set(int(payload["quality"]))
        if "crf" in payload:
            self.crf_var.set(int(payload["crf"]))
        if "audio_bitrate" in payload:
            self.bitrate_var.set(str(payload["audio_bitrate"]))
        if "video_preset" in payload:
            self.video_preset_var.set(str(payload["video_preset"]))
        if "zip_level" in payload:
            self.zip_level_var.set(int(payload["zip_level"]))

    def run_compress(self) -> None:
        if not self.files:
            messagebox.showwarning(APP_TITLE, "Add files before compressing.")
            return
        out_dir = Path(self.output_dir.get().strip())
        ensure_dir(out_dir)
        preset = self.export_preset()
        mode_key = preset["mode_key"]
        total = len(self.files)

        def work() -> None:
            self.app.call_ui(lambda: self.progress.configure(value=0, maximum=total))
            if mode_key == "zip_batch":
                archive = self.app.engine.create_zip_archive(self.files, out_dir, level=int(preset["zip_level"]))
                self.log(f"Created archive: {archive}")
                self.app.call_ui(lambda: self.progress.configure(value=total))
                self.app.call_ui(lambda: self.status_var.set(f"Created {archive.name} from {total} source(s)."))
                self.app.call_ui(lambda: self.clear_queue(self.files, self.listbox))
                return

            failures = []
            for index, file_path in enumerate(list(self.files), start=1):
                try:
                    out_path = self.app.engine.compress_file(file_path, out_dir, mode_key, preset)
                    self.log(f"{file_path.name} -> {out_path.name}")
                except Exception as exc:
                    failures.append(f"{file_path.name}: {exc}")
                self.app.call_ui(
                    lambda i=index, total_files=total, current=file_path.name: (
                        self.progress.configure(value=i),
                        self.status_var.set(f"Processing {i}/{total_files}: {current}"),
                    )
                )
                self.app.call_ui(lambda p=file_path: self.remove_path_from_queue(self.files, self.listbox, p))
            if failures:
                raise RuntimeError(f"{len(failures)} file(s) failed. First issue: {failures[0]}")
            self.app.call_ui(lambda: self.status_var.set(f"Completed compression for {total} file(s)."))

        self.run_async(work, done_message=f"Compress module finished {total} item(s).")


class ExtractTab(ModuleTab):
    tab_name = "Extract"

    OP_MAP = {
        "Audio from video": "audio_from_video",
        "Frames from video": "frames_from_video",
        "Subtitles from video": "subtitles_from_video",
        "Cover art from audio": "cover_art_from_audio",
    }

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.files: list[Path] = []
        self.operation_var = StringVar(value="Audio from video")
        self.output_dir = StringVar(value=str(self.app.default_output_root / "extract"))
        self.audio_format_var = StringVar(value="mp3")
        self.fps_var = StringVar(value="1")
        self.subtitle_index_var = IntVar(value=0)
        self.status_var = StringVar(value="Ready.")
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        controls = ttk.Frame(outer)
        controls.pack(fill="x")
        ttk.Button(controls, text="Add Files", command=lambda: self.add_files_to_queue(self.files, self.listbox)).pack(side="left")
        ttk.Button(controls, text="Add Folder", command=lambda: self.add_folder_to_queue(self.files, self.listbox)).pack(side="left", padx=6)
        ttk.Button(controls, text="Remove Selected", command=lambda: self.remove_selected(self.files, self.listbox)).pack(side="left")
        ttk.Button(controls, text="Clear", command=lambda: self.clear_queue(self.files, self.listbox)).pack(side="left", padx=6)

        queue = ttk.Frame(outer)
        queue.pack(fill="both", expand=True, pady=(8, 8))
        self.listbox = tk.Listbox(queue, selectmode=SINGLE)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(queue, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scroll.set)

        options = ttk.LabelFrame(outer, text="Extraction Settings")
        options.pack(fill="x")
        ttk.Label(options, text="Operation").grid(row=0, column=0, sticky="w", padx=(10, 6), pady=(10, 6))
        ttk.Combobox(options, textvariable=self.operation_var, values=list(self.OP_MAP.keys()), state="readonly", width=24).grid(
            row=0, column=1, sticky="w", padx=(0, 12), pady=(10, 6)
        )
        ttk.Label(options, text="Audio format").grid(row=0, column=2, sticky="w", padx=(10, 6), pady=(10, 6))
        ttk.Combobox(options, textvariable=self.audio_format_var, values=["mp3", "wav", "flac", "ogg", "m4a"], state="readonly", width=10).grid(
            row=0, column=3, sticky="w", padx=(0, 12), pady=(10, 6)
        )
        ttk.Label(options, text="Frame FPS").grid(row=1, column=0, sticky="w", padx=(10, 6), pady=(6, 10))
        ttk.Entry(options, textvariable=self.fps_var, width=10).grid(row=1, column=1, sticky="w", padx=(0, 12), pady=(6, 10))
        ttk.Label(options, text="Subtitle stream index").grid(row=1, column=2, sticky="w", padx=(10, 6), pady=(6, 10))
        ttk.Spinbox(options, from_=0, to=20, textvariable=self.subtitle_index_var, width=10).grid(
            row=1, column=3, sticky="w", padx=(0, 12), pady=(6, 10)
        )

        out_row = ttk.Frame(outer)
        out_row.pack(fill="x", pady=(10, 4))
        ttk.Label(out_row, text="Output folder:").pack(side="left")
        ttk.Entry(out_row, textvariable=self.output_dir).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(out_row, text="Browse", command=lambda: self.choose_output_dir(self.output_dir, "Choose output folder")).pack(side="left")

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(4, 0))
        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(bottom, text="Run Extraction", command=self.run_extract).pack(side="right")
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))

    def export_preset(self) -> dict[str, Any]:
        return {
            "operation_name": self.operation_var.get(),
            "operation_key": self.OP_MAP[self.operation_var.get()],
            "audio_format": self.audio_format_var.get(),
            "fps": self.fps_var.get(),
            "subtitle_index": self.subtitle_index_var.get(),
        }

    def apply_preset(self, payload: dict[str, Any]) -> None:
        if "operation_name" in payload and payload["operation_name"] in self.OP_MAP:
            self.operation_var.set(str(payload["operation_name"]))
        if "audio_format" in payload:
            self.audio_format_var.set(str(payload["audio_format"]))
        if "fps" in payload:
            self.fps_var.set(str(payload["fps"]))
        if "subtitle_index" in payload:
            self.subtitle_index_var.set(int(payload["subtitle_index"]))

    def run_extract(self) -> None:
        if not self.files:
            messagebox.showwarning(APP_TITLE, "Add files before extracting.")
            return
        out_dir = Path(self.output_dir.get().strip())
        ensure_dir(out_dir)
        preset = self.export_preset()
        operation_key = preset["operation_key"]
        total = len(self.files)

        def work() -> None:
            self.app.call_ui(lambda: self.progress.configure(value=0, maximum=total))
            failures = []
            for index, file_path in enumerate(list(self.files), start=1):
                try:
                    output = self.app.engine.extract_from_media(file_path, out_dir, operation_key, preset)
                    self.log(f"{file_path.name} -> {output}")
                except Exception as exc:
                    failures.append(f"{file_path.name}: {exc}")
                self.app.call_ui(
                    lambda i=index, total_files=total, current=file_path.name: (
                        self.progress.configure(value=i),
                        self.status_var.set(f"Processing {i}/{total_files}: {current}"),
                    )
                )
                self.app.call_ui(lambda p=file_path: self.remove_path_from_queue(self.files, self.listbox, p))
            if failures:
                raise RuntimeError(f"{len(failures)} file(s) failed. First issue: {failures[0]}")
            self.app.call_ui(lambda: self.status_var.set(f"Completed extraction for {total} file(s)."))

        self.run_async(work, done_message=f"Extract module finished {total} item(s).")


class MetadataTab(ModuleTab):
    tab_name = "Metadata"

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.file_var = StringVar(value="")
        self.output_dir = StringVar(value=str(self.app.default_output_root / "metadata"))
        self.key_var = StringVar(value="title")
        self.value_var = StringVar(value="")
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        top = ttk.Frame(outer)
        top.pack(fill="x")
        ttk.Label(top, text="File:").pack(side="left")
        ttk.Entry(top, textvariable=self.file_var).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(top, text="Browse", command=self.pick_file).pack(side="left")
        ttk.Button(top, text="Inspect", command=self.inspect_metadata).pack(side="left", padx=(6, 0))

        meta_frame = ttk.LabelFrame(outer, text="Update Metadata")
        meta_frame.pack(fill="x", pady=(10, 10))
        ttk.Label(meta_frame, text="Key").grid(row=0, column=0, sticky="w", padx=(10, 6), pady=(10, 6))
        ttk.Entry(meta_frame, textvariable=self.key_var, width=24).grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(10, 6))
        ttk.Label(meta_frame, text="Value").grid(row=0, column=2, sticky="w", padx=(10, 6), pady=(10, 6))
        ttk.Entry(meta_frame, textvariable=self.value_var).grid(row=0, column=3, sticky="ew", padx=(0, 12), pady=(10, 6))
        meta_frame.columnconfigure(3, weight=1)

        out_row = ttk.Frame(meta_frame)
        out_row.grid(row=1, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 10))
        ttk.Label(out_row, text="Output folder:").pack(side="left")
        ttk.Entry(out_row, textvariable=self.output_dir).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(out_row, text="Browse", command=lambda: self.choose_output_dir(self.output_dir, "Choose output folder")).pack(side="left")
        ttk.Button(out_row, text="Apply Metadata", command=self.apply_metadata).pack(side="left", padx=(8, 0))

        self.text = ScrolledText(outer, wrap="word")
        self.text.pack(fill="both", expand=True)

    def pick_file(self) -> None:
        raw = filedialog.askopenfilename(title="Select file")
        if raw:
            self.file_var.set(raw)

    def inspect_metadata(self) -> None:
        raw = self.file_var.get().strip()
        if not raw:
            messagebox.showwarning(APP_TITLE, "Choose a file first.")
            return
        path = Path(raw)
        if not path.exists():
            messagebox.showerror(APP_TITLE, "The selected file no longer exists.")
            return

        def work() -> None:
            details = self.app.engine.inspect_metadata(path)
            formatted = json.dumps(details, indent=2, ensure_ascii=False)
            self.app.call_ui(lambda: (self.text.delete("1.0", END), self.text.insert("1.0", formatted)))
            self.log(f"Read metadata for {path.name}")

        self.run_async(work, done_message="Metadata inspection complete.")

    def apply_metadata(self) -> None:
        raw = self.file_var.get().strip()
        if not raw:
            messagebox.showwarning(APP_TITLE, "Choose a file first.")
            return
        key = self.key_var.get().strip()
        value = self.value_var.get().strip()
        if not key:
            messagebox.showwarning(APP_TITLE, "Metadata key is required.")
            return
        path = Path(raw)
        out_dir = Path(self.output_dir.get().strip())
        ensure_dir(out_dir)

        def work() -> None:
            output = self.app.engine.apply_metadata(path, out_dir, key, value)
            self.log(f"Applied metadata to {path.name} -> {output.name}")
            self.app.call_ui(
                lambda: self.text.insert(
                    END,
                    f"\n\nUpdated metadata key '{key}' with value '{value}'. Output: {output}\n",
                )
            )

        self.run_async(work, done_message="Metadata update completed.")


class DocumentsTab(ModuleTab):
    tab_name = "PDF / Documents"

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.files: list[Path] = []
        self.output_dir = StringVar(value=str(self.app.default_output_root / "documents"))
        self.target_format = StringVar(value="pdf")
        self.status_var = StringVar(value="Ready.")
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        info = ttk.Label(
            outer,
            text=(
                "Starter document conversion tab. Best coverage is available when Pandoc or LibreOffice is installed. "
                "Without those tools, simple text-based copies (TXT/MD/HTML) still work."
            ),
            wraplength=1200,
        )
        info.pack(anchor="w", pady=(0, 8))

        controls = ttk.Frame(outer)
        controls.pack(fill="x")
        ttk.Button(controls, text="Add Files", command=lambda: self.add_files_to_queue(self.files, self.listbox)).pack(side="left")
        ttk.Button(controls, text="Clear", command=lambda: self.clear_queue(self.files, self.listbox)).pack(side="left", padx=6)
        ttk.Label(controls, text="Target format").pack(side="left", padx=(18, 6))
        ttk.Combobox(controls, textvariable=self.target_format, values=DOC_FORMATS, state="readonly", width=12).pack(side="left")
        ttk.Button(controls, text="Convert", command=self.convert_docs).pack(side="right")

        queue = ttk.Frame(outer)
        queue.pack(fill="both", expand=True, pady=(8, 8))
        self.listbox = tk.Listbox(queue, selectmode=SINGLE)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(queue, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scroll.set)

        out_row = ttk.Frame(outer)
        out_row.pack(fill="x")
        ttk.Label(out_row, text="Output folder:").pack(side="left")
        ttk.Entry(out_row, textvariable=self.output_dir).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(out_row, text="Browse", command=lambda: self.choose_output_dir(self.output_dir, "Choose output folder")).pack(side="left")
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))

    def convert_docs(self) -> None:
        if not self.files:
            messagebox.showwarning(APP_TITLE, "Add files before converting.")
            return
        out_dir = Path(self.output_dir.get().strip())
        ensure_dir(out_dir)
        target = self.target_format.get()
        total = len(self.files)

        def work() -> None:
            failures = []
            for index, path in enumerate(list(self.files), start=1):
                try:
                    output = self.app.engine.convert_document(path, out_dir, target)
                    self.log(f"{path.name} -> {output.name}")
                except Exception as exc:
                    failures.append(f"{path.name}: {exc}")
                self.app.call_ui(lambda i=index, total_files=total: self.status_var.set(f"Processing {i}/{total_files}..."))
                self.app.call_ui(lambda p=path: self.remove_path_from_queue(self.files, self.listbox, p))
            if failures:
                raise RuntimeError(f"{len(failures)} file(s) failed. First issue: {failures[0]}")
            self.app.call_ui(lambda: self.status_var.set(f"Converted {total} document(s)."))

        self.run_async(work, done_message=f"Document conversion finished for {total} file(s).")


class RoadmapModuleTab(ModuleTab):
    tab_name = "Roadmap Module"

    def __init__(self, master, app: SuiteApp, module_name: str, note: str, phase: str, planned_items: list[str]):
        super().__init__(master, app)
        self.module_name = module_name
        self.note = note
        self.phase = phase
        self.planned_items = planned_items
        self._build()

    def _build(self) -> None:
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=f"{self.module_name} Module", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(body, text=f"Current status: starter scaffold ({self.phase})", foreground="#1f4f8a").pack(anchor="w", pady=(2, 10))
        ttk.Label(body, text=self.note, wraplength=1180).pack(anchor="w", pady=(0, 10))

        box = ttk.LabelFrame(body, text="Planned expansion")
        box.pack(fill="both", expand=True)
        plan_text = ScrolledText(box, wrap="word")
        lines = "\n".join(f"- {item}" for item in self.planned_items)
        plan_text.insert("1.0", lines)
        plan_text.configure(state="disabled")
        plan_text.pack(fill="both", expand=True, padx=10, pady=10)


class ImagesRoadmapTab(RoadmapModuleTab):
    tab_name = "Images"

    def __init__(self, master, app: SuiteApp):
        super().__init__(
            master,
            app,
            module_name="Images",
            note=(
                "Image workflows are currently available through Convert and Compress. "
                "This dedicated tab is scaffolded for advanced image/design operations."
            ),
            phase="Phase 2/3",
            planned_items=[
                "Web export pipeline (JPEG/WEBP/AVIF presets)",
                "Print prep pipeline (DPI and color profile checks)",
                "Transparency cleanup and matte handling",
                "Sprite sheet / texture atlas builder",
                "Icon pack exporter (ICO/ICNS/mobile sizes)",
            ],
        )


class AudioRoadmapTab(RoadmapModuleTab):
    tab_name = "Audio"

    def __init__(self, master, app: SuiteApp):
        super().__init__(
            master,
            app,
            module_name="Audio",
            note=(
                "Audio conversions and extraction already run in Convert/Extract. "
                "This module is reserved for audio-specific production workflows."
            ),
            phase="Phase 3",
            planned_items=[
                "Sample rate / bit depth conversion presets",
                "Podcast cleanup (loudness normalization and silence trimming)",
                "Batch stem organizer for music exports",
                "Sound library tagging and one-shot/loop classifiers",
            ],
        )


class VideoRoadmapTab(RoadmapModuleTab):
    tab_name = "Video"

    def __init__(self, master, app: SuiteApp):
        super().__init__(
            master,
            app,
            module_name="Video",
            note=(
                "Video conversions and extraction already run in Convert/Compress/Extract. "
                "This dedicated tab is scaffolded for advanced video toolbox actions."
            ),
            phase="Phase 3",
            planned_items=[
                "Remux and trim without re-encode workflows",
                "Subtitle burn-in and subtitle QA checks",
                "Thumbnail sheet and clip batch exporter",
                "Streaming presets for YouTube, Shorts, TikTok, Twitch",
            ],
        )


class ArchivesTab(ModuleTab):
    tab_name = "Archives"

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.inputs: list[Path] = []
        self.archive_format = StringVar(value="zip")
        self.output_archive = StringVar(value=str(self.app.default_output_root / "archives" / "archive.zip"))
        self.extract_dest = StringVar(value=str(self.app.default_output_root / "archives" / "extracted"))
        self.status_var = StringVar(value="Ready.")
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        controls = ttk.Frame(outer)
        controls.pack(fill="x")
        ttk.Button(controls, text="Add Files", command=lambda: self.add_files_to_queue(self.inputs, self.listbox)).pack(side="left")
        ttk.Button(controls, text="Add Folder", command=self.add_folder).pack(side="left", padx=6)
        ttk.Button(controls, text="Remove Selected", command=lambda: self.remove_selected(self.inputs, self.listbox)).pack(side="left")
        ttk.Button(controls, text="Clear", command=lambda: self.clear_queue(self.inputs, self.listbox)).pack(side="left", padx=6)

        queue = ttk.Frame(outer)
        queue.pack(fill="both", expand=True, pady=(8, 8))
        self.listbox = tk.Listbox(queue, selectmode=SINGLE)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(queue, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scroll.set)

        create_box = ttk.LabelFrame(outer, text="Create Archive")
        create_box.pack(fill="x", pady=(0, 8))
        ttk.Label(create_box, text="Format").grid(row=0, column=0, sticky="w", padx=(10, 6), pady=(10, 6))
        ttk.Combobox(create_box, textvariable=self.archive_format, values=ARCHIVE_FORMATS, state="readonly", width=10).grid(
            row=0, column=1, sticky="w", padx=(0, 12), pady=(10, 6)
        )
        ttk.Label(create_box, text="Output archive").grid(row=0, column=2, sticky="w", padx=(10, 6), pady=(10, 6))
        ttk.Entry(create_box, textvariable=self.output_archive).grid(row=0, column=3, sticky="ew", padx=(0, 8), pady=(10, 6))
        ttk.Button(create_box, text="Browse", command=self.pick_output_archive).grid(row=0, column=4, sticky="w", padx=(0, 10), pady=(10, 6))
        ttk.Button(create_box, text="Create", command=self.create_archive).grid(row=0, column=5, sticky="w", pady=(10, 6))
        create_box.columnconfigure(3, weight=1)

        extract_box = ttk.LabelFrame(outer, text="Extract Archives")
        extract_box.pack(fill="x")
        ttk.Label(extract_box, text="Destination").grid(row=0, column=0, sticky="w", padx=(10, 6), pady=(10, 6))
        ttk.Entry(extract_box, textvariable=self.extract_dest).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(10, 6))
        ttk.Button(extract_box, text="Browse", command=lambda: self.choose_output_dir(self.extract_dest, "Choose extraction folder")).grid(
            row=0, column=2, sticky="w", padx=(0, 8), pady=(10, 6)
        )
        ttk.Button(extract_box, text="Extract Selected Archives", command=self.extract_selected_archives).grid(
            row=0, column=3, sticky="w", pady=(10, 6)
        )
        extract_box.columnconfigure(1, weight=1)

        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(8, 0))

    def add_folder(self) -> None:
        raw = filedialog.askdirectory(title="Select folder to include")
        if raw:
            path = Path(raw)
            if path not in self.inputs:
                self.inputs.append(path)
                self.listbox.insert(END, str(path))

    def pick_output_archive(self) -> None:
        fmt = self.archive_format.get()
        ext_map = {
            "zip": ".zip",
            "tar": ".tar",
            "tar.gz": ".tar.gz",
            "tar.bz2": ".tar.bz2",
            "tar.xz": ".tar.xz",
        }
        extension = ext_map.get(fmt, ".zip")
        path = filedialog.asksaveasfilename(
            title="Save archive as",
            defaultextension=extension,
            filetypes=[("Archive", f"*{extension}"), ("All files", "*.*")],
        )
        if path:
            self.output_archive.set(path)

    def create_archive(self) -> None:
        if not self.inputs:
            messagebox.showwarning(APP_TITLE, "Add files or folders before creating an archive.")
            return
        out_path = Path(self.output_archive.get().strip())
        fmt = self.archive_format.get().lower()
        ensure_dir(out_path.parent)

        def work() -> None:
            self.app.engine.create_archive(self.inputs, out_path, fmt)
            self.log(f"Created archive: {out_path}")
            self.app.call_ui(lambda: self.status_var.set(f"Created archive: {out_path.name}"))

        self.run_async(work, done_message=f"Archive created: {out_path}")

    def extract_selected_archives(self) -> None:
        selected_indices = list(self.listbox.curselection())
        if not selected_indices:
            messagebox.showwarning(APP_TITLE, "Select at least one archive in the queue.")
            return
        archives = [self.inputs[i] for i in selected_indices]
        dest = Path(self.extract_dest.get().strip())
        ensure_dir(dest)

        def work() -> None:
            failures = []
            for item in archives:
                if not item.exists() or not item.is_file():
                    failures.append(f"{item} is not a file archive.")
                    continue
                try:
                    out_dir = dest / item.stem
                    self.app.engine.extract_archive(item, out_dir)
                    self.log(f"Extracted {item.name} -> {out_dir}")
                except Exception as exc:
                    failures.append(f"{item.name}: {exc}")
            if failures:
                raise RuntimeError(f"{len(failures)} archive(s) failed. First issue: {failures[0]}")
            self.app.call_ui(lambda: self.status_var.set(f"Extracted {len(archives)} archive(s)."))

        self.run_async(work, done_message=f"Extracted {len(archives)} archive(s).")


class RenameOrganizeTab(ModuleTab):
    tab_name = "Rename / Organize"

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.files: list[Path] = []
        self.find_var = StringVar(value="")
        self.replace_var = StringVar(value="")
        self.regex_var = BooleanVar(value=False)
        self.prefix_var = StringVar(value="")
        self.suffix_var = StringVar(value="")
        self.number_var = BooleanVar(value=False)
        self.start_num_var = IntVar(value=1)
        self.status_var = StringVar(value="Ready.")
        self.preview_rows: list[tuple[Path, Path]] = []
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        controls = ttk.Frame(outer)
        controls.pack(fill="x")
        ttk.Button(controls, text="Add Files", command=lambda: self.add_files_to_queue(self.files, self.listbox)).pack(side="left")
        ttk.Button(controls, text="Clear", command=lambda: self.clear_queue(self.files, self.listbox)).pack(side="left", padx=6)
        ttk.Button(controls, text="Build Preview", command=self.build_preview).pack(side="left", padx=6)
        ttk.Button(controls, text="Apply Rename", command=self.apply_rename).pack(side="right")

        queue = ttk.Frame(outer)
        queue.pack(fill="both", expand=True, pady=(8, 8))
        self.listbox = tk.Listbox(queue, selectmode=SINGLE, height=8)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(queue, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scroll.set)

        rules = ttk.LabelFrame(outer, text="Rename Rules")
        rules.pack(fill="x")
        ttk.Label(rules, text="Find").grid(row=0, column=0, sticky="w", padx=(10, 6), pady=(10, 6))
        ttk.Entry(rules, textvariable=self.find_var).grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(10, 6))
        ttk.Label(rules, text="Replace").grid(row=0, column=2, sticky="w", padx=(10, 6), pady=(10, 6))
        ttk.Entry(rules, textvariable=self.replace_var).grid(row=0, column=3, sticky="ew", padx=(0, 12), pady=(10, 6))
        ttk.Checkbutton(rules, text="Regex", variable=self.regex_var).grid(row=0, column=4, sticky="w", pady=(10, 6))

        ttk.Label(rules, text="Prefix").grid(row=1, column=0, sticky="w", padx=(10, 6), pady=(6, 10))
        ttk.Entry(rules, textvariable=self.prefix_var).grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(6, 10))
        ttk.Label(rules, text="Suffix").grid(row=1, column=2, sticky="w", padx=(10, 6), pady=(6, 10))
        ttk.Entry(rules, textvariable=self.suffix_var).grid(row=1, column=3, sticky="ew", padx=(0, 12), pady=(6, 10))
        ttk.Checkbutton(rules, text="Number files", variable=self.number_var).grid(row=1, column=4, sticky="w", pady=(6, 10))
        ttk.Label(rules, text="Start").grid(row=1, column=5, sticky="w", padx=(8, 6), pady=(6, 10))
        ttk.Spinbox(rules, from_=1, to=99999, textvariable=self.start_num_var, width=8).grid(row=1, column=6, sticky="w", pady=(6, 10))
        rules.columnconfigure(1, weight=1)
        rules.columnconfigure(3, weight=1)

        preview_box = ttk.LabelFrame(outer, text="Preview")
        preview_box.pack(fill="both", expand=True, pady=(8, 0))
        self.preview_tree = ttk.Treeview(preview_box, columns=("old", "new"), show="headings")
        self.preview_tree.heading("old", text="Current name")
        self.preview_tree.heading("new", text="New name")
        self.preview_tree.column("old", width=500)
        self.preview_tree.column("new", width=500)
        self.preview_tree.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))

    def _build_new_name(self, source: Path, index: int) -> str:
        stem = source.stem
        find_text = self.find_var.get()
        replace_text = self.replace_var.get()
        if find_text:
            if self.regex_var.get():
                stem = re.sub(find_text, replace_text, stem)
            else:
                stem = stem.replace(find_text, replace_text)
        stem = f"{self.prefix_var.get()}{stem}{self.suffix_var.get()}"
        if self.number_var.get():
            number = self.start_num_var.get() + index
            stem = f"{number:04d}_{stem}"
        return f"{stem}{source.suffix}"

    def build_preview(self) -> None:
        if not self.files:
            messagebox.showwarning(APP_TITLE, "Add files before previewing rename rules.")
            return
        self.preview_rows.clear()
        for row in self.preview_tree.get_children():
            self.preview_tree.delete(row)

        for index, path in enumerate(self.files):
            candidate_name = self._build_new_name(path, index)
            target = path.with_name(candidate_name)
            if target.exists() and target != path:
                base = target.stem
                suffix = target.suffix
                parent = target.parent
                counter = 1
                while True:
                    fallback = parent / f"{base}_{counter}{suffix}"
                    if not fallback.exists():
                        target = fallback
                        break
                    counter += 1
            self.preview_rows.append((path, target))
            self.preview_tree.insert("", "end", values=(path.name, target.name))

        self.status_var.set(f"Prepared preview for {len(self.preview_rows)} file(s).")

    def apply_rename(self) -> None:
        if not self.preview_rows:
            messagebox.showwarning(APP_TITLE, "Build preview first.")
            return

        def work() -> None:
            completed = 0
            for source, target in self.preview_rows:
                if source == target:
                    continue
                source.rename(target)
                completed += 1
                self.log(f"Renamed {source.name} -> {target.name}")
            self.app.call_ui(lambda: self.status_var.set(f"Renamed {completed} file(s)."))
            self.app.call_ui(lambda: self.clear_queue(self.files, self.listbox))
            self.app.call_ui(self._clear_preview)

        self.run_async(work, done_message="Rename operation completed.")

    def _clear_preview(self) -> None:
        for row in self.preview_tree.get_children():
            self.preview_tree.delete(row)
        self.preview_rows.clear()


class DuplicateFinderTab(ModuleTab):
    tab_name = "Duplicate Finder"

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.folder_var = StringVar(value=str(Path.home()))
        self.min_size_mb = IntVar(value=1)
        self.status_var = StringVar(value="Ready.")
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        top = ttk.Frame(outer)
        top.pack(fill="x")
        ttk.Label(top, text="Folder").pack(side="left")
        ttk.Entry(top, textvariable=self.folder_var).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(top, text="Browse", command=lambda: self.choose_output_dir(self.folder_var, "Choose folder to scan")).pack(side="left")
        ttk.Label(top, text="Min size (MB)").pack(side="left", padx=(14, 6))
        ttk.Spinbox(top, from_=0, to=2048, textvariable=self.min_size_mb, width=8).pack(side="left")
        ttk.Button(top, text="Scan Duplicates", command=self.scan).pack(side="right")

        self.tree = ttk.Treeview(outer, columns=("hash", "size", "path"), show="headings")
        self.tree.heading("hash", text="SHA256")
        self.tree.heading("size", text="Size")
        self.tree.heading("path", text="File path")
        self.tree.column("hash", width=220)
        self.tree.column("size", width=120)
        self.tree.column("path", width=900)
        self.tree.pack(fill="both", expand=True, pady=(8, 0))
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))

    def scan(self) -> None:
        root = Path(self.folder_var.get().strip())
        if not root.exists():
            messagebox.showerror(APP_TITLE, "Scan folder does not exist.")
            return
        min_bytes = self.min_size_mb.get() * 1024 * 1024

        def work() -> None:
            candidates: dict[int, list[Path]] = {}
            total_seen = 0
            for current_root, _, files in os.walk(root):
                for name in files:
                    path = Path(current_root) / name
                    try:
                        size = path.stat().st_size
                    except Exception:
                        continue
                    total_seen += 1
                    if size < min_bytes:
                        continue
                    candidates.setdefault(size, []).append(path)

            duplicates: list[tuple[str, int, Path]] = []
            for size, group in candidates.items():
                if len(group) < 2:
                    continue
                by_hash: dict[str, list[Path]] = {}
                for item in group:
                    try:
                        digest = hash_file(item, "sha256")
                    except Exception:
                        continue
                    by_hash.setdefault(digest, []).append(item)
                for digest, hashed_group in by_hash.items():
                    if len(hashed_group) > 1:
                        for file_path in hashed_group:
                            duplicates.append((digest, size, file_path))

            def render() -> None:
                for row in self.tree.get_children():
                    self.tree.delete(row)
                for digest, size, path in duplicates:
                    self.tree.insert("", "end", values=(digest, human_size(size), str(path)))
                self.status_var.set(
                    f"Scanned {total_seen} files. Found {len(duplicates)} duplicate entries across matching hashes."
                )

            self.app.call_ui(render)

        self.run_async(work, done_message="Duplicate scan complete.")


class StorageAnalyzerTab(ModuleTab):
    tab_name = "Storage Analyzer"

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.folder_var = StringVar(value=str(Path.home()))
        self.top_n_var = IntVar(value=30)
        self.status_var = StringVar(value="Ready.")
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        top = ttk.Frame(outer)
        top.pack(fill="x")
        ttk.Label(top, text="Folder").pack(side="left")
        ttk.Entry(top, textvariable=self.folder_var).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(top, text="Browse", command=lambda: self.choose_output_dir(self.folder_var, "Choose folder to analyze")).pack(side="left")
        ttk.Label(top, text="Top N").pack(side="left", padx=(14, 6))
        ttk.Spinbox(top, from_=5, to=200, textvariable=self.top_n_var, width=8).pack(side="left")
        ttk.Button(top, text="Analyze", command=self.analyze).pack(side="right")

        split = ttk.Panedwindow(outer, orient="vertical")
        split.pack(fill="both", expand=True, pady=(8, 0))

        file_box = ttk.Labelframe(split, text="Largest Files")
        folder_box = ttk.Labelframe(split, text="Largest Folders")
        split.add(file_box, weight=1)
        split.add(folder_box, weight=1)

        self.file_tree = ttk.Treeview(file_box, columns=("size", "path"), show="headings")
        self.file_tree.heading("size", text="Size")
        self.file_tree.heading("path", text="File path")
        self.file_tree.column("size", width=120)
        self.file_tree.column("path", width=1020)
        self.file_tree.pack(fill="both", expand=True, padx=8, pady=8)

        self.folder_tree = ttk.Treeview(folder_box, columns=("size", "path"), show="headings")
        self.folder_tree.heading("size", text="Size")
        self.folder_tree.heading("path", text="Folder path")
        self.folder_tree.column("size", width=120)
        self.folder_tree.column("path", width=1020)
        self.folder_tree.pack(fill="both", expand=True, padx=8, pady=8)

        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))

    def analyze(self) -> None:
        root = Path(self.folder_var.get().strip())
        if not root.exists():
            messagebox.showerror(APP_TITLE, "Analysis folder does not exist.")
            return
        top_n = int(self.top_n_var.get())

        def work() -> None:
            file_sizes: list[tuple[Path, int]] = []
            folder_sizes: dict[Path, int] = {}
            scanned_files = 0
            for current_root, _, files in os.walk(root):
                root_path = Path(current_root)
                for name in files:
                    path = root_path / name
                    try:
                        size = path.stat().st_size
                    except Exception:
                        continue
                    scanned_files += 1
                    file_sizes.append((path, size))
                    cursor = path.parent
                    while True:
                        folder_sizes[cursor] = folder_sizes.get(cursor, 0) + size
                        if cursor == root:
                            break
                        if root not in cursor.parents and cursor != root:
                            break
                        cursor = cursor.parent

            largest_files = sorted(file_sizes, key=lambda row: row[1], reverse=True)[:top_n]
            largest_folders = sorted(folder_sizes.items(), key=lambda row: row[1], reverse=True)[:top_n]

            def render() -> None:
                for row in self.file_tree.get_children():
                    self.file_tree.delete(row)
                for row in self.folder_tree.get_children():
                    self.folder_tree.delete(row)
                for file_path, size in largest_files:
                    self.file_tree.insert("", "end", values=(human_size(size), str(file_path)))
                for folder_path, size in largest_folders:
                    self.folder_tree.insert("", "end", values=(human_size(size), str(folder_path)))
                self.status_var.set(
                    f"Scanned {scanned_files} files. Showing top {top_n} largest files and folders."
                )

            self.app.call_ui(render)

        self.run_async(work, done_message="Storage analysis complete.")


class ChecksumsTab(ModuleTab):
    tab_name = "Checksums / Integrity"

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.files: list[Path] = []
        self.algo_var = StringVar(value="sha256")
        self.status_var = StringVar(value="Ready.")
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        controls = ttk.Frame(outer)
        controls.pack(fill="x")
        ttk.Button(controls, text="Add Files", command=lambda: self.add_files_to_queue(self.files, self.listbox)).pack(side="left")
        ttk.Button(controls, text="Clear", command=lambda: self.clear_queue(self.files, self.listbox)).pack(side="left", padx=6)
        ttk.Label(controls, text="Algorithm").pack(side="left", padx=(18, 6))
        ttk.Combobox(controls, textvariable=self.algo_var, values=["md5", "sha1", "sha256", "sha512"], state="readonly", width=10).pack(side="left")
        ttk.Button(controls, text="Generate", command=self.generate).pack(side="right")

        queue = ttk.Frame(outer)
        queue.pack(fill="both", expand=True, pady=(8, 8))
        self.listbox = tk.Listbox(queue, selectmode=SINGLE, height=6)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(queue, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scroll.set)

        result_box = ttk.LabelFrame(outer, text="Hash Results")
        result_box.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(result_box, columns=("file", "hash"), show="headings")
        self.tree.heading("file", text="File")
        self.tree.heading("hash", text="Digest")
        self.tree.column("file", width=500)
        self.tree.column("hash", width=640)
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(8, 0))
        ttk.Button(bottom, text="Save Report", command=self.save_report).pack(side="right")
        ttk.Button(bottom, text="Verify Report", command=self.verify_report).pack(side="right", padx=(0, 8))
        ttk.Label(bottom, textvariable=self.status_var).pack(side="left")

    def generate(self) -> None:
        if not self.files:
            messagebox.showwarning(APP_TITLE, "Add files before generating hashes.")
            return
        algorithm = self.algo_var.get()
        total = len(self.files)

        def work() -> None:
            rows = []
            for index, path in enumerate(self.files, start=1):
                digest = hash_file(path, algorithm)
                rows.append((str(path), digest))
                self.app.call_ui(lambda i=index, total_files=total: self.status_var.set(f"Hashing {i}/{total_files}..."))

            def render() -> None:
                for row in self.tree.get_children():
                    self.tree.delete(row)
                for file_path, digest in rows:
                    self.tree.insert("", "end", values=(file_path, digest))
                self.status_var.set(f"Generated {algorithm} hashes for {total} file(s).")

            self.app.call_ui(render)

        self.run_async(work, done_message=f"Generated hashes for {total} file(s).")

    def save_report(self) -> None:
        if not self.tree.get_children():
            messagebox.showwarning(APP_TITLE, "Generate hashes first.")
            return
        path = filedialog.asksaveasfilename(
            title="Save checksum report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        lines = []
        for row in self.tree.get_children():
            file_path, digest = self.tree.item(row, "values")
            lines.append(f"{digest}  {file_path}")
        Path(path).write_text("\n".join(lines), encoding="utf-8")
        self.status_var.set(f"Saved report: {path}")

    def verify_report(self) -> None:
        path = filedialog.askopenfilename(
            title="Open checksum report",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        report_path = Path(path)
        lines = report_path.read_text(encoding="utf-8", errors="replace").splitlines()
        checked = 0
        mismatches = []

        for line in lines:
            line = line.strip()
            if not line or "  " not in line:
                continue
            digest, file_path = line.split("  ", 1)
            target = Path(file_path.strip())
            if not target.exists():
                mismatches.append(f"Missing: {target}")
                continue
            current = hash_file(target, self.algo_var.get())
            checked += 1
            if current.lower() != digest.lower():
                mismatches.append(f"Mismatch: {target}")

        if mismatches:
            preview = "\n".join(mismatches[:10])
            messagebox.showwarning(APP_TITLE, f"Verification completed with issues ({len(mismatches)}):\n{preview}")
            self.status_var.set(f"Verification found {len(mismatches)} issue(s).")
        else:
            messagebox.showinfo(APP_TITLE, f"Verification OK for {checked} file(s).")
            self.status_var.set(f"Verification passed for {checked} file(s).")


class SubtitlesTab(ModuleTab):
    tab_name = "Subtitles"

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.files: list[Path] = []
        self.target_var = StringVar(value="vtt")
        self.output_dir = StringVar(value=str(self.app.default_output_root / "subtitles"))
        self.status_var = StringVar(value="Ready.")
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)
        ttk.Label(
            outer,
            text=(
                "Starter subtitle conversion supports SRT <-> VTT directly. "
                "ASS/SSA files can be copied/renamed as placeholders for advanced conversion."
            ),
            wraplength=1200,
        ).pack(anchor="w", pady=(0, 8))

        controls = ttk.Frame(outer)
        controls.pack(fill="x")
        ttk.Button(controls, text="Add Subtitle Files", command=lambda: self.add_files_to_queue(self.files, self.listbox)).pack(side="left")
        ttk.Button(controls, text="Clear", command=lambda: self.clear_queue(self.files, self.listbox)).pack(side="left", padx=6)
        ttk.Label(controls, text="Target format").pack(side="left", padx=(18, 6))
        ttk.Combobox(controls, textvariable=self.target_var, values=["srt", "vtt", "ass", "ssa"], state="readonly", width=10).pack(side="left")
        ttk.Button(controls, text="Convert", command=self.convert).pack(side="right")

        queue = ttk.Frame(outer)
        queue.pack(fill="both", expand=True, pady=(8, 8))
        self.listbox = tk.Listbox(queue, selectmode=SINGLE)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(queue, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scroll.set)

        out_row = ttk.Frame(outer)
        out_row.pack(fill="x")
        ttk.Label(out_row, text="Output folder:").pack(side="left")
        ttk.Entry(out_row, textvariable=self.output_dir).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(out_row, text="Browse", command=lambda: self.choose_output_dir(self.output_dir, "Choose output folder")).pack(side="left")
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))

    def convert(self) -> None:
        if not self.files:
            messagebox.showwarning(APP_TITLE, "Add subtitle files first.")
            return
        target_fmt = self.target_var.get().lower()
        out_dir = Path(self.output_dir.get().strip())
        ensure_dir(out_dir)
        total = len(self.files)

        def work() -> None:
            failures = []
            for index, path in enumerate(list(self.files), start=1):
                suffix = path.suffix.lower()
                out_path = out_dir / f"{path.stem}.{target_fmt}"
                try:
                    resolved = self.app.resolve_output_path(out_path, context=f"Converted subtitle for {path.name}")
                    if resolved is None:
                        raise RuntimeError("Operation canceled by user.")
                    out_path = resolved
                    text = path.read_text(encoding="utf-8", errors="replace")
                    if suffix == ".srt" and target_fmt == "vtt":
                        out_path.write_text(srt_to_vtt(text), encoding="utf-8")
                    elif suffix == ".vtt" and target_fmt == "srt":
                        out_path.write_text(vtt_to_srt(text), encoding="utf-8")
                    elif suffix in {".ass", ".ssa"} and target_fmt in {"ass", "ssa"}:
                        out_path.write_text(text, encoding="utf-8")
                    elif suffix == f".{target_fmt}":
                        out_path.write_text(text, encoding="utf-8")
                    else:
                        raise RuntimeError("This starter currently supports direct SRT/VTT conversion.")
                    self.log(f"{path.name} -> {out_path.name}")
                except Exception as exc:
                    failures.append(f"{path.name}: {exc}")
                self.app.call_ui(lambda i=index, total_files=total: self.status_var.set(f"Processing {i}/{total_files}..."))
                self.app.call_ui(lambda p=path: self.remove_path_from_queue(self.files, self.listbox, p))
            if failures:
                raise RuntimeError(f"{len(failures)} file(s) failed. First issue: {failures[0]}")
            self.app.call_ui(lambda: self.status_var.set(f"Converted {total} subtitle file(s)."))

        self.run_async(work, done_message=f"Subtitle conversion finished for {total} file(s).")


class PresetsBatchTab(ModuleTab):
    tab_name = "Presets / Batch Jobs"

    PHASE1_MODULES = ["Convert", "Compress", "Extract"]

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.preset_file = self.app.appdata_dir / "suite_presets.json"
        self.presets: dict[str, dict[str, Any]] = {}
        self.jobs: list[dict[str, Any]] = []

        self.module_var = StringVar(value="Convert")
        self.preset_name_var = StringVar(value="")
        self.queue_preset_var = StringVar(value="")
        self.queue_output_var = StringVar(value=str(self.app.default_output_root / "batch"))
        self.status_var = StringVar(value="Ready.")

        self._load_presets()
        self._build()
        self._refresh_widgets()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        split = ttk.Panedwindow(outer, orient="horizontal")
        split.pack(fill="both", expand=True)

        left = ttk.Labelframe(split, text="Preset Manager")
        right = ttk.Labelframe(split, text="Batch Queue")
        split.add(left, weight=1)
        split.add(right, weight=2)

        ttk.Label(left, text="Module").pack(anchor="w", padx=10, pady=(10, 2))
        ttk.Combobox(left, textvariable=self.module_var, values=self.PHASE1_MODULES, state="readonly").pack(fill="x", padx=10)
        ttk.Label(left, text="Preset name").pack(anchor="w", padx=10, pady=(10, 2))
        ttk.Entry(left, textvariable=self.preset_name_var).pack(fill="x", padx=10)
        ttk.Button(left, text="Capture Current Module Settings", command=self.capture_preset).pack(fill="x", padx=10, pady=(10, 4))
        ttk.Button(left, text="Apply Selected Preset to Module", command=self.apply_preset_to_module).pack(fill="x", padx=10, pady=4)
        ttk.Button(left, text="Delete Selected Preset", command=self.delete_preset).pack(fill="x", padx=10, pady=4)

        preset_box = ttk.Frame(left)
        preset_box.pack(fill="both", expand=True, padx=10, pady=(10, 10))
        self.preset_list = tk.Listbox(preset_box)
        self.preset_list.pack(side="left", fill="both", expand=True)
        preset_scroll = ttk.Scrollbar(preset_box, orient="vertical", command=self.preset_list.yview)
        preset_scroll.pack(side="right", fill="y")
        self.preset_list.configure(yscrollcommand=preset_scroll.set)

        queue_controls = ttk.Frame(right)
        queue_controls.pack(fill="x", padx=10, pady=(10, 6))
        ttk.Label(queue_controls, text="Preset").pack(side="left")
        self.queue_preset_combo = ttk.Combobox(queue_controls, textvariable=self.queue_preset_var, state="readonly", width=26)
        self.queue_preset_combo.pack(side="left", padx=(8, 12))
        ttk.Button(queue_controls, text="Add Files as Jobs", command=self.add_jobs).pack(side="left")
        ttk.Button(queue_controls, text="Remove Selected Job", command=self.remove_job).pack(side="left", padx=6)
        ttk.Button(queue_controls, text="Clear Jobs", command=self.clear_jobs).pack(side="left")

        out_row = ttk.Frame(right)
        out_row.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Label(out_row, text="Queue output folder:").pack(side="left")
        ttk.Entry(out_row, textvariable=self.queue_output_var).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(out_row, text="Browse", command=lambda: self.choose_output_dir(self.queue_output_var, "Choose batch output folder")).pack(side="left")

        self.job_tree = ttk.Treeview(right, columns=("module", "preset", "file", "output"), show="headings")
        self.job_tree.heading("module", text="Module")
        self.job_tree.heading("preset", text="Preset")
        self.job_tree.heading("file", text="Input file")
        self.job_tree.heading("output", text="Output folder")
        self.job_tree.column("module", width=120)
        self.job_tree.column("preset", width=160)
        self.job_tree.column("file", width=460)
        self.job_tree.column("output", width=340)
        self.job_tree.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        bottom = ttk.Frame(right)
        bottom.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(bottom, text="Export Queue JSON", command=self.export_jobs).pack(side="left")
        ttk.Button(bottom, text="Run Queue", command=self.run_queue).pack(side="right")

        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))

    def _load_presets(self) -> None:
        if self.preset_file.exists():
            try:
                data = json.loads(self.preset_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.presets = data
            except Exception:
                self.presets = {}

    def _save_presets(self) -> None:
        self.preset_file.write_text(json.dumps(self.presets, indent=2, ensure_ascii=False), encoding="utf-8")

    def _refresh_widgets(self) -> None:
        self.preset_list.delete(0, END)
        ordered = sorted(self.presets.keys())
        for name in ordered:
            module_name = self.presets[name].get("module", "Unknown")
            self.preset_list.insert(END, f"{name} [{module_name}]")
        self.queue_preset_combo.configure(values=ordered)
        if ordered and not self.queue_preset_var.get():
            self.queue_preset_var.set(ordered[0])

    def _selected_preset_name(self) -> str | None:
        selected = self.preset_list.curselection()
        if not selected:
            return None
        label = self.preset_list.get(selected[0])
        return label.rsplit(" [", 1)[0].strip()

    def _module_tab(self, module_name: str):
        tab = self.app.tabs.get(module_name)
        if not tab:
            raise RuntimeError(f"Module tab not found: {module_name}")
        return tab

    def capture_preset(self) -> None:
        module_name = self.module_var.get()
        preset_name = self.preset_name_var.get().strip()
        if not preset_name:
            messagebox.showwarning(APP_TITLE, "Enter a preset name.")
            return
        module_tab = self._module_tab(module_name)
        if not hasattr(module_tab, "export_preset"):
            messagebox.showerror(APP_TITLE, f"{module_name} does not support presets in this starter.")
            return
        payload = module_tab.export_preset()
        self.presets[preset_name] = {"module": module_name, "config": payload}
        self._save_presets()
        self._refresh_widgets()
        self.status_var.set(f"Saved preset '{preset_name}' for {module_name}.")

    def apply_preset_to_module(self) -> None:
        preset_name = self._selected_preset_name() or self.queue_preset_var.get().strip()
        if not preset_name or preset_name not in self.presets:
            messagebox.showwarning(APP_TITLE, "Select a preset first.")
            return
        preset = self.presets[preset_name]
        module_name = preset.get("module", "")
        module_tab = self._module_tab(module_name)
        if not hasattr(module_tab, "apply_preset"):
            messagebox.showerror(APP_TITLE, f"{module_name} cannot apply presets in this starter.")
            return
        module_tab.apply_preset(preset.get("config", {}))
        self.app.select_tab(module_name)
        self.status_var.set(f"Applied preset '{preset_name}' to {module_name}.")

    def delete_preset(self) -> None:
        preset_name = self._selected_preset_name()
        if not preset_name:
            messagebox.showwarning(APP_TITLE, "Select a preset to delete.")
            return
        self.presets.pop(preset_name, None)
        self._save_presets()
        self._refresh_widgets()
        self.status_var.set(f"Deleted preset '{preset_name}'.")

    def add_jobs(self) -> None:
        preset_name = self.queue_preset_var.get().strip()
        if not preset_name or preset_name not in self.presets:
            messagebox.showwarning(APP_TITLE, "Select a valid preset before adding jobs.")
            return
        files = filedialog.askopenfilenames(title="Choose files for batch queue")
        if not files:
            return
        output_dir = self.queue_output_var.get().strip()
        for raw in files:
            preset = self.presets[preset_name]
            module_name = str(preset.get("module", "Convert"))
            job = {
                "module": module_name,
                "preset": preset_name,
                "input": raw,
                "output": output_dir,
            }
            self.jobs.append(job)
            self.job_tree.insert("", "end", values=(module_name, preset_name, raw, output_dir))
        self.status_var.set(f"Queue now has {len(self.jobs)} job(s).")

    def remove_job(self) -> None:
        selected = self.job_tree.selection()
        if not selected:
            return
        for item in selected:
            values = self.job_tree.item(item, "values")
            self.job_tree.delete(item)
            for index, job in enumerate(list(self.jobs)):
                if (job["module"], job["preset"], job["input"], job["output"]) == tuple(values):
                    self.jobs.pop(index)
                    break
        self.status_var.set(f"Queue now has {len(self.jobs)} job(s).")

    def clear_jobs(self) -> None:
        self.jobs.clear()
        for item in self.job_tree.get_children():
            self.job_tree.delete(item)
        self.status_var.set("Queue cleared.")

    def export_jobs(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save queue JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        Path(path).write_text(json.dumps(self.jobs, indent=2, ensure_ascii=False), encoding="utf-8")
        self.status_var.set(f"Exported queue to {path}")

    def run_queue(self) -> None:
        if not self.jobs:
            messagebox.showwarning(APP_TITLE, "Add jobs before running queue.")
            return
        total = len(self.jobs)

        def work() -> None:
            failures = []
            for index, job in enumerate(self.jobs, start=1):
                module_name = str(job.get("module"))
                preset_name = str(job.get("preset"))
                source = Path(str(job.get("input")))
                output_dir = Path(str(job.get("output")))
                ensure_dir(output_dir)
                preset = self.presets.get(preset_name)
                if not preset:
                    failures.append(f"Missing preset '{preset_name}' for job {index}")
                    continue
                config = dict(preset.get("config", {}))
                try:
                    if module_name == "Convert":
                        target = str(config.get("target_format", "png"))
                        self.app.engine.convert_file(source, output_dir, target, config)
                    elif module_name == "Compress":
                        mode_key = str(config.get("mode_key", "image_quality"))
                        if mode_key == "zip_batch":
                            self.app.engine.create_zip_archive([source], output_dir, level=int(config.get("zip_level", 6)))
                        else:
                            self.app.engine.compress_file(source, output_dir, mode_key, config)
                    elif module_name == "Extract":
                        operation_key = str(config.get("operation_key", "audio_from_video"))
                        self.app.engine.extract_from_media(source, output_dir, operation_key, config)
                    else:
                        failures.append(f"Unsupported module '{module_name}' in job {index}")
                except Exception as exc:
                    failures.append(f"Job {index} ({source.name}) failed: {exc}")

                self.app.call_ui(lambda i=index, total_jobs=total: self.status_var.set(f"Running job {i}/{total_jobs}..."))

            if failures:
                raise RuntimeError(f"{len(failures)} job(s) failed. First issue: {failures[0]}")
            self.app.call_ui(lambda: self.status_var.set(f"Batch queue finished successfully for {total} job(s)."))

        self.run_async(work, done_message=f"Batch queue completed {total} job(s).")


def main() -> None:
    root = tk.Tk()
    SuiteApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
