#!/usr/bin/env python3
"""
离线包下载脚本
在联网环境运行，将所有依赖下载到 packages/ 目录
目标环境：Python 3.10 + CUDA 12.6
"""

import os
import subprocess
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
PACKAGES_DIR = PROJECT_ROOT / "packages"

# 创建下载目录
PACKAGES_DIR.mkdir(exist_ok=True)

def run_pip_download(requirements_file: str, desc: str):
    """下载指定 requirements 文件中的所有包"""
    req_path = PROJECT_ROOT / requirements_file
    
    if not req_path.exists():
        print(f"[SKIP] {requirements_file} 不存在，跳过")
        return
    
    print(f"\n{'='*60}")
    print(f"📦 正在下载: {desc}")
    print(f"   文件: {requirements_file}")
    print(f"{'='*60}")
    
    # 构建下载命令
    cmd = [
        sys.executable, "-m", "pip", "download",
        "-r", str(req_path),
        "-d", str(PACKAGES_DIR),
        "--only-binary=:all:",
        "--python-version", "310",
        "--platform", "manylinux_2_17_x86_64",
        "--abi", "cp310",
        "--ignore-requires-python",
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[WARNING] 部分包下载失败，尝试不限制平台...")
            # 降级：允许源码包
            cmd_fallback = [
                sys.executable, "-m", "pip", "download",
                "-r", str(req_path),
                "-d", str(PACKAGES_DIR),
                "--python-version", "310",
                "--ignore-requires-python",
            ]
            result = subprocess.run(cmd_fallback, capture_output=True, text=True)
        
        # 统计下载数量
        downloaded = list(PACKAGES_DIR.glob("*"))
        print(f"✅ 下载完成，共 {len(downloaded)} 个文件")
        
    except Exception as e:
        print(f"[ERROR] 下载失败: {e}")

def download_torch_standalone():
    """单独下载 PyTorch（因为它有自己的下载逻辑）"""
    print(f"\n{'='*60}")
    print(f"📦 正在下载: PyTorch (CUDA 12.6)")
    print(f"{'='*60}")
    
    # PyTorch 需要从官方源下载
    cmd = [
        sys.executable, "-m", "pip", "download",
        "torch==2.4.0",
        "torchaudio==2.4.0",
        "--index-url", "https://download.pytorch.org/whl/cu126",
        "-d", str(PACKAGES_DIR),
        "--ignore-requires-python",
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, text=True)
        print("✅ PyTorch 下载完成")
    except Exception as e:
        print(f"[WARNING] PyTorch 下载失败: {e}")

def download_onnxruntime_gpu():
    """单独下载 ONNX Runtime GPU"""
    print(f"\n{'='*60}")
    print(f"📦 正在下载: ONNX Runtime GPU")
    print(f"{'='*60}")
    
    cmd = [
        sys.executable, "-m", "pip", "download",
        "onnxruntime-gpu==1.18.0",
        "--index-url", "https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/onnxruntime-cuda-12/pypi/simple/",
        "-d", str(PACKAGES_DIR),
        "--ignore-requires-python",
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, text=True)
        print("✅ ONNX Runtime GPU 下载完成")
    except Exception as e:
        print(f"[WARNING] ONNX Runtime GPU 下载失败: {e}")

def list_downloaded():
    """列出已下载的包"""
    print(f"\n{'='*60}")
    print(f"📋 已下载的包列表:")
    print(f"{'='*60}")
    
    files = sorted(PACKAGES_DIR.glob("*"))
    for f in files:
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {f.name} ({size_mb:.1f} MB)")
    
    print(f"\n总计: {len(files)} 个文件")
    total_size = sum(f.stat().st_size for f in files) / (1024 * 1024)
    print(f"总大小: {total_size:.1f} MB")

def main():
    print("=" * 60)
    print("🎯 PPT-TTS-Project 离线包下载工具")
    print("=" * 60)
    print(f"目标环境: Python 3.10 + CUDA 12.6")
    print(f"下载目录: {PACKAGES_DIR}")
    print()
    
    # 检查 pip 版本
    result = subprocess.run([sys.executable, "-m", "pip", "--version"], 
                          capture_output=True, text=True)
    print(f"Pip 版本: {result.stdout.strip()}")
    
    # 1. 下载 PyTorch（单独处理）
    download_torch_standalone()
    
    # 2. 下载 ONNX Runtime GPU（单独处理）
    download_onnxruntime_gpu()
    
    # 3. 下载其他 requirements
    run_pip_download("requirements-cpu.txt", "CPU 版本基础依赖")
    run_pip_download("requirements-gpu.txt", "GPU 版本基础依赖")
    run_pip_download("requirements-cosyvoice-minimal.txt", "CosyVoice 最小依赖")
    
    # 4. 下载 CosyVoice 自身 requirements
    cosyvoice_req = PROJECT_ROOT / "CosyVoice" / "requirements.txt"
    if cosyvoice_req.exists():
        run_pip_download("CosyVoice/requirements.txt", "CosyVoice 完整依赖")
    
    # 5. 列出下载结果
    list_downloaded()
    
    print("\n" + "=" * 60)
    print("✅ 下载完成!")
    print("=" * 60)
    print("\n下一步:")
    print(f"  1. 将 packages/ 目录复制到离线服务器")
    print(f"  2. 在服务器上运行: pip install --no-index --find-links=packages/ -r requirements-gpu.txt")

if __name__ == "__main__":
    main()
