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

Requirements files hierarchy: `requirements.txt` (meta/entry), `requirements-gpu.txt` (PyTorch 2.4.0 CUDA 12.6 + onnxruntime-gpu), `requirements-cpu.txt` (minimal: python-pptx, python-docx, gradio, openai, svglib), `requirements-cosyvoice-minimal.txt` (CosyVoice inference stack only).

### Running
```bash
# Convenience launcher (recommended)
bash start.sh webui              # WebUI on port 7860
bash start.sh webui 8080         # WebUI on custom port
bash start.sh cli                # CLI mode (reads data/input/input.txt)
bash start.sh status             # Check project state

# Direct python invocation
python main.py                                    # CLI with default input
python main.py --input path/to/text.txt           # CLI with custom text
python main.py --input-docx path/to/document.docx  # CLI with Word doc (multimodal)
python main.py --ppt-mode ppt-master               # Use SVG→native shapes mode
python main.py --webui --port 7860                 # WebUI
```

### Testing
```bash
python test/test_config.py
```

### Model download (offline deployment)
```bash
python download_model.py           # CosyVoice-300M-SFT (3 fallback methods: ModelScope, HuggingFace, wget)
python download_model.py --check   # Verify model exists
python download_packages.py        # pip wheels for offline install (Python 3.10 + CUDA 12.6)
```

### Diagnostic
```bash
python check_ppt.py   # Validates generated.pptx internals: layout refs, slide refs, cross-reference checks
```

## Architecture

### Three PPT Generation Modes

The pipeline has **three** PPT generation strategies, selected via `PPT_GENERATION_MODE` env var or `--ppt-mode` CLI flag:

| Mode | Description | Input paths | What it does |
|------|-------------|-------------|--------------|
| `basic` | Original python-pptx shapes | Text only | Parses .docx outline, builds slides programmatically with python-pptx |
| `template` | Template copy from `src/模板1.pptx` | Multimodal only | Copies the template .pptx, clears shapes, rebuilds per-slide content with layout indices (TITLE=0, CONTENT=1, END=2). Supports left-text/right-image split layout with aspect-ratio-preserving image scaling |
| `ppt-master` | SVG → native DrawingML shapes | Text + multimodal | LLM generates per-slide SVGs, then `src/ppt_master/svg_to_pptx/` converts them to native PowerPoint shapes (rects, circles, text, paths, etc.) with optional animations and transitions |

**Important**: `template` mode only works for the multimodal (docx) path. The text path only supports `basic` and `ppt-master`.

### Dual Input Paths

**Text path**: `text → outline(LLM) → ppt_generation → extract → narration → audio → embed`
**Multimodal path**: `docx → [extract_from_docx → build_slides → simplify(LLM) → ppt_generation] → extract → narration → audio → embed`

Steps 3-6 (extract through embed) are shared between both paths.

### Pipeline Flow (6 Steps)

0. **Backup** — timestamps and copies previous `data/output/` into `data/backup/`
1. **Text → Outline** (`src/outline_generator.py`) — LLM generates structured Word outline from input text
2. **Outline → PPT** (`src/ppt_generator.py`) — Dispatches to one of the three generation strategies (see table above)
3. **Extract Text** (`src/slides_extractor.py`) — Extracts text from generated PPT, handles GroupShape recursion
4. **Generate Narration** (`src/narration_generator.py`) — LLM generates voiceover script per slide; has offline fallback with hardcoded templates
5. **Generate Audio** (`src/audio_generator.py`) — TTS via CosyVoice (local, 22kHz output via soundfile) or Edge TTS (cloud)
6. **Embed Audio** (`src/audio_embedder.py`) — Unzips .pptx, injects audio shape XML via `</p:spTree>` replacement + timing XML via `</p:sld>` replacement, repacks with ZIP_DEFLATED in OPC-compliant order

### ppt-master Module (`src/ppt_master/`) — SVG→Native PPTX Engine

The largest subsystem (~10K lines across 34 files), integrated in commit `514451e`. It converts LLM-generated SVGs into native PowerPoint DrawingML shapes, producing a .pptx with real editable shapes instead of embedded images.

**Key pipeline** (`src/ppt_master/svg_to_pptx/pptx_builder.py:create_pptx_with_native_svg()`):
1. Creates a base PPTX with python-pptx (slide masters, layouts)
2. For each SVG: converts elements to DrawingML XML via `drawingml_converter.py`, builds slide XML, manages media files
3. Attaches animations (`src/ppt_master/pptx_animations.py`) and transitions per slide
4. Optionally injects narration audio with auto-advance timings (`pptx_narration.py`)
5. In dual mode: also pre-renders PNGs in parallel (`ProcessPoolExecutor`) for legacy Office compatibility

**DrawingML conversion chain** (`svg_to_pptx/`):
- `drawingml_converter.py` — Entry point: processes `<g>` groups, resolves z-order, identifies "chrome" elements (background, header, footer, decorations) to exclude from animation cascades
- `drawingml_elements.py` — Converts individual SVG elements (`<rect>`, `<circle>`, `<path>`, `<text>`, `<image>`, etc.) into native DrawingML XML
- `drawingml_styles.py` — Converts SVG visual properties (fill, stroke, opacity, gradients, text formatting, drop shadows) to DrawingML equivalents
- `drawingml_paths.py`, `drawingml_utils.py`, `drawingml_context.py` — Path geometry conversion, SVG namespace handling, transform matrix parsing
- `pptx_media.py` — PNG rendering via svglib+reportlab with content-hash-based caching
- `animation_config.py` — Loads `animations.json` sidecar for per-slide animation overrides, validates targets against actual SVG structure

**Animation system** (`src/ppt_master/pptx_animations.py`):
- 7 transitions: fade, push, wipe, split, strips, cover, random
- 21 entrance effects: appear, fade, fly, cut, zoom, wipe, split, blinds, checkerboard, dissolve, random_bars, peek, wheel, box, circle, diamond, plus, strips, wedge, stretch, expand, swivel
- 3 trigger modes: on-click, with-previous, after-previous
- Modes: single effect, 'mixed' (cycles through curated pool), 'random'

**CLI** (`svg_to_pptx/pptx_cli.py`): Standalone SVG→PPTX converter with `--native`/`--legacy`, `--transition`, `--animation`, `--workers`, `--cache-dir` flags.

### ppt-master Generator Bridge (`src/ppt_master_generator.py`)

Connects the pipeline to ppt-master. Two entry points `run_ppt_master()` (text path) and `run_ppt_master_multimodal()` (docx path) each:
1. Parse input into slide data structures
2. Call LLM to generate per-slide SVGs (using comprehensive `SVG_CONVENTIONS`: 1280×720 viewBox, layout grid with TITLE/CONTENT/FOOTER zones, z-order rules, color conventions)
3. Validate SVGs (non-blocking: viewBox dimensions, text positioning outliers)
4. Convert SVGs to PPTX via ppt-master's `create_pptx_with_native_svg()`

### LLM Client Pattern

The codebase uses a dual-client pattern (`src/config.py:83-96`):
- **`LLM_MODE=api`**: Uses `anthropic.Anthropic` client pointing at MiniMax's Anthropic-compatible endpoint (`https://api.minimaxi.com/anthropic`)
- **`LLM_MODE=local`**: Uses `openai.OpenAI` client pointing at SGlang v1 endpoint

This means Anthropic SDK calls (`.messages.create()`) for API mode, OpenAI SDK calls (`.chat.completions.create()`) for local mode. Responses are unwrapped differently per path (blocks vs choices).

### PipelineRunner (main.py)

`PipelineRunner` wraps the full pipeline with pause/resume/stop via threading primitives:
- `_stop_event` (`threading.Event`) — cancellation
- `_pause_event` (`threading.Event`) — suspension; `_check_pause()` blocks on `_pause_event.wait()`
- `_lock` (`threading.Lock`) — thread-safe logging
- Shared between CLI and WebUI; the WebUI runs each step in a `daemon=True` thread

### WebUI (app.py)

6-tab Gradio interface (port 7860 default):
1. **Configuration** — LLM/TTS/PPT mode settings, hot-swapped at runtime (temporarily mutates `src.config` globals, restores in `finally`)
2. **Input** — Text area + Word document upload
3. **Execution** — 6 step buttons + full pipeline + stop/pause/resume + status log with 3-second JS auto-refresh
4. **Output Files** — Downloads for generated artifacts
5. **Audio** — Individual slide MP3 downloads
6. **Backup** — Browse historical backups

### Key Modules

| Module | Purpose |
|--------|---------|
| `src/config.py` | Env-driven config, dual LLM client factory, directory setup, `_clean_api_key()` strips non-printable chars |
| `src/outline_generator.py` | Text→Word outline, LLM prompt with offline fallback |
| `src/ppt_generator.py` | All three PPT strategies: `run()` (basic/ppt-master), `run_multimodal()` (basic/template/ppt-master), plus `simplify_slides_text()` (LLM condenses to 3-5 bullets), `build_slides_from_extracted()`, `generate_pptx_with_images()` |
| `src/docx_extractor.py` | `DocxExtractor` class: parses .docx heading hierarchy with Chinese heading style support (`章标题`, `一级条标题`, etc.), extracts inline images from `<a:blip>` elements with dedup, title detection with 6-priority fallback |
| `src/multimodal_outline_generator.py` | Builds slides_data structure from extracted docx blocks |
| `src/ppt_master_generator.py` | LLM-driven SVG generation bridge with comprehensive SVG design conventions, image dimension calculation via PIL, table rendering rules |
| `src/ppt_master/` | SVG→native PPTX engine (see dedicated section above) |
| `src/audio_generator.py` | CosyVoice (submodule, soundfile 22kHz output) or Edge TTS |
| `src/audio_embedder.py` | XML injection into .pptx zip — adds audio shapes, relationships, timing |
| `src/backup.py` | Timestamped backup/restore of output directory |
| `check_ppt.py` | Diagnostic: validates .pptx internal structure (layout refs, slide refs, cross-reference validation) |

Note: There are two independent audio embedding implementations — `src/audio_embedder.py` (used by the main pipeline, step 6) and `src/ppt_master/svg_to_pptx/pptx_narration.py` (used by ppt-master's standalone CLI for native narration injection with auto-advance timings).

### LLM/TTS Configuration (`.env` / `src/config.py`)

- **LLM_MODE**: `api` (MiniMax via Anthropic SDK) or `local` (SGlang+Qwen3.5-9B via OpenAI SDK)
- **TTS_MODE**: `cosyvoice` (local CosyVoice-300M-SFT), `edge` (Microsoft Edge TTS), or `api`
- **PPT_GENERATION_MODE**: `basic`, `template`, or `ppt-master` (see architecture section)
- **COSYVOICE_MODE**: `sft` (default), `naive`, or `pretrained`
- **EDGE_VOICE**: default `zh-CN-XiaoxiaoNeural`
- CosyVoice model path: `models/iic/CosyVoice-300M-SFT/`
- CosyVoice is a git submodule at `CosyVoice/` — requires `Matcha-TTS` in its sys.path (injected at runtime in `audio_generator.py`)
- The `.env.example` has `COSYVOICE_SPEAKER=ChineseFemale` but `src/config.py` defaults to `中文女`

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
│       ├── images/
│       └── tables/
├── audio/                       # Generated MP3 files (slide_001.mp3, ...)
└── backup/                      # Timestamped backups
logs/
└── webui.log                    # WebUI runtime logs
```
