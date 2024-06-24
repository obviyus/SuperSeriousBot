import aiohttp
from bs4 import BeautifulSoup
from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes

from config.db import sqlite_conn
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
    cursor = sqlite_conn.cursor()
    cursor.execute(
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


@triggers(["enable_steam_offers"])
@usage("/enable_steam_offers")
@description("Enable notifications for free Steam games.")
@example("/enable_steam_offers")
async def enable_steam_offers(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Enable full text search in the current chat.
    """
    # Check if user is a moderator
    if update.message.chat.type != ChatType.PRIVATE:
        chat_admins = await context.bot.get_chat_administrators(update.message.chat_id)
        if not update.message.from_user.id in [admin.user.id for admin in chat_admins]:
            await update.message.reply_text("You are not a moderator.")
            return

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO group_settings (chat_id, steam_offers) VALUES (?, 1)
        ON CONFLICT(chat_id) DO UPDATE SET steam_offers = 1;
        """,
        (update.message.chat_id,),
    )

    await update.message.reply_text("Steam free game notifications enabled.")


async def offer_worker(context: ContextTypes.DEFAULT_TYPE):
    offers = await fetch_offers()
    if not offers:
        return

    cursor = sqlite_conn.cursor()
    notify = []

    for offer in offers:
        # Check if this game_id has already been posted this month
        cursor.execute(
            """
            SELECT * FROM steam_offers WHERE game_id = ? AND create_time >= DATETIME('now', '-1 month');
            """,
            (offer["id"],),
        )

        if cursor.fetchone():
            continue

        await store_offer(offer)
        notify.append(offer)

    if not notify:
        return

    cursor.execute(
        """
        SELECT chat_id FROM group_settings WHERE steam_offers = 1;
        """
    )

    groups = cursor.fetchall()
    for group in groups:
        message = "🎮 New free Steam games available:\n\n"

        for offer in notify:
            message += (
                f"<a href='{offer['url']}'>{offer['name']}</a>\n"
                f"Release date: {offer['release_date']}\n"
                f"Review score: {offer['review_score']}\n"
                f"Original price: {offer['original_price']}\n"
                f"Final price: {offer['final_price']}\n"
                f"Discount: {offer['discount']}\n\n"
            )

        await context.bot.send_message(
            group["chat_id"], message, parse_mode=ParseMode.HTML
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(fetch_offers(None))
