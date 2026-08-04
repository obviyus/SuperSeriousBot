from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import ai
import pydantic
from ai.providers.openai import (
    OpenAIChatCompletionsProtocol,
    OpenAICompatibleProvider,
)
from ai.types.messages import Message

from commands.model import get_model, get_thinking, normalize_model_name
from config.options import config

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_HEADERS = {
    "X-Title": "SuperSeriousBot",
    "HTTP-Referer": "https://superserio.us",
}
OPENROUTER_WEB_SEARCH = {
    "type": "openrouter:web_search",
    "parameters": {
        "engine": "native",
        "max_total_results": 20,
    },
}

_provider: OpenAICompatibleProvider | None = None


def openrouter_provider() -> OpenAICompatibleProvider:
    global _provider
    if _provider is None:
        provider = ai.get_provider(
            "openai",
            base_url=OPENROUTER_BASE_URL,
            api_key=config.API.OPENROUTER_API_KEY,
            headers=OPENROUTER_HEADERS,
            protocol=OpenAIChatCompletionsProtocol(),
        )
        if not isinstance(provider, OpenAICompatibleProvider):
            raise TypeError("OpenRouter requires an OpenAI-compatible provider.")
        _provider = provider
    return _provider


async def close_ai_provider() -> None:
    global _provider
    if _provider is not None:
        await _provider.aclose()
        _provider = None


async def request_params(
    command: str,
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    extra_body: dict[str, object] | None = None,
) -> ai.InferenceRequestParams:
    body = dict(extra_body or {})
    model_name = normalize_model_name(await get_model(command))
    if command == "ask" and model_name.startswith("x-ai/"):
        body["tools"] = [OPENROUTER_WEB_SEARCH]

    params = ai.InferenceRequestParams(
        output=ai.OutputParams(max_tokens=max_tokens),
        extra_body=body or None,
    )
    if temperature is not None:
        params = params.with_temperature(temperature)
    if command == "ask" and (thinking_level := await get_thinking()) != "none":
        params = params.with_reasoning_effort(thinking_level)
    return params


async def model(command: str) -> ai.Model:
    return ai.Model(
        id=normalize_model_name(await get_model(command)),
        provider=openrouter_provider(),
    )


@asynccontextmanager
async def stream_model(
    command: str,
    messages: list[Message],
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    extra_body: dict[str, object] | None = None,
) -> AsyncIterator[ai.Stream[str]]:
    async with ai.stream(
        await model(command),
        messages,
        params=await request_params(
            command,
            max_tokens=max_tokens,
            temperature=temperature,
            extra_body=extra_body,
        ),
    ) as stream:
        yield stream


async def generate_text(
    command: str,
    messages: list[Message],
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    extra_body: dict[str, object] | None = None,
) -> str:
    async with stream_model(
        command,
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
        extra_body=extra_body,
    ) as stream:
        async for _ in stream:
            pass
    return stream.output


async def generate_object[OutputT: pydantic.BaseModel](
    command: str,
    messages: list[Message],
    output_type: type[OutputT],
    *,
    max_tokens: int | None = None,
    extra_body: dict[str, object] | None = None,
) -> OutputT:
    async with ai.stream(
        await model(command),
        messages,
        output_type=output_type,
        params=await request_params(
            command,
            max_tokens=max_tokens,
            extra_body=extra_body,
        ),
    ) as stream:
        async for _ in stream:
            pass
    return stream.output
