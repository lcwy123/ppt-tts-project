# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PPT-TTS-Project is a fully automated PPT voiceover generation system with local offline deployment support.

## Commands

### Installation
```bash
# GPU version (with CosyVoice TTS)
pip install -r requirements-gpu.txt

# CPU version (without TTS)
pip install -r requirements-cpu.txt

# Offline deployment
pip install --no-index --find-links=packages/ -r requirements-gpu.txt
```

### Running
```bash
# CLI mode (text input from data/input/input.txt)
python main.py

# CLI mode with text file
python main.py --input path/to/text.txt

# WebUI mode
python main.py --webui --port 7860
```

### Testing
```bash
python test/test_config.py
```

## Architecture

### Pipeline Flow (6 Steps)
The system runs a 6-step pipeline orchestrated by `PipelineRunner` in `main.py`:

0. **Backup** - Backs up previous outputs before generating new ones
1. **Text → Outline** (`src/outline_generator.py`) - LLM generates structured Word outline from input text
2. **Outline → PPT** (`src/ppt_generator.py`) - Generates PPT from Word outline using python-pptx
3. **Extract Text** (`src/slides_extractor.py`) - Extracts text from generated PPT
4. **Generate Narration** (`src/narration_generator.py`) - LLM generates voiceover script per slide
5. **Generate Audio** (`src/audio_generator.py`) - TTS synthesis using CosyVoice (local) or Edge TTS
6. **Embed Audio** (`src/audio_embedder.py`) - Embeds audio into PPT with playback triggers

### Key Modules

| Module | Purpose |
|--------|---------|
| `src/config.py` | Configuration management via environment variables and `.env` |
| `src/outline_generator.py` | LLM generates structured Word outline from input text |
| `src/ppt_generator.py` | Generates PPT from Word outline using python-pptx |
| `src/audio_generator.py` | CosyVoice-300M-SFT local TTS, Edge TTS, or API TTS |

### LLM/TTS Configuration (`src/config.py`)
- **LLM_MODE**: `api` (MiniMax, default) or `local` (SGlang+Qwen3.5-9B)
- **TTS_MODE**: `cosyvoice` (local CosyVoice-300M-SFT), `edge` (Microsoft Edge TTS), or `api`
- CosyVoice model path: `models/iic/CosyVoice-300M-SFT/`

### Data Directory Structure
```
data/
├── input/input.txt          # Input text
├── output/
│   ├── ppt_outline.docx     # Generated Word outline
│   ├── generated.pptx       # Generated PPT
│   ├── slides_text.txt      # Extracted PPT text
│   ├── narration.txt        # Generated narration script
│   ├── audio_durations.json # Audio duration metadata
│   └── final_with_audio.pptx # Final PPT with audio
├── audio/                   # Generated MP3 files
└── backup/                   # Historical backups
```

### Backup/Restore
Run `restore_from_backup()` or `list_backups()` to manage historical outputs.
