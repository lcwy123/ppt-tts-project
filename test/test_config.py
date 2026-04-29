#!/usr/bin/env python3
"""测试配置是否正确"""
import sys
sys.path.insert(0, '.')

from src.config import (
    PROJECT_ROOT, DATA_DIR, INPUT_DIR, OUTPUT_DIR, AUDIO_DIR, BACKUP_DIR,
    LLM_MODE, TTS_MODE, COSYVOICE_DIR
)

print("="*50)
print("配置检查")
print("="*50)
print(f"项目根目录: {PROJECT_ROOT}")
print(f"数据目录: {DATA_DIR}")
print(f"输入目录: {INPUT_DIR}")
print(f"输出目录: {OUTPUT_DIR}")
print(f"音频目录: {AUDIO_DIR}")
print(f"备份目录: {BACKUP_DIR}")
print(f"LLM模式: {LLM_MODE}")
print(f"TTS模式: {TTS_MODE}")
print(f"CosyVoice目录: {COSYVOICE_DIR}")
print()

# 检查目录
print("目录检查:")
for name, path in [("INPUT", INPUT_DIR), ("OUTPUT", OUTPUT_DIR), ("AUDIO", AUDIO_DIR), ("BACKUP", BACKUP_DIR)]:
    exists = "✓" if path.exists() else "✗"
    print(f"  {exists} {name}: {path}")

# 检查CosyVoice模型
print()
cosyvoice_model = COSYVOICE_DIR / "CosyVoice-300M-SFT"
if cosyvoice_model.exists():
    print(f"✓ CosyVoice模型已下载: {cosyvoice_model}")
    files = list(cosyvoice_model.glob("*"))
    print(f"  包含 {len(files)} 个文件/目录")
else:
    print(f"✗ CosyVoice模型未下载: {cosyvoice_model}")
    print(f"  请等待模型下载完成...")

print()
print("配置检查完成!")
