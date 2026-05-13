#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PPT生成模块 - 使用python-pptx生成PPTX
"""

import os
from pathlib import Path
from typing import Optional, Dict

from src.config import OUTPUT_OUTLINE, OUTPUT_PPT, PPT_TEMPLATE_STYLE


def generate_pptx_basic(outline_path: str, output_path: str, progress_callback=None) -> str:
    """
    使用传统python-pptx生成PPTX（兼容模式）
    """
    from docx import Document
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor

    if progress_callback:
        progress_callback("使用基础模式生成PPT...")

    # 解析提纲
    doc = Document(outline_path)
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

    if progress_callback:
        progress_callback(f"共 {len(slides)} 页幻灯片")

    # 创建PPT
    prs = Presentation()

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

    # 保存
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    prs.save(output_path)

    if progress_callback:
        progress_callback(f"✅ PPT已保存: {output_path}")

    return output_path


def run(outline_path: Optional[str] = None, progress_callback=None) -> str:
    """
    运行PPT生成

    Args:
        outline_path: 提纲文件路径，默认使用配置中的路径
        progress_callback: 进度回调函数

    Returns:
        生成的PPTX文件路径
    """
    if outline_path is None:
        outline_path = str(OUTPUT_OUTLINE)

    if not os.path.exists(outline_path):
        raise FileNotFoundError(f"提纲文件不存在: {outline_path}")

    output_path = str(OUTPUT_PPT)
    return generate_pptx_basic(outline_path, output_path, progress_callback)


def run_multimodal(docx_path: str, progress_callback=None) -> str:
    """
    从Word文档生成多模态PPT（支持图片和表格）

    Args:
        docx_path: Word文档路径
        progress_callback: 进度回调函数

    Returns:
        生成的PPTX文件路径
    """
    from src.docx_extractor import extract_from_docx
    from src.multimodal_outline_generator import run as run_multimodal_outline

    if progress_callback:
        progress_callback("=" * 50)
        progress_callback("多模态PPT生成")
        progress_callback("=" * 50)

    # 1. 提取Word文档内容
    if progress_callback:
        progress_callback("步骤1: 提取Word文档内容...")
    extracted_data = extract_from_docx(docx_path, progress_callback)
    if progress_callback:
        progress_callback(f"提取完成: {len(extracted_data.get('images', []))}张图片, {len(extracted_data.get('tables', []))}个表格")

    # 2. 生成多模态提纲（并生成slides_data）
    if progress_callback:
        progress_callback("步骤2: 生成PPT提纲...")
    outline_path, outline_text = run_multimodal_outline(extracted_data, progress_callback)
    if progress_callback:
        progress_callback(f"提纲已保存: {outline_path}")

    # 3. 从extracted_data构建slides_data（每页对应一个内容块）
    if progress_callback:
        progress_callback("步骤3: 构建PPT页面...")

    slides_data = build_slides_from_extracted(extracted_data)

    # 4. 精简提炼每页文字内容
    if progress_callback:
        progress_callback("步骤4: 精简提炼文字内容...")
    slides_data = simplify_slides_text(slides_data, progress_callback)

    # 5. 生成PPT
    if progress_callback:
        progress_callback("步骤5: 生成PPT...")

    output_path = str(OUTPUT_PPT)
    return generate_pptx_with_images(extracted_data, slides_data, output_path, progress_callback)


def simplify_slides_text(slides_data: list, progress_callback=None) -> list:
    """使用LLM精简提炼每页文字内容"""
    from src.config import get_llm_client, get_llm_model_name, LLM_MODE

    client = get_llm_client()
    model = get_llm_model_name()

    simplified_slides = []

    for slide in slides_data:
        # 跳过封面页和结束页
        if slide.get("is_cover") or slide.get("title") == "谢谢观看":
            simplified_slides.append(slide)
            continue

        title = slide.get("title", "")
        content = slide.get("content", "")
        images = slide.get("images", [])

        if not content or len(content) < 10:
            simplified_slides.append(slide)
            continue

        if progress_callback:
            progress_callback(f"  精简: {title[:20]}...")

        # 调用LLM精简内容
        prompt = f"""请将以下PPT页面的文字内容精简提炼，要求：
1. 保留3-5个核心要点
2. 每个要点简洁明了，不超过20字
3. 使用项目符号列出
4. 关键词加粗（用**包围，如：**关键词**）
5. 不要添加额外解释

页面标题：{title}

原始内容：
{content[:2000]}

精简后的内容（只需输出要点列表）："""

        try:
            if LLM_MODE == "api":
                response = client.messages.create(
                    model=model,
                    max_tokens=1024,
                    system="You are a helpful assistant that outputs concise bullet points.",
                    messages=[{"role": "user", "content": prompt}]
                )
                simplified = ""
                for block in response.content:
                    if block.type == 'text':
                        simplified = block.text
                        break
            else:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                )
                simplified = response.choices[0].message.content

            simplified_slides.append({
                "page_num": slide.get("page_num"),
                "title": title,
                "content": simplified,
                "images": images,
                "is_cover": False
            })
        except Exception as e:
            if progress_callback:
                progress_callback(f"  精简失败: {e}")
            simplified_slides.append(slide)

    return simplified_slides


def build_slides_from_extracted(extracted_data: Dict) -> list:
    """从提取的数据构建PPT幻灯片列表"""
    slides_data = []

    # 封面页
    title = extracted_data.get("title", "PPT")
    slides_data.append({
        "page_num": 1,
        "title": title,
        "content": "封面",
        "images": [],
        "is_cover": True
    })

    page_num = 2
    for block in extracted_data.get("slides", []):
        block_title = block.get("title", "")
        block_text = block.get("text", "")
        block_images = block.get("images", [])

        if not block_title:
            continue

        # 跳过纯标题
        if not block_text or block_text == block_title:
            continue

        slides_data.append({
            "page_num": page_num,
            "title": block_title,
            "content": block_text,
            "images": block_images,  # 直接使用该块关联的图片
            "is_cover": False
        })
        page_num += 1

    # 结束页
    slides_data.append({
        "page_num": page_num,
        "title": "谢谢观看",
        "content": "",
        "images": [],
        "is_cover": False
    })

    return slides_data


def parse_outline_for_multimodal(outline_text: str) -> list:
    """从提纲文本解析幻灯片数据"""
    import re
    import json

    slides = []
    current_slide = None

    lines = outline_text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 检查是否是页分隔符
        page_match = re.match(r'=== 第(\d+)页 ===', line)
        if page_match:
            if current_slide:
                slides.append(current_slide)
            page_num = int(page_match.group(1))
            current_slide = {
                "page_num": page_num,
                "title": "",
                "content": "",
                "images": []
            }
        elif current_slide is not None:
            # 检查是否是标题
            if line.startswith('# '):
                current_slide["title"] = line[2:].strip()
            elif line.startswith('📷 配图:'):
                # 提取图片ID
                img_part = line.replace('📷 配图:', '').strip()
                img_ids = [x.strip() for x in img_part.split(',') if x.strip()]
                current_slide["images"] = img_ids
            elif line.startswith('- '):
                current_slide["content"] += line[2:] + "\n"
            elif current_slide["title"] and not current_slide["content"]:
                current_slide["content"] = line

    if current_slide:
        slides.append(current_slide)

    return slides


def add_formatted_content(text_frame, content: str, text_color, font_size: int = 16):
    """向text_frame添加格式化内容，支持项目符号和加粗

    Args:
        text_frame: python-pptx TextFrame对象
        content: 文本内容
        text_color: 文字颜色 RGBColor
        font_size: 字体大小
    """
    from pptx.util import Pt
    from pptx.dml.color import RGBColor

    # 第一段（空白，用于初始化）
    p = text_frame.paragraphs[0]
    p.text = ""
    p.font.size = Pt(font_size)
    p.font.color.rgb = text_color

    lines = content.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 检查是否是项目符号行
        is_bullet = line.startswith('-') or line.startswith('*') or line.startswith('•')
        if is_bullet:
            line = line.lstrip('-*•').strip()

        # 检查是否有加粗标记 **
        if '**' in line:
            # 处理加粗文本
            parts = line.split('**')
            p = text_frame.add_paragraph()
            p.font.size = Pt(font_size)
            p.font.color.rgb = text_color
            p.space_before = Pt(4)

            if is_bullet:
                p.text = "• "
                run = p.add_run()
                run.text = ""
            else:
                run = p.add_run()
                run.text = ""

            for i, part in enumerate(parts):
                run = p.add_run()
                run.text = part
                if i % 2 == 1:  # 奇数索引是被**包围的关键词，需要加粗
                    run.font.bold = True
                run.font.size = Pt(font_size)
                run.font.color.rgb = text_color
        else:
            # 普通文本
            p = text_frame.add_paragraph()
            p.font.size = Pt(font_size)
            p.font.color.rgb = text_color
            p.space_before = Pt(4)

            if is_bullet:
                run = p.add_run()
                run.text = "• "
                run.font.size = Pt(font_size)
                run.font.color.rgb = text_color

            run = p.add_run()
            run.text = line
            run.font.size = Pt(font_size)
            run.font.color.rgb = text_color


def generate_pptx_with_images(extracted_data: Dict, slides_data: list, output_path: str, progress_callback=None) -> str:
    """
    生成带图片的PPT

    Args:
        extracted_data: docx_extractor提取的数据
        slides_data: 多模态提纲生成的幻灯片数据
        output_path: 输出路径
        progress_callback: 进度回调
    """
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    if progress_callback:
        progress_callback(f"开始生成PPT，共{len(slides_data)}页...")

    # 创建PPT
    prs = Presentation()

    # 幻灯片尺寸：10 x 7.5 英寸
    SLIDE_WIDTH = 10
    SLIDE_HEIGHT = 7.5

    DARK_BLUE = RGBColor(*PPT_TEMPLATE_STYLE["title_bg_color"])
    LIGHT_BLUE = RGBColor(*PPT_TEMPLATE_STYLE["content_bg_color"])
    WHITE = RGBColor(*PPT_TEMPLATE_STYLE["title_font_color"])
    TEXT_COLOR = RGBColor(*PPT_TEMPLATE_STYLE["content_font_color"])

    # 构建图片映射
    image_map = {img["id"]: img for img in extracted_data.get("images", [])}

    for i, slide in enumerate(slides_data):
        page_num = slide.get("page_num", i + 1)
        title = slide.get("title", "")
        content = slide.get("content", "").strip()
        image_ids = slide.get("images", [])
        is_cover = slide.get("is_cover", i == 0)

        if progress_callback:
            progress_callback(f"生成第 {page_num}/{len(slides_data)} 页: {title}")

        if i == 0:
            # 封面页 - 使用空白布局，从头构建
            slide_layout = prs.slide_layouts[6]  # 空白布局
            ppt_slide = prs.slides.add_slide(slide_layout)

            # 设置背景
            background = ppt_slide.background
            fill = background.fill
            fill.solid()
            fill.fore_color.rgb = DARK_BLUE

            # 添加标题
            title_left = Inches(0.5)
            title_top = Inches(2.5)
            title_width = Inches(9)
            title_height = Inches(1.5)

            title_box = ppt_slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
            tf = title_box.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = title
            p.font.size = Pt(44)
            p.font.bold = True
            p.font.color.rgb = WHITE
            p.alignment = PP_ALIGN.CENTER

            # 副标题
            if content:
                subtitle_box = ppt_slide.shapes.add_textbox(title_left, Inches(4.2), title_width, Inches(0.8))
                tf = subtitle_box.text_frame
                p = tf.paragraphs[0]
                p.text = content
                p.font.size = Pt(24)
                p.font.color.rgb = WHITE
                p.alignment = PP_ALIGN.CENTER
        else:
            # 内容页 - 使用空白布局
            slide_layout = prs.slide_layouts[6]  # 空白布局
            ppt_slide = prs.slides.add_slide(slide_layout)

            # 设置背景
            background = ppt_slide.background
            fill = background.fill
            fill.solid()
            fill.fore_color.rgb = LIGHT_BLUE

            # 标题栏背景 - 使用实际幻灯片宽度
            title_bg = ppt_slide.shapes.add_shape(
                1, Inches(0), Inches(0), Inches(SLIDE_WIDTH), Inches(1.0)
            )
            title_bg.fill.solid()
            title_bg.fill.fore_color.rgb = DARK_BLUE
            title_bg.line.fill.background()

            # 标题文字
            title_box = ppt_slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(9), Inches(0.6))
            tf = title_box.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = title
            p.font.size = Pt(28)
            p.font.bold = True
            p.font.color.rgb = WHITE

            # 内容区域布局
            if image_ids:
                # 有图片：左侧文字(60%)，右侧图片(40%)
                text_left = Inches(0.5)
                text_top = Inches(1.3)
                text_width = Inches(5.5)
                text_height = Inches(5.5)

                img_left = Inches(6.2)
                img_top = Inches(1.3)
                img_max_width = Inches(3.3)
                img_max_height = Inches(5.5)

                # 添加文字内容（支持项目符号和加粗）
                text_frame = ppt_slide.shapes.add_textbox(text_left, text_top, text_width, text_height)
                tf = text_frame.text_frame
                tf.word_wrap = True

                add_formatted_content(tf, content, TEXT_COLOR)

                # 添加图片 - 计算合适的大小和位置
                for img_id in image_ids[:1]:  # 只放第一张图片
                    if img_id in image_map:
                        img_path = image_map[img_id]["path"]
                        try:
                            # 使用PIL获取图片尺寸
                            from PIL import Image as PILImage
                            with PILImage.open(img_path) as img:
                                img_w, img_h = img.size
                                aspect_ratio = img_w / img_h

                            # 计算合适的尺寸（确保在img_max_width和img_max_height范围内）
                            available_width = img_max_width
                            available_height = img_max_height

                            # 使用浮点数计算比例
                            avail_w_in = available_width / 914400  # 转换为英寸
                            avail_h_in = available_height / 914400

                            if aspect_ratio > 1:
                                # 横版图片：按宽度缩放
                                final_width = available_width
                                final_height = int(avail_w_in / aspect_ratio * 914400)
                                if final_height > available_height:
                                    final_height = available_height
                                    final_width = int(avail_h_in * aspect_ratio * 914400)
                            else:
                                # 竖版图片：按高度缩放
                                final_height = available_height
                                final_width = int(avail_h_in * aspect_ratio * 914400)
                                if final_width > available_width:
                                    final_width = available_width
                                    final_height = int(avail_w_in / aspect_ratio * 914400)

                            # 居中放置图片
                            img_left_final = img_left + (img_max_width - final_width) // 2
                            img_top_final = img_top + (img_max_height - final_height) // 2

                            pic = ppt_slide.shapes.add_picture(
                                img_path,
                                img_left_final,
                                img_top_final,
                                width=final_width
                            )
                        except Exception as e:
                            if progress_callback:
                                progress_callback(f"  添加图片失败: {img_id}")
            else:
                # 无图片：全宽文字
                text_left = Inches(0.5)
                text_top = Inches(1.3)
                text_width = Inches(9)
                text_height = Inches(5.5)

                text_frame = ppt_slide.shapes.add_textbox(text_left, text_top, text_width, text_height)
                tf = text_frame.text_frame
                tf.word_wrap = True

                add_formatted_content(tf, content, TEXT_COLOR)

    # 保存
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    prs.save(output_path)

    if progress_callback:
        progress_callback(f"✅ PPT已保存: {output_path}")

    return output_path
