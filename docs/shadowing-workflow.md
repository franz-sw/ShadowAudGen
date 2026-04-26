# Shadowing Audio Workflow

## Overview
The shadowing feature creates specialized language learning audio tracks with precise repetition patterns. It combines text markup parsing, AI-powered audio alignment, and pydub-based audio editing.

**Main entry point:** `AudioGenerator.generate_shadowing_audio()` in `generator.py`

**Core logic:** `ShadowingPreparer` class in `shadower_util.py`

## Workflow Steps

1. **Initial Audio Generation**
   - `generate_initial_audios()` uses ElevenLabs TTS to create `a_init_XXX.mp3`
   - Stored in topic-specific folders under `audio/`

2. **Shadowing Track Creation** (`generate_shadowing_audio()`)
   - Loads initial answer audio
   - Reads structured markup from `answer_metadata` (or falls back to `answer`)
   - Delegates to `ShadowingPreparer.create_shadowing_track()`

3. **Script Parsing** (`_parse_script()`)
   - Parses idiomatic markup:
     ```markdown
     [block break=1.0 multiplier=1.5]
     Full sentence here.
     [repeat]
     First chunk
     Second chunk |+2|
     Full sentence here.
     [/repeat]
     ```
   - Supports `break`, `multiplier`, `segment_break`, `ignore_repeat`, and extra repetition markers `|+N|`

4. **Word-Level Audio Alignment** (`_get_aligned_words()`)
   - **Library:** [whisperx](https://github.com/m-bain/whisperX)
   - **Model:** Whisper (large model from `config.WHISPER_MODEL_NAME`, int8 quantized on CPU)
   - Process:
     - Transcribe full audio with forced language (`hu` by default)
     - Load alignment model: `whisperx.load_align_model()`
     - Run forced alignment: `whisperx.align()` → produces precise per-word timestamps
   - Output: List of word objects with `start`, `end`, and `word`

5. **Audio Extraction** (`_extract_audio()`)
   - Cleans target text and aligned words (lowercase, remove punctuation)
   - Searches for exact contiguous word sequence match
   - Falls back to fuzzy substring match
   - Slices original audio using millisecond timestamps from alignment
   - Returns pydub `AudioSegment`

6. **Audio Assembly** (`_process_repeats()` + main loop)
   - Lead-in silence
   - Full sentence + configured break
   - Repeated chunks (default 2 plays + extras)
   - Gap calculation: `segment_length * multiplier + SEGMENT_BREAK_MS`
   - Final silence
   - Exports as MP3 (`192k` bitrate)

## Key Files
- `shadower_util.py` — Core logic (313 lines)
- `generator.py` — Orchestration and DB integration
- `config.py` — Whisper model, SEGMENT_BREAK_MS, language defaults

## Dependencies
- `pydub` — Audio manipulation
- `whisperx` — Transcription + forced alignment
- FFmpeg (required for pydub)

## Output
- Saved as `shadow_XXX.mp3` in `audio/<topic>/shadowing/`
- Path recorded in SQLite database

See `shadower_util.py` docstring for full markup examples.
