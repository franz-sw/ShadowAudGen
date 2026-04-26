from pathlib import Path
import asyncio
from pathlib import Path
from typing import Optional
import edge_tts
import requests

from config import (
    ELEVENLABS_API_KEY,
    ELEVENLABS_VOICE_ID,
    ELEVENLABS_MODEL_ID,
    QUESTION_VOICE_ID,
    DEFAULT_LANGUAGE,
)

LANG_TO_EDGE_VOICE = {
    'hu': 'hu-HU-NoemiNeural',
    'de': 'de-DE-KatjaNeural',
    'en': 'en-US-AriaNeural',
    'fr': 'fr-FR-RemyNeural',
    'es': 'es-ES-ElenaNeural',
    'it': 'it-IT-ElsaNeural',
    'pt': 'pt-BR-LeilaNeural',
    'nl': 'nl-NL-ColetteNeural',
    'pl': 'pl-PL-NatalieNeural',
    'ru': 'ru-RU-SvetlanaNeural',
    'ja': 'ja-JP-NanamiNeural',
    'ko': 'ko-KR-SunhiNeural',
    'zh': 'zh-CN-XiaoxiaoNeural',
}

async def _generate_edge_tts(text: str, output_path: str, voice: str) -> bool:
    try:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        communicate = edge_tts.Communicate(text, voice, pitch = "-10Hz")
        await communicate.save(output_path)
        return True
    except Exception as e:
        print(f"  edge-tts failed: {e}")
        return False


def call_tts_api(
        text: str,
        output_path: str,
        voice_id: str | None = None,
        speed: float = 1.0,
        overwrite: bool = False,
        previous_text: str = "",
        stability: float = 0.5,
        similarity_boost: float = 0.75,
) -> bool:
    """Call ElevenLabs TTS API with flexible voice and speed. Speed is always 1.0 for sentences per spec."""
    if not ELEVENLABS_API_KEY:
        print(f"  Error: No ELEVENLABS_API_KEY for TTS of '{text[:30]}...'")
        return False

    path = Path(output_path)
    if path.exists() and not overwrite:
        print(f"  Skipping existing audio for '{text[:30]}...'")
        return True

    if voice_id is None:
        voice_id = ELEVENLABS_VOICE_ID

    model_id = ELEVENLABS_MODEL_ID

    try:
        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": text,
                "model_id": model_id,
                "language_code": DEFAULT_LANGUAGE,
                "voice_settings": {
                    "stability": stability,
                    "similarity_boost": similarity_boost,
                    "speed": speed,
                    "previous_text": previous_text,
                }
            },
            timeout=30,
        )
        response.raise_for_status()

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)

        print(f"  Generated {len(response.content):,} bytes TTS for '{text[:40]}...' (speed={speed})")
        return True

    except Exception as e:
        print(f"  ❌ TTS API failed: voice={voice_id}, text='{text[:10]}...': {str(e)}")
        return False


def call_local_tts(
        text: str,
        output_path: str,
        overwrite: bool = False
) -> bool:
    """Generate TTS using edge-tts only. Returns False if edge-tts fails."""
    path = Path(output_path)
    if path.exists() and not overwrite:
        print(f"  Skipping existing local audio for '{text[:30]}...'")
        return True

    target_lang = DEFAULT_LANGUAGE.lower()[:2]
    edge_voice = LANG_TO_EDGE_VOICE.get(target_lang)
    
    if not edge_voice:
        print(f"  ❌ No edge-tts voice found for language '{DEFAULT_LANGUAGE}'")
        return False
    
    result = asyncio.run(_generate_edge_tts(text, output_path, edge_voice))
    
    if result:
        print(f"  Generated edge-tts for '{text[:40]}...' lang={DEFAULT_LANGUAGE})")
        return True
    
    print(f"  ❌ edge-tts failed for '{text[:10]}...'")
    return False
