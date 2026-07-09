"""Create onedir zip, patch zip, and file manifests for online update."""

import hashlib
import json
import os
import zipfile

PACKAGE_FOLDER = "LuxeLead"


def sha256_file(file_path: str) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def iter_package_files(source_dir: str, folder_name: str = PACKAGE_FOLDER):
    source_dir = os.path.abspath(source_dir)
    folder_name = (folder_name or PACKAGE_FOLDER).strip().strip("/\\")
    for root, _dirs, files in os.walk(source_dir):
        for name in files:
            full_path = os.path.join(root, name)
            rel_path = os.path.relpath(full_path, source_dir).replace("\\", "/")
            arcname = f"{folder_name}/{rel_path}"
            yield arcname, full_path


def build_file_manifest(source_dir: str, folder_name: str = PACKAGE_FOLDER) -> dict:
    manifest = {}
    for arcname, full_path in iter_package_files(source_dir, folder_name):
        manifest[arcname] = {
            "sha256": sha256_file(full_path),
            "size": os.path.getsize(full_path),
        }
    return manifest


def save_file_manifest(manifest: dict, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def load_file_manifest(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def diff_manifests(old_manifest: dict, new_manifest: dict) -> list[str]:
    changed = []
    for arcname, info in new_manifest.items():
        old_info = old_manifest.get(arcname)
        if not old_info or old_info.get("sha256") != info.get("sha256"):
            changed.append(arcname)
    return sorted(changed)


def create_onedir_zip(
    source_dir: str,
    zip_path: str,
    folder_name: str = PACKAGE_FOLDER,
    arcnames: list[str] | None = None,
) -> None:
    source_dir = os.path.abspath(source_dir)
    if not os.path.isdir(source_dir):
        raise FileNotFoundError(f"onedir 目录不存在: {source_dir}")

    folder_name = (folder_name or PACKAGE_FOLDER).strip().strip("/\\")
    if not folder_name:
        raise ValueError("folder_name 不能为空")

    os.makedirs(os.path.dirname(os.path.abspath(zip_path)), exist_ok=True)
    if os.path.isfile(zip_path):
        os.remove(zip_path)

    arc_filter = set(arcnames) if arcnames else None
    prefix = f"{folder_name}/"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for arcname, full_path in iter_package_files(source_dir, folder_name):
            if arc_filter is not None and arcname not in arc_filter:
                continue
            zf.write(full_path, arcname)


def create_patch_zip(
    source_dir: str,
    zip_path: str,
    changed_arcnames: list[str],
    folder_name: str = PACKAGE_FOLDER,
) -> int:
    if not changed_arcnames:
        raise ValueError("增量包没有变更文件")
    create_onedir_zip(source_dir, zip_path, folder_name, arcnames=changed_arcnames)
    return len(changed_arcnames)


def _version_match_keys(version: str) -> list[str]:
    parts = [part for part in (version or "").split(".") if part.isdigit()]
    keys: list[str] = []
    if len(parts) >= 2:
        keys.append(f"{parts[0]}{parts[1]}")
    if parts:
        keys.append("".join(parts))
    return keys


def find_onedir_folder(dist_root: str, version: str = "") -> str:
    dist_root = os.path.abspath(dist_root)
    version_keys = _version_match_keys(version) if version else []
    all_candidates: list[str] = []
    matched: list[str] = []
    for base in (
        os.path.join(dist_root, "windows_onefile"),
        os.path.join(dist_root, "windows_build"),
        os.path.join(dist_root, "windows"),
        dist_root,
    ):
        if not os.path.isdir(base):
            continue
        for name in os.listdir(base):
            path = os.path.join(base, name)
            if not os.path.isdir(path) or not name.endswith("_onedir"):
                continue
            all_candidates.append(path)
            if version_keys:
                folder_key = name.replace(".", "").replace("V", "v").lower()
                if any(key in folder_key for key in version_keys):
                    matched.append(path)
    candidates = matched or all_candidates
    if not candidates:
        raise FileNotFoundError(f"未找到 onedir 目录，请先运行 repack_onefile.bat: {dist_root}")
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates[0]


def find_launch_exe(onedir_path: str) -> str:
    for name in os.listdir(onedir_path):
        if name.lower().endswith(".exe") and "_internal" not in name.lower():
            return name
    raise FileNotFoundError(f"onedir 中未找到 exe: {onedir_path}")
