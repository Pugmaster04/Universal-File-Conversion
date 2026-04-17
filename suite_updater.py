import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import threading
import ctypes
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from functools import lru_cache
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import BooleanVar, StringVar, filedialog, messagebox, ttk

from support_runtime import (
    DEFAULT_GITHUB_REPO,
    DEFAULT_GITHUB_REPO_URL,
    DEFAULT_TRUSTED_UPDATE_HOSTS,
    build_environment_snapshot,
    evaluate_manifest_compatibility,
    parse_trusted_host_patterns,
    validate_trusted_remote_url,
)


APP_TITLE = "Format Foundry Updater"
CURRENT_VERSION = "1.8.8"
APP_SLUG = "FormatFoundry"
LEGACY_APP_SLUGS = ("UniversalConversionHubUCH", "UniversalConversionHubHCB", "UniversalFileUtilitySuite")
SINGLE_INSTANCE_MUTEX_NAMES = (
    "Local\\FormatFoundryUpdater_SingleInstanceMutex",
    "Local\\UniversalConversionHubUCHUpdater_SingleInstanceMutex",
    "Local\\UniversalConversionHubHCBUpdater_SingleInstanceMutex",
    "Local\\UniversalFileUtilitySuiteUpdater_SingleInstanceMutex",
)
SINGLE_INSTANCE_LOCKFILE_NAME = "format_foundry_updater.lock"
UPDATER_USER_AGENT = f"FormatFoundry-Updater/{CURRENT_VERSION}"
DEFAULT_UPDATE_DOWNLOAD_PREFIX = "FormatFoundry_Update"
LEGACY_WINDOW_TITLES = (
    APP_TITLE,
    "Universal Conversion Hub (UCH) Updater",
    "Universal Conversion Hub (HCB) Updater",
    "Universal File Utility Suite Updater",
)


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


@lru_cache(maxsize=1)
def resolve_git_executable() -> str:
    candidates: list[str] = ["git"]
    if os.name == "nt":
        candidates.extend(
            [
                r"C:\Program Files\Git\cmd\git.exe",
                r"C:\Program Files\Git\bin\git.exe",
                r"C:\Users\Pugma\AppData\Local\GitHubDesktop\app-3.5.6\resources\app\git\cmd\git.exe",
            ]
        )
    for git_cmd in candidates:
        try:
            probe = subprocess.run(
                [git_cmd, "--version"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
                **hidden_console_process_kwargs(),
            )
        except Exception:
            continue
        if int(probe.returncode) == 0:
            return git_cmd
    return ""


def current_platform_key() -> str:
    if os.name == "nt":
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    return "other"


def platform_settings_root() -> Path:
    if current_platform_key() == "windows":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    xdg_config = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg_config:
        return Path(xdg_config).expanduser()
    return Path.home() / ".config"


def platform_lock_root_path(app_slug: str) -> Path:
    if current_platform_key() == "windows":
        return Path(os.environ.get("TEMP", str(Path.home() / "AppData" / "Local" / "Temp")))
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR", "").strip()
    if xdg_runtime:
        return Path(xdg_runtime).expanduser()
    xdg_cache = os.environ.get("XDG_CACHE_HOME", "").strip()
    if xdg_cache:
        return Path(xdg_cache).expanduser() / app_slug
    return Path.home() / ".cache" / app_slug


def resolve_settings_dir(root: Path, settings_filename: str) -> Path:
    preferred = root / APP_SLUG
    if preferred.exists():
        return preferred
    for legacy_slug in LEGACY_APP_SLUGS:
        legacy_dir = root / legacy_slug
        if (legacy_dir / settings_filename).exists():
            return legacy_dir
    for legacy_slug in LEGACY_APP_SLUGS:
        legacy_dir = root / legacy_slug
        if legacy_dir.exists():
            return legacy_dir
    return preferred


def default_download_dir() -> Path:
    downloads = Path.home() / "Downloads"
    if downloads.exists() and downloads.is_dir():
        return downloads
    return Path.home()


def current_arch_markers() -> tuple[str, ...]:
    machine = platform.machine().strip().lower()
    mapping = {
        "x86_64": ("x86_64", "amd64"),
        "amd64": ("amd64", "x86_64"),
        "aarch64": ("aarch64", "arm64"),
        "arm64": ("arm64", "aarch64"),
    }
    return mapping.get(machine, (machine,) if machine else tuple())


@lru_cache(maxsize=1)
def linux_os_release() -> dict[str, str]:
    if current_platform_key() != "linux":
        return {}
    path = Path("/etc/os-release")
    if not path.exists():
        return {}
    data: dict[str, str] = {}
    try:
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip().upper()] = value.strip().strip('"').strip("'")
    except Exception:
        return {}
    return data


def is_debian_like_linux() -> bool:
    if current_platform_key() != "linux":
        return False
    release = linux_os_release()
    identity = " ".join(filter(None, [release.get("ID", ""), release.get("ID_LIKE", "")])).lower()
    return any(token in identity for token in ("debian", "ubuntu"))


def looks_like_sha256(value: str) -> bool:
    candidate = value.strip().lower()
    return bool(re.fullmatch(r"[0-9a-f]{64}", candidate))


def _show_startup_warning(message: str) -> None:
    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(None, message, APP_TITLE, 0x00000030)
            return
        except Exception:
            pass
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showwarning(APP_TITLE, message, parent=root)
            root.destroy()
            return
        except Exception:
            pass
    print(message, file=sys.stderr)


def _focus_existing_window() -> bool:
    if os.name != "nt":
        return False
    try:
        user32 = ctypes.windll.user32
        for title in LEGACY_WINDOW_TITLES:
            hwnd = user32.FindWindowW(None, title)
            if hwnd:
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
                return True
    except Exception:
        return False
    return False


def _acquire_single_instance_mutex() -> tuple[bool, Any | None]:
    if os.name == "nt":
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_mutex = kernel32.CreateMutexW
            create_mutex.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
            create_mutex.restype = ctypes.c_void_p
            handles: list[int] = []
            for mutex_name in SINGLE_INSTANCE_MUTEX_NAMES:
                handle = create_mutex(None, False, mutex_name)
                if not handle:
                    continue
                handles.append(int(handle))
                already_exists = ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS
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

    try:
        import fcntl  # type: ignore

        lock_root = platform_lock_root_path(APP_SLUG)
        lock_root.mkdir(parents=True, exist_ok=True)
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
        try:
            kernel32 = ctypes.windll.kernel32
            handles = handle if isinstance(handle, (list, tuple)) else [handle]
            for owned in handles:
                try:
                    kernel32.CloseHandle(ctypes.c_void_p(int(owned)))
                except Exception:
                    pass
        except Exception:
            pass
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
        self.settings_root = platform_settings_root()
        self._window_icon_photo = None
        self.appdata_dir = self._resolve_appdata_dir()
        self.settings_path = self.appdata_dir / "updater_settings.json"
        self.settings = self._load_settings()

        self._apply_icon()

        saved_source = str(self.settings.get("source", "")).strip()
        self.source_var = StringVar(value=saved_source or self._default_manifest_source())
        self.version_var = StringVar(value=CURRENT_VERSION)
        self.output_dir_var = StringVar(value=str(self.settings.get("output_dir", str(default_download_dir()))))
        self.status_var = StringVar(value="Ready.")
        self.latest_var = StringVar(value="Latest version: (not checked)")
        self.download_var = StringVar(value="Download URL: (not checked)")
        self.sha256_var = StringVar(value="SHA256: (not provided)")
        self.environment_var = StringVar(value="")
        self.compatibility_var = StringVar(value="Compatibility: not checked")
        self.require_https_manifest_var = BooleanVar(value=bool(self.settings.get("require_https_manifest", True)))
        self.require_https_download_var = BooleanVar(value=bool(self.settings.get("require_https_download", True)))
        self.require_sha256_var = BooleanVar(value=bool(self.settings.get("require_sha256_verification", True)))
        self.confirm_external_links_var = BooleanVar(value=bool(self.settings.get("confirm_external_links", True)))
        self.require_trusted_hosts_var = BooleanVar(value=bool(self.settings.get("require_trusted_update_hosts", True)))
        self.trusted_hosts_var = StringVar(value=str(self.settings.get("trusted_update_hosts", ", ".join(DEFAULT_TRUSTED_UPDATE_HOSTS))))
        self.accept_all_security_var = BooleanVar(
            value=all(
                [
                    bool(self.require_https_manifest_var.get()),
                    bool(self.require_https_download_var.get()),
                    bool(self.require_sha256_var.get()),
                    bool(self.confirm_external_links_var.get()),
                    bool(self.require_trusted_hosts_var.get()),
                ]
            )
        )
        self._suspend_security_traces = False

        self.last_manifest: dict[str, Any] | None = None
        self.last_download_url = ""
        self.last_release_url = ""
        self.last_latest = ""
        self.last_sha256 = ""
        self.last_download_block_reason = ""
        self.last_compatibility: dict[str, Any] | None = None
        self.checking = False
        self.downloading = False
        self._window_drag_offset: tuple[int, int] | None = None
        self.style: ttk.Style | None = None

        self._configure_styles()
        self._build_ui()
        self._bind_setting_traces()
        self._save_settings()
        self._refresh_environment_status()

    def _resolve_appdata_dir(self) -> Path:
        return resolve_settings_dir(self.settings_root, "updater_settings.json")

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
        png_candidates = [
            self.resource_dir / "assets" / "universal_file_utility_suite_preview.png",
            self.runtime_dir / "assets" / "universal_file_utility_suite_preview.png",
            self.script_dir / "assets" / "universal_file_utility_suite_preview.png",
        ]
        for candidate in png_candidates:
            if candidate.exists():
                try:
                    icon_image = tk.PhotoImage(file=str(candidate))
                    self._window_icon_photo = icon_image
                    self.root.iconphoto(True, icon_image)
                    return
                except Exception:
                    continue

    def _palette(self) -> dict[str, str]:
        return {
            "window_bg": "#EEF3F8",
            "surface_bg": "#F7FAFD",
            "card_bg": "#FFFFFF",
            "card_border": "#D4DEE8",
            "card_alt_bg": "#EAF0F6",
            "title_fg": "#0E2236",
            "text_fg": "#1B364B",
            "muted_fg": "#5D7387",
            "accent_bg": "#117D8E",
            "accent_active": "#1490A3",
            "accent_fg": "#F6FEFF",
            "soft_bg": "#E2F1F4",
            "soft_fg": "#0E4F59",
            "input_bg": "#FFFFFF",
            "input_fg": "#163247",
            "input_border": "#B7C6D4",
            "progress_bg": "#117D8E",
            "progress_trough": "#DDE7EF",
            "strip_bg": "#DCEAF3",
            "strip_fg": "#38566A",
            "status_bg": "#E8EEF5",
            "status_fg": "#244257",
        }

    def _configure_styles(self) -> None:
        palette = self._palette()
        self.root.configure(bg=palette["window_bg"])
        self.style = ttk.Style(self.root)
        if "clam" in set(self.style.theme_names()):
            self.style.theme_use("clam")

        self.style.configure(".", background=palette["window_bg"], foreground=palette["text_fg"], font=("Segoe UI", 10))
        self.style.configure("TFrame", background=palette["window_bg"])
        self.style.configure("TLabel", background=palette["window_bg"], foreground=palette["text_fg"])
        self.style.configure(
            "TButton",
            background=palette["card_bg"],
            foreground=palette["text_fg"],
            borderwidth=1,
            focusthickness=0,
            padding=(12, 7),
        )
        self.style.map("TButton", background=[("active", palette["card_alt_bg"])])
        self.style.configure("Updater.TFrame", background=palette["window_bg"])
        self.style.configure(
            "UpdaterCard.TFrame",
            background=palette["card_bg"],
            borderwidth=1,
            relief="solid",
            bordercolor=palette["card_border"],
        )
        self.style.configure(
            "UpdaterHero.TFrame",
            background=palette["card_bg"],
            borderwidth=1,
            relief="solid",
            bordercolor=palette["card_border"],
        )
        self.style.configure("UpdaterStrip.TFrame", background=palette["strip_bg"], borderwidth=1, relief="solid", bordercolor=palette["card_border"])
        self.style.configure("UpdaterStrip.TLabel", background=palette["strip_bg"], foreground=palette["strip_fg"], font=("Segoe UI Semibold", 8))
        self.style.configure("UpdaterTitle.TLabel", background=palette["card_bg"], foreground=palette["title_fg"], font=("Segoe UI Semibold", 17))
        self.style.configure("UpdaterSummary.TLabel", background=palette["card_bg"], foreground=palette["muted_fg"], font=("Segoe UI", 10))
        self.style.configure("UpdaterMetaValue.TLabel", background=palette["card_bg"], foreground=palette["title_fg"], font=("Segoe UI Semibold", 13))
        self.style.configure("UpdaterMetaLabel.TLabel", background=palette["card_bg"], foreground=palette["muted_fg"], font=("Segoe UI", 9))
        self.style.configure("UpdaterSection.TLabel", background=palette["window_bg"], foreground=palette["title_fg"], font=("Segoe UI Semibold", 11))
        self.style.configure("UpdaterBadge.TLabel", background=palette["soft_bg"], foreground=palette["soft_fg"], font=("Segoe UI Semibold", 9), padding=(8, 4))
        self.style.configure("UpdaterHint.TLabel", background=palette["window_bg"], foreground=palette["muted_fg"], font=("Segoe UI", 9))
        self.style.configure("UpdaterValue.TLabel", background=palette["card_bg"], foreground=palette["text_fg"], font=("Segoe UI", 10))
        self.style.configure("UpdaterPrimary.TButton", background=palette["accent_bg"], foreground=palette["accent_fg"], borderwidth=1, padding=(14, 8))
        self.style.map("UpdaterPrimary.TButton", background=[("active", palette["accent_active"])], foreground=[("active", palette["accent_fg"])])
        self.style.configure("UpdaterQuiet.TButton", background=palette["card_bg"], foreground=palette["text_fg"], borderwidth=1, padding=(12, 8))
        self.style.map("UpdaterQuiet.TButton", background=[("active", palette["card_alt_bg"])])
        self.style.configure(
            "TLabelframe",
            background=palette["card_bg"],
            foreground=palette["text_fg"],
            borderwidth=1,
            relief="solid",
            bordercolor=palette["card_border"],
        )
        self.style.configure("TLabelframe.Label", background=palette["card_bg"], foreground=palette["title_fg"], font=("Segoe UI Semibold", 10))
        self.style.configure(
            "TEntry",
            fieldbackground=palette["input_bg"],
            foreground=palette["input_fg"],
            bordercolor=palette["input_border"],
        )
        self.style.configure(
            "Horizontal.TProgressbar",
            troughcolor=palette["progress_trough"],
            background=palette["progress_bg"],
            bordercolor=palette["card_border"],
            lightcolor=palette["progress_bg"],
            darkcolor=palette["progress_bg"],
        )

    def _bind_window_drag_widget(self, widget: tk.Misc) -> None:
        try:
            widget.configure(cursor="fleur")
        except Exception:
            pass

        widget.bind("<ButtonPress-1>", self._begin_window_drag, add="+")
        widget.bind("<B1-Motion>", self._perform_window_drag, add="+")
        widget.bind("<ButtonRelease-1>", self._end_window_drag, add="+")

    def _begin_window_drag(self, event) -> str:
        self._window_drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())
        return "break"

    def _perform_window_drag(self, event) -> str | None:
        if not self._window_drag_offset:
            return None
        offset_x, offset_y = self._window_drag_offset
        try:
            self.root.geometry(f"+{event.x_root - offset_x}+{event.y_root - offset_y}")
        except Exception:
            return None
        return "break"

    def _end_window_drag(self, _event=None) -> None:
        self._window_drag_offset = None

    def _download_dialog_profile(self, url: str) -> tuple[str, str, list[tuple[str, str]]]:
        lower = url.strip().lower()
        asset_name = Path(urllib.parse.urlparse(url).path).name
        if lower.endswith(".deb") or asset_name.lower().endswith(".deb"):
            return "Save update package as", ".deb", [("Debian package", "*.deb"), ("All files", "*.*")]
        if lower.endswith(".appimage") or asset_name.lower().endswith(".appimage"):
            return "Save update package as", ".AppImage", [("AppImage", "*.AppImage"), ("All files", "*.*")]
        if lower.endswith(".tar.gz") or asset_name.lower().endswith(".tar.gz"):
            return "Save update package as", ".tar.gz", [("Tar archive", "*.tar.gz"), ("All files", "*.*")]
        if lower.endswith(".zip") or asset_name.lower().endswith(".zip"):
            return "Save update package as", ".zip", [("Zip archive", "*.zip"), ("All files", "*.*")]
        return "Save update package as", ".exe", [("Installer", "*.exe"), ("All files", "*.*")]

    def _default_settings(self) -> dict[str, Any]:
        return {
            "require_https_manifest": True,
            "require_https_download": True,
            "require_sha256_verification": True,
            "confirm_external_links": True,
            "require_trusted_update_hosts": True,
            "trusted_update_hosts": ", ".join(DEFAULT_TRUSTED_UPDATE_HOSTS),
            "source": "",
            "output_dir": "",
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
        self.settings["require_trusted_update_hosts"] = bool(self.require_trusted_hosts_var.get())
        self.settings["trusted_update_hosts"] = str(self.trusted_hosts_var.get()).strip() or ", ".join(DEFAULT_TRUSTED_UPDATE_HOSTS)
        self.settings["source"] = str(self.source_var.get()).strip()
        self.settings["output_dir"] = str(self.output_dir_var.get()).strip()
        self.settings_path.write_text(json.dumps(self.settings, indent=2, ensure_ascii=False), encoding="utf-8")

    def _all_security_options_enabled(self) -> bool:
        return all(
            [
                bool(self.require_https_manifest_var.get()),
                bool(self.require_https_download_var.get()),
                bool(self.require_sha256_var.get()),
                bool(self.confirm_external_links_var.get()),
                bool(self.require_trusted_hosts_var.get()),
            ]
        )

    def _set_all_security_options(self, enabled: bool) -> None:
        self._suspend_security_traces = True
        try:
            self.require_https_manifest_var.set(enabled)
            self.require_https_download_var.set(enabled)
            self.require_sha256_var.set(enabled)
            self.confirm_external_links_var.set(enabled)
            self.require_trusted_hosts_var.set(enabled)
        finally:
            self._suspend_security_traces = False

    def _on_accept_all_changed(self, *_args: object) -> None:
        if self._suspend_security_traces:
            return
        enabled = bool(self.accept_all_security_var.get())
        self._set_all_security_options(enabled)
        self._save_settings()
        if enabled:
            self.status_var.set("All security options enabled.")
        else:
            self.status_var.set("Security options can now be customized individually.")

    def _on_security_option_changed(self, *_args: object) -> None:
        if self._suspend_security_traces:
            return
        all_enabled = self._all_security_options_enabled()
        self._suspend_security_traces = True
        try:
            if bool(self.accept_all_security_var.get()) != all_enabled:
                self.accept_all_security_var.set(all_enabled)
        finally:
            self._suspend_security_traces = False
        self._save_settings()

    def _apply_security_settings_clicked(self) -> None:
        self._save_settings()
        self._refresh_environment_status(self.last_manifest or {})
        enabled_count = sum(
            [
                bool(self.require_https_manifest_var.get()),
                bool(self.require_https_download_var.get()),
                bool(self.require_sha256_var.get()),
                bool(self.confirm_external_links_var.get()),
                bool(self.require_trusted_hosts_var.get()),
            ]
        )
        self.status_var.set(f"Security settings saved ({enabled_count}/5 enabled).")

    def _bind_setting_traces(self) -> None:
        self.require_https_manifest_var.trace_add("write", self._on_security_option_changed)
        self.require_https_download_var.trace_add("write", self._on_security_option_changed)
        self.require_sha256_var.trace_add("write", self._on_security_option_changed)
        self.confirm_external_links_var.trace_add("write", self._on_security_option_changed)
        self.require_trusted_hosts_var.trace_add("write", self._on_security_option_changed)
        self.accept_all_security_var.trace_add("write", self._on_accept_all_changed)

    def _default_manifest_source(self) -> str:
        # Default to the project GitHub repo so update checks work without local manifest setup.
        return DEFAULT_GITHUB_REPO_URL

    def _trusted_update_hosts(self) -> tuple[str, ...]:
        raw = str(self.trusted_hosts_var.get()).strip()
        return parse_trusted_host_patterns(raw or DEFAULT_TRUSTED_UPDATE_HOSTS)

    def _url_scheme(self, value: str) -> str:
        return urllib.parse.urlparse(value.strip()).scheme.lower()

    def _validate_web_url(self, value: str, require_https: bool) -> tuple[bool, str]:
        scheme = self._url_scheme(value)
        if scheme not in {"http", "https"}:
            return False, f"Unsupported URL scheme '{scheme or '(none)'}'."
        if require_https and scheme != "https":
            return False, "HTTPS is required by current security settings."
        return True, ""

    def _validate_trusted_update_url(self, value: str) -> tuple[bool, str]:
        if not bool(self.require_trusted_hosts_var.get()):
            return True, ""
        return validate_trusted_remote_url(value, self._trusted_update_hosts())

    def _environment_snapshot(self) -> dict[str, Any]:
        return build_environment_snapshot(
            app_title=APP_TITLE,
            app_version=CURRENT_VERSION,
            settings_dir=self.appdata_dir,
            runtime_dir=self.runtime_dir,
            script_dir=self.script_dir,
            resource_dir=self.resource_dir,
            backend_paths={},
            settings={
                "source": str(self.source_var.get()).strip(),
                "require_https_manifest": bool(self.require_https_manifest_var.get()),
                "require_https_download": bool(self.require_https_download_var.get()),
                "require_sha256_verification": bool(self.require_sha256_var.get()),
                "confirm_external_links": bool(self.confirm_external_links_var.get()),
                "require_trusted_update_hosts": bool(self.require_trusted_hosts_var.get()),
                "trusted_update_hosts": list(self._trusted_update_hosts()),
            },
            popen_kwargs=hidden_console_process_kwargs(),
            extra={"mode": "updater"},
        )

    def _refresh_environment_status(self, manifest: dict[str, Any] | None = None) -> None:
        snapshot = self._environment_snapshot()
        os_details = snapshot.get("os", {})
        distro_name = str(os_details.get("distribution_name", "")).strip()
        os_name = distro_name or f"{os_details.get('system', 'Unknown')} {os_details.get('release', '')}".strip()
        support = snapshot.get("support", {})
        support_status = {
            "supported": "Supported baseline",
            "best_effort": "Best-effort baseline",
            "unsupported": "Needs attention",
        }.get(str(support.get("status", "")).strip().lower(), "Unknown baseline")
        self.environment_var.set(f"Environment: {os_name} | {os_details.get('architecture', 'unknown')} | {support_status}")

        compatibility = evaluate_manifest_compatibility(snapshot, manifest or {})
        self.last_compatibility = compatibility
        messages = [str(item).strip() for item in compatibility.get("messages", []) if str(item).strip()]
        label = {
            "compatible": "Compatibility: update allowed",
            "unsupported": "Compatibility: update not targeted to this environment",
            "unknown": "Compatibility: manifest does not declare environment rules",
        }.get(str(compatibility.get("status", "")).strip().lower(), "Compatibility: unknown")
        if messages:
            label = f"{label} | {messages[0]}"
        self.compatibility_var.set(label)

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

    def _fetch_text_url(self, url: str, timeout: int = 18) -> str:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": UPDATER_USER_AGENT,
                "Accept": "application/vnd.github+json, application/json;q=0.9, text/plain;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")

    def _fetch_json_url(self, url: str, timeout: int = 18) -> Any:
        payload = self._fetch_text_url(url, timeout=timeout)
        return json.loads(payload)

    def _extract_github_repo_spec(self, source: str) -> str:
        def normalize_repo_part(repo: str) -> str:
            value = repo.strip()
            if value.lower().endswith(".git"):
                value = value[:-4]
            return value

        value = source.strip()
        if not value:
            return ""
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
            return value
        if not value.lower().startswith(("http://", "https://")):
            return ""
        parsed = urllib.parse.urlparse(value)
        host = parsed.netloc.lower()
        parts = [segment for segment in parsed.path.split("/") if segment]
        if host in {"api.github.com"}:
            # Example: /repos/<owner>/<repo>/...
            if len(parts) >= 3 and parts[0].lower() == "repos":
                return f"{parts[1]}/{normalize_repo_part(parts[2])}"
            return ""
        if host in {"github.com", "www.github.com"}:
            if len(parts) >= 2:
                return f"{parts[0]}/{normalize_repo_part(parts[1])}"
        return ""

    def _latest_tag_from_git_remote(self, remote_url: str) -> str:
        git_cmd = resolve_git_executable()
        if not git_cmd:
            return ""
        try:
            result = subprocess.run(
                [git_cmd, "ls-remote", "--tags", "--refs", remote_url],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
                **hidden_console_process_kwargs(),
            )
        except Exception:
            return ""
        if int(result.returncode) != 0:
            return ""
        tags: list[str] = []
        for raw in result.stdout.splitlines():
            line = raw.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            ref = parts[1]
            prefix = "refs/tags/"
            if not ref.startswith(prefix):
                continue
            tag_name = ref[len(prefix) :].strip()
            if tag_name:
                tags.append(tag_name)
        if not tags:
            return ""
        return max(tags, key=lambda tag: (version_tuple(tag), tag))

    def _select_release_asset(self, assets: list[dict[str, Any]]) -> tuple[str, str]:
        normalized: list[tuple[str, str, str]] = []
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "").strip()
            url = str(asset.get("browser_download_url") or "").strip()
            if not name or not url:
                continue
            lower = name.lower()
            if lower.endswith((".sha256", ".sha256sum", ".sha256.txt", ".checksums", ".checksum", ".sig")):
                continue
            normalized.append((lower, name, url))
        if not normalized:
            return "", ""

        def is_primary_app_asset(lower: str) -> bool:
            normalized_name = lower.replace("_", "-")
            return (
                "updater" not in lower
                and (
                    "universalconversionhub" in lower
                    or "universal-conversion-hub" in normalized_name
                    or "hcb" in lower
                    or "universalfileutilitysuite" in lower
                )
            )

        platform_key = current_platform_key()
        arch_markers = current_arch_markers()

        if platform_key == "linux":
            priority_checks: list[Any] = []
            if is_debian_like_linux():
                priority_checks.extend(
                    [
                        lambda lower: lower.endswith(".deb") and is_primary_app_asset(lower) and any(marker in lower for marker in arch_markers),
                        lambda lower: lower.endswith(".deb") and is_primary_app_asset(lower),
                    ]
                )
            priority_checks.extend(
                [
                    lambda lower: lower.endswith(".appimage") and "linux" in lower and is_primary_app_asset(lower) and any(marker in lower for marker in arch_markers),
                    lambda lower: lower.endswith(".tar.gz") and "linux" in lower and is_primary_app_asset(lower) and any(marker in lower for marker in arch_markers),
                    lambda lower: lower.endswith(".appimage") and "linux" in lower and is_primary_app_asset(lower),
                    lambda lower: lower.endswith(".tar.gz") and "linux" in lower and is_primary_app_asset(lower),
                    lambda lower: "linux" in lower and is_primary_app_asset(lower),
                    lambda lower: lower.endswith(".deb") and is_primary_app_asset(lower),
                    lambda lower: lower.endswith((".appimage", ".tar.gz", ".deb")) and is_primary_app_asset(lower),
                    lambda lower: is_primary_app_asset(lower) and not lower.endswith(".exe"),
                    lambda _lower: True,
                ]
            )
        else:
            priority_checks = [
                lambda lower: lower.endswith(".exe") and "setup" in lower,
                lambda lower: lower.endswith(".exe") and is_primary_app_asset(lower),
                lambda lower: lower.endswith(".exe") and "updater" not in lower,
                lambda lower: lower.endswith(".exe"),
                lambda _lower: True,
            ]
        for rule in priority_checks:
            for lower_name, name, url in normalized:
                if rule(lower_name):
                    return name, url
        return "", ""

    def _find_sha256_in_text(self, text: str, target_name: str = "") -> str:
        target_lower = target_name.strip().lower()
        first_hash = ""
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            hashes = re.findall(r"\b[0-9a-fA-F]{64}\b", line)
            if not hashes:
                continue
            candidate = hashes[0].lower()
            if target_lower and target_lower in line.lower():
                return candidate
            if not first_hash:
                first_hash = candidate
        return first_hash

    def _extract_sha256_from_release(self, notes: str, assets: list[dict[str, Any]], target_name: str) -> str:
        from_notes = self._find_sha256_in_text(notes, target_name=target_name)
        if looks_like_sha256(from_notes):
            return from_notes

        checksum_assets: list[str] = []
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "").strip().lower()
            url = str(asset.get("browser_download_url") or "").strip()
            if not name or not url:
                continue
            if (
                name.endswith(".sha256")
                or name.endswith(".sha256.txt")
                or "sha256" in name
                or "checksum" in name
                or "checksums" in name
            ):
                checksum_assets.append(url)

        for checksum_url in checksum_assets:
            try:
                content = self._fetch_text_url(checksum_url, timeout=18)
            except Exception:
                continue
            parsed = self._find_sha256_in_text(content, target_name=target_name)
            if looks_like_sha256(parsed):
                return parsed
        return ""

    def _read_github_release_manifest(self, repo_spec: str) -> dict[str, Any]:
        api_url = f"https://api.github.com/repos/{repo_spec}/releases/latest"
        allow, reason = self._validate_web_url(api_url, require_https=bool(self.require_https_manifest_var.get()))
        if not allow:
            raise RuntimeError(f"GitHub API URL blocked by security settings.\n{reason}")
        allow_host, host_reason = self._validate_trusted_update_url(api_url)
        if not allow_host:
            raise RuntimeError(f"GitHub API URL blocked by security settings.\n{host_reason}")

        release: dict[str, Any]
        try:
            response_data = self._fetch_json_url(api_url, timeout=20)
            if not isinstance(response_data, dict):
                raise RuntimeError("GitHub release response is not a JSON object.")
            release = response_data
        except urllib.error.HTTPError as exc:
            if int(getattr(exc, "code", 0)) != 404:
                raise
            release = {}

        if release:
            latest = str(release.get("tag_name") or release.get("name") or "").strip()
            if not latest:
                raise RuntimeError("GitHub release is missing tag_name/name.")
            notes = str(release.get("body") or "").strip()
            raw_assets = release.get("assets")
            assets = raw_assets if isinstance(raw_assets, list) else []
            asset_name, download_url = self._select_release_asset(assets)
            sha256_value = self._extract_sha256_from_release(notes, assets, asset_name)
            release_url = str(release.get("html_url") or "").strip()
            if not download_url and release_url:
                notes = (
                    f"{notes}\n\nNo direct installer asset was detected in the latest release.\n"
                    f"Use the release page: {release_url}"
                ).strip()
            return {
                "latest_version": latest,
                "download_url": download_url,
                "notes": notes,
                "sha256": sha256_value,
                "release_url": release_url,
                "source_kind": "github_release",
                "repo": repo_spec,
                "asset_name": asset_name,
            }

        raw_candidates = [
            f"https://raw.githubusercontent.com/{repo_spec}/main/update_manifest.json",
            f"https://raw.githubusercontent.com/{repo_spec}/main/update_manifest.example.json",
            f"https://raw.githubusercontent.com/{repo_spec}/master/update_manifest.json",
            f"https://raw.githubusercontent.com/{repo_spec}/master/update_manifest.example.json",
        ]
        for raw_url in raw_candidates:
            try:
                allow_raw, reason_raw = self._validate_web_url(raw_url, require_https=bool(self.require_https_manifest_var.get()))
                if not allow_raw:
                    continue
                allow_raw_host, _raw_host_reason = self._validate_trusted_update_url(raw_url)
                if not allow_raw_host:
                    continue
                raw_manifest = self._fetch_json_url(raw_url, timeout=18)
                if not isinstance(raw_manifest, dict):
                    continue
                latest = str(raw_manifest.get("latest_version") or raw_manifest.get("version") or "").strip()
                if not latest:
                    continue
                fallback_manifest = dict(raw_manifest)
                fallback_manifest.setdefault("source_kind", "github_manifest_file")
                fallback_manifest.setdefault("repo", repo_spec)
                fallback_manifest.setdefault("notes", "")
                fallback_manifest["notes"] = (
                    f"{str(fallback_manifest.get('notes') or '').strip()}\n\n"
                    f"Loaded from repository manifest: {raw_url}"
                ).strip()
                return fallback_manifest
            except Exception:
                continue

        tags_url = f"https://api.github.com/repos/{repo_spec}/tags?per_page=1"
        allow_tags, reason_tags = self._validate_web_url(tags_url, require_https=bool(self.require_https_manifest_var.get()))
        if not allow_tags:
            raise RuntimeError(f"GitHub tags URL blocked by security settings.\n{reason_tags}")
        allow_tags_host, tags_host_reason = self._validate_trusted_update_url(tags_url)
        if not allow_tags_host:
            raise RuntimeError(f"GitHub tags URL blocked by security settings.\n{tags_host_reason}")
        tags_data: Any = []
        try:
            tags_data = self._fetch_json_url(tags_url, timeout=18)
        except Exception:
            tags_data = []
        if isinstance(tags_data, list) and tags_data:
            first = tags_data[0] if isinstance(tags_data[0], dict) else {}
            latest = str(first.get("name") or "").strip()
            if latest:
                release_url = f"https://github.com/{repo_spec}/releases/tag/{urllib.parse.quote(latest)}"
                return {
                    "latest_version": latest,
                    "download_url": "",
                    "notes": (
                        f"Latest tag detected from GitHub API: {latest}\n"
                        "No direct release asset URL was detected automatically."
                    ),
                    "sha256": "",
                    "release_url": release_url,
                    "source_kind": "github_tag",
                    "repo": repo_spec,
                    "asset_name": "",
                }

        remote_tag = self._latest_tag_from_git_remote(f"https://github.com/{repo_spec}.git")
        if remote_tag:
            release_url = f"https://github.com/{repo_spec}/releases/tag/{urllib.parse.quote(remote_tag)}"
            return {
                "latest_version": remote_tag,
                "download_url": "",
                "notes": (
                    f"Latest tag detected via git remote: {remote_tag}\n"
                    "GitHub API/manifest data was unavailable."
                ),
                "sha256": "",
                "release_url": release_url,
                "source_kind": "github_git_remote_tag",
                "repo": repo_spec,
                "asset_name": "",
            }

        raise RuntimeError(
            "No usable update metadata found in this GitHub repository.\n"
            "Create a GitHub Release or provide update_manifest.json in the repo."
        )

    def _read_update_source(self, source: str) -> dict[str, Any]:
        repo_spec = self._extract_github_repo_spec(source)
        if repo_spec:
            return self._read_github_release_manifest(repo_spec)
        return self._read_manifest(source)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, style="Updater.TFrame", padding=14)
        outer.pack(fill="both", expand=True)

        drag_strip = ttk.Frame(outer, style="UpdaterStrip.TFrame", height=18)
        drag_strip.pack(fill="x", pady=(0, 8))
        drag_strip.pack_propagate(False)
        drag_label = ttk.Label(drag_strip, text="Drag Window", style="UpdaterStrip.TLabel", anchor="center")
        drag_label.pack(fill="both", expand=True)
        self._bind_window_drag_widget(drag_strip)
        self._bind_window_drag_widget(drag_label)

        hero = ttk.Frame(outer, style="UpdaterHero.TFrame", padding=(16, 14))
        hero.pack(fill="x")
        hero.columnconfigure(0, weight=1)

        intro = ttk.Frame(hero, style="UpdaterHero.TFrame")
        intro.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        ttk.Label(intro, text="Release Control", style="UpdaterBadge.TLabel").pack(anchor="w")
        ttk.Label(intro, text=APP_TITLE, style="UpdaterTitle.TLabel").pack(anchor="w", pady=(10, 0))
        ttk.Label(
            intro,
            text=(
                "Checks the canonical release surface, pulls metadata from a manifest or GitHub repo, "
                "and downloads the correct installer package for the current platform."
            ),
            style="UpdaterSummary.TLabel",
            wraplength=520,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        stat_rail = ttk.Frame(hero, style="UpdaterHero.TFrame")
        stat_rail.grid(row=0, column=1, sticky="ne")
        for value, label, pad in [
            (CURRENT_VERSION, "Canonical version", (0, 0)),
            ("GitHub + manifest aware", "Source support", (8, 0)),
            ("Windows + Linux", "Package targets", (8, 0)),
        ]:
            card = ttk.Frame(stat_rail, style="UpdaterCard.TFrame", padding=(12, 10))
            card.pack(fill="x", pady=pad)
            ttk.Label(card, text=value, style="UpdaterMetaValue.TLabel").pack(anchor="w")
            ttk.Label(card, text=label, style="UpdaterMetaLabel.TLabel").pack(anchor="w", pady=(3, 0))

        source_card = ttk.Frame(outer, style="UpdaterCard.TFrame", padding=(14, 12))
        source_card.pack(fill="x", pady=(10, 0))
        ttk.Label(source_card, text="Update source", style="UpdaterSection.TLabel").pack(anchor="w")
        ttk.Label(
            source_card,
            text="Use a manifest URL/file or point directly at a GitHub repository such as https://github.com/owner/repo.",
            style="UpdaterHint.TLabel",
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))
        source_row = ttk.Frame(source_card, style="UpdaterCard.TFrame")
        source_row.pack(fill="x")
        ttk.Entry(source_row, textvariable=self.source_var).pack(side="left", fill="x", expand=True)
        ttk.Button(source_row, text="Browse File", style="UpdaterQuiet.TButton", command=self._browse_manifest).pack(side="left", padx=(8, 0))

        release_card = ttk.Frame(outer, style="UpdaterCard.TFrame", padding=(14, 12))
        release_card.pack(fill="x", pady=(10, 0))
        ttk.Label(release_card, text="Release state", style="UpdaterSection.TLabel").pack(anchor="w")

        ver_row = ttk.Frame(release_card, style="UpdaterCard.TFrame")
        ver_row.pack(fill="x", pady=(8, 0))
        ttk.Label(ver_row, text="Current app version", style="UpdaterMetaLabel.TLabel").pack(side="left")
        ttk.Entry(ver_row, width=12, textvariable=self.version_var).pack(side="left", padx=(8, 14))
        ttk.Label(ver_row, textvariable=self.latest_var, style="UpdaterValue.TLabel").pack(side="left")

        dl_row = ttk.Frame(release_card, style="UpdaterCard.TFrame")
        dl_row.pack(fill="x", pady=(8, 0))
        ttk.Label(dl_row, textvariable=self.download_var, style="UpdaterValue.TLabel", wraplength=760, justify="left").pack(side="left", anchor="w")
        hash_row = ttk.Frame(release_card, style="UpdaterCard.TFrame")
        hash_row.pack(fill="x", pady=(6, 0))
        ttk.Label(hash_row, textvariable=self.sha256_var, style="UpdaterValue.TLabel", wraplength=760, justify="left").pack(side="left", anchor="w")
        env_row = ttk.Frame(release_card, style="UpdaterCard.TFrame")
        env_row.pack(fill="x", pady=(6, 0))
        ttk.Label(env_row, textvariable=self.environment_var, style="UpdaterValue.TLabel", wraplength=760, justify="left").pack(side="left", anchor="w")
        compatibility_row = ttk.Frame(release_card, style="UpdaterCard.TFrame")
        compatibility_row.pack(fill="x", pady=(6, 0))
        ttk.Label(compatibility_row, textvariable=self.compatibility_var, style="UpdaterValue.TLabel", wraplength=760, justify="left").pack(side="left", anchor="w")

        out_row = ttk.Frame(release_card, style="UpdaterCard.TFrame")
        out_row.pack(fill="x", pady=(10, 0))
        ttk.Label(out_row, text="Download folder", style="UpdaterMetaLabel.TLabel").pack(side="left")
        ttk.Entry(out_row, textvariable=self.output_dir_var).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(out_row, text="Browse", style="UpdaterQuiet.TButton", command=self._browse_output_dir).pack(side="left")
        ttk.Button(out_row, text="Open", style="UpdaterQuiet.TButton", command=self._open_output_dir).pack(side="left", padx=(8, 0))

        action_row = ttk.Frame(outer, style="Updater.TFrame")
        action_row.pack(fill="x", pady=(10, 0))
        ttk.Button(action_row, text="Check for Updates", style="UpdaterPrimary.TButton", command=self._check_updates_clicked).pack(side="left")
        ttk.Button(action_row, text="Download Update", style="UpdaterQuiet.TButton", command=self._download_update_clicked).pack(side="left", padx=(8, 0))
        ttk.Button(action_row, text="Open Download Link", style="UpdaterQuiet.TButton", command=self._open_download_link).pack(side="left", padx=(8, 0))

        security_frame = ttk.Labelframe(outer, text="Security Options")
        security_frame.pack(fill="x", pady=(10, 0))
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
        ttk.Checkbutton(
            security_frame,
            text="Restrict manifests and download URLs to trusted hosts",
            variable=self.require_trusted_hosts_var,
        ).pack(anchor="w", padx=8)
        trusted_hosts_row = ttk.Frame(security_frame)
        trusted_hosts_row.pack(fill="x", padx=8, pady=(4, 4))
        ttk.Label(trusted_hosts_row, text="Trusted hosts").pack(side="left")
        ttk.Entry(trusted_hosts_row, textvariable=self.trusted_hosts_var).pack(side="left", fill="x", expand=True, padx=(8, 0))
        security_action_row = ttk.Frame(security_frame)
        security_action_row.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Checkbutton(
            security_action_row,
            text="Accept All Security Options",
            variable=self.accept_all_security_var,
        ).pack(side="left")
        ttk.Button(
            security_action_row,
            text="Apply",
            command=self._apply_security_settings_clicked,
        ).pack(side="right")

        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=100, value=0)
        self.progress.pack(fill="x", pady=(10, 8))

        notes_card = ttk.Frame(outer, style="UpdaterCard.TFrame", padding=(14, 12))
        notes_card.pack(fill="both", expand=True, pady=(0, 0))
        ttk.Label(notes_card, text="Release notes", style="UpdaterSection.TLabel").pack(anchor="w")
        ttk.Label(
            notes_card,
            text="This panel shows release notes, fallback notices, and any blocking security reasons discovered during the update check.",
            style="UpdaterHint.TLabel",
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(4, 8))

        palette = self._palette()
        self.notes_box = tk.Text(
            notes_card,
            height=11,
            wrap="word",
            bg=palette["card_bg"],
            fg=palette["text_fg"],
            insertbackground=palette["text_fg"],
            highlightthickness=1,
            highlightbackground=palette["card_border"],
            relief="flat",
            padx=10,
            pady=10,
        )
        self.notes_box.pack(fill="both", expand=True)
        self.notes_box.insert("1.0", "Release notes will appear here after update check.")
        self.notes_box.configure(state="disabled")

        status_bar = ttk.Frame(outer, style="UpdaterCard.TFrame", padding=(12, 8))
        status_bar.pack(fill="x", pady=(10, 0))
        ttk.Label(status_bar, textvariable=self.status_var, style="UpdaterValue.TLabel").pack(anchor="w")

    def _browse_manifest(self) -> None:
        raw = filedialog.askopenfilename(
            title="Select update manifest JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if raw:
            self.source_var.set(raw)
            self._refresh_environment_status(self.last_manifest or {})

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
            allow_host, host_reason = self._validate_trusted_update_url(source)
            if not allow_host:
                raise RuntimeError(f"Manifest URL blocked by security settings.\n{host_reason}")
            payload = self._fetch_text_url(source, timeout=18)
            return json.loads(payload)
        path = Path(source).expanduser().resolve()
        if not path.exists():
            raise RuntimeError(f"Manifest file was not found:\n{path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _check_updates_clicked(self) -> None:
        if self.checking:
            return
        self._save_settings()
        self.checking = True
        self.status_var.set("Checking updates...")
        self.progress.configure(value=8)

        def worker() -> None:
            try:
                manifest = self._read_update_source(self.source_var.get())
                latest = str(manifest.get("latest_version") or manifest.get("version") or "").strip()
                download_url = str(manifest.get("download_url") or manifest.get("url") or "").strip()
                release_url = str(manifest.get("release_url") or "").strip()
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
                    else:
                        allow_host, host_reason = self._validate_trusted_update_url(download_url)
                        if not allow_host:
                            blocked_reason = f"Download URL blocked by security settings: {host_reason}"
                            download_url = ""

                current = self.version_var.get().strip() or CURRENT_VERSION
                newer = is_version_newer(latest, current)
                compatibility = evaluate_manifest_compatibility(self._environment_snapshot(), manifest)
                compatibility_messages = [str(item).strip() for item in compatibility.get("messages", []) if str(item).strip()]
                if compatibility_messages:
                    notes = "\n".join(filter(None, [notes, "Compatibility", *compatibility_messages]))

                def apply() -> None:
                    self.last_manifest = manifest
                    self.last_download_url = download_url
                    self.last_release_url = release_url
                    self.last_latest = latest
                    self.last_sha256 = sha256_value
                    self.last_download_block_reason = blocked_reason
                    self._refresh_environment_status(manifest)
                    self.latest_var.set(f"Latest version: {latest}")
                    self.download_var.set(f"Download URL: {download_url or '(not provided)'}")
                    self.sha256_var.set(f"SHA256: {sha256_value or '(not provided)'}")
                    combined_notes = notes or "(No release notes.)"
                    if release_url and not download_url:
                        combined_notes = f"{combined_notes}\n\nRelease page: {release_url}"
                    if blocked_reason:
                        combined_notes = f"{combined_notes}\n\n{blocked_reason}"
                    self._set_notes(combined_notes)
                    self.progress.configure(value=100)
                    if newer and bool(compatibility.get("allowed", True)):
                        self.status_var.set(f"Update available: {current} -> {latest}")
                        messagebox.showinfo(APP_TITLE, f"Update available.\n\nCurrent: {current}\nLatest: {latest}")
                    elif newer:
                        self.status_var.set(f"Update {latest} is not targeted to this environment.")
                        messagebox.showwarning(APP_TITLE, f"Update {latest} is available, but it is not marked as compatible with this environment.")
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
        url = self.last_download_url.strip() or self.last_release_url.strip()
        if not url:
            messagebox.showwarning(APP_TITLE, "No download URL is available yet. Run Check for Updates first.")
            return
        allow, reason = self._validate_web_url(url, require_https=bool(self.require_https_download_var.get()))
        if not allow:
            messagebox.showwarning(APP_TITLE, f"Cannot open download URL.\n\n{reason}\n\nURL: {url}")
            return
        allow_host, host_reason = self._validate_trusted_update_url(url)
        if not allow_host:
            messagebox.showwarning(APP_TITLE, f"Cannot open download URL.\n\n{host_reason}\n\nURL: {url}")
            return
        if bool(self.confirm_external_links_var.get()):
            go = messagebox.askyesno(APP_TITLE, f"Open this external link?\n\n{url}")
            if not go:
                self.status_var.set("Canceled opening external link.")
                return
        webbrowser.open(url)
        if self.last_download_url.strip():
            self.status_var.set("Opened download URL in browser.")
        else:
            self.status_var.set("Opened release page in browser.")

    def _download_update_clicked(self) -> None:
        if self.downloading:
            return
        if self.last_download_block_reason:
            messagebox.showwarning(APP_TITLE, f"Cannot download.\n\n{self.last_download_block_reason}")
            return
        url = self.last_download_url.strip()
        if not url:
            if self.last_release_url.strip():
                messagebox.showwarning(
                    APP_TITLE,
                    "No direct download asset was detected.\n\n"
                    "Use 'Open Download Link' to open the release page.",
                )
            else:
                messagebox.showwarning(APP_TITLE, "No download URL is available yet. Run Check for Updates first.")
            return
        allow_url, url_reason = self._validate_web_url(url, require_https=bool(self.require_https_download_var.get()))
        if not allow_url:
            messagebox.showwarning(APP_TITLE, f"Download URL blocked by security settings.\n\n{url_reason}\n\nURL: {url}")
            return
        allow_host, host_reason = self._validate_trusted_update_url(url)
        if not allow_host:
            messagebox.showwarning(APP_TITLE, f"Download URL blocked by security settings.\n\n{host_reason}\n\nURL: {url}")
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
        default_name = Path(parsed.path).name or f"{DEFAULT_UPDATE_DOWNLOAD_PREFIX}_{self.last_latest or 'latest'}"
        dialog_title, default_extension, filetypes = self._download_dialog_profile(url)
        target = filedialog.asksaveasfilename(
            title=dialog_title,
            initialdir=str(out_dir),
            initialfile=default_name,
            defaultextension=default_extension,
            filetypes=filetypes,
        )
        if not target:
            return

        target_path = Path(target)
        self.downloading = True
        self.progress.configure(value=0)
        self.status_var.set(f"Downloading update to {target_path.name}...")

        def worker() -> None:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UPDATER_USER_AGENT})
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


def _run_cli_mode() -> int | None:
    parser = argparse.ArgumentParser(add_help=True, prog=APP_SLUG)
    parser.add_argument("--version", action="store_true", help="Print updater version and exit.")
    parser.add_argument("--smoke-test", action="store_true", help="Run a headless updater probe and exit.")
    args, unknown = parser.parse_known_args()
    if unknown:
        parser.error(f"unrecognized arguments: {' '.join(unknown)}")
    if args.version:
        print(f"{APP_TITLE} {CURRENT_VERSION}")
        return 0
    if args.smoke_test:
        script_dir = Path(__file__).resolve().parent
        resource_dir = Path(getattr(sys, "_MEIPASS", script_dir))
        runtime_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else script_dir
        settings_root = platform_settings_root()
        appdata_dir = resolve_settings_dir(settings_root, "updater_settings.json")
        payload = build_environment_snapshot(
            app_title=APP_TITLE,
            app_version=CURRENT_VERSION,
            settings_dir=appdata_dir,
            runtime_dir=runtime_dir,
            script_dir=script_dir,
            resource_dir=resource_dir,
            backend_paths={},
            popen_kwargs=hidden_console_process_kwargs(),
            extra={"mode": "smoke-test"},
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    return None


def main() -> None:
    cli_status = _run_cli_mode()
    if cli_status is not None:
        raise SystemExit(cli_status)
    acquired, mutex_handle = _acquire_single_instance_mutex()
    if not acquired:
        _focus_existing_window()
        _show_startup_warning(f"{APP_TITLE} is already running.\n\nOnly one updater instance can be open at a time.")
        return
    root = tk.Tk()
    try:
        UpdaterApp(root)
        root.mainloop()
    finally:
        _release_single_instance_mutex(mutex_handle)


if __name__ == "__main__":
    main()
