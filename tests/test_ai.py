import importlib
import os
import unittest
from unittest.mock import AsyncMock, patch

from ai.providers.openai import OpenAIChatCompletionsProtocol

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("QUOTE_CHANNEL_ID", "1")
os.environ.setdefault("TURSO_DATABASE_URL", ":memory:")
os.environ.setdefault("TURSO_AUTH_TOKEN", "test-token")

ai_module = importlib.import_module("commands.ai")


class AIRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_xai_models_use_native_agentic_web_search(self):
        with (
            patch.object(
                ai_module,
                "get_model",
                AsyncMock(return_value="openrouter/x-ai/grok-4.3"),
            ),
            patch.object(
                ai_module,
                "get_thinking",
                AsyncMock(return_value="medium"),
            ),
        ):
            params = await ai_module.request_params("ask")

        self.assertEqual(
            params.extra_body,
            {"tools": [ai_module.OPENROUTER_WEB_SEARCH]},
        )
        self.assertEqual(params.reasoning.effort, "medium")

    async def test_other_models_do_not_receive_openrouter_web_tool(self):
        with patch.object(
            ai_module,
            "get_model",
            AsyncMock(return_value="openrouter/google/gemini-3-flash-preview"),
        ):
            params = await ai_module.request_params("tldr")

        self.assertIsNone(params.extra_body)

    async def test_provider_speaks_chat_completions(self):
        # OpenRouter's Responses endpoint rejects audio/* parts, breaking /tr.
        self.addCleanup(ai_module.close_ai_provider)
        provider = ai_module.openrouter_provider()

        self.assertIsInstance(provider.protocol, OpenAIChatCompletionsProtocol)


if __name__ == "__main__":
    unittest.main()
