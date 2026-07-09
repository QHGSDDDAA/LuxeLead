# 安装指南

## YOLOv8 依赖安装

本项目需要 `ultralytics` 库来提供 YOLOv8 人物检测功能。

### 方法 1: 使用 Python 安装（推荐）

在命令行中运行：

```bash
python -m pip install ultralytics>=8.0.0
```

或者：

```bash
pip install ultralytics>=8.0.0
```

### 方法 2: 使用批处理脚本（Windows）

双击运行 `install_yolov8.bat` 文件。

### 验证安装

安装完成后，运行：

```bash
python test_yolov8_import.py
```

如果看到 "ultralytics imported successfully!" 和 "YOLOv8 model loaded successfully!"，说明安装成功。

## 常见问题

### Q: 提示 "pip : 无法将“pip”项识别"

**A:** 请尝试使用 `python -m pip` 替代直接使用 `pip`，或者检查 Python 是否正确添加到系统路径中。

### Q: 安装速度太慢

**A:** 可以使用国内镜像源：
```bash
python -m pip install ultralytics>=8.0.0 -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q: 安装后仍然提示 "YOLOv8未安装"

**A:** 请确保您在正确的 Python 环境中安装了依赖。如果使用了虚拟环境，需要先激活虚拟环境。
