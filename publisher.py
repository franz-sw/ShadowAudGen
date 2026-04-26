import os
import requests
from pathlib import Path
from typing import Optional

from config import CASTOPOD_HOST, CASTOPOD_PODCAST_ID, CASTOPOD_USER_ID, CASTOPOD_AUTH_USERNAME, CASTOPOD_AUTH_PASSWORD


class CastopodPublisher:
    def __init__(self):
        self.host = CASTOPOD_HOST
        self.podcast_id = CASTOPOD_PODCAST_ID
        self.user_id = CASTOPOD_USER_ID
        self.username = CASTOPOD_AUTH_USERNAME
        self.password = CASTOPOD_AUTH_PASSWORD

        if not all([self.host, self.podcast_id, self.user_id, self.username, self.password]):
            raise ValueError("Missing required Castopod configuration. Check .env file.")

    def _get_auth(self):
        return (self.username, self.password)

    def upload_episode(
        self,
        title: str,
        slug: str,
        audio_file: str,
        description: str = "",
        cover_file: Optional[str] = None,
    ) -> dict:
        """Upload and create a new episode."""
        url = f"{self.host}/episodes"

        with open(audio_file, "rb") as audio:
            files = {
                "audio_file": (Path(audio_file).name, audio, "audio/mpeg"),
            }

            data = {
                "title": title,
                "slug": slug,
                "podcast_id": self.podcast_id,
                "user_id": self.user_id,
                "updated_by": self.user_id,
                "description": description,
            }

            if cover_file:
                with open(cover_file, "rb") as cover:
                    files["cover"] = (Path(cover_file).name, cover, "image/jpeg")
                    response = requests.post(url, files=files, data=data, auth=self._get_auth())
            else:
                response = requests.post(url, files=files, data=data, auth=self._get_auth())

        if response.status_code == 201:
            return response.json()
        else:
            raise Exception(f"Failed to upload episode: {response.status_code} - {response.text}")

    def publish_episode(self, episode_id: int, publication_method: str = "now") -> dict:
        """Publish an episode."""
        url = f"{self.host}/episodes/{episode_id}/publish"

        data = {
            "publication_method": publication_method,
            "client_timezone": "UTC",
        }

        response = requests.post(url, data=data, auth=self._get_auth())

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to publish episode: {response.status_code} - {response.text}")


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

    if publish:
        episode_id = result.get("id")
        if episode_id:
            result = publisher.publish_episode(episode_id)
            print(f"Episode published: {title}")
        else:
            print(f"Episode uploaded but could not get ID to publish: {title}")

    return result