# Shadowing Audio Generator

Tool to generate **shadowing practice audios for language learning** (Hungarian → English) with **auto-injected breaks based on predefined repetition markers**.

## What This Code Does

This project creates shadowing audios for language learning. The key workflow:

1. **Input**: JSON files containing vocabulary lists, questions/answers, and special repetition markup tags
2. **Question TTS**: Uses pyttsx3 (local, offline) to generate question audio
3. **Answer TTS**: Uses ElevenLabs API to generate the initial answer audio
4. **Shadowing Generation**: Uses **WhisperX forced alignment** to precisely locate each word in the audio, then:
   - Splits the audio into individual word segments
   - Applies custom repetition patterns defined in `answer_metadata`
   - Auto-injects breaks (silence) based on `[block break=X multiplier=Y]` markers
   - Creates multiple repetitions per phrase with varying spacing

### Repetition Markers

The system uses special markup in `answer_metadata`:

- `[block break=1.0 multiplier=1.4]` - Sets a 1.0s break after the block, 1.4x spacing multiplier
- `[repeat]...phrase...[/repeat]` - Marks a phrase to be repeated (creates multiple shadowing iterations)
- `|+1|, |+2|` - Adds extra pause after the phrase (+1 = +500ms, +2 = +1000ms)

Example:
```
[block break=1.0 multiplier=1.4]
Reggel hatkor kelek.
[repeat]
Reggel hatkor
kelek
Reggel hatkor kelek
[/repeat]
```

This creates: "Reggel hatkor kelek" with 3 repetitions and appropriate breaks.

> **Python version**: Use **Python 3.12**. Uses uv for venv management.

## Installation

### 1. Install FFmpeg (CRITICAL)

Run in **PowerShell as Administrator**:
```powershell
winget install ffmpeg
```

Close and reopen your terminal/VS Code completely, then verify:
```powershell
ffmpeg -version
ffprobe -version
```

### 2. Install Dependencies

```powershell
uv sync
```
This creates/uses the `.venv` with the correct Python version.

### 3. Copy and Configure Environment

```powershell
copy examples\sample.env .env
```

Edit `.env` and add your **ElevenLabs API Key** (required):
- Get your API key from: https://elevenlabs.io/app/settings/api-key
- Replace `sk_example_00000000000000000000000000000000` with your actual key

(Optional) Add XAI_API_KEY for German translations in PDF exports.

### 4. Place Input JSON

Copy your input JSON to the `input/` folder (see `examples/sample_input.json` for format).

## Usage

### Activate Virtual Environment

```powershell
.venv\Scripts\activate
deactivate
```

### Generate Audios

```bash
# Basic usage
python main.py --json shadowing_source_input.json

# Another topic
python main.py --json another_topic.json --overwrite

# Export only (from current DB)
python main.py --export-only
```

### Arguments

- `--json, -j`: Path to JSON file (default: `input/shadowing_source_input.json`)
- `--overwrite, -o`: Regenerate existing audios
- `--export-only`: Only export markdown from current DB
- `--export-all`: Export all topics regardless of JSON input
- `--export-name`: Custom export filename (default: `shadowing_transcripts.md`)
- `--include-translations`: Include German translations in PDF export (requires XAI_API_KEY)
- `--publish`: Upload episode to Castopod after generation

## Input JSON Format

See `examples/sample_input.json`:

```json
{
  "topic": "Example: Daily Routine",
  "vocabulary": ["kel", "mos", "eszik"],
  "format": "Monologue",
  "tone": "Tégezni",
  "shadowing_source": [
    {
      "question": "Meséld el, kérlek, hogyan telik egy tipikus napod!",
      "answer": "Reggel hatkor kelek. Mosdatok és reggelizek.",
      "answer_metadata": "[block break=1.0 multiplier=1.4]\nReggel hatkor kelek.\n[repeat]\nReggel hatkor\nkelek\nReggel hatkor kelek\n[/repeat]\n..."
    }
  ]
}
```

The `answer_metadata` field contains the shadowing script with repetition markers.

## Project Structure

```
ShadowAudGen/
├── main.py                 # CLI entry point
├── generator.py            # Audio generation logic
├── shadower_util.py       # Shadowing track creation with WhisperX
├── exporter.py            # Markdown/PDF export
├── publisher.py          # Castopod publishing
├── config.py             # Configuration & constants
├── db.py                 # SQLite database operations
├── utils.py              # Utility functions
├── pyproject.toml        # Project dependencies
├── examples/             # Example input files
│   ├── sample_input.json
│   └── sample.env
├── input/                 # Input JSON files
├── output/
│     <topic>/
│         audio/
│            q_001.mp3    # Question audio
│            a_init_001.mp3  # Initial answer
│         shadowing/
│            shadow_001.mp3   # Custom shadowing audio
│         exports/
│           <topic>.md
│           <topic>.pdf
├── res/                   # Resources (intro, outro, cover)
└── docs/                  # Documentation
```

## API Keys

- **ElevenLabs** (required): https://elevenlabs.io/app/settings/api-key
- **XAI** (optional): https://console.x.ai/ (for German translations)

## Troubleshooting

### FFmpeg not found
- Restart your terminal/VS Code completely after installing FFmpeg
- Verify with `ffmpeg -version`

### API Key errors
- Make sure `.env` is in the project root (same folder as main.py)
- Verify the key format: should start with `sk_`

### WhisperX errors
- Ensure FFmpeg is properly installed and accessible in PATH
- First run may be slow as it downloads the Whisper model