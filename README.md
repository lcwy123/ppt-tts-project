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
├── packages/                # 离线依赖包（需下载）
├── main.py                  # 主程序入口
├── requirements-cpu.txt     # CPU版本依赖
├── requirements-gpu.txt     # GPU版本依赖
└── requirements-cosyvoice-minimal.txt  # CosyVoice最小依赖
```

## 快速开始

### 方式一：联网安装（推荐用于开发）

```bash
# 基础依赖
pip install -r requirements-cpu.txt

# GPU支持 + CosyVoice
pip install -r requirements-gpu.txt

# 或安装完整CosyVoice依赖
pip install -r CosyVoice/requirements.txt
```

### 方式二：离线部署（生产环境）

#### 第一步：在联网环境下载依赖

```bash
python download_packages.py
```

这会将所有依赖下载到 `packages/` 目录。

#### 第二步：复制到离线服务器

```bash
# 将整个项目复制到离线服务器
scp -r ppt-tts-project user@server:/path/to/

# 或只复制必要文件
rsync -av --include='packages/' --include='src/' --include='CosyVoice/' \
      --include='models/' --include='main.py' --include='app.py' \
      --include='requirements-*.txt' --exclude='*' \
      ppt-tts-project/ user@server:/path/to/ppt-tts-project/
```

#### 第三步：在离线服务器安装

```bash
cd ppt-tts-project

# 激活虚拟环境（假设服务器已配置 env_py310_cuda126）
source /path/to/env_py310_cuda126/bin/activate

# 安装离线依赖
pip install --no-index --find-links=packages/ -r requirements-gpu.txt

# 验证安装
python -c "import torch; print(f'PyTorch {torch.__version__}, CUDA: {torch.cuda.is_available()}')"
```

## 配置

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

## 下载模型

模型文件较大，需要单独下载：

```bash
python download_model.py
```

或手动下载：

| 模型 | 大小 | 说明 |
|------|------|------|
| CosyVoice-300M-SFT | ~3GB | 基础语音模型 |
| Qwen3.5-9B | ~18GB | LLM（可选，火山方舟API无需下载） |

## 运行

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
python ppt_generator.py      # 提纲→PPT
python slides_extractor.py   # 提取文本
python narration_generator.py # 生成解说词
python audio_generator.py    # 生成音频
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

## 离线部署服务器环境

- **操作系统**: 银河麒麟 Linux Advanced Server V10
- **Python**: 3.10.20
- **CUDA**: 12.6
- **虚拟环境**: env_py310_cuda126

## 常见问题

### Q: 离线环境下 torch 导入失败？
A: 确保使用 `--find-links=packages/` 参数安装，指定离线包目录。

### Q: 缺少某个 .whl 文件？
A: 在联网环境运行 `pip download <package-name> -d packages/` 补充下载。

### Q: GPU 未被识别？
A: 检查 CUDA 环境：`python -c "import torch; print(torch.cuda.is_available())"`

## License

MIT
