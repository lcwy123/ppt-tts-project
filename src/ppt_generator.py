#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Word提纲转PPT模块
"""

import os
from pathlib import Path
from docx import Document
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from src.config import OUTPUT_OUTLINE, OUTPUT_PPT, PPT_TEMPLATE_STYLE


def parse_word_outline(doc_path):
    """解析Word文档中的PPT提纲"""
    
    doc = Document(doc_path)
    slides = []
    current_slide = None
    
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        
        is_page_break = text.startswith('===') and '第' in text and '页' in text
        is_heading_1 = para.style.name == 'Heading 1'
        is_title = para.style.name == 'Title'
        
        if is_page_break or is_heading_1 or is_title:
            if current_slide:
                slides.append(current_slide)
            current_slide = {"title": "", "bullets": []}
            if not is_page_break:
                current_slide["title"] = text
        elif para.style.name.startswith('Heading') or text.startswith('# '):
            if not current_slide:
                current_slide = {"title": "", "bullets": []}
            title = text[2:] if text.startswith('# ') else text
            current_slide["title"] = title
        elif para.style.name == 'List Bullet' or text.startswith('- '):
            if current_slide:
                bullet = text[2:] if text.startswith('- ') else text
                current_slide["bullets"].append(bullet)
        else:
            if not current_slide:
                current_slide = {"title": text, "bullets": []}
            else:
                current_slide["bullets"].append(text)
    
    if current_slide:
        slides.append(current_slide)
    
    return slides


def create_stylish_ppt(slides, output_path=None, progress_callback=None):
    """创建美化的PPT"""
    
    if output_path is None:
        output_path = OUTPUT_PPT
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    prs = Presentation()
    
    # 颜色配置
    DARK_BLUE = RGBColor(*PPT_TEMPLATE_STYLE["title_bg_color"])
    LIGHT_BLUE = RGBColor(*PPT_TEMPLATE_STYLE["content_bg_color"])
    WHITE = RGBColor(*PPT_TEMPLATE_STYLE["title_font_color"])
    TEXT_COLOR = RGBColor(*PPT_TEMPLATE_STYLE["content_font_color"])
    
    for i, slide_data in enumerate(slides):
        if i == 0:
            # 封面页
            slide_layout = prs.slide_layouts[0]
            slide = prs.slides.add_slide(slide_layout)
            
            background = slide.background
            fill = background.fill
            fill.solid()
            fill.fore_color.rgb = DARK_BLUE
            
            title = slide.shapes.title
            subtitle = slide.placeholders[1]
            
            title.text = slide_data["title"]
            title.text_frame.paragraphs[0].font.color.rgb = WHITE
            title.text_frame.paragraphs[0].font.bold = True
            title.text_frame.paragraphs[0].font.size = Pt(44)
            
            subtitle.text = "AI自动生成"
            subtitle.text_frame.paragraphs[0].font.color.rgb = WHITE
        else:
            # 内容页
            slide_layout = prs.slide_layouts[1]
            slide = prs.slides.add_slide(slide_layout)
            
            background = slide.background
            fill = background.fill
            fill.solid()
            fill.fore_color.rgb = LIGHT_BLUE
            
            # 标题栏
            title_box = slide.shapes.add_shape(
                1, Inches(0), Inches(0), Inches(10), Inches(0.8)
            )
            title_box.fill.solid()
            title_box.fill.fore_color.rgb = DARK_BLUE
            title_box.line.fill.background()
            
            # 标题文字
            title = slide.shapes.title
            title.text = slide_data["title"]
            title.top = Inches(0.1)
            title.left = Inches(0.5)
            title.width = Inches(9)
            title.height = Inches(0.6)
            title.text_frame.paragraphs[0].font.color.rgb = WHITE
            title.text_frame.paragraphs[0].font.bold = True
            title.text_frame.paragraphs[0].font.size = Pt(PPT_TEMPLATE_STYLE["title_font_size"])
            
            # 内容
            content = slide.placeholders[1]
            content.top = Inches(1.2)
            content.left = Inches(0.5)
            content.width = Inches(9)
            content.height = Inches(5)
            
            tf = content.text_frame
            tf.clear()
            
            for j, bullet in enumerate(slide_data["bullets"]):
                p = tf.add_paragraph()
                p.text = bullet
                p.font.size = Pt(PPT_TEMPLATE_STYLE["content_font_size"])
                p.font.color.rgb = TEXT_COLOR
                p.level = 0
                p.space_before = Pt(12)
        
        if progress_callback:
            progress_callback(f"生成第 {i+1}/{len(slides)} 页...")
    
    prs.save(output_path)
    
    if progress_callback:
        progress_callback(f"PPT已保存: {output_path}")
    
    return output_path


def run(outline_path=None, progress_callback=None):
    """运行完整流程：Word→PPT"""
    
    if outline_path is None:
        outline_path = OUTPUT_OUTLINE
    
    if not os.path.exists(outline_path):
        raise FileNotFoundError(f"提纲文件不存在: {outline_path}")
    
    if progress_callback:
        progress_callback("正在解析Word提纲...")
    
    slides = parse_word_outline(outline_path)
    
    if progress_callback:
        progress_callback(f"共解析到 {len(slides)} 页幻灯片")
    
    output_path = create_stylish_ppt(slides, progress_callback=progress_callback)
    
    return output_path, slides
