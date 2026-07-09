# LuxeLead PPT Generator

> 轻奢领先竞品的PPT排版工具

LuxeLead 是一款专业的PPT自动生成工具，能够根据图片文件夹自动排版生成精美PPT演示文稿。

## 功能特性

- 🎯 **智能图片排版** - 自动计算最优布局，图片铺满页面
- 📁 **多模式支持** - 支持按文件夹或按文件前缀分组
- 🔄 **递归遍历** - 自动处理子文件夹中的图片
- 🖼️ **保持比例** - 图片等比例缩放，不裁剪不变形
- 📊 **批量生成** - 一次性处理大量图片
- 💾 **自动保存** - 默认保存到桌面，支持自定义路径

## 快速开始

### 安装依赖

```bash
pip install python-pptx Pillow lxml
```

### 运行应用

```bash
# 运行GUI版本
python -m luxelead.gui

# 命令行版本
luxelead --help
```

### 打包成可执行文件

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name="LuxeLead" src/luxelead/gui.py
```

## 项目结构

```
LuxeLead/
├── src/
│   └── luxelead/
│       ├── __init__.py
│       ├── gui.py          # GUI主界面
│       ├── generator.py    # PPT生成核心逻辑
│       ├── layout.py       # 图片布局算法
│       └── cli.py          # 命令行接口
├── tests/                  # 测试目录
│   ├── __init__.py
│   ├── conftest.py
│   └── test_*.py          # 测试文件
├── docs/                   # 文档目录
├── setup.py               # 打包配置
├── pyproject.toml         # 项目配置
└── README.md              # 项目说明
```

## 使用说明

### 按文件夹模式

将主文件夹中的图片生成第1页PPT，每个子文件夹生成独立页面。

### 按文件前缀模式

按文件名中的前缀（`_`分隔）分组，相同前缀的图片生成同一页PPT。支持递归遍历子文件夹，不同文件夹中的相同前缀不会合并。

## 版本历史

- **v0.2.0** - 支持按文件前缀分组，递归遍历子文件夹
- **v0.1.0** - 初始版本，支持按文件夹分组

## 许可证

MIT License