from pathlib import Path
from typing import Optional
import shutil
import re

from config import OUTPUT_DIR, QUESTION_VOICE_ID, ELEVENLABS_VOICE_ID, DEFAULT_JSON, DEFAULT_LANGUAGE
from utils import call_tts_api, call_local_tts, get_slug
from shadower_util import ShadowingPreparer, ShadowingConfig
from db import ShadowingDB


class AudioGenerator:
    """Handles generation of initial and shadowing audios. Uses file-based audio existence checking."""

    def __init__(self):
        self.db = ShadowingDB()
        self.output_dir = Path(OUTPUT_DIR)
        print("AudioGenerator initialized.")

    def _get_topic_dir(self, topic: str) -> Path:
        """Create clean topic-based subdirectory for organized storage."""
        slug = get_slug(topic)
        topic_dir = self.output_dir / slug
        topic_dir.mkdir(parents=True, exist_ok=True)
        (topic_dir / "audio").mkdir(exist_ok=True)
        (topic_dir / "shadowing").mkdir(exist_ok=True)
        return topic_dir

    def generate_initial_audios(self, entry: dict, entry_id: int, overwrite: bool = False) -> bool:
        """Generate question and initial answer audio in topic-specific folder."""
        topic_dir = self._get_topic_dir(entry["topic"])
        audio_subdir = topic_dir / "audio"
        q_path = audio_subdir / f"q_{entry_id:03d}.mp3"
        a_path = audio_subdir / f"a_init_{entry_id:03d}.mp3"

        success = True

        if not q_path.exists() or overwrite:
            print(f"Generating QUESTION audio for entry {entry_id}: '{entry['question'][:50]}...'")
            if not call_local_tts(
                text=entry["question"],
                output_path=str(q_path),
                overwrite=overwrite
            ):
                success = False
        else:
            print(f"  Question audio exists: {q_path}")

        if not a_path.exists() or overwrite:
            print(f"Generating INITIAL ANSWER audio for entry {entry_id}: '{entry['answer'][:50]}...'")
            if not call_tts_api(
                text=entry["answer"],
                output_path=str(a_path),
                voice_id=ELEVENLABS_VOICE_ID,
                speed=0.94,
                overwrite=overwrite,
                stability=0.6,
                similarity_boost=0.80
            ):
                success = False
        else:
            print(f"  Initial answer audio exists: {a_path}")


        return success

    def generate_shadowing_audio(self, entry: dict, entry_id: int, overwrite: bool = False, language: str = DEFAULT_LANGUAGE) -> Optional[str]:
        """Create customized shadowing audio in topic-specific folder."""
        topic_dir = self._get_topic_dir(entry["topic"])
        audio_subdir = topic_dir / "audio"
        init_a_path = audio_subdir / f"a_init_{entry_id:03d}.mp3"

        if not init_a_path.exists():
            print(f"  No initial answer audio found for entry {entry_id}")
            return None

        shadow_path = topic_dir / "shadowing" / f"shadow_{entry_id:03d}.mp3"

        if shadow_path.exists() and not overwrite:
            print(f"  Shadowing audio exists: {shadow_path}")
            return str(shadow_path)

        print(f"Generating CUSTOM SHADOWING audio for entry {entry_id} using metadata...")
        try:
            self.shadow_preparer = ShadowingPreparer(
                config=ShadowingConfig(output_dir=str(topic_dir / "shadowing"))
            )
            output_path = self.shadow_preparer.create_shadowing_track(
                audio_path=str(init_a_path),
                script=entry.get("answer_metadata", entry.get("answer", "")),
                output_filename=f"shadow_{entry_id:03d}.mp3",
                language=language
            )
            return output_path
        except Exception as e:
            print(f"  ❌ Shadowing generation failed for entry {entry_id}: {e}")
            return None

    def run_full_generation(self, json_path: str = None, overwrite: bool = False, language: str = DEFAULT_LANGUAGE, export_all: bool = False) -> None:
        """Orchestrate the full workflow: load JSON -> generate audios."""
        if json_path is None:
            json_path = DEFAULT_JSON
        
        source_file = Path(json_path).name
        
        print("=== Starting Shadowing Audio Generation Workflow ===")
        self.db.load_from_json(json_path)

        if export_all:
            db_entries = self.db.get_all_entries()
        else:
            db_entries = self.db.get_entries_by_source_file(source_file)
        
        if not db_entries:
            print(f"No entries found for source file: {source_file}")
            return
        
        for entry in db_entries:
            print(f"\nProcessing entry {entry['id']}: {entry['question'][:60]}...")
            self.generate_initial_audios(entry, entry["id"], overwrite=overwrite)
            self.generate_shadowing_audio(entry, entry["id"], overwrite=overwrite, language=language)

        print("\n=== Workflow completed. All audios generated. ===")
