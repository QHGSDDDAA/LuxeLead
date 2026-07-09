#!/usr/bin/env python3
"""Test onedir zip update flow locally."""

import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from luxelead.release_pack import PACKAGE_FOLDER, create_onedir_zip, find_launch_exe, find_onedir_folder
from luxelead.updater import apply_windows_onedir_update


def main() -> int:
    test_root = os.path.join(ROOT, "_update_test_onedir")
    shutil.rmtree(test_root, ignore_errors=True)
    os.makedirs(test_root, exist_ok=True)

    legacy_exe = os.path.join(test_root, "legacy_onefile.exe")
    with open(legacy_exe, "wb") as handle:
        handle.write(b"legacy")

    onedir_dir = find_onedir_folder(os.path.join(ROOT, "dist"))
    launch_exe = find_launch_exe(onedir_dir)
    zip_path = os.path.join(test_root, "update.zip")
    create_onedir_zip(onedir_dir, zip_path, folder_name=PACKAGE_FOLDER)

    manifest = {
        "package_type": "onedir_zip",
        "zip_root": PACKAGE_FOLDER,
        "app_folder": PACKAGE_FOLDER,
        "launch_exe": launch_exe,
    }

    apply_windows_onedir_update(
        zip_path,
        manifest,
        current_exe_path=legacy_exe,
        parent_pid=999999,
    )

    target = os.path.join(test_root, PACKAGE_FOLDER, launch_exe)
    for _ in range(180):
        if os.path.isfile(target):
            break
        __import__("time").sleep(1)
    else:
        print("[FAIL] onedir exe not installed:", target)
        return 1

    proc = subprocess.Popen([target], cwd=os.path.dirname(target))
    __import__("time").sleep(5)
    if proc.poll() is None:
        proc.terminate()
        print("[OK] onedir update install and launch succeeded")
        return 0

    print("[FAIL] launched exe exited early with code", proc.returncode)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
