#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.absolute()

# 目录路径
DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
AUDIO_DIR = DATA_DIR / "audio"
BACKUP_DIR = DATA_DIR / "backup"
MODELS_DIR = PROJECT_ROOT / "models"
COSYVOICE_DIR = MODELS_DIR / "iic" / "CosyVoice-300M-SFT"
LOGS_DIR = PROJECT_ROOT / "logs"

# 确保目录存在
for dir_path in [DATA_DIR, INPUT_DIR, OUTPUT_DIR, AUDIO_DIR, BACKUP_DIR, LOGS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# LLM 配置
LLM_MODE = os.getenv("LLM_MODE", "local")  # local 或 api
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:30000/v1")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "Qwen3.5-9B")
LOCAL_LLM_API_KEY = os.getenv("LOCAL_LLM_API_KEY", "token-xxx")

# 火山方舟 API 配置
ARK_API_KEY = os.getenv("ARK_API_KEY", "")
ARK_MODEL = os.getenv("ARK_MODEL", "doubao-pro-32k")
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

# TTS 配置
TTS_MODE = os.getenv("TTS_MODE", "cosyvoice")  # cosyvoice, edge, api
EDGE_VOICE = os.getenv("EDGE_VOICE", "zh-CN-XiaoxiaoNeural")

# CosyVoice 配置
COSYVOICE_SPEAKER = os.getenv("COSYVOICE_SPEAKER", "ChineseFemale")
COSYVOICE_MODE = os.getenv("COSYVOICE_MODE", "sft")  # sft, naive, pretrained

# PPT 配置
PPT_TEMPLATE_STYLE = {
    "title_bg_color": (31, 78, 120),  # 深蓝色
    "content_bg_color": (240, 248, 255),  # 浅蓝色
    "title_font_color": (255, 255, 255),  # 白色
    "content_font_color": (51, 51, 51),  # 深灰色
    "title_font_size": 28,
    "content_font_size": 24,
}

# 默认文件路径
DEFAULT_INPUT_TEXT = INPUT_DIR / "input.txt"
DEFAULT_INPUT_PPT = INPUT_DIR / "input.pptx"
OUTPUT_OUTLINE = OUTPUT_DIR / "ppt_outline.docx"
OUTPUT_PPT = OUTPUT_DIR / "generated.pptx"
OUTPUT_SLIDES_TEXT = OUTPUT_DIR / "slides_text.txt"
OUTPUT_NARRATION = OUTPUT_DIR / "narration.txt"
OUTPUT_AUDIO_DURATIONS = OUTPUT_DIR / "audio_durations.json"
OUTPUT_FINAL_PPT = OUTPUT_DIR / "final_with_audio.pptx"

def get_llm_client():
    """获取LLM客户端"""
    if LLM_MODE == "local":
        from openai import OpenAI
        return OpenAI(
            api_key=LOCAL_LLM_API_KEY,
            base_url=LOCAL_LLM_URL,
        )
    else:
        from openai import OpenAI
        return OpenAI(
            api_key=ARK_API_KEY,
            base_url=ARK_BASE_URL,
        )

def get_llm_model_name():
    """获取LLM模型名称"""
    if LLM_MODE == "local":
        return LOCAL_LLM_MODEL
    else:
        return ARK_MODEL
