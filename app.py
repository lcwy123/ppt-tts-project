#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gradio WebUI - PPT-TTS-Project
"""

import os
import sys
import threading
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/webui.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

import gradio as gr
from src.config import (
    LLM_MODE, TTS_MODE, LOCAL_LLM_URL, LOCAL_LLM_MODEL,
    ARK_API_KEY, ARK_MODEL, INPUT_DIR, OUTPUT_DIR, AUDIO_DIR
)
from src.backup import list_backups
from main import PipelineRunner

logger.info("WebUI模块加载中...")

# 全局运行器
runner = None
runner_lock = threading.Lock()


def get_runner():
    global runner
    with runner_lock:
        return runner


def start_pipeline(input_text, llm_mode, local_llm_url, local_llm_model, 
                   ark_api_key, ark_model, tts_mode):
    """启动流水线"""
    global runner
    logger.info(f"start_pipeline called: llm_mode={llm_mode}, tts_mode={tts_mode}")
    
    with runner_lock:
        runner = PipelineRunner()
    
    # 在后台线程中运行
    def run():
        global runner
        current_runner = get_runner()
        if current_runner:
            logger.info("开始执行流水线...")
            try:
                current_runner.run_full_pipeline(
                    input_text=input_text if input_text and input_text.strip() else None,
                    tts_mode=tts_mode
                )
                logger.info("流水线执行完成")
            except Exception as e:
                logger.error(f"流水线执行出错: {e}")
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    return "🚀 流水线已启动..."


def stop_pipeline():
    """停止流水线"""
    logger.info("stop_pipeline called")
    current_runner = get_runner()
    if current_runner:
        current_runner.stop()
        return "⏹ 已发送停止信号..."
    return "没有正在运行的流水线"


def pause_pipeline():
    """暂停流水线"""
    logger.info("pause_pipeline called")
    current_runner = get_runner()
    if current_runner:
        current_runner.pause()
        return "⏸ 已暂停"
    return "没有正在运行的流水线"


def resume_pipeline():
    """继续流水线"""
    logger.info("resume_pipeline called")
    current_runner = get_runner()
    if current_runner:
        current_runner.resume()
        return "▶ 继续运行"
    return "没有正在运行的流水线"


def refresh_logs():
    """刷新日志"""
    current_runner = get_runner()
    if current_runner:
        logs = current_runner.get_logs()
        result = "\n".join(logs[-100:])
        logger.info(f"refresh_logs: {len(logs)} log entries")
        return result
    return "暂无日志"


def list_output_files():
    """列出输出文件"""
    logger.info("list_output_files called")
    files = []
    if OUTPUT_DIR.exists():
        for f in OUTPUT_DIR.iterdir():
            if f.is_file():
                size = f.stat().st_size
                size_str = f"{size/1024:.1f}KB" if size < 1024*1024 else f"{size/1024/1024:.1f}MB"
                files.append(f"{f.name} ({size_str})")
    result = "\n".join(files) if files else "暂无输出文件"
    logger.info(f"output files: {len(files)} found")
    return result


def list_audio_files():
    """列出音频文件"""
    logger.info("list_audio_files called")
    files = []
    if AUDIO_DIR.exists():
        for f in sorted(AUDIO_DIR.iterdir()):
            if f.is_file() and f.suffix == '.mp3':
                size = f.stat().st_size
                size_str = f"{size/1024:.1f}KB" if size < 1024*1024 else f"{size/1024/1024:.1f}MB"
                files.append(f"{f.name} ({size_str})")
    result = "\n".join(files) if files else "暂无音频文件"
    logger.info(f"audio files: {len(files)} found")
    return result


def get_backup_list():
    """获取备份列表"""
    logger.info("get_backup_list called")
    backups = list_backups()
    result = "\n".join([b.name for b in backups]) if backups else "暂无备份"
    logger.info(f"backup count: {len(backups)}")
    return result


def main(port=7860):
    """启动WebUI"""
    logger.info(f"WebUI启动中... port={port}")
    
    # 检查输入文件
    default_input = ""
    input_file = INPUT_DIR / "input.txt"
    if input_file.exists():
        logger.info(f"读取默认输入文件: {input_file}")
        with open(input_file, 'r', encoding='utf-8') as f:
            default_input = f.read()
    
    logger.info("创建Gradio界面...")
    
    with gr.Blocks(title="PPT-TTS-Project") as demo:
        gr.Markdown("""
        # 🎤 PPT-TTS-Project
        ## 全自动PPT配音生成系统
        
        支持本地CosyVoice TTS + SGlang(Qwen3.5-9B) / 联网API模式
        """)
        
        # Tab 1: 配置
        with gr.Tab("⚙️ 配置"):
            logger.info("创建Tab: 配置")
            gr.Markdown("### LLM 配置")
            llm_mode_radio = gr.Radio(
                ["local", "api"],
                value=LLM_MODE,
                label="LLM模式"
            )
            local_llm_url = gr.Textbox(
                value=LOCAL_LLM_URL,
                label="本地LLM URL"
            )
            local_llm_model = gr.Textbox(
                value=LOCAL_LLM_MODEL,
                label="本地模型名称"
            )
            ark_api_key = gr.Textbox(
                value="****" if ARK_API_KEY else "",
                label="火山方舟API Key"
            )
            ark_model = gr.Textbox(
                value=ARK_MODEL,
                label="火山方舟模型"
            )
            
            gr.Markdown("### TTS 配置")
            tts_mode_radio = gr.Radio(
                ["cosyvoice", "edge"],
                value=TTS_MODE,
                label="TTS模式"
            )
            gr.Markdown("""
            **CosyVoice**: 本地TTS，需要下载模型  
            **Edge**: 微软Edge TTS，需要联网
            """)
        
        # Tab 2: 输入
        with gr.Tab("📝 输入"):
            logger.info("创建Tab: 输入")
            input_text = gr.Textbox(
                value=default_input,
                label="输入主题文字",
                lines=15,
                placeholder="输入PPT的主题内容..."
            )
            gr.Markdown("""
            💡 **提示**: 将文字保存到 `data/input/input.txt` 也可直接读取
            """)
        
        # Tab 3: 执行
        with gr.Tab("🚀 执行"):
            logger.info("创建Tab: 执行")
            with gr.Row():
                start_btn = gr.Button("▶ 开始生成", variant="primary")
                stop_btn = gr.Button("⏹ 停止")
                pause_btn = gr.Button("⏸ 暂停")
                resume_btn = gr.Button("▶ 继续")
            
            status_text = gr.Textbox(label="执行状态", lines=20, interactive=False)
            
            with gr.Row():
                refresh_btn = gr.Button("🔄 刷新日志")
                clear_btn = gr.Button("🗑 清空日志")
        
        # Tab 4: 输出文件
        with gr.Tab("📁 输出文件"):
            logger.info("创建Tab: 输出文件")
            gr.Markdown("### 生成的文件")
            output_files = gr.Textbox(label="输出文件列表", lines=10, interactive=False)
            refresh_files_btn = gr.Button("🔄 刷新文件列表")
        
        # Tab 5: 音频
        with gr.Tab("🔊 音频"):
            logger.info("创建Tab: 音频")
            gr.Markdown("### 已生成的音频文件")
            audio_files = gr.Textbox(label="音频文件", lines=15, interactive=False)
            refresh_audio_btn = gr.Button("🔄 刷新音频列表")
        
        # Tab 6: 备份
        with gr.Tab("📋 备份"):
            logger.info("创建Tab: 备份")
            gr.Markdown("### 历史备份")
            backup_list = gr.Textbox(label="可用备份", lines=10, interactive=False)
            refresh_backup_btn = gr.Button("🔄 刷新备份列表")
        
        # 事件绑定
        logger.info("绑定事件...")
        
        start_btn.click(
            fn=start_pipeline,
            inputs=[input_text, llm_mode_radio, local_llm_url, local_llm_model,
                   ark_api_key, ark_model, tts_mode_radio],
            outputs=status_text
        )
        logger.info("  - start_btn 绑定完成")
        
        stop_btn.click(
            fn=stop_pipeline,
            inputs=[],
            outputs=status_text
        )
        pause_btn.click(
            fn=pause_pipeline,
            inputs=[],
            outputs=status_text
        )
        resume_btn.click(
            fn=resume_pipeline,
            inputs=[],
            outputs=status_text
        )
        
        refresh_btn.click(
            fn=refresh_logs,
            inputs=[],
            outputs=status_text
        )
        
        clear_btn.click(
            fn=lambda: "",
            inputs=[],
            outputs=status_text
        )
        
        refresh_files_btn.click(
            fn=list_output_files,
            inputs=[],
            outputs=output_files
        )
        
        refresh_audio_btn.click(
            fn=list_audio_files,
            inputs=[],
            outputs=audio_files
        )
        
        refresh_backup_btn.click(
            fn=get_backup_list,
            inputs=[],
            outputs=backup_list
        )
        
        # 初始加载回调
        demo.load(
            fn=list_output_files,
            inputs=None,
            outputs=output_files
        )
        demo.load(
            fn=list_audio_files,
            inputs=None,
            outputs=audio_files
        )
        demo.load(
            fn=get_backup_list,
            inputs=None,
            outputs=backup_list
        )
        
        logger.info("所有事件绑定完成")
    
    logger.info("启动Gradio服务...")
    demo.launch(
        server_port=port,
        server_name="0.0.0.0",
        share=False
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    main(port=args.port)
