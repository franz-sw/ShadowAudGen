from typing import List
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import XAI_API_KEY, LLM_MODEL, REASONING_EFFORT, MAX_LLM_WORKERS


def _translate_chunk(sentences: List[str]) -> List[str]:
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
                "temperature": 0.3,
                "reasoning_effort": REASONING_EFFORT
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
        print(f"  Chunk translation failed: {e}")
        return [""] * len(sentences)


def translate_to_german(sentences: List[str]) -> List[str]:
    """Translate sentences to German using xAI API (grok) with parallel processing."""
    if not XAI_API_KEY:
        print("Warning: XAI_API_KEY not set. Returning empty translations.")
        return [""] * len(sentences)

    if not sentences:
        return []

    chunk_size = max(1, len(sentences) // MAX_LLM_WORKERS)
    chunks = [sentences[i:i + chunk_size] for i in range(0, len(sentences), chunk_size)]

    print(f"Translating {len(sentences)} sentence(s) to German via {LLM_MODEL} ({len(chunks)} worker(s))...")

    results = [None] * len(chunks)
    with ThreadPoolExecutor(max_workers=MAX_LLM_WORKERS) as executor:
        future_to_idx = {executor.submit(_translate_chunk, chunk): i for i, chunk in enumerate(chunks)}
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                print(f"  Worker {idx} failed: {e}")
                results[idx] = [""] * len(chunks[idx])

    translations = []
    for chunk_result in results:
        translations.extend(chunk_result)

    print(f"  Got {len(translations)} translation(s)")
    return translations