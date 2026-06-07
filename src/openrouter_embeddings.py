import json

import aiohttp

OPENROUTER_EMBEDDINGS_API_URL = "https://openrouter.ai/api/v1/embeddings"
OPENROUTER_TITLE = "SuperSeriousBot"
OPENROUTER_REFERER = "https://superserio.us"


def openrouter_api_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": OPENROUTER_TITLE,
        "HTTP-Referer": OPENROUTER_REFERER,
    }


async def openrouter_embeddings(
    session: aiohttp.ClientSession,
    api_key: str,
    model: str,
    inputs: list[str],
    *,
    dimensions: int,
) -> list[list[float]]:
    payload = {
        "model": model,
        "input": inputs,
        "dimensions": dimensions,
    }
    async with session.post(
        OPENROUTER_EMBEDDINGS_API_URL,
        headers=openrouter_api_headers(api_key),
        json=payload,
        timeout=aiohttp.ClientTimeout(total=120),
    ) as response:
        response.raise_for_status()
        data = await response.json()

    embeddings = []
    for item in data["data"]:
        embedding = item["embedding"]
        if len(embedding) != dimensions:
            raise RuntimeError(
                f"Expected {dimensions} embedding dimensions, got {len(embedding)}"
            )
        embeddings.append(embedding)
    return embeddings


def vector32_json(embedding: list[float]) -> str:
    return json.dumps(embedding, separators=(",", ":"))
