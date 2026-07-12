import datetime
import os

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("QUOTE_CHANNEL_ID", "1")
os.environ.setdefault("TURSO_DATABASE_URL", ":memory:")
os.environ.setdefault("TURSO_AUTH_TOKEN", "test-token")

import football_odds


def fixture() -> football_odds.OddsFixture:
    return football_odds.OddsFixture(
        competition="uefa.champions",
        home_team="Manchester City",
        away_team="Bayern Munich",
        kickoff=datetime.datetime(2026, 3, 17, 20, tzinfo=datetime.UTC),
        home_tracked=True,
        away_tracked=False,
    )


def moneyline(question: str, price: str) -> dict[str, object]:
    return {
        "sportsMarketType": "moneyline",
        "active": True,
        "closed": False,
        "question": question,
        "outcomes": '["Yes", "No"]',
        "outcomePrices": f'["{price}", "0.50"]',
    }


def test_match_does_not_depend_on_opponent_alias() -> None:
    event = {
        "slug": "ucl-mnc-bay-2026-03-17",
        "title": "Manchester City FC vs. FC Bayern München",
        "eventDate": "2026-03-17",
        "endDate": "2026-03-17T20:00:00Z",
        "active": True,
        "closed": False,
    }

    assert football_odds.event_matches(event, fixture())


def test_match_requires_tracked_team_as_one_phrase() -> None:
    manchester_united_fixture = football_odds.OddsFixture(
        competition="eng.1",
        home_team="Manchester United",
        away_team="Brighton & Hove Albion",
        kickoff=datetime.datetime(2026, 3, 17, 20, tzinfo=datetime.UTC),
        home_tracked=True,
        away_tracked=False,
    )
    event = {
        "slug": "epl-mac-new-2026-03-17",
        "title": "Manchester City FC vs. Newcastle United FC",
        "eventDate": "2026-03-17",
        "endDate": "2026-03-17T20:00:00Z",
        "active": True,
        "closed": False,
    }

    assert not football_odds.event_matches(event, manchester_united_fixture)


def test_match_allows_alias_for_second_tracked_team() -> None:
    big_six_fixture = football_odds.OddsFixture(
        competition="eng.1",
        home_team="Manchester City",
        away_team="Manchester United",
        kickoff=datetime.datetime(2026, 3, 17, 20, tzinfo=datetime.UTC),
        home_tracked=True,
        away_tracked=True,
    )
    event = {
        "slug": "epl-mac-mun-2026-03-17",
        "title": "Manchester City FC vs. Man Utd",
        "eventDate": "2026-03-17",
        "endDate": "2026-03-17T20:00:00Z",
        "active": True,
        "closed": False,
    }

    assert football_odds.event_matches(event, big_six_fixture)


def test_extract_odds_assigns_aliased_opponent_market() -> None:
    event = {
        "slug": "ucl-mnc-bay-2026-03-17",
        "markets": [
            moneyline("Will Manchester City FC win?", "0.45"),
            moneyline("Will the match end in a draw?", "0.25"),
            moneyline("Will FC Bayern München win?", "0.30"),
        ],
    }

    odds = football_odds.extract_odds(event, fixture())

    assert odds
    assert (odds.home, odds.draw, odds.away) == (0.45, 0.25, 0.3)


def test_extract_odds_rejects_invalid_price() -> None:
    event = {
        "slug": "ucl-mnc-bay-2026-03-17",
        "markets": [
            moneyline("Will Manchester City FC win?", "NaN"),
            moneyline("Will the match end in a draw?", "0.25"),
            moneyline("Will FC Bayern München win?", "0.30"),
        ],
    }

    assert football_odds.extract_odds(event, fixture()) is None


def test_extract_odds_rejects_closed_moneyline() -> None:
    closed_market = moneyline("Will FC Bayern München win?", "0.30")
    closed_market["closed"] = True
    event = {
        "slug": "ucl-mnc-bay-2026-03-17",
        "markets": [
            moneyline("Will Manchester City FC win?", "0.45"),
            moneyline("Will the match end in a draw?", "0.25"),
            closed_market,
        ],
    }

    assert football_odds.extract_odds(event, fixture()) is None


def test_extract_odds_rejects_extra_malformed_moneyline() -> None:
    event = {
        "slug": "ucl-mnc-bay-2026-03-17",
        "markets": [
            moneyline("Will Manchester City FC win?", "0.45"),
            moneyline("Will the match end in a draw?", "0.25"),
            moneyline("Will FC Bayern München win?", "0.30"),
            moneyline("Malformed replacement", "NaN"),
        ],
    }

    assert football_odds.extract_odds(event, fixture()) is None


def test_extract_odds_rejects_duplicate_outcome() -> None:
    event = {
        "slug": "ucl-mnc-bay-2026-03-17",
        "markets": [
            moneyline("Will the match end in a draw?", "0.25"),
            moneyline("Will the match end in a draw?", "0.30"),
            moneyline("Will Manchester City FC win?", "0.45"),
        ],
    }

    assert football_odds.extract_odds(event, fixture()) is None


def test_extract_odds_assigns_aliased_tracked_team_price() -> None:
    big_six_fixture = football_odds.OddsFixture(
        competition="eng.1",
        home_team="Manchester City",
        away_team="Manchester United",
        kickoff=datetime.datetime(2026, 3, 17, 20, tzinfo=datetime.UTC),
        home_tracked=True,
        away_tracked=True,
    )
    event = {
        "slug": "epl-mac-mun-2026-03-17",
        "markets": [
            moneyline("Will Manchester City FC win?", "0.45"),
            moneyline("Will the match end in a draw?", "0.25"),
            moneyline("Will the Red Devils win?", "0.30"),
        ],
    }

    odds = football_odds.extract_odds(event, big_six_fixture)

    assert odds
    assert odds.away == 0.3
