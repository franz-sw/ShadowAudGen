import os
import re
import paramiko
import requests
from pathlib import Path
from typing import Optional, Tuple, List
from contextlib import ExitStack

from config import CASTOPOD_HOST, CASTOPOD_PODCAST_ID, CASTOPOD_USER_ID, CASTOPOD_AUTH_USERNAME, CASTOPOD_AUTH_PASSWORD, SHADOWING_SOURCES_BASE_URL
from utils import get_slug
from pathlib import Path


class FTPClient:
    def __init__(self):
        self.server = os.getenv("FTP_SERVER")
        self.port = 23
        self.username = os.getenv("FTP_USERNAME")
        self.password = os.getenv("FTP_PASSWORD")
        self.remote_dir = os.getenv("FTP_REMOTE_DIRECTORY")
        self.base_url = SHADOWING_SOURCES_BASE_URL

    def _connect(self):
        transport = paramiko.Transport((self.server, self.port))
        transport.connect(username=self.username, password=self.password)
        return paramiko.SFTPClient.from_transport(transport)

    def upload_file(self, local_path: str, remote_filename: str = None) -> Optional[str]:
        if not all([self.server, self.username, self.password]):
            print("FTP configuration missing. Skipping upload.")
            return None

        if remote_filename is None:
            remote_filename = Path(local_path).name

        try:
            sftp = self._connect()
            if self.remote_dir:
                try:
                    sftp.mkdir(self.remote_dir)
                except IOError:
                    pass
                sftp.chdir(self.remote_dir)
            sftp.put(local_path, remote_filename)
            sftp.close()
            print(f"Uploaded {remote_filename} to FTP")
            return f"{self.base_url}/{remote_filename}"
        except Exception as e:
            print(f"FTP upload failed: {e}")
            return None


class CastopodPublisher:
    def __init__(self):
        self.host = CASTOPOD_HOST
        self.podcast_id = CASTOPOD_PODCAST_ID
        self.user_id = CASTOPOD_USER_ID
        self.username = CASTOPOD_AUTH_USERNAME
        self.password = CASTOPOD_AUTH_PASSWORD
        self.episode_counter_file = Path(__file__).parent / "res" / "episode_counter.txt"

        if not all([self.host, self.podcast_id, self.user_id, self.username, self.password]):
            raise ValueError("Missing required Castopod configuration. Check .env file.")

    def _get_next_episode_number(self) -> int:
        """Get and increment the episode counter. Only called on publish."""
        counter_file = self.episode_counter_file
        if counter_file.exists():
            current = int(counter_file.read_text().strip())
        else:
            current = 0
        next_num = current + 1
        counter_file.write_text(str(next_num))
        return next_num

    def _get_auth(self):
        return (self.username, self.password)

    def _find_export_files(self, topic: str) -> Optional[dict]:
        """Find all export files for a topic."""
        from config import OUTPUT_DIR
        topic_slug = get_slug(topic)
        topic_dir = Path(OUTPUT_DIR) / topic_slug
        export_dir = topic_dir / "export"

        if not export_dir.exists():
            return None

        files = {}
        for mp3 in export_dir.glob("*.mp3"):
            name = mp3.stem
            if "[PLAIN]" in name:
                files["plain_mp3"] = str(mp3)
                files["plain_base_name"] = name
                # Direct path construction for plain json/srt
                plain_json = export_dir / f"{name}.json"
                plain_srt = export_dir / f"{name}.srt"
                if plain_json.exists():
                    files["plain_json"] = str(plain_json)
                if plain_srt.exists():
                    files["plain_srt"] = str(plain_srt)
            else:
                files["shadowing_mp3"] = str(mp3)
                files["base_name"] = name
                # Direct path construction for shadowing json/srt
                shadow_json = export_dir / f"{name}.json"
                shadow_srt = export_dir / f"{name}.srt"
                if shadow_json.exists():
                    files["json"] = str(shadow_json)
                if shadow_srt.exists():
                    files["srt"] = str(shadow_srt)

        if not files:
            return None

        pdf_files = list(export_dir.glob("*.pdf"))
        if pdf_files:
            files["pdf"] = str(pdf_files[-1])

        return files

    def _generate_description(self, entries: List[dict], pdf_url: str = None) -> str:
        """Generate description with PDF link, tone, format, and transcript in markdown."""
        parts = []

        if pdf_url:
            parts.append(f"[Transcript (with German Translation)]({pdf_url})")

        # Add tone and format from first entry metadata (matches exporter.py logic)
        if entries:
            metadata = entries[0]
            tone = metadata.get("tone", "")
            fmt = metadata.get("format", "")
            if fmt or tone:
                if pdf_url:
                    parts.append("")
                if fmt:
                    parts.append(f"**Format:** {fmt}")
                if tone:
                    parts.append(f"**Tone:** {tone}")
                parts.append("")

        parts.append("---")
        parts.append("")
        parts.append("## Transcript")
        parts.append("")

        for entry in entries:
            q = entry.get("question", "")
            a = entry.get("answer", "")
            if q and a:
                parts.append(f"**{q}**\n")
                parts.append(f"{a}")
                parts.append("\n")

        return "\n".join(parts)

    def upload_episode(
            self,
            title: str,
            slug: str,
            audio_file: str,
            description: str = "",
            cover_file: Optional[str] = None,
            chapters_file: Optional[str] = None,
            transcript_file: Optional[str] = None,
    ) -> dict:
        """Upload and create a new episode."""
        slug = get_slug(slug)
        url = f"{self.host}/episodes"

        with ExitStack() as stack:
            audio = stack.enter_context(open(audio_file, "rb"))
            files = {
                "audio_file": (Path(audio_file).name, audio, "audio/mpeg"),
            }

            data = {
                "title": title,
                "slug": slug,
                "podcast_id": int(self.podcast_id),
                "user_id": int(self.user_id),
                "created_by": int(self.user_id),
                "updated_by": int(self.user_id),
                "description": description,
                "type": "full",
                "block": "no",
                "premium": "no",
                "parental_advisory": "clean",
            }

            if cover_file:
                cover = stack.enter_context(open(cover_file, "rb"))
                files["cover"] = (Path(cover_file).name, cover, "image/jpeg")

            if chapters_file:
                chapters = stack.enter_context(open(chapters_file, "rb"))
                files["chapters_file"] = (Path(chapters_file).name, chapters, "application/json")
                data["chapters-choice"] = "upload-file"

            if transcript_file:
                transcript = stack.enter_context(open(transcript_file, "rb"))
                files["transcript_file"] = (Path(transcript_file).name, transcript, "application/x-subrip")
                data["transcript-choice"] = "upload-file"

            response = requests.post(url, files=files, data=data, auth=self._get_auth())

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to upload episode: {response.status_code} - {response.text}")

    def publish_episode(self, episode_id: int, publication_method: str = "now") -> dict:
        """Publish an episode."""
        url = f"{self.host}/episodes/{episode_id}/publish"

        data = {
            "publication_method": publication_method,
            "client_timezone": "UTC",
            "user_id": int(self.user_id),
            "created_by": int(self.user_id),
            "updated_by": int(self.user_id),
        }
        response = requests.post(url, data=data, auth=self._get_auth())

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to publish episode: {response.status_code} - {response.text}")

    def upload_and_publish_episode(
            self,
            title: str,
            slug: str,
            audio_file: str,
            description: str = "",
            cover_file: Optional[str] = None,
            chapters_file: Optional[str] = None,
            transcript_file: Optional[str] = None,
            publish: bool = False,
    ) -> dict:
        """Upload and optionally publish an episode."""
        result = self.upload_episode(
            title=title,
            slug=slug,
            audio_file=audio_file,
            description=description,
            cover_file=cover_file,
            chapters_file=chapters_file,
            transcript_file=transcript_file,
        )

        if publish:
            episode_id = result.get("id")
            if episode_id:
                result = self.publish_episode(episode_id)
                print(f"Episode published: {title}")

        return result


def publish_episode(
        audio_file: str,
        title: str,
        slug: str,
        description: str = "",
        cover_file: Optional[str] = None,
        publish: bool = False,
) -> dict:
    """Upload and optionally publish an episode to Castopod."""
    publisher = CastopodPublisher()

    result = publisher.upload_episode(
        title=title,
        slug=slug,
        audio_file=audio_file,
        description=description,
        cover_file=cover_file,
    )

    print(f"Uploaded episode: {result}")

    if publish:
        episode_id = result.get("id")
        if episode_id:
            result = publisher.publish_episode(episode_id)
            print(f"Episode published: {title}")
        else:
            print(f"Episode uploaded but could not get ID to publish: {title}")

    return result


def publish_topic_episodes(topic: str, entries: List[dict], publish: bool = False) -> dict:
    """Publish both shadowing and plain episodes for a topic."""
    publisher = CastopodPublisher()
    ftp = FTPClient()

    export_files = publisher._find_export_files(topic)
    if not export_files:
        raise ValueError(f"No export files found for topic: {topic}")

    print(f"Exporting files: {export_files.keys()}")

    # Increment episode counter only on publish
    episode_num = None
    if publish:
        episode_num = publisher._get_next_episode_number()
        print(f"Episode counter incremented to {episode_num}")

    pdf_url = None
    if "pdf" in export_files:
        pdf_path = export_files["pdf"]
        pdf_filename = Path(pdf_path).name
        pdf_url = ftp.upload_file(pdf_path, pdf_filename.replace(' ', ''))
        if pdf_url:
            print(f"Transcript PDF URL: {pdf_url}")

    description = publisher._generate_description(entries, pdf_url)

    results = {}

    base_title = export_files.get("base_name", entries[0]["topic"])

    if "shadowing_mp3" in export_files:
        slug_shadow = get_slug(base_title)

        result = publisher.upload_and_publish_episode(
            title=f"{base_title}",
            slug=slug_shadow,
            audio_file=export_files["shadowing_mp3"],
            description=description,
            chapters_file=export_files.get("json"),
            transcript_file=export_files.get("srt"),
            publish=publish,
        )
        results["shadowing"] = result
        print(f"Shadowing episode uploaded: {base_title} - Shadowing")

    if "plain_mp3" in export_files:
        plain_title = export_files.get("plain_base_name", entries[0]["topic"])
        slug_plain = get_slug(plain_title)

        plain_description = publisher._generate_description(entries, pdf_url)

        result = publisher.upload_and_publish_episode(
            title=f"{plain_title}",
            slug=slug_plain,
            audio_file=export_files["plain_mp3"],
            description=plain_description,
            chapters_file=export_files.get("plain_json"),
            transcript_file=export_files.get("plain_srt"),
            publish=publish,
        )
        results["plain"] = result
        print(f"Plain episode uploaded: {plain_title}")

    return results
