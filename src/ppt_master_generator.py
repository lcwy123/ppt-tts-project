#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PPT Master integration module — LLM generates SVG pages, svg_to_pptx converts to native PPTX.

Two entry points:
    run_ppt_master(outline_path)       — text path: read .docx outline, generate SVGs, convert
    run_ppt_master_multimodal(docx_path) — multimodal path: extract docx, generate SVGs, convert
"""

import os
import json
import tempfile
from pathlib import Path
from typing import Dict, Optional

from src.config import (
    get_llm_client, get_llm_model_name, OUTPUT_OUTLINE, OUTPUT_PPT,
    PPT_TEMPLATE_STYLE, LLM_MODE,
)
from src.ppt_master.svg_to_pptx import create_pptx_with_native_svg


# ---------------------------------------------------------------------------
# SVG generation prompt
# ---------------------------------------------------------------------------

SVG_CONVENTIONS = """SVG requirements for native PowerPoint conversion:
- viewBox="0 0 1280 720" (16:9 slide, NO exceptions)
- Use standard SVG elements: <rect>, <circle>, <path>, <text>, <image>, <line>, <polygon>
- Group logical regions with <g id="...">
- Text MUST use <text> elements with font-family="sans-serif"
- Use hex colors (#RRGGBB) or rgb() for all fills and strokes
- Keep text within safe margins (80px from edges)
- No <foreignObject>, no CSS @import, no JavaScript
- No <use> elements referencing external files
- Icons expressed as simple <path> or <circle>/<rect> shapes
- Output ONLY raw SVG code, no markdown code fences, no explanation"""


def _svg_prompt_raw(slide_title, slide_content, page_num, total_pages, color_scheme=None):
    """Build the LLM prompt for generating a slide SVG from raw (unsimplified) content.
    The LLM is instructed to first simplify the content, then design the SVG.
    """
    if color_scheme is None:
        color_scheme = {
            "primary": "#1F4E78",
            "accent": "#C00000",
            "bg": "#FAFAFA",
            "text": "#333333",
        }

    first_page_hint = ""
    last_page_hint = ""
    if page_num == 1:
        first_page_hint = (
            "This is the COVER page. Design a striking title slide with the document title "
            "and subtitle. Use dark primary-color background, large bold white title text."
        )
    if page_num == total_pages:
        last_page_hint = (
            "This is the ENDING page. Design a simple closing slide saying '谢谢观看' or similar, "
            "matching the cover style."
        )

    return f"""You are an expert PowerPoint designer. Create one SVG slide.

First, distill the raw content below into 3-5 key bullet points (each under 20 Chinese characters). Then design a professional SVG slide presenting the distilled points.

{first_page_hint}{last_page_hint}
Slide {page_num} of {total_pages}

TITLE: {slide_title}

RAW CONTENT (simplify to 3-5 bullets before designing):
{slide_content[:2000]}

DESIGN RULES:
- Primary: {color_scheme['primary']} | Accent: {color_scheme['accent']} | BG: {color_scheme['bg']} | Text: {color_scheme['text']}
- Professional modern style, generous whitespace, large readable fonts
- Title at top with accent bar or primary color block
{'- Dark background, title centered vertically' if page_num == 1 else ''}
{SVG_CONVENTIONS}

Output ONLY the raw SVG code, no markdown fences, no explanation."""


def _svg_prompt(slide_title, slide_content, page_num, total_pages, color_scheme=None):
    """Build the LLM prompt for generating a single slide SVG."""
    if color_scheme is None:
        color_scheme = {
            "primary": "#1F4E78",
            "accent": "#C00000",
            "bg": "#FAFAFA",
            "text": "#333333",
        }

    first_page_hint = ""
    last_page_hint = ""
    if page_num == 1:
        first_page_hint = (
            "This is the COVER page. Design a striking title slide with large title text, "
            "dark background with the primary color, and subtitle if present."
        )
    if page_num == total_pages:
        last_page_hint = (
            "This is the ENDING page. Design a simple closing slide with 'Thank you' or similar, "
            "matching the cover style."
        )

    return f"""Create a PowerPoint slide as a native SVG.

{first_page_hint}{last_page_hint}
Page {page_num} of {total_pages}

{{TITLE}}
{slide_title}

{{CONTENT}}
{slide_content[:1200]}

{{DESIGN SPEC}}
Primary color: {color_scheme['primary']}
Accent color: {color_scheme['accent']}
Background: {color_scheme['bg']}
Text color: {color_scheme['text']}
Style: professional, clean, modern. Large readable fonts. Good use of whitespace.

{{SVG_CONVENTIONS}}"""


def _call_llm_for_svg(prompt, progress_callback=None):
    """Call LLM to generate a slide SVG. Returns SVG text string."""
    client = get_llm_client()
    model = get_llm_model_name()

    system = (
        "You are an expert PowerPoint designer. You write SVG code that converts "
        "directly to native PowerPoint shapes. Your output is clean, well-structured SVG "
        "with proper viewBox, semantic grouping, and professional typography. "
        "You output ONLY raw SVG code — no markdown fences, no explanation."
    )

    try:
        if LLM_MODE == "api":
            response = client.messages.create(
                model=model,
                max_tokens=8192,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            svg = ""
            for block in response.content:
                if block.type == "text":
                    svg = block.text
                    break
        else:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )
            svg = response.choices[0].message.content or ""

        # Strip markdown fences if the LLM added them
        svg = svg.strip()
        if svg.startswith("```"):
            lines = svg.split("\n")
            # Remove first fence line
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Remove last fence line
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            svg = "\n".join(lines).strip()

        return svg if svg.startswith("<svg") else None

    except Exception as e:
        if progress_callback:
            progress_callback(f"LLM call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Outline parsing (reused from ppt_generator.py pattern)
# ---------------------------------------------------------------------------

def _parse_outline_docx(outline_path):
    """Parse Word outline into slide data list."""
    from docx import Document

    doc = Document(outline_path)
    slides = []
    current_slide = None

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        is_page_break = text.startswith("===") and "第" in text and "页" in text
        is_heading = para.style.name.startswith("Heading")
        is_title = para.style.name == "Title"

        if is_page_break or is_heading or is_title:
            if current_slide:
                slides.append(current_slide)
            current_slide = {"title": "", "bullets": []}
            if not is_page_break:
                current_slide["title"] = text
        elif para.style.name == "List Bullet" or text.startswith("- "):
            if current_slide is None:
                current_slide = {"title": "", "bullets": []}
            bullet = text[2:] if text.startswith("- ") else text
            current_slide["bullets"].append(bullet)
        else:
            if current_slide is None:
                current_slide = {"title": text, "bullets": []}
            else:
                current_slide["bullets"].append(text)

    if current_slide:
        slides.append(current_slide)

    return slides


def _slides_to_content(slides_data):
    """Convert parsed slides to text format for SVG prompts."""
    result = []
    for s in slides_data:
        content = "\n".join(f"- {b}" for b in s.get("bullets", []))
        result.append({
            "title": s.get("title", ""),
            "content": content,
        })
    return result


# ---------------------------------------------------------------------------
# SVG generation loop
# ---------------------------------------------------------------------------

def _generate_svgs(slide_items, work_dir, progress_callback=None):
    """Generate SVG for each slide item. Returns list of SVG file paths."""
    svg_files = []
    total = len(slide_items)

    for i, item in enumerate(slide_items):
        page_num = i + 1
        title = item.get("title", f"Slide {page_num}")
        content = item.get("content", "")

        if progress_callback:
            progress_callback(f"AI 设计第 {page_num}/{total} 页: {title[:30]}...")

        prompt = _svg_prompt(title, content, page_num, total)
        svg_text = _call_llm_for_svg(prompt, progress_callback)

        if svg_text:
            svg_path = work_dir / f"{page_num:02d}_{_safe_name(title)}.svg"
            svg_path.write_text(svg_text, encoding="utf-8")
            svg_files.append(svg_path)
            if progress_callback:
                progress_callback(f"  ✓ 第 {page_num} 页 SVG 已生成")
        else:
            if progress_callback:
                progress_callback(f"  ✗ 第 {page_num} 页 SVG 生成失败，跳过")

    return svg_files


def _safe_name(text):
    """Convert text to filename-safe token."""
    import re
    safe = re.sub(r"[^\w]", "_", text)[:30]
    return safe.strip("_") or "slide"


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def run_ppt_master(outline_path=None, progress_callback=None):
    """
    Generate PPT using ppt-master SVG→native-PPTX pipeline (text path).

    1. Parse Word outline
    2. LLM generates SVG per slide
    3. svg_to_pptx converts SVGs to native PPTX

    Returns output .pptx path.
    """
    if outline_path is None:
        outline_path = str(OUTPUT_OUTLINE)

    if not os.path.exists(outline_path):
        raise FileNotFoundError(f"提纲文件不存在: {outline_path}")

    if progress_callback:
        progress_callback("=" * 50)
        progress_callback("PPT Master 模式: AI 设计 + 原生形状生成")
        progress_callback("=" * 50)

    # Parse outline
    if progress_callback:
        progress_callback("解析提纲...")
    slides_data = _parse_outline_docx(outline_path)
    slide_items = _slides_to_content(slides_data)

    if progress_callback:
        progress_callback(f"共 {len(slide_items)} 页幻灯片")

    # Generate SVGs
    with tempfile.TemporaryDirectory(prefix="ppt_master_") as work_dir:
        work_path = Path(work_dir)
        svg_files = _generate_svgs(slide_items, work_path, progress_callback)

        if not svg_files:
            raise RuntimeError("没有成功生成任何SVG页面")

        if progress_callback:
            progress_callback(f"\n转换 SVG → 原生 PPTX ({len(svg_files)} 页)...")

        # Convert to PPTX
        output_path = Path(str(OUTPUT_PPT))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        create_pptx_with_native_svg(
            svg_files=svg_files,
            output_path=output_path,
            canvas_format="ppt169",
            use_native_shapes=True,
            use_compat_mode=True,
            transition=None,
            animation=None,
            enable_notes=False,
            verbose=False,
        )

    if progress_callback:
        progress_callback(f"✅ PPT Master 生成完成: {output_path}")

    return str(output_path)


def run_ppt_master_multimodal(docx_path=None, progress_callback=None):
    """
    Generate PPT using ppt-master from a Word document (multimodal path).

    Extracts docx content, builds slides_data, generates SVGs (with inline LLM
    simplification), converts to PPTX. Single LLM call per slide.
    """
    from src.docx_extractor import extract_from_docx
    from src.ppt_generator import build_slides_from_extracted

    if progress_callback:
        progress_callback("=" * 50)
        progress_callback("PPT Master 多模态模式: AI 设计 + 原生形状生成")
        progress_callback("=" * 50)

    # 1. Extract docx content
    if progress_callback:
        progress_callback("提取Word文档内容...")
    extracted_data = extract_from_docx(docx_path, progress_callback)

    # 2. Build slides data (no separate LLM simplification — SVG prompt handles it)
    if progress_callback:
        progress_callback("构建PPT页面结构...")
    slides_data = build_slides_from_extracted(extracted_data)

    # 3. Convert to prompt items with raw content
    slide_items = []
    for sd in slides_data:
        slide_items.append({
            "title": sd.get("title", ""),
            "content": sd.get("content", ""),
        })

    if progress_callback:
        progress_callback(f"共 {len(slide_items)} 页幻灯片")

    # 4. Generate SVGs (inline simplification + design in one LLM call per slide)
    with tempfile.TemporaryDirectory(prefix="ppt_master_mm_") as work_dir:
        work_path = Path(work_dir)
        svg_files = _generate_svgs_raw(slide_items, work_path, progress_callback)

        if not svg_files:
            raise RuntimeError("没有成功生成任何SVG页面")

        if progress_callback:
            progress_callback(f"\n转换 SVG → 原生 PPTX ({len(svg_files)} 页)...")

        output_path = Path(str(OUTPUT_PPT))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        create_pptx_with_native_svg(
            svg_files=svg_files,
            output_path=output_path,
            canvas_format="ppt169",
            use_native_shapes=True,
            use_compat_mode=True,
            transition=None,
            animation=None,
            enable_notes=False,
            verbose=False,
        )

    if progress_callback:
        progress_callback(f"✅ PPT Master 多模态生成完成: {output_path}")

    return str(output_path)


def _generate_svgs_raw(slide_items, work_dir, progress_callback=None):
    """Generate SVG for each slide using raw-content prompt (simplification inline)."""
    svg_files = []
    total = len(slide_items)

    for i, item in enumerate(slide_items):
        page_num = i + 1
        title = item.get("title", f"Slide {page_num}")
        content = item.get("content", "")

        if progress_callback:
            progress_callback(f"AI 设计第 {page_num}/{total} 页: {title[:40]}...")

        prompt = _svg_prompt_raw(title, content, page_num, total)
        svg_text = _call_llm_for_svg(prompt, progress_callback)

        if svg_text:
            svg_path = work_dir / f"{page_num:02d}_{_safe_name(title)}.svg"
            svg_path.write_text(svg_text, encoding="utf-8")
            svg_files.append(svg_path)
            if progress_callback:
                progress_callback(f"  ✓ 第 {page_num} 页完成")
        else:
            if progress_callback:
                progress_callback(f"  ✗ 第 {page_num} 页失败，跳过")

    return svg_files
