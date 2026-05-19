#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频嵌入PPT模块 - 嵌入音频到PPT并设置自动播放和自动翻页
使用 ppt-master 的 pptx_narration 模块进行正确的 OOXML 注入
"""

import os
import json
import re
import zipfile
import shutil
import tempfile
from pathlib import Path

from src.config import OUTPUT_PPT, INPUT_DIR, OUTPUT_DIR, OUTPUT_AUDIO_DURATIONS, OUTPUT_FINAL_PPT
from src.ppt_master.svg_to_pptx.pptx_narration import (
    inject_narration,
    apply_recorded_timing,
    next_shape_id,
)


def load_audio_durations(file_path):
    """加载音频时长信息"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def embed_audio_with_auto_play(ppt_path: str, audio_dir: str, durations_path: str,
                                output_path: str, progress_callback=None):
    """
    嵌入音频到PPT并设置自动播放和自动翻页
    """
    with open(durations_path, 'r', encoding='utf-8') as f:
        durations = json.load(f)

    audio_map = {item["slide_num"]: item for item in durations}

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)

        ppt_name = Path(ppt_path).stem
        extract_dir = temp_dir / ppt_name
        with zipfile.ZipFile(ppt_path, 'r') as z:
            z.extractall(extract_dir)

        if progress_callback:
            progress_callback(f"PPT共 {len(audio_map)} 页，开始嵌入音频...")

        embedded_count = 0

        for slide_num, audio_info in audio_map.items():
            audio_rel_path = audio_info["audio_path"]
            audio_path = Path(audio_rel_path)

            if not audio_path.exists():
                audio_path = Path(audio_dir) / audio_path.name

            if not audio_path.exists():
                if progress_callback:
                    progress_callback(f"第 {slide_num} 页音频文件不存在")
                continue

            duration = audio_info["duration"]

            slide_xml_path = extract_dir / "ppt" / "slides" / f"slide{slide_num}.xml"
            slide_rels_path = extract_dir / "ppt" / "slides" / "_rels" / f"slide{slide_num}.xml.rels"

            if not slide_xml_path.exists():
                continue

            with open(slide_xml_path, 'r', encoding='utf-8') as f:
                slide_xml = f.read()

            with open(slide_rels_path, 'r', encoding='utf-8') as f:
                slide_rels = f.read()

            # 生成新的relationship ID
            rid_matches = re.findall(r'Id="rId(\d+)"', slide_rels)
            next_rid = max([int(m) for m in rid_matches] or [0]) + 1
            audio_rid = f"rId{next_rid}"
            media_rid = f"rId{next_rid + 1}"
            poster_rid = f"rId{next_rid + 2}"

            # 复制音频文件到ppt/media目录
            media_dir = extract_dir / "ppt" / "media"
            media_dir.mkdir(exist_ok=True)

            ext = audio_path.suffix.lower()
            if ext not in ['.mp3', '.m4a', '.wav']:
                ext = '.mp3'
            media_name = f"media{slide_num}{ext}"
            media_path = media_dir / media_name
            shutil.copy2(audio_path, media_path)

            # 生成透明1x1 PNG作为poster
            transparent_png = (
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
                b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
                b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
                b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
            )
            poster_name = f"media{slide_num}_poster.png"
            poster_path = media_dir / poster_name
            poster_path.write_bytes(transparent_png)

            # 添加relationship
            audio_rel = f'<Relationship Id="{audio_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/audio" Target="../media/{media_name}"/>'
            media_rel = f'<Relationship Id="{media_rid}" Type="http://schemas.microsoft.com/office/2007/relationships/media" Target="../media/{media_name}"/>'
            poster_rel = f'<Relationship Id="{poster_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/{poster_name}"/>'

            slide_rels = slide_rels.replace('</Relationships>',
                                            f'{audio_rel}\n{media_rel}\n{poster_rel}\n</Relationships>')

            with open(slide_rels_path, 'w', encoding='utf-8') as f:
                f.write(slide_rels)

            # 使用 ppt-master 的正确注入函数
            shape_id = next_shape_id(slide_xml)
            slide_xml = inject_narration(
                slide_xml,
                shape_id=shape_id,
                shape_name=f"Audio {slide_num}",
                audio_rid=audio_rid,
                media_rid=media_rid,
                poster_rid=poster_rid,
            )

            slide_xml = apply_recorded_timing(
                slide_xml,
                advance_after=duration,
                transition_duration=0.5,
                transition_effect="fade",
            )

            with open(slide_xml_path, 'w', encoding='utf-8') as f:
                f.write(slide_xml)

            embedded_count += 1
            if progress_callback:
                progress_callback(f"嵌入第 {slide_num} 页音频 (时长: {duration:.1f}秒)")

        # 更新[Content_Types].xml
        content_types_path = extract_dir / "[Content_Types].xml"
        with open(content_types_path, 'r', encoding='utf-8') as f:
            content_types = f.read()

        if 'Extension="mp3"' not in content_types:
            content_types = content_types.replace('</Types>',
                '<Default Extension="mp3" ContentType="audio/mpeg"/>\n</Types>')

        if 'Extension="png"' not in content_types:
            content_types = content_types.replace('</Types>',
                '<Default Extension="png" ContentType="image/png"/>\n</Types>')

        with open(content_types_path, 'w', encoding='utf-8') as f:
            f.write(content_types)

        # 重新打包PPT
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = str(file_path.relative_to(extract_dir))
                    z.write(file_path, arcname)

        return embedded_count


def run(ppt_path=None, durations_path=None, audio_dir=None, progress_callback=None):
    """运行完整流程：嵌入音频到PPT"""

    if ppt_path is None:
        generated_ppt = OUTPUT_PPT
        input_ppt = INPUT_DIR / "input.pptx"

        if generated_ppt.exists() and generated_ppt.stat().st_size > 0:
            ppt_path = generated_ppt
        elif input_ppt.exists() and input_ppt.stat().st_size > 0:
            ppt_path = input_ppt
        else:
            raise FileNotFoundError("未找到PPT文件")

    if audio_dir is None:
        audio_dir = OUTPUT_DIR / "audio"

    if durations_path is None:
        durations_path = OUTPUT_AUDIO_DURATIONS

    if not os.path.exists(durations_path):
        raise FileNotFoundError(f"音频时长文件不存在: {durations_path}")

    if progress_callback:
        progress_callback("正在嵌入音频...")

    output_path = OUTPUT_FINAL_PPT
    embedded_count = embed_audio_with_auto_play(
        str(ppt_path),
        str(audio_dir),
        str(durations_path),
        str(output_path),
        progress_callback
    )

    if progress_callback:
        progress_callback(f"\n✅ 音频嵌入完成！成功嵌入 {embedded_count} 页")
        progress_callback(f"📁 最终PPT: {output_path}")
        progress_callback("💡 提示：在PowerPoint中打开时，按F5放映，音频将自动播放，每页将根据音频时长自动翻页")

    return output_path, embedded_count
