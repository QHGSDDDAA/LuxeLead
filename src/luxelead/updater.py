"""Online update: fetch manifest, compare versions, download and apply updates."""

import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Callable, Optional, Tuple

from .update_progress import (
    ensure_powershell_progress_monitor,
    init_update_progress,
    progress_file_path,
)
from .version import DEFAULT_MANIFEST_URL, UPDATE_DEPLOY_TOKEN, VERSION


def parse_version(version_str: str) -> Tuple[int, ...]:
    match = re.search(r"(\d+(?:\.\d+)*)", version_str or "")
    if not match:
        return (0, 0, 0)
    parts = [int(part) for part in match.group(1).split(".")]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer_version(remote_version: str, local_version: str = VERSION) -> bool:
    return parse_version(remote_version) > parse_version(local_version)


def sha256_file(file_path: str) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def get_local_exe_sha256() -> str:
    if not getattr(sys, "frozen", False):
        return ""
    exe_path = get_executable_path()
    if not os.path.isfile(exe_path):
        return ""
    return sha256_file(exe_path)


def is_update_available(manifest: dict, local_version: str = VERSION) -> bool:
    """True when remote version is newer, or same version but build differs."""
    remote_version = manifest.get("version", "")
    if is_newer_version(remote_version, local_version):
        return True
    if parse_version(remote_version) != parse_version(local_version):
        return False
    package_type = (manifest.get("package_type") or "onefile").strip().lower()
    if package_type in ("onedir_zip", "onedir_patch"):
        return False
    remote_sha = (manifest.get("sha256") or "").strip().lower()
    local_sha = get_local_exe_sha256()
    return bool(remote_sha and local_sha and remote_sha != local_sha)


def get_manifest_url(config: Optional[dict] = None) -> str:
    if config:
        url = (config.get("update_manifest_url") or "").strip()
        if url:
            return url
    return DEFAULT_MANIFEST_URL


def get_manifest_auth(config: Optional[dict] = None) -> dict:
    token = UPDATE_DEPLOY_TOKEN
    if config:
        token = (config.get("update_deploy_token") or token).strip()
    if token:
        return {"DEPLOY-TOKEN": token}
    return {}


def _parse_github_release(data: dict) -> dict:\
    """Transform GitHub API release response into the internal manifest format."""\
    tag = data.get("tag_name", "").lstrip("v")\
    body = data.get("body") or ""\
    html_url = data.get("html_url") or ""\
    return {\
        "version": tag,\
        "display_version": f"V{tag}",\
        "release_notes": body,\
        "download_url": html_url,\
        "release_date": (data.get("published_at") or "")[:10],\
        "github_html_url": html_url,\
        "is_github_release": True,\
    }\
\

def fetch_manifest(
    url: Optional[str] = None,
    timeout: float = 15,
    config: Optional[dict] = None,
) -> dict:
    manifest_url = url or get_manifest_url(config)
    headers = {"User-Agent": f"LuxeLead/{VERSION}"}
    headers.update(get_manifest_auth(config))
    request = urllib.request.Request(manifest_url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    try:
        manifest = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as exc:
        preview = data[:120].decode("utf-8", "replace")
        raise ValueError(
            f"更新清单不是有效 JSON（服务器可能要求登录）: {preview}"
        ) from exc
    # GitHub API 格式特殊处理
    if manifest.get("tag_name"):
        manifest = _parse_github_release(manifest)
    for key in ("version", "display_version", "release_notes", "download_url"):
        if not manifest.get(key):
            raise ValueError(f"更新清单缺少必要字段: {key}")
    return manifest


def get_bundled_release_notes_path() -> str:
    if getattr(sys, "frozen", False):
        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(base_dir, "releases", "RELEASE_NOTES.md")


def load_local_release_notes() -> str:
    notes_path = get_bundled_release_notes_path()
    if os.path.isfile(notes_path):
        with open(notes_path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    return "（暂无版本说明）"


def get_download_headers(manifest: dict, config: Optional[dict] = None) -> dict:
    token = (manifest.get("download_token") or "").strip()
    if not token and config:
        token = (config.get("update_deploy_token") or UPDATE_DEPLOY_TOKEN).strip()
    elif not token:
        token = UPDATE_DEPLOY_TOKEN
    if token:
        return {"DEPLOY-TOKEN": token}
    return {}


def get_executable_path() -> str:
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.executable)
    return os.path.abspath(sys.argv[0])


def download_file(
    url: str,
    dest_path: str,
    progress_callback: Optional[Callable[[int, Optional[int]], None]] = None,
    timeout: float = 30,
    extra_headers: Optional[dict] = None,
) -> None:
    headers = {"User-Agent": f"LuxeLead/{VERSION}"}
    if extra_headers:
        headers.update(extra_headers)
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        total = response.headers.get("Content-Length")
        total_size = int(total) if total else None
        downloaded = 0
        chunk_size = 1024 * 256
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as handle:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total_size)


def verify_sha256(file_path: str, expected_hash: str) -> bool:
    if not expected_hash:
        return True
    return sha256_file(file_path) == expected_hash.strip().lower()


def _batch_progress_cmd(update_dir: str, percent: int, message: str) -> str:
    safe_message = message.replace('"', "'")
    return f'call :write_progress {percent} "{safe_message}"'


def _batch_progress_helpers(update_dir: str) -> list[str]:
    prog = os.path.join(update_dir, "progress.txt")
    return [
        ":write_progress",
        f'set "PROG={prog}"',
        '> "%PROG%" echo %~1',
        '>> "%PROG%" echo %~2',
        "exit /b 0",
    ]


def _batch_launch_monitor_cmd(update_dir: str) -> str:
    ps1_path = os.path.join(update_dir, "progress_monitor.ps1")
    progress_file = progress_file_path(update_dir)
    return (
        f'start "LuxeLeadUpdateProgress" powershell.exe -NoProfile -ExecutionPolicy Bypass '
        f'-File "{ps1_path}" -ProgressFile "{progress_file}"'
    )


def _robocopy_install_cmd(
    copy_from: str,
    target_dir: str,
    update_dir: str,
    backup_dir: str = "",
    backup_internal: str = "",
    internal_dir: str = "",
) -> list[str]:
    restore_lines = []
    if backup_dir:
        restore_lines.append(f'  if exist "{backup_dir}" move /Y "{backup_dir}" "{target_dir}"')
    if backup_internal and internal_dir:
        restore_lines.extend(
            [
                f'  if exist "{internal_dir}" rd /s /q "{internal_dir}" 2>nul',
                f'  if exist "{backup_internal}" move /Y "{backup_internal}" "{internal_dir}"',
            ]
        )
    return [
        f'robocopy "{copy_from}" "{target_dir}" /E /IS /IT /R:2 /W:2 /NFL /NDL /NJH /NJS /nc /ns /np',
        "if errorlevel 8 (",
        _batch_progress_cmd(update_dir, -1, "安装新版本失败，正在恢复..."),
        *restore_lines,
        "  exit /b 1",
        ")",
    ]


def _start_update_monitor_and_batch(update_dir: str, script_path: str, script: str) -> None:
    os.makedirs(update_dir, exist_ok=True)
    ensure_powershell_progress_monitor(update_dir)
    init_update_progress(update_dir, 0, "准备安装更新...")
    with open(script_path, "w", encoding="utf-8", newline="\r\n") as handle:
        handle.write(script)
    subprocess.Popen(
        ["cmd.exe", "/c", script_path],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
        cwd=update_dir,
    )


def apply_windows_update(
    new_exe_path: str,
    current_exe_path: Optional[str] = None,
    parent_pid: Optional[int] = None,
    manifest: Optional[dict] = None,
) -> None:
    package_type = (manifest or {}).get("package_type", "onefile")
    if package_type in ("onedir_zip", "onedir_patch"):
        apply_windows_onedir_update(new_exe_path, manifest or {}, current_exe_path, parent_pid)
        return

    if os.name != "nt":
        raise RuntimeError("自动更新目前仅支持 Windows 客户端")

    current_exe = os.path.abspath(current_exe_path or get_executable_path())
    new_exe = os.path.abspath(new_exe_path)
    if not os.path.isfile(new_exe):
        raise FileNotFoundError(f"更新文件不存在: {new_exe}")

    pid = parent_pid or os.getpid()
    update_dir = os.path.join(os.path.dirname(current_exe), "_luxelead_updates")
    os.makedirs(update_dir, exist_ok=True)
    script_path = os.path.join(update_dir, "apply_update.bat")
    backup_exe = current_exe + ".bak"

    script = "\r\n".join(
        [
            "@echo off",
            "chcp 65001 >nul",
            "setlocal",
            _batch_progress_cmd(update_dir, 5, "等待当前程序退出..."),
            f":wait_loop",
            f'tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul',
            "if not errorlevel 1 (",
            "  ping 127.0.0.1 -n 2 >nul",
            "  goto wait_loop",
            ")",
            "ping 127.0.0.1 -n 3 >nul",
            _batch_progress_cmd(update_dir, 8, "正在打开更新进度窗口..."),
            _batch_launch_monitor_cmd(update_dir),
            "ping 127.0.0.1 -n 5 >nul",
            _batch_progress_cmd(update_dir, 20, "正在备份当前版本..."),
            f'if exist "{current_exe}" copy /Y "{current_exe}" "{backup_exe}" >nul',
            _batch_progress_cmd(update_dir, 50, "正在安装新版本..."),
            f'copy /Y "{new_exe}" "{current_exe}"',
            "if errorlevel 1 (",
            _batch_progress_cmd(update_dir, -1, "安装失败，正在恢复备份..."),
            f'  if exist "{backup_exe}" copy /Y "{backup_exe}" "{current_exe}" >nul',
            "  exit /b 1",
            ")",
            _batch_progress_cmd(update_dir, 90, "正在启动新版本..."),
            f'start "" "{current_exe}"',
            _batch_progress_cmd(update_dir, 100, "更新完成"),
            f'del /F /Q "{new_exe}" 2>nul',
            'del /F /Q "%~f0" 2>nul',
            *_batch_progress_helpers(update_dir),
        ]
    )
    _start_update_monitor_and_batch(update_dir, script_path, script)


def _resolve_install_dir(app_dir: str, app_folder: str) -> str:
    folder = (app_folder or "").strip().replace("\\", "/")
    if folder in ("", ".", "./"):
        return app_dir
    if os.path.basename(app_dir).lower() == folder.lower():
        return app_dir
    return os.path.join(app_dir, folder)


def resolve_update_package(manifest: dict, local_version: str = VERSION) -> dict:
    """Pick incremental patch when available, otherwise full zip."""
    selected = dict(manifest)
    for patch in manifest.get("patches") or []:
        base_version = (patch.get("base_version") or "").strip()
        download_url = (patch.get("download_url") or "").strip()
        if base_version == local_version and download_url:
            selected.update(patch)
            selected["package_type"] = patch.get("package_type") or "onedir_patch"
            selected["_update_mode"] = "patch"
            return selected
    selected["package_type"] = manifest.get("package_type") or "onedir_zip"
    selected["_update_mode"] = "full"
    return selected


def apply_windows_onedir_update(
    zip_path: str,
    manifest: dict,
    current_exe_path: Optional[str] = None,
    parent_pid: Optional[int] = None,
) -> None:
    if os.name != "nt":
        raise RuntimeError("自动更新目前仅支持 Windows 客户端")

    current_exe = os.path.abspath(current_exe_path or get_executable_path())
    app_dir = os.path.dirname(current_exe)
    pid = parent_pid or os.getpid()
    zip_path = os.path.abspath(zip_path)
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(f"更新包不存在: {zip_path}")

    is_patch = (manifest.get("package_type") or "").strip().lower() == "onedir_patch"
    app_folder = manifest.get("app_folder", ".")
    launch_exe = manifest.get("launch_exe") or os.path.basename(current_exe)
    staging_dir = os.path.join(app_dir, "_luxelead_updates", "staging")
    update_dir = os.path.join(app_dir, "_luxelead_updates")
    target_dir = _resolve_install_dir(app_dir, app_folder)
    zip_root = (manifest.get("zip_root") or app_folder or "").strip().replace("\\", "/")
    if zip_root in ("", ".", "./"):
        copy_from = staging_dir
    else:
        copy_from = os.path.join(staging_dir, zip_root)
    in_place = os.path.normcase(target_dir) == os.path.normcase(app_dir)
    backup_internal = os.path.join(target_dir, "_internal.bak")
    backup_dir = target_dir + ".bak" if not in_place else ""
    old_onefile = current_exe + ".old"
    target_launch = os.path.join(target_dir, launch_exe)
    internal_dir = os.path.join(target_dir, "_internal")

    os.makedirs(update_dir, exist_ok=True)

    ps_expand = (
        f"Expand-Archive -LiteralPath '{zip_path}' "
        f"-DestinationPath '{staging_dir}' -Force"
    )

    pre_copy_lines = []
    if not is_patch:
        pre_copy_lines = [
            f'if exist "{old_onefile}" del /F /Q "{old_onefile}"',
            f'if exist "{current_exe}" move /Y "{current_exe}" "{old_onefile}"',
        ]
        if in_place:
            pre_copy_lines.extend(
                [
                    f'if exist "{backup_internal}" rd /s /q "{backup_internal}"',
                    f'if exist "{internal_dir}" move /Y "{internal_dir}" "{backup_internal}"',
                ]
            )
        else:
            pre_copy_lines.extend(
                [
                    f'if exist "{backup_dir}" rd /s /q "{backup_dir}"',
                    f'if exist "{target_dir}" move /Y "{target_dir}" "{backup_dir}"',
                    f'if not exist "{target_dir}" mkdir "{target_dir}"',
                ]
            )

    expand_message = "正在解压增量更新包..." if is_patch else "正在解压更新包，请稍候..."
    install_message = "正在应用增量更新..." if is_patch else "正在安装新版本..."

    script_lines = [
        "@echo off",
        "chcp 65001 >nul",
        "setlocal",
        _batch_progress_cmd(update_dir, 5, "等待当前程序退出..."),
        ":wait_loop",
        f'tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul',
        "if not errorlevel 1 (",
        "  ping 127.0.0.1 -n 2 >nul",
        "  goto wait_loop",
        ")",
        "ping 127.0.0.1 -n 3 >nul",
        _batch_progress_cmd(update_dir, 8, "正在打开更新进度窗口..."),
        _batch_launch_monitor_cmd(update_dir),
        "ping 127.0.0.1 -n 5 >nul",
        _batch_progress_cmd(update_dir, 15, "清理临时文件..."),
        f'if exist "{staging_dir}" rd /s /q "{staging_dir}"',
        _batch_progress_cmd(update_dir, 25, expand_message),
        f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{ps_expand}"',
        "if errorlevel 1 (",
        _batch_progress_cmd(update_dir, -1, "解压更新包失败"),
        "  exit /b 1",
        ")",
        _batch_progress_cmd(update_dir, 55, "解压完成，准备安装..."),
    ]
    if not is_patch:
        script_lines.extend(
            [
                _batch_progress_cmd(update_dir, 65, "正在备份旧版本..."),
                *pre_copy_lines,
            ]
        )
    script_lines.extend(
        [
            _batch_progress_cmd(update_dir, 75, install_message),
            *_robocopy_install_cmd(
                copy_from,
                target_dir,
                update_dir,
                backup_dir=backup_dir if not is_patch else "",
                backup_internal=backup_internal if in_place and not is_patch else "",
                internal_dir=internal_dir if in_place and not is_patch else "",
            ),
            _batch_progress_cmd(update_dir, 90, "正在启动新版本..."),
            f'start "" "{target_launch}"',
            _batch_progress_cmd(update_dir, 100, "更新完成"),
            f'rd /s /q "{staging_dir}" 2>nul',
            f'del /F /Q "{zip_path}" 2>nul',
            'del /F /Q "%~f0" 2>nul',
            *_batch_progress_helpers(update_dir),
        ]
    )
    script = "\r\n".join(script_lines)
    script_path = os.path.join(update_dir, "apply_onedir_update.bat")
    _start_update_monitor_and_batch(update_dir, script_path, script)


def prepare_download_path(filename: str) -> str:
    update_dir = os.path.join(os.path.dirname(get_executable_path()), "_luxelead_updates")
    os.makedirs(update_dir, exist_ok=True)
    safe_name = os.path.basename(filename) or "LuxeLead_update.exe"
    return os.path.join(update_dir, safe_name)


def check_for_update(
    manifest_url: Optional[str] = None,
    timeout: float = 15,
    config: Optional[dict] = None,
) -> Tuple[Optional[dict], Optional[str]]:
    try:
        manifest = fetch_manifest(manifest_url, timeout=timeout, config=config)
    except urllib.error.URLError as exc:
        return None, f"无法连接更新服务器: {exc.reason}"
    except urllib.error.HTTPError as exc:
        return None, f"更新服务器返回错误: HTTP {exc.code}"
    except (json.JSONDecodeError, ValueError) as exc:
        return None, f"更新清单格式错误: {exc}"
    except Exception as exc:
        return None, f"检查更新失败: {exc}"
    return manifest, None
