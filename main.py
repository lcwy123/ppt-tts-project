#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PPT-TTS-Project 主程序
支持命令行和WebUI两种运行模式
支持多模态输入：文本输入 或 Word文档输入（含图片、表格）
"""

import os
import sys
import argparse
import threading
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src import (
    run_outline, run_ppt, run_multimodal, run_extract, run_narration, run_audio, run_embed,
    backup_old_output, list_backups
)
from src.config import LLM_MODE, TTS_MODE


class PipelineRunner:
    """流水线运行器，支持暂停/继续"""

    def __init__(self):
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._is_paused = False
        self._current_step = ""
        self._logs = []
        self._lock = threading.Lock()

    def _log(self, message):
        """线程安全的日志记录"""
        with self._lock:
            self._logs.append(message)
            print(message)

    def _progress_callback(self, message):
        """进度回调"""
        self._log(f"[{self._current_step}] {message}")

    def stop(self):
        """停止执行"""
        self._stop_event.set()

    def pause(self):
        """暂停执行"""
        if not self._is_paused:
            self._is_paused = True
            self._pause_event.set()
            self._log("⏸ 已暂停")

    def resume(self):
        """继续执行"""
        if self._is_paused:
            self._is_paused = False
            self._pause_event.clear()
            self._log("▶ 继续执行")

    def is_paused(self):
        return self._is_paused

    def get_logs(self):
        with self._lock:
            return list(self._logs)

    def _check_pause(self):
        """检查是否需要暂停"""
        if self._is_paused:
            self._pause_event.wait()

    def run_full_pipeline(self, input_text=None, tts_mode=None, input_docx=None):
        """运行完整流程

        Args:
            input_text: 文本输入
            tts_mode: TTS模式
            input_docx: Word文档路径（多模态模式）
        """
        try:
            # 0. 备份
            self._current_step = "备份"
            self._log("="*50)
            self._log("步骤0: 备份上次输出")
            self._log("="*50)
            backup_old_output(progress_callback=self._progress_callback)

            if self._stop_event.is_set():
                self._log("⏹ 已停止")
                return False

            self._check_pause()

            # 判断输入模式
            if input_docx and os.path.exists(input_docx):
                # 多模态模式：从Word文档生成
                self._current_step = "多模态PPT生成"
                self._log("\n" + "="*50)
                self._log("检测到Word文档输入，使用多模态模式")
                self._log("="*50)
                run_multimodal(input_docx, progress_callback=self._progress_callback)
            else:
                # 文本模式：生成提纲然后PPT
                self._current_step = "提纲生成"
                self._log("\n" + "="*50)
                self._log("步骤1: 生成Word提纲")
                self._log("="*50)
                run_outline(input_text=input_text, progress_callback=self._progress_callback)

                if self._stop_event.is_set():
                    self._log("⏹ 已停止")
                    return False

                self._check_pause()

                # 生成PPT
                self._current_step = "PPT生成"
                self._log("\n" + "="*50)
                self._log("步骤2: 生成PPT")
                self._log("="*50)
                run_ppt(progress_callback=self._progress_callback)

            if self._stop_event.is_set():
                self._log("⏹ 已停止")
                return False

            self._check_pause()

            # 3. 提取文本
            self._current_step = "文本提取"
            self._log("\n" + "="*50)
            self._log("步骤3: 提取PPT文本")
            self._log("="*50)
            run_extract(progress_callback=self._progress_callback)

            if self._stop_event.is_set():
                self._log("⏹ 已停止")
                return False

            self._check_pause()

            # 4. 生成解说词
            self._current_step = "解说词生成"
            self._log("\n" + "="*50)
            self._log("步骤4: 生成解说词")
            self._log("="*50)
            run_narration(progress_callback=self._progress_callback)

            if self._stop_event.is_set():
                self._log("⏹ 已停止")
                return False

            self._check_pause()

            # 5. 生成音频
            self._current_step = "音频生成"
            self._log("\n" + "="*50)
            self._log("步骤5: 生成音频")
            self._log("="*50)
            run_audio(tts_mode=tts_mode, progress_callback=self._progress_callback)

            if self._stop_event.is_set():
                self._log("⏹ 已停止")
                return False

            self._check_pause()

            # 6. 嵌入音频
            self._current_step = "音频嵌入"
            self._log("\n" + "="*50)
            self._log("步骤6: 嵌入音频到PPT")
            self._log("="*50)
            run_embed(progress_callback=self._progress_callback)

            self._log("\n" + "="*50)
            self._log("🎉 全部流程完成！")
            self._log("="*50)

            return True

        except Exception as e:
            self._log(f"\n❌ 错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


def main():
    # 先解析已知参数，剩余的传给 run_cli
    parser = argparse.ArgumentParser(description="PPT-TTS-Project", allow_abbrev=False)
    parser.add_argument("--webui", action="store_true", help="启动WebUI模式")
    parser.add_argument("--port", type=int, default=7860, help="WebUI端口")
    parser.add_argument("--input", "-i", type=str, help="输入文本文件路径")
    parser.add_argument("--input-docx", "-d", type=str, help="输入Word文档路径（支持多模态：图片、表格）")
    parser.add_argument("--tts-mode", type=str, default=None, help="TTS模式: cosyvoice, edge, api")
    args, unknown = parser.parse_known_args()

    if args.webui:
        from app import main as webui_main
        webui_main(port=args.port)
    else:
        # 将参数传递给 run_cli
        import sys
        sys.argv = [sys.argv[0]] + unknown
        run_cli(args.input, args.tts_mode, args.input_docx)


def run_cli(input_text=None, tts_mode=None, input_docx=None):
    """命令行模式"""
    print("PPT-TTS-Project")
    print(f"LLM模式: {LLM_MODE}")
    print(f"TTS模式: {tts_mode or TTS_MODE}")
    print()

    runner = PipelineRunner()

    # 获取输入
    input_text_value = None

    if input_docx:
        # 多模态模式
        input_docx_value = input_docx
    elif input_text:
        input_file = Path(input_text)
        if input_file.exists():
            with open(input_file, 'r', encoding='utf-8') as f:
                input_text_value = f.read()
    else:
        # 默认使用 input.txt
        default_input = Path("data/input/input.txt")
        if default_input.exists():
            with open(default_input, 'r', encoding='utf-8') as f:
                input_text_value = f.read()

    runner.run_full_pipeline(
        input_text=input_text_value,
        tts_mode=tts_mode,
        input_docx=input_docx
    )


if __name__ == "__main__":
    main()
