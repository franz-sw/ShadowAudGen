import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from config import OUTPUT_DIR, QUESTION_VOICE_ID, ELEVENLABS_VOICE_ID, DEFAULT_JSON, DEFAULT_LANGUAGE, AUDIO_FILE_PREFIX
from llm_util import translate_to_german
from db import ShadowingDB
from pydub import AudioSegment
from fpdf import FPDF


class Exporter:
    def __init__(self):
        self.db = ShadowingDB()
        self.output_dir = Path(OUTPUT_DIR)
        self.episode_counter_file = Path(__file__).parent / "res" / "episode_counter.txt"

    def _get_next_episode_number(self) -> int:
        counter_file = self.episode_counter_file
        if counter_file.exists():
            current = int(counter_file.read_text().strip())
        else:
            current = 0
        next_num = current + 1
        counter_file.write_text(str(next_num))
        return next_num

    def _get_topic_slug(self, topic: str) -> str:
        return re.sub(r'[^a-zA-Z0-9]+', '_', topic.lower().strip())

    def _format_srt_time(self, ms: int) -> str:
        seconds, milliseconds = divmod(int(ms), 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def _combine_shadowing_audios(self, topic: str, entries: List[Dict]) -> Tuple[Optional[str], Optional[int]]:
        topic_slug = self._get_topic_slug(topic)
        topic_dir = self.output_dir / topic_slug
        shadow_audio_dir = topic_dir / "shadowing"
        audio_dir = topic_dir / "audio"
        res_dir = Path(__file__).parent / "res"
        outro_path = res_dir / "outro.mp3"

        if not shadow_audio_dir.exists():
            return None, None

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
                    return None, None
                if shadow_path.exists():
                    shadow_files.append((entry_id, shadow_path))
                else:
                    print(f"  Warning: Shadow audio for entry {entry_id} is missing. Skipping combined export for topic '{topic}'.")
                    return None, None
                if plain_path.exists():
                    plain_files.append((entry_id, plain_path))
                else:
                    print(f"  Warning: Initial answer audio for entry {entry_id} is missing. Skipping combined export for topic '{topic}'.")
                    return None, None

        entry_map = {e.get("id"): e for e in entries if e.get("id")}

        if not shadow_files:
            return None, None

        question_files.sort(key=lambda x: x[0])
        shadow_files.sort(key=lambda x: x[0])
        plain_files.sort(key=lambda x: x[0])

        episode_num = self._get_next_episode_number()
        base_name = f"{episode_num} - {AUDIO_FILE_PREFIX} - {topic}"
        plain_base_name = f"{episode_num} - {AUDIO_FILE_PREFIX}[PLAIN] - {topic}"
        export_dir = topic_dir / "export"
        export_dir.mkdir(parents=True, exist_ok=True)

        cover_path = (res_dir / "cover.jpeg")

        combined_shadowing = AudioSegment.empty()
        shadow_chapters = []
        shadow_srt = []
        current_time_shadow = 0
        srt_idx_shadow = 1

        for (eid, qf), (_, sf) in zip(question_files, shadow_files):
            q_audio = AudioSegment.from_mp3(str(qf))
            s_audio = AudioSegment.from_mp3(str(sf))
            q_dur = len(q_audio)
            s_dur = len(s_audio)
            
            entry = entry_map.get(eid, {})
            q_text = entry.get("question", "")
            a_text = entry.get("answer", "")
            
            shadow_chapters.append({
                "startTime": current_time_shadow / 1000.0,
                "title": q_text
            })
            
            q_start = current_time_shadow
            q_end = current_time_shadow + q_dur
            shadow_srt.append(f"{srt_idx_shadow}\n{self._format_srt_time(q_start)} --> {self._format_srt_time(q_end)}\n{q_text}\n")
            srt_idx_shadow += 1
            
            s_start = q_end
            s_end = q_end + s_dur
            shadow_srt.append(f"{srt_idx_shadow}\n{self._format_srt_time(s_start)} --> {self._format_srt_time(s_end)}\n{a_text}\n")
            srt_idx_shadow += 1
            
            combined_shadowing += q_audio
            combined_shadowing += s_audio
            current_time_shadow += q_dur + s_dur

        combined_shadowing = combined_shadowing.normalize(headroom=0.1)

        outro = AudioSegment.from_mp3(str(outro_path)) if outro_path.exists() else AudioSegment.silent(duration=1000)
        break_sil = AudioSegment.silent(duration=1000)
        combined_shadowing += break_sil + outro

        shadowing_path = export_dir / f"{base_name}.mp3"
        export_kwargs_shadowing = {
            "format": "mp3",
            "tags": {"artist": "Árnyékmester", "title": base_name}
        }
        if cover_path:
            export_kwargs_shadowing["cover"] = str(cover_path)
            
        combined_shadowing.export(str(shadowing_path), **export_kwargs_shadowing)
        print(f"  Combined {len(shadow_files)} question+shadowing audio pairs into {shadowing_path.name}")
        
        # Save shadow JSON chapters
        shadow_json_path = export_dir / f"{base_name}.json"
        with open(shadow_json_path, "w", encoding="utf-8") as f:
            json.dump({"version": "1.2.0", "chapters": shadow_chapters}, f, indent=2, ensure_ascii=False)
            
        # Save shadow SRT
        shadow_srt_path = export_dir / f"{base_name}.srt"
        with open(shadow_srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(shadow_srt))

        combined_plain = AudioSegment.empty()
        plain_chapters = []
        plain_srt = []
        current_time_plain = 0
        srt_idx_plain = 1

        for (eid, qf), (_, pf) in zip(question_files, plain_files):
            q_audio = AudioSegment.from_mp3(str(qf))
            p_audio = AudioSegment.from_mp3(str(pf))
            q_dur = len(q_audio)
            p_dur = len(p_audio)
            
            entry = entry_map.get(eid, {})
            q_text = entry.get("question", "")
            a_text = entry.get("answer", "")
            
            plain_chapters.append({
                "startTime": current_time_plain / 1000.0,
                "title": q_text
            })
            
            q_start = current_time_plain
            q_end = current_time_plain + q_dur
            plain_srt.append(f"{srt_idx_plain}\n{self._format_srt_time(q_start)} --> {self._format_srt_time(q_end)}\n{q_text}\n")
            srt_idx_plain += 1
            
            p_start = q_end
            p_end = q_end + p_dur
            plain_srt.append(f"{srt_idx_plain}\n{self._format_srt_time(p_start)} --> {self._format_srt_time(p_end)}\n{a_text}\n")
            srt_idx_plain += 1
            
            combined_plain += q_audio
            combined_plain += p_audio
            current_time_plain += q_dur + p_dur

        combined_plain = combined_plain.normalize(headroom=0.1)

        combined_plain += break_sil + outro

        plain_path = export_dir / f"{plain_base_name}.mp3"
        export_kwargs_plain = {
            "format": "mp3",
            "tags": {"artist": "Árnyékmester", "title": plain_base_name}
        }
        if cover_path:
            export_kwargs_plain["cover"] = str(cover_path)
            
        combined_plain.export(str(plain_path), **export_kwargs_plain)
        print(f"  Combined {len(plain_files)} question+answer audio pairs into {plain_path.name}")
        
        # Save plain JSON chapters
        plain_json_path = export_dir / f"{plain_base_name}.json"
        with open(plain_json_path, "w", encoding="utf-8") as f:
            json.dump({"version": "1.2.0", "chapters": plain_chapters}, f, indent=2, ensure_ascii=False)
            
        # Save plain SRT
        plain_srt_path = export_dir / f"{plain_base_name}.srt"
        with open(plain_srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(plain_srt))

        return str(shadowing_path), episode_num

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        if not text:
            return []
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s.strip() for s in sentences if s.strip()]

    def _export_topic_to_pdf(self, topic: str, topic_entries: List[Dict], combined_audio_path: Optional[str] = None, include_translations: bool = False, episode_num: int = None) -> str:
        topic_slug = self._get_topic_slug(topic)
        topic_dir = self.output_dir / topic_slug
        export_subdir = topic_dir / "export"
        export_subdir.mkdir(parents=True, exist_ok=True)
        if episode_num:
            pdf_path = export_subdir / f"{episode_num} - {topic_slug}.pdf"
        else:
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

            combined_audio_path, episode_num = self._combine_shadowing_audios(topic, topic_entries)

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

            pdf_path = self._export_topic_to_pdf(topic, topic_entries, combined_audio_path, include_translations, episode_num)
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
            export_dir = topic_dir / "export"
            
            if export_dir.exists():
                all_mp3s = list(export_dir.glob("*.mp3"))
                shadowing_files = [f for f in all_mp3s if " [MK1]" in f.name and "[PLAIN]" not in f.name]
                plain_files = [f for f in all_mp3s if "[PLAIN]" in f.name]

                shadowing_files.sort()
                plain_files.sort()

                if shadowing_files:
                    audio_files[topic] = str(shadowing_files[-1])
                if plain_files:
                    audio_files[f"{topic}_plain"] = str(plain_files[-1])

        return audio_files


def export_all():
    exporter = Exporter()
    return exporter.export_to_markdown()