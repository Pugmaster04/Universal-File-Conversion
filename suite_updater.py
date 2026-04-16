import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import ctypes
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import BooleanVar, StringVar, filedialog, messagebox, ttk


APP_TITLE = "Universal Conversion Hub (UCH) Updater"
# Versioning policy:
# - Major releases use X.0
# - Secondary feature releases use X.Y
# - Patch releases use X.Y.Z
CURRENT_VERSION = "0.7.3"
APP_SLUG = "UniversalConversionHubUCH"
LEGACY_APP_SLUGS = ("UniversalConversionHubHCB", "UniversalFileUtilitySuite")
SINGLE_INSTANCE_MUTEX_NAMES = (
    "Local\\UniversalConversionHubUCHUpdater_SingleInstanceMutex",
    "Local\\UniversalConversionHubHCBUpdater_SingleInstanceMutex",
    "Local\\UniversalFileUtilitySuiteUpdater_SingleInstanceMutex",
)
SINGLE_INSTANCE_LOCKFILE_NAME = "universal_conversion_hub_uch_updater.lock"
DEFAULT_GITHUB_REPO = "Pugmaster04/Universal-File-Conversion"
DEFAULT_GITHUB_REPO_URL = f"https://github.com/{DEFAULT_GITHUB_REPO}"
UPDATER_USER_AGENT = "UniversalConversionHubUCH-Updater/1.0"
DEFAULT_UPDATE_DOWNLOAD_PREFIX = "UniversalConversionHub_UCH_Update"
LEGACY_WINDOW_TITLES = (
    APP_TITLE,
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

        lock_root = Path(os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("TMPDIR") or "/tmp")
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
        self.local_appdata_root = Path(os.environ.get("LOCALAPPDATA", str(self.runtime_dir)))
        self.appdata_dir = self._resolve_appdata_dir()
        self.settings_path = self.appdata_dir / "updater_settings.json"
        self.settings = self._load_settings()

        self._apply_icon()

        saved_source = str(self.settings.get("source", "")).strip()
        self.source_var = StringVar(value=saved_source or self._default_manifest_source())
        self.version_var = StringVar(value=CURRENT_VERSION)
        self.output_dir_var = StringVar(value=str(self.settings.get("output_dir", str(self.runtime_dir))))
        self.status_var = StringVar(value="Ready.")
        self.latest_var = StringVar(value="Latest version: (not checked)")
        self.download_var = StringVar(value="Download URL: (not checked)")
        self.sha256_var = StringVar(value="SHA256: (not provided)")
        self.require_https_manifest_var = BooleanVar(value=bool(self.settings.get("require_https_manifest", True)))
        self.require_https_download_var = BooleanVar(value=bool(self.settings.get("require_https_download", True)))
        self.require_sha256_var = BooleanVar(value=bool(self.settings.get("require_sha256_verification", True)))
        self.confirm_external_links_var = BooleanVar(value=bool(self.settings.get("confirm_external_links", True)))
        self.accept_all_security_var = BooleanVar(
            value=all(
                [
                    bool(self.require_https_manifest_var.get()),
                    bool(self.require_https_download_var.get()),
                    bool(self.require_sha256_var.get()),
                    bool(self.confirm_external_links_var.get()),
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
        self.checking = False
        self.downloading = False
        self._window_drag_offset: tuple[int, int] | None = None

        self._build_ui()
        self._bind_setting_traces()
        self._save_settings()

    def _resolve_appdata_dir(self) -> Path:
        preferred = self.local_appdata_root / APP_SLUG
        if preferred.exists():
            return preferred
        for legacy_slug in LEGACY_APP_SLUGS:
            legacy_dir = self.local_appdata_root / legacy_slug
            if (legacy_dir / "updater_settings.json").exists():
                return legacy_dir
        for legacy_slug in LEGACY_APP_SLUGS:
            legacy_dir = self.local_appdata_root / legacy_slug
            if legacy_dir.exists():
                return legacy_dir
        return preferred

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

    def _default_settings(self) -> dict[str, Any]:
        return {
            "require_https_manifest": True,
            "require_https_download": True,
            "require_sha256_verification": True,
            "confirm_external_links": True,
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
            ]
        )

    def _set_all_security_options(self, enabled: bool) -> None:
        self._suspend_security_traces = True
        try:
            self.require_https_manifest_var.set(enabled)
            self.require_https_download_var.set(enabled)
            self.require_sha256_var.set(enabled)
            self.confirm_external_links_var.set(enabled)
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
        enabled_count = sum(
            [
                bool(self.require_https_manifest_var.get()),
                bool(self.require_https_download_var.get()),
                bool(self.require_sha256_var.get()),
                bool(self.confirm_external_links_var.get()),
            ]
        )
        self.status_var.set(f"Security settings saved ({enabled_count}/4 enabled).")

    def _bind_setting_traces(self) -> None:
        self.require_https_manifest_var.trace_add("write", self._on_security_option_changed)
        self.require_https_download_var.trace_add("write", self._on_security_option_changed)
        self.require_sha256_var.trace_add("write", self._on_security_option_changed)
        self.confirm_external_links_var.trace_add("write", self._on_security_option_changed)
        self.accept_all_security_var.trace_add("write", self._on_accept_all_changed)

    def _default_manifest_source(self) -> str:
        # Default to the project GitHub repo so update checks work without local manifest setup.
        return DEFAULT_GITHUB_REPO_URL

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
        commands: list[str] = ["git"]
        if os.name == "nt":
            commands.extend(
                [
                    r"C:\Program Files\Git\cmd\git.exe",
                    r"C:\Program Files\Git\bin\git.exe",
                ]
            )
        result = None
        for git_cmd in commands:
            try:
                probe = subprocess.run(
                    [git_cmd, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=8,
                    check=False,
                    **hidden_console_process_kwargs(),
                )
                if int(probe.returncode) != 0:
                    continue
                result = subprocess.run(
                    [git_cmd, "ls-remote", "--tags", "--refs", remote_url],
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                    **hidden_console_process_kwargs(),
                )
                break
            except Exception:
                continue
        if result is None:
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
            normalized.append((name.lower(), name, url))
        if not normalized:
            return "", ""

        priority_checks = [
            lambda lower: lower.endswith(".exe") and "setup" in lower,
            lambda lower: lower.endswith(".exe")
            and (
                "universalconversionhub" in lower
                or "hcb" in lower
                or "universalfileutilitysuite" in lower
            )
            and "updater" not in lower,
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
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        drag_strip = ttk.Frame(outer, height=18)
        drag_strip.pack(fill="x", pady=(0, 8))
        drag_strip.pack_propagate(False)
        drag_label = ttk.Label(drag_strip, text="Drag Window", anchor="center")
        drag_label.pack(fill="both", expand=True)
        self._bind_window_drag_widget(drag_strip)
        self._bind_window_drag_widget(drag_label)

        ttk.Label(outer, text=APP_TITLE, font=("Segoe UI Semibold", 14)).pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "Checks updates from a manifest URL/file or a GitHub repo URL "
                "(for example: https://github.com/owner/repo)."
            ),
            foreground="#4D5F76",
            wraplength=710,
        ).pack(anchor="w", pady=(2, 10))

        source_row = ttk.Frame(outer)
        source_row.pack(fill="x", pady=(0, 8))
        ttk.Label(source_row, text="Manifest URL/file or GitHub repo URL:").pack(side="left")
        ttk.Entry(source_row, textvariable=self.source_var).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(source_row, text="Browse File", command=self._browse_manifest).pack(side="left")

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
        security_action_row = ttk.Frame(security_frame)
        security_action_row.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Checkbutton(
            security_action_row,
            text="Accept All Security Options",
            variable=self.accept_all_security_var,
        ).pack(side="left")
        ttk.Button(
            security_action_row,
            text="OK",
            command=self._apply_security_settings_clicked,
        ).pack(side="right")

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

                current = self.version_var.get().strip() or CURRENT_VERSION
                newer = is_version_newer(latest, current)

                def apply() -> None:
                    self.last_manifest = manifest
                    self.last_download_url = download_url
                    self.last_release_url = release_url
                    self.last_latest = latest
                    self.last_sha256 = sha256_value
                    self.last_download_block_reason = blocked_reason
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
        url = self.last_download_url.strip() or self.last_release_url.strip()
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
        default_name = Path(parsed.path).name or f"{DEFAULT_UPDATE_DOWNLOAD_PREFIX}_{self.last_latest or 'latest'}.exe"
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


def main() -> None:
    acquired, mutex_handle = _acquire_single_instance_mutex()
    if not acquired:
        _focus_existing_window()
        return
    root = tk.Tk()
    try:
        UpdaterApp(root)
        root.mainloop()
    finally:
        _release_single_instance_mutex(mutex_handle)


if __name__ == "__main__":
    main()
