#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ppt-tts-project 源码包
"""

from src.config import *
from src.outline_generator import run as run_outline
from src.ppt_generator import run as run_ppt
from src.slides_extractor import run as run_extract
from src.narration_generator import run as run_narration
from src.audio_generator import run as run_audio
from src.audio_embedder import run as run_embed
from src.backup import backup_old_output, restore_from_backup, list_backups

__all__ = [
    'run_outline',
    'run_ppt',
    'run_extract',
    'run_narration',
    'run_audio',
    'run_embed',
    'backup_old_output',
    'restore_from_backup',
    'list_backups',
]
