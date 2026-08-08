import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
import logging
import asyncio
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ============================================================
# CONFIG
# ============================================================

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

PRODUCT_URL = "https://kojiesan.in/product/skin-lightening-soap-135g/"
PRODUCT_NAME = "Kojie San Skin Lightening Soap 135g"

CHECK_INTERVAL_MINUTES = 5

STATE_FILE = Path(__file__).parent / "stock_state.txt"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

log = logging.getLogger("stock_bot")


# ============================================================
# STOCK CHECKER
# ============================================================

def check_stock(url: str) -> bool | None:
    """
    Returns:
        True  = In stock
        False = Out of stock
        None  = Could not determine
    """

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

    except requests.RequestException as e:
        log.warning(f"Failed to fetch product page: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    # --------------------------------------------------------
    # Signal 1: WooCommerce stock element
    # --------------------------------------------------------

    stock_tag = soup.find("p", class_="stock")

    if stock_tag:
        text = stock_tag.get_text(" ", strip=True).lower()

        if "out of stock" in text:
            return False

        if "in stock" in text:
            return True

    # --------------------------------------------------------
    # Signal 2: Product page text
    # --------------------------------------------------------

    page_text = soup.get_text(" ", strip=True).lower()

    if "out of stock" in page_text:
        return False

    # --------------------------------------------------------
    # Signal 3: Add to cart button
    # --------------------------------------------------------

    add_to_cart = soup.find(
        class_="single_add_to_cart_button"
    )

    if add_to_cart:

        classes = add_to_cart.get("class", [])

        if "disabled" not in classes:
            return True

    log.warning(
        "Could not determine stock status from product page."
    )

    return None


# ============================================================
# STATE
# ============================================================

def load_last_status() -> bool | None:

    if not STATE_FILE.exists():
        return None

    try:
        value = STATE_FILE.read_text().strip()

        if value == "1":
            return True

        if value == "0":
            return False

    except OSError:
        pass

    return None


def save_last_status(in_stock: bool):

    try:
        STATE_FILE.write_text(
            "1" if in_stock else "0"
        )

    except OSError as e:
        log.warning(f"Could not save stock state: {e}")


# ============================================================
# TELEGRAM
# ============================================================

async def send_telegram_message(
    application,
    text: str
):

    if not TELEGRAM_CHAT_ID:
        log.warning(
            "TELEGRAM_CHAT_ID is not configured."
        )
        return

    try:

        await application.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=text,
            disable_web_page_preview=False,
        )

        log.info("Telegram message sent.")

    except Exception as e:

        log.error(
            f"Failed to send Telegram message: {e}"
        )


# ============================================================
# STOCK CHECK
# ============================================================

async def perform_stock_check(
    application,
    notify=True
):

    current = await asyncio.to_thread(
        check_stock,
        PRODUCT_URL
    )

    if current is None:
        return None

    previous = load_last_status()

    status = (
        "IN STOCK"
        if current
        else "OUT OF STOCK"
    )

    log.info(
        f"{PRODUCT_NAME} is currently: {status}"
    )

    # Product changed from OUT OF STOCK to IN STOCK
    if (
        current is True
        and previous is False
        and notify
    ):

        message = (
            "🚨 PRODUCT BACK IN STOCK!\n\n"
            f"🧴 {PRODUCT_NAME}\n\n"
            "✅ Available now!\n\n"
            f"🛒 {PRODUCT_URL}"
        )

        await send_telegram_message(
            application,
            message
        )

    save_last_status(current)

    return current


# ============================================================
# TELEGRAM COMMANDS
# ============================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id

    current = await asyncio.to_thread(
        check_stock,
        PRODUCT_URL
    )

    if current is True:
        status = "🟢 IN STOCK"
    elif current is False:
        status = "🔴 OUT OF STOCK"
    else:
        status = "⚠️ UNKNOWN"

    message = (
        "👋 Welcome to ChkStock!\n\n"
        f"🧴 Product:\n{PRODUCT_NAME}\n\n"
        f"📦 Status: {status}\n\n"
        f"⏱ Checking every {CHECK_INTERVAL_MINUTES} minutes.\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/status - Check stock now\n"
        "/id - Show your Chat ID"
    )

    await update.message.reply_text(message)

    log.info(
        f"/start received from Chat ID: {chat_id}"
    )


async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🔎 Checking product stock..."
    )

    current = await asyncio.to_thread(
        check_stock,
        PRODUCT_URL
    )

    if current is True:

        message = (
            "🟢 IN STOCK!\n\n"
            f"🧴 {PRODUCT_NAME}\n\n"
            f"🛒 {PRODUCT_URL}"
        )

    elif current is False:

        message = (
            "🔴 OUT OF STOCK\n\n"
            f"🧴 {PRODUCT_NAME}\n\n"
            "I'll keep checking automatically."
        )

    else:

        message = (
            "⚠️ Could not determine stock status.\n\n"
            "Please try again later."
        )

    await update.message.reply_text(message)


async def id_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id

    await update.message.reply_text(
        f"Your Telegram Chat ID is:\n\n{chat_id}"
    )

    log.info(
        f"Chat ID: {chat_id}"
    )


# ============================================================
# BACKGROUND STOCK WATCHER
# ============================================================

async def stock_watcher(application):

    log.info(
        f"Starting stock watcher for: {PRODUCT_NAME}"
    )

    log.info(
        f"Checking every {CHECK_INTERVAL_MINUTES} minutes."
    )

    while True:

        try:

            await perform_stock_check(
                application,
                notify=True
            )

        except Exception as e:

            log.exception(
                f"Stock checker error: {e}"
            )

        await asyncio.sleep(
            CHECK_INTERVAL_MINUTES * 60
        )


# ============================================================
# START BOT
# ============================================================

async def post_init(application):

    application.create_task(
        stock_watcher(application)
    )


def main():

    if not TELEGRAM_BOT_TOKEN:

        raise ValueError(
            "TELEGRAM_BOT_TOKEN is missing from .env"
        )

    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Telegram commands
    application.add_handler(
        CommandHandler(
            "start",
            start_command
        )
    )

    application.add_handler(
        CommandHandler(
            "status",
            status_command
        )
    )

    application.add_handler(
        CommandHandler(
            "id",
            id_command
        )
    )

    log.info("Telegram bot is starting...")

    application.run_polling()


if __name__ == "__main__":
    main()