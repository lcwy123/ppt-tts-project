# PPT-TTS-Project 离线部署指南

> 适用环境：银河麒麟 Linux Advanced Server V10 (x86_64) + Python 3.10.20 + CUDA 12.6

---

## 📦 部署包内容

部署包包含以下内容（解压后约 6.2GB）：

```
ppt-tts-offline/
├── SKILL.md                      # 项目说明文档
├── README.md                     # 项目说明
├── requirements-cpu.txt          # CPU版本依赖
├── requirements-gpu.txt          # GPU版本依赖
├── requirements-cosyvoice-minimal.txt  # CosyVoice最小依赖
├── download_packages.py          # 离线包下载脚本（备用）
├── download_model.py             # 模型下载脚本（备用）
├── main.py                      # 命令行入口
├── app.py                       # WebUI入口
├── start.sh                     # 启动脚本
├── src/                         # 源码
├── CosyVoice/                   # CosyVoice代码
├── webui/                       # WebUI
├── test/                        # 测试脚本
├── packages/                    # Python离线依赖包（352MB，66个文件）
│   └── *.whl
└── models/                     # 预训练模型（5.4GB）
    └── iic/CosyVoice-300M-SFT/
        ├── llm.pt              # LLM权重 (1.2GB)
        ├── flow.pt             # Flow模型 (401MB)
        ├── hift.pt             # HiFT模型 (79MB)
        ├── cosyvoice.yaml      # 配置文件
        ├── campplus.onnx       # ONNX模型 (27MB)
        ├── speech_tokenizer_v1.onnx  # 分词器 (499MB)
        ├── spk2info.pt         # 说话人信息
        └── ... (其他模型文件)
```

---

## 🚀 快速部署

### 第一步：解压部署包

```bash
# 解压所有分包（假设分成了 8 个 part）
cat ppt-tts-offline-part* > ppt-tts-offline.tar.gz
tar -xzf ppt-tts-offline.tar.gz
cd ppt-tts-offline
```

### 第二步：激活服务器虚拟环境

```bash
source /path/to/env_py310_cuda126/bin/activate
```

### 第三步：安装离线依赖

```bash
# 安装 GPU 版本依赖（包含 CosyVoice）
pip install --no-index --find-links=packages/ -r requirements-gpu.txt

# 如果只需要 CPU 功能（无 TTS）
pip install --no-index --find-links=packages/ -r requirements-cpu.txt
```

### 第四步：验证安装

```bash
# 验证 PyTorch + CUDA
python -c "import torch; print(f'PyTorch {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}')"

# 验证 CosyVoice
python -c "import sys; sys.path.insert(0, '.'); from cosyvoice.cli.cosyvoice import CosyVoice; print('CosyVoice OK')"
```

### 第五步：配置

创建 `.env` 文件：

```env
# LLM 模式: local (本地SGlang) 或 api (火山方舟)
LLM_MODE=local

# 本地SGlang配置
LOCAL_LLM_URL=http://localhost:30000/v1
LOCAL_LLM_MODEL=Qwen3.5-9B
LOCAL_LLM_API_KEY=your-token-here

# TTS 模式: cosyvoice (本地) 或 edge (联网)
TTS_MODE=cosyvoice
```

### 第六步：运行

```bash
# 命令行模式
python main.py

# WebUI模式
python main.py --webui --port 7860
```

---

## ⚠️ 注意事项

### 1. PyTorch GPU 版本

`packages/` 目录中**不包含** PyTorch 的 CUDA 版本（约 2GB）。如果安装 `requirements-gpu.txt` 后 torch 无法使用 GPU，需要单独处理：

```bash
# 方法A：从官网下载 whl 文件放入 packages/ 后重试
pip install --no-index --find-links=packages/ torch==2.4.0 --index-url https://download.pytorch.org/whl/cu126

# 方法B：如果服务器可以临时联网
pip install torch==2.4.0 --index-url https://download.pytorch.org/whl/cu126

# 方法C：使用 CPU 版本（不推荐，推理很慢）
pip install --no-index --find-links=packages/ -r requirements-cpu.txt
```

### 2. 模型文件路径

模型文件默认位于 `models/iic/CosyVoice-300M-SFT/`，代码中通过 `COSYVOICE_DIR` 配置项引用。如需更换位置，修改 `src/config.py` 或 `.env` 中的 `COSYVOICE_DIR` 路径。

### 3. 内存要求

- 最低：8GB RAM + 6GB GPU VRAM
- 推荐：16GB RAM + 12GB GPU VRAM

### 4. 权限问题

如果遇到权限错误，尝试：
```bash
pip install --no-index --find-links=packages/ -r requirements-gpu.txt --user
```

---

## 🔧 常见问题

### Q: pip 安装失败，提示找不到包
A: 确保当前目录包含 `packages/` 文件夹，且命令中使用了 `--find-links=packages/` 参数。

### Q: torch 导入成功但 CUDA 不可用
A: 检查 CUDA 环境：`python -c "import torch; print(torch.cuda.is_available())"`。如果为 False，说明 PyTorch 版本与 CUDA 版本不匹配。

### Q: CosyVoice 加载失败
A: 确认 `models/iic/CosyVoice-300M-SFT/cosyvoice.yaml` 文件存在且完整。

---

## 📁 文件清单

| 文件/目录 | 大小 | 说明 |
|-----------|------|------|
| `src/` | ~30KB | 核心源码 |
| `CosyVoice/` | ~5MB | CosyVoice 代码 |
| `webui/` | ~5KB | WebUI |
| `packages/` | 352MB | 离线依赖包 |
| `models/` | 5.4GB | CosyVoice 模型 |

**总计：约 5.8GB**
