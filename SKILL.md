# PPT-TTS-Project Skill

## 项目概述

全自动PPT配音生成系统，支持本地离线部署，集成ppt-master原生形状PPTX生成。

## 功能特性

- 📝 **文字 → Word提纲** - AI自动生成结构化提纲
- 📊 **提纲 → 美化PPT** - 自动生成专业PPT（支持原生形状）
- 🎤 **解说词生成** - AI生成口播解说词
- 🔊 **本地TTS配音** - 使用CosyVoice本地语音合成
- 📥 **音频嵌入** - 自动嵌入PPT并设置播放
- ✨ **动画支持** - 原生OOXML页面过渡和元素入场动画
- 🌐 **双模式支持** - 本地SGlang(Qwen) / 联网API

## 目录结构

```
ppt-tts-project/
├── src/                      # 源码模块
│   ├── config.py             # 配置管理
│   ├── outline_generator.py  # 文字→提纲
│   ├── ppt_generator.py     # 提纲→PPT (已集成ppt-master)
│   ├── ppt_master/          # ppt-master核心模块
│   │   ├── svg_generator.py # SVG生成器
│   │   ├── pptx_builder.py  # 原生PPTX构建器
│   │   ├── pptx_narration.py # 旁白嵌入
│   │   ├── pptx_animations.py # 动画支持
│   │   └── ...
│   ├── slides_extractor.py   # 提取PPT文本
│   ├── narration_generator.py  # 解说词生成
│   ├── audio_generator.py    # 音频生成(CosyVoice)
│   └── audio_embedder.py     # 音频嵌入PPT
├── data/                    # 数据目录
├── models/                  # 模型文件
├── packages/                # 离线依赖包
├── main.py                  # 主程序入口
└── requirements.txt         # 依赖清单
```

## ppt-master集成

### 核心能力

| 功能 | 状态 | 说明 |
|------|------|------|
| 原生DrawingML形状 | ✅ | 非图片，可直接编辑 |
| 页面过渡动画 | ✅ | fade/push/wipe等效果 |
| 元素入场动画 | ✅ | mixed/random等效果 |
| 旁白音频嵌入 | ✅ | 自动匹配slide |
| Office兼容模式 | ✅ | PNG+SVG双格式 |

### 使用方法

```python
from src.ppt_generator import run

# 默认使用enhanced模式(ppt-master)
run(progress_callback=print)

# 或强制使用enhanced模式
run(use_enhanced=True, progress_callback=print)

# 回退到基础模式
run(use_enhanced=False, progress_callback=print)
```

### 配置选项 (.env)

```env
ENABLE_PPT_MASTER=true        # 启用增强模式
PPT_MASTER_ANIMATIONS=true   # 启用动画
PPT_MASTER_TRANSITIONS=true  # 启用过渡
PPT_MASTER_STYLE=modern      # 风格: modern或classic
```

## 快速开始

### 联网安装

```bash
pip install -r requirements-gpu.txt
```

### 离线部署

```bash
# 1. 下载依赖包
python download_packages.py

# 2. 安装
pip install --no-index --find-links=packages/ -r requirements-gpu.txt
```

### 运行

```bash
# 命令行模式
python main.py

# WebUI模式
python main.py --webui --port 7860
```

## 技术栈

- **LLM**: 本地SGlang(Qwen3.5-9B) / 火山方舟豆包
- **PPT生成**: python-pptx + ppt-master原生形状
- **TTS**: CosyVoice-300M-SFT (本地) / Edge TTS
- **动画**: pptx_animations (原生OOXML)
- **WebUI**: Gradio

## 部署环境

- **操作系统**: 银河麒麟 Linux Advanced Server V10
- **Python**: 3.10.20
- **CUDA**: 12.6
- **虚拟环境**: env_py310_cuda126
