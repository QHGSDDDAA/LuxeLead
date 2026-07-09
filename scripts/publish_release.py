#!/usr/bin/env python3
"""Generate full zip, incremental patch, installer metadata, and version.json."""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import date

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from luxelead.release_pack import (
    PACKAGE_FOLDER,
    build_file_manifest,
    create_onedir_zip,
    create_patch_zip,
    diff_manifests,
    find_launch_exe,
    find_onedir_folder,
    load_file_manifest,
    save_file_manifest,
)
from luxelead.updater import sha256_file

MANIFEST_PATH = os.path.join(ROOT, "releases", "version.json")
MANIFESTS_DIR = os.path.join(ROOT, "releases", "manifests")
NOTES_PATH = os.path.join(ROOT, "releases", "RELEASE_NOTES.md")
GITLAB_BASE = "http://10.8.251.3:8081/api/v4/projects/220/packages/generic/luxelead"


def read_version_module() -> dict:
    version_py = os.path.join(ROOT, "src", "luxelead", "version.py")
    with open(version_py, "r", encoding="utf-8") as handle:
        content = handle.read()

    def pick(name: str, default: str = "") -> str:
        match = re.search(rf'{name}\s*=\s*"([^"]*)"', content)
        return match.group(1) if match else default

    return {
        "version": pick("VERSION"),
        "display_version": pick("DISPLAY_VERSION"),
        "release_date": pick("RELEASE_DATE", date.today().isoformat()),
    }


def package_url(version: str, filename: str, base_url: str) -> str:
    return f"{base_url.rstrip('/')}/{version}/{filename}"


def bootstrap_patch_base_manifest(patch_base: str, release_dir: str) -> dict:
    """Build baseline file manifest from a previous release zip when missing."""
    snapshot = os.path.join(MANIFESTS_DIR, f"{patch_base}.json")
    if os.path.isfile(snapshot):
        return load_file_manifest(snapshot)

    zip_name = f"LuxeLead_V{patch_base}_win64.zip"
    zip_path = os.path.join(release_dir, zip_name)
    if not os.path.isfile(zip_path):
        print(f"[WARN] 无法生成基线清单：缺少 {snapshot} 与 {zip_path}")
        return {}

    print(f"[INFO] 从 {zip_name} 生成基线清单 {patch_base}.json ...")
    temp_root = tempfile.mkdtemp(prefix="luxelead_manifest_")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(temp_root)
        source_dir = os.path.join(temp_root, PACKAGE_FOLDER)
        if not os.path.isdir(source_dir):
            top_dirs = [
                name
                for name in os.listdir(temp_root)
                if os.path.isdir(os.path.join(temp_root, name))
            ]
            source_dir = os.path.join(temp_root, top_dirs[0]) if len(top_dirs) == 1 else temp_root
        manifest = build_file_manifest(source_dir, PACKAGE_FOLDER)
        os.makedirs(MANIFESTS_DIR, exist_ok=True)
        save_file_manifest(manifest, snapshot)
        print(f"[OK] baseline manifest: {snapshot} ({len(manifest)} files)")
        return manifest
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成完整包、增量包与 version.json")
    parser.add_argument("--dist", default=os.path.join(ROOT, "dist"))
    parser.add_argument("--gitlab-base-url", default=GITLAB_BASE)
    parser.add_argument("--patch-base", default="", help="增量包基线版本，如 0.7.9")
    parser.add_argument("--notes-file", default=NOTES_PATH)
    parser.add_argument("--skip-installer", action="store_true")
    args = parser.parse_args()

    info = read_version_module()
    version = info["version"]
    zip_name = f"LuxeLead_V{version}_win64.zip"
    release_dir = os.path.join(ROOT, "dist", "release")
    os.makedirs(release_dir, exist_ok=True)
    zip_path = os.path.join(release_dir, zip_name)

    onedir_dir = find_onedir_folder(args.dist, version)
    launch_exe = find_launch_exe(onedir_dir)
    create_onedir_zip(onedir_dir, zip_path, folder_name=PACKAGE_FOLDER)

    file_manifest = build_file_manifest(onedir_dir, PACKAGE_FOLDER)
    os.makedirs(MANIFESTS_DIR, exist_ok=True)
    manifest_snapshot = os.path.join(MANIFESTS_DIR, f"{version}.json")
    save_file_manifest(file_manifest, manifest_snapshot)

    previous_manifest = {}
    previous_token = ""
    patch_base = (args.patch_base or "").strip()
    if os.path.isfile(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as handle:
                previous = json.load(handle)
            previous_token = (previous.get("download_token") or "").strip()
            if not patch_base:
                patch_base = (previous.get("version") or "").strip()
        except (json.JSONDecodeError, OSError):
            pass
    if patch_base:
        previous_manifest = bootstrap_patch_base_manifest(patch_base, release_dir)

    with open(args.notes_file, "r", encoding="utf-8") as handle:
        release_notes = handle.read().strip()

    manifest = {
        "version": version,
        "display_version": info["display_version"],
        "release_date": info["release_date"],
        "release_notes": release_notes,
        "package_type": "onedir_zip",
        "filename": zip_name,
        "download_url": package_url(version, zip_name, args.gitlab_base_url),
        "zip_root": PACKAGE_FOLDER,
        "app_folder": PACKAGE_FOLDER,
        "launch_exe": launch_exe,
        "file_size": os.path.getsize(zip_path),
        "sha256": sha256_file(zip_path),
        "file_count": len(file_manifest),
    }
    if previous_token:
        manifest["download_token"] = previous_token

    patches = []
    if patch_base and previous_manifest:
        changed = diff_manifests(previous_manifest, file_manifest)
        if changed:
            patch_name = f"LuxeLead_patch_{patch_base}_to_{version}.zip"
            patch_path = os.path.join(release_dir, patch_name)
            create_patch_zip(onedir_dir, patch_path, changed, folder_name=PACKAGE_FOLDER)
            patches.append(
                {
                    "base_version": patch_base,
                    "package_type": "onedir_patch",
                    "filename": patch_name,
                    "download_url": package_url(version, patch_name, args.gitlab_base_url),
                    "file_size": os.path.getsize(patch_path),
                    "sha256": sha256_file(patch_path),
                    "changed_files": len(changed),
                }
            )
            print(f"[OK] patch zip: {patch_path} ({len(changed)} files)")
        else:
            print(f"[INFO] 与 {patch_base} 相比无文件变化，跳过增量包")
    elif patch_base:
        print(f"[WARN] 未找到基线清单 releases/manifests/{patch_base}.json，跳过增量包")

    if patches:
        manifest["patches"] = patches

    setup_name = f"LuxeLead_Setup_V{version}.exe"
    setup_path = os.path.join(release_dir, setup_name)
    if not args.skip_installer:
        import subprocess

        cmd = [
            sys.executable,
            os.path.join(ROOT, "scripts", "build_installer.py"),
            "--version",
            version,
            "--display-version",
            info["display_version"],
            "--output-dir",
            release_dir,
        ]
        subprocess.run(cmd, cwd=ROOT, check=False)
    if os.path.isfile(setup_path):
        manifest["installer"] = {
            "filename": setup_name,
            "download_url": package_url(version, setup_name, args.gitlab_base_url),
            "file_size": os.path.getsize(setup_path),
            "sha256": sha256_file(setup_path),
        }
        print("[OK] installer:", setup_path)
    else:
        print("[INFO] 未生成安装包（需安装 Inno Setup 6 后重新 publish）")

    with open(MANIFEST_PATH, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print("[OK] full zip:", zip_path)
    print("[OK] file manifest:", manifest_snapshot)
    print("[OK] version.json:", MANIFEST_PATH)
    print(f"  version: {version}")
    print(f"  files:   {len(file_manifest)}")
    print(f"  sha256:  {manifest['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
