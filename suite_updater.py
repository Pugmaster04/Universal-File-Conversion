import json
import os
import re
import subprocess
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import StringVar, filedialog, messagebox, ttk


APP_TITLE = "Universal File Utility Suite Updater"
CURRENT_VERSION = "0.5"


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


class UpdaterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("760x460")
        self.root.minsize(680, 420)

        self.script_dir = Path(__file__).resolve().parent
        self.resource_dir = Path(getattr(__import__("sys"), "_MEIPASS", self.script_dir))
        self.runtime_dir = Path(__import__("sys").executable).resolve().parent if getattr(__import__("sys"), "frozen", False) else self.script_dir

        self._apply_icon()

        self.source_var = StringVar(value=self._default_manifest_source())
        self.version_var = StringVar(value=CURRENT_VERSION)
        self.output_dir_var = StringVar(value=str(self.runtime_dir))
        self.status_var = StringVar(value="Ready.")
        self.latest_var = StringVar(value="Latest version: (not checked)")
        self.download_var = StringVar(value="Download URL: (not checked)")

        self.last_manifest: dict[str, Any] | None = None
        self.last_download_url = ""
        self.last_latest = ""
        self.checking = False
        self.downloading = False

        self._build_ui()

    def _apply_icon(self) -> None:
        candidates = [
            self.resource_dir / "assets" / "universal_file_utility_suite.ico",
            self.runtime_dir / "assets" / "universal_file_utility_suite.ico",
            self.script_dir / "assets" / "universal_file_utility_suite.ico",
        ]
        for candidate in candidates:
            if candidate.exists():
                try:
                    self.root.iconbitmap(default=str(candidate))
                    return
                except Exception:
                    continue

    def _default_manifest_source(self) -> str:
        candidates = [
            self.runtime_dir / "update_manifest.json",
            self.runtime_dir / "update_manifest.example.json",
            self.script_dir / "update_manifest.json",
            self.script_dir / "update_manifest.example.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return ""

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text=APP_TITLE, font=("Segoe UI Semibold", 14)).pack(anchor="w")
        ttk.Label(
            outer,
            text="Checks update manifests and downloads the newest app/installer executable.",
            foreground="#4D5F76",
            wraplength=710,
        ).pack(anchor="w", pady=(2, 10))

        source_row = ttk.Frame(outer)
        source_row.pack(fill="x", pady=(0, 8))
        ttk.Label(source_row, text="Manifest URL or file path:").pack(side="left")
        ttk.Entry(source_row, textvariable=self.source_var).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(source_row, text="Browse", command=self._browse_manifest).pack(side="left")

        ver_row = ttk.Frame(outer)
        ver_row.pack(fill="x", pady=(0, 8))
        ttk.Label(ver_row, text="Current app version:").pack(side="left")
        ttk.Entry(ver_row, width=12, textvariable=self.version_var).pack(side="left", padx=(8, 16))
        ttk.Label(ver_row, textvariable=self.latest_var).pack(side="left")

        dl_row = ttk.Frame(outer)
        dl_row.pack(fill="x", pady=(0, 8))
        ttk.Label(dl_row, textvariable=self.download_var, wraplength=710).pack(side="left", anchor="w")

        out_row = ttk.Frame(outer)
        out_row.pack(fill="x", pady=(0, 8))
        ttk.Label(out_row, text="Download folder:").pack(side="left")
        ttk.Entry(out_row, textvariable=self.output_dir_var).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(out_row, text="Browse", command=self._browse_output_dir).pack(side="left")
        ttk.Button(out_row, text="Open", command=self._open_output_dir).pack(side="left", padx=(8, 0))

        action_row = ttk.Frame(outer)
        action_row.pack(fill="x", pady=(8, 8))
        ttk.Button(action_row, text="Check for Updates", command=self._check_updates_clicked).pack(side="left")
        ttk.Button(action_row, text="Download Update", command=self._download_update_clicked).pack(side="left", padx=(8, 0))
        ttk.Button(action_row, text="Open Download Link", command=self._open_download_link).pack(side="left", padx=(8, 0))

        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=100, value=0)
        self.progress.pack(fill="x", pady=(0, 8))

        self.notes_box = tk.Text(outer, height=11, wrap="word")
        self.notes_box.pack(fill="both", expand=True)
        self.notes_box.insert("1.0", "Release notes will appear here after update check.")
        self.notes_box.configure(state="disabled")

        status = ttk.Label(outer, textvariable=self.status_var)
        status.pack(anchor="w", pady=(8, 0))

    def _browse_manifest(self) -> None:
        raw = filedialog.askopenfilename(
            title="Select update manifest JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if raw:
            self.source_var.set(raw)

    def _browse_output_dir(self) -> None:
        raw = filedialog.askdirectory(title="Choose download folder")
        if raw:
            self.output_dir_var.set(raw)

    def _open_output_dir(self) -> None:
        target = Path(self.output_dir_var.get().strip() or str(self.runtime_dir))
        target.mkdir(parents=True, exist_ok=True)
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(target))
                return
            subprocess.Popen(["xdg-open", str(target)])
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Failed to open output folder:\n{exc}")

    def _set_notes(self, text: str) -> None:
        self.notes_box.configure(state="normal")
        self.notes_box.delete("1.0", "end")
        self.notes_box.insert("1.0", text.strip() or "(No release notes.)")
        self.notes_box.configure(state="disabled")

    def _read_manifest(self, source: str) -> dict[str, Any]:
        source = source.strip()
        if not source:
            raise RuntimeError("Provide a manifest URL or local JSON file path.")
        if source.lower().startswith(("http://", "https://")):
            with urllib.request.urlopen(source, timeout=18) as response:
                payload = response.read().decode("utf-8", errors="replace")
            return json.loads(payload)
        path = Path(source).expanduser().resolve()
        if not path.exists():
            raise RuntimeError(f"Manifest file was not found:\n{path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _check_updates_clicked(self) -> None:
        if self.checking:
            return
        self.checking = True
        self.status_var.set("Checking updates...")
        self.progress.configure(value=8)

        def worker() -> None:
            try:
                manifest = self._read_manifest(self.source_var.get())
                latest = str(manifest.get("latest_version") or manifest.get("version") or "").strip()
                download_url = str(manifest.get("download_url") or manifest.get("url") or "").strip()
                notes = str(manifest.get("notes") or manifest.get("release_notes") or "").strip()
                if not latest:
                    raise RuntimeError("Manifest is missing latest_version/version.")

                current = self.version_var.get().strip() or CURRENT_VERSION
                newer = is_version_newer(latest, current)

                def apply() -> None:
                    self.last_manifest = manifest
                    self.last_download_url = download_url
                    self.last_latest = latest
                    self.latest_var.set(f"Latest version: {latest}")
                    self.download_var.set(f"Download URL: {download_url or '(not provided)'}")
                    self._set_notes(notes or "(No release notes.)")
                    self.progress.configure(value=100)
                    if newer:
                        self.status_var.set(f"Update available: {current} -> {latest}")
                        messagebox.showinfo(APP_TITLE, f"Update available.\n\nCurrent: {current}\nLatest: {latest}")
                    else:
                        self.status_var.set(f"Already up to date ({current}).")
                self.root.after(0, apply)
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror(APP_TITLE, f"Update check failed:\n{exc}"))
                self.root.after(0, lambda: self.status_var.set("Update check failed."))
                self.root.after(0, lambda: self.progress.configure(value=0))
            finally:
                self.root.after(0, lambda: setattr(self, "checking", False))

        threading.Thread(target=worker, daemon=True).start()

    def _open_download_link(self) -> None:
        url = self.last_download_url.strip()
        if not url:
            messagebox.showwarning(APP_TITLE, "No download URL is available yet. Run Check for Updates first.")
            return
        import webbrowser

        webbrowser.open(url)
        self.status_var.set("Opened download URL in browser.")

    def _download_update_clicked(self) -> None:
        if self.downloading:
            return
        url = self.last_download_url.strip()
        if not url:
            messagebox.showwarning(APP_TITLE, "No download URL is available yet. Run Check for Updates first.")
            return
        out_dir = Path(self.output_dir_var.get().strip() or str(self.runtime_dir))
        out_dir.mkdir(parents=True, exist_ok=True)

        parsed = urllib.parse.urlparse(url)
        default_name = Path(parsed.path).name or f"UniversalFileUtilitySuite_Update_{self.last_latest or 'latest'}.exe"
        target = filedialog.asksaveasfilename(
            title="Save update executable as",
            initialdir=str(out_dir),
            initialfile=default_name,
            defaultextension=".exe",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if not target:
            return

        target_path = Path(target)
        self.downloading = True
        self.progress.configure(value=0)
        self.status_var.set(f"Downloading update to {target_path.name}...")

        def worker() -> None:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "UniversalFileUtilitySuite-Updater/1.0"})
                with urllib.request.urlopen(req, timeout=30) as response, target_path.open("wb") as out_file:
                    total_header = response.headers.get("Content-Length", "")
                    total = int(total_header) if total_header.isdigit() else 0
                    read = 0
                    while True:
                        chunk = response.read(1024 * 128)
                        if not chunk:
                            break
                        out_file.write(chunk)
                        read += len(chunk)
                        if total > 0:
                            pct = max(1, min(100, int((read / total) * 100)))
                            self.root.after(0, lambda p=pct: self.progress.configure(value=p))

                def done() -> None:
                    self.progress.configure(value=100)
                    self.status_var.set(f"Download complete: {target_path}")
                    if messagebox.askyesno(APP_TITLE, "Download complete.\n\nOpen file location?"):
                        try:
                            if os.name == "nt":
                                subprocess.Popen(["explorer", "/select,", str(target_path)])
                            else:
                                self._open_output_dir()
                        except Exception:
                            self._open_output_dir()

                self.root.after(0, done)
            except (urllib.error.URLError, TimeoutError) as exc:
                self.root.after(0, lambda: messagebox.showerror(APP_TITLE, f"Download failed:\n{exc}"))
                self.root.after(0, lambda: self.status_var.set("Download failed."))
                self.root.after(0, lambda: self.progress.configure(value=0))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror(APP_TITLE, f"Download failed:\n{exc}"))
                self.root.after(0, lambda: self.status_var.set("Download failed."))
                self.root.after(0, lambda: self.progress.configure(value=0))
            finally:
                self.root.after(0, lambda: setattr(self, "downloading", False))

        threading.Thread(target=worker, daemon=True).start()


def main() -> None:
    root = tk.Tk()
    UpdaterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
