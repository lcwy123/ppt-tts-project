#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Word文档解析模块 - 提取文字、图片、表格
按标题层级组织内容，确保图文对应
"""

import os
import uuid
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from lxml import etree

from src.config import OUTPUT_DIR


class DocxExtractor:
    """Word文档提取器"""

    def __init__(self, docx_path: str):
        self.docx_path = Path(docx_path)
        self.doc = Document(docx_path)

        # 输出目录
        self.output_dir = OUTPUT_DIR / "extracted"
        self.images_dir = self.output_dir / "images"
        self.tables_dir = self.output_dir / "tables"

        # 初始化目录
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.tables_dir.mkdir(parents=True, exist_ok=True)

        # 存储提取的数据
        self.images: List[Dict] = []
        self.tables: List[Dict] = []
        self.content_blocks: List[Dict] = []

        # 去重：已处理过的 embed 关系ID
        self._seen_embeds: set = set()

        # 当前标题上下文
        self._current_h1 = None
        self._current_h2 = None
        self._current_h3 = None
        self._current_block = None

        # 待处理的图片（还未确定归属的）
        self._pending_images: List[str] = []

    def _clean_extracted_dir(self):
        """清空提取目录，避免上次运行的残留文件混入。"""
        if self.images_dir.exists():
            for f in self.images_dir.iterdir():
                f.unlink()
        if self.tables_dir.exists():
            for f in self.tables_dir.iterdir():
                f.unlink()

    def extract_all(self, progress_callback=None) -> Dict[str, Any]:
        """提取Word文档的所有内容"""
        self._clean_extracted_dir()

        if progress_callback:
            progress_callback("开始解析Word文档...")

        title = self._extract_title()

        if progress_callback:
            progress_callback("正在提取文字内容...")

        # 一次性提取所有内容和图片
        self._extract_content_with_images()

        if progress_callback:
            progress_callback("正在提取表格...")
        self._extract_tables()

        # 保存最后一个块
        if self._current_block:
            self.content_blocks.append(self._current_block)

        if progress_callback:
            progress_callback(f"提取完成：{len(self.images)}张图片，{len(self.tables)}个表格")

        return {
            "title": title,
            "slides": self.content_blocks,
            "images": self.images,
            "tables": self.tables
        }

    def _extract_title(self) -> str:
        """提取文档标题，优先级：
        1. docx core properties (dc:title)
        2. Title 样式段落
        3. 第一个章节标题之前的首个非空段落
        4. 第一个章节标题段落
        5. 第一个非空段落
        6. 文件名 stem
        """
        # Priority 1: Docx core properties title
        try:
            core_title = self.doc.core_properties.title
            if core_title and core_title.strip():
                return core_title.strip()
        except Exception:
            pass

        # Priority 2: Title-styled paragraph
        for para in self.doc.paragraphs:
            if para.style.name == 'Title' and para.text.strip():
                return para.text.strip()

        def _is_heading_style(style_name):
            return (style_name.startswith('Heading')
                    or '章标题' in style_name
                    or '条标题' in style_name
                    or style_name == 'Title')

        # Priority 3: First non-empty paragraph BEFORE any heading
        for para in self.doc.paragraphs:
            text = para.text.strip()
            if _is_heading_style(para.style.name):
                break
            if text:
                return text

        # Priority 4: First heading paragraph
        for para in self.doc.paragraphs:
            if _is_heading_style(para.style.name) and para.text.strip():
                return para.text.strip()

        # Priority 5: First non-empty paragraph (anywhere)
        for para in self.doc.paragraphs:
            text = para.text.strip()
            if text:
                return text

        # Priority 6: Filename stem
        return self.docx_path.stem

    def _get_heading_level(self, style_name: str) -> Optional[int]:
        """获取标题级别"""
        if style_name == 'Title':
            return 0
        if 'Heading 1' in style_name or '标题 1' in style_name:
            return 1
        if 'Heading 2' in style_name or '标题 2' in style_name:
            return 2
        if 'Heading 3' in style_name or '标题 3' in style_name:
            return 3

        # 自定义标题样式 - 标准文件模板
        if '章标题' in style_name:
            return 1
        if '一级条标题' in style_name:
            return 2
        if '二级条标题' in style_name:
            return 3
        if '三级条标题' in style_name:
            return 4

        # toc样式
        if style_name.startswith('toc '):
            level = style_name[-1]
            if level.isdigit():
                return int(level) - 1

        if '目次标题' in style_name or '目录' in style_name:
            return 1

        return None

    def _start_new_block(self, heading_text: str, level: int):
        """开始一个新的内容块"""
        # 保存之前的块（只有当块有内容时才保存）
        if self._current_block and (self._current_block["text"] or self._current_block["images"]):
            self.content_blocks.append(self._current_block)

        # 分配待处理的图片到上一个块
        if self._current_block and self._pending_images:
            self._current_block["images"].extend(self._pending_images)
            self._pending_images = []

        # 创建新块
        self._current_block = {
            "id": f"block_{len(self.content_blocks) + 1}",
            "type": "heading",
            "level": level,
            "title": heading_text,
            "text": heading_text,
            "images": [],
            "tables": []
        }

        # 更新当前标题上下文
        if level == 1:
            self._current_h1 = heading_text
            self._current_h2 = None
            self._current_h3 = None
        elif level == 2:
            self._current_h2 = heading_text
            self._current_h3 = None
        elif level == 3:
            self._current_h3 = heading_text

    def _save_current_image(self, img_id: str):
        """保存当前图片到最近的标题块"""
        if self._current_block:
            # 如果当前块还没有图片，先添加到这里
            if img_id not in self._current_block["images"]:
                self._current_block["images"].append(img_id)
        else:
            # 如果还没有任何块，暂存
            if img_id not in self._pending_images:
                self._pending_images.append(img_id)

    def _extract_content_with_images(self):
        """提取内容，同时提取inline图片"""
        image_idx = 0

        for para in self.doc.paragraphs:
            text = para.text.strip()
            style_name = para.style.name
            heading_level = self._get_heading_level(style_name)

            # 检查段落中是否有图片
            found_image_in_para = False
            for elem in para._element.iter():
                elem_tag = elem.tag if isinstance(elem.tag, str) else ''
                if 'drawing' in elem_tag.lower():
                    found_image_in_para = True

                    # 查找blip
                    for child in elem.iter():
                        child_tag = child.tag if isinstance(child.tag, str) else ''
                        if 'blip' in child_tag.lower():
                            embed = child.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                            if embed and embed in self.doc.part.rels and embed not in self._seen_embeds:
                                self._seen_embeds.add(embed)
                                try:
                                    image_idx += 1
                                    img_id = f"img_{image_idx:03d}"

                                    image_part = self.doc.part.rels[embed].target_part
                                    image_bytes = image_part.blob
                                    ext = self._get_image_ext(image_part.content_type)
                                    filename = f"{img_id}{ext}"
                                    filepath = self.images_dir / filename

                                    with open(filepath, 'wb') as f:
                                        f.write(image_bytes)

                                    self.images.append({
                                        "id": img_id,
                                        "name": filename,
                                        "path": str(filepath),
                                        "title": f"图片{image_idx}"
                                    })

                                    # 将图片关联到当前块
                                    self._save_current_image(img_id)
                                except Exception as e:
                                    print(f"提取inline图片失败: {e}")

            # 处理标题（如果段落没有图片才处理标题）
            if not found_image_in_para:
                if heading_level is not None and text:
                    if heading_level == 0:
                        self._current_h1 = text
                        self._current_h2 = None
                        self._current_h3 = None
                    else:
                        self._start_new_block(text, heading_level)

                elif text and self._current_block:
                    # 普通段落，追加到当前块
                    if self._current_block["text"]:
                        self._current_block["text"] += "\n" + text
                    else:
                        self._current_block["text"] = text

    def _get_image_ext(self, content_type: str) -> str:
        """根据content type获取扩展名"""
        ext_map = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/gif": ".gif",
            "image/bmp": ".bmp",
            "image/svg+xml": ".svg",
        }
        return ext_map.get(content_type, ".png")

    def _extract_tables(self):
        """提取表格"""
        for idx, table in enumerate(self.doc.tables):
            table_data = []
            for row in table.rows:
                row_data = [cell.text.strip() for cell in row.cells]
                table_data.append(row_data)

            if table_data:
                table_id = f"table_{idx}"
                table_filename = f"{table_id}.txt"
                table_filepath = self.tables_dir / table_filename

                with open(table_filepath, 'w', encoding='utf-8') as f:
                    for row in table_data:
                        f.write("\t".join(row) + "\n")

                self.tables.append({
                    "id": table_id,
                    "name": table_filename,
                    "path": str(table_filepath),
                    "data": table_data,
                    "rows": len(table_data),
                    "cols": len(table_data[0]) if table_data else 0
                })

                # 将表格添加到当前块
                if self._current_block:
                    if table_id not in self._current_block["tables"]:
                        self._current_block["tables"].append(table_id)


def extract_from_docx(docx_path: str, progress_callback=None) -> Dict[str, Any]:
    """提取Word文档内容"""
    extractor = DocxExtractor(docx_path)
    return extractor.extract_all(progress_callback)


def get_image_by_id(extracted_data: Dict, image_id: str) -> Optional[Dict]:
    """根据ID获取图片信息"""
    for img in extracted_data.get("images", []):
        if img["id"] == image_id:
            return img
    return None


def get_table_by_id(extracted_data: Dict, table_id: str) -> Optional[Dict]:
    """根据ID获取表格信息"""
    for tbl in extracted_data.get("tables", []):
        if tbl["id"] == table_id:
            return tbl
    return None
