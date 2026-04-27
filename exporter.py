import json
import re
from pathlib import Path
from typing import List, Dict, Optional

from config import OUTPUT_DIR, QUESTION_VOICE_ID, ELEVENLABS_VOICE_ID, DEFAULT_JSON, DEFAULT_LANGUAGE, AUDIO_FILE_PREFIX
from llm_util import translate_to_german
from db import ShadowingDB
from pydub import AudioSegment
from fpdf import FPDF


class Exporter:
    def __init__(self):
        self.db = ShadowingDB()
        self.output_dir = Path(OUTPUT_DIR)

    def _get_topic_slug(self, topic: str) -> str:
        return re.sub(r'[^a-zA-Z0-9]+', '_', topic.lower().strip())

    def _combine_shadowing_audios(self, topic: str, entries: List[Dict]) -> Optional[str]:
        topic_slug = self._get_topic_slug(topic)
        topic_dir = self.output_dir / topic_slug
        shadow_audio_dir = topic_dir / "shadowing"
        audio_dir = topic_dir / "audio"
        res_dir = Path(__file__).parent / "res"
        outro_path = res_dir / "outro.mp3"

        if not shadow_audio_dir.exists():
            return None

        shadow_files = []
        question_files = []
        plain_files = []
        for entry in entries:
            entry_id = entry.get("id")
            if entry_id:
                question_path = audio_dir / f"q_{entry_id:03d}.mp3"
                shadow_path = shadow_audio_dir / f"shadow_{entry_id:03d}.mp3"
                plain_path = audio_dir / f"a_init_{entry_id:03d}.mp3"
                if question_path.exists():
                    question_files.append((entry_id, question_path))
                else:
                    print(f"  Warning: Question audio for entry {entry_id} is missing. Skipping combined export for topic '{topic}'.")
                    return None
                if shadow_path.exists():
                    shadow_files.append((entry_id, shadow_path))
                else:
                    print(f"  Warning: Shadow audio for entry {entry_id} is missing. Skipping combined export for topic '{topic}'.")
                    return None
                if plain_path.exists():
                    plain_files.append((entry_id, plain_path))
                else:
                    print(f"  Warning: Initial answer audio for entry {entry_id} is missing. Skipping combined export for topic '{topic}'.")
                    return None

        if not shadow_files:
            return None

        question_files.sort(key=lambda x: x[0])
        shadow_files.sort(key=lambda x: x[0])
        plain_files.sort(key=lambda x: x[0])

        base_name = f"{AUDIO_FILE_PREFIX} - {topic}"
        export_dir = topic_dir / "export"
        export_dir.mkdir(parents=True, exist_ok=True)

        combined_shadowing = AudioSegment.empty()
        for (_, qf), (_, sf) in zip(question_files, shadow_files):
            combined_shadowing += AudioSegment.from_mp3(str(qf))
            combined_shadowing += AudioSegment.from_mp3(str(sf))

        combined_shadowing = combined_shadowing.normalize(headroom=0.1)

        outro = AudioSegment.from_mp3(str(outro_path)) if outro_path.exists() else AudioSegment.silent(duration=1000)
        break_sil = AudioSegment.silent(duration=1000)
        combined_shadowing += break_sil + outro

        shadowing_path = export_dir / f"{base_name}.mp3"
        combined_shadowing.export(str(shadowing_path), format="mp3")
        print(f"  Combined {len(shadow_files)} question+shadowing audio pairs into {shadowing_path.name}")

        combined_plain = AudioSegment.empty()
        for (_, qf), (_, pf) in zip(question_files, plain_files):
            combined_plain += AudioSegment.from_mp3(str(qf))
            combined_plain += AudioSegment.from_mp3(str(pf))

        combined_plain = combined_plain.normalize(headroom=0.1)

        combined_plain += break_sil + outro

        plain_path = export_dir / f"{base_name}[PLAIN].mp3"
        combined_plain.export(str(plain_path), format="mp3")
        print(f"  Combined {len(plain_files)} question+answer audio pairs into {plain_path.name}")

        return str(shadowing_path)

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        if not text:
            return []
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s.strip() for s in sentences if s.strip()]

    def _export_topic_to_pdf(self, topic: str, topic_entries: List[Dict], combined_audio_path: Optional[str] = None, include_translations: bool = False) -> str:
        topic_slug = self._get_topic_slug(topic)
        topic_dir = self.output_dir / topic_slug
        export_subdir = topic_dir / "export"
        export_subdir.mkdir(parents=True, exist_ok=True)
        pdf_path = export_subdir / f"{topic_slug}.pdf"

        class TopicPDF(FPDF):
            def footer(self):
                self.set_y(-15)
                self.set_font("Segoe UI", "I", 8)
                self.cell(0, 10, f"Page {self.page_no()}", align="C")

        pdf = TopicPDF()
        pdf.set_margins(15, 15, 15)
        pdf.add_font("Segoe UI", "", r"C:\Windows\Fonts\segoeui.ttf", uni=True)
        pdf.add_font("Segoe UI", "B", r"C:\Windows\Fonts\segoeuib.ttf", uni=True)
        pdf.add_font("Segoe UI", "I", r"C:\Windows\Fonts\segoeuii.ttf", uni=True)
        pdf.add_page()
        pdf.set_font("Segoe UI", "B", 16)
        pdf.cell(0, 10, topic, ln=True, align="C")
        pdf.ln(5)
        pdf.set_font("Segoe UI", size=11)

        metadata = topic_entries[0]
        vocabulary = metadata.get("vocabulary", [])
        tone = metadata.get("tone", "")
        fmt = metadata.get("format", "")
        vocab_str = metadata.get("vocabulary", "")

        if isinstance(vocabulary, str):
            try:
                vocabulary = json.loads(vocabulary)
            except:
                vocabulary = []

        unused = metadata.get("unused_input_words", [])
        vocabulary = [w for w in vocabulary if w not in unused] if isinstance(vocabulary, list) else vocabulary

        pdf.set_font("Segoe UI", "", 12)
        pdf.cell(0, 8, f"Format: {fmt}")
        pdf.ln()
        pdf.cell(0, 8, f"Tone: {tone}")
        pdf.ln()
        pdf.multi_cell(0, 8, f"Vocabulary: {vocabulary}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(10)

        for entry in topic_entries:
            q_text = entry.get('question', '')
            a_text = entry.get('answer', '')
            cell_width = pdf.w - 30
            
            q_lines = (pdf.get_string_width(q_text) // cell_width) + 1
            a_lines = (pdf.get_string_width(a_text) // cell_width) + 1
            required_height = (q_lines + a_lines) * 8 + 10
            if pdf.get_y() + required_height > pdf.h - 15:
                pdf.add_page()
            
            pdf.set_x(15)
            pdf.set_font("Segoe UI", "B", 12)
            pdf.multi_cell(0, 8, q_text, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Segoe UI", "", 12)
            pdf.multi_cell(0, 8, a_text, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(5)

        pdf.add_page()
        if include_translations:
            pdf.set_font("Segoe UI", "B", 16)
            pdf.cell(0, 10, f"{topic} - German Translation", ln=True, align="C")
            pdf.ln(5)

            for entry in topic_entries:
                q_text = entry.get('question', '')
                a_text = entry.get('answer', '')

                q_sentences = self._split_sentences(q_text)
                a_sentences = self._split_sentences(a_text)

                all_sentences = q_sentences + a_sentences
                if all_sentences:
                    german_translations = translate_to_german(all_sentences)
                else:
                    german_translations = []

                cell_width = pdf.w - 30
                
                if pdf.get_y() > pdf.h - 40:
                    pdf.add_page()

                pdf.set_x(15)
                pdf.set_font("Segoe UI", "B", 12)
                pdf.multi_cell(0, 8, q_text, new_x="LMARGIN", new_y="NEXT")
                
                pdf.set_font("Segoe UI", "I", 11)
                for i, sent in enumerate(q_sentences):
                    if i < len(german_translations):
                        pdf.multi_cell(0, 7, german_translations[i], new_x="LMARGIN", new_y="NEXT")
                pdf.ln(3)

                pdf.set_font("Segoe UI", "", 12)
                pdf.multi_cell(0, 8, a_text, new_x="LMARGIN", new_y="NEXT")

                pdf.set_font("Segoe UI", "I", 11)
                q_count = len(q_sentences)
                for i, sent in enumerate(a_sentences):
                    idx = q_count + i
                    if idx < len(german_translations):
                        pdf.multi_cell(0, 7, german_translations[idx], new_x="LMARGIN", new_y="NEXT")
                pdf.ln(10)

        pdf.output(str(pdf_path))
        print(f"Exported PDF to {pdf_path}")
        return str(pdf_path)

    def export_to_markdown(self, default_json: str = None, output_name: str = None, include_translations: bool = False) -> List[str]:
        if default_json:
            self.db.load_from_json(default_json)
        
        entries = self.db.get_all_entries()
        if not entries:
            print("No entries loaded to export.")
            return []

        grouped = {}
        for entry in entries:
            topic = entry["topic"]
            if topic not in grouped:
                grouped[topic] = []
            grouped[topic].append(entry)

        output_files = []

        for topic, topic_entries in grouped.items():
            topic_slug = self._get_topic_slug(topic)
            topic_dir = self.output_dir / topic_slug
            export_subdir = topic_dir / "export"
            export_subdir.mkdir(parents=True, exist_ok=True)
            out_path = export_subdir / f"{topic_slug}.md"

            combined_audio_path = self._combine_shadowing_audios(topic, topic_entries)

            metadata = topic_entries[0]
            vocabulary = metadata.get("vocabulary", [])
            if isinstance(vocabulary, str):
                try:
                    vocabulary = json.loads(vocabulary)
                except:
                    vocabulary = []
            unused = metadata.get("unused_input_words", [])

            tone = metadata.get("tone", "")
            fmt = metadata.get("format", "")
            vocabulary = [w for w in vocabulary if w not in unused] if isinstance(vocabulary, list) else vocabulary
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(f"# {topic}\n\n")
                f.write(f"**Format:** {fmt}  \n")
                f.write(f"**Tone:** {tone}  \n")
                f.write(f"**Vocabulary:** {', '.join(vocabulary) if vocabulary else 'N/A'}  \n")
                if combined_audio_path:
                    f.write(f"**Audio:** {Path(combined_audio_path).name}  \n")
                f.write("\n---\n\n")

                for entry in topic_entries:
                    f.write(f"**Q:** {entry['question']}\n\n")
                    f.write(f"**A:** {entry['answer']}\n\n")
                    f.write("---\n\n")

            print(f"Exported {len(topic_entries)} entries to {out_path}")
            output_files.append(str(out_path))

            pdf_path = self._export_topic_to_pdf(topic, topic_entries, combined_audio_path, include_translations)
            output_files.append(pdf_path)

        return output_files

    def get_exported_audio_files(self, default_json: str = None) -> Dict[str, str]:
        if default_json:
            self.db.load_from_json(default_json)
        
        entries = self.db.get_all_entries()
        if not entries:
            return {}

        grouped = {}
        for entry in entries:
            topic = entry["topic"]
            if topic not in grouped:
                grouped[topic] = []
            grouped[topic].append(entry)

        audio_files = {}
        for topic, topic_entries in grouped.items():
            topic_slug = self._get_topic_slug(topic)
            topic_dir = self.output_dir / topic_slug
            base_name = f"{AUDIO_FILE_PREFIX} - {topic}"
            combined_audio_path = topic_dir / "export" / f"{base_name}.mp3"
            plain_audio_path = topic_dir / "export" / f"{base_name}[PLAIN].mp3"
            
            if combined_audio_path.exists():
                audio_files[topic] = str(combined_audio_path)
            if plain_audio_path.exists():
                audio_files[f"{topic}_plain"] = str(plain_audio_path)

        return audio_files


def export_all():
    exporter = Exporter()
    return exporter.export_to_markdown()