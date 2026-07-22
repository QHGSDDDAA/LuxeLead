# -*- mode: python ; coding: utf-8 -*-
"""
macOS PyInstaller spec for LuxeLead.
Produces a signed .app bundle for distribution to Apple notebook users.

Usage:
    pyinstaller luxelead_macos.spec --noconfirm


Environment variables:
    LUXELEAD_ICON       Path to .icns file (default: luxelead.icns)
    LUXELEAD_VERSION    Override version string (default: from src/luxelead/version.py)
    LUXELEAD_BUILD      Build number (default: 1)
"""

import os
import sys
import site

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
def _read_version():
    """Read VERSION from version.py without importing the package."""
    version_py = os.path.join(
        os.getcwd(), "src", "luxelead", "version.py"
    )
    with open(version_py, encoding="utf-8") as f:
        for line in f:
            if line.startswith("VERSION"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return "0.8.0"

APP_VERSION = os.environ.get("LUXELEAD_VERSION", _read_version())
BUILD_NUMBER = os.environ.get("LUXELEAD_BUILD", "1")

# ---------------------------------------------------------------------------
# Icon
# ---------------------------------------------------------------------------
ICON_PATH = os.environ.get("LUXELEAD_ICON", "luxelead.icns")
if not os.path.isfile(ICON_PATH):
    ICON_PATH = None  # PyInstaller will use a default icon

# ---------------------------------------------------------------------------
# Bundle metadata
# ---------------------------------------------------------------------------
BUNDLE_IDENTIFIER = "com.luxelead.ppt-generator"
BUNDLE_NAME = "LuxeLead"
BUNDLE_DISPLAY_NAME = "伊芙丽奢领竞PPT排版工具"

# ---------------------------------------------------------------------------
# Data files


datas = [
    ("yolov8n.pt", "."),
    ("src/luxelead/templates/default.pptx", "templates"),
    ("releases/RELEASE_NOTES.md", "releases"),
]

# 强制包含所有 luxelead .py 文件（有时 PyInstaller 会遗漏）
import os
for root, dirs, files in os.walk("src/luxelead"):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for f in files:
        if f.endswith(".py"):
            src = os.path.join(root, f)
            dst = os.path.relpath(root, "src")
            datas.append((src, dst))


# ---------------------------------------------------------------------------
# Hidden imports  (same as Windows, minus platform-specific ones)
# ---------------------------------------------------------------------------
hiddenimports = [
    "pptx",
    "ultralytics",
    "ultralytics.models",
    "ultralytics.nn",
    "ultralytics.engine",
    "ultralytics.utils",
    "torch",
    "torchvision",
    "cv2",
    "numpy",
    "lxml",
    "PIL",
    "matplotlib",
    "matplotlib.pyplot",
    "matplotlib.backends.backend_agg",
    "tkinter",
    "tkinter.ttk",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "pi_heif",
    "luxelead.version_dialog",
    "luxelead.version",
    "luxelead.update_progress",
]

# 强制包含所有 luxelead .py 文件（有时 PyInstaller 会遗漏）
import os
for root, dirs, files in os.walk("src/luxelead"):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for f in files:
        if f.endswith(".py"):
            src = os.path.join(root, f)
            dst = os.path.relpath(root, "src")
            datas.append((src, dst))


# ---------------------------------------------------------------------------
# Collect pptx data/bins recursively
# ---------------------------------------------------------------------------



for pkg in ("pptx", "pi_heif"):
    ret = collect_all(pkg)
    datas += ret[0]
    hiddenimports += ret[2]

# ---------------------------------------------------------------------------
# Exclude heavy / unused packages (same as Windows but no sympy/mpmath issue
# on macOS - ultralytics may still pull them in via YOLO export paths)
# ---------------------------------------------------------------------------
excludes = [
    "tensorboard",
    "tensorflow",
    "keras",
    "notebook",
    "IPython",
    "pytest",
    "pandas",
]

# 强制包含所有 luxelead .py 文件（有时 PyInstaller 会遗漏）
import os
for root, dirs, files in os.walk("src/luxelead"):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for f in files:
        if f.endswith(".py"):
            src = os.path.join(root, f)
            dst = os.path.relpath(root, "src")
            datas.append((src, dst))


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    ["src/luxelead/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# ---------------------------------------------------------------------------
# Executable  (windowed = no terminal; GUI app)
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=BUNDLE_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # GUI mode - no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,       # auto: arm64 on Apple Silicon, x86_64 on Intel
    codesign_identity=None,  # set via --osx-bundle-identifier or env
    entitlements_file=None,
)

# ---------------------------------------------------------------------------
# App bundle  (the .app folder macOS users double-click)
# ---------------------------------------------------------------------------
app = BUNDLE(
    exe,
    name=f"{BUNDLE_NAME}.app",
    icon=ICON_PATH,
    bundle_identifier=BUNDLE_IDENTIFIER,
    info_plist={
        "CFBundleName": BUNDLE_NAME,
        "CFBundleDisplayName": BUNDLE_DISPLAY_NAME,
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": f"{APP_VERSION}.{BUILD_NUMBER}",
        "CFBundleIdentifier": BUNDLE_IDENTIFIER,
        "CFBundleExecutable": BUNDLE_NAME,
        "CFBundlePackageType": "APPL",
        "CFBundleInfoDictionaryVersion": "6.0",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": f"Copyright (c) {_read_version()} LuxeLead Team. All rights reserved.",
        "LSMinimumSystemVersion": "11.0",   # macOS 11 Big Sur minimum
        "NSRequiresAquaSystemAppearance": False,
    },
    version=APP_VERSION,
)

