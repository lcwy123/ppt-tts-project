# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PPT-TTS-Project is a fully automated PPT voiceover generation system with local offline deployment support. It supports two input paths: plain text (LLM generates outline then PPT) and Word document multimodal (documents with images/tables generate PPT directly).

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
# CLI mode — text input from data/input/input.txt
python main.py

# CLI mode with custom text file
python main.py --input path/to/text.txt

# CLI mode with Word document (multimodal — preserves images/tables)
python main.py --input-docx path/to/document.docx

# WebUI mode (Gradio, supports both text and docx upload)
python main.py --webui --port 7860
```

### Testing
```bash
python test/test_config.py
```

### Model download (offline deployment)
```bash
python download_model.py        # CosyVoice-300M-SFT model
python download_packages.py     # pip wheel packages for offline install
```

## Architecture

### Dual Input Paths

The pipeline has two distinct input paths that diverge at step 2:

**Text path** (original): `text → outline(LLM) → ppt_basic → extract → narration → audio → embed`
**Multimodal path** (docx): `docx → [extract_from_docx → build_slides → simplify(LLM) → ppt_template_copy] → extract → narration → audio → embed`

Steps 3-6 (extract through embed) are shared between both paths. The multimodal path skips the standalone outline generation step — it extracts content blocks directly from the Word document's heading hierarchy.

### Pipeline Flow (6 Steps)

0. **Backup** — timestamps and copies previous `data/output/` into `data/backup/`
1. **Text → Outline** (`src/outline_generator.py`) — LLM generates structured Word outline from input text
2. **Outline → PPT** (`src/ppt_generator.py`) — Two generation strategies:
   - `run()`: parses .docx outline, builds slides with python-pptx (text-only path)
   - `run_multimodal()`: extracts docx content, calls `build_slides_from_extracted()` + `simplify_slides_text()` (LLM condenses), then copies `src/模板1.pptx` as a template and builds slides on it
3. **Extract Text** (`src/slides_extractor.py`) — Extracts text from generated PPT, handles GroupShape recursion
4. **Generate Narration** (`src/narration_generator.py`) — LLM generates voiceover script per slide
5. **Generate Audio** (`src/audio_generator.py`) — TTS via CosyVoice (local, 22kHz output via soundfile) or Edge TTS (cloud)
6. **Embed Audio** (`src/audio_embedder.py`) — Unzips .pptx, injects audio shape XML + relationship entries per slide, repacks with ZIP_DEFLATED

### LLM Client Pattern

The codebase uses a dual-client pattern (`src/config.py:77-98`):
- **`LLM_MODE=api`**: Uses `anthropic.Anthropic` client pointing at MiniMax's Anthropic-compatible endpoint (`https://api.minimaxi.com/anthropic`)
- **`LLM_MODE=local`**: Uses `openai.OpenAI` client pointing at SGlang v1 endpoint

This means Anthropic SDK calls (`.messages.create()`) for API mode, OpenAI SDK calls (`.chat.completions.create()`) for local mode. Responses are unwrapped differently per path (blocks vs choices).

### Key Modules

| Module | Purpose |
|--------|---------|
| `src/config.py` | Env-driven config, dual LLM client factory, directory setup |
| `src/outline_generator.py` | Text→Word outline, LLM prompt with offline fallback |
| `src/ppt_generator.py` | Both pptx generation strategies (basic + template-based multimodal) |
| `src/docx_extractor.py` | Parses .docx heading hierarchy, extracts inline images, saves to `data/output/extracted/` |
| `src/multimodal_outline_generator.py` | Builds slides_data structure from extracted docx blocks |
| `src/audio_generator.py` | CosyVoice (submodule, soundfile output) or Edge TTS |
| `src/audio_embedder.py` | XML injection into .pptx zip — adds audio shapes, relationships, timing |
| `src/backup.py` | Timestamped backup/restore of output directory |
| `check_ppt.py` | Diagnostic: validates .pptx internal structure (layout refs, slide refs) |

### LLM/TTS Configuration (`.env` / `src/config.py`)

- **LLM_MODE**: `api` (MiniMax via Anthropic SDK) or `local` (SGlang+Qwen3.5-9B via OpenAI SDK)
- **TTS_MODE**: `cosyvoice` (local CosyVoice-300M-SFT), `edge` (Microsoft Edge TTS), or `api`
- CosyVoice model path: `models/iic/CosyVoice-300M-SFT/`
- CosyVoice is a git submodule at `CosyVoice/` — requires `Matcha-TTS` in its sys.path
- The `.env.example` has a `COSYVOICE_SPEAKER=ChineseFemale` value but `src/config.py` defaults to `中文女`

### Data Directory Structure
```
data/
├── input/input.txt              # Text input
├── output/
│   ├── ppt_outline.docx         # Word outline
│   ├── generated.pptx           # Generated PPT
│   ├── slides_text.txt          # Extracted PPT text
│   ├── narration.txt            # Narration script
│   ├── audio_durations.json     # Audio duration metadata
│   ├── final_with_audio.pptx    # Final PPT with embedded audio
│   └── extracted/               # Images/tables from docx (multimodal mode)
├── audio/                       # Generated MP3 files (slide_001.mp3, ...)
└── backup/                      # Timestamped backups
```
