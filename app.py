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
    MINIMAX_API_KEY, MINIMAX_MODEL, INPUT_DIR, OUTPUT_DIR, AUDIO_DIR,
    OUTPUT_OUTLINE, OUTPUT_PPT, OUTPUT_SLIDES_TEXT, OUTPUT_NARRATION,
    OUTPUT_AUDIO_DURATIONS, OUTPUT_FINAL_PPT, PPT_GENERATION_MODE,
    COSYVOICE_SPEAKER, EDGE_VOICE
)

# CosyVoice 可用的说话人
COSYVOICE_SPEAKERS = ["中文女", "中文男", "粤语女", "英文女", "英文男", "日语男", "韩语女"]

# Edge TTS 可用的中文声音
EDGE_VOICE_CHOICES = [
    ("晓晓 (女)", "zh-CN-XiaoxiaoNeural"),
    ("晓伊 (女)", "zh-CN-XiaoyiNeural"),
    ("云健 (男)", "zh-CN-YunjianNeural"),
    ("云希 (男)", "zh-CN-YunxiNeural"),
    ("云夏 (男)", "zh-CN-YunxiaNeural"),
    ("云扬 (男)", "zh-CN-YunyangNeural"),
    ("晓北 (东北话·女)", "zh-CN-liaoning-XiaobeiNeural"),
    ("晓妮 (陕西话·女)", "zh-CN-shaanxi-XiaoniNeural"),
]
from src.backup import list_backups
from src import run_outline, run_ppt, run_multimodal, run_extract, run_narration, run_audio, run_embed
from main import PipelineRunner

logger.info("WebUI模块加载中...")

# 全局运行器
runner = None
runner_lock = threading.Lock()

# 步骤状态追踪
step_status = {
    "outline": False, "ppt": False, "extract": False,
    "narration": False, "audio": False, "embed": False
}
step_status_lock = threading.Lock()


def get_runner():
    global runner
    with runner_lock:
        return runner


def start_pipeline(input_text, llm_mode, local_llm_url, local_llm_model,
                   minimax_api_key, minimax_model, tts_mode, input_docx=None, ppt_mode=None, tts_voice=None):
    """启动流水线"""
    global runner
    logger.info(f"start_pipeline called: llm_mode={llm_mode}, tts_mode={tts_mode}, ppt_mode={ppt_mode}, input_docx={input_docx}")

    with runner_lock:
        runner = PipelineRunner()

    # 在后台线程中运行
    def run():
        global runner
        current_runner = get_runner()
        if current_runner:
            logger.info("开始执行流水线...")
            # 临时应用WebUI的LLM配置
            import src.config as cfg
            old_llm_mode = cfg.LLM_MODE
            old_url = cfg.LOCAL_LLM_URL
            old_model = cfg.LOCAL_LLM_MODEL
            old_key = cfg.MINIMAX_API_KEY
            try:
                cfg.LLM_MODE = llm_mode
                cfg.LOCAL_LLM_URL = local_llm_url
                cfg.LOCAL_LLM_MODEL = local_llm_model
                if minimax_api_key and minimax_api_key != "****":
                    cfg.MINIMAX_API_KEY = minimax_api_key
                current_runner.run_full_pipeline(
                    input_text=input_text if input_text and input_text.strip() else None,
                    tts_mode=tts_mode,
                    input_docx=input_docx,
                    ppt_mode=ppt_mode,
                    tts_voice=tts_voice,
                )
                logger.info("流水线执行完成")
            except Exception as e:
                logger.error(f"流水线执行出错: {e}")
            finally:
                cfg.LLM_MODE = old_llm_mode
                cfg.LOCAL_LLM_URL = old_url
                cfg.LOCAL_LLM_MODEL = old_model
                cfg.MINIMAX_API_KEY = old_key

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    return "🚀 流水线已启动..."


def run_step_ppt_multimodal(input_docx, ppt_mode=None):
    """步骤2: 多模态模式生成PPT（从Word文档）"""
    r = _get_or_create_runner()
    r._current_step = "PPT生成"

    def do_run():
        global runner
        current_runner = get_runner()
        if current_runner:
            current_runner._stop_event.clear()
        if not input_docx or not Path(input_docx).exists():
            r._log("⚠ 警告: Word文档不存在，请先上传")
            return

        r._log("="*50)
        r._log(f"步骤2: 多模态PPT生成 (模式: {ppt_mode or PPT_GENERATION_MODE})")
        r._log("="*50)
        r._log(f"输入文档: {input_docx}")

        try:
            current_runner = get_runner()
            if current_runner and current_runner._stop_event.is_set():
                r._log("⏹ 已停止")
                return
            run_multimodal(input_docx, progress_callback=r._progress_callback, mode=ppt_mode)
            with step_status_lock:
                step_status["ppt"] = True
            r._log("="*50)
            r._log("✅ 多模态PPT生成完成！")
            r._log("请在【输出文件】Tab查看生成的PPT")
            r._log("="*50)
        except Exception as e:
            r._log(f"✗ 步骤2出错: {e}")
            import traceback
            traceback.print_exc()

    threading.Thread(target=do_run, daemon=True).start()
    # 返回当前日志让UI立即显示
    return "\n".join(r.get_logs()[-20:]) if r.get_logs() else "正在启动多模态PPT生成..."


def stop_pipeline():
    """停止流水线"""
    logger.info("stop_pipeline called")
    current_runner = get_runner()
    if current_runner:
        current_runner.stop()
        current_runner._log("⏹ 已发送停止信号")
        return "⏹ 已发送停止信号..."
    return "没有正在运行的流水线"


def clear_all_logs():
    """清空所有日志（包括runner内部缓存和步骤状态）"""
    global runner
    logger.info("clear_all_logs called")
    with runner_lock:
        if runner is not None:
            with runner._lock:
                runner._logs.clear()
    with step_status_lock:
        for k in step_status:
            step_status[k] = False
    return ""


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


def refresh_all():
    """Periodic refresh: logs + step status notification"""
    logs = refresh_logs()
    with step_status_lock:
        completed = [k for k, v in step_status.items() if v]
        total = len(step_status)
    if completed:
        steps_done = ", ".join(completed)
        notification = f'<div style="padding: 12px 16px; border-radius: 8px; margin-bottom: 10px; font-size: 14px; background: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7;">已完成步骤: {steps_done} ({len(completed)}/{total})</div>'
    else:
        notification = ""
    return logs, notification


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


# ============== 分步执行函数 ==============

def _get_or_create_runner():
    """获取或创建运行器"""
    global runner
    with runner_lock:
        if runner is None:
            runner = PipelineRunner()
        return runner


def run_step_outline(input_text, llm_mode, local_llm_url, local_llm_model,
                     minimax_api_key, minimax_model, input_docx=None):
    """步骤1: 生成Word提纲（支持文本或多模态）"""
    r = _get_or_create_runner()
    r._current_step = "提纲生成"

    def do_run():
        global runner
        import src.config as cfg
        old_mode = cfg.LLM_MODE
        old_url = cfg.LOCAL_LLM_URL
        old_model = cfg.LOCAL_LLM_MODEL
        old_key = cfg.MINIMAX_API_KEY
        current_runner = get_runner()
        if current_runner:
            current_runner._stop_event.clear()
        try:
            cfg.LLM_MODE = llm_mode
            cfg.LOCAL_LLM_URL = local_llm_url
            cfg.LOCAL_LLM_MODEL = local_llm_model
            if minimax_api_key and minimax_api_key != "****":
                cfg.MINIMAX_API_KEY = minimax_api_key

            r._log("="*50)
            r._log("步骤1: 生成/确认提纲")
            r._log("="*50)

            if input_docx and Path(input_docx).exists():
                r._log(f"📄 检测到Word文档输入: {Path(input_docx).name}")
                r._log("多模态模式：将直接使用Word文档内容生成PPT，无需额外生成提纲")
                r._log("请点击「步骤2: 生成PPT」继续")
                with step_status_lock:
                    step_status["outline"] = True
                r._log("✓ 步骤1完成 (多模态输入已就绪)")
            else:
                current_runner = get_runner()
                if current_runner and current_runner._stop_event.is_set():
                    r._log("⏹ 已停止")
                    return
                run_outline(
                    input_text=input_text.strip() if input_text and input_text.strip() else None,
                    progress_callback=r._progress_callback
                )
                current_runner = get_runner()
                if current_runner and current_runner._stop_event.is_set():
                    r._log("⏹ 已停止")
                    return
                with step_status_lock:
                    step_status["outline"] = True
                r._log("✓ 步骤1完成")
        except Exception as e:
            r._log(f"✗ 步骤1出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            cfg.LLM_MODE = old_mode
            cfg.LOCAL_LLM_URL = old_url
            cfg.LOCAL_LLM_MODEL = old_model
            cfg.MINIMAX_API_KEY = old_key

    threading.Thread(target=do_run, daemon=True).start()
    return "步骤1(生成提纲)已启动..."


def run_step_ppt(ppt_mode=None, input_docx=None):
    """步骤2: 生成PPT（支持文本或多模态）"""
    r = _get_or_create_runner()
    r._current_step = "PPT生成"

    def do_run():
        global runner
        current_runner = get_runner()
        if current_runner:
            current_runner._stop_event.clear()
        try:
            r._log("="*50)
            r._log(f"步骤2: 生成PPT (模式: {ppt_mode or PPT_GENERATION_MODE})")
            r._log("="*50)

            if input_docx and Path(input_docx).exists():
                r._log(f"📄 使用Word文档生成PPT: {Path(input_docx).name}")
                current_runner = get_runner()
                if current_runner and current_runner._stop_event.is_set():
                    r._log("⏹ 已停止")
                    return
                run_multimodal(input_docx, progress_callback=r._progress_callback, mode=ppt_mode)
                current_runner = get_runner()
                if current_runner and current_runner._stop_event.is_set():
                    r._log("⏹ 已停止")
                    return
                with step_status_lock:
                    step_status["ppt"] = True
                r._log("="*50)
                r._log("✅ PPT生成完成！")
                r._log("请在【输出文件】Tab查看生成的PPT")
                r._log("="*50)
            else:
                if not OUTPUT_OUTLINE.exists():
                    r._log("⚠ 警告: ppt_outline.docx 不存在，步骤2可能失败")
                current_runner = get_runner()
                if current_runner and current_runner._stop_event.is_set():
                    r._log("⏹ 已停止")
                    return
                run_ppt(progress_callback=r._progress_callback, mode=ppt_mode)
                current_runner = get_runner()
                if current_runner and current_runner._stop_event.is_set():
                    r._log("⏹ 已停止")
                    return
                with step_status_lock:
                    step_status["ppt"] = True
                r._log("✓ 步骤2完成")
        except Exception as e:
            r._log(f"✗ 步骤2出错: {e}")
            import traceback
            traceback.print_exc()

    threading.Thread(target=do_run, daemon=True).start()
    return "步骤2(生成PPT)已启动..."


def run_step_extract():
    """步骤3: 提取PPT文本"""
    r = _get_or_create_runner()
    r._current_step = "文本提取"

    def do_run():
        global runner
        current_runner = get_runner()
        if current_runner:
            current_runner._stop_event.clear()
        if not OUTPUT_PPT.exists():
            r._log("⚠ 警告: generated.pptx 不存在，步骤3可能失败")
        try:
            r._log("="*50)
            r._log("步骤3: 提取PPT文本")
            r._log("="*50)
            current_runner = get_runner()
            if current_runner and current_runner._stop_event.is_set():
                r._log("⏹ 已停止")
                return
            run_extract(progress_callback=r._progress_callback)
            with step_status_lock:
                step_status["extract"] = True
            r._log("✓ 步骤3完成")
        except Exception as e:
            r._log(f"✗ 步骤3出错: {e}")
            import traceback
            traceback.print_exc()

    threading.Thread(target=do_run, daemon=True).start()
    return "步骤3(提取文本)已启动..."


def run_step_narration():
    """步骤4: 生成解说词"""
    r = _get_or_create_runner()
    r._current_step = "解说词生成"

    def do_run():
        global runner
        current_runner = get_runner()
        if current_runner:
            current_runner._stop_event.clear()
        if not OUTPUT_SLIDES_TEXT.exists():
            r._log("⚠ 警告: slides_text.txt 不存在，步骤4可能失败")
        try:
            r._log("="*50)
            r._log("步骤4: 生成解说词")
            r._log("="*50)
            current_runner = get_runner()
            if current_runner and current_runner._stop_event.is_set():
                r._log("⏹ 已停止")
                return
            run_narration(progress_callback=r._progress_callback)
            with step_status_lock:
                step_status["narration"] = True
            r._log("✓ 步骤4完成")
        except Exception as e:
            r._log(f"✗ 步骤4出错: {e}")
            import traceback
            traceback.print_exc()

    threading.Thread(target=do_run, daemon=True).start()
    return "步骤4(生成解说词)已启动..."


def update_voice_choices(tts_mode):
    """根据TTS模式更新音色下拉选项"""
    if tts_mode == "cosyvoice":
        default = COSYVOICE_SPEAKER if COSYVOICE_SPEAKER in COSYVOICE_SPEAKERS else "中文女"
        return gr.Dropdown(choices=COSYVOICE_SPEAKERS, value=default)
    else:
        edge_defaults = [v for _, v in EDGE_VOICE_CHOICES]
        default = EDGE_VOICE if EDGE_VOICE in edge_defaults else "zh-CN-XiaoxiaoNeural"
        return gr.Dropdown(choices=EDGE_VOICE_CHOICES, value=default)


def run_step_audio(tts_mode, tts_voice=None):
    """步骤5: 生成音频"""
    r = _get_or_create_runner()
    r._current_step = "音频生成"

    def do_run():
        global runner
        current_runner = get_runner()
        if current_runner:
            current_runner._stop_event.clear()
        if not OUTPUT_NARRATION.exists():
            r._log("⚠ 警告: narration.txt 不存在，步骤5可能失败")
        try:
            r._log("="*50)
            r._log(f"步骤5: 生成音频 (TTS: {tts_mode}, 音色: {tts_voice or '默认'})")
            r._log("="*50)
            current_runner = get_runner()
            if current_runner and current_runner._stop_event.is_set():
                r._log("⏹ 已停止")
                return
            run_audio(tts_mode=tts_mode, progress_callback=r._progress_callback, tts_voice=tts_voice)
            with step_status_lock:
                step_status["audio"] = True
            r._log("✓ 步骤5完成")
        except Exception as e:
            r._log(f"✗ 步骤5出错: {e}")
            import traceback
            traceback.print_exc()

    threading.Thread(target=do_run, daemon=True).start()
    return "步骤5(生成音频)已启动..."


def run_step_embed():
    """步骤6: 嵌入音频到PPT"""
    r = _get_or_create_runner()
    r._current_step = "音频嵌入"

    def do_run():
        global runner
        current_runner = get_runner()
        if current_runner:
            current_runner._stop_event.clear()
        if not OUTPUT_PPT.exists():
            r._log("⚠ 警告: generated.pptx 不存在，步骤6可能失败")
        if not OUTPUT_AUDIO_DURATIONS.exists():
            r._log("⚠ 警告: audio_durations.json 不存在，步骤6可能失败")
        try:
            r._log("="*50)
            r._log("步骤6: 嵌入音频到PPT")
            r._log("="*50)
            current_runner = get_runner()
            if current_runner and current_runner._stop_event.is_set():
                r._log("⏹ 已停止")
                return
            run_embed(progress_callback=r._progress_callback)
            with step_status_lock:
                step_status["embed"] = True
            r._log("✓ 步骤6完成")
        except Exception as e:
            r._log(f"✗ 步骤6出错: {e}")
            import traceback
            traceback.print_exc()

    threading.Thread(target=do_run, daemon=True).start()
    return "步骤6(嵌入音频)已启动..."


# ============== 文件刷新函数 ==============

def get_output_file(file_path):
    """返回文件路径（如果存在），否则返回None"""
    if file_path and Path(file_path).exists():
        return str(file_path)
    return None


def refresh_output_files():
    """刷新输出文件列表"""
    return (
        get_output_file(OUTPUT_OUTLINE),
        get_output_file(OUTPUT_PPT),
        get_output_file(OUTPUT_SLIDES_TEXT),
        get_output_file(OUTPUT_NARRATION),
        get_output_file(OUTPUT_FINAL_PPT),
    )


def refresh_audio_files():
    """刷新音频文件列表"""
    audio_files = []
    if AUDIO_DIR.exists():
        for f in sorted(AUDIO_DIR.iterdir()):
            if f.is_file() and f.suffix == '.mp3':
                audio_files.append(str(f))
    return audio_files if audio_files else None


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
            minimax_api_key = gr.Textbox(
                value="****" if MINIMAX_API_KEY else "",
                label="MiniMax API Key"
            )
            minimax_model = gr.Textbox(
                value=MINIMAX_MODEL,
                label="MiniMax模型"
            )
            
            gr.Markdown("### TTS 配置")
            tts_mode_radio = gr.Radio(
                ["cosyvoice", "edge"],
                value=TTS_MODE,
                label="TTS模式"
            )
            voice_dropdown = gr.Dropdown(
                choices=COSYVOICE_SPEAKERS if TTS_MODE == "cosyvoice" else EDGE_VOICE_CHOICES,
                value=COSYVOICE_SPEAKER if TTS_MODE == "cosyvoice" else EDGE_VOICE,
                label="音色/声音",
                interactive=True
            )
            gr.Markdown("""
            **CosyVoice**: 本地TTS，需要下载模型
            **Edge**: 微软Edge TTS，需要联网
            """)

            gr.Markdown("### PPT 生成方式")
            ppt_mode_radio = gr.Radio(
                ["basic", "template", "ppt-master"],
                value=PPT_GENERATION_MODE,
                label="PPT生成模式"
            )
            gr.Markdown("""
            **basic**: 原始python-pptx方式，纯文字PPT
            **template**: 基于模板复制方式，支持图片和表格
            **ppt-master**: AI设计SVG → 原生PowerPoint形状（实验性，需联网LLM）
            """)
        
        # Tab 2: 输入
        with gr.Tab("📝 输入"):
            logger.info("创建Tab: 输入")
            gr.Markdown("### 文本输入")
            input_text = gr.Textbox(
                value=default_input,
                label="输入主题文字",
                lines=10,
                placeholder="输入PPT的主题内容..."
            )
            gr.Markdown("""
            💡 **提示**: 将文字保存到 `data/input/input.txt` 也可直接读取
            """)

            gr.Markdown("---")
            gr.Markdown("### Word文档输入（多模态）")
            gr.Markdown("上传包含文字、图片、表格的Word文档，生成图文并茂的PPT")
            input_docx = gr.File(
                label="上传Word文档 (.doc/.docx)",
                file_types=[".docx", ".doc"],
                file_count="single"
            )
            btn_step2_multimodal = gr.Button("2️⃣ 生成多模态PPT", variant="secondary")
            gr.Markdown("""
            ⚠️ **多模态模式说明**: 上传Word文档后，点击上方按钮生成PPT（将跳过步骤1直接生成）
            """)

        # Tab 3: 执行
        with gr.Tab("🚀 执行"):
            logger.info("创建Tab: 执行")
            notification_html = gr.HTML("""
            <div id="step_notification" style="
                padding: 12px 16px; border-radius: 8px; margin-bottom: 10px;
                font-size: 14px; display: none; background: #e8f5e9; color: #2e7d32;
                border: 1px solid #a5d6a7;">
            </div>
            """)
            gr.Markdown("### 分步执行")
            with gr.Row():
                btn_step1 = gr.Button("1️⃣ 生成提纲", variant="primary")
                btn_step2 = gr.Button("2️⃣ 生成PPT", variant="primary")
                btn_step3 = gr.Button("3️⃣ 提取文本", variant="primary")
            with gr.Row():
                btn_step4 = gr.Button("4️⃣ 生成解说词", variant="primary")
                btn_step5 = gr.Button("5️⃣ 生成音频", variant="primary")
                btn_step6 = gr.Button("6️⃣ 嵌入音频", variant="primary")

            gr.Markdown("---")
            gr.Markdown("### 全量执行")
            with gr.Row():
                start_btn = gr.Button("▶ 开始生成(全流程)", variant="primary")
                stop_btn = gr.Button("⏹ 停止")
                pause_btn = gr.Button("⏸ 暂停")
                resume_btn = gr.Button("▶ 继续")

            gr.Markdown("---")
            gr.Markdown("### 执行日志")
            status_text = gr.Textbox(label="执行状态", lines=15, interactive=False)
            timer = gr.Timer(3)

            with gr.Row():
                refresh_btn = gr.Button("🔄 刷新日志")
                clear_btn = gr.Button("🗑 清空日志")

        # Tab 4: 输出文件
        with gr.Tab("📁 输出文件"):
            logger.info("创建Tab: 输出文件")
            gr.Markdown("### 输出文件下载")
            gr.Markdown("*点击文件名即可下载*")
            outline_file = gr.File(label="PPT提纲 (ppt_outline.docx)", file_types=[".docx"])
            ppt_file = gr.File(label="生成的PPT (generated.pptx)", file_types=[".pptx"])
            slides_text_file = gr.File(label="幻灯片文本 (slides_text.txt)", file_types=[".txt"])
            narration_file = gr.File(label="解说词 (narration.txt)", file_types=[".txt"])
            final_ppt_file = gr.File(label="最终PPT带音频 (final_with_audio.pptx)", file_types=[".pptx"])
            refresh_files_btn = gr.Button("🔄 刷新文件列表")

        # Tab 5: 音频
        with gr.Tab("🔊 音频"):
            logger.info("创建Tab: 音频")
            gr.Markdown("### 音频文件下载")
            gr.Markdown("*每个幻灯片对应的音频文件*")
            audio_files_list = gr.File(label="音频文件 (*.mp3)", file_types=[".mp3"])
            refresh_audio_btn = gr.Button("🔄 刷新音频列表")
        
        # Tab 6: 备份
        with gr.Tab("📋 备份"):
            logger.info("创建Tab: 备份")
            gr.Markdown("### 历史备份")
            backup_list = gr.Textbox(label="可用备份", lines=10, interactive=False)
            refresh_backup_btn = gr.Button("🔄 刷新备份列表")
        
        # 事件绑定
        logger.info("绑定事件...")

        # 分步执行按钮
        btn_step1.click(
            fn=run_step_outline,
            inputs=[input_text, llm_mode_radio, local_llm_url, local_llm_model,
                    minimax_api_key, minimax_model, input_docx],
            outputs=status_text
        )
        btn_step2.click(fn=run_step_ppt, inputs=[ppt_mode_radio, input_docx], outputs=status_text)
        btn_step3.click(fn=run_step_extract, inputs=[], outputs=status_text)
        btn_step4.click(fn=run_step_narration, inputs=[], outputs=status_text)
        btn_step5.click(fn=run_step_audio, inputs=[tts_mode_radio, voice_dropdown], outputs=status_text)
        btn_step6.click(fn=run_step_embed, inputs=[], outputs=status_text)
        logger.info("  - 分步按钮绑定完成")

        start_btn.click(
            fn=start_pipeline,
            inputs=[input_text, llm_mode_radio, local_llm_url, local_llm_model,
                   minimax_api_key, minimax_model, tts_mode_radio, input_docx, ppt_mode_radio, voice_dropdown],
            outputs=status_text
        )
        btn_step2_multimodal.click(
            fn=run_step_ppt_multimodal,
            inputs=[input_docx, ppt_mode_radio],
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
            fn=clear_all_logs,
            inputs=[],
            outputs=status_text
        )

        # 定时自动刷新日志和通知
        timer.tick(
            fn=refresh_all,
            inputs=[],
            outputs=[status_text, notification_html]
        )

        refresh_files_btn.click(
            fn=refresh_output_files,
            inputs=[],
            outputs=[outline_file, ppt_file, slides_text_file, narration_file, final_ppt_file]
        )

        refresh_audio_btn.click(
            fn=refresh_audio_files,
            inputs=[],
            outputs=audio_files_list
        )

        refresh_backup_btn.click(
            fn=get_backup_list,
            inputs=[],
            outputs=backup_list
        )

        # 初始加载回调
        demo.load(
            fn=refresh_output_files,
            inputs=None,
            outputs=[outline_file, ppt_file, slides_text_file, narration_file, final_ppt_file]
        )
        demo.load(
            fn=refresh_audio_files,
            inputs=None,
            outputs=audio_files_list
        )
        demo.load(
            fn=get_backup_list,
            inputs=None,
            outputs=backup_list
        )

        # TTS模式切换时更新音色下拉选项
        tts_mode_radio.change(
            fn=update_voice_choices,
            inputs=[tts_mode_radio],
            outputs=voice_dropdown
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
