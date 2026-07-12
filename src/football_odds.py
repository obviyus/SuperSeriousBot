import datetime
import json
import math
import re
from dataclasses import dataclass

import aiohttp

from config.logger import logger

POLYMARKET_SEARCH_URL = "https://gamma-api.polymarket.com/public-search"
POLYMARKET_EVENT_URL = "https://polymarket.com/event/{slug}"
POLYMARKET_COMPETITIONS = {
    "eng.1": "epl",
    "uefa.champions": "ucl",
    "eng.fa": "efa",
}
IGNORED_TEAM_WORDS = {"afc", "cf", "fc"}
MAX_KICKOFF_DIFFERENCE = datetime.timedelta(hours=2)


@dataclass(frozen=True, slots=True)
class OddsFixture:
    competition: str
    home_team: str
    away_team: str
    kickoff: datetime.datetime
    home_tracked: bool
    away_tracked: bool


@dataclass(frozen=True, slots=True)
class MatchOdds:
    event_slug: str
    home: float
    draw: float
    away: float


def normalized_words(name: str) -> list[str]:
    return [
        word
        for word in re.findall(r"[a-z0-9]+", name.casefold())
        if word not in IGNORED_TEAM_WORDS
    ]


def contains_team_name(text: str, team: str) -> bool:
    text_words = normalized_words(text)
    team_words = normalized_words(team)
    return any(
        text_words[index : index + len(team_words)] == team_words
        for index in range(len(text_words) - len(team_words) + 1)
    )


def parse_time(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def tracked_teams(fixture: OddsFixture) -> list[str]:
    teams: list[str] = []
    if fixture.home_tracked:
        teams.append(fixture.home_team)
    if fixture.away_tracked:
        teams.append(fixture.away_team)
    return teams


def string_mapping(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, object] = {}
    for key, item in value.items():
        if isinstance(key, str):
            result[key] = item
    return result


async def search_polymarket(
    session: aiohttp.ClientSession,
    fixture: OddsFixture,
) -> list[dict[str, object]]:
    events: dict[str, dict[str, object]] = {}
    queries = {
        f"{fixture.home_team} {fixture.away_team}",
        " ".join(tracked_teams(fixture)),
    }
    for query in queries:
        async with session.get(
            POLYMARKET_SEARCH_URL,
            params={
                "q": query,
                "events_status": "active",
                "limit_per_type": 50,
                "search_profiles": "false",
            },
        ) as response:
            response.raise_for_status()
            payload = string_mapping(await response.json())
        event_values = payload.get("events") if payload is not None else None
        if not isinstance(event_values, list):
            raise ValueError("Polymarket search returned an invalid response.")
        for value in event_values:
            event = string_mapping(value)
            if event is not None and "id" in event:
                events[str(event["id"])] = event
    return list(events.values())


def event_matches(event: dict[str, object], fixture: OddsFixture) -> bool:
    slug = str(event.get("slug", ""))
    if not slug.startswith(f"{POLYMARKET_COMPETITIONS[fixture.competition]}-"):
        return False
    if event.get("closed") or not event.get("active"):
        return False
    if event.get("eventDate") != fixture.kickoff.date().isoformat():
        return False

    title = str(event.get("title", ""))
    if not any(contains_team_name(title, team) for team in tracked_teams(fixture)):
        return False
    return isinstance(event.get("endDate"), str)


def yes_price(market: dict[str, object]) -> float | None:
    try:
        outcomes = json.loads(str(market["outcomes"]))
        prices = json.loads(str(market["outcomePrices"]))
    except (KeyError, json.JSONDecodeError):
        return None
    if not isinstance(outcomes, list) or not isinstance(prices, list):
        return None
    if len(outcomes) != len(prices) or "Yes" not in outcomes:
        return None
    try:
        price = float(prices[outcomes.index("Yes")])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(price) or not 0 <= price <= 1:
        return None
    return price


def extract_odds(event: dict[str, object], fixture: OddsFixture) -> MatchOdds | None:
    candidates: dict[str, list[float]] = {"home": [], "draw": [], "away": []}
    unmatched_prices: list[float] = []
    markets = event.get("markets")
    if not isinstance(markets, list):
        return None

    moneyline_markets: list[dict[str, object]] = []
    for value in markets:
        market = string_mapping(value)
        if (
            market is None
            or market.get("sportsMarketType") != "moneyline"
            or not market.get("active")
            or market.get("closed")
        ):
            continue
        moneyline_markets.append(market)
    if len(moneyline_markets) != 3:
        return None

    for market in moneyline_markets:
        price = yes_price(market)
        if price is None:
            return None
        question = str(market.get("question", ""))
        if "draw" in normalized_words(question):
            candidates["draw"].append(price)
        elif contains_team_name(question, fixture.home_team):
            candidates["home"].append(price)
        elif contains_team_name(question, fixture.away_team):
            candidates["away"].append(price)
        else:
            unmatched_prices.append(price)

    if sum(map(len, candidates.values())) + len(unmatched_prices) != 3:
        return None
    if any(len(values) > 1 for values in candidates.values()):
        return None
    prices = {outcome: values[0] for outcome, values in candidates.items() if values}
    missing_sides = {"home", "away"} - prices.keys()
    if len(missing_sides) == 1 and len(unmatched_prices) == 1:
        missing_side = missing_sides.pop()
        prices[missing_side] = unmatched_prices[0]

    if prices.keys() != {"home", "draw", "away"}:
        return None
    return MatchOdds(
        event_slug=str(event["slug"]),
        home=prices["home"],
        draw=prices["draw"],
        away=prices["away"],
    )


async def fetch_match_odds(
    session: aiohttp.ClientSession,
    fixture: OddsFixture,
) -> MatchOdds | None:
    events = await search_polymarket(session, fixture)
    matches = [event for event in events if event_matches(event, fixture)]
    if len(matches) != 1:
        if len(matches) > 1:
            logger.warning(
                "Found %s Polymarket events for %s vs %s",
                len(matches),
                fixture.home_team,
                fixture.away_team,
            )
        return None

    event = matches[0]
    event_kickoff = parse_time(str(event["endDate"]))
    difference = abs(event_kickoff - fixture.kickoff)
    if difference > MAX_KICKOFF_DIFFERENCE:
        # Polymarket has published correct FA Cup events with kickoff hours wrong.
        logger.warning(
            "Polymarket kickoff differs by %s hours for %s vs %s",
            difference.total_seconds() / 3600,
            fixture.home_team,
            fixture.away_team,
        )
    return extract_odds(event, fixture)


def event_url(odds: MatchOdds) -> str:
    return POLYMARKET_EVENT_URL.format(slug=odds.event_slug)
