#!/bin/bash
# PPT-TTS-Project 启动脚本

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# 检查虚拟环境
VENV_BIN="$PROJECT_DIR/venv/bin/python"
if [ ! -f "$VENV_BIN" ]; then
    echo "错误: 虚拟环境不存在，请先运行:"
    echo "  python -m venv venv"
    echo "  venv/bin/pip install -r requirements.txt"
    exit 1
fi

# 解析命令行参数
MODE="${1:-webui}"
PORT="${2:-7860}"

case "$MODE" in
    webui)
        echo "🚀 启动 WebUI 模式..."
        echo "   访问地址: http://localhost:$PORT"
        echo "   按 Ctrl+C 停止"
        $VENV_BIN main.py --webui --port $PORT
        ;;
    cli)
        echo "🚀 启动 CLI 模式..."
        $VENV_BIN main.py
        ;;
    status)
        echo "📊 项目状态检查"
        echo ""
        echo "目录结构:"
        echo "  ✓ src/        - $(ls -1 src/*.py 2>/dev/null | wc -l) 个模块"
        echo "  ✓ test/       - $(ls -1 test/*.py 2>/dev/null | wc -l) 个测试"
        echo "  ✓ data/input/ - $(ls -1 data/input/ 2>/dev/null | wc -l) 个文件"
        echo "  ✓ data/output/- $(ls -1 data/output/ 2>/dev/null | wc -l) 个文件"
        echo "  ✓ data/audio/ - $(ls -1 data/audio/ 2>/dev/null | wc -l) 个文件"
        echo ""
        echo "模型状态:"
        if [ -d "models/iic/CosyVoice-300M-SFT" ]; then
            MODEL_SIZE=$(du -sh models/iic/CosyVoice-300M-SFT 2>/dev/null | cut -f1)
            echo "  ✓ CosyVoice模型已下载: $MODEL_SIZE"
        else
            echo "  ✗ CosyVoice模型未下载"
        fi
        ;;
    *)
        echo "用法: $0 [webui|cli|status] [port]"
        echo ""
        echo "示例:"
        echo "  $0 webui          # 启动WebUI (默认端口7860)"
        echo "  $0 webui 8080     # 启动WebUI (端口8080)"
        echo "  $0 cli            # 命令行模式"
        echo "  $0 status          # 查看项目状态"
        ;;
esac
