from __future__ import annotations

import os
import platform
import re
import subprocess
import sys
import time
import urllib.parse
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


DEFAULT_GITHUB_REPO = "Pugmaster04/Format-Foundry"
DEFAULT_GITHUB_REPO_URL = f"https://github.com/{DEFAULT_GITHUB_REPO}"
DEFAULT_TRUSTED_UPDATE_HOSTS = (
    "github.com",
    "api.github.com",
    "raw.githubusercontent.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "githubusercontent.com",
    "pugmaster04.github.io",
)

BACKEND_NAME_TO_KEY = {
    "FFmpeg": "ffmpeg",
    "FFprobe": "ffprobe",
    "Pandoc": "pandoc",
    "LibreOffice": "libreoffice",
    "7-Zip": "sevenzip",
    "ImageMagick": "imagemagick",
    "Aria2": "aria2",
}
BACKEND_KEY_TO_NAME = {value: key for key, value in BACKEND_NAME_TO_KEY.items()}

BACKEND_VERSION_PROBES: dict[str, tuple[list[str], str]] = {
    "ffmpeg": (["-version"], r"ffmpeg version\s+([^\s]+)"),
    "ffprobe": (["-version"], r"ffprobe version\s+([^\s]+)"),
    "pandoc": (["--version"], r"pandoc\s+([0-9][^\s]*)"),
    "libreoffice": (["--headless", "--version"], r"LibreOffice\s+([^\s]+)"),
    "sevenzip": ([], r"7-Zip(?: \[[^\]]+\])?\s+([0-9][^\s]*)"),
    "imagemagick": (["-version"], r"ImageMagick\s+([0-9][^\s]*)"),
    "aria2": (["--version"], r"aria2 version\s+([^\s]+)"),
}


def current_platform_key() -> str:
    if os.name == "nt":
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    return "other"


def current_architecture() -> str:
    machine = platform.machine().strip().lower()
    aliases = {
        "amd64": "x86_64",
        "x64": "x86_64",
        "x86-64": "x86_64",
        "arm64": "aarch64",
    }
    return aliases.get(machine, machine)


def current_arch_markers() -> tuple[str, ...]:
    machine = current_architecture()
    mapping = {
        "x86_64": ("x86_64", "amd64"),
        "aarch64": ("aarch64", "arm64"),
    }
    return mapping.get(machine, (machine,) if machine else tuple())


def version_tuple(value: str) -> tuple[int, ...]:
    parts = re.split(r"[^0-9]+", str(value).strip())
    return tuple(int(part) for part in parts if part.isdigit())


def version_meets_minimum(actual: str, minimum: str) -> bool:
    actual_tuple = version_tuple(actual)
    minimum_tuple = version_tuple(minimum)
    if not minimum_tuple:
        return True
    if not actual_tuple:
        return False
    width = max(len(actual_tuple), len(minimum_tuple))
    actual_tuple = actual_tuple + (0,) * (width - len(actual_tuple))
    minimum_tuple = minimum_tuple + (0,) * (width - len(minimum_tuple))
    return actual_tuple >= minimum_tuple


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


def parse_trusted_host_patterns(raw: str | Iterable[str] | None) -> tuple[str, ...]:
    if raw is None:
        return tuple(DEFAULT_TRUSTED_UPDATE_HOSTS)
    if isinstance(raw, str):
        tokens = re.split(r"[\s,;]+", raw)
    else:
        tokens = [str(item).strip() for item in raw]
    cleaned: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        value = token.strip().lower()
        if not value:
            continue
        if value not in seen:
            cleaned.append(value)
            seen.add(value)
    return tuple(cleaned)


def host_matches_pattern(host: str, pattern: str) -> bool:
    host_value = host.strip().lower().rstrip(".")
    pattern_value = pattern.strip().lower().rstrip(".")
    if not host_value or not pattern_value:
        return False
    if pattern_value.startswith("*."):
        suffix = pattern_value[2:]
        return host_value == suffix or host_value.endswith(f".{suffix}")
    if pattern_value.startswith("."):
        suffix = pattern_value[1:]
        return host_value == suffix or host_value.endswith(f".{suffix}")
    return host_value == pattern_value


def validate_trusted_remote_url(url: str, trusted_hosts: Iterable[str]) -> tuple[bool, str]:
    value = str(url).strip()
    if not value:
        return False, "No URL was provided."
    parsed = urllib.parse.urlparse(value)
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return False, "URL does not contain a hostname."
    patterns = parse_trusted_host_patterns(tuple(trusted_hosts))
    if not patterns:
        return False, "No trusted update hosts are configured."
    for pattern in patterns:
        if host_matches_pattern(host, pattern):
            return True, ""
    return False, f"Host '{host}' is not in the trusted update host allowlist."


def collect_os_details() -> dict[str, Any]:
    uname = platform.uname()
    linux_release = linux_os_release()
    platform_key = current_platform_key()
    distro_id = str(linux_release.get("ID", "")).strip().lower() if platform_key == "linux" else ""
    distro_version = str(linux_release.get("VERSION_ID", "")).strip() if platform_key == "linux" else ""
    distro_name = str(linux_release.get("PRETTY_NAME", "")).strip() if platform_key == "linux" else ""
    return {
        "platform_key": platform_key,
        "system": uname.system,
        "release": uname.release,
        "version": uname.version,
        "machine": uname.machine,
        "architecture": current_architecture(),
        "python_version": platform.python_version(),
        "distribution_id": distro_id,
        "distribution_version": distro_version,
        "distribution_name": distro_name,
    }


def _probe_backend_version(
    backend_key: str,
    path_value: str,
    popen_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    command_suffix, pattern = BACKEND_VERSION_PROBES.get(backend_key, (["--version"], r"([0-9][^\s]*)"))
    command = [path_value, *command_suffix]
    result: dict[str, Any] = {
        "detected": True,
        "path": path_value,
        "version": "",
        "raw": "",
        "error": "",
    }
    try:
        timeout_seconds = 3 if backend_key == "libreoffice" else 8
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            **(popen_kwargs or {}),
        )
    except Exception as exc:
        result["error"] = str(exc)
        return result
    output = "\n".join(part for part in [completed.stdout, completed.stderr] if part).strip()
    result["raw"] = output
    if output:
        match = re.search(pattern, output, flags=re.IGNORECASE)
        if match:
            result["version"] = str(match.group(1)).strip()
            return result
        first_line = output.splitlines()[0].strip()
        simple_match = re.search(r"\b([0-9]+(?:\.[0-9A-Za-z_-]+)+)\b", first_line)
        if simple_match:
            result["version"] = str(simple_match.group(1)).strip()
            return result
        result["error"] = "Version string not recognized."
        return result
    result["error"] = f"Version probe exited with code {completed.returncode} and no output."
    return result


def collect_backend_details(
    backend_paths: dict[str, str | None],
    popen_kwargs: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    for backend_key, path_value in backend_paths.items():
        value = str(path_value or "").strip()
        if not value or value == "Not found":
            details[backend_key] = {
                "detected": False,
                "path": "",
                "version": "",
                "raw": "",
                "error": "Not found",
            }
            continue
        details[backend_key] = _probe_backend_version(backend_key, value, popen_kwargs=popen_kwargs)
    return details


def evaluate_runtime_support(snapshot: dict[str, Any]) -> dict[str, Any]:
    os_details = snapshot.get("os", {}) if isinstance(snapshot, dict) else {}
    platform_key = str(os_details.get("platform_key", "")).lower()
    architecture = str(os_details.get("architecture", "")).lower()
    messages: list[str] = []
    status = "supported"

    if platform_key == "windows":
        if not version_meets_minimum(str(os_details.get("release", "")), "10"):
            status = "unsupported"
            messages.append("Windows 10 or newer is required for the supported Windows target.")
        else:
            messages.append("Windows runtime is within the supported baseline.")
    elif platform_key == "linux":
        distro_id = str(os_details.get("distribution_id", "")).lower()
        distro_version = str(os_details.get("distribution_version", ""))
        if architecture not in {"x86_64", "amd64"}:
            status = "best_effort"
            messages.append("Official Linux packaging is currently targeted at x86_64/amd64.")
        if distro_id == "ubuntu" and version_meets_minimum(distro_version, "24.04"):
            messages.append("Linux runtime matches the validated Ubuntu 24.04+ baseline.")
        elif distro_id in {"ubuntu", "debian"}:
            if status == "supported":
                status = "best_effort"
            messages.append("Debian-family Linux is likely compatible, but only Ubuntu 24.04 is currently validated.")
        else:
            if status == "supported":
                status = "best_effort"
            messages.append("Linux runtime is outside the explicitly validated distro baseline.")
    else:
        status = "unsupported"
        messages.append("This operating system is outside the supported desktop targets.")

    backend_details = snapshot.get("backends", {}) if isinstance(snapshot, dict) else {}
    missing = [BACKEND_KEY_TO_NAME.get(key, key) for key, data in backend_details.items() if not bool(data.get("detected"))]
    if missing:
        messages.append(f"Optional backends missing: {', '.join(sorted(missing))}.")

    return {
        "status": status,
        "messages": messages,
    }


def evaluate_manifest_compatibility(snapshot: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    compatibility = manifest.get("compatibility")
    if not isinstance(compatibility, dict):
        return {
            "status": "unknown",
            "allowed": True,
            "messages": ["Manifest does not declare platform compatibility metadata."],
        }

    os_details = snapshot.get("os", {}) if isinstance(snapshot, dict) else {}
    platform_key = str(os_details.get("platform_key", "")).lower()
    architecture = str(os_details.get("architecture", "")).lower()
    distro_id = str(os_details.get("distribution_id", "")).lower()
    backend_details = snapshot.get("backends", {}) if isinstance(snapshot, dict) else {}

    status = "compatible"
    allowed = True
    messages: list[str] = []

    platforms = [str(item).strip().lower() for item in compatibility.get("platforms", []) if str(item).strip()]
    if platforms and platform_key not in platforms:
        allowed = False
        status = "unsupported"
        messages.append(f"Update does not target this platform ({platform_key or 'unknown'}).")

    architectures = [str(item).strip().lower() for item in compatibility.get("architectures", []) if str(item).strip()]
    if architectures and architecture not in architectures:
        allowed = False
        status = "unsupported"
        messages.append(f"Update does not target this architecture ({architecture or 'unknown'}).")

    minimum_os_versions = compatibility.get("minimum_os_versions")
    if isinstance(minimum_os_versions, dict):
        candidates = []
        if platform_key == "linux" and distro_id:
            candidates.append(f"{platform_key}:{distro_id}")
        if platform_key:
            candidates.append(platform_key)
        candidates.append("default")
        for candidate in candidates:
            required_value = str(minimum_os_versions.get(candidate, "")).strip()
            if not required_value:
                continue
            actual_value = str(os_details.get("distribution_version") or os_details.get("release") or "")
            if not version_meets_minimum(actual_value, required_value):
                allowed = False
                status = "unsupported"
                messages.append(f"Update requires {candidate} version {required_value} or newer.")
            break

    minimum_backends = compatibility.get("minimum_backends")
    if isinstance(minimum_backends, dict):
        for backend_key, minimum_version in minimum_backends.items():
            detail = backend_details.get(str(backend_key), {})
            if not bool(detail.get("detected")):
                allowed = False
                status = "unsupported"
                messages.append(
                    f"Update expects backend {BACKEND_KEY_TO_NAME.get(str(backend_key), str(backend_key))} >= {minimum_version}, but it is not detected."
                )
                continue
            actual_version = str(detail.get("version", "")).strip()
            if actual_version and not version_meets_minimum(actual_version, str(minimum_version)):
                allowed = False
                status = "unsupported"
                messages.append(
                    f"Update expects backend {BACKEND_KEY_TO_NAME.get(str(backend_key), str(backend_key))} >= {minimum_version}, current version is {actual_version}."
                )

    if not messages:
        messages.append("Manifest compatibility rules allow this environment.")
    return {
        "status": status,
        "allowed": allowed,
        "messages": messages,
    }


def build_environment_snapshot(
    *,
    app_title: str,
    app_version: str,
    settings_dir: Path,
    runtime_dir: Path,
    script_dir: Path,
    resource_dir: Path,
    backend_paths: dict[str, str | None],
    settings: dict[str, Any] | None = None,
    popen_kwargs: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    backend_details = collect_backend_details(backend_paths, popen_kwargs=popen_kwargs)
    snapshot: dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "app": {
            "title": app_title,
            "version": app_version,
        },
        "os": collect_os_details(),
        "paths": {
            "settings_dir": str(settings_dir),
            "runtime_dir": str(runtime_dir),
            "runtime_dir_exists": runtime_dir.exists(),
            "script_dir": str(script_dir),
            "script_dir_exists": script_dir.exists(),
            "resource_dir": str(resource_dir),
            "resource_dir_exists": resource_dir.exists(),
        },
        "backends": backend_details,
    }
    if isinstance(settings, dict):
        snapshot["settings"] = settings
    if isinstance(extra, dict):
        snapshot["extra"] = extra
    snapshot["support"] = evaluate_runtime_support(snapshot)
    return snapshot
