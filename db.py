import json
from pathlib import Path
from typing import List, Dict, Optional

from config import DB_PATH, OUTPUT_DIR


class ShadowingDB:
    """Loads entries from JSON. Uses file-based audio existence checking (no DB required)."""

    def __init__(self):
        self.entries_cache: List[Dict] = []
        self.output_dir = Path(OUTPUT_DIR)
        print("ShadowingDB initialized (file-based mode, no DB required).")

    def load_from_json(self, json_path: str) -> List[Dict]:
        """Load and deserialize from JSON with same schema."""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        source_file = Path(json_path).name
        topic = data.get("topic", Path(json_path).stem.replace("_", " ").title())

        self.topic_metadata = {
            "source_file": source_file,
            "topic": topic,
            "vocabulary": data.get("vocabulary", []),
            "format": data.get("format"),
            "tone": data.get("tone")
        }

        self.entries_cache = []
        for idx, item in enumerate(data.get("shadowing_source", []), start=1):
            self.entries_cache.append({
                "id": idx,
                "source_file": source_file,
                "topic": topic,
                "question": item["question"],
                "answer": item["answer"],
                "answer_metadata": item.get("answer_metadata", ""),
                "vocabulary": data.get("vocabulary", []),
                "format": data.get("format"),
                "tone": data.get("tone")
            })
        print(f"Loaded {len(self.entries_cache)} entries from {source_file}")
        return self.entries_cache

    def get_entries_by_source_file(self, source_file: str) -> List[Dict]:
        """Get entries filtered by source_file with file-based audio paths."""
        entries = [e for e in self.entries_cache if e["source_file"] == source_file]
        return self._add_audio_paths(entries)

    def get_all_entries(self) -> List[Dict]:
        """Get all entries with file-based audio paths."""
        return self._add_audio_paths(self.entries_cache)

    def _add_audio_paths(self, entries: List[Dict]) -> List[Dict]:
        """Add audio paths by checking filesystem."""
        for entry in entries:
            entry_id = entry["id"]
            topic = entry["topic"]
            topic_slug = self._get_topic_slug(topic)
            topic_dir = self.output_dir / topic_slug

            q_path = topic_dir / "audio" / f"q_{entry_id:03d}.mp3"
            a_init_path = topic_dir / "audio" / f"a_init_{entry_id:03d}.mp3"
            shadow_path = topic_dir / "shadowing" / f"shadow_{entry_id:03d}.mp3"

            entry["question_audio"] = str(q_path) if q_path.exists() else None
            entry["initial_answer_audio"] = str(a_init_path) if a_init_path.exists() else None
            entry["shadowing_audio"] = str(shadow_path) if shadow_path.exists() else None
        return entries

    def _get_topic_slug(self, topic: str) -> str:
        import re
        return re.sub(r'[^a-zA-Z0-9]+', '_', topic.lower().strip())

    def update_audio_paths(self, entry_id: int, question_audio: Optional[str] = None,
                          initial_answer_audio: Optional[str] = None,
                          shadowing_audio: Optional[str] = None):
        """Update is no-op in file-based mode (filesystem is source of truth)."""
        pass

    def insert_or_update_entries(self, entries: List[Dict]) -> int:
        """No-op in file-based mode."""
        return len(entries)