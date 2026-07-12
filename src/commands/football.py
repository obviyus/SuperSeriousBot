import asyncio
import datetime
import html
from dataclasses import dataclass
from itertools import groupby

import aiohttp
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Update,
)
from telegram.constants import KeyboardButtonStyle, ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from config.db import TursoRow, get_db
from config.logger import logger
from football_odds import MatchOdds, OddsFixture, event_url, fetch_match_odds
from utils.decorators import command
from utils.messages import get_message

ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/{competition}/scoreboard"
)
ESPN_SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/{competition}/summary"
)
SCHEDULED_STATUS = "STATUS_SCHEDULED"
MENTIONS_PER_MESSAGE = 5
ODDS_LOOKUP_TIMEOUT_SECONDS = 5


@dataclass(frozen=True, slots=True)
class Competition:
    slug: str
    name: str


@dataclass(frozen=True, slots=True)
class FootballFixture:
    provider_id: str
    competition: str
    competition_name: str
    home_team: str
    away_team: str
    kickoff_time: int
    status: str


@dataclass(frozen=True, slots=True)
class AlertMember:
    user_id: int
    display_name: str


COMPETITIONS = (
    Competition("eng.1", "Premier League"),
    Competition("uefa.champions", "Champions League"),
    Competition("eng.fa", "FA Cup"),
)
COMPETITIONS_BY_SLUG = {competition.slug: competition for competition in COMPETITIONS}
COMPETITION_ORDER = {
    competition.name: index for index, competition in enumerate(COMPETITIONS)
}
TRACKED_TEAMS = frozenset(
    {
        "Arsenal",
        "Chelsea",
        "Liverpool",
        "Manchester City",
        "Manchester United",
        "Tottenham Hotspur",
    }
)
FIXTURE_UPDATE_LOCK = asyncio.Lock()


def football_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Join",
                    callback_data="fb:join",
                    style=KeyboardButtonStyle.SUCCESS,
                ),
                InlineKeyboardButton(
                    "❌ Leave",
                    callback_data="fb:leave",
                    style=KeyboardButtonStyle.DANGER,
                ),
            ]
        ]
    )


def season_date_ranges(
    now: datetime.datetime,
) -> tuple[
    tuple[datetime.date, datetime.date],
    tuple[datetime.date, datetime.date],
]:
    season_year = now.year if now.month >= 7 else now.year - 1
    return (
        (
            datetime.date(season_year, 7, 1),
            datetime.date(season_year + 1, 6, 30),
        ),
        (
            datetime.date(season_year + 1, 7, 1),
            datetime.date(season_year + 2, 6, 30),
        ),
    )


def utc_timestamp() -> int:
    return int(datetime.datetime.now(datetime.UTC).timestamp())


def is_tracked_fixture(fixture: FootballFixture) -> bool:
    return fixture.competition in COMPETITIONS_BY_SLUG and (
        fixture.home_team in TRACKED_TEAMS or fixture.away_team in TRACKED_TEAMS
    )


def required_mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"ESPN response missing {field}.")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"ESPN response has an invalid {field} key.")
        result[key] = item
    return result


def required_list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"ESPN response missing {field}.")
    result: list[object] = []
    result.extend(value)
    return result


def required_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"ESPN response missing {field}.")
    return value


def required_first(value: object, field: str) -> object:
    items = required_list(value, field)
    if not items:
        raise ValueError(f"ESPN response missing {field}.")
    return items[0]


def parse_fixture_competition(
    provider_id: str,
    competition: Competition,
    value: object,
) -> FootballFixture:
    fixture = required_mapping(value, "competition")
    date_text = required_string(fixture.get("date"), "date")
    status = required_mapping(fixture.get("status"), "status")
    status_type = required_mapping(status.get("type"), "status.type")
    competitors = required_list(fixture.get("competitors"), "competitors")

    teams: dict[str, str] = {}
    for raw_competitor in competitors:
        competitor = required_mapping(raw_competitor, "competitor")
        side = required_string(competitor.get("homeAway"), "homeAway")
        team = required_mapping(competitor.get("team"), "team")
        teams[side] = required_string(team.get("displayName"), "team.displayName")

    kickoff = datetime.datetime.fromisoformat(date_text.replace("Z", "+00:00"))
    return FootballFixture(
        provider_id=provider_id,
        competition=competition.slug,
        competition_name=competition.name,
        home_team=required_string(teams.get("home"), "home team"),
        away_team=required_string(teams.get("away"), "away team"),
        kickoff_time=int(kickoff.timestamp()),
        status=required_string(status_type.get("name"), "status.type.name"),
    )


def parse_scoreboard_event(value: object, competition: Competition) -> FootballFixture:
    event = required_mapping(value, "event")
    provider_id = required_string(event.get("id"), "event.id")
    fixture = required_first(event.get("competitions"), "event.competitions")
    return parse_fixture_competition(provider_id, competition, fixture)


async def fetch_competition_fixtures(
    session: aiohttp.ClientSession,
    competition: Competition,
    now: datetime.datetime,
) -> list[FootballFixture]:
    fixtures: list[FootballFixture] = []
    for start_date, end_date in season_date_ranges(now):
        async with session.get(
            ESPN_SCOREBOARD_URL.format(competition=competition.slug),
            params={
                "dates": f"{start_date:%Y%m%d}-{end_date:%Y%m%d}",
                "limit": "1000",
            },
        ) as response:
            response.raise_for_status()
            payload = required_mapping(await response.json(), "response")

        fixtures.extend(
            parse_scoreboard_event(event, competition)
            for event in required_list(payload.get("events"), "events")
        )
    return fixtures


async def fetch_fixture(
    session: aiohttp.ClientSession,
    fixture: FootballFixture,
) -> FootballFixture:
    competition = COMPETITIONS_BY_SLUG[fixture.competition]
    async with session.get(
        ESPN_SUMMARY_URL.format(competition=competition.slug),
        params={"event": fixture.provider_id},
    ) as response:
        response.raise_for_status()
        payload = required_mapping(await response.json(), "response")

    header = required_mapping(payload.get("header"), "header")
    provider_id = required_string(header.get("id"), "header.id")
    current_fixture = required_first(header.get("competitions"), "header.competitions")
    return parse_fixture_competition(provider_id, competition, current_fixture)


async def store_fixtures(fixtures: list[FootballFixture]) -> None:
    if not fixtures:
        return

    async with get_db() as conn:
        await conn.executemany(
            """
            INSERT INTO football_fixtures (
                provider_id,
                competition,
                competition_name,
                home_team,
                away_team,
                kickoff_time,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (provider_id) DO UPDATE SET
                competition = excluded.competition,
                competition_name = excluded.competition_name,
                home_team = excluded.home_team,
                away_team = excluded.away_team,
                kickoff_time = excluded.kickoff_time,
                status = excluded.status,
                alert_time = CASE
                    WHEN football_fixtures.kickoff_time != excluded.kickoff_time
                    THEN NULL
                    ELSE football_fixtures.alert_time
                END,
                update_time = CURRENT_TIMESTAMP
            """,
            [
                (
                    fixture.provider_id,
                    fixture.competition,
                    fixture.competition_name,
                    fixture.home_team,
                    fixture.away_team,
                    fixture.kickoff_time,
                    fixture.status,
                )
                for fixture in fixtures
            ],
        )


async def reconcile_competition_fixtures(
    competition: Competition,
    fixtures: list[FootballFixture],
) -> None:
    await store_fixtures(fixtures)
    provider_ids = [fixture.provider_id for fixture in fixtures]
    async with get_db() as conn:
        if provider_ids:
            placeholders = ", ".join("?" for _ in provider_ids)
            await conn.execute(
                f"""
                DELETE FROM football_fixtures
                WHERE competition = ?
                  AND provider_id NOT IN ({placeholders})
                """,
                (competition.slug, *provider_ids),
            )
        else:
            await conn.execute(
                "DELETE FROM football_fixtures WHERE competition = ?",
                (competition.slug,),
            )


async def sync_football_fixtures() -> int:
    async with FIXTURE_UPDATE_LOCK:
        now = datetime.datetime.now(datetime.UTC)
        timeout = aiohttp.ClientTimeout(total=30)
        fixture_count = 0
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for competition in COMPETITIONS:
                try:
                    fixtures = await fetch_competition_fixtures(
                        session, competition, now
                    )
                except (aiohttp.ClientError, TimeoutError, ValueError):
                    logger.exception("Could not sync %s fixtures", competition.name)
                    continue
                fixtures = [
                    fixture for fixture in fixtures if is_tracked_fixture(fixture)
                ]
                await reconcile_competition_fixtures(competition, fixtures)
                fixture_count += len(fixtures)

    logger.info("Synced %s football fixtures", fixture_count)
    return fixture_count


def row_to_fixture(row: TursoRow) -> FootballFixture:
    return FootballFixture(
        provider_id=str(row["provider_id"]),
        competition=str(row["competition"]),
        competition_name=str(row["competition_name"]),
        home_team=str(row["home_team"]),
        away_team=str(row["away_team"]),
        kickoff_time=int(row["kickoff_time"]),
        status=str(row["status"]),
    )


async def load_due_fixtures(now: int) -> list[FootballFixture]:
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT
                provider_id,
                competition,
                competition_name,
                home_team,
                away_team,
                kickoff_time,
                status
            FROM football_fixtures
            WHERE status = ?
              AND alert_time IS NULL
              AND kickoff_time > ?
              AND kickoff_time <= ?
            ORDER BY kickoff_time, competition_name, home_team
            """,
            (SCHEDULED_STATUS, now, now + 360),
        ) as cursor:
            fixtures = [row_to_fixture(row) for row in await cursor.fetchall()]
    return [fixture for fixture in fixtures if is_tracked_fixture(fixture)]


async def load_next_fixtures(now: int) -> list[FootballFixture]:
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT
                provider_id,
                competition,
                competition_name,
                home_team,
                away_team,
                kickoff_time,
                status
            FROM football_fixtures
            WHERE status = ?
              AND kickoff_time > ?
            ORDER BY kickoff_time, competition_name, home_team
            """,
            (SCHEDULED_STATUS, now),
        ) as cursor:
            fixtures = [row_to_fixture(row) for row in await cursor.fetchall()]

    tracked_fixtures = [fixture for fixture in fixtures if is_tracked_fixture(fixture)]
    if not tracked_fixtures:
        return []
    kickoff_time = tracked_fixtures[0].kickoff_time
    return [
        fixture for fixture in tracked_fixtures if fixture.kickoff_time == kickoff_time
    ]


async def verify_fixtures(fixtures: list[FootballFixture]) -> set[str]:
    candidate_ids = {fixture.provider_id for fixture in fixtures}
    fixtures = [
        fixture
        for fixture in await load_due_fixtures(utc_timestamp())
        if fixture.provider_id in candidate_ids
    ]
    verified_ids: set[str] = set()
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for fixture in fixtures:
            try:
                current_fixture = await fetch_fixture(session, fixture)
            except (aiohttp.ClientError, TimeoutError, ValueError):
                logger.exception(
                    "Could not verify football fixture %s", fixture.provider_id
                )
                continue
            await store_fixtures([current_fixture])
            verified_ids.add(current_fixture.provider_id)
    return verified_ids


async def fetch_fixture_odds(
    session: aiohttp.ClientSession,
    fixture: FootballFixture,
) -> tuple[str, MatchOdds | None]:
    odds_fixture = OddsFixture(
        competition=fixture.competition,
        home_team=fixture.home_team,
        away_team=fixture.away_team,
        kickoff=datetime.datetime.fromtimestamp(
            fixture.kickoff_time,
            datetime.UTC,
        ),
        home_tracked=fixture.home_team in TRACKED_TEAMS,
        away_tracked=fixture.away_team in TRACKED_TEAMS,
    )
    try:
        odds = await fetch_match_odds(session, odds_fixture)
    except (aiohttp.ClientError, TimeoutError, ValueError, KeyError):
        logger.exception(
            "Could not fetch Polymarket odds for fixture %s",
            fixture.provider_id,
        )
        odds = None
    return fixture.provider_id, odds


async def load_fixture_odds(
    fixtures: list[FootballFixture],
) -> dict[str, MatchOdds]:
    if not fixtures:
        return {}
    timeout = aiohttp.ClientTimeout(total=ODDS_LOOKUP_TIMEOUT_SECONDS)
    headers = {"User-Agent": "SuperSeriousBot/Football-Odds"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        tasks = [
            asyncio.create_task(fetch_fixture_odds(session, fixture))
            for fixture in fixtures
        ]
        done, pending = await asyncio.wait(
            tasks,
            timeout=ODDS_LOOKUP_TIMEOUT_SECONDS,
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    if pending:
        logger.warning("Timed out fetching odds for %s fixtures", len(pending))
    odds_by_fixture: dict[str, MatchOdds] = {}
    for task in done:
        try:
            provider_id, odds = task.result()
        except Exception:
            logger.exception("Polymarket odds lookup task failed")
            continue
        if odds is not None:
            odds_by_fixture[provider_id] = odds
    return odds_by_fixture


async def mark_fixtures_alerted(fixtures: list[FootballFixture], now: int) -> None:
    async with get_db() as conn:
        await conn.executemany(
            """
            UPDATE football_fixtures
            SET alert_time = ?, update_time = CURRENT_TIMESTAMP
            WHERE provider_id = ?
              AND kickoff_time = ?
              AND status = ?
              AND alert_time IS NULL
            """,
            [
                (now, fixture.provider_id, fixture.kickoff_time, SCHEDULED_STATUS)
                for fixture in fixtures
            ],
        )


async def load_alert_chats() -> list[int]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT DISTINCT chat_id FROM football_alert_members ORDER BY chat_id"
        ) as cursor:
            return [int(row["chat_id"]) for row in await cursor.fetchall()]


def member_mention(member: AlertMember) -> str:
    return (
        f'<a href="tg://user?id={member.user_id}">'
        f"{html.escape(member.display_name)}</a>"
    )


async def load_pending_member_groups(
    fixtures: list[FootballFixture],
    chat_id: int,
) -> list[tuple[list[FootballFixture], list[AlertMember]]]:
    placeholders = ", ".join("?" for _ in fixtures)
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT user_id, display_name
            FROM football_alert_members
            WHERE chat_id = ?
            ORDER BY create_time, user_id
            """,
            (chat_id,),
        ) as member_cursor:
            members = [
                AlertMember(int(row["user_id"]), str(row["display_name"]))
                for row in await member_cursor.fetchall()
            ]
        async with conn.execute(
            f"""
            SELECT provider_id, kickoff_time, user_id
            FROM football_alert_deliveries
            WHERE chat_id = ?
              AND provider_id IN ({placeholders})
            """,
            (chat_id, *(fixture.provider_id for fixture in fixtures)),
        ) as delivery_cursor:
            delivered = {
                (
                    str(row["provider_id"]),
                    int(row["kickoff_time"]),
                    int(row["user_id"]),
                )
                for row in await delivery_cursor.fetchall()
            }

    groups: dict[tuple[FootballFixture, ...], list[AlertMember]] = {}
    for member in members:
        pending = tuple(
            fixture
            for fixture in fixtures
            if (fixture.provider_id, fixture.kickoff_time, member.user_id)
            not in delivered
        )
        if pending:
            groups.setdefault(pending, []).append(member)
    return [(list(pending), members) for pending, members in groups.items()]


async def record_deliveries(
    fixtures: list[FootballFixture],
    chat_id: int,
    members: list[AlertMember],
    delivery_time: int,
) -> None:
    async with get_db() as conn:
        await conn.executemany(
            """
            INSERT INTO football_alert_deliveries (
                provider_id,
                kickoff_time,
                chat_id,
                user_id,
                delivery_time
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (provider_id, kickoff_time, chat_id, user_id) DO NOTHING
            """,
            [
                (
                    fixture.provider_id,
                    fixture.kickoff_time,
                    chat_id,
                    member.user_id,
                    delivery_time,
                )
                for fixture in fixtures
                for member in members
            ],
        )


def fixture_alert_text(
    fixtures: list[FootballFixture],
    odds_by_fixture: dict[str, MatchOdds],
) -> str:
    lines = ["⚽ <b>Kickoff in five minutes</b>"]
    ordered = sorted(
        fixtures,
        key=lambda fixture: (
            COMPETITION_ORDER[fixture.competition_name],
            fixture.home_team,
            fixture.away_team,
        ),
    )
    for competition_name, competition_fixtures in groupby(
        ordered, key=lambda fixture: fixture.competition_name
    ):
        lines.extend(("", f"<b>{html.escape(competition_name)}</b>"))
        lines.extend(
            f"• {html.escape(fixture.home_team)} vs {html.escape(fixture.away_team)}"
            for fixture in competition_fixtures
        )
    fixtures_with_odds = [
        fixture for fixture in ordered if fixture.provider_id in odds_by_fixture
    ]
    if fixtures_with_odds:
        lines.extend(("", "📊 <b>Polymarket odds</b>"))
        for fixture in fixtures_with_odds:
            odds = odds_by_fixture[fixture.provider_id]
            market_url = html.escape(event_url(odds), quote=True)
            lines.append(
                f"• {html.escape(fixture.home_team)} <b>{odds.home:.0%}</b> · "
                f"Draw <b>{odds.draw:.0%}</b> · "
                f"{html.escape(fixture.away_team)} <b>{odds.away:.0%}</b> · "
                f'<a href="{market_url}">market</a>'
            )
    return "\n".join(lines)


def next_fixture_text(fixtures: list[FootballFixture]) -> str:
    kickoff_time = fixtures[0].kickoff_time
    fallback_time = datetime.datetime.fromtimestamp(
        kickoff_time, datetime.UTC
    ).strftime("%Y-%m-%d %H:%M UTC")
    lines = ["⚽ <b>Next Big Six match</b>"]
    ordered = sorted(
        fixtures,
        key=lambda fixture: (
            COMPETITION_ORDER[fixture.competition_name],
            fixture.home_team,
            fixture.away_team,
        ),
    )
    for competition_name, competition_fixtures in groupby(
        ordered, key=lambda fixture: fixture.competition_name
    ):
        lines.extend(("", f"<b>{html.escape(competition_name)}</b>"))
        lines.extend(
            f"• {html.escape(fixture.home_team)} vs {html.escape(fixture.away_team)}"
            for fixture in competition_fixtures
        )
    lines.extend(
        (
            "",
            f'Kickoff <tg-time unix="{kickoff_time}" format="r">'
            f"{fallback_time}</tg-time>",
        )
    )
    return "\n".join(lines)


async def send_fixture_alerts(
    context: ContextTypes.DEFAULT_TYPE,
    fixtures: list[FootballFixture],
    odds_by_fixture: dict[str, MatchOdds],
    delivery_time: int,
) -> bool:
    all_delivered = True
    for chat_id in await load_alert_chats():
        groups = await load_pending_member_groups(fixtures, chat_id)
        for pending_fixtures, members in groups:
            alert_text = fixture_alert_text(pending_fixtures, odds_by_fixture)
            for index in range(0, len(members), MENTIONS_PER_MESSAGE):
                member_chunk = members[index : index + MENTIONS_PER_MESSAGE]
                mention_text = " ".join(map(member_mention, member_chunk))
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"{alert_text}\n\n{mention_text}",
                        parse_mode=ParseMode.HTML,
                        reply_markup=football_keyboard(),
                        link_preview_options=LinkPreviewOptions(is_disabled=True),
                    )
                except TelegramError:
                    logger.exception(
                        "Could not send football alert to chat %s", chat_id
                    )
                    all_delivered = False
                    continue
                await record_deliveries(
                    pending_fixtures,
                    chat_id,
                    member_chunk,
                    delivery_time,
                )
    return all_delivered


async def sync_football_fixtures_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await sync_football_fixtures()


async def worker_football_alerts(context: ContextTypes.DEFAULT_TYPE) -> None:
    async with FIXTURE_UPDATE_LOCK:
        now = utc_timestamp()
        due_fixtures = await load_due_fixtures(now)
        if not due_fixtures:
            return

        verified_ids = await verify_fixtures(due_fixtures)
        now = utc_timestamp()
        current_due_fixtures = [
            fixture
            for fixture in await load_due_fixtures(now)
            if fixture.provider_id in verified_ids
        ]
        odds_by_fixture = await load_fixture_odds(current_due_fixtures)
        for _, slot in groupby(
            current_due_fixtures, key=lambda fixture: fixture.kickoff_time
        ):
            fixtures = list(slot)
            if await send_fixture_alerts(
                context,
                fixtures,
                odds_by_fixture,
                now,
            ):
                await mark_fixtures_alerted(fixtures, now)


@command(
    triggers=["next"],
    usage="/next",
    example="/next",
    description="Show the countdown to the next Big Six match.",
)
async def next_match(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return

    fixtures = await load_next_fixtures(utc_timestamp())
    if not fixtures:
        await message.reply_text("No upcoming Big Six matches found.")
        return

    await message.reply_text(
        next_fixture_text(fixtures),
        parse_mode=ParseMode.HTML,
    )


@command(
    triggers=["football"],
    usage="/football",
    example="/football",
    description="Join five-minute Big Six football alerts for this group.",
)
async def football(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not update.effective_chat or not update.effective_user:
        return
    if update.effective_chat.type == "private":
        await message.reply_text("Football alerts can only be used in group chats.")
        return

    async with get_db() as conn:
        await conn.execute(
            """
            INSERT INTO football_alert_members (chat_id, user_id, display_name)
            VALUES (?, ?, ?)
            ON CONFLICT (chat_id, user_id) DO UPDATE SET
                display_name = excluded.display_name
            """,
            (
                update.effective_chat.id,
                update.effective_user.id,
                update.effective_user.full_name,
            ),
        )

    await message.reply_text(
        "⚽ <b>Football alerts enabled</b>\n\n"
        "You'll be tagged five minutes before Arsenal, Chelsea, Liverpool, "
        "Manchester City, Manchester United and Tottenham Hotspur matches in "
        "the Premier League, Champions League and FA Cup.",
        parse_mode=ParseMode.HTML,
        reply_markup=football_keyboard(),
    )


async def football_button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = get_message(update)
    query = update.callback_query
    if not message or not query or not query.data:
        return

    action = query.data.removeprefix("fb:")
    if action == "join":
        async with get_db() as conn:
            await conn.execute(
                """
                INSERT INTO football_alert_members (chat_id, user_id, display_name)
                VALUES (?, ?, ?)
                ON CONFLICT (chat_id, user_id) DO UPDATE SET
                    display_name = excluded.display_name
                """,
                (message.chat_id, query.from_user.id, query.from_user.full_name),
            )
        await query.answer("Joined football alerts.")
        return
    if action == "leave":
        async with get_db() as conn:
            await conn.execute(
                """
                DELETE FROM football_alert_members
                WHERE chat_id = ? AND user_id = ?
                """,
                (message.chat_id, query.from_user.id),
            )
        await query.answer("Left football alerts.")
        return

    await query.answer("Invalid football alert action.")
