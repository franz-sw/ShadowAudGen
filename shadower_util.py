"""
Shadowing Preparer - Multi-Sentence Support
================================================

EXPLANATION OF PARAMETERS:
- block break: The silence duration (in seconds) after the initial full sentence is played. 
                E.g., `break=1.0` means a 1-second pause before the repeats start.
- multiplier: Determines the length of the silence gap between repetitions, calculated 
               as a multiple of the audio segment's length. E.g., `multiplier=1.5` means 
               the pause is 1.5x the length of the spoken chunk.
- segment_break: Additional silence from config.py (SEGMENT_BREAK_MS), applied on top of multiplier gap.

IDIOMATIC INPUT FORMAT:

[block break=1.0 multiplier=1.5]
Értem. A helyzet a következő.
[repeat]
A helyzet
a következő
Értem. A helyzet a következő.
[/repeat]

[block break=1.0 multiplier=1.5 segment_break=0.5]
A laktanyában mindenki megtisztítja a csizmáját és letörli róla a sarat.
[repeat]
A laktanyában
mindenki megtisztítja a csizmáját |+1|
és letörli róla a sarat
A laktanyában mindenki megtisztítja a csizmáját és letörli róla a sarat.
[/repeat]

The `|+2|` marker adds 2 extra 
repetitions (on top of the standard 1 repeat) for difficult words.

The additional break between segment plays comes from SEGMENT_BREAK_MS in config.py (default 500ms),
applied on top of the multiplier gap. For example, `multiplier=1.5` with a 500ms audio 
segment: gap = (500 * 1.5) + 500 = 1250ms
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple
import re
import shutil
import os
import warnings
import string
import unicodedata
import difflib

from pydub import AudioSegment
import whisperx
import numpy as np

from config import WHISPER_MODEL_STORAGE, WHISPER_MODEL_NAME, SEGMENT_BREAK_MS, DEFAULT_LANGUAGE

class AlignmentError(Exception):
    """Exception raised when audio alignment fails."""
    pass

# Global parameters
model_storage = WHISPER_MODEL_STORAGE
model_name = WHISPER_MODEL_NAME

# Cache for the models so they are only downloaded/loaded once
_whisper_model = None
_align_models = {}

@dataclass
class ShadowingConfig:
    """Global default parameters."""
    default_multiplier: float = 1.5
    default_initial_break_ms: int = 1500
    default_language: str = DEFAULT_LANGUAGE
    output_dir: str = "shadowing_output"
    lead_in_ms: int = 600
    final_silence_ms: int = 1000
    bitrate: str = "320k"
    midpoint_cuts: bool = False
    chunk_fade_out_ms: int = 30


@dataclass
class SentenceBlock:
    """Represents a single sentence and its repetition rules."""
    initial_text: str = ""
    # Stores tuples of (text_chunk, extra_repetitions)
    repeat_chunks: List[Tuple[str, int]] = field(default_factory=list)
    initial_break_ms: int = 1000
    multiplier: float = 1.5
    ignore_repeat: bool = False


class ShadowingPreparer:
    """
    Creates shadowing tracks that follow your exact repetition schema 
    across multiple sentences with custom metadata.
    """
    
    def __init__(self, config: Optional[ShadowingConfig] = None):
        self.config = config or ShadowingConfig()
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """Check if ffmpeg and ffprobe are available."""
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            print("\n❌ ERROR: FFmpeg is not installed or not in your PATH!")
            print("   This is required for audio processing (pydub + whisperx).")
            print("\n   Fix by running this command in PowerShell (as Administrator):")
            print("   winget install ffmpeg")
            print("\n   Then CLOSE and reopen your terminal / VS Code.")
            print("   After that run: ffmpeg -version")
            raise RuntimeError("FFmpeg not found. Please install it using 'winget install ffmpeg'")

    def create_shadowing_track(
        self,
        audio_path: str,
        script: str,
        output_filename: Optional[str] = None,
        language: Optional[str] = None
    ) -> str:
        """
        Main function.
        
        Args:
            audio_path: Path to the original .mp3
            script: Text using [block] and [repeat] tags
            output_filename: Optional name for the output file
            language: Language code for transcription (default hu, no autodetect)
        """
        sound = AudioSegment.from_file(audio_path)
        output = AudioSegment.silent(self.config.lead_in_ms)
        
        blocks = self._parse_script(script)
        effective_lang = language or self.config.default_language
        
        print("Transcribing and aligning audio... This may take a moment.")
        aligned_words = self._get_aligned_words(sound, effective_lang)
        
        for block in blocks:
            # 1. Initial full sentence + break
            if block.initial_text:
                audio = self._extract_audio(sound, block.initial_text, aligned_words, self.config.midpoint_cuts)
                output += audio
                output += AudioSegment.silent(block.initial_break_ms)
            
            # 2. Process repeat chunks if not ignored
            if not block.ignore_repeat and block.repeat_chunks:
                output = self._process_repeats(
                    output, sound, block.repeat_chunks, block.multiplier, aligned_words
                )
        
        output += AudioSegment.silent(self.config.final_silence_ms)
        
        out_path = self.output_dir / (output_filename or Path(audio_path).stem + "_shadowing.mp3")
        output.export(str(out_path), format="mp3", bitrate=self.config.bitrate)
        print(f"✅ Shadowing track saved: {out_path}")
        return str(out_path)

    def _parse_script(self, script: str) -> List[SentenceBlock]:
        """Parse the clean idiomatic markup into multiple blocks."""
        blocks: List[SentenceBlock] = []
        current_block: Optional[SentenceBlock] = None
        in_repeat = False
        
        lines = [line.strip() for line in script.split('\n') if line.strip()]
        
        for line in lines:
            # Start of a new sentence block
            if line.startswith('[block'):
                current_block = SentenceBlock(
                    initial_break_ms=self.config.default_initial_break_ms,
                    multiplier=self.config.default_multiplier
                )
                
                # Parse metadata
                break_match = re.search(r'break=([\d.]+)', line)
                if break_match:
                    current_block.initial_break_ms = int(float(break_match.group(1)) * 1000)
                    
                mult_match = re.search(r'multiplier=([\d.]+)', line)
                if mult_match:
                    current_block.multiplier = float(mult_match.group(1))
                
                if 'ignore_repeat=true' in line.lower():
                    current_block.ignore_repeat = True
                    
                blocks.append(current_block)
                in_repeat = False
                continue
                
            if current_block is None:
                continue # Skip text that isn't in a block
                
            if line.startswith('[repeat'):
                in_repeat = True
                continue
                
            if line.startswith('[/repeat]') or line.startswith('[/]'):
                in_repeat = False
                continue
                
            if in_repeat:
                # Check for extra repetitions marker, e.g., |+2|
                match = re.search(r'\|\+(\d+)\|', line)
                if match:
                    extra_repeats = int(match.group(1))
                    clean_line = line[:match.start()].strip()
                    current_block.repeat_chunks.append((clean_line, extra_repeats))
                else:
                    current_block.repeat_chunks.append((line, 0))
            elif not current_block.initial_text and not line.startswith('['):
                current_block.initial_text = line
                
        return blocks

    def _process_repeats(
        self,
        output: AudioSegment,
        sound: AudioSegment,
        chunks: List[Tuple[str, int]],
        multiplier: float,
        aligned_words: List[dict]
    ) -> AudioSegment:
        """Each chunk is played twice by default, plus any extra repetitions."""
        for text, extra_repeats in chunks:
            if not text:
                continue
            segment = self._extract_audio(sound, text, aligned_words, self.config.midpoint_cuts)
            gap_ms = int(len(segment) * multiplier)
            
            # Initial play (1) + standard repeat (1) + any extra repetitions requested
            total_plays = 2 + extra_repeats 
            for _ in range(total_plays):
                output = output.append(segment, crossfade=50)
                output += AudioSegment.silent(gap_ms + SEGMENT_BREAK_MS)
                
        return output


    def _get_aligned_words(self, sound: AudioSegment, language: str) -> List[dict]:
        global model_storage, model_name, _whisper_model, _align_models
        
        # 1. Download/Load the whisper model if not already done
        if _whisper_model is None:
            os.makedirs(model_storage, exist_ok=True)
            # Change device="cuda" and compute_type="float16" if you have a GPU
            _whisper_model = whisperx.load_model(
                model_name, 
                device="cpu", 
                compute_type="int8", 
                download_root=model_storage
            )
            
        # 2. Convert AudioSegment to numpy array directly (avoids torchcodec issues with FFmpeg 8)
        audio_np = np.array(sound.set_frame_rate(16000).set_channels(1).get_array_of_samples())
        audio_np = audio_np.astype(np.float32) / np.iinfo(np.int16).max
            
        # 3. Transcribe with forced language (no autodetect)
        result = _whisper_model.transcribe(audio_np, language=language)
        lang = language
        
        # 4. Load Alignment Model (cached per language)
        if lang not in _align_models:
            _align_models[lang] = whisperx.load_align_model(language_code=lang, device="cpu")
        model_a, metadata = _align_models[lang]
        
        # 5. Force Align for precise word-level timestamps
        aligned_result = whisperx.align(
            result["segments"], model_a, metadata, audio_np, "cpu", return_char_alignments=False
        )
        
        # Flatten all words with valid timestamps
        words = [
            w for seg in aligned_result["segments"] 
            for w in seg.get("words", []) 
            if "start" in w and "end" in w
        ]
        return words

    def _extract_audio(
        self, 
        sound: AudioSegment, 
        text: str, 
        aligned_words: List[dict],
        midpoint_cuts: bool
    ) -> AudioSegment:
        def clean_text(t: str) -> str:
            t = t.lower().translate(str.maketrans('', '', string.punctuation)).replace(" ", "")
            return unicodedata.normalize('NFKD', t).encode('ASCII', 'ignore').decode('utf-8')
            
        target = clean_text(text)
        
        # Find the best matching word indices (store for midpoint calculation)
        best_indices = None
        
        # 1. Try to find exact match
        for i in range(len(aligned_words)):
            for j in range(i, len(aligned_words)):
                chunk = "".join(clean_text(w["word"]) for w in aligned_words[i:j+1])

                # If the spoken chunk matches the target text exactly
                if target == chunk:
                    best_indices = (i, j)
                    # print(f"DEBUG EXACT MATCH: text='{text}' target='{target}'")
                    # print(f"  indices=({i}, {j})")
                    # print(f"  words={[w['word'] for w in aligned_words[i:j+1]]}")
                    # print(f"  times=({aligned_words[i]['start']:.3f}-{aligned_words[j]['end']:.3f})")
                    # if j < len(aligned_words) - 1:
                        # print(f"  NEXT word: '{aligned_words[j+1]['word']}' starts at {aligned_words[j+1]['start']:.3f}")
                    break
            if best_indices:
                break
                
        # 2. Try to find substring match if exact fails
        # Only use this when target is a proper substring (not just contained with extra chars)
        if best_indices is None:
            best_len_diff = float('inf')
            for i in range(len(aligned_words)):
                for j in range(i, len(aligned_words)):
                    chunk = "".join(clean_text(w["word"]) for w in aligned_words[i:j+1])

                    if target in chunk:
                        len_diff = len(chunk) - len(target)
                        # Prefer matches where we're not adding too many extra characters
                        if len_diff < best_len_diff and len_diff < 5:
                            best_len_diff = len_diff
                            best_indices = (i, j)
                if best_indices and best_len_diff == 0:
                    break

        # 3. Try difflib sequence matcher for fuzzy matching
        if best_indices is None:
            best_ratio = 0
            best_match = None
            for i in range(len(aligned_words)):
                for j in range(i, min(i + len(text.split()) + 5, len(aligned_words))):
                    chunk = "".join(clean_text(w["word"]) for w in aligned_words[i:j+1])
                    ratio = difflib.SequenceMatcher(None, target, chunk).ratio()
                    if ratio > best_ratio and len(chunk) >= len(target) * 0.9:
                        best_ratio = ratio
                        best_match = (i, j)

            if best_ratio > 0.85 and best_match:
                best_indices = best_match
                print(f"⚠️ Warning: Used fuzzy match (ratio {best_ratio:.2f}) for: '{text}'")
            else:
                raise AlignmentError(f"Could not find exact or fuzzy alignment for: '{text}'")

        i, j = best_indices
        
        # Calculate cut positions
        if midpoint_cuts and len(aligned_words) > 0:
            # Start: midpoint between previous word's end and first selected word's start
            if i > 0:
                prev_end = aligned_words[i - 1]["end"]
                curr_start = aligned_words[i]["start"]
                start_ms = int(((prev_end + curr_start) / 2) * 1000)
            else:
                start_ms = int(aligned_words[i]["start"] * 1000)
            
            # End: midpoint between last selected word's end and next word's start
            if j < len(aligned_words) - 1:
                curr_end = aligned_words[j]["end"]
                next_start = aligned_words[j + 1]["start"]
                end_ms = int(((curr_end + next_start) / 2) * 1000)
            else:
                end_ms = int(aligned_words[j]["end"] * 1000)
        else:
            # Direct cuts at word boundaries
            start_ms = int(aligned_words[i]["start"] * 1000)
            end_ms = int(aligned_words[j]["end"] * 1000)

        segment = sound[start_ms:end_ms]
        return segment.fade_out(self.config.chunk_fade_out_ms)


def check_and_fix_word_spacing(
    audio_path: str,
    min_gap_ms: int = 80,
    language: str = "hu",
    slowdown_factor: float = 1.1,
    max_slowdowns: int = 3,
) -> str:
    """
    Check if aligned words in audio have sufficient gaps between them.
    If gaps are too small, slows down the audio until spacing is adequate.

    Args:
        audio_path: Path to the audio file
        min_gap_ms: Minimum acceptable gap between consecutive words in milliseconds
        language: Language code for whisper alignment
        slowdown_factor: How much to slow down the audio on each iteration (e.g., 1.1 = 10% slower)
        max_slowdowns: Maximum number of slowdown iterations before giving up

    Returns:
        Path to the (possibly modified) audio file
    """
    sound = AudioSegment.from_file(audio_path)
    global _whisper_model, _align_models, model_storage, model_name

    # Load whisper model if needed
    if _whisper_model is None:
        os.makedirs(model_storage, exist_ok=True)
        _whisper_model = whisperx.load_model(
            model_name,
            device="cpu",
            compute_type="int8",
            download_root=model_storage,
        )

    for attempt in range(max_slowdowns + 1):
        if attempt > 0:
            sound = sound.speedup(playback_speed=1.0 / slowdown_factor)

        # Convert to numpy
        audio_np = np.array(sound.set_frame_rate(16000).set_channels(1).get_array_of_samples())
        audio_np = audio_np.astype(np.float32) / np.iinfo(np.int16).max

        # Transcribe
        result = _whisper_model.transcribe(audio_np, language=language)

        # Align
        if language not in _align_models:
            _align_models[language] = whisperx.load_align_model(language_code=language, device="cpu")
        model_a, metadata = _align_models[language]

        aligned_result = whisperx.align(
            result["segments"], model_a, metadata, audio_np, "cpu", return_char_alignments=False
        )

        words = [
            w for seg in aligned_result["segments"]
            for w in seg.get("words", [])
            if "start" in w and "end" in w
        ]

        if len(words) < 2:
            break

        # Check gaps
        min_found_gap = float("inf")
        for k in range(len(words) - 1):
            gap_ms = int((words[k + 1]["start"] - words[k]["end"]) * 1000)
            min_found_gap = min(min_found_gap, gap_ms)

        if min_found_gap >= min_gap_ms:
            if attempt == 0:
                print(f"  Word spacing OK (min gap: {min_found_gap}ms)")
            else:
                print(f"  Word spacing fixed after {attempt} slowdown(s) (min gap: {min_found_gap}ms)")
                out_path = audio_path
                Path(out_path).parent.mkdir(parents=True, exist_ok=True)
                sound.export(out_path, format="mp3", bitrate="320k")
            return audio_path

        print(f"  Attempt {attempt + 1}: min gap {min_found_gap}ms < {min_gap_ms}ms threshold, slowing down...")

    print(f"  WARNING: Could not achieve {min_gap_ms}ms gaps after {max_slowdowns} slowdowns")
    return audio_path

