from __future__ import annotations

import asyncio
import datetime
import importlib
import os
import unittest
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import libsql

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("QUOTE_CHANNEL_ID", "1")
os.environ.setdefault("TURSO_DATABASE_URL", ":memory:")
os.environ.setdefault("TURSO_AUTH_TOKEN", "test-token")

db = importlib.import_module("config.db")
football = importlib.import_module("commands.football")
migrate = importlib.import_module("migrate")


def fixture(
    provider_id: str,
    kickoff_time: int,
    *,
    competition: str = "eng.1",
    competition_name: str = "Premier League",
    home_team: str = "Arsenal",
    away_team: str = "Coventry City",
) -> football.FootballFixture:
    return football.FootballFixture(
        provider_id=provider_id,
        competition=competition,
        competition_name=competition_name,
        home_team=home_team,
        away_team=away_team,
        kickoff_time=kickoff_time,
        status=football.SCHEDULED_STATUS,
    )


class FootballTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        raw_connection = libsql.connect(":memory:", autocommit=True)
        migration = migrate.load_migration(
            Path("migrations/20260712000000_add_football_alerts.py")
        )
        migration.upgrade(raw_connection)
        self.connection = db.TursoConnection(raw_connection)

        @asynccontextmanager
        async def test_db():
            yield self.connection

        self.db_patch = patch.object(football, "get_db", test_db)
        self.db_patch.start()
        self.fetch_match_odds = AsyncMock(return_value=None)
        self.odds_patch = patch.object(
            football,
            "fetch_match_odds",
            self.fetch_match_odds,
        )
        self.odds_patch.start()

    async def asyncTearDown(self) -> None:
        self.odds_patch.stop()
        self.db_patch.stop()
        await self.connection.close()

    def test_schedule_range_includes_next_season(self) -> None:
        self.assertEqual(
            football.season_date_ranges(
                datetime.datetime(2027, 6, 15, tzinfo=datetime.UTC)
            ),
            (
                (datetime.date(2026, 7, 1), datetime.date(2027, 6, 30)),
                (datetime.date(2027, 7, 1), datetime.date(2028, 6, 30)),
            ),
        )

    def test_parse_scoreboard_event(self) -> None:
        parsed = football.parse_scoreboard_event(
            {
                "id": "401879301",
                "competitions": [
                    {
                        "date": "2026-08-21T19:00Z",
                        "status": {"type": {"name": "STATUS_SCHEDULED"}},
                        "competitors": [
                            {
                                "homeAway": "home",
                                "team": {"displayName": "Arsenal"},
                            },
                            {
                                "homeAway": "away",
                                "team": {"displayName": "Coventry City"},
                            },
                        ],
                    }
                ],
            },
            football.COMPETITIONS[0],
        )

        self.assertEqual(parsed.provider_id, "401879301")
        self.assertEqual(parsed.home_team, "Arsenal")
        self.assertEqual(parsed.away_team, "Coventry City")
        self.assertEqual(parsed.kickoff_time, 1787338800)
        self.assertEqual(parsed.status, football.SCHEDULED_STATUS)

    def test_only_big_six_fixtures_are_tracked(self) -> None:
        self.assertTrue(
            football.is_tracked_fixture(
                fixture("tracked", 1_800_000_000, away_team="Everton")
            )
        )
        self.assertFalse(
            football.is_tracked_fixture(
                fixture(
                    "untracked",
                    1_800_000_000,
                    home_team="Everton",
                    away_team="Fulham",
                )
            )
        )
        self.assertFalse(
            football.is_tracked_fixture(
                fixture(
                    "unsupported-competition",
                    1_800_000_000,
                    competition="eng.league_cup",
                    competition_name="League Cup",
                )
            )
        )

    async def test_changed_kickoff_resets_alert(self) -> None:
        original = fixture("match-1", 1_800_000_000)
        await football.store_fixtures([original])
        await self.connection.execute(
            "UPDATE football_fixtures SET alert_time = 123 WHERE provider_id = ?",
            (original.provider_id,),
        )

        await football.store_fixtures(
            [replace(original, kickoff_time=original.kickoff_time + 3600)]
        )

        async with self.connection.execute(
            "SELECT kickoff_time, alert_time FROM football_fixtures WHERE provider_id = ?",
            (original.provider_id,),
        ) as cursor:
            row = await cursor.fetchone()
        self.assertEqual(row["kickoff_time"], original.kickoff_time + 3600)
        self.assertIsNone(row["alert_time"])

    async def test_next_fixtures_returns_every_match_at_earliest_kickoff(
        self,
    ) -> None:
        now = 1_800_000_000
        fixtures = [
            fixture("later", now + 7200),
            fixture("next-1", now + 3600),
            fixture(
                "next-2",
                now + 3600,
                competition="uefa.champions",
                competition_name="Champions League",
                home_team="Real Madrid",
                away_team="Liverpool",
            ),
            fixture(
                "untracked",
                now + 1800,
                home_team="Everton",
                away_team="Fulham",
            ),
        ]
        await football.store_fixtures(fixtures)

        next_fixtures = await football.load_next_fixtures(now)

        self.assertEqual(
            [item.provider_id for item in next_fixtures],
            ["next-2", "next-1"],
        )

    async def test_next_command_shows_live_countdown(self) -> None:
        kickoff_time = 1_800_003_600
        fixtures = [
            fixture("next-1", kickoff_time),
            fixture(
                "next-2",
                kickoff_time,
                competition="uefa.champions",
                competition_name="Champions League",
                home_team="Real Madrid",
                away_team="Liverpool",
            ),
        ]
        await football.store_fixtures(fixtures)
        message = SimpleNamespace(reply_text=AsyncMock())

        with (
            patch.object(football, "get_message", return_value=message),
            patch.object(football, "utc_timestamp", return_value=1_800_000_000),
        ):
            await football.next_match(SimpleNamespace(), SimpleNamespace())

        message.reply_text.assert_awaited_once()
        sent = message.reply_text.await_args
        self.assertIn("Arsenal vs Coventry City", sent.args[0])
        self.assertIn("Real Madrid vs Liverpool", sent.args[0])
        self.assertIn(f'<tg-time unix="{kickoff_time}" format="r">', sent.args[0])
        self.assertIn("📊 <b>Polymarket odds</b>", sent.args[0])
        self.assertIn(
            "Arsenal vs Coventry City: not available yet",
            sent.args[0],
        )
        self.assertEqual(sent.kwargs["parse_mode"], football.ParseMode.HTML)
        self.assertTrue(sent.kwargs["link_preview_options"].is_disabled)

    async def test_next_command_handles_empty_schedule(self) -> None:
        message = SimpleNamespace(reply_text=AsyncMock())

        with patch.object(football, "get_message", return_value=message):
            await football.next_match(SimpleNamespace(), SimpleNamespace())

        message.reply_text.assert_awaited_once_with(
            "No upcoming Big Six matches found."
        )

    async def test_old_kickoff_delivery_cannot_finalize_rescheduled_fixture(
        self,
    ) -> None:
        original = fixture("match-1", 1_800_000_000)
        rescheduled = replace(original, kickoff_time=original.kickoff_time + 3600)
        await football.store_fixtures([original])
        await football.store_fixtures([rescheduled])

        await football.mark_fixtures_alerted([original], 1_799_999_700)

        async with self.connection.execute(
            "SELECT kickoff_time, alert_time FROM football_fixtures WHERE provider_id = ?",
            (original.provider_id,),
        ) as cursor:
            row = await cursor.fetchone()
        self.assertEqual(row["kickoff_time"], rescheduled.kickoff_time)
        self.assertIsNone(row["alert_time"])

    async def test_worker_groups_simultaneous_matches_and_claims_them(self) -> None:
        now = int(datetime.datetime.now(datetime.UTC).timestamp())
        fixtures = [
            fixture("match-1", now + 300),
            fixture(
                "match-2",
                now + 300,
                competition="uefa.champions",
                competition_name="Champions League",
                home_team="Real Madrid",
                away_team="Liverpool",
            ),
        ]
        await football.store_fixtures(fixtures)
        await self.connection.execute(
            """
            INSERT INTO football_alert_members (chat_id, user_id, display_name)
            VALUES (?, ?, ?)
            """,
            (-1001, 7, "Ayaan"),
        )
        bot = AsyncMock()
        bot.send_message.side_effect = lambda **_kwargs: self.assertTrue(
            football.FIXTURE_UPDATE_LOCK.locked()
        )
        context = SimpleNamespace(bot=bot)

        with patch.object(
            football,
            "verify_fixtures",
            AsyncMock(return_value={item.provider_id for item in fixtures}),
        ):
            await football.worker_football_alerts(context)

        bot.send_message.assert_awaited_once()
        sent = bot.send_message.await_args.kwargs
        self.assertEqual(sent["chat_id"], -1001)
        self.assertIn("<b>Premier League</b>", sent["text"])
        self.assertIn("Arsenal vs Coventry City", sent["text"])
        self.assertIn("<b>Champions League</b>", sent["text"])
        self.assertIn("Real Madrid vs Liverpool", sent["text"])
        self.assertIn("tg://user?id=7", sent["text"])
        self.assertNotIn("Polymarket odds", sent["text"])
        self.assertTrue(sent["link_preview_options"].is_disabled)

        async with self.connection.execute(
            "SELECT COUNT(*) AS count FROM football_fixtures WHERE alert_time IS NOT NULL"
        ) as cursor:
            row = await cursor.fetchone()
        self.assertEqual(row["count"], 2)
        async with self.connection.execute(
            "SELECT COUNT(*) AS count FROM football_alert_deliveries"
        ) as cursor:
            row = await cursor.fetchone()
        self.assertEqual(row["count"], 2)

    async def test_worker_suppresses_rescheduled_fixture(self) -> None:
        now = int(datetime.datetime.now(datetime.UTC).timestamp())
        stale_fixture = fixture("match-1", now + 300)
        current_fixture = replace(stale_fixture, kickoff_time=now + 3600)
        await football.store_fixtures([stale_fixture])
        bot = AsyncMock()
        context = SimpleNamespace(bot=bot)

        with patch.object(
            football,
            "fetch_fixture",
            AsyncMock(return_value=current_fixture),
        ):
            await football.worker_football_alerts(context)

        bot.send_message.assert_not_awaited()
        async with self.connection.execute(
            "SELECT kickoff_time, alert_time FROM football_fixtures WHERE provider_id = ?",
            (stale_fixture.provider_id,),
        ) as cursor:
            row = await cursor.fetchone()
        self.assertEqual(row["kickoff_time"], current_fixture.kickoff_time)
        self.assertIsNone(row["alert_time"])

    async def test_verification_does_not_restore_removed_fixture(self) -> None:
        now = int(datetime.datetime.now(datetime.UTC).timestamp())
        removed_fixture = fixture("removed", now + 300)
        fetch = AsyncMock()

        with (
            patch.object(football, "utc_timestamp", return_value=now),
            patch.object(football, "fetch_fixture", fetch),
        ):
            verified_ids = await football.verify_fixtures([removed_fixture])

        self.assertEqual(verified_ids, set())
        fetch.assert_not_awaited()

    async def test_worker_does_not_alert_after_verification_passes_kickoff(
        self,
    ) -> None:
        now = int(datetime.datetime.now(datetime.UTC).timestamp())
        due_fixture = fixture("match-1", now + 300)
        await football.store_fixtures([due_fixture])
        bot = AsyncMock()
        context = SimpleNamespace(bot=bot)

        with (
            patch.object(football, "utc_timestamp", side_effect=[now, now + 301]),
            patch.object(
                football,
                "verify_fixtures",
                AsyncMock(return_value={due_fixture.provider_id}),
            ),
        ):
            await football.worker_football_alerts(context)

        bot.send_message.assert_not_awaited()

    async def test_join_and_leave_buttons_update_membership(self) -> None:
        message = SimpleNamespace(chat_id=-1001)
        query = SimpleNamespace(
            data="fb:join",
            from_user=SimpleNamespace(id=7, full_name="Ayaan"),
            answer=AsyncMock(),
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace()

        with patch.object(football, "get_message", return_value=message):
            await football.football_button_handler(update, context)
            query.data = "fb:leave"
            await football.football_button_handler(update, context)

        self.assertEqual(
            [call.args[0] for call in query.answer.await_args_list],
            ["Joined football alerts.", "Left football alerts."],
        )
        async with self.connection.execute(
            "SELECT COUNT(*) AS count FROM football_alert_members"
        ) as cursor:
            row = await cursor.fetchone()
        self.assertEqual(row["count"], 0)

    async def test_mentions_do_not_require_bot_admin_access(self) -> None:
        self.assertEqual(
            football.member_mention(football.AlertMember(7, "Ayaan & Co")),
            '<a href="tg://user?id=7">Ayaan &amp; Co</a>',
        )

    def test_alert_text_includes_glanceable_polymarket_odds(self) -> None:
        match = fixture("match-1", 1_800_000_000)
        odds = football.MatchOdds(
            event_slug="epl-ars-cov-2026-08-21",
            home=0.62,
            draw=0.23,
            away=0.15,
        )

        text = football.fixture_alert_text([match], {match.provider_id: odds})

        self.assertIn("📊 <b>Polymarket odds</b>", text)
        self.assertIn(
            "Arsenal <b>62%</b> · Draw <b>23%</b> · Coventry City <b>15%</b>",
            text,
        )
        self.assertIn(
            'href="https://polymarket.com/event/epl-ars-cov-2026-08-21"',
            text,
        )

        next_text = football.next_fixture_text(
            [match],
            {match.provider_id: odds},
        )
        self.assertIn("📊 <b>Polymarket odds</b>", next_text)
        self.assertIn(
            "Arsenal <b>62%</b> · Draw <b>23%</b> · Coventry City <b>15%</b>",
            next_text,
        )

    async def test_odds_lookup_keeps_completed_results_on_timeout(self) -> None:
        fixtures = [
            fixture("fast", 1_800_000_000),
            fixture(
                "slow",
                1_800_000_000,
                home_team="Liverpool",
                away_team="Everton",
            ),
        ]
        odds = football.MatchOdds("epl-ars-cov-2026-08-21", 0.62, 0.23, 0.15)

        async def fetch(_session, odds_fixture):
            if odds_fixture.home_team == "Arsenal":
                return odds
            await asyncio.sleep(1)

        self.fetch_match_odds.side_effect = fetch
        with patch.object(football, "ODDS_LOOKUP_TIMEOUT_SECONDS", 0.01):
            result = await football.load_fixture_odds(fixtures)

        self.assertEqual(result, {"fast": odds})

    async def test_odds_task_failure_does_not_escape(self) -> None:
        self.fetch_match_odds.side_effect = RuntimeError("bad upstream data")

        result = await football.load_fixture_odds([fixture("match-1", 1_800_000_000)])

        self.assertEqual(result, {})

    async def test_worker_loads_odds_once_for_all_kickoff_slots(self) -> None:
        now = int(datetime.datetime.now(datetime.UTC).timestamp())
        fixtures = [
            fixture("match-1", now + 300),
            fixture(
                "match-2",
                now + 330,
                home_team="Liverpool",
                away_team="Everton",
            ),
        ]
        await football.store_fixtures(fixtures)
        odds_loader = AsyncMock(return_value={})

        with (
            patch.object(football, "load_fixture_odds", odds_loader),
            patch.object(
                football,
                "verify_fixtures",
                AsyncMock(return_value={item.provider_id for item in fixtures}),
            ),
        ):
            await football.worker_football_alerts(SimpleNamespace(bot=AsyncMock()))

        odds_loader.assert_awaited_once()
        self.assertEqual(
            [item.provider_id for item in odds_loader.await_args.args[0]],
            ["match-1", "match-2"],
        )

    async def test_failed_delivery_retries_without_resending_successful_chats(
        self,
    ) -> None:
        now = int(datetime.datetime.now(datetime.UTC).timestamp())
        due_fixture = fixture("match-1", now + 300)
        await football.store_fixtures([due_fixture])
        await self.connection.executemany(
            """
            INSERT INTO football_alert_members (chat_id, user_id, display_name)
            VALUES (?, ?, ?)
            """,
            [(-1001, 7, "Ayaan"), (-1002, 8, "Friend")],
        )
        bot = AsyncMock()
        bot.send_message.side_effect = [None, football.TelegramError("temporary")]
        context = SimpleNamespace(bot=bot)

        with patch.object(
            football,
            "verify_fixtures",
            AsyncMock(return_value={due_fixture.provider_id}),
        ):
            await football.worker_football_alerts(context)
        failed_chat_id = bot.send_message.await_args_list[-1].kwargs["chat_id"]

        async with self.connection.execute(
            "SELECT alert_time FROM football_fixtures WHERE provider_id = ?",
            (due_fixture.provider_id,),
        ) as cursor:
            row = await cursor.fetchone()
        self.assertIsNone(row["alert_time"])
        self.assertEqual(
            [
                fixture.provider_id
                for fixture in await football.load_due_fixtures(now + 120)
            ],
            [due_fixture.provider_id],
        )

        bot.send_message.reset_mock()
        bot.send_message.side_effect = None
        with patch.object(
            football,
            "verify_fixtures",
            AsyncMock(return_value={due_fixture.provider_id}),
        ):
            await football.worker_football_alerts(context)

        bot.send_message.assert_awaited_once()
        self.assertEqual(bot.send_message.await_args.kwargs["chat_id"], failed_chat_id)
        async with self.connection.execute(
            "SELECT alert_time FROM football_fixtures WHERE provider_id = ?",
            (due_fixture.provider_id,),
        ) as cursor:
            row = await cursor.fetchone()
        self.assertIsNotNone(row["alert_time"])

    async def test_retry_sends_only_fixtures_missing_for_chat(self) -> None:
        now = int(datetime.datetime.now(datetime.UTC).timestamp())
        delivered_fixture = fixture("match-1", now + 300)
        pending_fixture = fixture(
            "match-2",
            now + 300,
            competition="uefa.champions",
            competition_name="Champions League",
            home_team="Liverpool",
            away_team="Real Madrid",
        )
        fixtures = [delivered_fixture, pending_fixture]
        await football.store_fixtures(fixtures)
        await self.connection.execute(
            """
            INSERT INTO football_alert_members (chat_id, user_id, display_name)
            VALUES (?, ?, ?)
            """,
            (-1001, 7, "Ayaan"),
        )
        await football.record_deliveries(
            [delivered_fixture],
            -1001,
            [football.AlertMember(7, "Ayaan")],
            now - 60,
        )
        bot = AsyncMock()
        context = SimpleNamespace(bot=bot)

        delivered = await football.send_fixture_alerts(context, fixtures, {}, now)

        self.assertTrue(delivered)
        bot.send_message.assert_awaited_once()
        text = bot.send_message.await_args.kwargs["text"]
        self.assertNotIn("Arsenal vs Coventry City", text)
        self.assertIn("Liverpool vs Real Madrid", text)
        async with self.connection.execute(
            "SELECT provider_id FROM football_alert_deliveries ORDER BY provider_id"
        ) as cursor:
            rows = await cursor.fetchall()
        self.assertEqual(
            [row["provider_id"] for row in rows],
            ["match-1", "match-2"],
        )

    async def test_partial_member_chunk_failure_retries_only_failed_chunk(self) -> None:
        now = int(datetime.datetime.now(datetime.UTC).timestamp())
        due_fixture = fixture("match-1", now + 300)
        await football.store_fixtures([due_fixture])
        await self.connection.executemany(
            """
            INSERT INTO football_alert_members (chat_id, user_id, display_name)
            VALUES (?, ?, ?)
            """,
            [(-1001, user_id, f"User {user_id}") for user_id in range(1, 7)],
        )
        bot = AsyncMock()
        bot.send_message.side_effect = [None, football.TelegramError("temporary")]
        context = SimpleNamespace(bot=bot)

        delivered = await football.send_fixture_alerts(context, [due_fixture], {}, now)

        self.assertFalse(delivered)
        bot.send_message.reset_mock()
        bot.send_message.side_effect = None

        delivered = await football.send_fixture_alerts(
            context,
            [due_fixture],
            {},
            now + 60,
        )

        self.assertTrue(delivered)
        bot.send_message.assert_awaited_once()
        retry_text = bot.send_message.await_args.kwargs["text"]
        self.assertIn("User 6", retry_text)
        self.assertNotIn("User 1", retry_text)
        async with self.connection.execute(
            "SELECT COUNT(*) AS count FROM football_alert_deliveries"
        ) as cursor:
            row = await cursor.fetchone()
        self.assertEqual(row["count"], 6)

    async def test_sync_keeps_successful_competitions_when_one_fails(self) -> None:
        now = int(datetime.datetime.now(datetime.UTC).timestamp())

        async def fetch(_session, competition, _now):
            if competition.slug == "uefa.champions":
                raise football.aiohttp.ClientError("temporary")
            return [
                fixture(
                    competition.slug,
                    now + 300,
                    competition=competition.slug,
                    competition_name=competition.name,
                )
            ]

        with patch.object(football, "fetch_competition_fixtures", side_effect=fetch):
            synced = await football.sync_football_fixtures()

        self.assertEqual(synced, 2)
        async with self.connection.execute(
            "SELECT competition FROM football_fixtures ORDER BY competition"
        ) as cursor:
            rows = await cursor.fetchall()
        self.assertEqual(
            [row["competition"] for row in rows],
            ["eng.1", "eng.fa"],
        )

    async def test_sync_stores_only_big_six_fixtures(self) -> None:
        now = int(datetime.datetime.now(datetime.UTC).timestamp())

        async def fetch(_session, competition, _now):
            if competition.slug != "eng.1":
                return []
            return [
                fixture("tracked", now + 300),
                fixture(
                    "untracked",
                    now + 300,
                    home_team="Everton",
                    away_team="Fulham",
                ),
            ]

        with patch.object(football, "fetch_competition_fixtures", side_effect=fetch):
            synced = await football.sync_football_fixtures()

        self.assertEqual(synced, 1)
        async with self.connection.execute(
            "SELECT provider_id FROM football_fixtures"
        ) as cursor:
            rows = await cursor.fetchall()
        self.assertEqual([row["provider_id"] for row in rows], ["tracked"])

    async def test_sync_removes_fixtures_missing_from_successful_snapshot(
        self,
    ) -> None:
        now = int(datetime.datetime.now(datetime.UTC).timestamp())
        await football.store_fixtures([fixture("stale", now + 300)])

        async def fetch(_session, competition, _now):
            if competition.slug != "eng.1":
                return []
            return [fixture("replacement", now + 600)]

        with patch.object(football, "fetch_competition_fixtures", side_effect=fetch):
            await football.sync_football_fixtures()

        async with self.connection.execute(
            "SELECT provider_id FROM football_fixtures ORDER BY provider_id"
        ) as cursor:
            rows = await cursor.fetchall()
        self.assertEqual([row["provider_id"] for row in rows], ["replacement"])
