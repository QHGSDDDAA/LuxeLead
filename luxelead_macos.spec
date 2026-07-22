# -*- mode: python ; coding: utf-8 -*-
"""
macOS PyInstaller spec for LuxeLead.
Produces a signed .app bundle for distribution to Apple notebook users.
"""

import os
import sys
import site
from PyInstaller.utils.hooks import collect_all

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
def _read_version():
    version_py = os.path.join(os.getcwd(), "src", "luxelead", "version.py")
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
    ICON_PATH = None

# ---------------------------------------------------------------------------
# Bundle metadata
# ---------------------------------------------------------------------------
BUNDLE_IDENTIFIER = "com.luxelead.ppt-generator"
BUNDLE_NAME = "LuxeLead"
BUNDLE_DISPLAY_NAME = "\u4f0a\u5b5c\u4e3d\u5962\u9886\u7adePPT\u6392\u7248\u5de5\u5177"

# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------
datas = [
    ("yolov8n.pt", "."),
    ("src/luxelead/templates/default.pptx", "templates"),
    ("releases/RELEASE_NOTES.md", "releases"),
]

# Force-include ALL luxelead source files (PyInstaller sometimes misses)
for root, dirs, files in os.walk("src/luxelead"):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for f in files:
        if f.endswith(".py"):
            src = os.path.join(root, f)
            dst = os.path.relpath(root, "src")
            datas.append((src, dst))

# ---------------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------------
hiddenimports = [
    "pptx",
    "ultralytics", "ultralytics.models", "ultralytics.nn",
    "ultralytics.engine", "ultralytics.utils",
    "torch", "torchvision",
    "cv2", "numpy", "lxml", "PIL",
    "matplotlib", "matplotlib.pyplot",
    "matplotlib.backends.backend_agg",
    "tkinter", "tkinter.ttk",
    "tkinter.filedialog", "tkinter.messagebox",
    "pi_heif",
]

# Collect pptx/pi_heif submodules
for pkg in ("pptx", "pi_heif"):
    ret = collect_all(pkg)
    datas += ret[0]
    hiddenimports += ret[2]

# ---------------------------------------------------------------------------
# Excludes
# ---------------------------------------------------------------------------
excludes = [
    "tensorboard", "tensorflow", "keras",
    "notebook", "IPython", "pytest", "pandas",
]

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
# Executable (windowed = GUI)
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# ---------------------------------------------------------------------------
# App bundle (.app)
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
        "NSHumanReadableCopyright": f"Copyright (c) {APP_VERSION} LuxeLead Team",
        "LSMinimumSystemVersion": "11.0",
        "NSRequiresAquaSystemAppearance": False,
    },
    version=APP_VERSION,
)
