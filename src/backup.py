#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
备份工具模块
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from src.config import OUTPUT_DIR, BACKUP_DIR


def backup_old_output(progress_callback=None):
    """备份上次输出"""
    
    if not os.path.exists(OUTPUT_DIR):
        if progress_callback:
            progress_callback("输出目录不存在，无需备份")
        return None
    
    # 检查目录是否为空
    if not os.listdir(OUTPUT_DIR):
        if progress_callback:
            progress_callback("输出目录为空，无需备份")
        return None
    
    # 创建备份目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_DIR / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # 复制所有文件
    file_count = 0
    for item in os.listdir(OUTPUT_DIR):
        src_path = OUTPUT_DIR / item
        dst_path = backup_dir / item
        
        if src_path.is_file():
            shutil.copy2(src_path, dst_path)
            file_count += 1
            if progress_callback:
                progress_callback(f"已备份: {item}")
        elif src_path.is_dir():
            shutil.copytree(src_path, dst_path)
            file_count += 1
            if progress_callback:
                progress_callback(f"已备份目录: {item}")
    
    if progress_callback:
        progress_callback(f"\n✅ 备份完成！路径: {backup_dir}")
    
    return backup_dir


def restore_from_backup(backup_path, progress_callback=None):
    """从备份恢复"""
    
    backup_path = Path(backup_path)
    
    if not backup_path.exists():
        if progress_callback:
            progress_callback(f"备份目录不存在: {backup_path}")
        return False
    
    # 恢复到output目录
    for item in os.listdir(backup_path):
        src_path = backup_path / item
        dst_path = OUTPUT_DIR / item
        
        if src_path.is_file():
            shutil.copy2(src_path, dst_path)
            if progress_callback:
                progress_callback(f"已恢复: {item}")
        elif src_path.is_dir():
            if dst_path.exists():
                shutil.rmtree(dst_path)
            shutil.copytree(src_path, dst_path)
            if progress_callback:
                progress_callback(f"已恢复目录: {item}")
    
    if progress_callback:
        progress_callback(f"\n✅ 恢复完成！从: {backup_path}")
    
    return True


def list_backups(progress_callback=None):
    """列出所有备份"""
    
    if not BACKUP_DIR.exists():
        return []
    
    backups = sorted([d for d in BACKUP_DIR.iterdir() if d.is_dir()], reverse=True)
    
    if progress_callback:
        if backups:
            progress_callback("可用备份:")
            for b in backups:
                progress_callback(f"  - {b.name}")
        else:
            progress_callback("暂无备份")
    
    return backups
