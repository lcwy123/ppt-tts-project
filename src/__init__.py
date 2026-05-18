#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ppt-tts-project 源码包
"""

from src.config import *
from src.outline_generator import run as run_outline
from src.ppt_generator import run as run_ppt, run_multimodal
from src.ppt_master_generator import run_ppt_master, run_ppt_master_multimodal
from src.slides_extractor import run as run_extract
from src.narration_generator import run as run_narration
from src.audio_generator import run as run_audio
from src.audio_embedder import run as run_embed
from src.backup import backup_old_output, restore_from_backup, list_backups
from src.docx_extractor import extract_from_docx, DocxExtractor

__all__ = [
    'run_outline',
    'run_ppt',
    'run_multimodal',
    'run_ppt_master',
    'run_ppt_master_multimodal',
    'run_extract',
    'run_narration',
    'run_audio',
    'run_embed',
    'backup_old_output',
    'restore_from_backup',
    'list_backups',
    'extract_from_docx',
    'DocxExtractor',
]
