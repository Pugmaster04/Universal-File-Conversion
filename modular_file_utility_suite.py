import ctypes
import colorsys
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
import tempfile
import threading
import time
import urllib.error
import urllib.parse
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
    from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError
except Exception:
    Image = None
    ImageFilter = None
    ImageOps = None
    UnidentifiedImageError = Exception

try:
    from pillow_heif import register_heif_opener
except Exception:
    register_heif_opener = None
else:
    register_heif_opener()

try:
    import yaml
except Exception:
    yaml = None

try:
    import imageio_ffmpeg
except Exception:
    imageio_ffmpeg = None

try:
    import windnd
except Exception:
    windnd = None

try:
    from torrentool.api import Torrent
except Exception:
    Torrent = None


APP_TITLE = "Universal Conversion Hub (UCH)"
APP_SLUG = "UniversalConversionHubUCH"
LEGACY_APP_SLUGS = ("UniversalConversionHubHCB", "UniversalFileUtilitySuite")
# Versioning policy:
# - Major releases use X.0
# - Secondary feature releases use X.Y
# - Patch releases use X.Y.Z
APP_VERSION = "0.7.3"
DEFAULT_UPDATE_MANIFEST_URL = ""
APP_EXE_BASENAME = "UniversalConversionHub_UCH"
UPDATER_EXE_BASENAME = "UniversalConversionHub_UCH_Updater"
LEGACY_UPDATER_EXE_BASENAMES = ("UniversalConversionHub_HCB_Updater", "UniversalFileUtilitySuite_Updater")
LEGACY_WINDOW_TITLES = (
    APP_TITLE,
    "Universal Conversion Hub (HCB)",
    "Universal File Utility Suite - Modular Starter",
)
GUIDE_FILENAMES = (
    "README.md",
    "HOW_TO_Universal_File_Utility_Suite.txt",
    "README_build.txt",
)

TORRENT_SOURCE_EXTS = {".torrent"}
METALINK_SOURCE_EXTS = {".meta4", ".metalink"}
ARIA2_METADATA_SOURCE_EXTS = TORRENT_SOURCE_EXTS | METALINK_SOURCE_EXTS
ARIA2_PROGRESS_RE = re.compile(r"\((\d+)%\)")


def hidden_console_process_kwargs() -> dict[str, Any]:
    if os.name != "nt":
        return {}
    kwargs: dict[str, Any] = {}
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if creationflags:
        kwargs["creationflags"] = creationflags
    startupinfo_type = getattr(subprocess, "STARTUPINFO", None)
    use_show_window = getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    sw_hide = getattr(subprocess, "SW_HIDE", 0)
    if startupinfo_type and use_show_window:
        startupinfo = startupinfo_type()
        startupinfo.dwFlags |= use_show_window
        startupinfo.wShowWindow = sw_hide
        kwargs["startupinfo"] = startupinfo
    return kwargs

HEIF_IMAGE_EXTS = {
    ".heic",
    ".heif",
    ".avif",
}

CAMERA_RAW_IMAGE_EXTS = {
    ".raw",
    ".dng",
    ".cr2",
    ".cr3",
    ".nef",
    ".nrw",
    ".arw",
    ".srf",
    ".sr2",
    ".raf",
    ".orf",
    ".rw2",
    ".pef",
    ".erf",
    ".kdc",
    ".mos",
    ".iiq",
    ".3fr",
}

IMAGEMAGICK_IMAGE_INPUT_EXTS = {
    ".jxl",
} | CAMERA_RAW_IMAGE_EXTS

IMAGEMAGICK_IMAGE_TARGET_FORMATS = {
    "jxl",
}

LOSSY_IMAGE_FORMATS = {
    "jpg",
    "jpeg",
    "webp",
    "heic",
    "heif",
    "avif",
}
JPEG_LIKE_IMAGE_FORMATS = {
    "jpg",
    "jpeg",
}

IMAGE_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".jpe",
    ".jfif",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
    ".ico",
} | (HEIF_IMAGE_EXTS if register_heif_opener is not None else set())

SUPPORTED_IMAGE_INPUT_EXTS = IMAGE_EXTS | IMAGEMAGICK_IMAGE_INPUT_EXTS

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

IMAGE_FORMATS = ["png", "jpg", "webp", "bmp", "gif", "tiff", "ico", "jxl"] + (
    ["heic", "heif", "avif"] if register_heif_opener is not None else []
)
MEDIA_FORMATS = ["mp4", "mkv", "mov", "webm", "mp3", "wav", "flac", "ogg", "m4a"]
DATA_FORMATS = ["json", "yaml", "csv", "tsv"]
DOC_FORMATS = ["pdf", "docx", "odt", "html", "md", "txt", "epub", "rtf"]
ARCHIVE_FORMATS = ["zip", "tar", "tar.gz", "tar.bz2", "tar.xz"]
ARCHIVE_INPUT_EXTS = {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z"}
AUDIO_BITRATE_HELP_TEXT = "Higher bitrate = better audio and larger files. 128k-192k is a common balance."
VIDEO_PRESET_HELP_TEXT = "Controls speed vs compression efficiency. Slower presets take longer but can make smaller files."
VIDEO_CRF_HELP_TEXT = "Lower CRF = higher quality and larger files. Higher CRF = smaller files and lower quality. Typical: 18-23 high quality."
ZIP_LEVEL_HELP_TEXT = "Higher ZIP level = slower compression and smaller archives. Lower level = faster compression and larger archives."
IMAGE_RESIZE_HELP_TEXT = (
    "Resize images to fit within the chosen width and height while keeping aspect ratio. "
    "Use 0 to leave that dimension unconstrained."
)
IMAGE_SHARPEN_HELP_TEXT = "Apply a light unsharp mask after resize/export. 0 disables sharpening."
AUDIO_SAMPLE_RATE_HELP_TEXT = (
    "Keep source preserves the original rate. 44.1 kHz and 48 kHz are common delivery targets."
)
AUDIO_CHANNELS_HELP_TEXT = (
    "Keep source preserves the original channel layout. Mono reduces size; stereo is the common default."
)
AUDIO_CLEANUP_HELP_TEXT = (
    "Normalization evens out loudness. Silence trim removes quiet leading and trailing sections."
)
VIDEO_MODE_HELP_TEXT = (
    "Remux repackages without re-encoding. Trim makes a clip. Stream Prep re-encodes for delivery. "
    "Thumbnail Sheet creates a contact image."
)
VIDEO_TRIM_HELP_TEXT = "Use HH:MM:SS, MM:SS, or seconds. Start and end values are optional, but at least one is required."
VIDEO_THUMBNAIL_HELP_TEXT = "Generate a contact sheet by sampling frames at a fixed interval."
AUDIO_PROCESS_FORMATS = ["mp3", "wav", "flac", "ogg", "m4a"]
VIDEO_REMUX_FORMATS = ["mp4", "mkv", "mov"]
VIDEO_STREAM_PRESETS: dict[str, dict[str, Any]] = {
    "YouTube 1080p": {"width": 1920, "height": 1080, "fps": 30, "video_bitrate": "8000k", "audio_bitrate": "192k", "suffix": "youtube1080p"},
    "Discord 720p": {"width": 1280, "height": 720, "fps": 30, "video_bitrate": "3500k", "audio_bitrate": "128k", "suffix": "discord720p"},
    "Shorts 1080x1920": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "video_bitrate": "6000k",
        "audio_bitrate": "160k",
        "suffix": "shorts1080x1920",
    },
    "TikTok 1080x1920": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "video_bitrate": "5500k",
        "audio_bitrate": "160k",
        "suffix": "tiktok1080x1920",
    },
}

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
    "Aria2": {
        "homepage": "https://aria2.github.io/",
        "docs": "https://aria2.github.io/manual/en/html/aria2c.html",
        "download": "https://github.com/aria2/aria2/releases",
        "install_cmd": "winget install --id aria2.aria2 -e",
    },
}
BACKEND_DESCRIPTIONS: dict[str, str] = {
    "FFmpeg": "Core media engine for video/audio convert, compress, and extract workflows.",
    "FFprobe": "Media inspection tool used for stream/format metadata readout.",
    "Pandoc": "Document conversion backend for formats like Markdown, DOCX, HTML, and PDF.",
    "LibreOffice": "Fallback document conversion engine for office file formats.",
    "7-Zip": "Archive utility backend for broader archive format support.",
    "ImageMagick": "Image processing backend for advanced transform and format workflows.",
    "Aria2": "Torrent download backend used to fetch and extract torrent contents with no speed cap flags applied.",
}


def is_torrent_source_path(path: Path) -> bool:
    return path.suffix.lower() in TORRENT_SOURCE_EXTS


def is_metalink_source_path(path: Path) -> bool:
    return path.suffix.lower() in METALINK_SOURCE_EXTS


def is_aria2_metadata_source_path(path: Path) -> bool:
    return path.suffix.lower() in ARIA2_METADATA_SOURCE_EXTS


def is_magnet_uri(value: str) -> bool:
    return str(value).strip().lower().startswith("magnet:?")


def is_aria2_download_uri(value: str) -> bool:
    text = str(value).strip()
    if is_magnet_uri(text):
        return True
    try:
        parsed = urllib.parse.urlparse(text)
    except Exception:
        return False
    return parsed.scheme.lower() in {"http", "https", "ftp", "sftp"}

SINGLE_INSTANCE_MUTEX_NAMES = (
    "Local\\UniversalConversionHubUCH_SingleInstanceMutex",
    "Local\\UniversalConversionHubHCB_SingleInstanceMutex",
    "Local\\UniversalFileUtilitySuite_SingleInstanceMutex",
)
SINGLE_INSTANCE_LOCKFILE_NAME = "universal_conversion_hub_uch.lock"


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


def is_archive_input_path(path: Path) -> bool:
    lower_name = path.name.lower()
    return path.suffix.lower() in ARCHIVE_INPUT_EXTS or lower_name.endswith((".tar.gz", ".tar.bz2", ".tar.xz"))


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


def quick_file_fingerprint(path: Path, size: int, sample_bytes: int = 1024 * 64) -> str:
    """Build a fast pre-hash fingerprint from file edges to reduce full-file hashing work."""
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        digest.update(handle.read(sample_bytes))
        if size > sample_bytes:
            handle.seek(max(0, size - sample_bytes))
            digest.update(handle.read(sample_bytes))
    digest.update(str(size).encode("ascii", errors="ignore"))
    return digest.hexdigest()


def parse_timecode_seconds(value: str) -> float | None:
    raw = value.strip()
    if not raw:
        return None
    try:
        return float(raw)
    except Exception:
        pass
    parts = raw.split(":")
    if not parts or len(parts) > 3:
        return None
    try:
        factors = [1.0, 60.0, 3600.0]
        total = 0.0
        for index, part in enumerate(reversed(parts)):
            total += float(part) * factors[index]
        return total
    except Exception:
        return None


class OperationCanceledError(RuntimeError):
    """Raised when a user cancels a long-running task."""


@dataclass
class StorageViewEntry:
    label: str
    path: Path | None
    size: int
    kind: str


def _show_startup_warning(message: str) -> None:
    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(None, message, APP_TITLE, 0x00000030)
            return
        except Exception:
            pass
    print(message, file=sys.stderr)


def _focus_existing_window() -> None:
    if os.name != "nt":
        return
    try:
        user32 = ctypes.windll.user32
        for title in LEGACY_WINDOW_TITLES:
            hwnd = user32.FindWindowW(None, title)
            if hwnd:
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
                break
    except Exception:
        return


def _flash_window_taskbar_attention(window: tk.Misc, count: int = 6) -> None:
    if os.name != "nt":
        return
    try:
        hwnd = int(window.winfo_id())
        if not hwnd:
            return

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("hwnd", ctypes.c_void_p),
                ("dwFlags", ctypes.c_uint),
                ("uCount", ctypes.c_uint),
                ("dwTimeout", ctypes.c_uint),
            ]

        flash = FLASHWINFO(
            cbSize=ctypes.sizeof(FLASHWINFO),
            hwnd=ctypes.c_void_p(hwnd),
            dwFlags=0x00000002,  # FLASHW_TRAY
            uCount=max(1, int(count)),
            dwTimeout=0,
        )
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(flash))
    except Exception:
        return


def _acquire_single_instance_mutex() -> tuple[bool, Any | None]:
    if os.name == "nt":
        try:
            kernel32 = ctypes.windll.kernel32
            create_mutex = kernel32.CreateMutexW
            create_mutex.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
            create_mutex.restype = ctypes.c_void_p
            handles: list[int] = []
            for mutex_name in SINGLE_INSTANCE_MUTEX_NAMES:
                handle = create_mutex(None, False, mutex_name)
                if not handle:
                    continue
                handles.append(int(handle))
                already_exists = kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
                if already_exists:
                    for owned in handles:
                        try:
                            kernel32.CloseHandle(ctypes.c_void_p(owned))
                        except Exception:
                            pass
                    return False, None
            return True, (handles if handles else None)
        except Exception:
            return True, None

    # POSIX fallback: advisory lock file to keep one instance.
    try:
        import fcntl  # type: ignore

        lock_root = Path(os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("TMPDIR") or "/tmp")
        ensure_dir(lock_root)
        lock_path = lock_root / SINGLE_INSTANCE_LOCKFILE_NAME
        lock_handle = lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            lock_handle.close()
            return False, None
        lock_handle.seek(0)
        lock_handle.truncate(0)
        lock_handle.write(str(os.getpid()))
        lock_handle.flush()
        return True, lock_handle
    except Exception:
        return True, None


def _release_single_instance_mutex(handle: Any | None) -> None:
    if not handle:
        return
    if os.name == "nt":
        kernel32 = ctypes.windll.kernel32
        handles = handle if isinstance(handle, (list, tuple)) else [handle]
        for owned in handles:
            try:
                kernel32.CloseHandle(ctypes.c_void_p(int(owned)))
            except Exception:
                continue
        return
    try:
        import fcntl  # type: ignore

        if hasattr(handle, "fileno"):
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        if hasattr(handle, "close"):
            handle.close()
    except Exception:
        return


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
    def __init__(self, widget: tk.Widget, text_provider, dark_mode_provider=None, enabled_provider=None, font_provider=None, delay_ms: int = 320):
        self.widget = widget
        self.text_provider = text_provider
        self.dark_mode_provider = dark_mode_provider
        self.enabled_provider = enabled_provider
        self.font_provider = font_provider
        self.delay_ms = delay_ms
        self.tip_window: tk.Toplevel | None = None
        self.after_id: str | None = None
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")
        widget.bind("<Motion>", self._on_motion, add="+")

    def _is_enabled(self) -> bool:
        if self.enabled_provider is None:
            return True
        try:
            return bool(self.enabled_provider())
        except Exception:
            return True

    def _on_enter(self, _event=None) -> None:
        if not self._is_enabled():
            self._hide()
            return
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
        if not self._is_enabled():
            self._hide()
            return
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
        if not self._is_enabled():
            self._hide()
            return
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
        font_value = self.font_provider() if self.font_provider else ("Segoe UI", 10)

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
            font=font_value,
        )
        label.pack(fill="both", expand=True)

        x = self.widget.winfo_pointerx() + 14
        y = self.widget.winfo_pointery() + 16
        self.tip_window.geometry(f"+{x}+{y}")

    def _hide(self) -> None:
        if self.tip_window and self.tip_window.winfo_exists():
            self.tip_window.destroy()
        self.tip_window = None

    def refresh_enabled_state(self) -> None:
        if not self._is_enabled():
            self._cancel()
            self._hide()


@dataclass
class BackendRegistry:
    ffmpeg: str | None
    ffprobe: str | None
    pandoc: str | None
    libreoffice: str | None
    sevenzip: str | None
    imagemagick: str | None
    aria2: str | None

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

        local_aria2_bases: list[Path] = [Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent]
        if getattr(sys, "frozen", False):
            executable_dir = Path(sys.executable).resolve().parent
            local_aria2_bases.extend([executable_dir, executable_dir.parent])
        deduped_local_aria2_bases: list[Path] = []
        seen_local_aria2_bases: set[str] = set()
        for base in local_aria2_bases:
            key = str(base)
            if key in seen_local_aria2_bases:
                continue
            seen_local_aria2_bases.add(key)
            deduped_local_aria2_bases.append(base)

        aria2 = existing(shutil.which("aria2c") or shutil.which("aria2c.exe"))
        if not aria2:
            aria2 = first_existing(
                [
                    Path(os.environ.get("ProgramFiles", "")) / "aria2" / "aria2c.exe",
                    Path(os.environ.get("ProgramFiles(x86)", "")) / "aria2" / "aria2c.exe",
                    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "aria2" / "aria2c.exe",
                    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "aria2c.exe",
                    *[base / "aria2c.exe" for base in deduped_local_aria2_bases],
                    *[base / "aria2" / "aria2c.exe" for base in deduped_local_aria2_bases],
                ]
            )
        if not aria2:
            aria2 = first_glob(
                [
                    str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" / "aria2.aria2_Microsoft.Winget.Source_*" / "**" / "aria2c.exe"),
                    *[str(base / "aria2*" / "aria2c.exe") for base in deduped_local_aria2_bases],
                ]
            )

        return cls(
            ffmpeg=ffmpeg_path,
            ffprobe=ffprobe_path,
            pandoc=pandoc,
            libreoffice=libreoffice,
            sevenzip=sevenzip,
            imagemagick=imagemagick,
            aria2=aria2,
        )

    def as_rows(self) -> list[tuple[str, str]]:
        return [
            ("FFmpeg", self.ffmpeg or "Not found"),
            ("FFprobe", self.ffprobe or "Not found"),
            ("Pandoc", self.pandoc or "Not found"),
            ("LibreOffice", self.libreoffice or "Not found"),
            ("7-Zip", self.sevenzip or "Not found"),
            ("ImageMagick", self.imagemagick or "Not found"),
            ("Aria2", self.aria2 or "Not found"),
        ]


class TaskEngine:
    def __init__(self, app: "SuiteApp"):
        self.app = app

    def _prepare_output_path(self, target_path: Path, context: str) -> Path:
        resolved = self.app.resolve_output_path(target_path, context=context)
        if resolved is None:
            raise RuntimeError("Operation canceled by user.")
        return resolved

    def _ffmpeg_thread_args(self) -> list[str]:
        raw = self.app.settings.get("ffmpeg_thread_count", 0)
        try:
            count = int(raw)
        except Exception:
            return []
        if count > 0:
            return ["-threads", str(count)]
        return []

    @staticmethod
    def _normalized_image_format(source: Path, requested_format: str) -> str:
        target_format = requested_format.strip().lower()
        if target_format in {"", "keep", "source"}:
            target_format = source.suffix.lower().lstrip(".")
        aliases = {"jpeg": "jpg", "jpe": "jpg", "jfif": "jpg", "tif": "tiff", "hif": "heif"}
        return aliases.get(target_format, target_format)

    @staticmethod
    def _image_save_format_name(target_format: str) -> str:
        return {
            "jpg": "JPEG",
            "jpeg": "JPEG",
            "tif": "TIFF",
            "tiff": "TIFF",
            "ico": "ICO",
            "heic": "HEIF",
            "heif": "HEIF",
            "avif": "AVIF",
        }.get(target_format, target_format.upper())

    def _should_use_imagemagick_for_image(self, source: Path, target_format: str) -> bool:
        suffix = source.suffix.lower()
        normalized_target = self._normalized_image_format(source, target_format)
        return normalized_target in IMAGEMAGICK_IMAGE_TARGET_FORMATS or suffix in (IMAGEMAGICK_IMAGE_INPUT_EXTS - {".raw"})

    @staticmethod
    def _ambiguous_raw_message(source: Path) -> str:
        return (
            f"{source.name} uses the generic .raw extension. This file can be converted if its data is a standard image "
            "with the wrong extension, but true generic RAW pixel files do not include enough format information to open "
            "reliably. Rename it to its real format or export it as DNG/CR2/NEF/ARW/RAF/ORF/RW2 first."
        )

    def _load_image_with_pillow(self, source: Path):
        if Image is None:
            raise RuntimeError("Pillow is not installed; cannot process image files.")
        try:
            with Image.open(source) as opened:
                image = ImageOps.exif_transpose(opened) if ImageOps is not None else opened.copy()
                if image is opened:
                    image = image.copy()
            return image
        except UnidentifiedImageError as exc:
            if source.suffix.lower() == ".raw":
                raise RuntimeError(self._ambiguous_raw_message(source)) from exc
            raise

    def _prepare_imagemagick_source(self, source: Path) -> tuple[Path, tempfile.TemporaryDirectory | None]:
        if source.suffix.lower() != ".raw":
            return source, None
        image = self._load_image_with_pillow(source)
        if image.mode not in {"RGB", "RGBA", "L", "LA"}:
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        temp_dir = tempfile.TemporaryDirectory()
        normalized = Path(temp_dir.name) / f"{source.stem}_normalized.png"
        image.save(normalized, format="PNG")
        return normalized, temp_dir

    def _convert_image_with_imagemagick(
        self,
        source: Path,
        out_path: Path,
        *,
        quality: int,
        max_width: int = 0,
        max_height: int = 0,
        sharpen_amount: int = 0,
    ) -> Path:
        magick = self.app.backends.imagemagick
        if not magick:
            raise RuntimeError(
                "ImageMagick is required for JPEG XL and camera-raw image conversions. Install ImageMagick and try again."
            )
        magick_source, temp_dir = self._prepare_imagemagick_source(source)
        try:
            cmd = [magick, f"{magick_source}[0]", "-auto-orient"]
            if max_width > 0 or max_height > 0:
                width_part = str(max_width) if max_width > 0 else ""
                height_part = str(max_height) if max_height > 0 else ""
                cmd += ["-resize", f"{width_part}x{height_part}>"]
            if sharpen_amount > 0:
                sharpen_radius = max(0.3, min(4.0, sharpen_amount / 100.0))
                cmd += ["-unsharp", f"0x{sharpen_radius:.2f}"]
            cmd += ["-quality", str(max(1, min(100, quality))), str(out_path)]
            self.app.run_process(cmd)
        finally:
            if temp_dir is not None:
                temp_dir.cleanup()
        return out_path

    def _convert_image_document_to_pdf(self, source: Path, final_path: Path) -> Path:
        try:
            image = self._load_image_with_pillow(source)
        except UnidentifiedImageError:
            image = None
        if image is not None:
            if "A" in image.getbands():
                flattened = Image.new("RGB", image.size, (255, 255, 255))
                flattened.paste(image, mask=image.getchannel("A"))
                image = flattened
            elif image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            image.save(final_path, format="PDF", resolution=300.0)
            return final_path

        suffix = source.suffix.lower()
        if self.app.backends.imagemagick and self._should_use_imagemagick_for_image(source, "pdf"):
            cmd = [self.app.backends.imagemagick, f"{source}[0]", "-auto-orient", str(final_path)]
            self.app.run_process(cmd)
            return final_path

        if suffix == ".raw":
            raise RuntimeError(self._ambiguous_raw_message(source))

        raise RuntimeError(
            "PDF export for image or camera-raw files requires Pillow or ImageMagick."
        )

    @staticmethod
    def _audio_codec_args(target_format: str, bitrate: str) -> list[str]:
        fmt = target_format.strip().lower()
        if fmt == "mp3":
            return ["-c:a", "libmp3lame", "-b:a", bitrate]
        if fmt == "wav":
            return ["-c:a", "pcm_s16le"]
        if fmt == "flac":
            return ["-c:a", "flac"]
        if fmt == "ogg":
            return ["-c:a", "libvorbis", "-b:a", bitrate]
        if fmt == "m4a":
            return ["-c:a", "aac", "-b:a", bitrate]
        raise RuntimeError(f"Unsupported audio format: {target_format}")

    def process_image_file(self, source: Path, output_dir: Path, options: dict[str, Any]) -> Path:
        if Image is None:
            raise RuntimeError("Pillow is not installed; cannot process image files.")
        ensure_dir(output_dir)
        target_format = self._normalized_image_format(source, str(options.get("target_format", "keep")))
        if target_format not in IMAGE_FORMATS:
            raise RuntimeError(f"Unsupported image target format: {target_format}")

        out_path = output_dir / f"{source.stem}_image.{target_format}"
        out_path = self._prepare_output_path(out_path, f"Processed image for {source.name}")
        quality = max(1, min(100, int(options.get("quality", 92))))
        sharpen_amount = max(0, min(300, int(options.get("sharpen", 0))))
        max_width = max(0, int(options.get("max_width", 0)))
        max_height = max(0, int(options.get("max_height", 0)))
        if self._should_use_imagemagick_for_image(source, target_format):
            return self._convert_image_with_imagemagick(
                source,
                out_path,
                quality=quality,
                max_width=max_width,
                max_height=max_height,
                sharpen_amount=sharpen_amount,
            )
        resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS", getattr(Image, "LANCZOS", Image.BICUBIC))

        image = self._load_image_with_pillow(source)
        try:
            if max_width > 0 or max_height > 0:
                width_limit = max_width if max_width > 0 else image.width
                height_limit = max_height if max_height > 0 else image.height
                image.thumbnail((max(1, width_limit), max(1, height_limit)), resampling)
            if sharpen_amount > 0 and ImageFilter is not None:
                image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=max(50, sharpen_amount), threshold=3))

            save_kwargs: dict[str, Any] = {}
            if target_format == "jpg":
                if "A" in image.getbands():
                    flattened = Image.new("RGB", image.size, (255, 255, 255))
                    flattened.paste(image, mask=image.getchannel("A"))
                    image = flattened
                elif image.mode not in {"RGB", "L"}:
                    image = image.convert("RGB")
                save_kwargs["quality"] = quality
                save_kwargs["optimize"] = True
            elif target_format == "webp":
                save_kwargs["quality"] = quality
                save_kwargs["method"] = 6
            elif target_format in {"heic", "heif", "avif"}:
                save_kwargs["quality"] = quality
            elif target_format == "png":
                save_kwargs["optimize"] = True
            elif target_format == "ico":
                if image.mode not in {"RGBA", "RGB"}:
                    image = image.convert("RGBA")
                icon_size = max(16, min(256, max(image.size)))
                if image.size != (icon_size, icon_size):
                    image = image.resize((icon_size, icon_size), resampling)

            format_name = self._image_save_format_name(target_format)
            image.save(out_path, format=format_name, **save_kwargs)
        finally:
            try:
                image.close()
            except Exception:
                pass
        return out_path

    def process_audio_file(self, source: Path, output_dir: Path, options: dict[str, Any]) -> Path:
        ffmpeg = self.app.backends.ffmpeg
        if not ffmpeg:
            raise RuntimeError("FFmpeg is required for advanced audio processing and was not detected.")
        ensure_dir(output_dir)
        target_format = str(options.get("target_format", "mp3")).strip().lower()
        bitrate = str(options.get("audio_bitrate", "192k")).strip() or "192k"
        sample_rate = str(options.get("sample_rate", "keep")).strip().lower()
        channels = str(options.get("channels", "keep")).strip().lower()
        normalize = bool(options.get("normalize", False))
        trim_silence = bool(options.get("trim_silence", False))

        out_path = output_dir / f"{source.stem}_audio.{target_format}"
        out_path = self._prepare_output_path(out_path, f"Processed audio for {source.name}")
        cmd = [ffmpeg, *self._ffmpeg_thread_args(), "-y", "-i", str(source), "-vn"]
        filters: list[str] = []
        if normalize:
            filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
        if trim_silence:
            filters.append(
                "silenceremove=start_periods=1:start_silence=0.25:start_threshold=-45dB:"
                "stop_periods=1:stop_silence=0.25:stop_threshold=-45dB"
            )
        if filters:
            cmd += ["-af", ",".join(filters)]
        if sample_rate not in {"", "keep"}:
            cmd += ["-ar", sample_rate]
        if channels == "mono":
            cmd += ["-ac", "1"]
        elif channels == "stereo":
            cmd += ["-ac", "2"]
        cmd += self._audio_codec_args(target_format, bitrate)
        cmd.append(str(out_path))
        self.app.run_process(cmd)
        return out_path

    def process_video_file(self, source: Path, output_dir: Path, mode_key: str, options: dict[str, Any]) -> Path:
        ffmpeg = self.app.backends.ffmpeg
        if not ffmpeg:
            raise RuntimeError("FFmpeg is required for advanced video processing and was not detected.")
        ensure_dir(output_dir)

        if mode_key == "remux":
            container = str(options.get("container", "mp4")).strip().lower()
            if container not in VIDEO_REMUX_FORMATS:
                raise RuntimeError(f"Unsupported remux container: {container}")
            out_path = output_dir / f"{source.stem}_remux.{container}"
            out_path = self._prepare_output_path(out_path, f"Remuxed video for {source.name}")
            cmd = [ffmpeg, *self._ffmpeg_thread_args(), "-y", "-i", str(source), "-c", "copy", str(out_path)]
            self.app.run_process(cmd)
            return out_path

        if mode_key == "trim":
            trim_container = str(options.get("trim_container", "keep")).strip().lower()
            if trim_container in {"", "keep"}:
                trim_container = source.suffix.lower().lstrip(".")
            start_value = str(options.get("trim_start", "")).strip()
            end_value = str(options.get("trim_end", "")).strip()
            if not start_value and not end_value:
                raise RuntimeError("Trim requires a start time, an end time, or both.")
            out_path = output_dir / f"{source.stem}_trim.{trim_container}"
            out_path = self._prepare_output_path(out_path, f"Trimmed video for {source.name}")
            cmd = [ffmpeg, *self._ffmpeg_thread_args(), "-y"]
            if start_value:
                cmd += ["-ss", start_value]
            cmd += ["-i", str(source)]
            start_seconds = parse_timecode_seconds(start_value)
            end_seconds = parse_timecode_seconds(end_value)
            if start_value and end_value and start_seconds is not None and end_seconds is not None and end_seconds > start_seconds:
                cmd += ["-t", f"{end_seconds - start_seconds:.3f}"]
            elif end_value:
                cmd += ["-to", end_value]
            cmd += ["-c", "copy", str(out_path)]
            self.app.run_process(cmd)
            return out_path

        if mode_key == "stream_prep":
            preset_name = str(options.get("stream_preset_name", next(iter(VIDEO_STREAM_PRESETS)))).strip()
            preset = VIDEO_STREAM_PRESETS.get(preset_name)
            if preset is None:
                raise RuntimeError(f"Unknown stream preset: {preset_name}")
            video_preset = str(options.get("video_preset", "medium")).strip() or "medium"
            video_crf = str(options.get("video_crf", 23)).strip() or "23"
            out_path = output_dir / f"{source.stem}_{preset['suffix']}.mp4"
            out_path = self._prepare_output_path(out_path, f"Stream-prepped video for {source.name}")
            vf = (
                f"scale=w={preset['width']}:h={preset['height']}:force_original_aspect_ratio=decrease,"
                f"pad={preset['width']}:{preset['height']}:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"fps={preset['fps']}"
            )
            cmd = [
                ffmpeg,
                *self._ffmpeg_thread_args(),
                "-y",
                "-i",
                str(source),
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-preset",
                video_preset,
                "-crf",
                video_crf,
                "-pix_fmt",
                "yuv420p",
                "-b:v",
                str(preset["video_bitrate"]),
                "-maxrate",
                str(preset["video_bitrate"]),
                "-bufsize",
                str(preset["video_bitrate"]).replace("k", "") + "k",
                "-c:a",
                "aac",
                "-b:a",
                str(preset["audio_bitrate"]),
                "-ar",
                "48000",
                "-movflags",
                "+faststart",
                str(out_path),
            ]
            self.app.run_process(cmd)
            return out_path

        if mode_key == "thumbnail_sheet":
            interval = str(options.get("thumb_interval", "15")).strip() or "15"
            columns = max(1, int(options.get("thumb_columns", 4)))
            rows = max(1, int(options.get("thumb_rows", 4)))
            frame_width = max(120, int(options.get("thumb_width", 320)))
            out_path = output_dir / f"{source.stem}_sheet.png"
            out_path = self._prepare_output_path(out_path, f"Thumbnail sheet for {source.name}")
            vf = f"fps=1/{interval},scale={frame_width}:-1,tile={columns}x{rows}"
            cmd = [ffmpeg, *self._ffmpeg_thread_args(), "-y", "-i", str(source), "-vf", vf, "-frames:v", "1", str(out_path)]
            self.app.run_process(cmd)
            return out_path

        raise RuntimeError(f"Unknown advanced video mode: {mode_key}")

    def convert_file(self, source: Path, output_dir: Path, target_format: str, options: dict[str, Any]) -> Path:
        target_format = target_format.lower()
        ensure_dir(output_dir)
        out_path = output_dir / f"{source.stem}.{target_format}"
        suffix = source.suffix.lower()

        if suffix in SUPPORTED_IMAGE_INPUT_EXTS and target_format in IMAGE_FORMATS:
            if Image is None:
                raise RuntimeError("Pillow is not installed; cannot convert image files.")
            out_path = self._prepare_output_path(out_path, f"Converted file for {source.name}")
            quality = int(options.get("image_quality", 92))
            if self._should_use_imagemagick_for_image(source, target_format):
                return self._convert_image_with_imagemagick(source, out_path, quality=quality)
            image = self._load_image_with_pillow(source)
            try:
                save_kwargs: dict[str, Any] = {}
                if target_format in LOSSY_IMAGE_FORMATS:
                    if target_format in JPEG_LIKE_IMAGE_FORMATS and image.mode in {"RGBA", "P"}:
                        image = image.convert("RGB")
                    elif image.mode == "P":
                        image = image.convert("RGBA")
                    save_kwargs["quality"] = quality
                    save_kwargs["optimize"] = True
                if target_format == "png":
                    save_kwargs["optimize"] = True
                format_name = self._image_save_format_name(target_format)
                image.save(out_path, format=format_name, **save_kwargs)
            finally:
                try:
                    image.close()
                except Exception:
                    pass
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
            cmd = [ffmpeg, *self._ffmpeg_thread_args(), "-y", "-i", str(source)]
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
                normalized_suffix = self._normalized_image_format(source, suffix.lstrip("."))
                if normalized_suffix in LOSSY_IMAGE_FORMATS:
                    save_kwargs["quality"] = quality
                    if normalized_suffix in JPEG_LIKE_IMAGE_FORMATS and image.mode in {"RGBA", "P"}:
                        image = image.convert("RGB")
                    elif image.mode == "P":
                        image = image.convert("RGBA")
                if suffix == ".png":
                    png_level = max(0, min(9, 9 - int(quality / 12)))
                    save_kwargs["compress_level"] = png_level
                image.save(out_path, format=self._image_save_format_name(normalized_suffix), **save_kwargs)
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
                *self._ffmpeg_thread_args(),
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
            cmd = [ffmpeg, *self._ffmpeg_thread_args(), "-y", "-i", str(source), "-vn", "-b:a", bitrate, str(out_path)]
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
            cmd = [ffmpeg, *self._ffmpeg_thread_args(), "-y", "-i", str(source), "-vn", str(out_path)]
            self.app.run_process(cmd)
            return out_path

        if operation_key == "frames_from_video":
            fps = str(options.get("fps", "1"))
            frame_dir = output_dir / f"{source.stem}_frames"
            ensure_dir(frame_dir)
            pattern = frame_dir / "frame_%05d.png"
            cmd = [ffmpeg, *self._ffmpeg_thread_args(), "-y", "-i", str(source), "-vf", f"fps={fps}", str(pattern)]
            self.app.run_process(cmd)
            return frame_dir

        if operation_key == "subtitles_from_video":
            subtitle_index = int(options.get("subtitle_index", 0))
            out_path = output_dir / f"{source.stem}.srt"
            out_path = self._prepare_output_path(out_path, f"Extracted file for {source.name}")
            cmd = [
                ffmpeg,
                *self._ffmpeg_thread_args(),
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
            cmd = [ffmpeg, *self._ffmpeg_thread_args(), "-y", "-i", str(source), "-an", "-vcodec", "copy", str(out_path)]
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
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    **hidden_console_process_kwargs(),
                )
                info["ffprobe"] = json.loads(result.stdout)
            except Exception as exc:
                info["ffprobe_error"] = str(exc)

        if source.suffix.lower() in SUPPORTED_IMAGE_INPUT_EXTS:
            if Image is not None:
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
                    if source.suffix.lower() == ".raw":
                        info["image_error"] = self._ambiguous_raw_message(source)
                    else:
                        info["image_error"] = "File extension looks like image but data is not recognized."
                except Exception as exc:
                    info["image_error"] = str(exc)
            elif self.app.backends.imagemagick:
                cmd = [self.app.backends.imagemagick, "identify", "-format", "%m\t%w\t%h", f"{source}[0]"]
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        check=True,
                        **hidden_console_process_kwargs(),
                    )
                    fmt, width, height = result.stdout.strip().split("\t")
                    info["image"] = {
                        "mode": "unknown",
                        "width": int(width),
                        "height": int(height),
                        "format": fmt,
                    }
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
                *self._ffmpeg_thread_args(),
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

        if target_format == "pdf" and source.suffix.lower() in SUPPORTED_IMAGE_INPUT_EXTS:
            return self._convert_image_document_to_pdf(source, final_path)

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
        self.root.withdraw()
        self.root.title(APP_TITLE)
        min_width, min_height = self._preferred_min_window_size()
        self.root.minsize(min_width, min_height)
        self.root.geometry(self._calculate_display_matched_geometry())
        self.root.protocol("WM_DELETE_WINDOW", self._request_close)

        self.main_thread = threading.current_thread()
        self.ui_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.script_dir = Path(__file__).resolve().parent
        self.resource_dir = Path(getattr(sys, "_MEIPASS", self.script_dir))
        self.runtime_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else self.script_dir
        self.local_appdata_root = Path(os.environ.get("LOCALAPPDATA", str(self.runtime_dir)))
        self.appdata_dir = self._resolve_appdata_dir()
        ensure_dir(self.appdata_dir)

        self.settings_path = self.appdata_dir / "settings.json"
        self.settings = self._load_settings()
        self._refresh_paths_from_settings()

        self.status_left_var = StringVar(value="Ready.")
        self.status_right_var = StringVar(value="")
        self.dark_mode_var = BooleanVar(value=bool(self.settings.get("dark_mode", False)))
        self.fullscreen_var = BooleanVar(value=bool(self.settings.get("fullscreen", False)))
        self.borderless_max_var = BooleanVar(value=bool(self.settings.get("borderless_maximized", False)))
        self._startup_window_shown = False
        self._startup_tasks_scheduled = False
        self._startup_update_flow_handled = False
        self._startup_animation_active = False
        self._startup_splash_hidden_by_focus_loss = False
        self._startup_taskbar_attention_pending = False
        self._startup_deferred_tasks_pending = False
        self.tabs: dict[str, ttk.Frame] = {}
        self.top_notebook: ttk.Notebook | None = None
        self.notebook: ttk.Notebook | None = None
        self.workspace_category_notebook: ttk.Notebook | None = None
        self.workspace_module_notebooks: dict[str, ttk.Notebook] = {}
        self.module_categories: dict[str, str] = {}
        self.workspace_tab: ttk.Frame | None = None
        self.backend_corner_button: ttk.Button | None = None
        self._root_frame: ttk.Frame | None = None
        self._header_card: ttk.Frame | None = None
        self.window_drag_strip: ttk.Frame | None = None
        self.window_drag_label: ttk.Label | None = None
        self._window_drag_offset: tuple[int, int] | None = None
        self.drag_drop_enabled = False
        self._last_drop_signature: tuple[tuple[str, ...], float] | None = None
        self.backend_hover_cards: list[HoverCard] = []
        self._normal_geometry = self.root.geometry()
        self._normal_zoomed = False
        self._window_mode_state = "normal"
        self.root.bind("<Configure>", self._on_root_window_configured, add="+")
        self.root.bind("<FocusIn>", self._on_root_focus_in, add="+")
        self.root.bind("<F11>", self._on_f11_toggle)
        self.root.bind("<F10>", self._on_f10_toggle_borderless)
        self.root.bind("<Escape>", self._on_escape_exit_fullscreen)

        self.backends = BackendRegistry.detect()
        self.engine = TaskEngine(self)

        if not self.settings.get("first_run_done", False):
            self._run_first_run_setup_wizard()

        self._apply_window_icon()
        self._configure_styles()
        self._build_menu()
        self._build_ui()
        self._setup_drag_and_drop()
        if bool(self.fullscreen_var.get()) and bool(self.borderless_max_var.get()):
            self.borderless_max_var.set(False)
        self._set_backend_summary_status()
        self._refresh_hover_tooltip_preferences()
        self.root.after(100, self._poll_ui_queue)
        show_startup_animation = bool(self.settings.get("show_startup_animation", True))
        if bool(self.settings.get("check_updates_on_startup", True)):
            show_startup_animation = True
        if show_startup_animation:
            try:
                self._show_startup_logo_animation(show_main_when_done=False, modal=True)
            except Exception:
                pass
        self._run_startup_update_flow()
        self._show_main_window_after_startup()

    def _resolve_appdata_dir(self) -> Path:
        preferred = self.local_appdata_root / APP_SLUG
        if preferred.exists():
            return preferred
        for legacy_slug in LEGACY_APP_SLUGS:
            legacy_dir = self.local_appdata_root / legacy_slug
            if (legacy_dir / "settings.json").exists():
                return legacy_dir
        for legacy_slug in LEGACY_APP_SLUGS:
            legacy_dir = self.local_appdata_root / legacy_slug
            if legacy_dir.exists():
                return legacy_dir
        return preferred

    def _default_settings(self) -> dict[str, Any]:
        default_output = Path.home() / "Documents" / "Universal Conversion Hub Output"
        return {
            "first_run_done": False,
            "dark_mode": False,
            "high_contrast_mode": False,
            "fullscreen": False,
            "borderless_maximized": False,
            "reduce_motion": False,
            "ui_scale_percent": 100,
            "use_hover_tooltips": False,
            "output_folder": str(default_output),
            "check_updates_on_startup": True,
            "prompt_backend_install_on_startup": True,
            "show_startup_animation": True,
            "startup_animation_seconds": 4.6,
            "ffmpeg_thread_count": 0,
            "log_max_lines": 4000,
            "security_confirm_external_links": True,
            "security_require_https_for_web_links": True,
            "security_require_https_for_update_manifest": True,
            "security_allow_local_update_manifests": True,
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
        hover_tooltips_var = BooleanVar(value=bool(self.settings.get("use_hover_tooltips", False)))
        update_check_var = BooleanVar(value=bool(self.settings.get("check_updates_on_startup", True)))
        backend_prompt_var = BooleanVar(value=bool(self.settings.get("prompt_backend_install_on_startup", True)))
        startup_animation_var = BooleanVar(value=bool(self.settings.get("show_startup_animation", True)))
        security_confirm_links_var = BooleanVar(value=bool(self.settings.get("security_confirm_external_links", True)))
        security_https_manifest_var = BooleanVar(value=bool(self.settings.get("security_require_https_for_update_manifest", True)))
        update_url_var = StringVar(value=str(self.settings.get("update_manifest_url", "")))
        finished = {"done": False}

        self._apply_window_icon_to(wizard)
        outer = self._build_draggable_dialog_shell(wizard, drag_label="Drag Setup Wizard")

        ttk.Label(outer, text="Welcome to Universal Conversion Hub (UCH)", font=self._font(14, semibold=True)).pack(anchor="w")
        ttk.Label(
            outer,
            text="Set your defaults now. You can change them later from File -> Settings.",
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
        ttk.Checkbutton(row2, text="Show startup logo animation", variable=startup_animation_var).pack(anchor="w")
        ttk.Checkbutton(row2, text="Confirm before opening external links", variable=security_confirm_links_var).pack(anchor="w")
        ttk.Checkbutton(row2, text="Require HTTPS update manifest URLs", variable=security_https_manifest_var).pack(anchor="w")
        ttk.Button(row2, text="Review Missing Backends Now", command=self._open_backend_install_assistant).pack(anchor="w", pady=(6, 0))

        row3 = ttk.Frame(outer)
        row3.pack(fill="x", pady=(0, 10))
        ttk.Label(row3, text="Update manifest URL (optional):").pack(anchor="w")
        ttk.Entry(row3, textvariable=update_url_var).pack(fill="x", pady=(4, 0))

        ttk.Label(
            outer,
            text='Manifest example: {"latest_version":"0.7.3","download_url":"https://example.com/app.exe","notes":"Release notes"}',
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
            self.settings["show_startup_animation"] = bool(startup_animation_var.get())
            self.settings["security_confirm_external_links"] = bool(security_confirm_links_var.get())
            self.settings["security_require_https_for_update_manifest"] = bool(security_https_manifest_var.get())
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

    def _bind_drag_handlers_to_window(self, window: tk.Misc, widget: tk.Misc, offset_holder: dict[str, tuple[int, int] | None]) -> None:
        try:
            widget.configure(cursor="fleur")
        except Exception:
            pass

        def begin_drag(event) -> str:
            offset_holder["value"] = (event.x_root - window.winfo_x(), event.y_root - window.winfo_y())
            return "break"

        def drag_motion(event) -> str | None:
            offset = offset_holder.get("value")
            if not offset:
                return None
            offset_x, offset_y = offset
            try:
                window.geometry(f"+{event.x_root - offset_x}+{event.y_root - offset_y}")
            except Exception:
                return None
            return "break"

        def end_drag(_event=None) -> None:
            offset_holder["value"] = None

        widget.bind("<ButtonPress-1>", begin_drag, add="+")
        widget.bind("<B1-Motion>", drag_motion, add="+")
        widget.bind("<ButtonRelease-1>", end_drag, add="+")

    def _build_draggable_dialog_shell(
        self,
        window: tk.Misc,
        *,
        padding: tuple[int, int, int, int] = (14, 14, 14, 14),
        drag_label: str = "Drag Window",
    ) -> ttk.Frame:
        host = ttk.Frame(window, style="App.TFrame", padding=padding)
        host.pack(fill="both", expand=True)
        strip = ttk.Frame(host, style="DragStrip.TFrame", height=self._scaled(18))
        strip.pack(fill="x", pady=(0, 10))
        strip.pack_propagate(False)
        label = ttk.Label(strip, text=drag_label, style="DragStrip.TLabel", anchor="center")
        label.pack(fill="both", expand=True)
        offset_holder: dict[str, tuple[int, int] | None] = {"value": None}
        self._bind_drag_handlers_to_window(window, strip, offset_holder)
        self._bind_drag_handlers_to_window(window, label, offset_holder)
        body = ttk.Frame(host, style="App.TFrame")
        body.pack(fill="both", expand=True)
        return body

    def _show_app_modal_dialog(
        self,
        title: str,
        message: str,
        buttons: list[tuple[str, str]],
        *,
        default_choice: str,
        width: int = 620,
    ) -> str:
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.resizable(False, False)
        self._apply_window_icon_to(dialog)
        if str(self.root.state()) != "withdrawn":
            try:
                dialog.transient(self.root)
            except Exception:
                pass
        dialog.grab_set()

        result = {"choice": default_choice}
        outer = self._build_draggable_dialog_shell(dialog, drag_label="Drag Popup")
        ttk.Label(outer, text=title, font=self._font(13, semibold=True)).pack(anchor="w")
        ttk.Label(outer, text=message, justify="left", wraplength=width - 60).pack(anchor="w", pady=(8, 12))

        button_row = ttk.Frame(outer, style="App.TFrame")
        button_row.pack(fill="x")

        def choose(choice: str) -> None:
            result["choice"] = choice
            try:
                dialog.grab_release()
            except Exception:
                pass
            dialog.destroy()

        for index, (label, value) in enumerate(buttons):
            ttk.Button(button_row, text=label, style="App.TButton", command=lambda c=value: choose(c)).pack(
                side="right",
                padx=(8 if index else 0, 0),
            )

        dialog.protocol("WM_DELETE_WINDOW", lambda: choose(default_choice))
        dialog.update_idletasks()
        dialog_width = max(width, dialog.winfo_width())
        dialog_height = dialog.winfo_height()
        if str(self.root.state()) != "withdrawn":
            x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - dialog_width) // 2)
            y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - dialog_height) // 2)
        else:
            screen_w = dialog.winfo_screenwidth()
            screen_h = dialog.winfo_screenheight()
            x = max(0, (screen_w - dialog_width) // 2)
            y = max(0, (screen_h - dialog_height) // 2)
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        self.root.wait_window(dialog)
        return str(result["choice"])

    def _ui_scale_factor(self) -> float:
        try:
            percent = float(self.settings.get("ui_scale_percent", 100))
        except Exception:
            percent = 100.0
        return max(0.9, min(1.8, percent / 100.0))

    def _scaled(self, value: int, minimum: int = 1) -> int:
        return max(minimum, int(round(float(value) * self._ui_scale_factor())))

    def _font(self, size: int, semibold: bool = False, bold: bool = False, underline: bool = False):
        family = "Segoe UI Semibold" if semibold else "Segoe UI"
        font_parts: list[Any] = [family, self._scaled(size)]
        if bold:
            font_parts.append("bold")
        if underline:
            font_parts.append("underline")
        return tuple(font_parts)

    def _tooltip_font(self):
        return self._font(10)

    def high_contrast_enabled(self) -> bool:
        return bool(self.settings.get("high_contrast_mode", False))

    def reduced_motion_enabled(self) -> bool:
        return bool(self.settings.get("reduce_motion", False))

    def _configure_styles(self) -> None:
        base_font_size = self._scaled(10)
        self.root.option_add("*Font", f"{{Segoe UI}} {base_font_size}")
        self.style = ttk.Style(self.root)
        themes = set(self.style.theme_names())
        if "clam" in themes:
            self.style.theme_use("clam")

        self.style.configure(".", font=self._font(10))
        self.style.configure("App.TButton", padding=(self._scaled(12), self._scaled(7)), font=self._font(10, semibold=True))
        self.style.configure("PrimaryApp.TButton", padding=(self._scaled(12), self._scaled(7)), font=self._font(10, semibold=True))
        self.style.configure("QuietApp.TButton", padding=(self._scaled(12), self._scaled(7)), font=self._font(10))
        self.style.configure("App.TNotebook", borderwidth=0, tabmargins=(self._scaled(8), 0, 0, 0))
        try:
            self.style.configure("App.TNotebook", tabposition="n")
        except tk.TclError:
            # Some Tk builds do not support tabposition.
            pass
        self.style.configure(
            "App.TNotebook.Tab",
            padding=(self._scaled(14), self._scaled(10)),
            font=self._font(10, semibold=True),
            background="#DCE5F1",
            foreground="#17304F",
            borderwidth=1,
        )
        self.style.configure("TopTabs.TNotebook", borderwidth=0, tabmargins=(self._scaled(6), 0, 0, 0))
        self.style.configure(
            "TopTabs.TNotebook.Tab",
            padding=(self._scaled(18), self._scaled(10)),
            font=self._font(10, semibold=True),
            background="#DCE5F1",
            foreground="#17304F",
            borderwidth=1,
        )
        self._apply_theme(bool(self.dark_mode_var.get()))

    def _theme_palette(self, dark_mode: bool) -> dict[str, str]:
        if dark_mode:
            palette = {
                "window_bg": "#10151C",
                "surface_bg": "#121A23",
                "surface_alt_bg": "#0D141D",
                "card_bg": "#171F29",
                "card_border": "#2D3A49",
                "title_fg": "#F2F7FF",
                "subtitle_fg": "#C7D4E6",
                "meta_fg": "#E4EEFB",
                "muted_fg": "#9FB1C8",
                "status_bg": "#0C1117",
                "status_fg": "#D6E4F5",
                "button_bg": "#1D2835",
                "button_fg": "#E7F0FE",
                "button_active": "#2A3A4E",
                "button_press": "#324861",
                "accent_bg": "#3874B6",
                "accent_fg": "#F8FBFF",
                "accent_active": "#4A86C9",
                "accent_press": "#2C629C",
                "accent_soft_bg": "#203246",
                "input_bg": "#111923",
                "input_fg": "#F1F6FF",
                "input_border": "#304153",
                "select_bg": "#355276",
                "select_fg": "#FFFFFF",
                "tree_header_bg": "#202D3B",
                "tree_header_fg": "#EAF3FF",
                "progress_bg": "#5A95D6",
                "progress_trough": "#0E151E",
                "notebook_bg": "#10151C",
                "tab_bg": "#1C2734",
                "tab_fg": "#DCE7F7",
                "tab_sel_bg": "#2A3C52",
                "tab_sel_fg": "#FFFFFF",
                "tab_active_bg": "#243447",
                "tab_active_fg": "#FFFFFF",
                "log_bg": "#0D131A",
                "log_fg": "#F0F6FF",
                "log_border": "#314252",
                "backend_detected_fg": "#A8D5FF",
                "backend_missing_fg": "#FFB178",
            }
        else:
            palette = {
            "window_bg": "#EEF2F8",
            "surface_bg": "#F5F8FC",
            "surface_alt_bg": "#E6ECF5",
            "card_bg": "#FFFFFF",
            "card_border": "#CFD8E6",
            "title_fg": "#0B2440",
            "subtitle_fg": "#405368",
            "meta_fg": "#1A3555",
            "muted_fg": "#5A6C84",
            "status_bg": "#DCE4EF",
            "status_fg": "#163150",
            "button_bg": "#F8FBFF",
            "button_fg": "#17304F",
            "button_active": "#E8EEF8",
            "button_press": "#DDE6F4",
            "accent_bg": "#2D69A8",
            "accent_fg": "#FFFFFF",
            "accent_active": "#3D79B8",
            "accent_press": "#23598E",
            "accent_soft_bg": "#E7EEF8",
            "input_bg": "#FFFFFF",
            "input_fg": "#10253F",
            "input_border": "#B8C7DC",
            "select_bg": "#2D69A8",
            "select_fg": "#FFFFFF",
            "tree_header_bg": "#E7EEF8",
            "tree_header_fg": "#17304F",
            "progress_bg": "#3A76B6",
            "progress_trough": "#E4ECF7",
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
        if self.high_contrast_enabled():
            if dark_mode:
                palette.update(
                    {
                        "window_bg": "#090E14",
                        "surface_bg": "#0E1620",
                        "surface_alt_bg": "#0B121A",
                        "card_bg": "#121C28",
                        "card_border": "#4D627C",
                        "title_fg": "#FFFFFF",
                        "subtitle_fg": "#E1EEFF",
                        "meta_fg": "#F3F8FF",
                        "muted_fg": "#CBDCF1",
                        "status_bg": "#070B10",
                        "status_fg": "#F3F8FF",
                        "button_bg": "#162231",
                        "button_fg": "#F5FAFF",
                        "button_active": "#233448",
                        "button_press": "#2C425B",
                        "accent_bg": "#4B9CFF",
                        "accent_active": "#67ADFF",
                        "accent_press": "#337FD8",
                        "accent_soft_bg": "#17365A",
                        "input_bg": "#0D151F",
                        "input_fg": "#FFFFFF",
                        "input_border": "#5D7DA2",
                        "select_bg": "#4B9CFF",
                        "tree_header_bg": "#24374A",
                        "tree_header_fg": "#FFFFFF",
                        "progress_bg": "#72B6FF",
                        "progress_trough": "#0A121A",
                        "log_bg": "#0A1118",
                        "log_fg": "#FFFFFF",
                        "log_border": "#4D627C",
                        "backend_detected_fg": "#BDE0FF",
                        "backend_missing_fg": "#FFC58A",
                    }
                )
            else:
                palette.update(
                    {
                        "window_bg": "#F8FBFF",
                        "surface_bg": "#FFFFFF",
                        "surface_alt_bg": "#EFF4FB",
                        "card_bg": "#FFFFFF",
                        "card_border": "#889BB3",
                        "title_fg": "#081C33",
                        "subtitle_fg": "#1B3555",
                        "meta_fg": "#0E2845",
                        "muted_fg": "#324C6A",
                        "status_bg": "#DCE7F4",
                        "status_fg": "#0E2845",
                        "button_bg": "#FFFFFF",
                        "button_fg": "#0E2845",
                        "button_active": "#E8F0FB",
                        "button_press": "#DCE8F7",
                        "accent_bg": "#155BA8",
                        "accent_active": "#246ABB",
                        "accent_press": "#0E4D90",
                        "accent_soft_bg": "#D9E8F8",
                        "input_fg": "#081C33",
                        "input_border": "#7B91AF",
                        "select_bg": "#155BA8",
                        "tree_header_bg": "#DCE8F7",
                        "tree_header_fg": "#0E2845",
                        "progress_bg": "#1F6BBD",
                        "progress_trough": "#DEE8F5",
                        "log_bg": "#FFFFFF",
                        "log_fg": "#081C33",
                        "log_border": "#889BB3",
                    }
                )
        return palette

    def _apply_theme(self, dark_mode: bool) -> None:
        palette = self._theme_palette(dark_mode)
        self.root.configure(bg=palette["window_bg"])
        self.root.option_add("*TCombobox*Listbox.background", palette["input_bg"])
        self.root.option_add("*TCombobox*Listbox.foreground", palette["input_fg"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", palette["select_bg"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", palette["select_fg"])

        self.style.configure(".", font=self._font(10), background=palette["window_bg"], foreground=palette["meta_fg"])
        self.style.configure("TFrame", background=palette["window_bg"])
        self.style.configure("TLabel", background=palette["window_bg"], foreground=palette["meta_fg"])
        self.style.configure("TLabelframe", background=palette["card_bg"], borderwidth=1, relief="solid")
        self.style.configure("TLabelframe.Label", background=palette["card_bg"], foreground=palette["meta_fg"], font=self._font(11, semibold=True))
        self.style.configure("TButton", background=palette["button_bg"], foreground=palette["button_fg"], borderwidth=1, focusthickness=0)
        self.style.map(
            "TButton",
            background=[("active", palette["button_active"]), ("pressed", palette["button_press"]), ("disabled", palette["window_bg"])],
            foreground=[("disabled", palette["subtitle_fg"])],
        )
        self.style.configure(
            "TEntry",
            fieldbackground=palette["input_bg"],
            foreground=palette["input_fg"],
            bordercolor=palette["input_border"],
        )
        self.style.map(
            "TEntry",
            fieldbackground=[("disabled", palette["window_bg"])],
            foreground=[("disabled", palette["subtitle_fg"])],
        )
        self.style.configure(
            "TCombobox",
            fieldbackground=palette["input_bg"],
            foreground=palette["input_fg"],
            background=palette["button_bg"],
            bordercolor=palette["input_border"],
            arrowcolor=palette["meta_fg"],
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", palette["input_bg"]), ("disabled", palette["window_bg"])],
            foreground=[("readonly", palette["input_fg"]), ("disabled", palette["subtitle_fg"])],
            selectbackground=[("readonly", palette["select_bg"])],
            selectforeground=[("readonly", palette["select_fg"])],
            background=[("active", palette["button_active"])],
        )
        self.style.configure(
            "TSpinbox",
            fieldbackground=palette["input_bg"],
            foreground=palette["input_fg"],
            background=palette["button_bg"],
            bordercolor=palette["input_border"],
            arrowcolor=palette["meta_fg"],
        )
        self.style.configure("TScrollbar", background=palette["button_bg"], troughcolor=palette["window_bg"], arrowcolor=palette["meta_fg"])
        self.style.map("TScrollbar", background=[("active", palette["button_active"])])
        self.style.configure(
            "Treeview",
            background=palette["input_bg"],
            fieldbackground=palette["input_bg"],
            foreground=palette["input_fg"],
            bordercolor=palette["input_border"],
            rowheight=self._scaled(30),
            font=self._font(10),
        )
        self.style.map("Treeview", background=[("selected", palette["select_bg"])], foreground=[("selected", palette["select_fg"])])
        self.style.configure(
            "Treeview.Heading",
            background=palette["tree_header_bg"],
            foreground=palette["tree_header_fg"],
            relief="flat",
            font=self._font(10, semibold=True),
        )
        self.style.map(
            "Treeview.Heading",
            background=[("active", palette["tab_active_bg"])],
            foreground=[("active", palette["tab_active_fg"])],
        )
        self.style.configure(
            "Horizontal.TProgressbar",
            troughcolor=palette["progress_trough"],
            background=palette["progress_bg"],
            bordercolor=palette["input_border"],
            lightcolor=palette["progress_bg"],
            darkcolor=palette["progress_bg"],
        )
        self.style.configure("Horizontal.TScale", background=palette["window_bg"], troughcolor=palette["progress_trough"])
        self.style.configure("TScale", background=palette["window_bg"], troughcolor=palette["progress_trough"])

        self.style.configure("App.TFrame", background=palette["window_bg"])
        self.style.configure("Surface.TFrame", background=palette["surface_bg"])
        self.style.configure("SurfaceInset.TFrame", background=palette["surface_alt_bg"])
        self.style.configure("Card.TFrame", background=palette["card_bg"])
        self.style.configure("HeaderCard.TFrame", background=palette["card_bg"])
        self.style.configure("DragStrip.TFrame", background=palette["accent_soft_bg"], borderwidth=1, relief="solid")
        self.style.configure("Card.TLabelframe", background=palette["card_bg"], borderwidth=1, relief="solid", bordercolor=palette["card_border"])
        self.style.configure("Card.TLabelframe.Label", background=palette["card_bg"], foreground=palette["meta_fg"], font=self._font(10, semibold=True))
        self.style.configure("QuickGroup.TLabelframe", background=palette["card_bg"], borderwidth=1, relief="solid", bordercolor=palette["card_border"])
        self.style.configure("QuickGroup.TLabelframe.Label", background=palette["card_bg"], foreground=palette["meta_fg"], font=self._font(9, semibold=True))
        self.style.configure("HeaderTitle.TLabel", background=palette["card_bg"], foreground=palette["title_fg"], font=self._font(18, semibold=True))
        self.style.configure("HeaderSubtitle.TLabel", background=palette["card_bg"], foreground=palette["subtitle_fg"], font=self._font(10))
        self.style.configure("HeaderMeta.TLabel", background=palette["card_bg"], foreground=palette["meta_fg"], font=self._font(10, semibold=True))
        self.style.configure("CardBody.TLabel", background=palette["card_bg"], foreground=palette["meta_fg"], font=self._font(10))
        self.style.configure("CardMuted.TLabel", background=palette["card_bg"], foreground=palette["muted_fg"], font=self._font(9))
        self.style.configure("DragStrip.TLabel", background=palette["accent_soft_bg"], foreground=palette["muted_fg"], font=self._font(8, semibold=True))
        self.style.configure("Badge.TLabel", background=palette["accent_soft_bg"], foreground=palette["tab_sel_fg"], font=self._font(9, semibold=True), padding=(self._scaled(8), self._scaled(4)))
        self.style.configure(
            "BackendDetectedLink.TLabel",
            background=palette["card_bg"],
            foreground=palette["backend_detected_fg"],
            font=self._font(10, semibold=True, underline=True),
        )
        self.style.configure(
            "BackendMissingLink.TLabel",
            background=palette["card_bg"],
            foreground=palette["backend_missing_fg"],
            font=self._font(10, semibold=True, underline=True),
        )
        self.style.configure("StatusBar.TFrame", background=palette["status_bg"])
        self.style.configure("StatusLeft.TLabel", background=palette["status_bg"], foreground=palette["status_fg"], font=self._font(10))
        self.style.configure("StatusRight.TLabel", background=palette["status_bg"], foreground=palette["status_fg"], font=self._font(10))
        self.style.configure("App.TButton", background=palette["button_bg"], foreground=palette["button_fg"], borderwidth=1)
        self.style.map(
            "App.TButton",
            background=[("active", palette["button_active"]), ("pressed", palette["button_press"]), ("disabled", palette["window_bg"])],
            foreground=[("disabled", palette["subtitle_fg"])],
        )
        self.style.configure("PrimaryApp.TButton", background=palette["accent_bg"], foreground=palette["accent_fg"], borderwidth=1)
        self.style.map(
            "PrimaryApp.TButton",
            background=[("active", palette["accent_active"]), ("pressed", palette["accent_press"]), ("disabled", palette["window_bg"])],
            foreground=[("disabled", palette["subtitle_fg"])],
        )
        self.style.configure("QuietApp.TButton", background=palette["button_bg"], foreground=palette["button_fg"], borderwidth=1)
        self.style.map(
            "QuietApp.TButton",
            background=[("active", palette["button_active"]), ("pressed", palette["button_press"]), ("disabled", palette["window_bg"])],
            foreground=[("disabled", palette["subtitle_fg"])],
        )
        self.style.configure("Shell.TButton", background=palette["button_bg"], foreground=palette["button_fg"], borderwidth=1, padding=(self._scaled(8), self._scaled(4)))
        self.style.map(
            "Shell.TButton",
            background=[("active", palette["button_active"]), ("pressed", palette["button_press"]), ("disabled", palette["window_bg"])],
            foreground=[("disabled", palette["subtitle_fg"])],
        )
        self.style.configure("ShellPrimary.TButton", background=palette["accent_bg"], foreground=palette["accent_fg"], borderwidth=1, padding=(self._scaled(8), self._scaled(4)))
        self.style.map(
            "ShellPrimary.TButton",
            background=[("active", palette["accent_active"]), ("pressed", palette["accent_press"]), ("disabled", palette["window_bg"])],
            foreground=[("disabled", palette["subtitle_fg"])],
        )
        self.style.configure("CornerTab.TButton", background=palette["accent_soft_bg"], foreground=palette["meta_fg"], borderwidth=1, padding=(self._scaled(10), self._scaled(4)))
        self.style.map(
            "CornerTab.TButton",
            background=[("active", palette["button_active"]), ("pressed", palette["button_press"]), ("disabled", palette["window_bg"])],
            foreground=[("disabled", palette["subtitle_fg"])],
        )
        self.style.configure("App.TNotebook", background=palette["surface_bg"], borderwidth=0)
        self.style.configure("App.TNotebook.Tab", background=palette["tab_bg"], foreground=palette["tab_fg"], borderwidth=1)
        self.style.map(
            "App.TNotebook.Tab",
            background=[("selected", palette["tab_sel_bg"]), ("active", palette["tab_active_bg"])],
            foreground=[("selected", palette["tab_sel_fg"]), ("active", palette["tab_active_fg"])],
        )
        self.style.configure("TopTabs.TNotebook", background=palette["surface_bg"], borderwidth=0)
        self.style.configure("TopTabs.TNotebook.Tab", background=palette["tab_bg"], foreground=palette["tab_fg"], borderwidth=1)
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
        self._apply_theme_to_widget_tree(self.root, palette)

    def _apply_theme_to_widget_tree(self, widget: tk.Misc, palette: dict[str, str]) -> None:
        try:
            children = widget.winfo_children()
        except Exception:
            return
        for child in children:
            self._apply_theme_to_tk_widget(child, palette)
            self._apply_theme_to_widget_tree(child, palette)

    def _apply_theme_to_tk_widget(self, widget: tk.Misc, palette: dict[str, str]) -> None:
        try:
            if isinstance(widget, tk.Listbox):
                widget.configure(
                    bg=palette["input_bg"],
                    fg=palette["input_fg"],
                    font=self._font(10),
                    selectbackground=palette["select_bg"],
                    selectforeground=palette["select_fg"],
                    highlightbackground=palette["input_border"],
                    highlightcolor=palette["input_border"],
                    disabledforeground=palette["subtitle_fg"],
                    activestyle="none",
                )
                return
            if isinstance(widget, tk.Text):
                widget.configure(
                    bg=palette["log_bg"],
                    fg=palette["log_fg"],
                    font=self._font(10),
                    insertbackground=palette["log_fg"],
                    selectbackground=palette["select_bg"],
                    selectforeground=palette["select_fg"],
                    highlightbackground=palette["log_border"],
                    highlightcolor=palette["log_border"],
                )
                return
            if isinstance(widget, tk.Entry):
                widget.configure(
                    bg=palette["input_bg"],
                    fg=palette["input_fg"],
                    font=self._font(10),
                    insertbackground=palette["input_fg"],
                    disabledbackground=palette["window_bg"],
                    disabledforeground=palette["subtitle_fg"],
                    highlightbackground=palette["input_border"],
                    highlightcolor=palette["input_border"],
                    readonlybackground=palette["input_bg"],
                )
                return
            if isinstance(widget, tk.Spinbox):
                widget.configure(
                    bg=palette["input_bg"],
                    fg=palette["input_fg"],
                    font=self._font(10),
                    insertbackground=palette["input_fg"],
                    buttonbackground=palette["button_bg"],
                    disabledbackground=palette["window_bg"],
                    disabledforeground=palette["subtitle_fg"],
                    highlightbackground=palette["input_border"],
                    highlightcolor=palette["input_border"],
                    readonlybackground=palette["input_bg"],
                )
                return
            if isinstance(widget, tk.Scale):
                widget.configure(
                    bg=palette["window_bg"],
                    fg=palette["meta_fg"],
                    font=self._font(10),
                    troughcolor=palette["progress_trough"],
                    activebackground=palette["button_active"],
                    highlightbackground=palette["window_bg"],
                    highlightcolor=palette["window_bg"],
                )
                return
            if isinstance(widget, tk.Canvas):
                widget.configure(
                    bg=palette["window_bg"],
                    highlightbackground=palette["card_border"],
                    highlightcolor=palette["card_border"],
                )
                return
            if isinstance(widget, tk.Frame):
                widget.configure(bg=palette["window_bg"])
                return
            if isinstance(widget, tk.Label):
                widget.configure(bg=palette["window_bg"], fg=palette["meta_fg"])
                return
        except Exception:
            return

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

    def _bind_window_drag_widget(self, widget: tk.Misc | None) -> None:
        if widget is None:
            return
        try:
            widget.configure(cursor="fleur")
        except Exception:
            pass
        widget.bind("<ButtonPress-1>", self._begin_window_drag, add="+")
        widget.bind("<B1-Motion>", self._perform_window_drag, add="+")
        widget.bind("<ButtonRelease-1>", self._end_window_drag, add="+")

    def _window_drag_strip_enabled(self) -> bool:
        if self._window_mode_state != "normal":
            return False
        try:
            return str(self.root.state()) == "normal"
        except Exception:
            return True

    def _update_window_drag_strip_visibility(self) -> None:
        if self.window_drag_strip is None:
            return
        if self._window_drag_strip_enabled():
            if not self.window_drag_strip.winfo_manager():
                pack_kwargs: dict[str, Any] = {"fill": "x", "pady": (0, 8)}
                if self._header_card is not None:
                    pack_kwargs["before"] = self._header_card
                self.window_drag_strip.pack(**pack_kwargs)
        elif self.window_drag_strip.winfo_manager():
            self.window_drag_strip.pack_forget()

    def _begin_window_drag(self, event) -> str | None:
        if not self._window_drag_strip_enabled():
            self._window_drag_offset = None
            return None
        self._window_drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())
        return "break"

    def _perform_window_drag(self, event) -> str | None:
        if not self._window_drag_offset or not self._window_drag_strip_enabled():
            return None
        offset_x, offset_y = self._window_drag_offset
        self.root.geometry(f"+{event.x_root - offset_x}+{event.y_root - offset_y}")
        return "break"

    def _end_window_drag(self, _event=None) -> str | None:
        self._window_drag_offset = None
        return None

    def _on_root_window_configured(self, event=None) -> None:
        if event is not None and getattr(event, "widget", None) is not self.root:
            return
        if self._window_mode_state == "normal":
            self._capture_normal_window_state()
        self._update_window_drag_strip_visibility()

    def _on_root_focus_in(self, _event=None) -> None:
        if not self._startup_taskbar_attention_pending:
            return
        self._startup_taskbar_attention_pending = False
        if self._startup_deferred_tasks_pending:
            self._startup_deferred_tasks_pending = False
            self.root.after(120, self._schedule_startup_tasks_once)

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
            self._update_window_drag_strip_visibility()
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
            self._update_window_drag_strip_visibility()
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
        self._update_window_drag_strip_visibility()

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
        file_menu.add_command(label="Settings", command=self._open_settings_dialog)
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
        help_menu.add_command(label="How-To", command=self._open_how_to_window)
        help_menu.add_command(label="About", command=self._show_about)
        menu.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menu)

    def _build_ui(self) -> None:
        root_frame = ttk.Frame(self.root, style="App.TFrame", padding=(16, 14, 16, 12))
        root_frame.pack(fill="both", expand=True)
        self._root_frame = root_frame

        self.window_drag_strip = ttk.Frame(root_frame, style="DragStrip.TFrame", height=self._scaled(18))
        self.window_drag_strip.pack(fill="x", pady=(0, 8))
        self.window_drag_strip.pack_propagate(False)
        self.window_drag_label = ttk.Label(self.window_drag_strip, text="Drag Window", style="DragStrip.TLabel", anchor="center")
        self.window_drag_label.pack(fill="both", expand=True)
        self._bind_window_drag_widget(self.window_drag_strip)
        self._bind_window_drag_widget(self.window_drag_label)

        header_card = ttk.Frame(root_frame, style="HeaderCard.TFrame", padding=(14, 10))
        header_card.pack(fill="x")
        self._header_card = header_card

        hero_row = ttk.Frame(header_card, style="HeaderCard.TFrame")
        hero_row.pack(fill="x")
        hero_row.columnconfigure(0, weight=1)

        intro_col = ttk.Frame(hero_row, style="HeaderCard.TFrame")
        intro_col.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        ttk.Label(intro_col, text=APP_TITLE, style="HeaderTitle.TLabel").pack(anchor="w")
        ttk.Label(
            intro_col,
            text="Modular desktop workspace for conversion, extraction, metadata, archives, batch jobs, and analysis.",
            style="HeaderSubtitle.TLabel",
            wraplength=980,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        meta_col = ttk.Frame(hero_row, style="HeaderCard.TFrame")
        meta_col.grid(row=0, column=1, sticky="ne")
        ttk.Label(meta_col, text=f"v{APP_VERSION}", style="Badge.TLabel").pack(anchor="e")
        ttk.Label(meta_col, text="Module workflow unchanged", style="CardMuted.TLabel").pack(anchor="e", pady=(4, 0))

        quick_shell = ttk.Frame(root_frame, style="App.TFrame")
        quick_shell.pack(fill="x", pady=(8, 0))
        quick_shell.columnconfigure(0, weight=1)

        self._build_action_group(
            quick_shell,
            0,
            "Workspace",
            [
                ("Open Output Folder", self._open_output_folder, "ShellPrimary.TButton"),
                ("Settings", self._open_settings_dialog, "Shell.TButton"),
                ("Check Updates", lambda: self._check_updates_in_background(interactive=True), "Shell.TButton"),
            ],
        )

        self.backend_hover_cards = []
        content_frame = ttk.Frame(root_frame, style="Surface.TFrame", padding=(10, 8, 10, 8))
        content_frame.pack(fill="both", expand=True)

        corner_bar = ttk.Frame(content_frame, style="Surface.TFrame")
        corner_bar.pack(fill="x", pady=(0, 4))
        self.backend_corner_button = ttk.Button(
            corner_bar,
            text="Backends",
            style="CornerTab.TButton",
            command=lambda: self.select_tab("Backends / Links"),
        )
        self.backend_corner_button.pack(side="right")
        self.backend_hover_cards.append(
            HoverCard(
                self.backend_corner_button,
                text_provider=self._backend_corner_hover_text,
                dark_mode_provider=self.dark_mode_var.get,
                enabled_provider=self.hover_tooltips_enabled,
                font_provider=self._tooltip_font,
            )
        )

        top_notebook = ttk.Notebook(content_frame, style="TopTabs.TNotebook")
        top_notebook.pack(fill="both", expand=True)
        top_notebook.enable_traversal()
        self.top_notebook = top_notebook

        workspace_tab = ttk.Frame(top_notebook, style="Surface.TFrame")
        top_notebook.add(workspace_tab, text="Workspace")
        self.workspace_tab = workspace_tab

        suite_plan_tab = SuitePlanTab(top_notebook, self)
        self.tabs["Suite Plan"] = suite_plan_tab
        top_notebook.add(suite_plan_tab, text="Suite Plan")

        backend_links_tab = BackendLinksTab(top_notebook, self)
        self.tabs["Backends / Links"] = backend_links_tab
        top_notebook.add(backend_links_tab, text="Backends / Links")

        activity_log_tab = ttk.Frame(top_notebook, style="Surface.TFrame", padding=10)
        top_notebook.add(activity_log_tab, text="Activity Log")

        workspace_shell = ttk.Frame(workspace_tab, style="Surface.TFrame", padding=(0, 10, 0, 0))
        workspace_shell.pack(fill="both", expand=True)

        self.workspace_category_notebook = ttk.Notebook(workspace_shell, style="App.TNotebook")
        self.workspace_category_notebook.pack(fill="both", expand=True)
        self.workspace_category_notebook.enable_traversal()
        self.workspace_module_notebooks.clear()
        self.module_categories.clear()

        categorized_specs = [
            (
                "Conversion",
                [
                    ("Convert", ConvertTab),
                    ("Compress", CompressTab),
                    ("Extract", ExtractTab),
                    ("PDF / Documents", DocumentsTab),
                    ("Archives", ArchivesTab),
                ],
            ),
            (
                "Advanced",
                [
                    ("Images", ImagesTab),
                    ("Audio", AudioTab),
                    ("Video", VideoTab),
                    ("Metadata", MetadataTab),
                ],
            ),
            (
                "Misc",
                [
                    ("Rename / Organize", RenameOrganizeTab),
                    ("Duplicate Finder", DuplicateFinderTab),
                    ("Storage Analyzer", StorageAnalyzerTab),
                    ("Checksums / Integrity", ChecksumsTab),
                    ("Subtitles", SubtitlesTab),
                    ("Presets / Batch Jobs", PresetsBatchTab),
                ],
            ),
            (
                "Aria2",
                [
                    ("Downloads", Aria2DownloadsTab),
                    ("Torrents", TorrentsTab),
                ],
            ),
        ]

        first_module_notebook: ttk.Notebook | None = None
        for category_name, tab_specs in categorized_specs:
            category_frame = ttk.Frame(self.workspace_category_notebook, style="Surface.TFrame", padding=(0, 8, 0, 0))
            self.workspace_category_notebook.add(category_frame, text=category_name)
            module_notebook = ttk.Notebook(category_frame, style="App.TNotebook")
            module_notebook.pack(fill="both", expand=True)
            module_notebook.enable_traversal()
            module_notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
            self.workspace_module_notebooks[category_name] = module_notebook
            if first_module_notebook is None:
                first_module_notebook = module_notebook

            for name, tab_class in tab_specs:
                tab = tab_class(module_notebook, self)
                self.tabs[name] = tab
                self.module_categories[name] = category_name
                module_notebook.add(tab, text=name)

        self.notebook = first_module_notebook
        self.workspace_category_notebook.bind("<<NotebookTabChanged>>", self._on_workspace_category_changed)
        top_notebook.bind("<<NotebookTabChanged>>", self._on_top_tab_changed)

        log_frame = ttk.LabelFrame(activity_log_tab, text="Recent Operations", style="Card.TLabelframe")
        log_frame.pack(fill="both", expand=True)
        self.log_box = ScrolledText(log_frame, height=10, wrap="word")
        self.log_box.configure(relief="flat", highlightthickness=1)
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)

        self._apply_theme(bool(self.dark_mode_var.get()))
        self._update_window_drag_strip_visibility()

        status_bar = ttk.Frame(root_frame, style="StatusBar.TFrame")
        status_bar.pack(fill="x", pady=(10, 0))
        ttk.Label(status_bar, textvariable=self.status_left_var, style="StatusLeft.TLabel").pack(side="left", padx=(10, 0), pady=4)
        ttk.Label(status_bar, textvariable=self.status_right_var, style="StatusRight.TLabel").pack(side="right", padx=(0, 10), pady=4)

        self.log("Suite ready.")

    def _build_action_group(self, parent: ttk.Frame, column: int, title: str, actions: list[tuple[str, Any, str]]) -> None:
        group = ttk.LabelFrame(parent, text=title, style="QuickGroup.TLabelframe")
        group.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 10, 0))
        body = ttk.Frame(group, style="Card.TFrame")
        body.pack(fill="x", expand=True, padx=8, pady=8)
        for index, (label, command, style_name) in enumerate(actions):
            ttk.Button(body, text=label, style=style_name, command=command).pack(side="left", padx=(0 if index == 0 else 6, 0))

    def _setup_drag_and_drop(self) -> None:
        if os.name != "nt" or windnd is None:
            self.drag_drop_enabled = False
            return
        try:
            self._hook_drag_drop_widget_tree(self.root)
            self.drag_drop_enabled = True
            self.log("Drag and drop enabled.")
        except Exception as exc:
            self.drag_drop_enabled = False
            self.log(f"Drag and drop unavailable: {exc}")

    def _hook_drag_drop_widget_tree(self, widget: tk.Misc) -> None:
        if getattr(widget, "_uch_drop_hooked", False):
            return
        try:
            windnd.hook_dropfiles(widget, func=lambda files: self._queue_external_drop(files))
            setattr(widget, "_uch_drop_hooked", True)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._hook_drag_drop_widget_tree(child)

    @staticmethod
    def _decode_drop_paths(raw_items: list[Any]) -> list[Path]:
        decoded: list[Path] = []
        for item in raw_items:
            try:
                text = os.fsdecode(item).replace("\x00", "").strip()
            except Exception:
                continue
            if len(text) >= 2 and text.startswith("{") and text.endswith("}"):
                text = text[1:-1]
            if not text:
                continue
            path = Path(text).expanduser()
            if path.exists():
                decoded.append(path)
        return ModuleTab._dedupe_paths(decoded)

    def _queue_external_drop(self, raw_items: list[Any]) -> None:
        paths = self._decode_drop_paths(raw_items)
        if not paths:
            return
        self.root.after(0, lambda dropped=paths: self._dispatch_external_drop(dropped))

    def _active_drop_target_tab(self):
        try:
            if self.top_notebook is None:
                return None
            selected_top = self.top_notebook.select()
            if not selected_top:
                return None
            top_widget = self.root.nametowidget(selected_top)
            if self.workspace_tab is not None and top_widget == self.workspace_tab:
                inner_notebook = self._active_workspace_module_notebook()
                if inner_notebook is None:
                    return None
                selected_inner = inner_notebook.select()
                if not selected_inner:
                    return None
                return self.root.nametowidget(selected_inner)
            return top_widget
        except Exception:
            return None

    def _dispatch_external_drop(self, paths: list[Path]) -> None:
        signature = tuple(str(path) for path in paths)
        now = time.time()
        if self._last_drop_signature and self._last_drop_signature[0] == signature and (now - self._last_drop_signature[1]) < 0.75:
            return
        self._last_drop_signature = (signature, now)
        target = self._active_drop_target_tab()
        if target is None or not hasattr(target, "handle_external_drop"):
            self.status_left_var.set("Current tab does not accept dropped files.")
            return
        try:
            handled = bool(target.handle_external_drop(paths))
        except Exception as exc:
            self.error(f"Drag-and-drop failed:\n{exc}")
            return
        if not handled:
            tab_name = getattr(target, "tab_name", "Current tab")
            self.status_left_var.set(f"{tab_name} does not accept the dropped files.")

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

    def _url_scheme(self, value: str) -> str:
        return urllib.parse.urlparse(value.strip()).scheme.lower()

    def _validate_web_url_policy(self, url: str, require_https: bool) -> tuple[bool, str]:
        value = url.strip()
        if not value:
            return False, "No URL was provided."
        scheme = self._url_scheme(value)
        if scheme not in {"http", "https"}:
            return False, f"Unsupported URL scheme '{scheme or '(none)'}'. Only HTTP/HTTPS links are allowed."
        if require_https and scheme != "https":
            return False, "Blocked by security settings: HTTPS is required."
        return True, ""

    def _validate_manifest_source_policy(self, source: str) -> tuple[bool, str]:
        value = source.strip()
        if not value:
            return False, "No update manifest source is configured."
        scheme = self._url_scheme(value)
        if scheme in {"", "file"}:
            if not bool(self.settings.get("security_allow_local_update_manifests", True)):
                return False, "Blocked by security settings: local update manifest files are disabled."
            return True, ""
        if scheme in {"http", "https"}:
            if bool(self.settings.get("security_require_https_for_update_manifest", True)) and scheme != "https":
                return False, "Blocked by security settings: update manifest URL must use HTTPS."
            return True, ""
        return False, f"Unsupported manifest source scheme '{scheme}'."

    def _open_external_url(self, url: str, purpose: str = "external link") -> bool:
        value = url.strip()
        if not value:
            messagebox.showwarning(APP_TITLE, f"No URL is available for {purpose}.")
            return False
        require_https = bool(self.settings.get("security_require_https_for_web_links", True))
        allowed, reason = self._validate_web_url_policy(value, require_https=require_https)
        if not allowed:
            messagebox.showwarning(APP_TITLE, f"Cannot open URL for {purpose}.\n\n{reason}\n\nURL: {value}")
            return False
        if bool(self.settings.get("security_confirm_external_links", True)):
            allow = messagebox.askyesno(
                APP_TITLE,
                f"Open this external link for {purpose}?\n\n{value}",
            )
            if not allow:
                self.log(f"Canceled external link for {purpose}: {value}")
                return False
        try:
            webbrowser.open(value)
            self.log(f"Opened external link for {purpose}: {value}")
            return True
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Failed to open URL:\n{exc}")
            return False

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

    def hover_tooltips_enabled(self) -> bool:
        return bool(self.settings.get("use_hover_tooltips", False))

    def _backend_corner_hover_text(self) -> str:
        rows = self.backends.as_rows()
        total = len(rows)
        available = sum(1 for _, value in rows if value != "Not found")
        missing = total - available
        return (
            f"Backends / Links\n"
            f"Detected: {available}/{total}\n"
            f"Missing: {missing}\n\n"
            "Open the Backends / Links tab to review detected paths, install sources, docs, and commands."
        )

    def _refresh_hover_tooltip_preferences(self) -> None:
        for hover_card in list(self.backend_hover_cards):
            hover_card.refresh_enabled_state()
        for tab in self.tabs.values():
            refresh = getattr(tab, "refresh_hover_tooltip_preference", None)
            if callable(refresh):
                refresh()

    def _open_backend_install_links(self, backend_names: list[str]) -> int:
        opened = 0
        for backend_name in backend_names:
            install_link = self._backend_install_link(backend_name)
            if install_link and self._open_external_url(install_link, purpose=f"{backend_name} install page"):
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
            self._open_external_url(install_link, purpose=f"{backend_name} install page")
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

    def _open_settings_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Settings")
        dialog.geometry("840x670")
        dialog.minsize(780, 610)
        dialog.transient(self.root)
        dialog.grab_set()
        self._apply_window_icon_to(dialog)

        output_var = StringVar(value=str(self.settings.get("output_folder", self.default_output_root)))
        update_url_var = StringVar(value=str(self.settings.get("update_manifest_url", "")))
        dark_mode_var = BooleanVar(value=bool(self.settings.get("dark_mode", False)))
        high_contrast_var = BooleanVar(value=bool(self.settings.get("high_contrast_mode", False)))
        fullscreen_var = BooleanVar(value=bool(self.settings.get("fullscreen", False)))
        borderless_var = BooleanVar(value=bool(self.settings.get("borderless_maximized", False)))
        reduce_motion_var = BooleanVar(value=bool(self.settings.get("reduce_motion", False)))
        ui_scale_var = StringVar(value=str(int(self.settings.get("ui_scale_percent", 100))))
        hover_tooltips_var = BooleanVar(value=bool(self.settings.get("use_hover_tooltips", False)))
        update_check_var = BooleanVar(value=bool(self.settings.get("check_updates_on_startup", True)))
        backend_prompt_var = BooleanVar(value=bool(self.settings.get("prompt_backend_install_on_startup", True)))
        startup_animation_var = BooleanVar(value=bool(self.settings.get("show_startup_animation", True)))
        startup_animation_seconds_var = StringVar(value=str(self.settings.get("startup_animation_seconds", 4.6)))
        ffmpeg_threads_var = StringVar(value=str(self.settings.get("ffmpeg_thread_count", 0)))
        log_lines_var = StringVar(value=str(self.settings.get("log_max_lines", 4000)))
        security_confirm_links_var = BooleanVar(value=bool(self.settings.get("security_confirm_external_links", True)))
        security_https_links_var = BooleanVar(value=bool(self.settings.get("security_require_https_for_web_links", True)))
        security_https_manifest_var = BooleanVar(value=bool(self.settings.get("security_require_https_for_update_manifest", True)))
        security_allow_local_manifest_var = BooleanVar(value=bool(self.settings.get("security_allow_local_update_manifests", True)))

        outer = self._build_draggable_dialog_shell(dialog, drag_label="Drag Settings")

        ttk.Label(outer, text="Settings", font=self._font(14, semibold=True)).pack(anchor="w")
        ttk.Label(
            outer,
            text="Adjust startup, output, visual, and processing defaults for better stability and performance.",
            foreground="#475A72",
            wraplength=760,
        ).pack(anchor="w", pady=(4, 10))

        tabs = ttk.Notebook(outer)
        tabs.pack(fill="both", expand=True)

        general_tab = ttk.Frame(tabs, style="App.TFrame", padding=12)
        startup_tab = ttk.Frame(tabs, style="App.TFrame", padding=12)
        performance_tab = ttk.Frame(tabs, style="App.TFrame", padding=12)
        security_tab = ttk.Frame(tabs, style="App.TFrame", padding=12)
        tabs.add(general_tab, text="General")
        tabs.add(startup_tab, text="Startup / Updates")
        tabs.add(performance_tab, text="Performance / Logs")
        tabs.add(security_tab, text="Security")

        def open_output_from_var() -> None:
            target = Path(output_var.get().strip() or str(self.default_output_root))
            ensure_dir(target)
            self._open_path(target)

        ttk.Label(general_tab, text="Default output folder:").pack(anchor="w")
        output_row = ttk.Frame(general_tab)
        output_row.pack(fill="x", pady=(4, 8))
        ttk.Entry(output_row, textvariable=output_var).pack(side="left", fill="x", expand=True)
        ttk.Button(
            output_row,
            text="Browse",
            command=lambda: self._browse_into_var(output_var, "Choose default output folder"),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            output_row,
            text="Open",
            command=open_output_from_var,
        ).pack(side="left", padx=(8, 0))

        ttk.Label(general_tab, text="Appearance and window mode:").pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(general_tab, text="Dark mode", variable=dark_mode_var).pack(anchor="w", pady=(2, 0))
        ttk.Checkbutton(general_tab, text="High contrast mode", variable=high_contrast_var).pack(anchor="w")
        ttk.Checkbutton(general_tab, text="Start in fullscreen mode", variable=fullscreen_var).pack(anchor="w")
        ttk.Checkbutton(general_tab, text="Start in borderless maximized mode", variable=borderless_var).pack(anchor="w")

        accessibility_row = ttk.Frame(general_tab, style="App.TFrame")
        accessibility_row.pack(anchor="w", pady=(8, 0))
        ttk.Label(accessibility_row, text="Interface scale (%):").pack(side="left")
        ttk.Combobox(
            accessibility_row,
            textvariable=ui_scale_var,
            values=["90", "100", "110", "125", "140", "160"],
            state="readonly",
            width=8,
        ).pack(side="left", padx=(8, 12))
        ttk.Checkbutton(
            accessibility_row,
            text="Reduce motion / skip startup animation effects",
            variable=reduce_motion_var,
        ).pack(side="left")
        ttk.Checkbutton(
            general_tab,
            text="Use hover tooltips instead of always-visible helper text",
            variable=hover_tooltips_var,
        ).pack(anchor="w", pady=(2, 0))
        ttk.Label(
            general_tab,
            text="Scale, contrast, motion, and tooltip preferences are applied live after saving.",
            foreground="#57687F",
            wraplength=760,
        ).pack(anchor="w", pady=(2, 0))

        ttk.Label(general_tab, text="Window controls for this session:").pack(anchor="w", pady=(12, 0))
        session_window_row = ttk.Frame(general_tab, style="App.TFrame")
        session_window_row.pack(anchor="w", pady=(4, 0))
        ttk.Button(session_window_row, text="Toggle Dark Mode", style="Shell.TButton", command=self._toggle_dark_mode_button).pack(side="left")
        ttk.Button(session_window_row, text="Toggle Borderless", style="Shell.TButton", command=self._toggle_borderless_button).pack(side="left", padx=(6, 0))
        ttk.Button(session_window_row, text="Toggle Fullscreen", style="Shell.TButton", command=self._toggle_fullscreen_button).pack(side="left", padx=(6, 0))

        ttk.Label(general_tab, text="Help and reference:").pack(anchor="w", pady=(12, 0))
        help_row = ttk.Frame(general_tab, style="App.TFrame")
        help_row.pack(anchor="w", pady=(4, 0))
        ttk.Button(help_row, text="How-To", style="Shell.TButton", command=self._open_how_to_window).pack(side="left")
        ttk.Button(help_row, text="About", style="Shell.TButton", command=self._show_about).pack(side="left", padx=(6, 0))

        ttk.Label(general_tab, text="Update manifest URL (optional):").pack(anchor="w", pady=(10, 0))
        ttk.Entry(general_tab, textvariable=update_url_var).pack(fill="x", pady=(4, 0))
        ttk.Label(
            general_tab,
            text='Example JSON: {"latest_version":"0.7.3","download_url":"https://example.com/app.exe","notes":"Release notes"}',
            foreground="#57687F",
            wraplength=760,
        ).pack(anchor="w", pady=(4, 0))

        ttk.Checkbutton(startup_tab, text="Check for updates on startup", variable=update_check_var).pack(anchor="w")
        ttk.Checkbutton(
            startup_tab,
            text="Prompt to install missing optional backends on startup",
            variable=backend_prompt_var,
        ).pack(anchor="w", pady=(2, 0))
        ttk.Checkbutton(startup_tab, text="Show startup logo animation", variable=startup_animation_var).pack(anchor="w", pady=(2, 0))

        duration_row = ttk.Frame(startup_tab)
        duration_row.pack(anchor="w", pady=(10, 0))
        ttk.Label(duration_row, text="Startup animation length (seconds):").pack(side="left")
        ttk.Entry(duration_row, width=8, textvariable=startup_animation_seconds_var).pack(side="left", padx=(8, 0))

        ttk.Button(startup_tab, text="Install Missing Backends Now", command=self._open_backend_install_assistant).pack(anchor="w", pady=(12, 0))

        threads_row = ttk.Frame(performance_tab)
        threads_row.pack(anchor="w", pady=(0, 8))
        ttk.Label(threads_row, text="FFmpeg thread count (0 = auto):").pack(side="left")
        ttk.Entry(threads_row, width=8, textvariable=ffmpeg_threads_var).pack(side="left", padx=(8, 0))

        logs_row = ttk.Frame(performance_tab)
        logs_row.pack(anchor="w", pady=(0, 8))
        ttk.Label(logs_row, text="Max activity log lines to keep:").pack(side="left")
        ttk.Entry(logs_row, width=8, textvariable=log_lines_var).pack(side="left", padx=(8, 0))

        ttk.Label(
            performance_tab,
            text=(
                "Higher FFmpeg thread counts can improve speed on multi-core systems, but may increase CPU usage.\n"
                "Log retention controls memory use during long sessions."
            ),
            foreground="#57687F",
            justify="left",
            wraplength=760,
        ).pack(anchor="w", pady=(2, 0))

        ttk.Label(
            security_tab,
            text="Security controls for update checks and external links.",
            foreground="#57687F",
            wraplength=760,
        ).pack(anchor="w", pady=(0, 8))
        ttk.Checkbutton(
            security_tab,
            text="Confirm before opening external web links",
            variable=security_confirm_links_var,
        ).pack(anchor="w")
        ttk.Checkbutton(
            security_tab,
            text="Require HTTPS for external web links (backend pages, update links)",
            variable=security_https_links_var,
        ).pack(anchor="w", pady=(2, 0))
        ttk.Checkbutton(
            security_tab,
            text="Require HTTPS for update manifest URLs",
            variable=security_https_manifest_var,
        ).pack(anchor="w", pady=(2, 0))
        ttk.Checkbutton(
            security_tab,
            text="Allow local update manifest files for offline/test workflows",
            variable=security_allow_local_manifest_var,
        ).pack(anchor="w", pady=(2, 0))
        ttk.Label(
            security_tab,
            text=(
                "Recommended for production: keep HTTPS requirements enabled.\n"
                "Disable local manifests only if you want update checks to require network-hosted manifests."
            ),
            foreground="#57687F",
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        status_var = StringVar(value="")
        ttk.Label(outer, textvariable=status_var, foreground="#8A5A00").pack(anchor="w", pady=(8, 4))

        def restore_defaults() -> None:
            defaults = self._default_settings()
            output_var.set(str(defaults["output_folder"]))
            update_url_var.set(str(defaults["update_manifest_url"]))
            dark_mode_var.set(bool(defaults["dark_mode"]))
            high_contrast_var.set(bool(defaults["high_contrast_mode"]))
            fullscreen_var.set(bool(defaults["fullscreen"]))
            borderless_var.set(bool(defaults["borderless_maximized"]))
            reduce_motion_var.set(bool(defaults["reduce_motion"]))
            ui_scale_var.set(str(defaults["ui_scale_percent"]))
            hover_tooltips_var.set(bool(defaults["use_hover_tooltips"]))
            update_check_var.set(bool(defaults["check_updates_on_startup"]))
            backend_prompt_var.set(bool(defaults["prompt_backend_install_on_startup"]))
            startup_animation_var.set(bool(defaults["show_startup_animation"]))
            startup_animation_seconds_var.set(str(defaults["startup_animation_seconds"]))
            ffmpeg_threads_var.set(str(defaults["ffmpeg_thread_count"]))
            log_lines_var.set(str(defaults["log_max_lines"]))
            security_confirm_links_var.set(bool(defaults["security_confirm_external_links"]))
            security_https_links_var.set(bool(defaults["security_require_https_for_web_links"]))
            security_https_manifest_var.set(bool(defaults["security_require_https_for_update_manifest"]))
            security_allow_local_manifest_var.set(bool(defaults["security_allow_local_update_manifests"]))
            status_var.set("Recommended defaults restored. Save to apply.")

        def save_settings() -> None:
            output_folder = output_var.get().strip() or str(self.default_output_root)
            try:
                animation_seconds = float(startup_animation_seconds_var.get().strip())
            except Exception:
                messagebox.showerror(APP_TITLE, "Startup animation length must be a number between 1.0 and 20.0 seconds.")
                return
            if animation_seconds < 1.0 or animation_seconds > 20.0:
                messagebox.showerror(APP_TITLE, "Startup animation length must be between 1.0 and 20.0 seconds.")
                return

            try:
                ui_scale_percent = int(str(ui_scale_var.get()).strip().replace("%", ""))
            except Exception:
                messagebox.showerror(APP_TITLE, "Interface scale must be a whole number between 90 and 180.")
                return
            if ui_scale_percent < 90 or ui_scale_percent > 180:
                messagebox.showerror(APP_TITLE, "Interface scale must be between 90 and 180.")
                return

            try:
                ffmpeg_threads = int(ffmpeg_threads_var.get().strip())
            except Exception:
                messagebox.showerror(APP_TITLE, "FFmpeg thread count must be an integer from 0 to 128.")
                return
            if ffmpeg_threads < 0 or ffmpeg_threads > 128:
                messagebox.showerror(APP_TITLE, "FFmpeg thread count must be between 0 and 128.")
                return

            try:
                log_max_lines = int(log_lines_var.get().strip())
            except Exception:
                messagebox.showerror(APP_TITLE, "Max activity log lines must be an integer from 200 to 50000.")
                return
            if log_max_lines < 200 or log_max_lines > 50000:
                messagebox.showerror(APP_TITLE, "Max activity log lines must be between 200 and 50000.")
                return

            self.settings["output_folder"] = output_folder
            self.settings["dark_mode"] = bool(dark_mode_var.get())
            self.settings["high_contrast_mode"] = bool(high_contrast_var.get())
            self.settings["fullscreen"] = bool(fullscreen_var.get())
            self.settings["borderless_maximized"] = bool(borderless_var.get())
            self.settings["reduce_motion"] = bool(reduce_motion_var.get())
            self.settings["ui_scale_percent"] = int(ui_scale_percent)
            self.settings["use_hover_tooltips"] = bool(hover_tooltips_var.get())
            if self.settings["fullscreen"] and self.settings["borderless_maximized"]:
                self.settings["borderless_maximized"] = False
                status_var.set("Borderless was disabled because fullscreen is enabled.")
            self.settings["check_updates_on_startup"] = bool(update_check_var.get())
            self.settings["prompt_backend_install_on_startup"] = bool(backend_prompt_var.get())
            self.settings["show_startup_animation"] = bool(startup_animation_var.get())
            self.settings["startup_animation_seconds"] = float(animation_seconds)
            self.settings["ffmpeg_thread_count"] = int(ffmpeg_threads)
            self.settings["log_max_lines"] = int(log_max_lines)
            self.settings["security_confirm_external_links"] = bool(security_confirm_links_var.get())
            self.settings["security_require_https_for_web_links"] = bool(security_https_links_var.get())
            self.settings["security_require_https_for_update_manifest"] = bool(security_https_manifest_var.get())
            self.settings["security_allow_local_update_manifests"] = bool(security_allow_local_manifest_var.get())
            self.settings["update_manifest_url"] = update_url_var.get().strip()
            self.settings["first_run_done"] = True

            self._refresh_paths_from_settings()
            self.dark_mode_var.set(bool(self.settings["dark_mode"]))
            self.fullscreen_var.set(bool(self.settings["fullscreen"]))
            self.borderless_max_var.set(bool(self.settings["borderless_maximized"]))
            self._configure_styles()
            self._apply_window_mode_state()
            self._set_backend_summary_status()
            self._refresh_hover_tooltip_preferences()
            self._save_settings()
            self.log("Settings updated from Settings dialog.")
            dialog.destroy()

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(6, 0))
        ttk.Button(buttons, text="Restore Defaults", command=restore_defaults).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="Save Settings", command=save_settings).pack(side="right", padx=(0, 8))

    def _locate_how_to_file(self) -> Path | None:
        candidates: list[Path] = []
        for base_dir in (self.runtime_dir, self.script_dir, self.resource_dir):
            for name in GUIDE_FILENAMES:
                candidates.append(base_dir / name)
        checked: set[Path] = set()
        for candidate in candidates:
            if candidate in checked:
                continue
            checked.add(candidate)
            if candidate.exists():
                return candidate
        return None

    def _open_how_to_window(self) -> None:
        how_to_path = self._locate_how_to_file()
        if how_to_path is None:
            messagebox.showerror(
                APP_TITLE,
                "Guide file was not found.\n"
                f"Expected one of: {', '.join(GUIDE_FILENAMES)}\n\n"
                "Place README.md in the app folder and try again.",
            )
            return
        try:
            content = how_to_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Failed to open How-To file:\n{exc}")
            return

        window = tk.Toplevel(self.root)
        window.title("Help Guide")
        window.geometry("980x700")
        window.minsize(780, 520)
        window.transient(self.root)
        self._apply_window_icon_to(window)

        outer = ttk.Frame(window, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=f"Help Guide ({how_to_path.name})", font=self._font(12, semibold=True)).pack(anchor="w")
        ttk.Label(outer, text=str(how_to_path), foreground="#57687F", wraplength=920).pack(anchor="w", pady=(2, 8))

        viewer = ScrolledText(outer, wrap="word")
        viewer.pack(fill="both", expand=True)
        viewer.insert("1.0", content)
        viewer.configure(state="disabled")

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(8, 0))

        def open_external() -> None:
            try:
                if os.name == "nt":
                    subprocess.Popen(["notepad.exe", str(how_to_path)])
                else:
                    self._open_path(how_to_path)
            except Exception as exc:
                messagebox.showerror(APP_TITLE, f"Failed to open external editor:\n{exc}")

        ttk.Button(actions, text="Open in Editor", command=open_external).pack(side="left")
        ttk.Button(actions, text="Close", command=window.destroy).pack(side="right")

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

    def _resolve_updater_launch_command(self) -> list[str] | None:
        candidates = [
            self.runtime_dir / UPDATER_EXE_BASENAME,
            self.script_dir / UPDATER_EXE_BASENAME,
            self.script_dir / "dist" / UPDATER_EXE_BASENAME,
            self.runtime_dir / f"{UPDATER_EXE_BASENAME}.exe",
            self.script_dir / f"{UPDATER_EXE_BASENAME}.exe",
            self.script_dir / "dist" / f"{UPDATER_EXE_BASENAME}.exe",
        ]
        for legacy_name in LEGACY_UPDATER_EXE_BASENAMES:
            candidates.extend(
                [
                    self.runtime_dir / legacy_name,
                    self.script_dir / legacy_name,
                    self.script_dir / "dist" / legacy_name,
                    self.runtime_dir / f"{legacy_name}.exe",
                    self.script_dir / f"{legacy_name}.exe",
                    self.script_dir / "dist" / f"{legacy_name}.exe",
                ]
            )
        for candidate in candidates:
            if candidate.exists():
                return [str(candidate)]
        script_candidate = self.script_dir / "suite_updater.py"
        if script_candidate.exists():
            return [sys.executable, str(script_candidate)]
        return None

    def _show_startup_choice_popup(self, latest_version: str = "") -> str:
        # Keep root hidden during startup-choice flow so only one window is visible.
        try:
            self.root.withdraw()
        except Exception:
            pass
        dialog = tk.Toplevel(self.root)
        dialog.title("How do you want to open this app?")
        dialog.resizable(False, False)
        try:
            dialog.transient(self.root)
        except Exception:
            pass
        dialog.grab_set()
        self._apply_window_icon_to(dialog)

        choice = {"value": "open"}
        version_note = latest_version.strip() if latest_version else "a newer version"

        outer = ttk.Frame(dialog, padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="How do you want to open this app?", font=self._font(13, semibold=True)).pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                f"Update {version_note} is available.\n\n"
                "Open Normally: launch the app.\n"
                "Install Updates: run updater first, then continue to the app."
            ),
            justify="left",
            wraplength=460,
        ).pack(anchor="w", pady=(8, 14))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x")

        def choose(value: str) -> None:
            choice["value"] = value
            dialog.destroy()

        ttk.Button(buttons, text="Install Updates", command=lambda: choose("update")).pack(side="left")
        ttk.Button(buttons, text="Open Normally", command=lambda: choose("open")).pack(side="right")

        dialog.protocol("WM_DELETE_WINDOW", lambda: choose("open"))
        dialog.update_idletasks()
        self._center_window_on_screen(dialog)
        self.root.wait_window(dialog)
        return str(choice["value"])

    def _resolve_update_manifest_source(self) -> str:
        manifest_url = str(self.settings.get("update_manifest_url", "")).strip()
        if manifest_url:
            return manifest_url
        local_candidates = [
            self.runtime_dir / "update_manifest.json",
            self.runtime_dir / "update_manifest.example.json",
            self.script_dir / "update_manifest.json",
            self.script_dir / "update_manifest.example.json",
        ]
        found = next((candidate for candidate in local_candidates if candidate.exists()), None)
        return found.as_uri() if found else ""

    def _run_startup_update_flow(self) -> None:
        if not bool(self.settings.get("check_updates_on_startup", True)):
            return
        if self._startup_splash_hidden_by_focus_loss:
            return
        self._startup_update_flow_handled = True
        self.settings["last_update_check"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._save_settings()

        manifest_url = self._resolve_update_manifest_source()
        if not manifest_url:
            return

        allowed_source, source_reason = self._validate_manifest_source_policy(manifest_url)
        if not allowed_source:
            self.log(f"Startup update check blocked: {source_reason} Source: {manifest_url}")
            return

        try:
            with urllib.request.urlopen(manifest_url, timeout=12) as response:
                payload = response.read().decode("utf-8", errors="replace")
            data = json.loads(payload)
            if not isinstance(data, dict):
                self.log(f"Startup update check skipped: manifest is not an object ({manifest_url})")
                return
            latest = str(data.get("latest_version") or data.get("version") or "").strip()
        except Exception as exc:
            self.log(f"Startup update check failed: {exc}")
            return

        if not latest or not is_version_newer(latest, APP_VERSION):
            return

        choice = self._show_startup_choice_popup(latest)
        if choice != "update":
            return

        command = self._resolve_updater_launch_command()
        if not command:
            messagebox.showwarning(
                APP_TITLE,
                "Updater was not found in this installation.\n\nContinuing with normal app startup.",
            )
            return
        try:
            process = subprocess.Popen(command, cwd=str(self.runtime_dir))
            process.wait()
        except Exception as exc:
            messagebox.showerror(
                APP_TITLE,
                f"Failed to open updater:\n{exc}\n\nContinuing with normal app startup.",
            )

    def _show_startup_logo_animation(self, show_main_when_done: bool = True, modal: bool = False) -> None:
        if self.reduced_motion_enabled():
            if show_main_when_done:
                self._show_main_window_after_startup()
            return

        self._startup_animation_active = True
        self._startup_splash_hidden_by_focus_loss = False
        splash = tk.Toplevel(self.root)
        splash.withdraw()
        splash.overrideredirect(True)
        splash.attributes("-topmost", True)
        splash.configure(bg="#0E1726")
        self._apply_window_icon_to(splash)

        width, height = self._scaled(560), self._scaled(320)
        x = (splash.winfo_screenwidth() - width) // 2
        y = (splash.winfo_screenheight() - height) // 2
        splash.geometry(f"{width}x{height}+{x}+{y}")

        container = tk.Frame(splash, bg="#0E1726")
        container.pack(fill="both", expand=True, padx=self._scaled(24), pady=self._scaled(20))

        s = self._scaled
        logo = tk.Canvas(container, width=s(140), height=s(120), bg="#0E1726", highlightthickness=0, bd=0)
        logo.pack(pady=(self._scaled(6), self._scaled(8)))
        logo.create_rectangle(s(30), s(20), s(90), s(100), fill="#3DA4FF", outline="#70C8FF", width=max(1, s(2)))
        logo.create_polygon(s(90), s(20), s(110), s(20), s(110), s(40), s(90), s(40), fill="#70C8FF", outline="#70C8FF")
        line_a = logo.create_line(s(38), s(58), s(106), s(58), fill="#DDF0FF", width=max(2, s(5)), arrow="last", arrowshape=(s(10), s(12), s(5)))
        line_b = logo.create_line(s(106), s(78), s(38), s(78), fill="#9FD6FF", width=max(2, s(5)), arrow="last", arrowshape=(s(10), s(12), s(5)))
        orbit = logo.create_oval(s(64), s(14), s(74), s(24), fill="#FDEB7C", outline="")

        tk.Label(
            container,
            text=APP_TITLE,
            bg="#0E1726",
            fg="#EAF4FF",
            font=self._font(15, semibold=True),
        ).pack()
        tk.Label(
            container,
            text="Preparing modules, backends, and workspace...",
            bg="#0E1726",
            fg="#A5C3E6",
            font=self._font(10),
        ).pack(pady=(self._scaled(4), self._scaled(12)))

        progress = ttk.Progressbar(container, mode="determinate", maximum=100, length=self._scaled(440))
        progress.pack(pady=(0, self._scaled(8)))
        state_label = tk.Label(container, text="Loading UI...", bg="#0E1726", fg="#B9D4F1", font=self._font(9))
        state_label.pack()

        start = time.perf_counter()
        try:
            duration = float(self.settings.get("startup_animation_seconds", 4.6))
        except Exception:
            duration = 4.6
        duration = max(1.0, min(20.0, duration))
        spin_cycles = 1.6
        pulse_cycles = 1.2
        focus_loss_enabled = {"value": False}

        def on_focus_out(_event=None) -> None:
            if not focus_loss_enabled["value"]:
                return
            if not self._startup_animation_active or self._startup_splash_hidden_by_focus_loss:
                return
            if not splash.winfo_exists():
                return
            self._startup_splash_hidden_by_focus_loss = True
            self._startup_deferred_tasks_pending = True
            try:
                splash.withdraw()
            except Exception:
                pass
            try:
                self.root.withdraw()
            except Exception:
                pass

        splash.bind("<FocusOut>", on_focus_out, add="+")

        def tick() -> None:
            if not splash.winfo_exists():
                return
            ratio = min((time.perf_counter() - start) / duration, 1.0)
            progress.configure(value=ratio * 100.0)
            state_label.configure(text=f"Loading UI... {int(ratio * 100):d}%")
            angle = ratio * math.tau * spin_cycles
            cx = s(69) + s(28) * math.cos(angle)
            cy = s(59) + s(28) * math.sin(angle)
            orbit_radius = max(4, s(5))
            logo.coords(orbit, cx - orbit_radius, cy - orbit_radius, cx + orbit_radius, cy + orbit_radius)
            shift = s(4) * math.sin(ratio * math.tau * pulse_cycles)
            logo.coords(line_a, s(38) + shift, s(58), s(106) + shift, s(58))
            logo.coords(line_b, s(106) - shift, s(78), s(38) - shift, s(78))
            if ratio < 1.0:
                splash.after(16, tick)
                return
            self._startup_animation_active = False
            splash.destroy()
            if show_main_when_done:
                self._show_main_window_after_startup()

        splash.update_idletasks()
        splash.deiconify()
        splash.lift()
        try:
            splash.focus_force()
        except Exception:
            pass
        splash.after(220, lambda: focus_loss_enabled.__setitem__("value", True))
        splash.after(20, tick)
        if modal:
            try:
                self.root.wait_window(splash)
            finally:
                self._startup_animation_active = False

    def _center_window_on_screen(self, window: tk.Misc) -> None:
        try:
            window.update_idletasks()
            width = int(window.winfo_width())
            height = int(window.winfo_height())
            if width <= 1 or height <= 1:
                geometry = str(window.geometry())
                size_part = geometry.split("+", 1)[0]
                if "x" in size_part:
                    raw_w, raw_h = size_part.split("x", 1)
                    width = int(raw_w)
                    height = int(raw_h)
            if width <= 1 or height <= 1:
                return
            x = max(0, (window.winfo_screenwidth() - width) // 2)
            y = max(0, (window.winfo_screenheight() - height) // 2)
            window.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            return

    def _preferred_min_window_size(self) -> tuple[int, int]:
        try:
            screen_width = max(1, int(self.root.winfo_screenwidth()))
            screen_height = max(1, int(self.root.winfo_screenheight()))
        except Exception:
            return (self._scaled(1180), self._scaled(780))
        target_min_width = self._scaled(1180)
        target_min_height = self._scaled(780)
        floor_width = self._scaled(920)
        floor_height = self._scaled(660)
        min_width = min(target_min_width, max(floor_width, screen_width - self._scaled(140)))
        min_height = min(target_min_height, max(floor_height, screen_height - self._scaled(180)))
        return (min_width, min_height)

    def _calculate_display_matched_geometry(self) -> str:
        try:
            self.root.update_idletasks()
            screen_width = max(1, int(self.root.winfo_screenwidth()))
            screen_height = max(1, int(self.root.winfo_screenheight()))
            min_width, min_height = self._preferred_min_window_size()
            aspect_ratio = screen_width / max(1, screen_height)
            target_width = min(screen_width - max(96, int(screen_width * 0.08)), max(min_width, int(screen_width * 0.84)))
            target_height = min(screen_height - max(108, int(screen_height * 0.10)), max(min_height, int(screen_height * 0.84)))

            width = max(min_width, target_width)
            height = int(round(width / aspect_ratio))
            if height > target_height:
                height = max(min_height, target_height)
                width = int(round(height * aspect_ratio))

            if width > screen_width:
                width = screen_width
                height = int(round(width / aspect_ratio))
            if height > screen_height:
                height = screen_height
                width = int(round(height * aspect_ratio))

            width = max(720, min(screen_width, width))
            height = max(520, min(screen_height, height))
            x = max(0, (screen_width - width) // 2)
            y = max(0, (screen_height - height) // 2)
            return f"{width}x{height}+{x}+{y}"
        except Exception:
            return "1380x920"

    def _schedule_startup_tasks_once(self) -> None:
        if self._startup_tasks_scheduled:
            return
        self._startup_tasks_scheduled = True
        if self.settings.get("check_updates_on_startup", True) and not self._startup_update_flow_handled:
            self.root.after(1200, lambda: self._check_updates_in_background(interactive=False))
        self.root.after(1800, self._prompt_install_missing_backends_on_startup)

    def _show_main_window_after_startup(self) -> None:
        if self._startup_window_shown:
            return
        self._startup_window_shown = True
        fullscreen_like = bool(self.fullscreen_var.get()) or bool(self.borderless_max_var.get())
        if not fullscreen_like:
            self.root.geometry(self._calculate_display_matched_geometry())
            self._center_window_on_screen(self.root)
            self._normal_geometry = self.root.geometry()
            self._normal_zoomed = False
        self._apply_window_mode_state()
        self.root.deiconify()
        if self._startup_splash_hidden_by_focus_loss and not fullscreen_like:
            self.root.update_idletasks()
            try:
                self.root.iconify()
            except Exception:
                pass
            self._startup_taskbar_attention_pending = True
            _flash_window_taskbar_attention(self.root)
            return
        self.root.lift()
        self.root.focus_force()
        self._schedule_startup_tasks_once()

    def _set_backend_summary_status(self) -> None:
        available = sum(1 for _, value in self.backends.as_rows() if value != "Not found")
        total = len(self.backends.as_rows())
        self.status_right_var.set(f"Backends {available}/{total}")
        if self.backend_corner_button is not None:
            self.backend_corner_button.configure(text=f"Backends {available}/{total}")

    def _check_updates_in_background(self, interactive: bool) -> None:
        if hasattr(self, "_update_thread") and self._update_thread and self._update_thread.is_alive():
            if interactive:
                self._show_app_modal_dialog(
                    APP_TITLE,
                    "Update check is already running.",
                    [("OK", "ok")],
                    default_choice="ok",
                    width=420,
                )
            return

        def worker() -> None:
            manifest_url = self._resolve_update_manifest_source()
            self.settings["last_update_check"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self._save_settings()

            if not manifest_url:
                if interactive:
                    self.call_ui(self._prompt_configure_updates)
                    return
                return

            try:
                allowed_source, source_reason = self._validate_manifest_source_policy(manifest_url)
                if not allowed_source:
                    msg = f"Update check blocked by security settings.\n\n{source_reason}\n\nSource: {manifest_url}"
                    self.log(msg.replace("\n", " "))
                    if interactive:
                        self.error(msg)
                    return
                with urllib.request.urlopen(manifest_url, timeout=12) as response:
                    payload = response.read().decode("utf-8", errors="replace")
                data = json.loads(payload)
                latest = str(data.get("latest_version") or data.get("version") or "").strip()
                download_url = str(data.get("download_url") or data.get("url") or "").strip()
                notes = str(data.get("notes") or "").strip()
                blocked_download_reason = ""

                if download_url:
                    allow_link, link_reason = self._validate_web_url_policy(
                        download_url,
                        require_https=bool(self.settings.get("security_require_https_for_web_links", True)),
                    )
                    if not allow_link:
                        blocked_download_reason = f"Download URL blocked by security settings: {link_reason}"
                        self.log(blocked_download_reason)
                        download_url = ""

                if latest and is_version_newer(latest, APP_VERSION):
                    self.call_ui(lambda: self._show_update_available(latest, download_url, notes, blocked_download_reason))
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
        was_visible = str(self.root.state()) != "withdrawn"
        if was_visible:
            self.root.withdraw()
        try:
            answer = (
                self._show_app_modal_dialog(
                    APP_TITLE,
                    "No update manifest is configured.\n\nOpen setup wizard now to configure update settings?",
                    [("No", "no"), ("Yes", "yes")],
                    default_choice="no",
                    width=520,
                )
                == "yes"
            )
        finally:
            if was_visible:
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
        if answer:
            self._rerun_setup_wizard()

    def _show_update_available(self, latest: str, download_url: str, notes: str, blocked_reason: str = "") -> None:
        details = notes if notes else "No release notes provided."
        if blocked_reason:
            details = f"{details}\n\n{blocked_reason}"
        info_prompt = (
            f"Update available.\n\nCurrent version: {APP_VERSION}\nLatest version: {latest}\n\n"
            f"{details}\n\nClick OK to continue."
        )
        was_visible = str(self.root.state()) != "withdrawn"
        if was_visible:
            self.root.withdraw()
        try:
            self._show_app_modal_dialog(
                APP_TITLE,
                info_prompt,
                [("OK", "ok")],
                default_choice="ok",
                width=620,
            )
        finally:
            if was_visible:
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
        if download_url:
            if (
                self._show_app_modal_dialog(
                    APP_TITLE,
                    "Open download page now?",
                    [("No", "no"), ("Yes", "yes")],
                    default_choice="no",
                    width=420,
                )
                == "yes"
            ):
                self._open_external_url(download_url, purpose=f"update download for version {latest}")
        else:
            suffix = f"\n\n{blocked_reason}" if blocked_reason else ""
            self._show_app_modal_dialog(
                APP_TITLE,
                f"Update {latest} is available, but no download URL was provided.{suffix}",
                [("OK", "ok")],
                default_choice="ok",
                width=620,
            )

    def _current_workspace_category_name(self) -> str | None:
        if self.workspace_category_notebook is None:
            return None
        selected = self.workspace_category_notebook.select()
        if not selected:
            return None
        try:
            return str(self.workspace_category_notebook.tab(selected, "text"))
        except Exception:
            return None

    def _active_workspace_module_notebook(self) -> ttk.Notebook | None:
        category_name = self._current_workspace_category_name()
        if not category_name:
            return None
        return self.workspace_module_notebooks.get(category_name)

    def _current_workspace_module_name(self) -> str | None:
        notebook = self._active_workspace_module_notebook()
        if notebook is None:
            return None
        selected = notebook.select()
        if not selected:
            return None
        try:
            return str(notebook.tab(selected, "text"))
        except Exception:
            return None

    def _on_tab_changed(self, _event=None) -> None:
        current = self._current_workspace_module_name()
        category = self._current_workspace_category_name()
        if current and category:
            self.status_left_var.set(f"Module: {current} [{category}]")
            return
        if current:
            self.status_left_var.set(f"Module: {current}")
            return
        self.status_left_var.set("Workspace")

    def _on_workspace_category_changed(self, _event=None) -> None:
        self._on_tab_changed()

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
        category_name = self.module_categories.get(name)
        if category_name:
            module_notebook = self.workspace_module_notebooks.get(category_name)
            if workspace_index is not None:
                self.top_notebook.select(workspace_index)
            if self.workspace_category_notebook is not None:
                for category_index, category_id in enumerate(self.workspace_category_notebook.tabs()):
                    if self.workspace_category_notebook.tab(category_id, "text") == category_name:
                        self.workspace_category_notebook.select(category_index)
                        break
            if module_notebook is not None:
                for index, tab_id in enumerate(module_notebook.tabs()):
                    if module_notebook.tab(tab_id, "text") == name:
                        module_notebook.select(index)
                        self.status_left_var.set(f"Module: {name} [{category_name}]")
                        return
        for top_index, top_id in enumerate(self.top_notebook.tabs()):
            if self.top_notebook.tab(top_id, "text") == name:
                self.top_notebook.select(top_index)
                self._on_top_tab_changed()
                return

    def _append_log(self, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_box.insert(END, f"[{stamp}] {message}\n")
        try:
            max_lines = int(self.settings.get("log_max_lines", 4000))
        except Exception:
            max_lines = 4000
        max_lines = max(200, min(50000, max_lines))
        total_lines = int(float(self.log_box.index("end-1c").split(".")[0]))
        overflow = total_lines - max_lines
        if overflow > 0:
            self.log_box.delete("1.0", f"{overflow + 1}.0")
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
            **hidden_console_process_kwargs(),
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
        self.hover_cards: list[HoverCard] = []

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
            except OperationCanceledError as exc:
                self.log(str(exc))
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

    def add_hover_tooltip(self, widgets, text_provider) -> None:
        if isinstance(widgets, (list, tuple, set)):
            targets = list(widgets)
        else:
            targets = [widgets]
        for widget in targets:
            if widget is None:
                continue
            self.hover_cards.append(
                HoverCard(
                    widget,
                    text_provider=text_provider,
                    dark_mode_provider=self.app.dark_mode_var.get,
                    enabled_provider=self.app.hover_tooltips_enabled,
                    font_provider=self.app._tooltip_font,
                )
            )

    def refresh_hover_tooltip_preference(self) -> None:
        for hover_card in self.hover_cards:
            hover_card.refresh_enabled_state()

    def apply_inline_help_visibility(self, labels) -> None:
        show_inline_help = not self.app.hover_tooltips_enabled()
        for label in labels:
            manager = str(label.winfo_manager())
            if show_inline_help:
                if manager == "grid":
                    label.grid()
                elif manager == "":
                    pack_info = getattr(label, "_inline_pack_info", None)
                    if pack_info is not None:
                        options = dict(pack_info)
                        if "in" in options:
                            options["in_"] = options.pop("in")
                        label.pack(**options)
            else:
                if manager == "grid":
                    label.grid_remove()
                elif manager == "pack":
                    if not hasattr(label, "_inline_pack_info"):
                        setattr(label, "_inline_pack_info", label.pack_info())
                    label.pack_forget()

    def choose_output_dir(self, variable: StringVar, title: str) -> None:
        raw = filedialog.askdirectory(title=title)
        if raw:
            variable.set(raw)

    def handle_external_drop(self, paths: list[Path]) -> bool:
        return False

    @staticmethod
    def _dedupe_paths(paths: list[Path]) -> list[Path]:
        ordered: list[Path] = []
        seen: set[Path] = set()
        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            ordered.append(path)
        return ordered

    def _collect_drop_files(self, paths: list[Path], expand_directories: bool = True) -> list[Path]:
        collected: list[Path] = []
        for path in self._dedupe_paths(paths):
            if path.is_file():
                collected.append(path)
                continue
            if expand_directories and path.is_dir():
                collected.extend(child for child in path.rglob("*") if child.is_file())
        return self._dedupe_paths(collected)

    def _set_drop_feedback(self, message: str) -> None:
        status_var = getattr(self, "status_var", None)
        if hasattr(status_var, "set"):
            status_var.set(message)
        elif hasattr(self.app, "status_left_var"):
            self.app.status_left_var.set(message)

    def _append_paths_to_queue(self, files: list[Path], listbox: tk.Listbox, candidates: list[Path]) -> tuple[int, int]:
        added = 0
        duplicates = 0
        for path in self._dedupe_paths(candidates):
            if path in files:
                duplicates += 1
                continue
            files.append(path)
            listbox.insert(END, str(path))
            added += 1
        return added, duplicates

    def _add_dropped_file_paths(
        self, files: list[Path], listbox: tk.Listbox, dropped_paths: list[Path], expand_directories: bool = True
    ) -> bool:
        candidates = self._collect_drop_files(dropped_paths, expand_directories=expand_directories)
        if not candidates:
            self._set_drop_feedback("No valid files were found in the dropped selection.")
            return False
        added, duplicates = self._append_paths_to_queue(files, listbox, candidates)
        if added:
            message = f"Added {added} dropped file(s)."
            if duplicates:
                message += f" Skipped {duplicates} duplicate(s)."
            self._set_drop_feedback(message)
        else:
            self._set_drop_feedback("All dropped files were already in the queue.")
        return True

    def _enqueue_paths_by_extension(
        self,
        files: list[Path],
        listbox: tk.Listbox,
        raw_paths: list[Path],
        allowed_exts: set[str],
        source_label: str,
        kind_label: str,
        expand_directories: bool = True,
    ) -> bool:
        candidates = self._collect_drop_files(raw_paths, expand_directories=expand_directories)
        if not candidates:
            self._set_drop_feedback("No valid files were found in the selected input.")
            return False
        matching = [path for path in candidates if path.suffix.lower() in allowed_exts]
        unsupported_count = len(candidates) - len(matching)
        if not matching:
            self._set_drop_feedback(f"Only {kind_label} files are accepted here.")
            return False
        added, duplicates = self._append_paths_to_queue(files, listbox, matching)
        message = f"Added {added} {kind_label} file(s) from {source_label}."
        if duplicates:
            message += f" Skipped {duplicates} duplicate(s)."
        if unsupported_count:
            message += f" Ignored {unsupported_count} unsupported file(s)."
        self._set_drop_feedback(message)
        return True

    def _add_dropped_mixed_paths(self, items: list[Path], listbox: tk.Listbox, dropped_paths: list[Path]) -> bool:
        candidates = [path for path in self._dedupe_paths(dropped_paths) if path.exists()]
        if not candidates:
            self._set_drop_feedback("No valid files or folders were found in the dropped selection.")
            return False
        added, duplicates = self._append_paths_to_queue(items, listbox, candidates)
        if added:
            message = f"Added {added} dropped item(s)."
            if duplicates:
                message += f" Skipped {duplicates} duplicate(s)."
            self._set_drop_feedback(message)
        else:
            self._set_drop_feedback("All dropped items were already in the queue.")
        return True


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
            "Phase 3 (Expanded)\n"
            "- Duplicate Finder\n"
            "- Storage Analyzer\n"
            "- Images: batch resize/export/sharpen workflow\n"
            "- Audio: format/sample-rate/normalize/trim-silence workflow\n"
            "- Video: remux/trim/stream-preset/thumbnail-sheet workflow\n\n"
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
        self.inline_help_labels: list[ttk.Label] = []
        self._build()
        self._populate()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        intro_label = ttk.Label(
            outer,
            text=(
                "Backend links tab: official homepage, documentation, download page, and install command "
                "for each backend used by the suite."
            ),
            wraplength=1180,
        )
        intro_label.pack(anchor="w", pady=(0, 8))
        self.inline_help_labels.append(intro_label)

        top_controls = ttk.Frame(outer)
        top_controls.pack(fill="x", pady=(0, 8))
        refresh_button = ttk.Button(top_controls, text="Refresh Detection", command=self._populate)
        refresh_button.pack(side="left")
        open_homepage_button = ttk.Button(top_controls, text="Open Homepage", command=lambda: self._open_url(self.homepage_var.get()))
        open_homepage_button.pack(side="left", padx=(8, 0))
        open_docs_button = ttk.Button(top_controls, text="Open Docs", command=lambda: self._open_url(self.docs_var.get()))
        open_docs_button.pack(side="left", padx=(8, 0))
        open_download_button = ttk.Button(top_controls, text="Open Download", command=lambda: self._open_url(self.download_var.get()))
        open_download_button.pack(side="left", padx=(8, 0))
        copy_install_button = ttk.Button(top_controls, text="Copy Install Command", command=self._copy_install_command)
        copy_install_button.pack(side="left", padx=(8, 0))
        open_detected_button = ttk.Button(top_controls, text="Open Detected Path", command=self._open_detected_path)
        open_detected_button.pack(side="left", padx=(8, 0))

        self.add_hover_tooltip(
            refresh_button,
            lambda: "Re-scan the system for optional backends and refresh detected paths in this tab.",
        )
        self.add_hover_tooltip(
            open_homepage_button,
            lambda: self._backend_field_tooltip("Homepage", self.homepage_var, "Open the official project home page."),
        )
        self.add_hover_tooltip(
            open_docs_button,
            lambda: self._backend_field_tooltip("Docs", self.docs_var, "Open the documentation for the selected backend."),
        )
        self.add_hover_tooltip(
            open_download_button,
            lambda: self._backend_field_tooltip("Download", self.download_var, "Open the install or download page for the selected backend."),
        )
        self.add_hover_tooltip(
            copy_install_button,
            lambda: self._backend_field_tooltip("Install Command", self.install_cmd_var, "Copy the suggested install command for the selected backend."),
        )
        self.add_hover_tooltip(
            open_detected_button,
            lambda: self._backend_field_tooltip("Detected Path", self.detected_path_var, "Open the installed location for the selected backend."),
        )

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
        self.add_hover_tooltip(
            self.tree,
            lambda: (
                "Select a backend to review its links and detection status.\n"
                "Detected entries point to installed paths. Missing entries still expose install sources."
            ),
        )

        form = ttk.Frame(right, padding=10)
        form.pack(fill="both", expand=True)

        homepage_label = ttk.Label(form, text="Homepage")
        homepage_label.grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        homepage_entry = ttk.Entry(form, textvariable=self.homepage_var)
        homepage_entry.grid(row=0, column=1, sticky="ew", pady=(0, 8))

        docs_label = ttk.Label(form, text="Docs")
        docs_label.grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        docs_entry = ttk.Entry(form, textvariable=self.docs_var)
        docs_entry.grid(row=1, column=1, sticky="ew", pady=(0, 8))

        download_label = ttk.Label(form, text="Download")
        download_label.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        download_entry = ttk.Entry(form, textvariable=self.download_var)
        download_entry.grid(row=2, column=1, sticky="ew", pady=(0, 8))

        install_label = ttk.Label(form, text="Install Command")
        install_label.grid(row=3, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        install_entry = ttk.Entry(form, textvariable=self.install_cmd_var)
        install_entry.grid(row=3, column=1, sticky="ew", pady=(0, 8))

        detected_label = ttk.Label(form, text="Detected Path")
        detected_label.grid(row=4, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        detected_entry = ttk.Entry(form, textvariable=self.detected_path_var)
        detected_entry.grid(row=4, column=1, sticky="ew", pady=(0, 8))
        form.columnconfigure(1, weight=1)

        self.add_hover_tooltip(
            [homepage_label, homepage_entry],
            lambda: self._backend_field_tooltip("Homepage", self.homepage_var, "Official project home page."),
        )
        self.add_hover_tooltip(
            [docs_label, docs_entry],
            lambda: self._backend_field_tooltip("Docs", self.docs_var, "Documentation link for the selected backend."),
        )
        self.add_hover_tooltip(
            [download_label, download_entry],
            lambda: self._backend_field_tooltip("Download", self.download_var, "Download or install page for the selected backend."),
        )
        self.add_hover_tooltip(
            [install_label, install_entry],
            lambda: self._backend_field_tooltip("Install Command", self.install_cmd_var, "Suggested install command for the selected backend."),
        )
        self.add_hover_tooltip(
            [detected_label, detected_entry],
            lambda: self._backend_field_tooltip("Detected Path", self.detected_path_var, "Installed location of the selected backend."),
        )

        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(8, 0))
        self.refresh_hover_tooltip_preference()

    def _selected_backend_name(self) -> str:
        selected = self.tree.selection()
        if not selected:
            return "Selected backend"
        return str(self.tree.item(selected[0], "values")[0])

    def _backend_field_tooltip(self, field_name: str, variable: StringVar, description: str) -> str:
        current_value = variable.get().strip() or "Not available for the selected backend."
        return (
            f"{self._selected_backend_name()} - {field_name}\n"
            f"{description}\n\n"
            f"Current value: {current_value}"
        )

    def refresh_hover_tooltip_preference(self) -> None:
        super().refresh_hover_tooltip_preference()
        self.apply_inline_help_visibility(self.inline_help_labels)

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
        self.app._open_external_url(url, purpose="backend resource")

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
        self.inline_help_labels: list[ttk.Label] = []
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

        audio_label = ttk.Label(options, text="Audio bitrate")
        audio_label.grid(row=1, column=0, sticky="w", padx=(10, 6), pady=(6, 10))
        audio_combo = ttk.Combobox(
            options,
            textvariable=self.audio_bitrate,
            values=["96k", "128k", "160k", "192k", "256k", "320k"],
            state="readonly",
            width=18,
        )
        audio_combo.grid(row=1, column=1, sticky="w", padx=(0, 12), pady=(6, 10))
        audio_help_label = ttk.Label(
            options,
            text=AUDIO_BITRATE_HELP_TEXT,
            justify="left",
            wraplength=240,
        )
        audio_help_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=(10, 12), pady=(0, 10))
        self.inline_help_labels.append(audio_help_label)
        self.add_hover_tooltip([audio_label, audio_combo], lambda: AUDIO_BITRATE_HELP_TEXT)

        video_preset_label = ttk.Label(options, text="Video preset")
        video_preset_label.grid(row=1, column=2, sticky="w", padx=(12, 6), pady=(6, 10))
        video_preset_combo = ttk.Combobox(
            options,
            textvariable=self.video_preset,
            values=["ultrafast", "veryfast", "medium", "slow"],
            state="readonly",
            width=12,
        )
        video_preset_combo.grid(row=1, column=3, sticky="w", padx=(0, 10), pady=(6, 10))
        video_preset_help_label = ttk.Label(
            options,
            text=VIDEO_PRESET_HELP_TEXT,
            justify="left",
            wraplength=250,
        )
        video_preset_help_label.grid(row=2, column=2, columnspan=2, sticky="w", padx=(12, 10), pady=(0, 10))
        self.inline_help_labels.append(video_preset_help_label)
        self.add_hover_tooltip([video_preset_label, video_preset_combo], lambda: VIDEO_PRESET_HELP_TEXT)

        video_crf_label = ttk.Label(options, text="Video quality (CRF)")
        video_crf_label.grid(row=1, column=4, sticky="w", padx=(8, 6), pady=(6, 10))
        video_crf_scale = ttk.Scale(
            options,
            from_=18,
            to=35,
            variable=self.video_crf,
            orient="horizontal",
            command=self._on_video_crf_scale_changed,
        )
        video_crf_scale.grid(
            row=1, column=5, sticky="ew", padx=(0, 10), pady=(6, 10)
        )
        video_crf_value = ttk.Label(options, textvariable=self.video_crf_display, width=4)
        video_crf_value.grid(row=1, column=6, sticky="w", padx=(0, 10), pady=(6, 10))
        video_crf_help_label = ttk.Label(
            options,
            text=VIDEO_CRF_HELP_TEXT,
            justify="left",
            wraplength=300,
        )
        video_crf_help_label.grid(row=2, column=4, columnspan=3, sticky="w", padx=(8, 10), pady=(0, 10))
        self.inline_help_labels.append(video_crf_help_label)
        self.add_hover_tooltip([video_crf_label, video_crf_scale, video_crf_value], lambda: VIDEO_CRF_HELP_TEXT)
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
        self.refresh_hover_tooltip_preference()

    def refresh_hover_tooltip_preference(self) -> None:
        super().refresh_hover_tooltip_preference()
        self.apply_inline_help_visibility(self.inline_help_labels)

    def export_preset(self) -> dict[str, Any]:
        return {
            "target_format": self.target_format.get(),
            "image_quality": self.image_quality.get(),
            "audio_bitrate": self.audio_bitrate.get(),
            "video_preset": self.video_preset.get(),
            "video_crf": self.video_crf.get(),
        }

    def handle_external_drop(self, paths: list[Path]) -> bool:
        candidates = self._collect_drop_files(paths, expand_directories=True)
        if not candidates:
            self._set_drop_feedback("No valid files were found in the dropped selection.")
            return False
        self._enqueue_candidates(candidates)
        return True

    def _normalize_source_suffix(self, value: Path | str) -> str:
        raw = value.suffix if isinstance(value, Path) else str(value)
        suffix = raw.strip().lower()
        if suffix and not suffix.startswith("."):
            suffix = f".{suffix}"
        return self._SUFFIX_ALIASES.get(suffix, suffix)

    def _supported_source_suffix(self, suffix: str) -> bool:
        return suffix in (SUPPORTED_IMAGE_INPUT_EXTS | DATA_EXTS | TEXT_EXTS | MEDIA_EXTS)

    def _targets_for_source_suffix(self, source_suffix: str) -> list[str]:
        suffix = self._normalize_source_suffix(source_suffix)
        if suffix in SUPPORTED_IMAGE_INPUT_EXTS:
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
        "Video (quality via CRF)": "video_crf",
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
        self.inline_help_labels: list[ttk.Label] = []
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

        mode_label = ttk.Label(options, text="Mode")
        mode_label.grid(row=0, column=0, sticky="w", padx=(10, 6), pady=(10, 6))
        mode_combo = ttk.Combobox(options, textvariable=self.mode_var, values=list(self.MODE_MAP.keys()), state="readonly", width=22)
        mode_combo.grid(
            row=0, column=1, sticky="w", padx=(0, 12), pady=(10, 6)
        )

        image_quality_label = ttk.Label(options, text="Image quality")
        image_quality_label.grid(row=0, column=2, sticky="w", padx=(10, 6), pady=(10, 6))
        image_quality_scale = ttk.Scale(options, from_=10, to=100, variable=self.quality_var, orient="horizontal")
        image_quality_scale.grid(
            row=0, column=3, sticky="ew", padx=(0, 10), pady=(10, 6)
        )
        video_crf_label = ttk.Label(options, text="Video quality (CRF)")
        video_crf_label.grid(row=0, column=4, sticky="w", padx=(8, 6), pady=(10, 6))
        video_crf_scale = ttk.Scale(options, from_=18, to=35, variable=self.crf_var, orient="horizontal")
        video_crf_scale.grid(
            row=0, column=5, sticky="ew", padx=(0, 10), pady=(10, 6)
        )
        self.add_hover_tooltip([video_crf_label, video_crf_scale], lambda: VIDEO_CRF_HELP_TEXT)

        audio_label = ttk.Label(options, text="Audio bitrate")
        audio_label.grid(row=1, column=0, sticky="w", padx=(10, 6), pady=(6, 10))
        audio_combo = ttk.Combobox(
            options,
            textvariable=self.bitrate_var,
            values=["96k", "128k", "160k", "192k", "256k", "320k"],
            state="readonly",
            width=12,
        )
        audio_combo.grid(row=1, column=1, sticky="w", padx=(0, 12), pady=(6, 10))
        audio_help_label = ttk.Label(
            options,
            text=AUDIO_BITRATE_HELP_TEXT,
            justify="left",
            wraplength=240,
        )
        audio_help_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=(10, 12), pady=(0, 10))
        self.inline_help_labels.append(audio_help_label)
        self.add_hover_tooltip([audio_label, audio_combo], lambda: AUDIO_BITRATE_HELP_TEXT)

        video_preset_label = ttk.Label(options, text="Video preset")
        video_preset_label.grid(row=1, column=2, sticky="w", padx=(10, 6), pady=(6, 10))
        video_preset_combo = ttk.Combobox(
            options,
            textvariable=self.video_preset_var,
            values=["ultrafast", "veryfast", "medium", "slow"],
            state="readonly",
            width=12,
        )
        video_preset_combo.grid(row=1, column=3, sticky="w", padx=(0, 12), pady=(6, 10))
        video_preset_help_label = ttk.Label(
            options,
            text=VIDEO_PRESET_HELP_TEXT,
            justify="left",
            wraplength=250,
        )
        video_preset_help_label.grid(row=2, column=2, columnspan=2, sticky="w", padx=(10, 10), pady=(0, 10))
        self.inline_help_labels.append(video_preset_help_label)
        self.add_hover_tooltip([video_preset_label, video_preset_combo], lambda: VIDEO_PRESET_HELP_TEXT)

        zip_level_label = ttk.Label(options, text="ZIP level")
        zip_level_label.grid(row=1, column=4, sticky="w", padx=(10, 6), pady=(6, 10))
        zip_level_scale = ttk.Scale(options, from_=1, to=9, variable=self.zip_level_var, orient="horizontal")
        zip_level_scale.grid(
            row=1, column=5, sticky="ew", padx=(0, 10), pady=(6, 10)
        )
        zip_level_help_label = ttk.Label(
            options,
            text=ZIP_LEVEL_HELP_TEXT,
            justify="left",
            wraplength=300,
        )
        zip_level_help_label.grid(row=2, column=4, columnspan=2, sticky="w", padx=(10, 10), pady=(0, 10))
        self.inline_help_labels.append(zip_level_help_label)
        self.add_hover_tooltip([zip_level_label, zip_level_scale], lambda: ZIP_LEVEL_HELP_TEXT)
        video_crf_help_label = ttk.Label(
            options,
            text=VIDEO_CRF_HELP_TEXT,
            justify="left",
            wraplength=540,
        )
        video_crf_help_label.grid(row=3, column=2, columnspan=4, sticky="w", padx=(10, 10), pady=(0, 10))
        self.inline_help_labels.append(video_crf_help_label)
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
        self.refresh_hover_tooltip_preference()

    def refresh_hover_tooltip_preference(self) -> None:
        super().refresh_hover_tooltip_preference()
        self.apply_inline_help_visibility(self.inline_help_labels)

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

    def handle_external_drop(self, paths: list[Path]) -> bool:
        return self._add_dropped_file_paths(self.files, self.listbox, paths, expand_directories=True)

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
        ttk.Button(controls, text="Add Files", command=self._add_media_files).pack(side="left")
        ttk.Button(controls, text="Add Folder", command=self._add_media_folder).pack(side="left", padx=6)
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

    def handle_external_drop(self, paths: list[Path]) -> bool:
        return self._enqueue_media_candidates(paths, source_label="dropped selection")

    def _route_archives_to_archives_tab(self, archive_paths: list[Path]) -> None:
        if not archive_paths:
            return
        archive_tab = self.app.tabs.get("Archives")
        if archive_tab and hasattr(archive_tab, "handle_external_drop"):
            self.app.select_tab("Archives")
            handled = bool(archive_tab.handle_external_drop(archive_paths))
            if handled:
                self.app.status_left_var.set("Archive files were redirected to the Archives tab.")

    def _enqueue_media_candidates(self, raw_paths: list[Path], source_label: str) -> bool:
        candidates = self._collect_drop_files(raw_paths, expand_directories=True)
        if not candidates:
            self._set_drop_feedback("No valid files were found in the dropped selection.")
            return False
        media_files = [path for path in candidates if path.suffix.lower() in MEDIA_EXTS]
        archive_files = [path for path in candidates if is_archive_input_path(path)]
        unsupported_count = len(candidates) - len(media_files) - len(archive_files)

        if archive_files:
            self._route_archives_to_archives_tab(archive_files)

        handled = False
        if media_files:
            added, duplicates = self._append_paths_to_queue(self.files, self.listbox, media_files)
            handled = True
            message = f"Added {added} media file(s) from {source_label}."
            if duplicates:
                message += f" Skipped {duplicates} duplicate(s)."
            if archive_files:
                message += f" Redirected {len(archive_files)} archive file(s) to Archives."
            if unsupported_count:
                message += f" Ignored {unsupported_count} unsupported file(s)."
            self._set_drop_feedback(message)
            return True

        if archive_files:
            handled = True
            message = f"Redirected {len(archive_files)} archive file(s) to Archives."
            if unsupported_count:
                message += f" Ignored {unsupported_count} unsupported file(s)."
            self._set_drop_feedback(message)
            return True

        if unsupported_count:
            self._set_drop_feedback("Only audio/video media files are accepted in Extract.")
        return handled

    def _add_media_files(self) -> None:
        chosen = filedialog.askopenfilenames(title="Select media files")
        if chosen:
            self._enqueue_media_candidates([Path(raw) for raw in chosen], source_label="selection")

    def _add_media_folder(self) -> None:
        raw = filedialog.askdirectory(title="Select folder")
        if raw:
            self._enqueue_media_candidates([Path(raw)], source_label="folder")

    def run_extract(self) -> None:
        if not self.files:
            messagebox.showwarning(APP_TITLE, "Add files before extracting.")
            return
        invalid_files = [path for path in self.files if path.suffix.lower() not in MEDIA_EXTS]
        if invalid_files:
            archive_files = [path for path in invalid_files if is_archive_input_path(path)]
            if archive_files:
                self._route_archives_to_archives_tab(archive_files)
                for item in archive_files:
                    self.remove_path_from_queue(self.files, self.listbox, item)
            remaining_invalid = [path for path in invalid_files if path not in archive_files]
            if remaining_invalid:
                preview = ", ".join(path.name for path in remaining_invalid[:4])
                messagebox.showwarning(
                    APP_TITLE,
                    "Extract accepts audio/video media files only.\n\n"
                    f"Unsupported item(s): {preview}",
                )
                return
            if not self.files:
                self.status_var.set("Archive files were moved to the Archives tab.")
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

    def handle_external_drop(self, paths: list[Path]) -> bool:
        files = self._collect_drop_files(paths, expand_directories=False)
        if not files:
            self._set_drop_feedback("Drop a file onto Metadata to inspect or edit it.")
            return False
        self.file_var.set(str(files[0]))
        self._set_drop_feedback(f"Metadata file set to {files[0].name}.")
        return True

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

    def handle_external_drop(self, paths: list[Path]) -> bool:
        return self._add_dropped_file_paths(self.files, self.listbox, paths, expand_directories=True)


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
        ttk.Label(body, text=f"{self.module_name} Module", font=self.app._font(13, bold=True)).pack(anchor="w")
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


class ImagesTab(ModuleTab):
    tab_name = "Images"

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.files: list[Path] = []
        self.target_format = StringVar(value="keep")
        self.output_dir = StringVar(value=str(self.app.default_output_root / "images"))
        self.max_width_var = IntVar(value=0)
        self.max_height_var = IntVar(value=0)
        self.quality_var = IntVar(value=92)
        self.sharpen_var = IntVar(value=0)
        self.status_var = StringVar(value="Ready.")
        self.progress_percent_var = StringVar(value="0%")
        self.inline_help_labels: list[ttk.Label] = []
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        controls = ttk.Frame(outer)
        controls.pack(fill="x")
        ttk.Button(controls, text="Add Images", command=self._add_images).pack(side="left")
        ttk.Button(controls, text="Add Folder", command=self._add_image_folder).pack(side="left", padx=6)
        ttk.Button(controls, text="Remove Selected", command=lambda: self.remove_selected(self.files, self.listbox)).pack(side="left")
        ttk.Button(controls, text="Clear", command=lambda: self.clear_queue(self.files, self.listbox)).pack(side="left", padx=6)

        queue = ttk.Frame(outer)
        queue.pack(fill="both", expand=True, pady=(8, 8))
        self.listbox = tk.Listbox(queue, selectmode=SINGLE)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(queue, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scroll.set)

        options = ttk.LabelFrame(outer, text="Image Pipeline")
        options.pack(fill="x")

        format_label = ttk.Label(options, text="Output format")
        format_label.grid(row=0, column=0, sticky="w", padx=(10, 6), pady=(10, 6))
        format_combo = ttk.Combobox(
            options,
            textvariable=self.target_format,
            values=["keep", *IMAGE_FORMATS],
            state="readonly",
            width=12,
        )
        format_combo.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(10, 6))

        width_label = ttk.Label(options, text="Max width")
        width_label.grid(row=0, column=2, sticky="w", padx=(10, 6), pady=(10, 6))
        width_spin = ttk.Spinbox(options, from_=0, to=20000, textvariable=self.max_width_var, width=10)
        width_spin.grid(row=0, column=3, sticky="w", padx=(0, 12), pady=(10, 6))

        height_label = ttk.Label(options, text="Max height")
        height_label.grid(row=0, column=4, sticky="w", padx=(10, 6), pady=(10, 6))
        height_spin = ttk.Spinbox(options, from_=0, to=20000, textvariable=self.max_height_var, width=10)
        height_spin.grid(row=0, column=5, sticky="w", padx=(0, 12), pady=(10, 6))

        quality_label = ttk.Label(options, text="Export quality")
        quality_label.grid(row=1, column=0, sticky="w", padx=(10, 6), pady=(6, 10))
        quality_spin = ttk.Spinbox(options, from_=1, to=100, textvariable=self.quality_var, width=10)
        quality_spin.grid(row=1, column=1, sticky="w", padx=(0, 12), pady=(6, 10))

        sharpen_label = ttk.Label(options, text="Sharpen")
        sharpen_label.grid(row=1, column=2, sticky="w", padx=(10, 6), pady=(6, 10))
        sharpen_spin = ttk.Spinbox(options, from_=0, to=300, textvariable=self.sharpen_var, width=10)
        sharpen_spin.grid(row=1, column=3, sticky="w", padx=(0, 12), pady=(6, 10))

        resize_help_label = ttk.Label(options, text=IMAGE_RESIZE_HELP_TEXT, justify="left", wraplength=420)
        resize_help_label.grid(row=2, column=0, columnspan=4, sticky="w", padx=(10, 12), pady=(0, 10))
        sharpen_help_label = ttk.Label(options, text=IMAGE_SHARPEN_HELP_TEXT, justify="left", wraplength=360)
        sharpen_help_label.grid(row=2, column=4, columnspan=2, sticky="w", padx=(10, 12), pady=(0, 10))
        self.inline_help_labels.extend([resize_help_label, sharpen_help_label])

        self.add_hover_tooltip(
            [format_label, format_combo],
            lambda: (
                "Choose the export format. 'keep' keeps the current image format.\n\n"
                "JPEG XL output and camera-raw inputs use ImageMagick when that backend is available."
            ),
        )
        self.add_hover_tooltip([width_label, width_spin, height_label, height_spin], lambda: IMAGE_RESIZE_HELP_TEXT)
        self.add_hover_tooltip(
            [quality_label, quality_spin],
            lambda: "Quality applies to lossy outputs such as JPG, WEBP, HEIC/HEIF, and AVIF.",
        )
        self.add_hover_tooltip([sharpen_label, sharpen_spin], lambda: IMAGE_SHARPEN_HELP_TEXT)

        out_row = ttk.Frame(outer)
        out_row.pack(fill="x", pady=(10, 4))
        ttk.Label(out_row, text="Output folder:").pack(side="left")
        ttk.Entry(out_row, textvariable=self.output_dir).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(out_row, text="Browse", command=lambda: self.choose_output_dir(self.output_dir, "Choose image output folder")).pack(side="left")

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(4, 0))
        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(bottom, textvariable=self.progress_percent_var, width=6).pack(side="left", padx=(0, 10))
        ttk.Button(bottom, text="Run Image Pipeline", command=self.run_images).pack(side="right")
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))
        self.refresh_hover_tooltip_preference()

    def refresh_hover_tooltip_preference(self) -> None:
        super().refresh_hover_tooltip_preference()
        self.apply_inline_help_visibility(self.inline_help_labels)

    def export_preset(self) -> dict[str, Any]:
        return {
            "target_format": self.target_format.get(),
            "max_width": self.max_width_var.get(),
            "max_height": self.max_height_var.get(),
            "quality": self.quality_var.get(),
            "sharpen": self.sharpen_var.get(),
        }

    def apply_preset(self, payload: dict[str, Any]) -> None:
        if "target_format" in payload:
            self.target_format.set(str(payload["target_format"]))
        if "max_width" in payload:
            self.max_width_var.set(int(payload["max_width"]))
        if "max_height" in payload:
            self.max_height_var.set(int(payload["max_height"]))
        if "quality" in payload:
            self.quality_var.set(int(payload["quality"]))
        if "sharpen" in payload:
            self.sharpen_var.set(int(payload["sharpen"]))

    def _add_images(self) -> None:
        chosen = filedialog.askopenfilenames(title="Select image files")
        if chosen:
            self._enqueue_paths_by_extension(
                self.files,
                self.listbox,
                [Path(raw) for raw in chosen],
                SUPPORTED_IMAGE_INPUT_EXTS,
                "selection",
                "image",
            )

    def _add_image_folder(self) -> None:
        raw = filedialog.askdirectory(title="Select folder")
        if raw:
            self._enqueue_paths_by_extension(
                self.files,
                self.listbox,
                [Path(raw)],
                SUPPORTED_IMAGE_INPUT_EXTS,
                "folder",
                "image",
            )

    def handle_external_drop(self, paths: list[Path]) -> bool:
        return self._enqueue_paths_by_extension(
            self.files,
            self.listbox,
            paths,
            SUPPORTED_IMAGE_INPUT_EXTS,
            "dropped selection",
            "image",
        )

    def run_images(self) -> None:
        if not self.files:
            messagebox.showwarning(APP_TITLE, "Add image files before running the image pipeline.")
            return
        out_dir = Path(self.output_dir.get().strip())
        ensure_dir(out_dir)
        options = self.export_preset()
        total = len(self.files)

        def work() -> None:
            self.app.call_ui(lambda: (self.progress.configure(value=0, maximum=total), self.progress_percent_var.set("0%")))
            failures = []
            for index, file_path in enumerate(list(self.files), start=1):
                try:
                    result = self.app.engine.process_image_file(file_path, out_dir, options)
                    self.log(f"{file_path.name} -> {result.name}")
                except Exception as exc:
                    failures.append(f"{file_path.name}: {exc}")
                percent = int((index / total) * 100) if total else 0
                self.app.call_ui(
                    lambda i=index, total_files=total, current=file_path.name, p=percent: (
                        self.progress.configure(value=i),
                        self.progress_percent_var.set(f"{p}%"),
                        self.status_var.set(f"Processed {i}/{total_files}: {current}"),
                    )
                )
                self.app.call_ui(lambda p=file_path: self.remove_path_from_queue(self.files, self.listbox, p))
            if failures:
                raise RuntimeError(f"{len(failures)} image file(s) failed. First issue: {failures[0]}")
            self.app.call_ui(lambda: self.status_var.set(f"Completed image processing for {total} file(s)."))

        self.run_async(work, done_message=f"Images module finished {total} file(s).")


class AudioTab(ModuleTab):
    tab_name = "Audio"

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.files: list[Path] = []
        self.target_format = StringVar(value="mp3")
        self.output_dir = StringVar(value=str(self.app.default_output_root / "audio"))
        self.audio_bitrate = StringVar(value="192k")
        self.sample_rate = StringVar(value="keep")
        self.channels = StringVar(value="keep")
        self.normalize_var = BooleanVar(value=True)
        self.trim_silence_var = BooleanVar(value=False)
        self.status_var = StringVar(value="Ready.")
        self.progress_percent_var = StringVar(value="0%")
        self.inline_help_labels: list[ttk.Label] = []
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        controls = ttk.Frame(outer)
        controls.pack(fill="x")
        ttk.Button(controls, text="Add Audio", command=self._add_audio).pack(side="left")
        ttk.Button(controls, text="Add Folder", command=self._add_audio_folder).pack(side="left", padx=6)
        ttk.Button(controls, text="Remove Selected", command=lambda: self.remove_selected(self.files, self.listbox)).pack(side="left")
        ttk.Button(controls, text="Clear", command=lambda: self.clear_queue(self.files, self.listbox)).pack(side="left", padx=6)

        queue = ttk.Frame(outer)
        queue.pack(fill="both", expand=True, pady=(8, 8))
        self.listbox = tk.Listbox(queue, selectmode=SINGLE)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(queue, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scroll.set)

        options = ttk.LabelFrame(outer, text="Audio Pipeline")
        options.pack(fill="x")

        format_label = ttk.Label(options, text="Output format")
        format_label.grid(row=0, column=0, sticky="w", padx=(10, 6), pady=(10, 6))
        format_combo = ttk.Combobox(options, textvariable=self.target_format, values=AUDIO_PROCESS_FORMATS, state="readonly", width=12)
        format_combo.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(10, 6))

        bitrate_label = ttk.Label(options, text="Audio bitrate")
        bitrate_label.grid(row=0, column=2, sticky="w", padx=(10, 6), pady=(10, 6))
        bitrate_combo = ttk.Combobox(
            options,
            textvariable=self.audio_bitrate,
            values=["96k", "128k", "160k", "192k", "256k", "320k"],
            state="readonly",
            width=12,
        )
        bitrate_combo.grid(row=0, column=3, sticky="w", padx=(0, 12), pady=(10, 6))

        sample_label = ttk.Label(options, text="Sample rate")
        sample_label.grid(row=1, column=0, sticky="w", padx=(10, 6), pady=(6, 10))
        sample_combo = ttk.Combobox(
            options,
            textvariable=self.sample_rate,
            values=["keep", "22050", "32000", "44100", "48000", "96000"],
            state="readonly",
            width=12,
        )
        sample_combo.grid(row=1, column=1, sticky="w", padx=(0, 12), pady=(6, 10))

        channels_label = ttk.Label(options, text="Channels")
        channels_label.grid(row=1, column=2, sticky="w", padx=(10, 6), pady=(6, 10))
        channels_combo = ttk.Combobox(options, textvariable=self.channels, values=["keep", "mono", "stereo"], state="readonly", width=12)
        channels_combo.grid(row=1, column=3, sticky="w", padx=(0, 12), pady=(6, 10))

        normalize_check = ttk.Checkbutton(options, text="Normalize loudness", variable=self.normalize_var)
        normalize_check.grid(row=0, column=4, sticky="w", padx=(10, 12), pady=(10, 6))
        trim_check = ttk.Checkbutton(options, text="Trim start/end silence", variable=self.trim_silence_var)
        trim_check.grid(row=1, column=4, sticky="w", padx=(10, 12), pady=(6, 10))

        sample_help_label = ttk.Label(options, text=AUDIO_SAMPLE_RATE_HELP_TEXT, justify="left", wraplength=340)
        sample_help_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=(10, 12), pady=(0, 10))
        channels_help_label = ttk.Label(options, text=AUDIO_CHANNELS_HELP_TEXT, justify="left", wraplength=320)
        channels_help_label.grid(row=2, column=2, columnspan=2, sticky="w", padx=(10, 12), pady=(0, 10))
        cleanup_help_label = ttk.Label(options, text=AUDIO_CLEANUP_HELP_TEXT, justify="left", wraplength=360)
        cleanup_help_label.grid(row=2, column=4, sticky="w", padx=(10, 12), pady=(0, 10))
        self.inline_help_labels.extend([sample_help_label, channels_help_label, cleanup_help_label])

        self.add_hover_tooltip([format_label, format_combo], lambda: "Choose the delivery format for the processed audio.")
        self.add_hover_tooltip([bitrate_label, bitrate_combo], lambda: AUDIO_BITRATE_HELP_TEXT)
        self.add_hover_tooltip([sample_label, sample_combo], lambda: AUDIO_SAMPLE_RATE_HELP_TEXT)
        self.add_hover_tooltip([channels_label, channels_combo], lambda: AUDIO_CHANNELS_HELP_TEXT)
        self.add_hover_tooltip([normalize_check, trim_check], lambda: AUDIO_CLEANUP_HELP_TEXT)

        out_row = ttk.Frame(outer)
        out_row.pack(fill="x", pady=(10, 4))
        ttk.Label(out_row, text="Output folder:").pack(side="left")
        ttk.Entry(out_row, textvariable=self.output_dir).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(out_row, text="Browse", command=lambda: self.choose_output_dir(self.output_dir, "Choose audio output folder")).pack(side="left")

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(4, 0))
        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(bottom, textvariable=self.progress_percent_var, width=6).pack(side="left", padx=(0, 10))
        ttk.Button(bottom, text="Run Audio Pipeline", command=self.run_audio).pack(side="right")
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))
        self.refresh_hover_tooltip_preference()

    def refresh_hover_tooltip_preference(self) -> None:
        super().refresh_hover_tooltip_preference()
        self.apply_inline_help_visibility(self.inline_help_labels)

    def export_preset(self) -> dict[str, Any]:
        return {
            "target_format": self.target_format.get(),
            "audio_bitrate": self.audio_bitrate.get(),
            "sample_rate": self.sample_rate.get(),
            "channels": self.channels.get(),
            "normalize": bool(self.normalize_var.get()),
            "trim_silence": bool(self.trim_silence_var.get()),
        }

    def apply_preset(self, payload: dict[str, Any]) -> None:
        if "target_format" in payload:
            self.target_format.set(str(payload["target_format"]))
        if "audio_bitrate" in payload:
            self.audio_bitrate.set(str(payload["audio_bitrate"]))
        if "sample_rate" in payload:
            self.sample_rate.set(str(payload["sample_rate"]))
        if "channels" in payload:
            self.channels.set(str(payload["channels"]))
        if "normalize" in payload:
            self.normalize_var.set(bool(payload["normalize"]))
        if "trim_silence" in payload:
            self.trim_silence_var.set(bool(payload["trim_silence"]))

    def _add_audio(self) -> None:
        chosen = filedialog.askopenfilenames(title="Select audio files")
        if chosen:
            self._enqueue_paths_by_extension(self.files, self.listbox, [Path(raw) for raw in chosen], AUDIO_EXTS, "selection", "audio")

    def _add_audio_folder(self) -> None:
        raw = filedialog.askdirectory(title="Select folder")
        if raw:
            self._enqueue_paths_by_extension(self.files, self.listbox, [Path(raw)], AUDIO_EXTS, "folder", "audio")

    def handle_external_drop(self, paths: list[Path]) -> bool:
        return self._enqueue_paths_by_extension(self.files, self.listbox, paths, AUDIO_EXTS, "dropped selection", "audio")

    def run_audio(self) -> None:
        if not self.files:
            messagebox.showwarning(APP_TITLE, "Add audio files before running the audio pipeline.")
            return
        out_dir = Path(self.output_dir.get().strip())
        ensure_dir(out_dir)
        options = self.export_preset()
        total = len(self.files)

        def work() -> None:
            self.app.call_ui(lambda: (self.progress.configure(value=0, maximum=total), self.progress_percent_var.set("0%")))
            failures = []
            for index, file_path in enumerate(list(self.files), start=1):
                try:
                    result = self.app.engine.process_audio_file(file_path, out_dir, options)
                    self.log(f"{file_path.name} -> {result.name}")
                except Exception as exc:
                    failures.append(f"{file_path.name}: {exc}")
                percent = int((index / total) * 100) if total else 0
                self.app.call_ui(
                    lambda i=index, total_files=total, current=file_path.name, p=percent: (
                        self.progress.configure(value=i),
                        self.progress_percent_var.set(f"{p}%"),
                        self.status_var.set(f"Processed {i}/{total_files}: {current}"),
                    )
                )
                self.app.call_ui(lambda p=file_path: self.remove_path_from_queue(self.files, self.listbox, p))
            if failures:
                raise RuntimeError(f"{len(failures)} audio file(s) failed. First issue: {failures[0]}")
            self.app.call_ui(lambda: self.status_var.set(f"Completed audio processing for {total} file(s)."))

        self.run_async(work, done_message=f"Audio module finished {total} file(s).")


class VideoTab(ModuleTab):
    tab_name = "Video"

    MODE_MAP = {
        "Stream Prep": "stream_prep",
        "Remux (container copy)": "remux",
        "Trim Clip": "trim",
        "Thumbnail Sheet": "thumbnail_sheet",
    }

    MODE_HELP = {
        "Stream Prep": "Re-encode for common delivery targets such as YouTube, Discord, Shorts, and TikTok.",
        "Remux (container copy)": "Copy the existing streams into another container without re-encoding when codecs are compatible.",
        "Trim Clip": "Cut a clip using start/end times. This starter prefers stream-copy for fast trims.",
        "Thumbnail Sheet": "Build a contact sheet image by sampling frames at a fixed interval.",
    }

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.files: list[Path] = []
        self.mode_var = StringVar(value="Stream Prep")
        self.mode_help_var = StringVar(value=self.MODE_HELP["Stream Prep"])
        self.output_dir = StringVar(value=str(self.app.default_output_root / "video"))
        self.container_var = StringVar(value="mp4")
        self.trim_container_var = StringVar(value="keep")
        self.trim_start_var = StringVar(value="")
        self.trim_end_var = StringVar(value="")
        self.stream_preset_var = StringVar(value=next(iter(VIDEO_STREAM_PRESETS)))
        self.video_preset_var = StringVar(value="medium")
        self.video_crf_var = IntVar(value=23)
        self.thumb_interval_var = StringVar(value="15")
        self.thumb_columns_var = IntVar(value=4)
        self.thumb_rows_var = IntVar(value=4)
        self.thumb_width_var = IntVar(value=320)
        self.status_var = StringVar(value="Ready.")
        self.progress_percent_var = StringVar(value="0%")
        self.inline_help_labels: list[ttk.Label] = []
        self.mode_var.trace_add("write", self._update_mode_help)
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        controls = ttk.Frame(outer)
        controls.pack(fill="x")
        ttk.Button(controls, text="Add Videos", command=self._add_videos).pack(side="left")
        ttk.Button(controls, text="Add Folder", command=self._add_video_folder).pack(side="left", padx=6)
        ttk.Button(controls, text="Remove Selected", command=lambda: self.remove_selected(self.files, self.listbox)).pack(side="left")
        ttk.Button(controls, text="Clear", command=lambda: self.clear_queue(self.files, self.listbox)).pack(side="left", padx=6)

        queue = ttk.Frame(outer)
        queue.pack(fill="both", expand=True, pady=(8, 8))
        self.listbox = tk.Listbox(queue, selectmode=SINGLE)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(queue, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scroll.set)

        options = ttk.LabelFrame(outer, text="Video Workflows")
        options.pack(fill="x")

        mode_label = ttk.Label(options, text="Workflow")
        mode_label.grid(row=0, column=0, sticky="w", padx=(10, 6), pady=(10, 6))
        mode_combo = ttk.Combobox(options, textvariable=self.mode_var, values=list(self.MODE_MAP.keys()), state="readonly", width=22)
        mode_combo.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(10, 6))
        mode_help_label = ttk.Label(options, textvariable=self.mode_help_var, justify="left", wraplength=760)
        mode_help_label.grid(row=0, column=2, columnspan=4, sticky="w", padx=(10, 12), pady=(10, 6))
        self.inline_help_labels.append(mode_help_label)

        remux_label = ttk.Label(options, text="Remux container")
        remux_label.grid(row=1, column=0, sticky="w", padx=(10, 6), pady=(6, 6))
        remux_combo = ttk.Combobox(options, textvariable=self.container_var, values=VIDEO_REMUX_FORMATS, state="readonly", width=12)
        remux_combo.grid(row=1, column=1, sticky="w", padx=(0, 12), pady=(6, 6))

        trim_start_label = ttk.Label(options, text="Trim start")
        trim_start_label.grid(row=1, column=2, sticky="w", padx=(10, 6), pady=(6, 6))
        trim_start_entry = ttk.Entry(options, textvariable=self.trim_start_var, width=12)
        trim_start_entry.grid(row=1, column=3, sticky="w", padx=(0, 12), pady=(6, 6))

        trim_end_label = ttk.Label(options, text="Trim end")
        trim_end_label.grid(row=1, column=4, sticky="w", padx=(10, 6), pady=(6, 6))
        trim_end_entry = ttk.Entry(options, textvariable=self.trim_end_var, width=12)
        trim_end_entry.grid(row=1, column=5, sticky="w", padx=(0, 12), pady=(6, 6))

        trim_container_label = ttk.Label(options, text="Trim output")
        trim_container_label.grid(row=2, column=0, sticky="w", padx=(10, 6), pady=(6, 6))
        trim_container_combo = ttk.Combobox(
            options,
            textvariable=self.trim_container_var,
            values=["keep", *VIDEO_REMUX_FORMATS],
            state="readonly",
            width=12,
        )
        trim_container_combo.grid(row=2, column=1, sticky="w", padx=(0, 12), pady=(6, 6))

        stream_preset_label = ttk.Label(options, text="Stream preset")
        stream_preset_label.grid(row=2, column=2, sticky="w", padx=(10, 6), pady=(6, 6))
        stream_preset_combo = ttk.Combobox(
            options,
            textvariable=self.stream_preset_var,
            values=list(VIDEO_STREAM_PRESETS.keys()),
            state="readonly",
            width=22,
        )
        stream_preset_combo.grid(row=2, column=3, sticky="w", padx=(0, 12), pady=(6, 6))

        encode_preset_label = ttk.Label(options, text="Encode preset")
        encode_preset_label.grid(row=2, column=4, sticky="w", padx=(10, 6), pady=(6, 6))
        encode_preset_combo = ttk.Combobox(
            options,
            textvariable=self.video_preset_var,
            values=["ultrafast", "veryfast", "medium", "slow"],
            state="readonly",
            width=12,
        )
        encode_preset_combo.grid(row=2, column=5, sticky="w", padx=(0, 12), pady=(6, 6))

        crf_label = ttk.Label(options, text="Video quality (CRF)")
        crf_label.grid(row=3, column=0, sticky="w", padx=(10, 6), pady=(6, 10))
        crf_spin = ttk.Spinbox(options, from_=18, to=35, textvariable=self.video_crf_var, width=10)
        crf_spin.grid(row=3, column=1, sticky="w", padx=(0, 12), pady=(6, 10))

        thumb_interval_label = ttk.Label(options, text="Sheet interval (s)")
        thumb_interval_label.grid(row=3, column=2, sticky="w", padx=(10, 6), pady=(6, 10))
        thumb_interval_entry = ttk.Entry(options, textvariable=self.thumb_interval_var, width=12)
        thumb_interval_entry.grid(row=3, column=3, sticky="w", padx=(0, 12), pady=(6, 10))

        thumb_columns_label = ttk.Label(options, text="Columns")
        thumb_columns_label.grid(row=3, column=4, sticky="w", padx=(10, 6), pady=(6, 10))
        thumb_columns_spin = ttk.Spinbox(options, from_=1, to=12, textvariable=self.thumb_columns_var, width=8)
        thumb_columns_spin.grid(row=3, column=5, sticky="w", padx=(0, 12), pady=(6, 10))

        thumb_rows_label = ttk.Label(options, text="Rows")
        thumb_rows_label.grid(row=4, column=0, sticky="w", padx=(10, 6), pady=(0, 10))
        thumb_rows_spin = ttk.Spinbox(options, from_=1, to=12, textvariable=self.thumb_rows_var, width=8)
        thumb_rows_spin.grid(row=4, column=1, sticky="w", padx=(0, 12), pady=(0, 10))

        thumb_width_label = ttk.Label(options, text="Frame width")
        thumb_width_label.grid(row=4, column=2, sticky="w", padx=(10, 6), pady=(0, 10))
        thumb_width_spin = ttk.Spinbox(options, from_=120, to=1200, textvariable=self.thumb_width_var, width=10)
        thumb_width_spin.grid(row=4, column=3, sticky="w", padx=(0, 12), pady=(0, 10))

        trim_help_label = ttk.Label(options, text=VIDEO_TRIM_HELP_TEXT, justify="left", wraplength=420)
        trim_help_label.grid(row=5, column=0, columnspan=3, sticky="w", padx=(10, 12), pady=(0, 10))
        thumbnail_help_label = ttk.Label(options, text=VIDEO_THUMBNAIL_HELP_TEXT, justify="left", wraplength=420)
        thumbnail_help_label.grid(row=5, column=3, columnspan=3, sticky="w", padx=(10, 12), pady=(0, 10))
        self.inline_help_labels.extend([trim_help_label, thumbnail_help_label])

        self.add_hover_tooltip([mode_label, mode_combo], lambda: VIDEO_MODE_HELP_TEXT)
        self.add_hover_tooltip([mode_help_label], lambda: self.mode_help_var.get())
        self.add_hover_tooltip([remux_label, remux_combo], lambda: "Remux changes only the container. Compatible streams can be copied without re-encoding.")
        self.add_hover_tooltip([trim_start_label, trim_start_entry, trim_end_label, trim_end_entry, trim_container_label, trim_container_combo], lambda: VIDEO_TRIM_HELP_TEXT)
        self.add_hover_tooltip([stream_preset_label, stream_preset_combo], lambda: "Destination preset that sets output size, frame rate, and target bitrate.")
        self.add_hover_tooltip([encode_preset_label, encode_preset_combo], lambda: VIDEO_PRESET_HELP_TEXT)
        self.add_hover_tooltip([crf_label, crf_spin], lambda: VIDEO_CRF_HELP_TEXT)
        self.add_hover_tooltip([thumb_interval_label, thumb_interval_entry, thumb_columns_label, thumb_columns_spin, thumb_rows_label, thumb_rows_spin, thumb_width_label, thumb_width_spin], lambda: VIDEO_THUMBNAIL_HELP_TEXT)

        out_row = ttk.Frame(outer)
        out_row.pack(fill="x", pady=(10, 4))
        ttk.Label(out_row, text="Output folder:").pack(side="left")
        ttk.Entry(out_row, textvariable=self.output_dir).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(out_row, text="Browse", command=lambda: self.choose_output_dir(self.output_dir, "Choose video output folder")).pack(side="left")

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(4, 0))
        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(bottom, textvariable=self.progress_percent_var, width=6).pack(side="left", padx=(0, 10))
        ttk.Button(bottom, text="Run Video Workflow", command=self.run_video).pack(side="right")
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))
        self.refresh_hover_tooltip_preference()

    def refresh_hover_tooltip_preference(self) -> None:
        super().refresh_hover_tooltip_preference()
        self.apply_inline_help_visibility(self.inline_help_labels)

    def _update_mode_help(self, *_args) -> None:
        self.mode_help_var.set(self.MODE_HELP.get(self.mode_var.get(), VIDEO_MODE_HELP_TEXT))

    def export_preset(self) -> dict[str, Any]:
        return {
            "mode_name": self.mode_var.get(),
            "mode_key": self.MODE_MAP[self.mode_var.get()],
            "container": self.container_var.get(),
            "trim_container": self.trim_container_var.get(),
            "trim_start": self.trim_start_var.get(),
            "trim_end": self.trim_end_var.get(),
            "stream_preset_name": self.stream_preset_var.get(),
            "video_preset": self.video_preset_var.get(),
            "video_crf": self.video_crf_var.get(),
            "thumb_interval": self.thumb_interval_var.get(),
            "thumb_columns": self.thumb_columns_var.get(),
            "thumb_rows": self.thumb_rows_var.get(),
            "thumb_width": self.thumb_width_var.get(),
        }

    def apply_preset(self, payload: dict[str, Any]) -> None:
        if "mode_name" in payload and payload["mode_name"] in self.MODE_MAP:
            self.mode_var.set(str(payload["mode_name"]))
        if "container" in payload:
            self.container_var.set(str(payload["container"]))
        if "trim_container" in payload:
            self.trim_container_var.set(str(payload["trim_container"]))
        if "trim_start" in payload:
            self.trim_start_var.set(str(payload["trim_start"]))
        if "trim_end" in payload:
            self.trim_end_var.set(str(payload["trim_end"]))
        if "stream_preset_name" in payload and str(payload["stream_preset_name"]) in VIDEO_STREAM_PRESETS:
            self.stream_preset_var.set(str(payload["stream_preset_name"]))
        if "video_preset" in payload:
            self.video_preset_var.set(str(payload["video_preset"]))
        if "video_crf" in payload:
            self.video_crf_var.set(int(payload["video_crf"]))
        if "thumb_interval" in payload:
            self.thumb_interval_var.set(str(payload["thumb_interval"]))
        if "thumb_columns" in payload:
            self.thumb_columns_var.set(int(payload["thumb_columns"]))
        if "thumb_rows" in payload:
            self.thumb_rows_var.set(int(payload["thumb_rows"]))
        if "thumb_width" in payload:
            self.thumb_width_var.set(int(payload["thumb_width"]))
        self._update_mode_help()

    def _add_videos(self) -> None:
        chosen = filedialog.askopenfilenames(title="Select video files")
        if chosen:
            self._enqueue_paths_by_extension(self.files, self.listbox, [Path(raw) for raw in chosen], VIDEO_EXTS, "selection", "video")

    def _add_video_folder(self) -> None:
        raw = filedialog.askdirectory(title="Select folder")
        if raw:
            self._enqueue_paths_by_extension(self.files, self.listbox, [Path(raw)], VIDEO_EXTS, "folder", "video")

    def handle_external_drop(self, paths: list[Path]) -> bool:
        return self._enqueue_paths_by_extension(self.files, self.listbox, paths, VIDEO_EXTS, "dropped selection", "video")

    def run_video(self) -> None:
        if not self.files:
            messagebox.showwarning(APP_TITLE, "Add video files before running the video workflow.")
            return
        mode_name = self.mode_var.get()
        mode_key = self.MODE_MAP[mode_name]
        if mode_key == "trim" and not self.trim_start_var.get().strip() and not self.trim_end_var.get().strip():
            messagebox.showwarning(APP_TITLE, "Enter a trim start time, an end time, or both before running Trim Clip.")
            return
        if mode_key == "thumbnail_sheet":
            try:
                if float(self.thumb_interval_var.get().strip()) <= 0:
                    raise ValueError
            except Exception:
                messagebox.showwarning(APP_TITLE, "Sheet interval must be a positive number of seconds.")
                return
        out_dir = Path(self.output_dir.get().strip())
        ensure_dir(out_dir)
        options = self.export_preset()
        total = len(self.files)

        def work() -> None:
            self.app.call_ui(lambda: (self.progress.configure(value=0, maximum=total), self.progress_percent_var.set("0%")))
            failures = []
            for index, file_path in enumerate(list(self.files), start=1):
                try:
                    result = self.app.engine.process_video_file(file_path, out_dir, mode_key, options)
                    self.log(f"{file_path.name} -> {result.name}")
                except Exception as exc:
                    failures.append(f"{file_path.name}: {exc}")
                percent = int((index / total) * 100) if total else 0
                self.app.call_ui(
                    lambda i=index, total_files=total, current=file_path.name, p=percent: (
                        self.progress.configure(value=i),
                        self.progress_percent_var.set(f"{p}%"),
                        self.status_var.set(f"Processed {i}/{total_files}: {current}"),
                    )
                )
                self.app.call_ui(lambda p=file_path: self.remove_path_from_queue(self.files, self.listbox, p))
            if failures:
                raise RuntimeError(f"{len(failures)} video file(s) failed. First issue: {failures[0]}")
            self.app.call_ui(lambda: self.status_var.set(f"Completed video workflow for {total} file(s)."))

        self.run_async(work, done_message=f"Video module finished {total} file(s).")


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

    def handle_external_drop(self, paths: list[Path]) -> bool:
        return self._add_dropped_mixed_paths(self.inputs, self.listbox, paths)

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

    def handle_external_drop(self, paths: list[Path]) -> bool:
        return self._add_dropped_file_paths(self.files, self.listbox, paths, expand_directories=True)


class DuplicateFinderTab(ModuleTab):
    tab_name = "Duplicate Finder"

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.folder_var = StringVar(value=str(Path.home()))
        self.min_size_mb = IntVar(value=1)
        self.status_var = StringVar(value="Ready.")
        self.cancel_scan_event = threading.Event()
        self.scan_button: ttk.Button | None = None
        self.cancel_button: ttk.Button | None = None
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        top = ttk.Frame(outer)
        top.pack(fill="x")
        folder_label = ttk.Label(top, text="Folder")
        folder_label.pack(side="left")
        folder_entry = ttk.Entry(top, textvariable=self.folder_var)
        folder_entry.pack(side="left", fill="x", expand=True, padx=(8, 8))
        browse_button = ttk.Button(top, text="Browse", command=lambda: self.choose_output_dir(self.folder_var, "Choose folder to scan"))
        browse_button.pack(side="left")
        min_size_label = ttk.Label(top, text="Min size (MB)")
        min_size_label.pack(side="left", padx=(14, 6))
        min_size_spinbox = ttk.Spinbox(top, from_=0, to=2048, textvariable=self.min_size_mb, width=8)
        min_size_spinbox.pack(side="left")
        self.cancel_button = ttk.Button(top, text="Cancel Scan", command=self.cancel_scan, state="disabled")
        self.cancel_button.pack(side="right")
        self.scan_button = ttk.Button(top, text="Scan Duplicates", command=self.scan)
        self.scan_button.pack(side="right", padx=(0, 8))

        self.add_hover_tooltip(
            [folder_label, folder_entry, browse_button],
            lambda: "Choose the folder tree to scan for duplicate files.",
        )
        self.add_hover_tooltip(
            [min_size_label, min_size_spinbox],
            lambda: (
                f"Skip files smaller than the configured threshold.\n"
                f"Current minimum: {self.min_size_mb.get()} MB."
            ),
        )
        self.add_hover_tooltip(
            self.scan_button,
            lambda: (
                "Scan for duplicates using a staged approach:\n"
                "size filter -> quick fingerprint -> full SHA256 verification."
            ),
        )
        self.add_hover_tooltip(
            self.cancel_button,
            lambda: "Request cancellation of the current duplicate scan.",
        )

        self.tree = ttk.Treeview(outer, columns=("hash", "size", "path"), show="headings")
        self.tree.heading("hash", text="SHA256")
        self.tree.heading("size", text="Size")
        self.tree.heading("path", text="File path")
        self.tree.column("hash", width=220)
        self.tree.column("size", width=120)
        self.tree.column("path", width=900)
        self.tree.pack(fill="both", expand=True, pady=(8, 0))
        self.add_hover_tooltip(
            self.tree,
            lambda: "Verified duplicate results. Each group shares the same SHA256 hash and file size.",
        )
        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=100, value=0)
        self.progress.pack(fill="x", pady=(8, 0))
        self.add_hover_tooltip(
            self.progress,
            lambda: "Progress through duplicate candidate filtering and full SHA256 verification.",
        )
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))
        self.refresh_hover_tooltip_preference()

    def _set_scan_running(self, running: bool) -> None:
        if self.scan_button is not None:
            self.scan_button.configure(state="disabled" if running else "normal")
        if self.cancel_button is not None:
            self.cancel_button.configure(state="normal" if running else "disabled")

    def _check_cancel_scan(self) -> None:
        if self.cancel_scan_event.is_set():
            raise OperationCanceledError("Duplicate scan canceled by user.")

    def cancel_scan(self) -> None:
        if self.worker and self.worker.is_alive():
            self.cancel_scan_event.set()
            self.status_var.set("Cancel requested... stopping current scan.")
            self.log("Cancellation requested for duplicate scan.")

    def scan(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(APP_TITLE, f"{self.tab_name} is already running.")
            return
        root = Path(self.folder_var.get().strip())
        if not root.exists():
            messagebox.showerror(APP_TITLE, "Scan folder does not exist.")
            return
        min_bytes = self.min_size_mb.get() * 1024 * 1024
        self.cancel_scan_event.clear()
        self._set_scan_running(True)

        def work() -> None:
            try:
                self.app.call_ui(
                    lambda: (
                        self.progress.stop(),
                        self.progress.configure(mode="indeterminate", value=0),
                        self.progress.start(12),
                        self.status_var.set("Scanning files..."),
                    )
                )
                candidates: dict[int, list[Path]] = {}
                total_seen = 0
                skipped_errors = 0
                for current_root, _, files in os.walk(root):
                    self._check_cancel_scan()
                    for name in files:
                        self._check_cancel_scan()
                        path = Path(current_root) / name
                        try:
                            size = path.stat().st_size
                        except Exception:
                            skipped_errors += 1
                            continue
                        total_seen += 1
                        if total_seen % 400 == 0:
                            self.app.call_ui(
                                lambda seen=total_seen: self.status_var.set(f"Scanning files... {seen} inspected")
                            )
                        if size < min_bytes:
                            continue
                        candidates.setdefault(size, []).append(path)

                size_collision_groups = [(size, group) for size, group in candidates.items() if len(group) > 1]
                fingerprint_total = sum(len(group) for _, group in size_collision_groups)
                self.app.call_ui(
                    lambda total=fingerprint_total: (
                        self.progress.stop(),
                        self.progress.configure(mode="determinate", maximum=max(1, total), value=0),
                        self.status_var.set(
                            "No same-size collisions found. Finalizing..."
                            if total == 0
                            else f"Prefiltering {total} same-size files..."
                        ),
                    )
                )

                duplicates: list[tuple[str, int, Path]] = []
                if fingerprint_total > 0:
                    possible_duplicate_groups: list[tuple[int, list[Path]]] = []
                    fingerprints_done = 0
                    for size, group in size_collision_groups:
                        self._check_cancel_scan()
                        by_fingerprint: dict[str, list[Path]] = {}
                        for item in group:
                            self._check_cancel_scan()
                            try:
                                fingerprint = quick_file_fingerprint(item, size)
                            except Exception:
                                continue
                            by_fingerprint.setdefault(fingerprint, []).append(item)
                            fingerprints_done += 1
                            if fingerprints_done % 50 == 0 or fingerprints_done == fingerprint_total:
                                self.app.call_ui(
                                    lambda done=fingerprints_done, total=fingerprint_total: (
                                        self.progress.configure(value=done),
                                        self.status_var.set(f"Prefiltering candidates... {done}/{total}"),
                                    )
                                )
                        for fingerprint_group in by_fingerprint.values():
                            if len(fingerprint_group) > 1:
                                possible_duplicate_groups.append((size, fingerprint_group))

                    full_hash_total = sum(len(group) for _, group in possible_duplicate_groups)
                    total_work = fingerprint_total + full_hash_total
                    self.app.call_ui(
                        lambda work_total=total_work, done=fingerprint_total, hash_total=full_hash_total: (
                            self.progress.configure(maximum=max(1, work_total), value=done),
                            self.status_var.set(
                                "No matching fingerprints found. Finalizing..."
                                if hash_total == 0
                                else f"Verifying with SHA256... 0/{hash_total}"
                            ),
                        )
                    )

                    hashed_done = 0
                    for size, group in possible_duplicate_groups:
                        self._check_cancel_scan()
                        by_hash: dict[str, list[Path]] = {}
                        for item in group:
                            self._check_cancel_scan()
                            try:
                                digest = hash_file(item, "sha256")
                            except Exception:
                                continue
                            by_hash.setdefault(digest, []).append(item)
                            hashed_done += 1
                            if hashed_done % 25 == 0 or hashed_done == full_hash_total:
                                self.app.call_ui(
                                    lambda done=hashed_done, total=full_hash_total, base=fingerprint_total: (
                                        self.progress.configure(value=base + done),
                                        self.status_var.set(f"Verifying with SHA256... {done}/{total}"),
                                    )
                                )
                        for digest, hashed_group in by_hash.items():
                            if len(hashed_group) > 1:
                                for file_path in hashed_group:
                                    duplicates.append((digest, size, file_path))
                else:
                    full_hash_total = 0
                    total_work = 1

                duplicate_entries = sorted(duplicates, key=lambda row: (row[0], str(row[2]).lower()))
                duplicate_groups = len({f"{digest}:{size}" for digest, size, _ in duplicate_entries})

                def render() -> None:
                    self.progress.stop()
                    self.progress.configure(mode="determinate", maximum=max(1, total_work), value=max(1, total_work))
                    for row in self.tree.get_children():
                        self.tree.delete(row)
                    for digest, size, path in duplicate_entries:
                        self.tree.insert("", "end", values=(digest, human_size(size), str(path)))
                    self.status_var.set(
                        "Scanned "
                        f"{total_seen} files ({skipped_errors} unreadable skipped). "
                        f"Found {len(duplicate_entries)} duplicate files across {duplicate_groups} groups."
                    )

                self.app.call_ui(render)
            except OperationCanceledError:
                self.app.call_ui(
                    lambda: (
                        self.progress.stop(),
                        self.progress.configure(mode="determinate", maximum=100, value=0),
                        self.status_var.set("Duplicate scan canceled."),
                    )
                )
                raise
            finally:
                self.app.call_ui(lambda: self._set_scan_running(False))

        self.run_async(work, done_message="Duplicate scan complete.")

    def handle_external_drop(self, paths: list[Path]) -> bool:
        for path in self._dedupe_paths(paths):
            target = path if path.is_dir() else path.parent
            if target.exists():
                self.folder_var.set(str(target))
                self._set_drop_feedback(f"Duplicate scan folder set to {target}.")
                return True
        self._set_drop_feedback("Drop a folder or a file whose parent folder should be scanned.")
        return False


class StorageAnalyzerTab(ModuleTab):
    tab_name = "Storage Analyzer"

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.folder_var = StringVar(value=str(Path.home()))
        self.top_n_var = IntVar(value=30)
        self.status_var = StringVar(value="Ready.")
        self.progress_percent_var = StringVar(value="0%")
        self.cancel_scan_event = threading.Event()
        self.analyze_button: ttk.Button | None = None
        self.cancel_button: ttk.Button | None = None
        self.progress: ttk.Progressbar | None = None
        self.view_notebook: ttk.Notebook | None = None
        self.graph_canvases: dict[str, tk.Canvas] = {}
        self.graph_hint_vars: dict[str, StringVar] = {}
        self.tree_views: dict[str, ttk.Treeview] = {}
        self.tree_entries: dict[str, dict[str, StorageViewEntry]] = {}
        self.graph_entries: dict[str, list[StorageViewEntry]] = {}
        self._render_after_ids: dict[str, str] = {}
        self.root_total_size = 0
        self.inline_help_labels: list[ttk.Label] = []
        self.view_descriptions = {
            "top_level": "Pie chart of the largest direct children in the selected folder.",
            "largest_files": "Pie chart of the largest individual files within the selected folder tree.",
            "largest_folders": "Pie chart comparing the largest cumulative folders within the selected folder tree.",
        }
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, style="App.TFrame", padding=12)
        outer.pack(fill="both", expand=True)

        controls_box = ttk.LabelFrame(outer, text="Storage Analysis", style="Card.TLabelframe")
        controls_box.pack(fill="x")
        controls_body = ttk.Frame(controls_box, style="Card.TFrame")
        controls_body.pack(fill="x", padx=12, pady=12)

        folder_row = ttk.Frame(controls_body, style="Card.TFrame")
        folder_row.pack(fill="x")
        folder_label = ttk.Label(folder_row, text="Folder", style="CardBody.TLabel")
        folder_label.pack(side="left")
        folder_entry = ttk.Entry(folder_row, textvariable=self.folder_var)
        folder_entry.pack(side="left", fill="x", expand=True, padx=(8, 8))
        browse_button = ttk.Button(
            folder_row,
            text="Browse",
            style="QuietApp.TButton",
            command=lambda: self.choose_output_dir(self.folder_var, "Choose folder to analyze"),
        )
        browse_button.pack(side="left")
        self.add_hover_tooltip(
            [folder_label, folder_entry, browse_button],
            lambda: "Choose the folder tree to analyze for storage usage.",
        )

        action_row = ttk.Frame(controls_body, style="Card.TFrame")
        action_row.pack(fill="x", pady=(10, 0))
        top_n_label = ttk.Label(action_row, text="Top N", style="CardBody.TLabel")
        top_n_label.pack(side="left")
        top_n_spinbox = ttk.Spinbox(action_row, from_=5, to=200, textvariable=self.top_n_var, width=8)
        top_n_spinbox.pack(side="left", padx=(8, 12))
        compare_help_label = ttk.Label(
            action_row,
            text="Compare direct children, largest files, and largest folders using the tabs below.",
            style="CardMuted.TLabel",
        )
        compare_help_label.pack(side="left")
        self.inline_help_labels.append(compare_help_label)
        self.cancel_button = ttk.Button(action_row, text="Cancel", style="QuietApp.TButton", command=self.cancel_analysis, state="disabled")
        self.cancel_button.pack(side="right")
        self.analyze_button = ttk.Button(action_row, text="Analyze", style="PrimaryApp.TButton", command=self.analyze)
        self.analyze_button.pack(side="right", padx=(0, 8))
        self.add_hover_tooltip(
            [top_n_label, top_n_spinbox],
            lambda: (
                "Number of items to surface into each chart and table view.\n"
                f"Current Top N: {self.top_n_var.get()}."
            ),
        )
        self.add_hover_tooltip(
            compare_help_label,
            lambda: "Switch the tabs below to compare top-level items, largest files, and largest folders.",
        )
        self.add_hover_tooltip(
            self.analyze_button,
            lambda: "Start a storage scan and build pie-chart and table views for the selected folder.",
        )
        self.add_hover_tooltip(
            self.cancel_button,
            lambda: "Request cancellation of the current storage analysis.",
        )

        progress_box = ttk.LabelFrame(outer, text="Scan Progress", style="Card.TLabelframe")
        progress_box.pack(fill="x", pady=(10, 0))
        progress_body = ttk.Frame(progress_box, style="Card.TFrame")
        progress_body.pack(fill="x", padx=12, pady=12)
        self.progress = ttk.Progressbar(progress_body, mode="determinate", maximum=100, value=0)
        self.progress.pack(side="left", fill="x", expand=True)
        ttk.Label(progress_body, textvariable=self.progress_percent_var, style="CardBody.TLabel", width=6, anchor="e").pack(side="left", padx=(8, 0))
        self.add_hover_tooltip(
            self.progress,
            lambda: "Progress through indexing and size aggregation for the current storage scan.",
        )

        views_shell = ttk.Frame(outer, style="Surface.TFrame", padding=(0, 10, 0, 0))
        views_shell.pack(fill="both", expand=True)
        self.view_notebook = ttk.Notebook(views_shell, style="App.TNotebook")
        self.view_notebook.pack(fill="both", expand=True)
        self.view_notebook.enable_traversal()
        self._build_view_tab("top_level", "Top-Level")
        self._build_view_tab("largest_files", "Largest Files")
        self._build_view_tab("largest_folders", "Largest Folders")

        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(8, 0))
        self.refresh_hover_tooltip_preference()

    def _build_view_tab(self, view_key: str, title: str) -> None:
        assert self.view_notebook is not None
        frame = ttk.Frame(self.view_notebook, style="Surface.TFrame", padding=10)
        self.view_notebook.add(frame, text=title)

        split = ttk.Panedwindow(frame, orient="horizontal")
        split.pack(fill="both", expand=True)

        graph_box = ttk.Labelframe(split, text=f"{title} Chart", style="Card.TLabelframe")
        table_box = ttk.Labelframe(split, text=f"{title} Table", style="Card.TLabelframe")
        split.add(graph_box, weight=3)
        split.add(table_box, weight=4)

        graph_body = ttk.Frame(graph_box, style="Card.TFrame")
        graph_body.pack(fill="both", expand=True, padx=10, pady=10)
        canvas = tk.Canvas(graph_body, height=420, highlightthickness=1, cursor="hand2")
        canvas.pack(fill="both", expand=True)
        canvas.bind("<Configure>", lambda _event, view=view_key: self._schedule_chart_render(view))
        self.graph_canvases[view_key] = canvas
        self.add_hover_tooltip(
            canvas,
            lambda view=view_key: (
                f"{self.view_descriptions[view]}\n\n"
                "Click a slice to select the matching row. Double-click a slice to open that file or folder."
            ),
        )

        hint_var = StringVar(value=self.view_descriptions[view_key])
        self.graph_hint_vars[view_key] = hint_var
        ttk.Label(graph_body, textvariable=hint_var, style="CardMuted.TLabel", wraplength=520, justify="left").pack(anchor="w", pady=(10, 0))

        table_body = ttk.Frame(table_box, style="Card.TFrame")
        table_body.pack(fill="both", expand=True, padx=10, pady=10)
        tree_frame = ttk.Frame(table_body, style="Card.TFrame")
        tree_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(tree_frame, columns=("size", "share", "path"), show="headings")
        tree.heading("size", text="Size")
        tree.heading("share", text="Share")
        tree.heading("path", text="Path")
        tree.column("size", width=120, anchor="e")
        tree.column("share", width=90, anchor="e")
        tree.column("path", width=720, anchor="w")
        tree.pack(side="left", fill="both", expand=True)
        tree.bind("<Double-1>", lambda _event, view=view_key: self._open_selected_storage_item(view))
        self.tree_views[view_key] = tree
        self.add_hover_tooltip(
            tree,
            lambda view=view_key: (
                f"{self.view_descriptions[view]}\n\n"
                "Double-click a row to open the selected file or folder."
            ),
        )

        y_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        y_scroll.pack(side="right", fill="y")
        x_scroll = ttk.Scrollbar(table_body, orient="horizontal", command=tree.xview)
        x_scroll.pack(fill="x", pady=(8, 0))
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

    def refresh_hover_tooltip_preference(self) -> None:
        super().refresh_hover_tooltip_preference()
        self.apply_inline_help_visibility(self.inline_help_labels)

    def _set_scan_running(self, running: bool) -> None:
        if self.analyze_button is not None:
            self.analyze_button.configure(state="disabled" if running else "normal")
        if self.cancel_button is not None:
            self.cancel_button.configure(state="normal" if running else "disabled")

    def _check_cancel_scan(self) -> None:
        if self.cancel_scan_event.is_set():
            raise OperationCanceledError("Storage analysis canceled by user.")

    def cancel_analysis(self) -> None:
        if self.worker and self.worker.is_alive():
            self.cancel_scan_event.set()
            self.status_var.set("Cancel requested... stopping current storage analysis.")
            self.log("Cancellation requested for storage analyzer.")

    def _set_progress_percent(self, percent: int) -> None:
        clamped = max(0, min(100, int(percent)))
        if self.progress is not None:
            self.progress.configure(mode="determinate", maximum=100, value=clamped)
        self.progress_percent_var.set(f"{clamped}%")

    def _make_storage_entry(self, path: Path, size: int, kind: str | None = None) -> StorageViewEntry:
        entry_kind = kind or ("folder" if path.is_dir() else "file")
        label = path.name or str(path)
        return StorageViewEntry(label=label, path=path, size=size, kind=entry_kind)

    @staticmethod
    def _percentage_text(size: int, total: int) -> str:
        if total <= 0:
            return "0.0%"
        return f"{(size / total) * 100:.1f}%"

    def _view_total_size(self, view_key: str) -> int:
        return sum(entry.size for entry in self.graph_entries.get(view_key, []) if entry.size > 0)

    def _share_text(self, size: int) -> str:
        return self._percentage_text(size, self.root_total_size)

    def _chart_share_text(self, view_key: str, size: int) -> str:
        return self._percentage_text(size, self._view_total_size(view_key))

    def _set_view_hint(self, view_key: str, entry: StorageViewEntry | None = None) -> None:
        if entry is None:
            self.graph_hint_vars[view_key].set(self.view_descriptions[view_key])
            return
        location = str(entry.path) if entry.path else entry.label
        extra = " Double-click to open." if entry.path else ""
        chart_share = self._chart_share_text(view_key, entry.size)
        root_share = self._share_text(entry.size)
        share_text = f"{chart_share} of chart"
        if chart_share != root_share:
            share_text = f"{share_text} - {root_share} of scanned data"
        self.graph_hint_vars[view_key].set(
            f"{entry.label} - {human_size(entry.size)} - {share_text} - {location}.{extra}"
        )

    def _schedule_chart_render(self, view_key: str) -> None:
        if view_key in self._render_after_ids:
            try:
                self.after_cancel(self._render_after_ids[view_key])
            except Exception:
                pass
        self._render_after_ids[view_key] = self.after(40, lambda view=view_key: self._render_pie_chart(view))

    def _entry_fill_color(self, entry: StorageViewEntry) -> str:
        key = str(entry.path) if entry.path else entry.label
        digest = hashlib.md5(key.encode("utf-8", errors="ignore")).digest()
        if entry.kind == "folder":
            base_hue = 0.58
        elif entry.kind == "file":
            base_hue = 0.08
        else:
            base_hue = 0.0
        hue = (base_hue + ((digest[0] / 255.0) - 0.5) * 0.10) % 1.0
        saturation = 0.42 + (digest[1] / 255.0) * 0.20
        value = 0.72 + (digest[2] / 255.0) * 0.18
        red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)
        return f"#{int(red * 255):02x}{int(green * 255):02x}{int(blue * 255):02x}"

    @staticmethod
    def _darken_color(color: str, factor: float = 0.74) -> str:
        red = int(color[1:3], 16)
        green = int(color[3:5], 16)
        blue = int(color[5:7], 16)
        return f"#{int(red * factor):02x}{int(green * factor):02x}{int(blue * factor):02x}"

    @staticmethod
    def _contrast_text_color(color: str) -> str:
        red = int(color[1:3], 16)
        green = int(color[3:5], 16)
        blue = int(color[5:7], 16)
        luminance = (0.299 * red) + (0.587 * green) + (0.114 * blue)
        return "#101722" if luminance > 165 else "#F7FAFF"

    @staticmethod
    def _truncate_label(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        if limit <= 3:
            return text[:limit]
        return text[: limit - 3] + "..."

    def _build_pie_label(self, view_key: str, entry: StorageViewEntry, angle_span: float) -> str:
        if angle_span < 10:
            return ""
        if angle_span < 20:
            return self._truncate_label(entry.label, 14)
        lines = [self._truncate_label(entry.label, 18)]
        if angle_span >= 26:
            lines.append(self._chart_share_text(view_key, entry.size))
        if angle_span >= 42:
            lines.append(human_size(entry.size))
        return "\n".join(lines)

    def _select_entry_in_view(self, view_key: str, entry: StorageViewEntry) -> None:
        self._set_view_hint(view_key, entry)
        if not entry.path:
            return
        tree = self.tree_views[view_key]
        row_map = self.tree_entries.get(view_key, {})
        for item_id, row_entry in row_map.items():
            if row_entry.path == entry.path:
                tree.selection_set(item_id)
                tree.focus(item_id)
                tree.see(item_id)
                return

    def _open_storage_entry(self, entry: StorageViewEntry) -> None:
        if not entry.path:
            return
        try:
            if entry.kind == "file":
                self.app._open_file_location(entry.path)
            else:
                self.app._open_path(entry.path)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Failed to open item:\n{exc}")

    def _open_selected_storage_item(self, view_key: str) -> None:
        tree = self.tree_views[view_key]
        selected = tree.selection()
        if not selected:
            return
        entry = self.tree_entries.get(view_key, {}).get(selected[0])
        if entry:
            self._open_storage_entry(entry)

    def _populate_view(
        self, view_key: str, table_entries: list[StorageViewEntry], graph_entries: list[StorageViewEntry]
    ) -> None:
        tree = self.tree_views[view_key]
        for row in tree.get_children():
            tree.delete(row)
        row_lookup: dict[str, StorageViewEntry] = {}
        for entry in table_entries:
            item_id = tree.insert(
                "",
                "end",
                values=(human_size(entry.size), self._share_text(entry.size), str(entry.path) if entry.path else entry.label),
            )
            row_lookup[item_id] = entry
        self.tree_entries[view_key] = row_lookup
        self.graph_entries[view_key] = [entry for entry in graph_entries if entry.size > 0]
        self._set_view_hint(view_key, None)
        self._schedule_chart_render(view_key)

    def _render_pie_chart(self, view_key: str) -> None:
        canvas = self.graph_canvases[view_key]
        palette = self.app._theme_palette(bool(self.app.dark_mode_var.get()))
        canvas.configure(bg=palette["log_bg"], highlightbackground=palette["card_border"], highlightcolor=palette["card_border"])
        canvas.delete("all")
        entries = self.graph_entries.get(view_key, [])
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        if width < 40 or height < 40:
            return
        if not entries:
            canvas.create_text(
                width / 2,
                height / 2,
                text="Run an analysis to draw the pie chart.",
                fill=palette["subtitle_fg"],
                font=self.app._font(11),
            )
            return

        chart_total = sum(entry.size for entry in entries if entry.size > 0)
        if chart_total <= 0:
            canvas.create_text(
                width / 2,
                height / 2,
                text="Nothing to chart in this view.",
                fill=palette["subtitle_fg"],
                font=self.app._font(11),
            )
            return

        diameter = max(80, min(width - 24, height - 24))
        radius = diameter / 2
        center_x = width / 2
        center_y = height / 2
        x1 = center_x - radius
        y1 = center_y - radius
        x2 = center_x + radius
        y2 = center_y + radius

        accumulated = 0.0
        for index, entry in enumerate(entries):
            start_angle = 90.0 - accumulated
            if index == len(entries) - 1:
                extent = max(0.0, 360.0 - accumulated)
            else:
                extent = (entry.size / chart_total) * 360.0
            accumulated += extent
            fill_color = self._entry_fill_color(entry)
            border_color = self._darken_color(fill_color)
            text_color = self._contrast_text_color(fill_color)
            tag = f"{view_key}_node_{index}"
            arc_tag = f"{tag}_arc"
            canvas.create_arc(
                x1,
                y1,
                x2,
                y2,
                start=start_angle,
                extent=-extent,
                fill=fill_color,
                outline=border_color,
                width=2,
                style=tk.PIESLICE,
                tags=(tag, arc_tag),
            )
            label = self._build_pie_label(view_key, entry, extent)
            if label:
                mid_angle = math.radians(start_angle - (extent / 2.0))
                label_radius = radius * (0.55 if extent >= 30 else 0.68)
                label_x = center_x + math.cos(mid_angle) * label_radius
                label_y = center_y - math.sin(mid_angle) * label_radius
                font_name = self.app._font(9, semibold=True) if extent >= 26 else self.app._font(8)
                canvas.create_text(
                    label_x,
                    label_y,
                    anchor="center",
                    text=label,
                    fill=text_color,
                    width=max(70, radius * 0.55),
                    font=font_name,
                    tags=(tag,),
                )
            canvas.tag_bind(
                tag,
                "<Enter>",
                lambda _event, view=view_key, item=entry, node=arc_tag: (
                    canvas.itemconfigure(node, width=3),
                    self._set_view_hint(view, item),
                ),
            )
            canvas.tag_bind(
                tag,
                "<Leave>",
                lambda _event, view=view_key, node=arc_tag: (
                    canvas.itemconfigure(node, width=2),
                    self._set_view_hint(view, None),
                ),
            )
            canvas.tag_bind(tag, "<Button-1>", lambda _event, view=view_key, item=entry: self._select_entry_in_view(view, item))
            canvas.tag_bind(tag, "<Double-Button-1>", lambda _event, item=entry: self._open_storage_entry(item))

    def analyze(self) -> None:
        root = Path(self.folder_var.get().strip())
        if not root.exists() or not root.is_dir():
            messagebox.showerror(APP_TITLE, "Analysis folder does not exist.")
            return
        try:
            top_n = max(5, min(200, int(self.top_n_var.get())))
        except Exception:
            messagebox.showerror(APP_TITLE, "Top N must be a whole number between 5 and 200.")
            return
        self.top_n_var.set(top_n)
        self.cancel_scan_event.clear()
        self._set_scan_running(True)

        def work() -> None:
            try:
                self.app.call_ui(
                    lambda: (
                        self._set_progress_percent(0),
                        self.status_var.set("Indexing files..."),
                    )
                )
                discovered_files: list[Path] = []
                scanned_directories = 0
                for current_root, _, files in os.walk(root):
                    self._check_cancel_scan()
                    scanned_directories += 1
                    root_path = Path(current_root)
                    for name in files:
                        discovered_files.append(root_path / name)
                    if scanned_directories % 50 == 0:
                        self.app.call_ui(
                            lambda found=len(discovered_files): self.status_var.set(f"Indexing files... {found} found")
                        )

                total_files = len(discovered_files)
                self.app.call_ui(
                    lambda total=total_files: (
                        self._set_progress_percent(0 if total > 0 else 100),
                        self.status_var.set(
                            "No files found. Preparing empty views." if total == 0 else f"Analyzing file sizes... 0/{total}"
                        ),
                    )
                )

                file_sizes: list[tuple[Path, int]] = []
                folder_sizes: dict[Path, int] = {}
                top_level_sizes: dict[Path, int] = {}
                scanned_files = 0
                skipped_errors = 0

                for index, path in enumerate(discovered_files, start=1):
                    self._check_cancel_scan()
                    try:
                        size = path.stat().st_size
                    except Exception:
                        skipped_errors += 1
                        continue
                    scanned_files += 1
                    file_sizes.append((path, size))

                    try:
                        relative_parts = path.relative_to(root).parts
                        if relative_parts:
                            top_level_path = root / relative_parts[0]
                            top_level_sizes[top_level_path] = top_level_sizes.get(top_level_path, 0) + size
                    except ValueError:
                        pass

                    cursor = path.parent
                    while True:
                        folder_sizes[cursor] = folder_sizes.get(cursor, 0) + size
                        if cursor == root:
                            break
                        if root not in cursor.parents and cursor != root:
                            break
                        cursor = cursor.parent

                    if index % 200 == 0 or index == total_files:
                        percent = int((index / max(1, total_files)) * 100)
                        self.app.call_ui(
                            lambda done=index, total=total_files, pct=percent: (
                                self._set_progress_percent(pct),
                                self.status_var.set(f"Analyzing file sizes... {done}/{total}"),
                            )
                        )

                root_total = folder_sizes.get(root, sum(size for _, size in file_sizes))
                largest_file_rows = sorted(file_sizes, key=lambda row: row[1], reverse=True)
                largest_folder_rows = sorted(
                    [(folder_path, size) for folder_path, size in folder_sizes.items() if folder_path != root and size > 0],
                    key=lambda row: row[1],
                    reverse=True,
                )
                top_level_rows = sorted(top_level_sizes.items(), key=lambda row: row[1], reverse=True)

                top_level_table_entries = [self._make_storage_entry(path, size) for path, size in top_level_rows[:top_n]]
                top_level_graph_entries = list(top_level_table_entries)
                if len(top_level_rows) > top_n:
                    remaining_size = sum(size for _, size in top_level_rows[top_n:])
                    if remaining_size > 0:
                        top_level_graph_entries.append(
                            StorageViewEntry(
                                label=f"Other ({len(top_level_rows) - top_n} more)",
                                path=None,
                                size=remaining_size,
                                kind="other",
                            )
                        )

                largest_file_table_entries = [
                    StorageViewEntry(label=path.name or str(path), path=path, size=size, kind="file")
                    for path, size in largest_file_rows[:top_n]
                ]
                largest_file_graph_entries = list(largest_file_table_entries)
                remaining_file_size = max(0, root_total - sum(entry.size for entry in largest_file_table_entries))
                if remaining_file_size > 0:
                    largest_file_graph_entries.append(
                        StorageViewEntry(
                            label=f"Other ({max(0, len(largest_file_rows) - top_n)} more)",
                            path=None,
                            size=remaining_file_size,
                            kind="other",
                        )
                    )

                largest_folder_table_entries = [self._make_storage_entry(path, size, kind="folder") for path, size in largest_folder_rows[:top_n]]
                largest_folder_graph_entries = list(largest_folder_table_entries)

                def render() -> None:
                    self.root_total_size = root_total
                    self._populate_view("top_level", top_level_table_entries, top_level_graph_entries)
                    self._populate_view("largest_files", largest_file_table_entries, largest_file_graph_entries)
                    self._populate_view("largest_folders", largest_folder_table_entries, largest_folder_graph_entries)
                    self._set_progress_percent(100 if total_files > 0 else 0)
                    if scanned_files == 0:
                        self.status_var.set("No files were found in the selected folder.")
                    else:
                        self.status_var.set(
                            f"Scanned {scanned_files} files totaling {human_size(root_total)}. "
                            f"Showing top {top_n} entries per view. Skipped {skipped_errors} unreadable file(s)."
                        )

                self.app.call_ui(render)
            except OperationCanceledError:
                self.app.call_ui(
                    lambda: (
                        self._set_progress_percent(0),
                        self.status_var.set("Storage analysis canceled."),
                    )
                )
                raise
            finally:
                self.app.call_ui(lambda: self._set_scan_running(False))

        self.run_async(work, done_message="Storage analysis complete.")

    def handle_external_drop(self, paths: list[Path]) -> bool:
        for path in self._dedupe_paths(paths):
            target = path if path.is_dir() else path.parent
            if target.exists():
                self.folder_var.set(str(target))
                self._set_drop_feedback(f"Storage analysis folder set to {target}.")
                return True
        self._set_drop_feedback("Drop a folder or a file whose parent folder should be analyzed.")
        return False


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

    def handle_external_drop(self, paths: list[Path]) -> bool:
        return self._add_dropped_file_paths(self.files, self.listbox, paths, expand_directories=True)


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

    def handle_external_drop(self, paths: list[Path]) -> bool:
        return self._add_dropped_file_paths(self.files, self.listbox, paths, expand_directories=True)


class Aria2DownloadsTab(ModuleTab):
    tab_name = "Downloads"

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.sources: list[str] = []
        self.uri_var = StringVar(value="")
        self.output_dir = StringVar(value=str(self.app.default_output_root / "aria2" / "downloads"))
        self.status_var = StringVar(value="Ready.")
        self.progress_var = IntVar(value=0)
        self.progress_text_var = StringVar(value="0%")
        self.download_process: subprocess.Popen[str] | None = None
        self.download_cancel_requested = threading.Event()
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text=(
                "aria2 handles HTTP(S), FTP, SFTP, BitTorrent, magnet, and Metalink downloads. "
                "This tab uses the detected aria2c backend directly and does not apply any download speed limit flags."
            ),
            wraplength=1200,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        warning_box = ttk.LabelFrame(outer, text="Warning / Disclaimer")
        warning_box.pack(fill="x", pady=(0, 8))
        ttk.Label(
            warning_box,
            text=(
                "aria2 comes with no warranty. Use this workflow at your own risk. Universal Conversion Hub does not "
                "accept responsibility for damage, data loss, malware, or other issues caused by downloaded content, "
                "metadata files, trackers, or remote servers. Only download files, torrents, magnet links, or Metalink "
                "sources when you trust the source and all related data."
            ),
            wraplength=1200,
            justify="left",
        ).pack(anchor="w", padx=10, pady=8)

        queue_box = ttk.LabelFrame(outer, text="aria2 Download Queue")
        queue_box.pack(fill="both", expand=True, pady=(0, 8))

        controls = ttk.Frame(queue_box)
        controls.pack(fill="x", padx=10, pady=(10, 6))
        ttk.Button(controls, text="Add URI", command=self.add_uri).pack(side="left")
        ttk.Button(controls, text="Add Metadata Files", command=self.add_metadata_files).pack(side="left", padx=(6, 0))
        ttk.Button(controls, text="Import URL List", command=self.import_url_list).pack(side="left", padx=(6, 0))
        ttk.Button(controls, text="Remove Selected", command=self.remove_selected_sources).pack(side="left", padx=(6, 0))
        ttk.Button(controls, text="Clear", command=self.clear_sources).pack(side="left", padx=(6, 0))

        uri_row = ttk.Frame(queue_box)
        uri_row.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Label(uri_row, text="URI / Magnet").pack(side="left")
        ttk.Entry(uri_row, textvariable=self.uri_var).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(uri_row, text="Add", command=self.add_uri).pack(side="left")

        queue = ttk.Frame(queue_box)
        queue.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.listbox = tk.Listbox(queue, selectmode=SINGLE)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(queue, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scroll.set)

        folder_row = ttk.Frame(queue_box)
        folder_row.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(folder_row, text="Download folder").pack(side="left")
        ttk.Entry(folder_row, textvariable=self.output_dir).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(folder_row, text="Browse", command=lambda: self.choose_output_dir(self.output_dir, "Choose aria2 download folder")).pack(side="left")
        ttk.Button(folder_row, text="Open", command=lambda: self.app._open_path(Path(self.output_dir.get().strip() or str(self.app.default_output_root)))).pack(
            side="left",
            padx=(6, 0),
        )
        ttk.Button(folder_row, text="Start Download", command=self.start_download).pack(side="right")
        ttk.Button(folder_row, text="Cancel", command=self.cancel_download).pack(side="right", padx=(0, 6))

        info_box = ttk.LabelFrame(outer, text="Supported Inputs")
        info_box.pack(fill="x", pady=(0, 8))
        ttk.Label(
            info_box,
            text=(
                "Use direct URIs for HTTP(S), FTP, and SFTP, or add .torrent / .meta4 / .metalink files. "
                "Import URL List accepts a text file with one URI per line."
            ),
            wraplength=1200,
            justify="left",
        ).pack(anchor="w", padx=10, pady=8)

        progress_row = ttk.Frame(outer)
        progress_row.pack(fill="x", pady=(0, 4))
        ttk.Progressbar(progress_row, variable=self.progress_var, maximum=100).pack(side="left", fill="x", expand=True)
        ttk.Label(progress_row, textvariable=self.progress_text_var).pack(side="left", padx=(8, 0))

        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w")

    def _add_source(self, value: str) -> bool:
        text = str(value).strip()
        if not text or text in self.sources:
            return False
        self.sources.append(text)
        self.listbox.insert(END, text)
        return True

    def add_uri(self) -> None:
        value = self.uri_var.get().strip()
        if not value:
            messagebox.showwarning(APP_TITLE, "Enter a URI or magnet link first.")
            return
        if not is_aria2_download_uri(value):
            messagebox.showwarning(APP_TITLE, "Only HTTP(S), FTP, SFTP, and magnet URIs are accepted here.")
            return
        if self._add_source(value):
            self.uri_var.set("")

    def add_metadata_files(self) -> None:
        chosen = filedialog.askopenfilenames(
            title="Select aria2 metadata files",
            filetypes=[
                ("aria2 metadata", "*.torrent *.meta4 *.metalink"),
                ("Torrent files", "*.torrent"),
                ("Metalink files", "*.meta4 *.metalink"),
                ("All files", "*.*"),
            ],
        )
        for raw in chosen:
            path = Path(raw)
            if path.exists() and is_aria2_metadata_source_path(path):
                self._add_source(str(path))

    def import_url_list(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Import URL list",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not chosen:
            return
        path = Path(chosen)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except Exception as exc:
            self.app.error(f"Could not read URL list:\n{exc}")
            return
        added = 0
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if is_aria2_download_uri(line):
                added += int(self._add_source(line))
        if added:
            self.status_var.set(f"Imported {added} URI(s) from {path.name}.")
        else:
            self.status_var.set(f"No supported URIs were found in {path.name}.")

    def remove_selected_sources(self) -> None:
        selected = list(self.listbox.curselection())
        selected.reverse()
        for index in selected:
            self.listbox.delete(index)
            self.sources.pop(index)

    def clear_sources(self) -> None:
        self.sources.clear()
        self.listbox.delete(0, END)

    def _set_progress(self, percent: int, status: str) -> None:
        bounded = max(0, min(100, percent))
        self.progress_var.set(bounded)
        self.progress_text_var.set(f"{bounded}%")
        self.status_var.set(status)

    def start_download(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(APP_TITLE, "An aria2 download is already running.")
            return
        if not self.sources:
            messagebox.showwarning(APP_TITLE, "Add at least one URI, magnet link, torrent, or Metalink source first.")
            return
        aria2 = self.app.backends.aria2
        if not aria2:
            messagebox.showwarning(
                APP_TITLE,
                "Aria2 was not detected. Install or connect the Aria2 backend before using this tab.",
            )
            return
        destination = Path(self.output_dir.get().strip() or str(self.app.default_output_root / "aria2" / "downloads"))
        ensure_dir(destination)
        sources = list(self.sources)
        self.download_cancel_requested.clear()
        self._set_progress(0, "Starting aria2 download...")

        def work() -> None:
            cmd = [
                aria2,
                "--dir",
                str(destination),
                "--summary-interval=1",
                "--console-log-level=notice",
                "--check-integrity=true",
                "--continue=true",
                "--auto-file-renaming=true",
                "--follow-torrent=true",
                "--follow-metalink=true",
                "--bt-save-metadata=true",
                "--seed-time=0",
                *sources,
            ]
            self.log(f"Running aria2 command: {quote_cmd(cmd)}")
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                **hidden_console_process_kwargs(),
            )
            self.download_process = proc
            last_detail = ""
            try:
                assert proc.stdout is not None
                for raw_line in proc.stdout:
                    line = raw_line.strip()
                    if not line:
                        continue
                    last_detail = line
                    self.log(line)
                    match = ARIA2_PROGRESS_RE.search(line)
                    if match:
                        percent = int(match.group(1))
                        self.app.call_ui(lambda p=percent, s=line: self._set_progress(p, s))
                    elif any(keyword in line.lower() for keyword in ("download complete", "complete:", "seeding")):
                        self.app.call_ui(lambda s=line: self.status_var.set(s))
                code = proc.wait()
            finally:
                self.download_process = None
            if self.download_cancel_requested.is_set():
                raise OperationCanceledError("Aria2 download canceled.")
            if code != 0:
                raise RuntimeError(last_detail or f"aria2 exited with code {code}")
            self.app.call_ui(lambda: self._set_progress(100, f"Downloaded {len(sources)} aria2 source(s)."))

        self.worker = threading.Thread(target=lambda: self._run_download_worker(work), daemon=True)
        self.worker.start()

    def _run_download_worker(self, action) -> None:
        try:
            action()
            self.app.info("Aria2 download finished.")
        except OperationCanceledError as exc:
            self.log(str(exc))
            self.app.call_ui(lambda: self.status_var.set(str(exc)))
        except Exception as exc:
            self.log(f"Error: {exc}")
            self.app.error(f"Aria2 download failed:\n{exc}")

    def cancel_download(self) -> None:
        self.download_cancel_requested.set()
        process = self.download_process
        if process and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass
            self.status_var.set("Canceling aria2 download...")
        else:
            self.status_var.set("No aria2 download is currently running.")

    def handle_external_drop(self, paths: list[Path]) -> bool:
        handled = False
        for path in paths:
            if path.is_dir():
                for pattern in ("*.torrent", "*.meta4", "*.metalink"):
                    for child in path.rglob(pattern):
                        handled = self._add_source(str(child)) or handled
                continue
            if is_aria2_metadata_source_path(path):
                handled = self._add_source(str(path)) or handled
        return handled


class TorrentsTab(ModuleTab):
    tab_name = "Torrents"

    def __init__(self, master, app: SuiteApp):
        super().__init__(master, app)
        self.download_items: list[str] = []
        self.magnet_var = StringVar(value="")
        self.download_dir = StringVar(value=str(self.app.default_output_root / "torrents" / "downloads"))
        self.create_source = StringVar(value="")
        self.torrent_output = StringVar(value=str(self.app.default_output_root / "torrents" / "new_download.torrent"))
        self.comment_var = StringVar(value="")
        self.private_var = BooleanVar(value=False)
        self.status_var = StringVar(value="Ready.")
        self.progress_var = IntVar(value=0)
        self.progress_text_var = StringVar(value="0%")
        self.download_process: subprocess.Popen[str] | None = None
        self.download_cancel_requested = threading.Event()
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)
        ttk.Label(
            outer,
            text=(
                "Create .torrent files directly in-app. Torrent download/extraction uses the optional Aria2 backend. "
                "This workflow does not apply any download speed limit flags."
            ),
            wraplength=1200,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        warning_box = ttk.LabelFrame(outer, text="Warning / Disclaimer")
        warning_box.pack(fill="x", pady=(0, 8))
        ttk.Label(
            warning_box,
            text=(
                "Use torrent features at your own risk. Universal Conversion Hub does not accept responsibility for "
                "damage, data loss, malware, or other issues caused by torrent files, magnet links, trackers, or any "
                "downloaded content. Do not download data from websites or torrent sources unless you fully trust all "
                "files, metadata, and peers involved."
            ),
            wraplength=1200,
            justify="left",
        ).pack(anchor="w", padx=10, pady=8)

        download_box = ttk.LabelFrame(outer, text="Download / Extract Torrent Contents")
        download_box.pack(fill="both", expand=True, pady=(0, 8))

        download_controls = ttk.Frame(download_box)
        download_controls.pack(fill="x", padx=10, pady=(10, 6))
        ttk.Button(download_controls, text="Add Torrent Files", command=self.add_torrent_files).pack(side="left")
        ttk.Button(download_controls, text="Remove Selected", command=self.remove_selected_sources).pack(side="left", padx=(6, 0))
        ttk.Button(download_controls, text="Clear", command=self.clear_sources).pack(side="left", padx=(6, 0))
        ttk.Label(download_controls, text="Magnet").pack(side="left", padx=(18, 6))
        ttk.Entry(download_controls, textvariable=self.magnet_var).pack(side="left", fill="x", expand=True)
        ttk.Button(download_controls, text="Add Magnet", command=self.add_magnet_link).pack(side="left", padx=(6, 0))

        queue = ttk.Frame(download_box)
        queue.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.listbox = tk.Listbox(queue, selectmode=SINGLE)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(queue, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scroll.set)

        folder_row = ttk.Frame(download_box)
        folder_row.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(folder_row, text="Download folder").pack(side="left")
        ttk.Entry(folder_row, textvariable=self.download_dir).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(folder_row, text="Browse", command=lambda: self.choose_output_dir(self.download_dir, "Choose torrent download folder")).pack(side="left")
        ttk.Button(folder_row, text="Open", command=lambda: self.app._open_path(Path(self.download_dir.get().strip() or str(self.app.default_output_root)))).pack(
            side="left",
            padx=(6, 0),
        )
        ttk.Button(folder_row, text="Start Download", command=self.start_download).pack(side="right")
        ttk.Button(folder_row, text="Cancel", command=self.cancel_download).pack(side="right", padx=(0, 6))

        progress_row = ttk.Frame(download_box)
        progress_row.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Progressbar(progress_row, variable=self.progress_var, maximum=100).pack(side="left", fill="x", expand=True)
        ttk.Label(progress_row, textvariable=self.progress_text_var).pack(side="left", padx=(8, 0))

        create_box = ttk.LabelFrame(outer, text="Create Torrent File")
        create_box.pack(fill="x")

        source_row = ttk.Frame(create_box)
        source_row.pack(fill="x", padx=10, pady=(10, 6))
        ttk.Label(source_row, text="Source").pack(side="left")
        ttk.Entry(source_row, textvariable=self.create_source).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(source_row, text="File", command=self.pick_create_source_file).pack(side="left")
        ttk.Button(source_row, text="Folder", command=self.pick_create_source_folder).pack(side="left", padx=(6, 0))

        output_row = ttk.Frame(create_box)
        output_row.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Label(output_row, text="Torrent file").pack(side="left")
        ttk.Entry(output_row, textvariable=self.torrent_output).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(output_row, text="Save As", command=self.pick_torrent_output).pack(side="left")

        comment_row = ttk.Frame(create_box)
        comment_row.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Label(comment_row, text="Comment").pack(side="left")
        ttk.Entry(comment_row, textvariable=self.comment_var).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Checkbutton(comment_row, text="Private torrent", variable=self.private_var).pack(side="left")

        ttk.Label(create_box, text="Trackers (one per line)").pack(anchor="w", padx=10)
        self.trackers_box = ScrolledText(create_box, height=5, wrap="word")
        self.trackers_box.pack(fill="x", padx=10, pady=(4, 8))
        self.trackers_box.insert("1.0", "https://tracker.opentrackr.org:1337/announce")

        create_actions = ttk.Frame(create_box)
        create_actions.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(create_actions, text="Create Torrent", command=self.create_torrent).pack(side="right")

        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(8, 0))

    def _add_download_source(self, value: str) -> bool:
        text = str(value).strip()
        if not text:
            return False
        if text in self.download_items:
            return False
        self.download_items.append(text)
        self.listbox.insert(END, text)
        return True

    def add_torrent_files(self) -> None:
        chosen = filedialog.askopenfilenames(title="Select torrent files", filetypes=[("Torrent files", "*.torrent"), ("All files", "*.*")])
        for raw in chosen:
            path = Path(raw)
            if path.exists() and is_torrent_source_path(path):
                self._add_download_source(str(path))

    def add_magnet_link(self) -> None:
        magnet = self.magnet_var.get().strip()
        if not magnet:
            messagebox.showwarning(APP_TITLE, "Enter a magnet link first.")
            return
        if not is_magnet_uri(magnet):
            messagebox.showwarning(APP_TITLE, "Magnet links must start with magnet:?.")
            return
        if self._add_download_source(magnet):
            self.magnet_var.set("")

    def remove_selected_sources(self) -> None:
        selected = list(self.listbox.curselection())
        selected.reverse()
        for index in selected:
            self.listbox.delete(index)
            self.download_items.pop(index)

    def clear_sources(self) -> None:
        self.download_items.clear()
        self.listbox.delete(0, END)

    def pick_create_source_file(self) -> None:
        chosen = filedialog.askopenfilename(title="Select file to package into a torrent")
        if chosen:
            path = Path(chosen)
            self.create_source.set(str(path))
            self.torrent_output.set(str(path.with_suffix(".torrent")))

    def pick_create_source_folder(self) -> None:
        chosen = filedialog.askdirectory(title="Select folder to package into a torrent")
        if chosen:
            path = Path(chosen)
            self.create_source.set(str(path))
            self.torrent_output.set(str(path.parent / f"{path.name}.torrent"))

    def pick_torrent_output(self) -> None:
        chosen = filedialog.asksaveasfilename(
            title="Save torrent as",
            defaultextension=".torrent",
            filetypes=[("Torrent files", "*.torrent"), ("All files", "*.*")],
        )
        if chosen:
            self.torrent_output.set(chosen)

    def _tracker_list(self) -> list[str]:
        raw = self.trackers_box.get("1.0", "end").strip()
        trackers: list[str] = []
        for line in raw.splitlines():
            for part in line.split(","):
                item = part.strip()
                if item:
                    trackers.append(item)
        return trackers

    def create_torrent(self) -> None:
        if Torrent is None:
            messagebox.showerror(APP_TITLE, "The torrentool Python dependency is not installed.")
            return
        source = Path(self.create_source.get().strip())
        if not source.exists():
            messagebox.showwarning(APP_TITLE, "Choose a file or folder to package into a torrent.")
            return
        output_path = Path(self.torrent_output.get().strip() or str(source.with_suffix(".torrent")))
        if output_path.suffix.lower() != ".torrent":
            output_path = output_path.with_suffix(".torrent")
        trackers = self._tracker_list()
        comment = self.comment_var.get().strip()
        private = bool(self.private_var.get())

        def work() -> None:
            resolved = self.app.resolve_output_path(output_path, context=f"Torrent file for {source.name}")
            if resolved is None:
                raise RuntimeError("Operation canceled by user.")
            ensure_dir(resolved.parent)
            torrent = Torrent.create_from(source)
            if trackers:
                torrent.announce_urls = [[tracker] for tracker in trackers]
            if comment:
                torrent.comment = comment
            torrent.private = private
            torrent.to_file(str(resolved))
            self.log(f"Created torrent: {resolved}")
            self.app.call_ui(lambda: self.status_var.set(f"Created torrent: {resolved.name}"))

        self.run_async(work, done_message=f"Torrent created: {output_path}")

    def _set_download_progress(self, percent: int, status: str) -> None:
        self.progress_var.set(max(0, min(100, percent)))
        self.progress_text_var.set(f"{max(0, min(100, percent))}%")
        self.status_var.set(status)

    def start_download(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(APP_TITLE, "Torrent download is already running.")
            return
        if not self.download_items:
            messagebox.showwarning(APP_TITLE, "Add at least one torrent file or magnet link first.")
            return
        aria2 = self.app.backends.aria2
        if not aria2:
            messagebox.showwarning(
                APP_TITLE,
                "Aria2 was not detected. Install the Aria2 backend to download and extract torrent contents.",
            )
            return
        destination = Path(self.download_dir.get().strip())
        ensure_dir(destination)
        sources = list(self.download_items)
        self.download_cancel_requested.clear()
        self._set_download_progress(0, "Starting torrent download...")

        def work() -> None:
            cmd = [
                aria2,
                "--dir",
                str(destination),
                "--summary-interval=1",
                "--console-log-level=notice",
                "--seed-time=0",
                "--bt-save-metadata=true",
                "--follow-torrent=true",
                "--enable-dht=true",
                "--enable-peer-exchange=true",
                "--check-integrity=true",
            ]
            cmd.extend(sources)
            self.log(f"$ {quote_cmd(cmd)}")
            last_detail = "Starting torrent transfer..."
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                universal_newlines=True,
                encoding="utf-8",
                errors="replace",
                **hidden_console_process_kwargs(),
            )
            self.download_process = proc
            assert proc.stdout is not None
            for raw_line in proc.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                last_detail = line
                progress_match = ARIA2_PROGRESS_RE.search(line)
                if progress_match:
                    percent = int(progress_match.group(1))
                    self.app.call_ui(lambda p=percent, s=line: self._set_download_progress(p, s))
                elif any(keyword in line.lower() for keyword in ("download complete", "complete:", "seeding")):
                    self.app.call_ui(lambda s=line: self.status_var.set(s))
                if any(keyword in line.lower() for keyword in ("error", "warn", "fail")):
                    self.log(line)
            code = proc.wait()
            self.download_process = None
            if self.download_cancel_requested.is_set():
                raise OperationCanceledError("Torrent download canceled.")
            if code != 0:
                raise RuntimeError(last_detail or f"aria2 exited with code {code}")
            self.app.call_ui(lambda: self.clear_sources())
            self.app.call_ui(lambda: self._set_download_progress(100, f"Downloaded {len(sources)} torrent source(s)."))

        self.worker = threading.Thread(target=lambda: self._run_download_worker(work), daemon=True)
        self.worker.start()

    def _run_download_worker(self, action) -> None:
        try:
            action()
            self.app.info("Torrent download finished.")
        except OperationCanceledError as exc:
            self.log(str(exc))
            self.app.call_ui(lambda: self.status_var.set(str(exc)))
        except Exception as exc:
            self.log(f"Error: {exc}")
            self.app.error(f"{self.tab_name} failed:\n{exc}")

    def cancel_download(self) -> None:
        self.download_cancel_requested.set()
        process = self.download_process
        if process and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass
            self.status_var.set("Canceling torrent download...")
        else:
            self.status_var.set("No torrent download is currently running.")

    def handle_external_drop(self, paths: list[Path]) -> bool:
        handled = False
        for path in paths:
            if path.is_dir():
                if not self.create_source.get().strip():
                    self.create_source.set(str(path))
                    self.torrent_output.set(str(path.parent / f"{path.name}.torrent"))
                    handled = True
                for child in path.rglob("*.torrent"):
                    handled = self._add_download_source(str(child)) or handled
                continue
            if is_torrent_source_path(path):
                handled = self._add_download_source(str(path)) or handled
                continue
            if not self.create_source.get().strip():
                self.create_source.set(str(path))
                self.torrent_output.set(str(path.with_suffix(".torrent")))
                handled = True
        return handled


class PresetsBatchTab(ModuleTab):
    tab_name = "Presets / Batch Jobs"

    SUPPORTED_MODULES = ["Convert", "Compress", "Extract", "Images", "Audio", "Video"]

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
        ttk.Combobox(left, textvariable=self.module_var, values=self.SUPPORTED_MODULES, state="readonly").pack(fill="x", padx=10)
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
        self._add_job_paths([Path(raw) for raw in files])

    def _add_job_paths(self, paths: list[Path]) -> bool:
        preset_name = self.queue_preset_var.get().strip()
        if not preset_name or preset_name not in self.presets:
            messagebox.showwarning(APP_TITLE, "Select a valid preset before adding jobs.")
            return False
        output_dir = self.queue_output_var.get().strip()
        candidates = self._collect_drop_files(paths, expand_directories=True)
        if not candidates:
            self._set_drop_feedback("No valid files were found for the batch queue.")
            return False
        preset = self.presets[preset_name]
        existing = {(job["module"], job["preset"], job["input"], job["output"]) for job in self.jobs}
        added = 0
        duplicates = 0
        for path in candidates:
            module_name = str(preset.get("module", "Convert"))
            job_key = (module_name, preset_name, str(path), output_dir)
            if job_key in existing:
                duplicates += 1
                continue
            job = {
                "module": module_name,
                "preset": preset_name,
                "input": str(path),
                "output": output_dir,
            }
            self.jobs.append(job)
            self.job_tree.insert("", "end", values=(module_name, preset_name, str(path), output_dir))
            existing.add(job_key)
            added += 1
        if added:
            message = f"Queue now has {len(self.jobs)} job(s). Added {added} file(s)."
            if duplicates:
                message += f" Skipped {duplicates} duplicate job(s)."
            self.status_var.set(message)
        else:
            self.status_var.set("All dropped files were already present in the batch queue.")
        return True

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

    def handle_external_drop(self, paths: list[Path]) -> bool:
        return self._add_job_paths(paths)

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
                    elif module_name == "Images":
                        self.app.engine.process_image_file(source, output_dir, config)
                    elif module_name == "Audio":
                        self.app.engine.process_audio_file(source, output_dir, config)
                    elif module_name == "Video":
                        mode_key = str(config.get("mode_key", "stream_prep"))
                        self.app.engine.process_video_file(source, output_dir, mode_key, config)
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
    acquired, mutex_handle = _acquire_single_instance_mutex()
    if not acquired:
        _focus_existing_window()
        _show_startup_warning(f"{APP_TITLE} is already running.\n\nOnly one instance can be open at a time.")
        return
    root = tk.Tk()
    try:
        SuiteApp(root)
        root.mainloop()
    finally:
        _release_single_instance_mutex(mutex_handle)


if __name__ == "__main__":
    main()
