#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解说词生成模块
"""

import os
from pathlib import Path
from src.config import get_llm_client, get_llm_model_name, OUTPUT_SLIDES_TEXT, OUTPUT_NARRATION


def load_slides_text(file_path):
    """加载提取的PPT文本"""
    
    slides = []
    current_slide = 0
    current_content = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip()
            
            if line.startswith("=== 第"):
                if current_slide > 0:
                    slides.append({
                        "slide_num": current_slide,
                        "content": "\n".join(current_content).strip()
                    })
                
                import re
                match = re.search(r'第\s*(\d+)\s*页', line)
                if match:
                    current_slide = int(match.group(1))
                else:
                    current_slide += 1
                current_content = []
            else:
                current_content.append(line)
        
        if current_slide > 0:
            slides.append({
                "slide_num": current_slide,
                "content": "\n".join(current_content).strip()
            })
    
    return slides


def generate_narration_for_slide(slide_content, slide_index, total_slides, progress_callback=None):
    """为单页PPT生成解说词"""
    
    client = get_llm_client()
    model = get_llm_model_name()
    
    prompt = f"""
你是一位专业的PPT演讲教练。请根据以下PPT页面内容，生成一段自然、流畅、专业的口播解说词。

要求：
1. 口语化，适合朗读，不要太书面化
2. 每段解说词约100-300字
3. 包含开场和过渡语
4. 第1页是封面，要有欢迎词
5. 最后1页要有结束语

当前是第 {slide_index + 1} 页，共 {total_slides} 页

PPT内容：
{slide_content}

请只输出解说词内容，不要任何其他解释。
"""
    
    if progress_callback:
        progress_callback(f"正在生成第 {slide_index + 1} 页解说词...")
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        if progress_callback:
            progress_callback(f"LLM调用失败: {e}，使用离线模式")
        return generate_narration_offline(slide_index, total_slides)


def generate_narration_offline(slide_index, total_slides):
    """离线生成解说词（模板）"""
    
    narrations = [
        "大家好，欢迎来到今天的主题分享。在接下来的时间里，我将和大家一起深入了解这个话题。希望通过今天的分享，大家能有所收获。现在让我们开始吧。",
        "首先，让我们来看一下今天的主要内容。我们将分几个部分来讲解，每个部分都有重要的知识点需要大家掌握。",
        "接下来进入第一部分的内容。这一部分非常重要，我们需要认真理解。",
        "现在让我们继续深入了解这部分内容。请大家注意几个关键点。",
        "这部分内容非常关键，我们需要重点掌握。让我来详细解释一下。",
        "在实际应用中，我们需要综合考虑多方面因素。接下来让我们看看具体的应用场景。",
        "现在让我们总结一下前面讲的内容。",
        "最后，让我们来了解一下这个领域的发展趋势和前景。",
        "以上就是我们今天分享的全部内容。希望这些信息对大家有所帮助。",
        "感谢大家的聆听！如果有其他问题，欢迎随时交流。谢谢！",
    ]
    
    if slide_index < len(narrations):
        return narrations[slide_index]
    return f"这是第{slide_index + 1}页的解说词内容。"


def save_narrations(narrations, output_path=None, progress_callback=None):
    """保存解说词到文件"""
    
    if output_path is None:
        output_path = OUTPUT_NARRATION
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in narrations:
            f.write(f"=== 第 {item['slide_num']} 页 ===\n")
            f.write(item["narration"])
            f.write("\n\n")
    
    if progress_callback:
        progress_callback(f"解说词已保存: {output_path}")
    
    return output_path


def run(slides_text_path=None, progress_callback=None):
    """运行完整流程：生成解说词"""
    
    if slides_text_path is None:
        slides_text_path = OUTPUT_SLIDES_TEXT
    
    if not os.path.exists(slides_text_path):
        raise FileNotFoundError(f"幻灯片文本文件不存在: {slides_text_path}")
    
    if progress_callback:
        progress_callback("正在加载幻灯片文本...")
    
    slides = load_slides_text(slides_text_path)
    
    if progress_callback:
        progress_callback(f"共 {len(slides)} 页幻灯片，开始生成解说词...")
    
    narrations = []
    
    for i, slide in enumerate(slides):
        narration = generate_narration_for_slide(
            slide["content"], i, len(slides), progress_callback
        )
        narrations.append({
            "slide_num": slide["slide_num"],
            "narration": narration
        })
    
    output_path = save_narrations(narrations, progress_callback=progress_callback)
    
    return output_path, narrations
