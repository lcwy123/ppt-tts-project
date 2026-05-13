#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频嵌入PPT模块 - 嵌入音频到PPT并设置自动播放和自动翻页
"""

import os
import json
import re
import zipfile
import shutil
import tempfile
from pathlib import Path

from src.config import OUTPUT_PPT, INPUT_DIR, OUTPUT_DIR, OUTPUT_AUDIO_DURATIONS, OUTPUT_FINAL_PPT


def inject_narration(slide_xml, shape_id, shape_name, audio_rid, media_rid, poster_rid):
    """注入音频形状到slide XML"""
    # 音频形状模板
    audio_shape = f'''<p:sp>
      <p:nvSpPr>
        <p:cNvPr id="{shape_id}" name="{shape_name}"/>
        <p:cNvSpPr/>
        <p:nvPr/>
      </p:nvSpPr>
      <p:spPr>
        <a:xfrm>
          <a:off x="0" y="0"/>
          <a:ext cx="0" cy="0"/>
        </a:xfrm>
        <a:prstGeom prst="rect">
          <a:avLst/>
        </a:prstGeom>
        <a:noFill/>
        <a:nvSpPr/>
        <a:stCndn/>
      </p:spPr>
      <p:txBody>
        <a:bodyPr/>
        <a:lstStyle/>
        <a:p>
          <a:pPr/>
          <a:endParaRPr/>
        </a:p>
      </p:txBody>
      <mc:ADSH"
        xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
        xmlns:am3d="http://schemas.microsoft.com/office/drawing/2013/model3d"
        xmlns:od="http://schemas.microsoft.com/office/drawing/2012/annotation"
        xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main"
        xmlns:p15="http://schemas.microsoft.com/office/powerpoint/2012/main"
        xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
        xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
        xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"
        xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/main"
        xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        xmlns:p14md="http://schemas.microsoft.com/office/powerpoint/2014/markdown"
        xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main"
        xmlns:adobe="http://ns.adobe.com/AdobeDocument/1.0"
        xmlns:aq="http://schemas.authorwaver.com/2014/schemas/AQu vile"
        xmlns:aapi="http://schemas.authorware.com/XML映射/2014/Squirrel"
        xmlns:i="http://schemas.openxmlformats.org/drawingml/2006/image"
        xmlns:ds="http://schemas.openxmlformats.org/drawingml/2006/alternateContent"
        xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"
        xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram"
        xmlns:th="http://schemas.microsoft.com/office/threading/2011/excel"
        xmlns:s7="http://schemas.microsoft.com/office/powerpoint/2012/slidesource"
        xmlns:xlr="http://schemas.microsoft.com/Office/2019/relationxlr"
        xmlns:ve="http://schemas.openxmlformats.org/markup-compatibility/2006"
        xmlns:o="urn:schemas-microsoft-com:office:office"
        xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"
        xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
        xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
        xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml"
        xmlns:w16cex="http://schemas.microsoft.com/office/word/2018/wordml/cex"
        xmlns:w16cid="http://schemas.microsoft.com/office/word/2015/wordml/citex"
        xmlns:w16="http://schemas.microsoft.com/office/word/2018/wordml"
        xmlns:w16sdtdh="http://schemas.microsoft.com/office/word/2020/wordml/sdtdatahash"
        xmlns:w16se="http://schemas.microsoft.com/office/word/2015/wordml/symex"
        xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"
        xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk"
        xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml"
        xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
        xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas"
        xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
        xmlns:wps14ct="http://schemas.microsoft.com/office/word/2010/wordprocessingCT"
      </mc:ADSH>
      <p:nvAudioPr>
        <p:audioPr>
          <p:noPlay/>
        </p:audioPr>
        <p:nvPr/>
      </p:nvAudioPr>
    </p:sp>'''

    # 查找</p:spTree>的位置并插入音频形状
    if '</p:spTree>' in slide_xml:
        # 简化的音频形状插入
        audio_xml = f'''<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="{shape_id}" name="{shape_name}"/>
    <p:cNvSpPr/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm/>
    <a:prstGeom prst="rect">
      <a:avLst/>
    </a:prstGeom>
  </p:spPr>
  <p:txBody>
    <a:bodyPr/>
    <a:lstStyle/>
    <a:p>
      <a:pPr/>
      <a:endParaRPr/>
    </a:p>
  </p:txBody>
  <p:nvAudioPr>
    <p:audioPr>
      <p:noPlay/>
    </p:audioPr>
    <p:nvPr/>
  </p:nvAudioPr>
</p:sp>'''
        slide_xml = slide_xml.replace('</p:spTree>', f'{audio_xml}</p:spTree>')

    return slide_xml


def apply_recorded_timing(slide_xml, advance_after, transition_duration=0.5, transition_effect="fade"):
    """添加自动翻页timing到slide XML"""
    # 查找slide timing的CT_Timing元素
    if '<p:sldTrmLnk>' not in slide_xml and 'advanceAfter' not in slide_xml:
        # 插入slide timing
        timing_xml = f'''<p:sldTrmLnk>
          <p:stnLst>
            <p:stnNm>
              <p:stnNmVal>ClickTree</p:stnNmVal>
              <p:stnXmlSrc/>
            </p:stnNm>
          </p:stnLst>
          <p:bldLst>
            <p:bldP spid="0" grpId="0" animBg="1">
              <p:bldCond>
                <p:delay duration="0"/>
              </p:bldCond>
            </p:bldP>
          </p:bldLst>
          <p:sldSch>
            <p:sldSz cx="{9144000}" cy="{6858000}"/>
            <p:nodeTypes>
              <p:nvNode>
                <p:type value="0"/>
                <p:stCndn/>
              </p:nvNode>
              <p:nvNode>
                <p:type value="1"/>
                <p:stCndn/>
              </p:nvNode>
              <p:nvNode>
                <p:type value="2"/>
                <p:stCndn/>
              </p:nvNode>
            </p:nodeTypes>
          </p:sldSch>
        </p:sldTrmLnk>'''

        # 在</p:sldIdLst>之后插入timing
        if '</p:sldIdLst>' in slide_xml:
            slide_xml = slide_xml.replace('</p:sldIdLst>', f'</p:sldIdLst>{timing_xml}')

    return slide_xml


def load_audio_durations(file_path):
    """加载音频时长信息"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def embed_audio_with_auto_play(ppt_path: str, audio_dir: str, durations_path: str, output_path: str, progress_callback=None):
    """
    使用ppt-master的正确方式嵌入音频到PPT，设置自动播放和自动翻页
    """
    # 加载时长信息
    with open(durations_path, 'r', encoding='utf-8') as f:
        durations = json.load(f)
    
    audio_map = {item["slide_num"]: item for item in durations}
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        
        # 解压PPT
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
            
            # 确定slide文件
            slide_xml_path = extract_dir / "ppt" / "slides" / f"slide{slide_num}.xml"
            slide_rels_path = extract_dir / "ppt" / "slides" / "_rels" / f"slide{slide_num}.xml.rels"
            
            if not slide_xml_path.exists():
                continue
            
            # 读取slide XML
            with open(slide_xml_path, 'r', encoding='utf-8') as f:
                slide_xml = f.read()
            
            # 读取slide rels
            with open(slide_rels_path, 'r', encoding='utf-8') as f:
                slide_rels = f.read()
            
            # 生成新的relationship ID
            rid_matches = re.findall(r'Id="rId(\d+)"', slide_rels)
            next_rid = max([int(m) for m in rid_matches] or [0]) + 1
            audio_rid = f"rId{next_rid}"
            media_rid = f"rId{next_rid + 1}"
            poster_rid = f"rId{next_rid + 2}"
            
            # 复制音频文件到ppt/media目录
            # 使用slide_num来区分文件名，避免不同slide的文件被覆盖
            media_dir = extract_dir / "ppt" / "media"
            media_dir.mkdir(exist_ok=True)
            
            ext = audio_path.suffix.lower()
            if ext not in ['.mp3', '.m4a', '.wav']:
                ext = '.mp3'
            # 使用slide_num和next_rid组合来确保文件名唯一
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
            
            # 添加relationship - audio、media和poster
            # audio_rid: audioFile使用
            audio_rel = f'<Relationship Id="{audio_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/audio" Target="../media/{media_name}"/>'
            # media_rid: p14:media使用（Microsoft扩展）
            media_rel = f'<Relationship Id="{media_rid}" Type="http://schemas.microsoft.com/office/2007/relationships/media" Target="../media/{media_name}"/>'
            # poster_rid: blip使用
            poster_rel = f'<Relationship Id="{poster_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/{poster_name}"/>'
            
            slide_rels = slide_rels.replace('</Relationships>', f'{audio_rel}\n{media_rel}\n{poster_rel}\n</Relationships>')
            
            with open(slide_rels_path, 'w', encoding='utf-8') as f:
                f.write(slide_rels)
            
            # 生成shape ID
            shape_id_match = re.findall(r'id="(\d+)"', slide_xml)
            next_shape_id = max([int(m) for m in shape_id_match] or [0]) + 1
            
            # 使用ppt-master的inject_narration注入音频和自动播放
            slide_xml = inject_narration(
                slide_xml,
                shape_id=next_shape_id,
                shape_name=f"Audio {slide_num}",
                audio_rid=audio_rid,
                media_rid=media_rid,
                poster_rid=poster_rid
            )
            
            # 使用ppt-master的apply_recorded_timing添加自动翻页
            slide_xml = apply_recorded_timing(
                slide_xml,
                advance_after=duration,
                transition_duration=0.5,
                transition_effect="fade"
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
        
        # 重新打包PPT - 使用DEFLATED压缩确保兼容性
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
    
    # 确定PPT文件
    if ppt_path is None:
        generated_ppt = OUTPUT_PPT
        input_ppt = INPUT_DIR / "input.pptx"
        
        if generated_ppt.exists() and generated_ppt.stat().st_size > 0:
            ppt_path = generated_ppt
        elif input_ppt.exists() and input_ppt.stat().st_size > 0:
            ppt_path = input_ppt
        else:
            raise FileNotFoundError("未找到PPT文件")
    
    # 确定音频目录
    if audio_dir is None:
        audio_dir = OUTPUT_DIR / "audio"
    
    # 确定时长文件
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
