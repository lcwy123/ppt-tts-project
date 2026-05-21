#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PPT Master integration module — LLM generates SVG pages, svg_to_pptx converts to native PPTX.

Two entry points:
    run_ppt_master(outline_path)       — text path: read .docx outline, generate SVGs, convert
    run_ppt_master_multimodal(docx_path) — multimodal path: extract docx, generate SVGs, convert
"""

import os
import re
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
- No <foreignObject>, no CSS @import, no JavaScript
- No <use> elements referencing external files
- Icons expressed as simple <path> or <circle>/<rect> shapes
- Output ONLY raw SVG code, no markdown code fences, no explanation

LAYOUT GRID (1280x720 canvas):
- TITLE ZONE: y=40 to y=130 (slide title, decorative accent bar)
- CONTENT ZONE: y=140 to y=640 (bullet points, images, tables, diagrams)
- FOOTER ZONE: y=650 to y=710 (page number, source line, small text)
- Left margin: x=60, Right margin: x=1220
- Text column (left): x=60-600. Graphics column (right): x=660-1220

COLLISION AVOIDANCE:
- Minimum 24px vertical gap between all text elements
- Minimum 20px horizontal gap between adjacent columns
- Background decorations (rects, circles behind text) must have 16px padding inside text bounds
- No two visible elements may share the same (x, y, width, height) region
- If content exceeds available height, reduce font size rather than overlapping
- Images must not overlap with text; place images beside (right column) or below text blocks

Z-ORDER (draw order in SVG, first=bottom, last=top):
- Layer 1 (bottom): Background fills, gradients, decorative large shapes
- Layer 2: Section dividers, accent bars, decorative lines
- Layer 3: Images, diagrams, tables
- Layer 4 (top): All text elements — must NEVER be obscured by other layers

TEXT RULES:
- Title font-size: 36-48px, bold, placed in TITLE ZONE
- Section heading font-size: 24-30px, bold
- Body text font-size: 18-22px, line spacing dy=28-32px
- Bullet text font-size: 16-20px
- Footer font-size: 14px, centered at y=690
- Max 5 bullet points per slide
- Text width limit: if text exceeds 560px, split into multiple <tspan> lines or truncate with ...
- Long words (over 40 chars): abbreviate or hyphenate
- text-anchor="start" for left-aligned, text-anchor="middle" for centered text"""


def _get_image_dimensions(image_path):
    """Return (width, height) in pixels for an image file, or (None, None) on failure."""
    try:
        from PIL import Image as PILImage
        with PILImage.open(image_path) as img:
            return img.size
    except Exception:
        return None, None


def _svg_prompt_raw(slide_title, slide_content, page_num, total_pages,
                    images=None, tables=None, color_scheme=None):
    """Build the LLM prompt for generating a slide SVG from raw (unsimplified) content.
    The LLM is instructed to first simplify the content, then design the SVG.
    images: list of absolute paths to image files available for this slide
    tables: list of table data (list of rows, each row a list of cell strings)
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

    cover_template = ""
    if page_num == 1:
        subtitle_text = slide_content.strip()[:50] if slide_content and slide_content.strip() else ""
        cover_template = f"""COVER LAYOUT:
<rect width="1280" height="720" fill="{color_scheme['primary']}"/>
<text x="640" y="310" font-size="52" font-weight="bold" fill="#FFFFFF" text-anchor="middle">{slide_title}</text>
<rect x="490" y="340" width="300" height="4" fill="{color_scheme['accent']}"/>
<text x="640" y="420" font-size="22" fill="rgba(255,255,255,0.85)" text-anchor="middle">{subtitle_text}</text>
"""

    # --- Image instructions ---
    image_block = ""
    if images:
        # Limit to max 6 images per slide to keep prompt manageable
        selected_images = images[:6]
        img_lines = []
        # Compute stacked y positions for images (start at y=180, 24px gap)
        img_y = 180
        for img_path in selected_images:
            w, h = _get_image_dimensions(img_path)
            if w and h:
                # Suggest scaled dimensions to fit right column (max 560x520)
                scale = min(560 / w, 520 / h, 1.0)
                sw, sh = int(w * scale), int(h * scale)
                img_lines.append(
                    f"  <image href='{img_path}' x='660' y='{img_y}' "
                    f"width='{sw}' height='{sh}' "
                    f"preserveAspectRatio='xMidYMid meet'/> "
                    f"(natural {w}x{h}px)"
                )
                img_y += sh + 24
            else:
                img_lines.append(
                    f"  <image href='{img_path}' x='660' y='{img_y}' "
                    f"width='500' height='375' "
                    f"preserveAspectRatio='xMidYMid meet'/>"
                )
                img_y += 375 + 24
        image_block = f"""
IMAGES TO INCLUDE ON THIS SLIDE:
{chr(10).join(img_lines)}

IMAGE PLACEMENT RULES:
- You MUST include at least some of these images (pick 1-4 that best illustrate the content)
- Use the EXACT href path shown above (absolute path, copy verbatim)
- Place in right column: x=660-1220, below the title area at y=180+
- Stack multiple images vertically with 24px gap between them
- Images are read-only references — keep preserveAspectRatio='xMidYMid meet'
- Keep 20px padding between images and slide edges or text
"""

    # --- Table instructions ---
    table_block = ""
    if tables:
        for ti, table_data in enumerate(tables):
            if not table_data:
                continue
            rows = len(table_data)
            cols = max(len(row) for row in table_data) if table_data else 0
            display_rows = min(rows, 5)
            display_cols = min(cols, 6)
            preview_lines = []
            for row in table_data[:display_rows]:
                cells = [str(cell)[:15] for cell in row[:display_cols]]
                preview_lines.append(" | ".join(cells))
            table_preview = "\n".join(preview_lines)
            table_block += f"""
TABLE {ti+1} ({display_rows}x{display_cols}, total {rows}x{cols}):
{table_preview}
"""

    if table_block:
        table_block = f"""
TABLES TO RENDER ON THIS SLIDE:{table_block}
TABLE RENDERING RULES:
- Render each table as SVG shapes (NOT as <image>): use <rect> for cell backgrounds, <line> or <path> for grid lines, <text> for cell text
- Table width: max 800px, place in the right column or centered below text
- Header row: {color_scheme['primary']} background with white bold text (font-size 15px)
- Data rows: alternating #F5F5F5 and #FFFFFF backgrounds, text font-size 14px
- Cell padding: 8px horizontal, 4px vertical; row height 28px
- Grid lines: 0.5px stroke, color #CCCCCC
- Truncate cell text to 15 characters per cell, use title for full text
"""

    return f"""You are an expert PowerPoint designer. Create one SVG slide.

First, distill the raw content below into 3-5 key bullet points (each under 20 Chinese characters). Then design a professional SVG slide presenting the distilled points.

{first_page_hint}{last_page_hint}
Slide {page_num} of {total_pages}

TITLE: {slide_title}

RAW CONTENT (simplify to 3-5 bullets before designing):
{slide_content[:2000]}
{image_block}{table_block}
DESIGN RULES:
- Primary: {color_scheme['primary']} | Accent: {color_scheme['accent']} | BG: {color_scheme['bg']} | Text: {color_scheme['text']}
- Professional modern style, generous whitespace, large readable fonts
- Title at top with accent bar or primary color block
{'- Dark background, title centered vertically' if page_num == 1 else ''}
{cover_template}

STRUCTURED LAYOUT (follow this structure precisely):
<svg viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <!-- Layer 1: Background -->
  <rect width="1280" height="720" fill="{color_scheme['bg']}"/>
  <!-- Layer 2: Decorative (accent bar at y=130, subtle corner shapes) -->
  <!-- Layer 3: Images / tables / diagrams (right column x=660-1220) -->
  <!-- Layer 4: Title text in TITLE ZONE (y=60-100, x=60, font-size 36-40) -->
  <!-- Layer 5: Content bullet points in CONTENT ZONE (y=170-580, x=60) -->
  <!-- Layer 6: Footer page number at y=690 centered -->
</svg>

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
        "CRITICAL: Your SVG MUST be valid XML. Escape all & as &amp; in text content. "
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

        # Strip XML declaration if present (<?xml version="1.0"?>)
        svg = re.sub(r'^<\?xml\b[^?]*\?>\s*', '', svg, flags=re.IGNORECASE).strip()

        if not svg.startswith("<svg"):
            return None

        # Validate and repair XML well-formedness (LLM often forgets to escape &)
        return _repair_svg_xml(svg, progress_callback)

    except Exception as e:
        if progress_callback:
            progress_callback(f"LLM call failed: {e}")
        return None


def _repair_svg_xml(svg_text, progress_callback=None):
    """Fix common XML well-formedness issues in LLM-generated SVG.

    Returns the repaired SVG string, or None if the SVG is beyond repair.
    """
    from xml.etree import ElementTree as ET

    # Quick check: already well-formed?
    try:
        ET.fromstring(svg_text)
        return svg_text
    except ET.ParseError:
        pass

    # Step 1: remove control characters
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', svg_text)

    # Step 2: fix unescaped & (not part of valid XML entities)
    cleaned = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#x?[0-9a-fA-F]+;)', '&amp;', cleaned)

    # Step 3: re-validate
    try:
        ET.fromstring(cleaned)
        if progress_callback:
            progress_callback("  ⚠ SVG XML 格式已自动修复（& 转义）")
        return cleaned
    except ET.ParseError as e:
        if progress_callback:
            progress_callback(f"  ⚠ SVG XML 修复后仍无效: {e}")
        # Extract <svg>...</svg> fragment as last resort
        m = re.search(r'<svg\b.*?</svg>', cleaned, re.DOTALL)
        if m:
            try:
                ET.fromstring(m.group(0))
                if progress_callback:
                    progress_callback("  ✓ 已提取有效 SVG 片段")
                return m.group(0)
            except ET.ParseError:
                pass
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
#  SVG layout validation
# ---------------------------------------------------------------------------


def _validate_svg_layout(svg_text, slide_num):
    """Check SVG for obvious layout issues. Returns list of warning strings (max 3)."""
    import re
    warnings = []

    if not svg_text.strip().startswith('<svg') and not svg_text.strip().startswith('<?xml'):
        warnings.append(f"Slide {slide_num}: SVG does not start with <svg>")
        return warnings

    vb_match = re.search(r'viewBox\s*=\s*["\']?0\s+0\s+(\d+)(?:\.\d+)?\s+(\d+)(?:\.\d+)?["\']?', svg_text)
    if vb_match:
        w, h = int(vb_match.group(1)), int(vb_match.group(2))
        if w != 1280 or h != 720:
            warnings.append(f"Slide {slide_num}: viewBox is {w}x{h}, expected 1280x720")

    # Strip <defs> blocks — they contain non-rendered template text
    clean_svg = re.sub(r'<defs\b[^>]*>.*?</defs>', '', svg_text, flags=re.DOTALL)
    text_positions = re.findall(
        r'<text\b[^>]*?\sx\s*=\s*["\']([\d.]+)["\'][^>]*?\sy\s*=\s*["\']([\d.]+)["\']',
        clean_svg
    )

    outlier_count = 0
    for x_str, y_str in text_positions:
        x, y = float(x_str), float(y_str)
        if x < 20 or x > 1260:
            outlier_count += 1
        if y < 20 or y > 700:
            outlier_count += 1

    if outlier_count > len(text_positions) * 0.5 and text_positions:
        warnings.append(
            f"Slide {slide_num}: {outlier_count}/{len(text_positions)} text elements "
            f"outside generous safe area — possible layout issue"
        )

    return warnings[:3]


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

    # 3. Convert to prompt items with raw content (preserve images and tables)
    slide_items = []
    for sd in slides_data:
        slide_items.append({
            "title": sd.get("title", ""),
            "content": sd.get("content", ""),
            "images": sd.get("images", []),
            "tables": sd.get("tables", []),
            "is_cover": sd.get("is_cover", False),
        })

    if progress_callback:
        progress_callback(f"共 {len(slide_items)} 页幻灯片")

    # 4. Generate SVGs (inline simplification + design in one LLM call per slide)
    with tempfile.TemporaryDirectory(prefix="ppt_master_mm_") as work_dir:
        work_path = Path(work_dir)
        svg_files = _generate_svgs_raw(slide_items, work_path, extracted_data, progress_callback)

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


def _generate_svgs_raw(slide_items, work_dir, extracted_data=None, progress_callback=None):
    """Generate SVG for each slide using raw-content prompt (simplification inline)."""
    from src.docx_extractor import get_image_by_id, get_table_by_id

    svg_files = []
    total = len(slide_items)

    for i, item in enumerate(slide_items):
        page_num = i + 1
        title = item.get("title", f"Slide {page_num}")
        content = item.get("content", "")
        image_ids = item.get("images", [])
        table_ids = item.get("tables", [])
        is_cover = item.get("is_cover", False)

        # Resolve image paths from extracted_data
        image_paths = []
        if extracted_data and image_ids:
            for img_id in image_ids:
                img_info = get_image_by_id(extracted_data, img_id)
                if img_info and os.path.exists(img_info["path"]):
                    image_paths.append(img_info["path"])

        # Resolve table data from extracted_data
        tables_for_slide = []
        if extracted_data and table_ids:
            for tbl_id in table_ids:
                tbl_info = get_table_by_id(extracted_data, tbl_id)
                if tbl_info and tbl_info.get("data"):
                    tables_for_slide.append(tbl_info["data"])

        if progress_callback:
            extra = ""
            if image_paths:
                extra += f" [图片:{len(image_paths)}张]"
            if tables_for_slide:
                extra += f" [表格:{len(tables_for_slide)}个]"
            progress_callback(f"AI 设计第 {page_num}/{total} 页: {title[:40]}...{extra}")

        prompt = _svg_prompt_raw(title, content, page_num, total,
                                 images=image_paths, tables=tables_for_slide)
        svg_text = _call_llm_for_svg(prompt, progress_callback)

        if svg_text:
            svg_path = work_dir / f"{page_num:02d}_{_safe_name(title)}.svg"
            svg_path.write_text(svg_text, encoding="utf-8")
            svg_files.append(svg_path)
            if progress_callback:
                progress_callback(f"  ✓ 第 {page_num} 页完成")
            # Layout validation (non-blocking)
            layout_warnings = _validate_svg_layout(svg_text, page_num)
            for w in layout_warnings:
                if progress_callback:
                    progress_callback(f"  ⚠ {w}")
        else:
            if progress_callback:
                progress_callback(f"  ✗ 第 {page_num} 页失败，跳过")

    return svg_files
