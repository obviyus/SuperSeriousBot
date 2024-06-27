import asyncio

import aiohttp
from bs4 import BeautifulSoup
from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes

from config.db import get_db
from utils.decorators import description, example, triggers, usage

STEAM_PAGE_URL = "https://store.steampowered.com/search/?maxprice=free&specials=1"


async def fetch_offers() -> list[dict[str, str]] | None:
    """
    Check for Steam offers with additional details.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(
            STEAM_PAGE_URL, headers={"User-Agent": "SuperSeriousBot"}
        ) as response:
            if response.status != 200:
                return

            text = await response.text()
            soup = BeautifulSoup(text, "html.parser")
            offers = []

        search_results = soup.find("div", {"id": "search_resultsRows"})
        if not search_results:
            return offers

        for game in search_results.find_all("a", class_="search_result_row"):
            name_elem = game.find("span", class_="title")
            name = name_elem.text.strip() if name_elem else "Unknown"
            url = game.get("href", "")
            id = game.get("data-ds-appid", "")

            # Extract release date
            release_date_elem = game.find("div", class_="search_released")
            release_date = (
                release_date_elem.text.strip() if release_date_elem else "Unknown"
            )

            # Extract review score
            review_elem = game.find("span", class_="search_review_summary")
            review_score = (
                review_elem.get("data-tooltip-html", "").split("<br>")[0]
                if review_elem
                else "Unknown"
            )

            # Extract pricing information
            price_elem = game.find("div", class_="search_price_discount_combined")
            if price_elem:
                original_price_elem = price_elem.find(
                    "div", class_="discount_original_price"
                )
                original_price = (
                    original_price_elem.text.strip() if original_price_elem else "N/A"
                )

                final_price_elem = price_elem.find("div", class_="discount_final_price")
                final_price = (
                    final_price_elem.text.strip() if final_price_elem else "N/A"
                )

                discount_pct_elem = price_elem.find("div", class_="discount_pct")
                discount = discount_pct_elem.text.strip() if discount_pct_elem else "0%"
            else:
                original_price = final_price = discount = "N/A"

            if discount != "-100%":
                continue

            offers.append(
                {
                    "name": name,
                    "url": url,
                    "id": id,
                    "release_date": release_date,
                    "review_score": review_score,
                    "original_price": original_price,
                    "final_price": final_price,
                    "discount": discount,
                }
            )

    return offers if offers else None


async def store_offer(offer: dict[str, str]):
    """
    Store offers in the database.
    """
    async with get_db(write=True) as conn:
        await conn.execute(
            """
            INSERT INTO steam_offers (game_id, name, url, release_date, review_score, original_price, final_price, discount)          
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                offer["id"],
                offer["name"],
                offer["url"],
                offer["release_date"],
                offer["review_score"],
                offer["original_price"],
                offer["final_price"],
                offer["discount"],
            ),
        )
        await conn.commit()


@triggers(["enable_steam_offers"])
@usage("/enable_steam_offers")
@description("Enable notifications for free Steam games.")
@example("/enable_steam_offers")
async def enable_steam_offers(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Enable notifications for free Steam games.
    """
    # Check if user is a moderator
    if update.message.chat.type != ChatType.PRIVATE:
        chat_admins = await context.bot.get_chat_administrators(update.message.chat_id)
        if update.message.from_user.id not in [admin.user.id for admin in chat_admins]:
            await update.message.reply_text(
                "You are not authorized to use this command."
            )
            return

    async with get_db(write=True) as conn:
        await conn.execute(
            """
            INSERT INTO group_settings (chat_id, steam_offers) VALUES (?, 1)
            ON CONFLICT(chat_id) DO UPDATE SET steam_offers = 1;
            """,
            (update.message.chat_id,),
        )
        await conn.commit()

    await update.message.reply_text("Steam free game notifications enabled.")


async def offer_worker(context: ContextTypes.DEFAULT_TYPE):
    offers = await fetch_offers()
    if not offers:
        return

    async with get_db() as conn:
        notify = []

        for offer in offers:
            async with conn.execute(
                # Check if the offer has been notified within the last month
                """
                SELECT * FROM steam_offers WHERE game_id = ? AND notified = 1 AND create_time > datetime('now', '-1 month');
                """,
                (offer["id"],),
            ) as cursor:
                if await cursor.fetchone():
                    continue

            await store_offer(offer)
            notify.append(offer)

        if not notify:
            return

        async with conn.execute(
            """
            SELECT chat_id FROM group_settings WHERE steam_offers = 1;
            """
        ) as cursor:
            groups = await cursor.fetchall()

    message = "🎮 New Free Steam Games Available! 🎉\n\n"

    for offer in notify:
        message += (
            f"🏷️ <b><a href='{offer['url']}'>{offer['name']}</a></b>\n"
            f"📅 Release: {offer['release_date'] or 'N/A'}\n"
            f"⭐ Rating: {offer['review_score'] or 'N/A'}\n"
            f"💰 Price: <s>{offer['original_price'] or 'N/A'}</s> → {offer['final_price'] or 'FREE'}\n"
            f"🏷️ Discount: {offer['discount'] or 'N/A'}\n"
            f"──────────────────\n\n"
        )

    message = message.strip()

    tasks = []
    for group in groups:
        tasks.append(
            context.bot.send_message(
                group["chat_id"], message, parse_mode=ParseMode.HTML
            )
        )

    await asyncio.gather(*tasks)

    async with get_db(write=True) as conn:
        for offer in notify:
            await conn.execute(
                """
                UPDATE steam_offers SET notified = 1 WHERE game_id = ?;
                """,
                (offer["id"],),
            )
        await conn.commit()
