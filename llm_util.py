from typing import List
import requests
from config import XAI_API_KEY, LLM_MODEL


def translate_to_german(sentences: List[str]) -> List[str]:
    """Translate sentences to German using xAI API (grok)."""
    if not XAI_API_KEY:
        print("Warning: XAI_API_KEY not set. Returning empty translations.")
        return [""] * len(sentences)

    if not sentences:
        return []

    prompt = "Translate the following sentences to German. Return ONLY the translations, one per line, no numbering, no explanation:\n\n"
    prompt += "\n".join(sentences)

    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {XAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 5000,
                "temperature": 0.3
            },
            timeout=120
        )
        response.raise_for_status()

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        translations = [line.strip() for line in content.split("\n") if line.strip()]
        
        if len(translations) < len(sentences):
            translations = (translations + [""] * len(sentences))[:len(sentences)]
        
        return translations

    except Exception as e:
        print(f"Translation failed: {e}")
        return [""] * len(sentences)