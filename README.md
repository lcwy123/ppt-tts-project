# PPT-TTS-Project

全自动PPT配音生成系统 - 支持本地离线部署

## 功能特点

- 📝 **文字 → Word提纲** - AI自动生成结构化提纲
- 📊 **提纲 → 美化PPT** - 自动生成专业PPT
- 🎤 **解说词生成** - AI生成口播解说词
- 🔊 **本地TTS配音** - 使用CosyVoice本地语音合成
- 📥 **音频嵌入** - 自动嵌入PPT并设置播放
- 🌐 **双模式支持** - 本地SGlang(Qwen) / 联网API

## 项目结构

```
ppt-tts-project/
├── src/                      # 源码模块
│   ├── config.py             # 配置管理
│   ├── outline_generator.py  # 文字→提纲
│   ├── ppt_generator.py       # 提纲→PPT
│   ├── slides_extractor.py   # 提取PPT文本
│   ├── narration_generator.py  # 解说词生成
│   ├── audio_generator.py    # 音频生成
│   ├── audio_embedder.py     # 音频嵌入PPT
│   └── backup.py             # 备份工具
├── test/                     # 测试脚本
├── data/                    # 数据目录
│   ├── input/               # 输入文件
│   ├── output/              # 输出文件
│   ├── audio/               # 音频文件
│   └── backup/              # 备份文件
├── webui/                   # Gradio WebUI
│   └── app.py
├── models/                  # 模型文件
│   └── CosyVoice-300M-SFT/ # CosyVoice预训练模型
├── main.py                  # 主程序入口
└── requirements.txt         # 依赖
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

编辑 `.env` 文件：

```env
# LLM 模式: local (本地SGlang) 或 api (火山方舟)
LLM_MODE=local

# 本地SGlang配置
LOCAL_LLM_URL=http://localhost:30000/v1
LOCAL_LLM_MODEL=Qwen3.5-9B
LOCAL_LLM_API_KEY=token-xxx

# TTS 模式: cosyvoice (本地) 或 edge (联网)
TTS_MODE=cosyvoice
```

### 3. 下载模型

```bash
python download_model.py
```

### 4. 运行

**命令行模式：**
```bash
python main.py
```

**WebUI模式：**
```bash
python main.py --webui --port 7860
```

## 使用方法

### 方式一：WebUI（推荐）

1. 启动WebUI: `python main.py --webui`
2. 打开浏览器访问: http://localhost:7860
3. 输入主题文字
4. 点击"开始生成"
5. 支持暂停/继续/停止

### 方式二：命令行

```bash
# 完整流程
python main.py

# 或分步骤执行
cd src
python outline_generator.py   # 文字→提纲
python ppt_generator.py        # 提纲→PPT
python slides_extractor.py     # 提取文本
python narration_generator.py  # 生成解说词
python audio_generator.py     # 生成音频
python audio_embedder.py     # 嵌入PPT
```

## 技术栈

- **LLM**: 本地SGlang(Qwen3.5-9B) / 火山方舟豆包
- **TTS**: CosyVoice-300M-SFT (本地) / Edge TTS
- **PPT处理**: python-pptx
- **Word处理**: python-docx
- **WebUI**: Gradio

## 数据目录

所有输入输出文件都在 `data/` 目录下：

```
data/
├── input/
│   ├── input.txt              # 输入文字（从零生成时）
│   └── input.pptx             # 输入PPT（已有PPT配音时）
├── output/
│   ├── ppt_outline.docx       # 生成的Word提纲
│   ├── generated.pptx         # 生成的PPT
│   ├── slides_text.txt        # 提取的PPT文本
│   ├── narration.txt          # AI生成的解说词
│   ├── audio_durations.json   # 音频时长信息
│   └── final_with_audio.pptx # 最终带音频的PPT
├── audio/                     # 生成的音频文件
└── backup/                    # 历史备份
```

## License

MIT
