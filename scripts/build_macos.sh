#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# build_macos.sh — 本地构建 LuxeLead macOS .app
#
# 无需 Apple 开发者证书！构建的 .app 可直接在 Mac 上运行。
# （首次打开时如果 Gatekeeper 提示"无法验证开发者"，右键 → 打开即可）
#
# 如果你有 Apple Developer 账号，设以下环境变量可开启签名+公证：
#   export APPLE_DEVELOPER_IDENTITY="Developer ID Application: Your Name (TEAMID)"
#   export APPLE_ID="your@apple.id"
#   export APPLE_TEAM_ID="YOURTEAMID"
#   export APPLE_APP_SPECIFIC_PASSWORD="xxxx-xxxx-xxxx-xxxx"
#
# 用法:
#   bash scripts/build_macos.sh
#
# 环境变量(可选):
#   LUXELEAD_ICON       .icns 图标路径（默认使用 PyInstaller 默认图标）
#   LUXELEAD_VERSION    版本号覆盖
#   LUXELEAD_BUILD      Build 号（默认 1）
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== LuxeLead macOS Build ==="
echo "项目目录: $PROJECT_DIR"
cd "$PROJECT_DIR"

# ---- 读取版本 ----
VERSION_FILE="$PROJECT_DIR/src/luxelead/version.py"
VERSION="${LUXELEAD_VERSION:-$(python3 -c "
exec(open('$VERSION_FILE').read())
print(VERSION)
" 2>/dev/null || echo "0.8.0")}"
echo "构建版本: $VERSION"

# ---- 1. 系统依赖 ----
echo ""
echo "=== [1/7] 系统依赖 (Homebrew) ==="
if command -v brew &>/dev/null; then
    brew install libheif libde265 2>/dev/null || echo "  （已安装，跳过）"
else
    echo "  ⚠️ 未找到 Homebrew。HEIC 图片支持需要安装 libheif。"
fi

# ---- 2. Python 依赖 ----
echo ""
echo "=== [2/7] Python 依赖 ==="
python3 -m pip install --upgrade pip
if [ -f requirements-macos.txt ]; then
    python3 -m pip install -r requirements-macos.txt
else
    python3 -m pip install pyinstaller ultralytics pillow python-pptx lxml pi-heif torch torchvision
fi

python3 -c "import ultralytics; print('  ultralytics', ultralytics.__version__)"
python3 -c "import torch; print('  torch', torch.__version__)"
python3 -c "import pi_heif; print('  pi-heif OK')"

# ---- 3. 图标 ----
echo ""
echo "=== [3/7] 应用图标 ==="
if [ -n "${LUXELEAD_ICON:-}" ] && [ -f "$LUXELEAD_ICON" ]; then
    echo "  使用图标: $LUXELEAD_ICON"
    export LUXELEAD_ICON
elif [ -f "luxelead.icns" ]; then
    echo "  使用项目图标: luxelead.icns"
else
    echo "  未找到 .icns，使用 PyInstaller 默认图标"
    echo "  提示: 准备 1024×1024 PNG 后运行 scripts/make_icon.sh 生成图标"
fi

# ---- 4. YOLOv8 模型 ----
echo ""
echo "=== [4/7] YOLOv8 模型 ==="
if [ ! -f "yolov8n.pt" ]; then
    echo "  正在下载 yolov8n.pt..."
    python3 -c "from ultralytics import YOLO; YOLO('yolov8n.pt'); print('  下载完成')"
else
    echo "  yolov8n.pt 已存在"
fi
ls -lh yolov8n.pt

# ---- 5. PyInstaller 打包 ----
echo ""
echo "=== [5/7] PyInstaller 打包 ==="
rm -rf build dist
pyinstaller luxelead_macos.spec --noconfirm --log-level=INFO

APP_BUNDLE="dist/LuxeLead.app"
if [ ! -d "$APP_BUNDLE" ]; then
    echo "❌ 打包失败: dist/LuxeLead.app 未生成"
    ls -la dist/ 2>/dev/null
    exit 1
fi
echo "  ✅ .app 已创建: $APP_BUNDLE"
echo "  大小: $(du -sh "$APP_BUNDLE" | cut -f1)"

# ---- 6. [可选] 代码签名 ----
echo ""
if [ -z "${APPLE_DEVELOPER_IDENTITY:-}" ]; then
    echo "=== [6/7] 代码签名: 跳过（未设置 APPLE_DEVELOPER_IDENTITY）==="
    echo "  ℹ️  应用可直接运行，但 Gatekeeper 会提示"无法验证开发者""
else
    echo "=== [6/7] 代码签名 ==="
    echo "  证书: $APPLE_DEVELOPER_IDENTITY"
    find "$APP_BUNDLE" -type f \( -perm +111 -o -name "*.dylib" -o -name "*.so" \) | \
    while read -r binary; do
        codesign --force --options runtime --sign "$APPLE_DEVELOPER_IDENTITY" \
            --entitlements scripts/entitlements.plist "$binary" 2>/dev/null || true
    done
    codesign --force --options runtime --deep \
        --sign "$APPLE_DEVELOPER_IDENTITY" \
        --entitlements scripts/entitlements.plist \
        "$APP_BUNDLE"
    codesign -dvvv "$APP_BUNDLE" 2>&1 | head -10
    echo "  ✅ 签名完成"

    # ---- 6b. [可选] DMG + 公证 ----
    echo ""
    echo "=== [6b/7] DMG 打包 ==="
    _make_dmg "$VERSION" "$APP_BUNDLE"

    echo ""
    echo "=== [6c/7] Apple 公证 ==="
    if [ -n "${APPLE_ID:-}" ] && [ -n "${APPLE_APP_SPECIFIC_PASSWORD:-}" ] && [ -n "${APPLE_TEAM_ID:-}" ]; then
        DMG_PATH="dist/LuxeLead-$VERSION.dmg"
        xcrun notarytool submit "$DMG_PATH" \
            --apple-id "$APPLE_ID" \
            --team-id "$APPLE_TEAM_ID" \
            --password "$APPLE_APP_SPECIFIC_PASSWORD" \
            --wait 10m --progress
        xcrun stapler staple "$DMG_PATH"
        xcrun stapler staple "$APP_BUNDLE"
        echo "  ✅ 公证完成"
    else
        echo "  ⏭️  跳过公证（未设置 APPLE_ID / APPLE_TEAM_ID / APPLE_APP_SPECIFIC_PASSWORD）"
    fi
    echo ""
    echo "=============================="
    echo "构建完成！签名版 DMG 可直接分发给用户。"
    ls -lh "dist/LuxeLead-$VERSION.dmg"
    exit 0
fi

# ---- 7. DMG 打包（无签名版本） ----
echo ""
echo "=== [7/7] DMG 打包 ==="
if command -v create-dmg &>/dev/null; then
    create-dmg \
        --volname "LuxeLead $VERSION" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "LuxeLead.app" 175 190 \
        --hide-extension "LuxeLead.app" \
        --app-drop-link 425 190 \
        "dist/LuxeLead-$VERSION.dmg" \
        "$APP_BUNDLE"
else
    DMG_DIR="dist/dmg_staging"
    mkdir -p "$DMG_DIR"
    cp -R "$APP_BUNDLE" "$DMG_DIR/"
    ln -s /Applications "$DMG_DIR/Applications"
    hdiutil create \
        -volname "LuxeLead $VERSION" \
        -srcfolder "$DMG_DIR" \
        -ov -format UDZO \
        "dist/LuxeLead-$VERSION.dmg"
    rm -rf "$DMG_DIR"
fi

echo ""
echo "=============================="
echo "  ✅ 构建完毕！"
echo "  DMG: dist/LuxeLead-$VERSION.dmg"
echo ""
echo "  📖 分发给用户后，请告知："
echo "     首次打开 → 右键点击 → 选择"打开""
echo "=============================="
ls -lh "dist/LuxeLead-$VERSION.dmg"
