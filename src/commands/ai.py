import json
from collections.abc import AsyncIterator

import aiohttp

from commands.model import get_model, get_thinking, normalize_model_name
from config.options import config

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
type JsonObject = dict[str, object]


def openrouter_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": "SuperSeriousBot",
        "HTTP-Referer": "https://superserio.us",
    }


def openrouter_api_key() -> str:
    return config.API.OPENROUTER_API_KEY


async def openrouter_payload(
    command: str,
    messages: list[JsonObject],
    *,
    max_tokens: int | None = None,
    stream: bool = False,
    modalities: list[str] | None = None,
) -> JsonObject:
    model_name = normalize_model_name(await get_model(command))
    payload: JsonObject = {"model": model_name, "messages": messages}
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if stream:
        payload["stream"] = True
    if modalities:
        payload["modalities"] = modalities
    if model_name.startswith("x-ai/"):
        payload["plugins"] = [{"id": "web", "engine": "native"}]
    if command == "ask" and (thinking_level := await get_thinking()) != "none":
        payload["reasoning"] = {"effort": thinking_level}
    return payload


async def openrouter_json(
    session: aiohttp.ClientSession,
    payload: JsonObject,
) -> JsonObject:
    async with session.post(
        OPENROUTER_API_URL,
        headers=openrouter_headers(openrouter_api_key()),
        json=payload,
    ) as response:
        response.raise_for_status()
        data = await response.json()
    return data if isinstance(data, dict) else {}


async def stream_openrouter_deltas(response: aiohttp.ClientResponse) -> AsyncIterator[str]:
    buffer = ""
    async for chunk in response.content.iter_chunked(1024):
        buffer += chunk.decode("utf-8", errors="ignore")
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            if not (line := line.strip()).startswith("data:"):
                continue
            if (data := line[5:].strip()) == "[DONE]":
                return
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = payload.get("choices")
            first_choice = choices[0] if isinstance(choices, list) and choices else None
            delta = first_choice.get("delta") if isinstance(first_choice, dict) else None
            content = delta.get("content") if isinstance(delta, dict) else None
            if content:
                yield content


def first_message_content(response: JsonObject) -> object:
    choices = response.get("choices")
    choice = choices[0] if isinstance(choices, list) and choices else None
    match choice:
        case {"message": {"content": content}}:
            return content
    return None
