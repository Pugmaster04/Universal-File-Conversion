import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import BooleanVar, StringVar, filedialog, messagebox, ttk


APP_TITLE = "Universal File Utility Suite Updater"
CURRENT_VERSION = "0.5"
APP_SLUG = "UniversalFileUtilitySuite"


def looks_like_sha256(value: str) -> bool:
    candidate = value.strip().lower()
    return bool(re.fullmatch(r"[0-9a-f]{64}", candidate))


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
        self.root.geometry("800x560")
        self.root.minsize(720, 500)

        self.script_dir = Path(__file__).resolve().parent
        self.resource_dir = Path(getattr(sys, "_MEIPASS", self.script_dir))
        self.runtime_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else self.script_dir
        self.appdata_dir = Path(os.environ.get("LOCALAPPDATA", str(self.runtime_dir))) / APP_SLUG
        self.settings_path = self.appdata_dir / "updater_settings.json"
        self.settings = self._load_settings()

        self._apply_icon()

        self.source_var = StringVar(value=self._default_manifest_source())
        self.version_var = StringVar(value=CURRENT_VERSION)
        self.output_dir_var = StringVar(value=str(self.runtime_dir))
        self.status_var = StringVar(value="Ready.")
        self.latest_var = StringVar(value="Latest version: (not checked)")
        self.download_var = StringVar(value="Download URL: (not checked)")
        self.sha256_var = StringVar(value="SHA256: (not provided)")
        self.require_https_manifest_var = BooleanVar(value=bool(self.settings.get("require_https_manifest", True)))
        self.require_https_download_var = BooleanVar(value=bool(self.settings.get("require_https_download", True)))
        self.require_sha256_var = BooleanVar(value=bool(self.settings.get("require_sha256_verification", True)))
        self.confirm_external_links_var = BooleanVar(value=bool(self.settings.get("confirm_external_links", True)))

        self.last_manifest: dict[str, Any] | None = None
        self.last_download_url = ""
        self.last_latest = ""
        self.last_sha256 = ""
        self.last_download_block_reason = ""
        self.checking = False
        self.downloading = False

        self._build_ui()
        self._bind_setting_traces()
        self._save_settings()

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

    def _default_settings(self) -> dict[str, Any]:
        return {
            "require_https_manifest": True,
            "require_https_download": True,
            "require_sha256_verification": True,
            "confirm_external_links": True,
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
        self.appdata_dir.mkdir(parents=True, exist_ok=True)
        self.settings["require_https_manifest"] = bool(self.require_https_manifest_var.get())
        self.settings["require_https_download"] = bool(self.require_https_download_var.get())
        self.settings["require_sha256_verification"] = bool(self.require_sha256_var.get())
        self.settings["confirm_external_links"] = bool(self.confirm_external_links_var.get())
        self.settings_path.write_text(json.dumps(self.settings, indent=2, ensure_ascii=False), encoding="utf-8")

    def _bind_setting_traces(self) -> None:
        def on_change(*_args) -> None:
            self._save_settings()

        self.require_https_manifest_var.trace_add("write", on_change)
        self.require_https_download_var.trace_add("write", on_change)
        self.require_sha256_var.trace_add("write", on_change)
        self.confirm_external_links_var.trace_add("write", on_change)

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

    def _url_scheme(self, value: str) -> str:
        return urllib.parse.urlparse(value.strip()).scheme.lower()

    def _validate_web_url(self, value: str, require_https: bool) -> tuple[bool, str]:
        scheme = self._url_scheme(value)
        if scheme not in {"http", "https"}:
            return False, f"Unsupported URL scheme '{scheme or '(none)'}'."
        if require_https and scheme != "https":
            return False, "HTTPS is required by current security settings."
        return True, ""

    def _extract_manifest_sha256(self, manifest: dict[str, Any]) -> str:
        candidates = [
            manifest.get("sha256"),
            manifest.get("sha256_hex"),
            manifest.get("file_sha256"),
        ]
        for value in candidates:
            if value is None:
                continue
            text = str(value).strip().lower()
            if looks_like_sha256(text):
                return text
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
        hash_row = ttk.Frame(outer)
        hash_row.pack(fill="x", pady=(0, 8))
        ttk.Label(hash_row, textvariable=self.sha256_var, wraplength=710).pack(side="left", anchor="w")

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

        security_frame = ttk.Labelframe(outer, text="Security Options")
        security_frame.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(
            security_frame,
            text="Require HTTPS for update manifest URL",
            variable=self.require_https_manifest_var,
        ).pack(anchor="w", padx=8, pady=(4, 0))
        ttk.Checkbutton(
            security_frame,
            text="Require HTTPS for download URL",
            variable=self.require_https_download_var,
        ).pack(anchor="w", padx=8)
        ttk.Checkbutton(
            security_frame,
            text="Require SHA256 checksum in manifest and verify downloaded file",
            variable=self.require_sha256_var,
        ).pack(anchor="w", padx=8)
        ttk.Checkbutton(
            security_frame,
            text="Confirm before opening external links",
            variable=self.confirm_external_links_var,
        ).pack(anchor="w", padx=8, pady=(0, 4))

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
            allow, reason = self._validate_web_url(
                source,
                require_https=bool(self.require_https_manifest_var.get()),
            )
            if not allow:
                raise RuntimeError(f"Manifest URL blocked by security settings.\n{reason}")
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
                sha256_value = self._extract_manifest_sha256(manifest)
                blocked_reason = ""
                if not latest:
                    raise RuntimeError("Manifest is missing latest_version/version.")
                if download_url:
                    allow_dl, reason = self._validate_web_url(
                        download_url,
                        require_https=bool(self.require_https_download_var.get()),
                    )
                    if not allow_dl:
                        blocked_reason = f"Download URL blocked by security settings: {reason}"
                        download_url = ""

                current = self.version_var.get().strip() or CURRENT_VERSION
                newer = is_version_newer(latest, current)

                def apply() -> None:
                    self.last_manifest = manifest
                    self.last_download_url = download_url
                    self.last_latest = latest
                    self.last_sha256 = sha256_value
                    self.last_download_block_reason = blocked_reason
                    self.latest_var.set(f"Latest version: {latest}")
                    self.download_var.set(f"Download URL: {download_url or '(not provided)'}")
                    self.sha256_var.set(f"SHA256: {sha256_value or '(not provided)'}")
                    combined_notes = notes or "(No release notes.)"
                    if blocked_reason:
                        combined_notes = f"{combined_notes}\n\n{blocked_reason}"
                    self._set_notes(combined_notes)
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
        allow, reason = self._validate_web_url(url, require_https=bool(self.require_https_download_var.get()))
        if not allow:
            messagebox.showwarning(APP_TITLE, f"Cannot open download URL.\n\n{reason}\n\nURL: {url}")
            return
        if bool(self.confirm_external_links_var.get()):
            go = messagebox.askyesno(APP_TITLE, f"Open this external link?\n\n{url}")
            if not go:
                self.status_var.set("Canceled opening external link.")
                return
        webbrowser.open(url)
        self.status_var.set("Opened download URL in browser.")

    def _download_update_clicked(self) -> None:
        if self.downloading:
            return
        if self.last_download_block_reason:
            messagebox.showwarning(APP_TITLE, f"Cannot download.\n\n{self.last_download_block_reason}")
            return
        url = self.last_download_url.strip()
        if not url:
            messagebox.showwarning(APP_TITLE, "No download URL is available yet. Run Check for Updates first.")
            return
        allow_url, url_reason = self._validate_web_url(url, require_https=bool(self.require_https_download_var.get()))
        if not allow_url:
            messagebox.showwarning(APP_TITLE, f"Download URL blocked by security settings.\n\n{url_reason}\n\nURL: {url}")
            return
        expected_sha256 = self.last_sha256.strip().lower()
        if bool(self.require_sha256_var.get()) and not expected_sha256:
            messagebox.showwarning(
                APP_TITLE,
                "Security policy requires SHA256 verification, but manifest did not provide a valid sha256 value.",
            )
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
                hasher = hashlib.sha256()
                with urllib.request.urlopen(req, timeout=30) as response, target_path.open("wb") as out_file:
                    total_header = response.headers.get("Content-Length", "")
                    total = int(total_header) if total_header.isdigit() else 0
                    read = 0
                    while True:
                        chunk = response.read(1024 * 128)
                        if not chunk:
                            break
                        out_file.write(chunk)
                        hasher.update(chunk)
                        read += len(chunk)
                        if total > 0:
                            pct = max(1, min(100, int((read / total) * 100)))
                            self.root.after(0, lambda p=pct: self.progress.configure(value=p))
                actual_sha256 = hasher.hexdigest().lower()
                if expected_sha256 and actual_sha256 != expected_sha256:
                    try:
                        target_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    raise RuntimeError(
                        "Downloaded file hash mismatch.\n\n"
                        f"Expected: {expected_sha256}\n"
                        f"Actual:   {actual_sha256}\n\n"
                        "File was removed."
                    )
                if bool(self.require_sha256_var.get()) and not expected_sha256:
                    try:
                        target_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    raise RuntimeError(
                        "Downloaded file has no manifest SHA256 to verify against.\n"
                        "File was removed due to security policy."
                    )

                def done() -> None:
                    self.progress.configure(value=100)
                    if expected_sha256:
                        self.status_var.set(f"Download verified (SHA256): {target_path}")
                    else:
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
                try:
                    target_path.unlink(missing_ok=True)
                except Exception:
                    pass
                self.root.after(0, lambda: messagebox.showerror(APP_TITLE, f"Download failed:\n{exc}"))
                self.root.after(0, lambda: self.status_var.set("Download failed."))
                self.root.after(0, lambda: self.progress.configure(value=0))
            except Exception as exc:
                try:
                    target_path.unlink(missing_ok=True)
                except Exception:
                    pass
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
