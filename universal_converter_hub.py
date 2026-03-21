import configparser
import csv
import json
import os
import queue
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time
import tomllib
import zipfile
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from tkinter import Tk, StringVar, BooleanVar, IntVar, END, SINGLE, filedialog, messagebox
import tkinter as tk
from tkinter import ttk
import xml.etree.ElementTree as ET

import imageio_ffmpeg
import py7zr
import tomli_w
import xmltodict
import yaml
from PIL import Image

APP_TITLE = "Universal File Converter Hub"


# ---------- Helpers ----------

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def lower_name(path: Path) -> str:
    return path.name.lower()


def strip_composite_suffix(path: Path) -> str:
    lower = lower_name(path)
    composite = [
        ".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2", ".txz",
        ".csv.gz", ".json.gz", ".xml.gz", ".yaml.gz", ".yml.gz",
    ]
    for suffix in composite:
        if lower.endswith(suffix):
            return path.name[: -len(suffix)]
    return path.stem


def composite_suffix(path: Path) -> str:
    lower = lower_name(path)
    composite = [
        ".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2", ".txz",
        ".csv.gz", ".json.gz", ".xml.gz", ".yaml.gz", ".yml.gz",
    ]
    for suffix in composite:
        if lower.endswith(suffix):
            return suffix
    return path.suffix.lower()


def seconds_from_hms(value: str) -> float:
    parts = value.strip().split(":")
    if len(parts) != 3:
        return 0.0
    h, m, s = parts
    return int(h) * 3600 + int(m) * 60 + float(s)


def flatten_for_table(data):
    if isinstance(data, list):
        if not data:
            return []
        if all(isinstance(item, dict) for item in data):
            return data
        return [{"value": item} for item in data]
    if isinstance(data, dict):
        if all(isinstance(v, (str, int, float, bool, type(None))) for v in data.values()):
            return [data]
        return [{"key": k, "value": json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v} for k, v in data.items()]
    return [{"value": data}]


def which_any(*names: str) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def quote_cmd(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


# ---------- Backend detection ----------

@dataclass
class BackendRegistry:
    ffmpeg: str | None
    imagemagick: str | None
    pandoc: str | None
    libreoffice: str | None
    inkscape: str | None
    calibre: str | None
    sevenzip: str | None

    @classmethod
    def detect(cls) -> "BackendRegistry":
        ffmpeg = None
        try:
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg = which_any("ffmpeg")

        libreoffice = which_any("soffice", "soffice.exe")
        if not libreoffice:
            common = [
                Path(os.environ.get("ProgramFiles", "")) / "LibreOffice" / "program" / "soffice.exe",
                Path(os.environ.get("ProgramFiles(x86)", "")) / "LibreOffice" / "program" / "soffice.exe",
            ]
            for candidate in common:
                if candidate.exists():
                    libreoffice = str(candidate)
                    break

        inkscape = which_any("inkscape", "inkscape.exe")
        if not inkscape:
            common = [
                Path(os.environ.get("ProgramFiles", "")) / "Inkscape" / "bin" / "inkscape.exe",
                Path(os.environ.get("ProgramFiles", "")) / "Inkscape" / "inkscape.exe",
            ]
            for candidate in common:
                if candidate.exists():
                    inkscape = str(candidate)
                    break

        calibre = which_any("ebook-convert", "ebook-convert.exe")
        if not calibre:
            common = [
                Path(os.environ.get("ProgramFiles", "")) / "Calibre2" / "ebook-convert.exe",
                Path(os.environ.get("ProgramFiles(x86)", "")) / "Calibre2" / "ebook-convert.exe",
            ]
            for candidate in common:
                if candidate.exists():
                    calibre = str(candidate)
                    break

        return cls(
            ffmpeg=ffmpeg,
            imagemagick=which_any("magick", "magick.exe"),
            pandoc=which_any("pandoc", "pandoc.exe"),
            libreoffice=libreoffice,
            inkscape=inkscape,
            calibre=calibre,
            sevenzip=which_any("7z", "7z.exe", "7za", "7za.exe"),
        )

    def status_rows(self) -> list[tuple[str, str]]:
        rows = [
            ("FFmpeg", self.ffmpeg or "Not found"),
            ("ImageMagick", self.imagemagick or "Not found"),
            ("Pandoc", self.pandoc or "Not found"),
            ("LibreOffice", self.libreoffice or "Not found"),
            ("Inkscape", self.inkscape or "Not found"),
            ("Calibre", self.calibre or "Not found"),
            ("7-Zip", self.sevenzip or "Not found"),
        ]
        return rows


# ---------- Core batch UI ----------

@dataclass
class QueueItem:
    path: Path
    root: Path | None = None


class ConversionCancelled(Exception):
    pass


class BatchTab(ttk.Frame):
    title = "Base"
    notes = ""

    def __init__(self, master, app: "UniversalConverterApp"):
        super().__init__(master)
        self.app = app
        self.items: list[QueueItem] = []
        self.worker = None
        self.cancel_requested = False

        self.output_format = StringVar(value="")
        self.preserve_structure = BooleanVar(value=False)

        self._build_ui()
        self.refresh_formats()

    def _build_ui(self):
        controls = ttk.Frame(self)
        controls.pack(fill="x", padx=12, pady=12)

        ttk.Button(controls, text="Add Files", command=self.add_files).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Add Folder", command=self.add_folder).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Remove Selected", command=self.remove_selected).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Clear Queue", command=self.clear_items).pack(side="left")

        queue_frame = ttk.Frame(self)
        queue_frame.pack(fill="both", expand=True, padx=12)

        self.listbox = tk.Listbox(queue_frame, selectmode=SINGLE, height=12)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(queue_frame, orient="vertical", command=self.listbox.yview)
        sb.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=sb.set)

        settings = ttk.LabelFrame(self, text="Conversion Settings")
        settings.pack(fill="x", padx=12, pady=12)

        row1 = ttk.Frame(settings)
        row1.pack(fill="x", padx=10, pady=8)
        ttk.Label(row1, text="Output format:", width=18).pack(side="left")
        self.format_box = ttk.Combobox(row1, textvariable=self.output_format, state="readonly", width=24)
        self.format_box.pack(side="left")
        ttk.Button(row1, text="Refresh Options", command=self.refresh_formats).pack(side="left", padx=(8, 0))

        ttk.Checkbutton(
            settings,
            text="Preserve folder structure for folder imports",
            variable=self.preserve_structure,
        ).pack(anchor="w", padx=10, pady=(0, 6))

        self.note_label = ttk.Label(settings, text=self.notes, wraplength=860)
        self.note_label.pack(anchor="w", padx=10, pady=(0, 8))

        progress = ttk.LabelFrame(self, text="Progress")
        progress.pack(fill="x", padx=12, pady=(0, 12))

        self.file_progress = ttk.Progressbar(progress, maximum=100, mode="determinate")
        self.file_progress.pack(fill="x", padx=10, pady=(10, 6))
        self.file_label = ttk.Label(progress, text="Current file: idle")
        self.file_label.pack(anchor="w", padx=10)

        self.batch_progress = ttk.Progressbar(progress, maximum=100, mode="determinate")
        self.batch_progress.pack(fill="x", padx=10, pady=(10, 6))
        self.batch_label = ttk.Label(progress, text="Batch: 0 / 0")
        self.batch_label.pack(anchor="w", padx=10, pady=(0, 10))

        actions = ttk.Frame(self)
        actions.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(actions, text="Choose Output Folder", command=self.choose_output_folder).pack(side="left", padx=(0, 6))
        self.convert_button = ttk.Button(actions, text="Convert Queue", command=self.start_convert)
        self.convert_button.pack(side="left", padx=(0, 6))
        self.cancel_button = ttk.Button(actions, text="Cancel", command=self.request_cancel, state="disabled")
        self.cancel_button.pack(side="left")

        self.output_folder_label = ttk.Label(self, text="Output folder: not selected")
        self.output_folder_label.pack(anchor="w", padx=12)

    def get_output_formats(self) -> list[str]:
        return []

    def refresh_formats(self):
        values = self.get_output_formats()
        self.format_box.configure(values=values)
        if values and self.output_format.get() not in values:
            self.output_format.set(values[0])
        elif not values:
            self.output_format.set("")
        self.note_label.configure(text=self.notes_for_status())
        self.convert_button.configure(state="normal" if values else "disabled")

    def notes_for_status(self) -> str:
        return self.notes

    def supported(self, path: Path) -> bool:
        return False

    def add_files(self):
        files = filedialog.askopenfilenames(title=f"Choose {self.title} files")
        count = 0
        for raw in files:
            path = Path(raw)
            if self.supported(path):
                self._append_item(path, None)
                count += 1
        self.app.log(f"{self.title}: added {count} file(s).")

    def add_folder(self):
        folder = filedialog.askdirectory(title=f"Choose folder for {self.title} files")
        if not folder:
            return
        root = Path(folder)
        count = 0
        for child in root.rglob("*"):
            if child.is_file() and self.supported(child):
                self._append_item(child, root)
                count += 1
        self.app.log(f"{self.title}: added {count} file(s) from folder.")

    def _append_item(self, path: Path, root: Path | None):
        if any(existing.path == path for existing in self.items):
            return
        self.items.append(QueueItem(path=path, root=root))
        self.listbox.insert(END, str(path))

    def remove_selected(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.listbox.delete(idx)
        del self.items[idx]

    def clear_items(self):
        self.items.clear()
        self.listbox.delete(0, END)

    def choose_output_folder(self):
        folder = filedialog.askdirectory(title="Choose output folder")
        if folder:
            self.app.output_folder = Path(folder)
            for tab in self.app.tabs.values():
                tab.output_folder_label.configure(text=f"Output folder: {folder}")
            self.app.log(f"Output folder set to {folder}")

    def request_cancel(self):
        self.cancel_requested = True
        self.cancel_button.configure(state="disabled")
        self.app.log(f"{self.title}: cancel requested...")
        self.app.cancel_active_process(self)

    def target_output_path(self, item: QueueItem, extension: str) -> Path:
        if not self.app.output_folder:
            raise RuntimeError("Choose an output folder first.")
        out_root = self.app.output_folder
        if self.preserve_structure.get() and item.root:
            rel_parent = item.path.parent.relative_to(item.root)
            out_dir = out_root / rel_parent
        else:
            out_dir = out_root
        ensure_dir(out_dir)
        return out_dir / f"{strip_composite_suffix(item.path)}_converted.{extension}"

    def ui(self, action: str, value):
        self.app.ui_queue.put((self, action, value))

    def start_convert(self):
        if not self.items:
            messagebox.showwarning(APP_TITLE, "Add at least one file first.")
            return
        if not self.app.output_folder:
            messagebox.showwarning(APP_TITLE, "Choose an output folder first.")
            return
        if not self.get_output_formats():
            messagebox.showwarning(APP_TITLE, "No usable output formats are available for this tab right now.")
            return
        if self.worker and self.worker.is_alive():
            return

        self.cancel_requested = False
        self.convert_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.file_progress["value"] = 0
        self.batch_progress["value"] = 0
        self.batch_label.configure(text=f"Batch: 0 / {len(self.items)}")
        self.file_label.configure(text="Current file: preparing")
        self.worker = threading.Thread(target=self._convert_worker, daemon=True)
        self.worker.start()

    def _convert_worker(self):
        total = len(self.items)
        converted = 0
        failed = 0
        processed = 0

        for item in self.items:
            if self.cancel_requested:
                break
            self.ui("file_label", f"Current file: {item.path.name}")
            self.ui("file_progress", 0)
            try:
                self.convert_one(item)
                converted += 1
                processed += 1
                self.app.log(f"{self.title}: converted {item.path.name}")
                self.ui("file_progress", 100)
            except ConversionCancelled:
                self.cancel_requested = True
                self.app.log(f"{self.title}: canceled during {item.path.name}")
                self.ui("file_progress", 0)
                break
            except Exception as exc:
                failed += 1
                processed += 1
                self.app.log(f"{self.title}: failed {item.path.name}: {exc}")
                self.ui("file_progress", 0)

            self.ui("batch_progress", processed / total * 100)
            self.ui("batch_label", f"Batch: {processed} / {total}")

        if self.cancel_requested:
            summary = f"{self.title}: canceled after {converted} converted, {failed} failed."
        else:
            summary = f"{self.title}: finished. Converted {converted}, failed {failed}."
        self.app.log(summary)
        self.ui("done", summary)

    def convert_one(self, item: QueueItem):
        raise NotImplementedError


# ---------- Images ----------

class ImagesTab(BatchTab):
    title = "Images"
    pillow_inputs = {
        ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff",
        ".ico", ".ppm", ".pgm", ".pbm", ".pnm", ".pcx", ".tga", ".dds",
        ".xbm", ".xpm", ".icns", ".apng"
    }
    broad_inputs = pillow_inputs | {
        ".avif", ".heic", ".heif", ".jp2", ".j2k", ".jpf", ".jpx", ".jpm", ".jxl",
        ".miff", ".mif", ".dib", ".cur", ".ora", ".wdp"
    }
    pillow_outputs = ["png", "jpg", "webp", "bmp", "gif", "tiff", "ico", "ppm"]
    magick_outputs = ["png", "jpg", "webp", "bmp", "gif", "tiff", "ico", "ppm", "pbm", "pgm", "pnm", "pcx", "tga", "xbm", "xpm", "jp2", "jxl", "avif", "heic", "miff"]

    notes = (
        "Built-in mode uses Pillow for safe raster conversions. If ImageMagick is installed, this tab expands to many less-common "
        "image formats such as AVIF/HEIC/JP2/JXL and can also act as a fallback when Pillow cannot decode a file."
    )

    def get_output_formats(self) -> list[str]:
        formats = list(self.pillow_outputs)
        if self.app.backends.imagemagick:
            for fmt in self.magick_outputs:
                if fmt not in formats:
                    formats.append(fmt)
        return formats

    def notes_for_status(self) -> str:
        if self.app.backends.imagemagick:
            return self.notes + " ImageMagick detected."
        return self.notes + " ImageMagick not detected, so the rare-format list is smaller."

    def supported(self, path: Path) -> bool:
        return composite_suffix(path) in self.broad_inputs

    def _save_with_pillow(self, image: Image.Image, out_path: Path, out_fmt: str):
        fmt_map = {
            "jpg": "JPEG",
            "png": "PNG",
            "webp": "WEBP",
            "bmp": "BMP",
            "gif": "GIF",
            "tiff": "TIFF",
            "ico": "ICO",
            "ppm": "PPM",
        }
        pil_fmt = fmt_map[out_fmt]
        save_image = image
        if out_fmt == "jpg":
            if image.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", image.size, (255, 255, 255))
                alpha_src = image.convert("RGBA")
                bg.paste(alpha_src, mask=alpha_src.getchannel("A"))
                save_image = bg
            elif image.mode != "RGB":
                save_image = image.convert("RGB")
        elif out_fmt in {"bmp", "ppm"} and image.mode != "RGB":
            save_image = image.convert("RGB")
        kwargs = {}
        if out_fmt in {"jpg", "webp"}:
            kwargs["quality"] = int(self.app.image_quality.get())
        save_image.save(out_path, format=pil_fmt, **kwargs)

    def convert_one(self, item: QueueItem):
        out_fmt = self.output_format.get().lower()
        out_path = self.target_output_path(item, out_fmt)
        in_ext = composite_suffix(item.path)
        needs_magick = in_ext not in self.pillow_inputs or out_fmt not in self.pillow_outputs

        if self.app.backends.imagemagick and needs_magick:
            cmd = [self.app.backends.imagemagick, str(item.path)]
            if out_fmt in {"jpg", "webp", "avif", "heic", "jp2", "jxl"}:
                cmd += ["-quality", str(self.app.image_quality.get())]
            cmd.append(str(out_path))
            self.app.run_simple_process(self, cmd)
            return

        try:
            with Image.open(item.path) as image:
                self._save_with_pillow(image, out_path, out_fmt)
        except Exception:
            if self.app.backends.imagemagick:
                cmd = [self.app.backends.imagemagick, str(item.path), str(out_path)]
                self.app.run_simple_process(self, cmd)
            else:
                raise


# ---------- Audio ----------

class AudioTab(BatchTab):
    title = "Audio"
    notes = (
        "Uses FFmpeg. This tab accepts many audio formats and can also extract audio from video files. "
        "The exact encoder availability depends on the FFmpeg build bundled on the Windows machine."
    )

    audio_inputs = {
        ".mp3", ".wav", ".flac", ".aac", ".m4a", ".m4b", ".ogg", ".oga", ".opus", ".wma", ".aif", ".aiff",
        ".ac3", ".eac3", ".amr", ".ape", ".au", ".caf", ".dts", ".mka", ".ra", ".tta", ".voc", ".mp2"
    }
    video_inputs = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mts", ".m2ts", ".ts", ".ogv", ".flv"}
    output_formats = ["mp3", "wav", "flac", "aac", "m4a", "ogg", "opus", "aiff", "ac3", "au", "caf", "wma", "mp2"]

    def get_output_formats(self) -> list[str]:
        return self.output_formats if self.app.backends.ffmpeg else []

    def notes_for_status(self) -> str:
        return self.notes + (" FFmpeg detected." if self.app.backends.ffmpeg else " FFmpeg not detected.")

    def supported(self, path: Path) -> bool:
        return composite_suffix(path) in (self.audio_inputs | self.video_inputs)

    def convert_one(self, item: QueueItem):
        fmt = self.output_format.get().lower()
        out_path = self.target_output_path(item, fmt)
        cmd = [self.app.backends.ffmpeg, "-y", "-i", str(item.path), "-vn"]
        bitrate = self.app.audio_bitrate.get()
        if fmt == "mp3":
            cmd += ["-c:a", "libmp3lame", "-b:a", bitrate]
        elif fmt == "wav":
            cmd += ["-c:a", "pcm_s16le"]
        elif fmt == "flac":
            cmd += ["-c:a", "flac"]
        elif fmt in {"aac", "m4a"}:
            cmd += ["-c:a", "aac", "-b:a", bitrate]
        elif fmt == "ogg":
            cmd += ["-c:a", "libvorbis", "-q:a", "5"]
        elif fmt == "opus":
            cmd += ["-c:a", "libopus", "-b:a", bitrate]
        elif fmt == "aiff":
            cmd += ["-c:a", "pcm_s16be"]
        elif fmt == "ac3":
            cmd += ["-c:a", "ac3", "-b:a", bitrate]
        elif fmt == "au":
            cmd += ["-c:a", "pcm_s16be"]
        elif fmt == "caf":
            cmd += ["-c:a", "pcm_s16le"]
        elif fmt == "wma":
            cmd += ["-c:a", "wmav2", "-b:a", bitrate]
        elif fmt == "mp2":
            cmd += ["-c:a", "mp2", "-b:a", bitrate]
        else:
            raise ValueError("Unsupported audio output format")
        cmd.append(str(out_path))
        self.app.run_ffmpeg(self, cmd, lambda p: self.ui("file_progress", p))


# ---------- Video ----------

class VideoTab(BatchTab):
    title = "Video"
    notes = (
        "Uses FFmpeg for broader container and codec handling. Output choices are intentionally restricted to combinations that are reasonably likely to work across machines."
    )

    inputs = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mts", ".m2ts", ".ts", ".ogv", ".flv", ".3gp", ".wmv", ".asf", ".vob"}
    outputs = ["mp4", "mkv", "mov", "avi", "webm", "ogv", "ts", "m2ts", "flv"]

    def get_output_formats(self) -> list[str]:
        return self.outputs if self.app.backends.ffmpeg else []

    def notes_for_status(self) -> str:
        return self.notes + (" FFmpeg detected." if self.app.backends.ffmpeg else " FFmpeg not detected.")

    def supported(self, path: Path) -> bool:
        return composite_suffix(path) in self.inputs

    def convert_one(self, item: QueueItem):
        fmt = self.output_format.get().lower()
        out_path = self.target_output_path(item, fmt)
        preset = self.app.video_preset.get()
        crf = str(int(self.app.video_crf.get()))
        bitrate = self.app.audio_bitrate.get()
        cmd = [self.app.backends.ffmpeg, "-y", "-i", str(item.path)]

        if fmt in {"mp4", "mkv", "mov"}:
            cmd += ["-c:v", "libx264", "-preset", preset, "-crf", crf, "-c:a", "aac", "-b:a", bitrate]
            if fmt == "mp4":
                cmd += ["-movflags", "+faststart"]
        elif fmt == "avi":
            cmd += ["-c:v", "mpeg4", "-q:v", "5", "-c:a", "libmp3lame", "-b:a", bitrate]
        elif fmt == "webm":
            cmd += ["-c:v", "libvpx-vp9", "-crf", crf, "-b:v", "0", "-row-mt", "1", "-c:a", "libopus", "-b:a", bitrate]
        elif fmt == "ogv":
            cmd += ["-c:v", "libtheora", "-q:v", "7", "-c:a", "libvorbis", "-q:a", "5"]
        elif fmt in {"ts", "m2ts"}:
            cmd += ["-c:v", "libx264", "-preset", preset, "-crf", crf, "-c:a", "ac3", "-b:a", bitrate, "-f", "mpegts"]
        elif fmt == "flv":
            cmd += ["-c:v", "libx264", "-preset", preset, "-crf", crf, "-c:a", "aac", "-b:a", bitrate, "-f", "flv"]
        else:
            raise ValueError("Unsupported video output format")

        cmd.append(str(out_path))
        self.app.run_ffmpeg(self, cmd, lambda p: self.ui("file_progress", p))


# ---------- Data ----------

class DataTab(BatchTab):
    title = "Data"
    notes = "Converts between common structured text formats and a few less-common but still useful ones, such as NDJSON, TOML, INI/properties, and XML."
    inputs = {".json", ".ndjson", ".yaml", ".yml", ".csv", ".tsv", ".toml", ".ini", ".properties", ".xml"}
    outputs = ["json", "ndjson", "yaml", "csv", "tsv", "toml", "ini", "properties", "xml"]

    def get_output_formats(self) -> list[str]:
        return self.outputs

    def supported(self, path: Path) -> bool:
        return composite_suffix(path) in self.inputs

    def _read_structured(self, path: Path):
        ext = composite_suffix(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        if ext == ".json":
            return json.loads(text)
        if ext == ".ndjson":
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        if ext in {".yaml", ".yml"}:
            return yaml.safe_load(text)
        if ext == ".toml":
            return tomllib.loads(text)
        if ext in {".ini", ".properties"}:
            parser = configparser.ConfigParser()
            parser.read_string(text)
            data = {section: dict(parser[section]) for section in parser.sections()}
            if parser.defaults():
                data["DEFAULT"] = dict(parser.defaults())
            return data
        if ext == ".xml":
            return xmltodict.parse(text)
        if ext in {".csv", ".tsv"}:
            delimiter = "," if ext == ".csv" else "\t"
            with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
                return list(csv.DictReader(handle, delimiter=delimiter))
        raise ValueError("Unsupported data input format")

    def _write_structured(self, data, path: Path, fmt: str):
        if fmt == "json":
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return
        if fmt == "ndjson":
            rows = data if isinstance(data, list) else [data]
            lines = [json.dumps(row, ensure_ascii=False) for row in rows]
            path.write_text("\n".join(lines), encoding="utf-8")
            return
        if fmt == "yaml":
            path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
            return
        if fmt == "toml":
            payload = data if isinstance(data, dict) else {"items": data}
            path.write_text(tomli_w.dumps(payload), encoding="utf-8")
            return
        if fmt in {"ini", "properties"}:
            parser = configparser.ConfigParser()
            if isinstance(data, dict):
                simple_scalars = all(not isinstance(v, (dict, list)) for v in data.values())
                if simple_scalars:
                    parser["DEFAULT"] = {str(k): "" if v is None else str(v) for k, v in data.items()}
                else:
                    for section, values in data.items():
                        if isinstance(values, dict):
                            parser[str(section)] = {str(k): "" if v is None else str(v) for k, v in values.items()}
            else:
                rows = flatten_for_table(data)
                parser["DEFAULT"] = {str(i): json.dumps(row, ensure_ascii=False) for i, row in enumerate(rows, start=1)}
            with path.open("w", encoding="utf-8") as handle:
                parser.write(handle, space_around_delimiters=False)
            return
        if fmt == "xml":
            payload = data if isinstance(data, dict) else {"root": {"item": data}}
            path.write_text(xmltodict.unparse(payload, pretty=True), encoding="utf-8")
            return
        if fmt in {"csv", "tsv"}:
            rows = flatten_for_table(data)
            fieldnames = []
            for row in rows:
                for key in row.keys():
                    if key not in fieldnames:
                        fieldnames.append(key)
            delimiter = "," if fmt == "csv" else "\t"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=delimiter)
                writer.writeheader()
                writer.writerows(rows)
            return
        raise ValueError("Unsupported data output format")

    def convert_one(self, item: QueueItem):
        out_fmt = self.output_format.get().lower()
        out_path = self.target_output_path(item, out_fmt)
        data = self._read_structured(item.path)
        self._write_structured(data, out_path, out_fmt)


# ---------- Documents ----------

class DocumentsTab(BatchTab):
    title = "Documents"
    notes = (
        "Pandoc handles markup/text-oriented document conversion. LibreOffice handles office-style documents and PDF export from those documents. "
        "The app only enables conversions that map to at least one detected backend."
    )

    pandoc_inputs = {".md", ".markdown", ".txt", ".rst", ".html", ".htm", ".docx", ".odt", ".epub", ".tex", ".latex", ".org", ".rtf"}
    pandoc_outputs = ["md", "html", "docx", "odt", "epub", "rst", "tex", "rtf", "txt"]
    libreoffice_inputs = {".doc", ".docx", ".odt", ".rtf", ".txt", ".html", ".htm", ".xls", ".xlsx", ".ods", ".csv", ".ppt", ".pptx", ".odp"}
    libreoffice_outputs = ["pdf", "docx", "odt", "rtf", "txt", "html", "xlsx", "ods", "csv", "pptx", "odp"]

    def get_output_formats(self) -> list[str]:
        formats: list[str] = []
        if self.app.backends.pandoc:
            formats.extend(self.pandoc_outputs)
        if self.app.backends.libreoffice:
            for fmt in self.libreoffice_outputs:
                if fmt not in formats:
                    formats.append(fmt)
        return formats

    def notes_for_status(self) -> str:
        pieces = [self.notes]
        if self.app.backends.pandoc:
            pieces.append("Pandoc detected.")
        else:
            pieces.append("Pandoc not detected.")
        if self.app.backends.libreoffice:
            pieces.append("LibreOffice detected.")
        else:
            pieces.append("LibreOffice not detected.")
        return " ".join(pieces)

    def supported(self, path: Path) -> bool:
        ext = composite_suffix(path)
        return ext in self.pandoc_inputs or ext in self.libreoffice_inputs

    def convert_one(self, item: QueueItem):
        out_fmt = self.output_format.get().lower()
        in_ext = composite_suffix(item.path)
        out_path = self.target_output_path(item, out_fmt)

        if self.app.backends.pandoc and in_ext in self.pandoc_inputs and out_fmt in self.pandoc_outputs:
            cmd = [self.app.backends.pandoc, str(item.path), "-o", str(out_path)]
            self.app.run_simple_process(self, cmd)
            return

        if self.app.backends.libreoffice and in_ext in self.libreoffice_inputs and out_fmt in self.libreoffice_outputs:
            temp_out = Path(tempfile.mkdtemp(prefix="ufc_docs_"))
            try:
                cmd = [self.app.backends.libreoffice, "--headless", "--convert-to", out_fmt, "--outdir", str(temp_out), str(item.path)]
                self.app.run_simple_process(self, cmd)
                candidates = sorted(temp_out.glob(f"{item.path.stem}*"))
                if not candidates:
                    raise RuntimeError("LibreOffice did not produce an output file.")
                shutil.move(str(candidates[0]), str(out_path))
            finally:
                shutil.rmtree(temp_out, ignore_errors=True)
            return

        raise ValueError("This document conversion pair needs Pandoc or LibreOffice support that is not currently available.")


# ---------- Vector ----------

class VectorTab(BatchTab):
    title = "Vector"
    notes = (
        "Uses Inkscape when present. This tab is for vector and page-oriented graphics such as SVG, PDF, EPS, PS, and some AI/PDF-like imports that Inkscape can open."
    )
    inputs = {".svg", ".svgz", ".pdf", ".eps", ".ps", ".ai"}
    outputs = ["png", "pdf", "eps", "ps", "svg", "jpg", "webp", "tiff"]

    def get_output_formats(self) -> list[str]:
        return self.outputs if self.app.backends.inkscape else []

    def notes_for_status(self) -> str:
        return self.notes + (" Inkscape detected." if self.app.backends.inkscape else " Inkscape not detected.")

    def supported(self, path: Path) -> bool:
        return composite_suffix(path) in self.inputs

    def convert_one(self, item: QueueItem):
        fmt = self.output_format.get().lower()
        out_path = self.target_output_path(item, fmt)
        cmd = [self.app.backends.inkscape, str(item.path)]
        if fmt == "svg":
            cmd += ["--export-plain-svg", f"--export-filename={out_path}"]
        else:
            cmd += [f"--export-filename={out_path}"]
        self.app.run_simple_process(self, cmd)


# ---------- Ebooks ----------

class EbooksTab(BatchTab):
    title = "Ebooks"
    notes = (
        "Uses calibre's ebook-convert tool when installed. It supports many ebook-specific formats, but DRM-protected files are outside scope."
    )
    inputs = {".azw", ".azw3", ".azw4", ".cbz", ".cbr", ".cb7", ".cbc", ".chm", ".djvu", ".docx", ".epub", ".fb2", ".fbz", ".html", ".htmlz", ".kepub", ".lit", ".lrf", ".mobi", ".odt", ".pdf", ".prc", ".pdb", ".pml", ".rb", ".rtf", ".snb", ".tcr", ".txt", ".txtz"}
    outputs = ["epub", "azw3", "mobi", "fb2", "docx", "odt", "pdf", "rtf", "txt", "htmlz"]

    def get_output_formats(self) -> list[str]:
        return self.outputs if self.app.backends.calibre else []

    def notes_for_status(self) -> str:
        return self.notes + (" calibre detected." if self.app.backends.calibre else " calibre not detected.")

    def supported(self, path: Path) -> bool:
        return composite_suffix(path) in self.inputs

    def convert_one(self, item: QueueItem):
        fmt = self.output_format.get().lower()
        out_path = self.target_output_path(item, fmt)
        cmd = [self.app.backends.calibre, str(item.path), str(out_path)]
        self.app.run_simple_process(self, cmd)


# ---------- Archives ----------

class ArchivesTab(BatchTab):
    title = "Archives"
    notes = (
        "Pure Python handles ZIP/TAR/TAR.GZ/TAR.BZ2/TAR.XZ/7Z output. If 7-Zip is installed, this tab can also read more unusual archives such as RAR, CAB, ISO, and WIM for repacking into supported output formats."
    )
    python_inputs = {".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz", ".7z"}
    sevenzip_extra_inputs = {".rar", ".cab", ".iso", ".wim", ".arj", ".lzh"}

    def get_output_formats(self) -> list[str]:
        return ["zip", "tar", "tar.gz", "tar.bz2", "tar.xz", "7z"]

    def notes_for_status(self) -> str:
        if self.app.backends.sevenzip:
            return self.notes + " 7-Zip detected for extra input formats."
        return self.notes + " 7-Zip not detected, so rare archive inputs are unavailable."

    def supported(self, path: Path) -> bool:
        ext = composite_suffix(path)
        if ext in self.python_inputs:
            return True
        return bool(self.app.backends.sevenzip and ext in self.sevenzip_extra_inputs)

    def _extract_to(self, item: QueueItem, temp_dir: Path):
        ext = composite_suffix(item.path)
        if ext == ".zip":
            with zipfile.ZipFile(item.path, "r") as zf:
                zf.extractall(temp_dir)
            return
        if ext in {".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz"}:
            with tarfile.open(item.path, "r:*") as tf:
                tf.extractall(temp_dir)
            return
        if ext == ".7z":
            with py7zr.SevenZipFile(item.path, mode="r") as archive:
                archive.extractall(path=temp_dir)
            return
        if self.app.backends.sevenzip and ext in self.sevenzip_extra_inputs:
            cmd = [self.app.backends.sevenzip, "x", str(item.path), f"-o{temp_dir}", "-y"]
            self.app.run_simple_process(self, cmd)
            return
        raise ValueError("Unsupported archive input format")

    def _pack_from(self, source_dir: Path, out_path: Path, fmt: str):
        if fmt == "zip":
            with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for file in source_dir.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(source_dir))
            return
        if fmt in {"tar", "tar.gz", "tar.bz2", "tar.xz"}:
            mode = {"tar": "w", "tar.gz": "w:gz", "tar.bz2": "w:bz2", "tar.xz": "w:xz"}[fmt]
            with tarfile.open(out_path, mode) as tf:
                for file in source_dir.rglob("*"):
                    tf.add(file, arcname=file.relative_to(source_dir))
            return
        if fmt == "7z":
            with py7zr.SevenZipFile(out_path, mode="w") as archive:
                for file in source_dir.rglob("*"):
                    archive.write(file, arcname=str(file.relative_to(source_dir)))
            return
        raise ValueError("Unsupported archive output format")

    def convert_one(self, item: QueueItem):
        fmt = self.output_format.get().lower()
        out_path = self.target_output_path(item, fmt)
        temp_dir = Path(tempfile.mkdtemp(prefix="ufc_archive_"))
        try:
            self._extract_to(item, temp_dir)
            self._pack_from(temp_dir, out_path, fmt)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


# ---------- Main app ----------

class UniversalConverterApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1120x860")
        self.root.minsize(1000, 760)

        self.ui_queue = queue.Queue()
        self.main_thread = threading.current_thread()
        self.output_folder: Path | None = None
        self.backends = BackendRegistry.detect()
        self.active_processes: dict[BatchTab, subprocess.Popen] = {}

        self.image_quality = IntVar(value=92)
        self.audio_bitrate = StringVar(value="192k")
        self.video_preset = StringVar(value="veryfast")
        self.video_crf = IntVar(value=23)

        self._build_ui()
        self.root.after(100, self.poll_ui_queue)

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=12)
        top.pack(fill="both", expand=True)

        header = ttk.Frame(top)
        header.pack(fill="x")
        ttk.Label(header, text=APP_TITLE, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            header,
            text="A broader Windows conversion hub that combines built-in Python handlers with optional external backends like FFmpeg, ImageMagick, Pandoc, LibreOffice, Inkscape, calibre, and 7-Zip.",
            wraplength=1040,
        ).pack(anchor="w", pady=(4, 10))

        backend_box = ttk.LabelFrame(top, text="Detected backends on this machine")
        backend_box.pack(fill="x", pady=(0, 12))
        rows = ttk.Frame(backend_box)
        rows.pack(fill="x", padx=10, pady=10)
        for idx, (name, value) in enumerate(self.backends.status_rows()):
            ttk.Label(rows, text=f"{name}:", width=14).grid(row=idx // 2, column=(idx % 2) * 2, sticky="w", padx=(0, 6), pady=2)
            ttk.Label(rows, text=value).grid(row=idx // 2, column=(idx % 2) * 2 + 1, sticky="w", padx=(0, 20), pady=2)

        presets = ttk.LabelFrame(top, text="Global presets")
        presets.pack(fill="x", pady=(0, 12))
        row = ttk.Frame(presets)
        row.pack(fill="x", padx=10, pady=10)

        ttk.Label(row, text="Image quality").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Scale(row, from_=10, to=100, variable=self.image_quality, orient="horizontal").grid(row=0, column=1, sticky="ew", padx=(0, 18))
        ttk.Label(row, textvariable=self.image_quality, width=5).grid(row=0, column=2, sticky="w")

        ttk.Label(row, text="Audio bitrate").grid(row=0, column=3, sticky="w", padx=(18, 8))
        ttk.Combobox(row, textvariable=self.audio_bitrate, values=["96k", "128k", "160k", "192k", "256k", "320k"], width=10, state="readonly").grid(row=0, column=4, sticky="w")

        ttk.Label(row, text="Video preset").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(10, 0))
        ttk.Combobox(row, textvariable=self.video_preset, values=["ultrafast", "veryfast", "medium", "slow"], width=12, state="readonly").grid(row=1, column=1, sticky="w", pady=(10, 0))

        ttk.Label(row, text="Video CRF").grid(row=1, column=3, sticky="w", padx=(18, 8), pady=(10, 0))
        ttk.Scale(row, from_=18, to=35, variable=self.video_crf, orient="horizontal").grid(row=1, column=4, sticky="ew", pady=(10, 0))
        ttk.Label(row, textvariable=self.video_crf, width=5).grid(row=1, column=5, sticky="w", pady=(10, 0))
        row.columnconfigure(1, weight=1)
        row.columnconfigure(4, weight=1)

        self.notebook = ttk.Notebook(top)
        self.notebook.pack(fill="both", expand=True)

        self.tabs = {
            "Images": ImagesTab(self.notebook, self),
            "Audio": AudioTab(self.notebook, self),
            "Video": VideoTab(self.notebook, self),
            "Data": DataTab(self.notebook, self),
            "Documents": DocumentsTab(self.notebook, self),
            "Vector": VectorTab(self.notebook, self),
            "Ebooks": EbooksTab(self.notebook, self),
            "Archives": ArchivesTab(self.notebook, self),
        }
        for name, tab in self.tabs.items():
            self.notebook.add(tab, text=name)

        log_frame = ttk.LabelFrame(top, text="Activity log")
        log_frame.pack(fill="both", pady=(12, 0))
        self.log_box = tk.Text(log_frame, height=11, wrap="word")
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)
        self.log("Ready.")

    def _append_log(self, message: str):
        self.log_box.insert(END, message + "\n")
        self.log_box.see(END)

    def log(self, message: str):
        if threading.current_thread() is self.main_thread:
            self._append_log(message)
        else:
            self.ui_queue.put((None, "log", message))

    def poll_ui_queue(self):
        try:
            while True:
                tab, action, value = self.ui_queue.get_nowait()
                if action == "log":
                    self._append_log(value)
                elif action == "file_progress":
                    tab.file_progress["value"] = value
                elif action == "batch_progress":
                    tab.batch_progress["value"] = value
                elif action == "batch_label":
                    tab.batch_label.configure(text=value)
                elif action == "file_label":
                    tab.file_label.configure(text=value)
                elif action == "done":
                    tab.convert_button.configure(state="normal")
                    tab.cancel_button.configure(state="disabled")
                    tab.file_label.configure(text="Current file: idle")
                    messagebox.showinfo(APP_TITLE, value)
        except queue.Empty:
            pass
        self.root.after(100, self.poll_ui_queue)

    def cancel_active_process(self, tab: BatchTab):
        proc = self.active_processes.get(tab)
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                self.log(f"{tab.title}: stopping active process...")
            except Exception as exc:
                self.log(f"{tab.title}: failed to stop process cleanly: {exc}")

    def run_simple_process(self, tab: BatchTab, cmd: list[str], cwd: Path | None = None):
        self.log(quote_cmd(cmd))
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
        self.active_processes[tab] = proc
        recent = deque(maxlen=25)
        try:
            assert proc.stdout is not None
            for raw_line in proc.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                recent.append(line)
                lower = line.lower()
                if any(k in lower for k in ("error", "warning", "failed", "invalid")):
                    self.log(f"{tab.title}: {line}")
                if tab.cancel_requested and proc.poll() is None:
                    proc.terminate()
            try:
                code = proc.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                proc.kill()
                code = proc.wait()

            if tab.cancel_requested:
                raise ConversionCancelled("Conversion canceled by user.")
            if code != 0:
                detail = recent[-1] if recent else f"Process exited with code {code}"
                raise RuntimeError(detail)
        finally:
            self.active_processes.pop(tab, None)

    def run_ffmpeg(self, tab: BatchTab, cmd: list[str], on_progress):
        self.log(quote_cmd(cmd))
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
        )
        self.active_processes[tab] = proc

        duration = None
        time_pattern = re.compile(r"time=(\d{2}:\d{2}:\d{2}\.\d+)")
        dur_pattern = re.compile(r"Duration:\s*(\d{2}:\d{2}:\d{2}\.\d+)")
        last_logged_percent = -10.0
        last_progress_log_at = 0.0
        recent_lines = deque(maxlen=20)

        try:
            assert proc.stderr is not None
            for raw_line in proc.stderr:
                line = raw_line.strip()
                if not line:
                    continue
                recent_lines.append(line)
                lower = line.lower()
                if any(word in lower for word in ("error", "warning", "invalid", "failed")):
                    self.log(f"FFmpeg: {line}")
                if duration is None:
                    m = dur_pattern.search(line)
                    if m:
                        duration = seconds_from_hms(m.group(1))
                m = time_pattern.search(line)
                if m and duration:
                    current = seconds_from_hms(m.group(1))
                    percent = max(0.0, min(100.0, current / duration * 100.0))
                    on_progress(percent)
                    now = time.monotonic()
                    if percent >= last_logged_percent + 10.0 or now - last_progress_log_at >= 5.0:
                        self.log(f"{tab.title}: FFmpeg progress {percent:.1f}%")
                        last_logged_percent = percent
                        last_progress_log_at = now
                if tab.cancel_requested and proc.poll() is None:
                    proc.terminate()
            try:
                code = proc.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                proc.kill()
                code = proc.wait()

            if tab.cancel_requested:
                raise ConversionCancelled("Conversion canceled by user.")
            if code != 0:
                detail = recent_lines[-1] if recent_lines else f"ffmpeg exited with code {code}"
                raise RuntimeError(detail)
        finally:
            self.active_processes.pop(tab, None)


def main():
    root = Tk()
    UniversalConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
