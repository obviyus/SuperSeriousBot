import html
import re
from dataclasses import dataclass

import aiohttp

STREAM_ROOT_URL = "https://thestreameast.one/"
STREAM_LOOKUP_TIMEOUT_SECONDS = 5
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
}

STREAM_ITEM_PATTERN = re.compile(
    r'<a href="(?P<url>https://thestreameast\.one/watch/[^"]+)"'
    r'.*?<span\s+class="d-md-inline[^"]*">\s*(?P<title>.*?)\s*</span>',
    re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class StreamLink:
    url: str
    home_team: str
    away_team: str


def normalized_words(name: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", name.casefold())


def contains_team_name(text: str, team: str) -> bool:
    text_words = normalized_words(text)
    team_words = normalized_words(team)
    if not team_words:
        return False
    return any(
        text_words[index : index + len(team_words)] == team_words
        for index in range(len(text_words) - len(team_words) + 1)
    )


def same_team(left: str, right: str) -> bool:
    return contains_team_name(left, right) or contains_team_name(right, left)


def parse_stream_links(page_html: str) -> list[StreamLink]:
    links: list[StreamLink] = []
    for match in STREAM_ITEM_PATTERN.finditer(page_html):
        title = html.unescape(match.group("title"))
        if " vs " not in title:
            continue
        home_team, away_team = title.split(" vs ", 1)
        links.append(
            StreamLink(
                url=html.unescape(match.group("url")).strip(),
                home_team=home_team.strip(),
                away_team=away_team.strip(),
            )
        )
    return links


def match_stream_link(
    links: list[StreamLink],
    home_team: str,
    away_team: str,
) -> str | None:
    for link in links:
        if (
            same_team(link.home_team, home_team)
            and same_team(link.away_team, away_team)
        ) or (
            same_team(link.home_team, away_team)
            and same_team(link.away_team, home_team)
        ):
            return link.url
    return None


async def fetch_stream_links() -> list[StreamLink]:
    timeout = aiohttp.ClientTimeout(total=STREAM_LOOKUP_TIMEOUT_SECONDS)
    async with (
        aiohttp.ClientSession(timeout=timeout, headers=BROWSER_HEADERS) as session,
        session.get(STREAM_ROOT_URL) as response,
    ):
        response.raise_for_status()
        return parse_stream_links(await response.text())
