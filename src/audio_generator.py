#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频生成模块 - 支持CosyVoice本地TTS和Edge TTS
"""

import os
import re
import json
import asyncio
from pathlib import Path
from mutagen.mp3 import MP3
from src.config import (
    OUTPUT_NARRATION, OUTPUT_DIR, AUDIO_DIR, 
    TTS_MODE, COSYVOICE_DIR, COSYVOICE_SPEAKER, COSYVOICE_MODE,
    EDGE_VOICE
)


def load_narrations(file_path):
    """加载解说词"""
    
    narrations = []
    current_slide = 0
    current_content = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip()
            
            if line.startswith("=== 第"):
                if current_slide > 0:
                    narrations.append({
                        "slide_num": current_slide,
                        "text": "\n".join(current_content).strip()
                    })
                
                match = re.search(r'第\s*(\d+)\s*页', line)
                if match:
                    current_slide = int(match.group(1))
                else:
                    current_slide += 1
                current_content = []
            else:
                current_content.append(line)
        
        if current_slide > 0:
            narrations.append({
                "slide_num": current_slide,
                "text": "\n".join(current_content).strip()
            })
    
    return narrations


def generate_audio_cosyvoice(text, output_path, progress_callback=None):
    """使用本地CosyVoice生成音频"""
    
    try:
        import sys
        cosyvoice_root = str(Path(__file__).parent.parent / "CosyVoice")
        matcha_root = cosyvoice_root + "/third_party/Matcha-TTS"
        sys.path.insert(0, matcha_root)
        sys.path.insert(0, cosyvoice_root)
        from cosyvoice.cli.cosyvoice import CosyVoice
        
        if progress_callback:
            progress_callback(f"加载CosyVoice模型...")
        
        cosyvoice = CosyVoice(str(COSYVOICE_DIR))
        
        if progress_callback:
            progress_callback(f"正在生成音频...")
        
        # 生成音频
        output = cosyvoice.inference_sft(text, COSYVOICE_SPEAKER)

        # CosyVoice returns a generator, iterate to get result
        for item in output:
            tts_speech = item['tts_speech']

        # 保存 (使用soundfile，避免torchcodec依赖)
        import soundfile as sf
        sf.write(output_path, tts_speech.cpu().numpy().T, 22050)
        
        return True
        
    except ImportError as e:
        if progress_callback:
            progress_callback(f"CosyVoice导入失败: {e}")
        return False
    except Exception as e:
        if progress_callback:
            progress_callback(f"CosyVoice错误: {e}")
        return False


def generate_audio_edge(text, output_path, progress_callback=None):
    """使用微软Edge TTS生成音频"""
    
    try:
        import edge_tts
        
        async def generate():
            communicate = edge_tts.Communicate(text, EDGE_VOICE)
            await communicate.save(output_path)
        
        asyncio.run(generate())
        return True
        
    except ImportError:
        if progress_callback:
            progress_callback("edge-tts未安装，请运行: pip install edge-tts")
        return False
    except Exception as e:
        if progress_callback:
            progress_callback(f"Edge TTS错误: {e}")
        return False


def get_audio_duration(audio_path):
    """获取音频时长（秒）"""
    
    try:
        audio = MP3(audio_path)
        return audio.info.length
    except:
        return 0


def run(narration_path=None, tts_mode=None, progress_callback=None):
    """运行完整流程：生成音频"""
    
    if narration_path is None:
        narration_path = OUTPUT_NARRATION
    
    if not os.path.exists(narration_path):
        raise FileNotFoundError(f"解说词文件不存在: {narration_path}")
    
    if tts_mode is None:
        tts_mode = TTS_MODE
    
    if progress_callback:
        progress_callback(f"使用TTS模式: {tts_mode}")
        progress_callback("正在加载解说词...")
    
    narrations = load_narrations(narration_path)
    
    if progress_callback:
        progress_callback(f"共 {len(narrations)} 页解说词，开始生成音频...")
    
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    
    durations = []
    success_count = 0
    
    for item in narrations:
        slide_num = item["slide_num"]
        text = item["text"]
        audio_path = AUDIO_DIR / f"slide_{slide_num:03d}.mp3"
        
        if progress_callback:
            progress_callback(f"正在生成第 {slide_num} 页音频...")
        
        success = False
        
        if tts_mode == "cosyvoice":
            success = generate_audio_cosyvoice(text, str(audio_path), progress_callback)
        elif tts_mode == "edge":
            success = generate_audio_edge(text, str(audio_path), progress_callback)
        else:
            # API模式暂未实现
            if progress_callback:
                progress_callback(f"未知的TTS模式: {tts_mode}")
        
        if success and os.path.exists(audio_path):
            duration = get_audio_duration(str(audio_path))
            durations.append({
                "slide_num": slide_num,
                "duration": duration,
                "audio_path": str(audio_path)
            })
            if progress_callback:
                progress_callback(f"✓ 第 {slide_num} 页成功，时长: {duration:.2f}秒")
            success_count += 1
        else:
            if progress_callback:
                progress_callback(f"✗ 第 {slide_num} 页失败")
    
    # 保存时长信息
    durations_path = OUTPUT_DIR / "audio_durations.json"
    with open(durations_path, 'w', encoding='utf-8') as f:
        json.dump(durations, f, indent=2, ensure_ascii=False)
    
    if progress_callback:
        progress_callback(f"\n音频生成完成！成功: {success_count}/{len(narrations)}")
        progress_callback(f"时长信息已保存: {durations_path}")
    
    return durations_path, durations
