# Shadowing Audio Generator

Tool to generate shadowing practice audios for language learning (Hungarian → English).

> **Python version**: Use **Python 3.12**. Uses uv for venv management.

Uses pyttsx3 (local, offline) for Question TTS and ElevenLabs TTS + WhisperX forced alignment for precise repetition blocks.

## Features
- Input JSONs in `input/` folder with `vocabulary` list, `format` (Monologue/Conversation), `tone` (Tégezni/Magázni)
- Metadata saved to dedicated `topic_metadata` table (main table altered for source_file)
- Supports multiple topics/files with clean topic-based audio organization
- Custom repetition scripting with `[block break=1.0 multiplier=1.5]` markup
- Exports clean Markdown + PDF (same basename) to output/exports/
- Robust temp file handling (Windows compatible)

## Installation

**Requirements:**
- Python 3.12
- uv (Python package manager)

1. **Install FFmpeg** (CRITICAL):
   Run in **PowerShell as Administrator**:
   ```powershell
   winget install ffmpeg
   ```
   Close and reopen your terminal/VS Code completely, then verify:
   ```powershell
   ffmpeg -version
   ffprobe -version
   ```

2. Install dependencies:
   ```powershell
   uv sync
   ```
   This creates/uses the `.venv` with the correct Python version.

3. Copy `.env.example` to `.env` and fill in your API keys (ElevenLabs + XAI).

4. Place your input JSON file(s) in the `input/` folder.

## Usage

```bash
// venv
.venv\Scripts\activate   
deactivate

python main.py --json shadowing_source_input.json
python main.py --json another_topic.json --overwrite
python main.py --export-only
```

### Arguments
- `--json, -j`: Path to JSON file (default: `input/shadowing_source_input.json`)
- `--overwrite, -o`: Regenerate existing audios
- `--export-only`: Only export markdown from current DB

## Project Structure
```
output/
  audio/
    fizikai_cselekvesek/          # topic-based folders
      q_001.mp3
      a_init_001.mp3
      shadowing/
        shadow_001.mp3
  exports/
    fizikai_cselekv_sek_mozg_sok_s_interakci_k.md
    fizikai_cselekv_sek_mozg_sok_s_interakci_k.pdf
    shadowing_transcripts.md
shadowing.db                      # SQLite with entries + topic_metadata (vocabulary, format, tone)
```

## AGENTS.md
This file is updated after major changes. Always update `README.md` when adding significant features or changing usage.

## Notes
- Do not edit `.env`
- Do not run Python scripts directly via agent (use manual execution)
- After changes, commit with meaningful message
