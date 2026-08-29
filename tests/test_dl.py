import importlib
import os
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
from urllib.parse import urlparse

import httpx2

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("QUOTE_CHANNEL_ID", "1")
os.environ.setdefault("TURSO_DATABASE_URL", ":memory:")
os.environ.setdefault("TURSO_AUTH_TOKEN", "test-token")

dl = importlib.import_module("commands.dl")


class SessionContext:
    def __init__(self) -> None:
        self.session = SimpleNamespace()

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_args):
        return None


class DownloadTests(IsolatedAsyncioTestCase):
    async def test_instagram_post_cobalt_error_uses_page_image(self) -> None:
        message = SimpleNamespace(reply_text=AsyncMock())
        url = urlparse("https://www.instagram.com/p/DbW6GhitktH/")
        session = SessionContext()

        with (
            patch.object(dl.config.API, "COBALT_URL", "http://cobalt/"),
            patch.object(dl.httpx2, "AsyncClient", return_value=session),
            patch.object(
                dl,
                "_request_cobalt",
                AsyncMock(
                    return_value={
                        "status": "error",
                        "error": {"code": "error.api.fetch.empty"},
                    }
                ),
            ),
            patch.object(dl, "_fetch_instagram_image", AsyncMock()) as fallback,
        ):
            await dl._download_media(message, url)

        fallback.assert_awaited_once_with(message, session.session, url.geturl())
        message.reply_text.assert_not_awaited()

    async def test_instagram_image_parser_reads_og_image(self) -> None:
        parser = dl.InstagramImageParser()
        parser.feed(
            '<meta property="og:image" content="https://cdn.example/image.jpg?a=1&amp;b=2">'
        )

        self.assertEqual(parser.image_url, "https://cdn.example/image.jpg?a=1&b=2")

    async def test_instagram_reel_image_falls_back_to_yt_dlp(self) -> None:
        message = SimpleNamespace(reply_text=AsyncMock())
        url = urlparse("https://www.instagram.com/reel/DbT2vSHtvXs/")
        session = SessionContext()

        with (
            patch.object(dl.config.API, "COBALT_URL", "http://cobalt/"),
            patch.object(dl.httpx2, "AsyncClient", return_value=session),
            patch.object(
                dl,
                "_request_cobalt",
                AsyncMock(
                    return_value={
                        "status": "tunnel",
                        "url": "http://cobalt/tunnel/photo",
                        "filename": "instagram_DbT2vSHtvXs.jpg",
                    }
                ),
            ),
            patch.object(dl, "_fetch_with_yt_dlp", AsyncMock()) as fallback,
            patch.object(dl, "_fetch_and_send", AsyncMock()) as cobalt_fetch,
        ):
            await dl._download_media(message, url)

        fallback.assert_awaited_once_with(message, session.session, url.geturl())
        cobalt_fetch.assert_not_awaited()

    async def test_instagram_reel_cobalt_video_stays_on_cobalt(self) -> None:
        message = SimpleNamespace(reply_text=AsyncMock())
        url = urlparse("https://www.instagram.com/reel/DbT2vSHtvXs/")
        session = SessionContext()
        cobalt_url = "https://cdn.example.com/reel.mp4"

        with (
            patch.object(dl.config.API, "COBALT_URL", "http://cobalt/"),
            patch.object(dl.httpx2, "AsyncClient", return_value=session),
            patch.object(
                dl,
                "_request_cobalt",
                AsyncMock(
                    return_value={
                        "status": "redirect",
                        "url": cobalt_url,
                        "filename": "instagram_DbT2vSHtvXs.mp4",
                    }
                ),
            ),
            patch.object(dl, "_fetch_with_yt_dlp", AsyncMock()) as fallback,
            patch.object(dl, "_fetch_and_send", AsyncMock()) as cobalt_fetch,
        ):
            await dl._download_media(message, url)

        fallback.assert_not_awaited()
        cobalt_fetch.assert_awaited_once_with(
            message,
            session.session,
            cobalt_url,
            "instagram_DbT2vSHtvXs.mp4",
        )

    async def test_instagram_reel_cobalt_failure_falls_back_to_yt_dlp(self) -> None:
        message = SimpleNamespace(reply_text=AsyncMock())
        url = urlparse("https://www.instagram.com/reel/DbT2vSHtvXs/")
        session = SessionContext()

        with (
            patch.object(dl.config.API, "COBALT_URL", "http://cobalt/"),
            patch.object(dl.httpx2, "AsyncClient", return_value=session),
            patch.object(
                dl,
                "_request_cobalt",
                AsyncMock(side_effect=httpx2.ConnectError("offline")),
            ),
            patch.object(dl, "_fetch_with_yt_dlp", AsyncMock()) as fallback,
        ):
            await dl._download_media(message, url)

        fallback.assert_awaited_once_with(message, session.session, url.geturl())
