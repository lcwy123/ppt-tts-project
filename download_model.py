#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CosyVoice 模型下载脚本

支持的下载方式:
1. ModelScope (推荐，国内速度快)
2. HuggingFace (备选)
3. 手动下载 (兜底)

使用方法:
    python download_model.py                    # 交互式选择
    python download_model.py --model sft        # 下载 SFT 模型
    python download_model.py --all              # 下载全部模型
    python download_model.py --check            # 仅检查模型状态

模型将下载到: models/iic/CosyVoice-300M-SFT/
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from typing import Optional, List, Dict

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.absolute()
MODELS_DIR = PROJECT_ROOT / "models"
COSYVOICE_MODEL_DIR = MODELS_DIR / "iic" / "CosyVoice-300M-SFT"

# CosyVoice 模型 ID (ModelScope)
MODELSCOPE_ID = "iic/CosyVoice-300M-SFT"

# HuggingFace 地址
HF_REPO = "https://huggingface.co/csukuangfj/CosyVoice-300M-SFT"
HF_FILES = [
    "cosyvoice.yaml",
    "llm.pt",
    "flow.pt",
    "hift.pt",
    "campplus.onnx",
    "speech_tokenizer_v1.onnx",
    "spk2info.pt",
]


def get_installed_models() -> Dict[str, bool]:
    """检查已安装的模型文件"""
    files = {
        "cosyvoice.yaml": False,
        "llm.pt": False,
        "flow.pt": False,
        "hift.pt": False,
        "campplus.onnx": False,
        "speech_tokenizer_v1.onnx": False,
        "spk2info.pt": False,
    }
    
    if not COSYVOICE_MODEL_DIR.exists():
        return files
    
    for fname in files:
        fpath = COSYVOICE_MODEL_DIR / fname
        files[fname] = fpath.exists() and fpath.stat().st_size > 0
    
    return files


def check_models_complete() -> bool:
    """检查模型是否完整"""
    files = get_installed_models()
    missing = [f for f, exists in files.items() if not exists]
    
    if missing:
        print(f"❌ 缺少文件: {', '.join(missing)}")
        return False
    else:
        print("✅ 模型文件完整")
        return True


def download_via_modelscope(model_dir: Path) -> bool:
    """通过 ModelScope 下载模型（推荐，国内速度快）"""
    print("\n" + "=" * 60)
    print("📦 方式一: ModelScope 下载 (推荐)")
    print("=" * 60)
    
    try:
        from modelscope import snapshot_download
        
        print(f"\n开始下载: {MODELSCOPE_ID}")
        print(f"目标路径: {model_dir}")
        print("首次下载需要下载模型文件，请耐心等待...\n")
        
        # 使用 snapshot_download 自动下载整个模型目录
        local_dir = snapshot_download(
            MODELSCOPE_ID,
            cache_dir=str(PROJECT_ROOT / "models"),
            revision="master"
        )
        
        # 如果下载位置不是目标位置，创建链接或复制
        if Path(local_dir) != model_dir:
            print(f"\n模型已下载到: {local_dir}")
            print(f"需要移动到: {model_dir}")
            
            # 创建目标目录
            model_dir.parent.mkdir(parents=True, exist_ok=True)
            
            # 使用符号链接（推荐）或复制
            if model_dir.exists():
                print(f"目标目录已存在，跳过")
            else:
                try:
                    os.symlink(local_dir, model_dir)
                    print(f"已创建符号链接: {model_dir} -> {local_dir}")
                except OSError:
                    # 符号链接失败，使用复制
                    import shutil
                    shutil.copytree(local_dir, model_dir)
                    print(f"已复制到: {model_dir}")
        
        print("\n✅ ModelScope 下载完成!")
        return True
        
    except ImportError:
        print("❌ modelscope 未安装，请运行: pip install modelscope")
        return False
    except Exception as e:
        print(f"❌ ModelScope 下载失败: {e}")
        return False


def download_via_huggingface(model_dir: Path) -> bool:
    """通过 HuggingFace 下载模型"""
    print("\n" + "=" * 60)
    print("📦 方式二: HuggingFace 下载")
    print("=" * 60)
    
    model_dir.mkdir(parents=True, exist_ok=True)
    
    # 检查 git-lfs
    try:
        subprocess.run(["git-lfs", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️ git-lfs 未安装，尝试安装...")
        try:
            subprocess.run(["pip", "install", "git-lfs"], check=True)
            subprocess.run(["git-lfs", "install"], check=True)
        except:
            print("❌ git-lfs 安装失败，请手动安装: https://git-lfs.com")
            return False
    
    # 使用 git clone
    cmd = [
        "git", "clone",
        "https://huggingface.co/csukuangfj/CosyVoice-300M-SFT",
        str(model_dir),
        "--depth", "1"  # 浅克隆
    ]
    
    print(f"\n执行: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("\n✅ HuggingFace 下载完成!")
            return True
        else:
            print(f"❌ 下载失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ 下载异常: {e}")
        return False


def download_via_wget(model_dir: Path) -> bool:
    """通过 wget/curl 单文件下载（兜底方案）"""
    print("\n" + "=" * 60)
    print("📦 方式三: wget/curl 单文件下载 (兜底)")
    print("=" * 60)
    
    model_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n目标路径: {model_dir}")
    print("\n请手动下载以下文件:")
    print(f"\n访问: {HF_REPO}")
    print("\n需要下载的文件:")
    for f in HF_FILES:
        print(f"  - {f}")
    
    print(f"\n下载命令示例:")
    print(f"  mkdir -p {model_dir}")
    print(f"  cd {model_dir}")
    print(f"  wget {HF_REPO}/resolve/main/cosyvoice.yaml")
    print(f"  wget {HF_REPO}/resolve/main/llm.pt")
    print(f"  ...")
    
    return False  # 需要手动操作


def download_all_models():
    """下载所有模型"""
    print("=" * 60)
    print("🎯 CosyVoice 模型批量下载")
    print("=" * 60)
    
    # 检查现有状态
    installed = get_installed_models()
    complete = check_models_complete()
    
    if complete:
        print("\n模型已完整安装，无需下载")
        return True
    
    # 尝试 ModelScope（国内推荐）
    if download_via_modelscope(COSYVOICE_MODEL_DIR):
        return True
    
    # 降级到 HuggingFace
    if download_via_huggingface(COSYVOICE_MODEL_DIR):
        return True
    
    # 兜底手动下载
    download_via_wget(COSYVOICE_MODEL_DIR)
    return False


def download_sft_model():
    """下载 CosyVoice-300M-SFT 模型"""
    print("=" * 60)
    print("🎯 下载 CosyVoice-300M-SFT")
    print("=" * 60)
    
    # 先检查
    if check_models_complete():
        print("\n模型已存在，无需重复下载")
        return True
    
    # 优先 ModelScope
    if download_via_modelscope(COSYVOICE_MODEL_DIR):
        return True
    
    # 降级 HuggingFace
    if download_via_huggingface(COSYVOICE_MODEL_DIR):
        return True
    
    # 手动
    download_via_wget(COSYVOICE_MODEL_DIR)
    return False


def check_status():
    """检查模型状态"""
    print("=" * 60)
    print("🔍 CosyVoice 模型状态检查")
    print("=" * 60)
    print(f"\n模型目录: {COSYVOICE_MODEL_DIR}")
    
    files = get_installed_models()
    print("\n文件状态:")
    for fname, exists in files.items():
        status = "✅" if exists else "❌"
        print(f"  {status} {fname}")
    
    complete = all(files.values())
    print()
    if complete:
        print("✅ 模型完整，可以正常使用")
    else:
        missing = [f for f, e in files.items() if not e]
        print(f"❌ 缺少 {len(missing)} 个文件，需要下载")
        print("\n运行以下命令下载:")
        print("  python download_model.py")
    
    return complete


def main():
    parser = argparse.ArgumentParser(
        description="CosyVoice 模型下载工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python download_model.py                    # 交互式下载 SFT 模型
  python download_model.py --check             # 仅检查模型状态
  python download_model.py --all               # 下载全部模型
  python download_model.py --model sft         # 下载 SFT 模型
        """
    )
    
    parser.add_argument(
        "--model", "-m",
        choices=["sft", "instruct", "pretrained"],
        default="sft",
        help="选择要下载的模型 (默认: sft)"
    )
    
    parser.add_argument(
        "--check", "-c",
        action="store_true",
        help="仅检查模型状态，不下载"
    )
    
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="下载全部模型"
    )
    
    parser.add_argument(
        "--method",
        choices=["modelscope", "huggingface", "wget"],
        help="指定下载方式 (默认自动选择)"
    )
    
    args = parser.parse_args()
    
    # 检查模式
    if args.check:
        success = check_status()
        sys.exit(0 if success else 1)
    
    # 下载模式
    print()
    if args.all:
        success = download_all_models()
    else:
        success = download_sft_model()
    
    # 最终检查
    print("\n" + "=" * 60)
    print("📋 最终状态")
    print("=" * 60)
    check_status()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
