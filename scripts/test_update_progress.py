#!/usr/bin/env python3
"""Test update progress window with onedir exe."""

import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from luxelead.release_pack import find_launch_exe, find_onedir_folder
from luxelead.updater import _batch_launch_monitor_cmd, init_update_progress, write_update_progress


def main() -> int:
    onedir = find_onedir_folder(os.path.join(ROOT, "dist"))
    exe = os.path.join(onedir, find_launch_exe(onedir))
    if not os.path.isfile(exe):
        print("[FAIL] exe not found:", exe)
        return 1

    test_dir = os.path.join(ROOT, "_test_progress")
    os.makedirs(test_dir, exist_ok=True)
    init_update_progress(test_dir, 5, "测试：等待程序退出...")

    bat = os.path.join(test_dir, "run_progress_test.bat")
    lines = [
        "@echo off",
        _batch_launch_monitor_cmd(exe, test_dir),
        "ping 127.0.0.1 -n 8 >nul",
    ]
    for pct, msg in ((25, "测试：解压中..."), (60, "测试：安装中..."), (100, "测试：完成")):
        lines.append(f'("{pct}"& echo {msg})> "{os.path.join(test_dir, "progress.txt")}"')
        lines.append("ping 127.0.0.1 -n 3 >nul")

    with open(bat, "w", encoding="utf-8", newline="\r\n") as handle:
        handle.write("\r\n".join(lines))

    print("[INFO] launching monitor via batch:", exe)
    subprocess.Popen(["cmd.exe", "/c", bat], cwd=test_dir)
    time.sleep(40)
    print("[OK] progress test finished (check if window appeared)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
