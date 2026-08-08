import os
import json
import logging
from pathlib import Path

import requests
from bs4 import BeautifulSoup


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

PRODUCT_URL = "https://kojiesan.in/product/skin-lightening-soap-135g/"
PRODUCT_NAME = "Kojie San Skin Lightening Soap 135g"

STATE_FILE = Path("stock_state.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

log = logging.getLogger("stock-checker")


def check_stock():
    try:
        response = requests.get(
            PRODUCT_URL,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

    except requests.RequestException as error:
        log.error(f"Could not fetch product page: {error}")
        return None

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    # WooCommerce stock element
    stock_tag = soup.find(
        "p",
        class_="stock"
    )

    if stock_tag:
        text = stock_tag.get_text(
            " ",
            strip=True
        ).lower()

        if "out of stock" in text:
            return False

        if "in stock" in text:
            return True

    # Add to cart button
    add_to_cart = soup.find(
        class_="single_add_to_cart_button"
    )

    if add_to_cart:
        classes = add_to_cart.get(
            "class",
            []
        )

        if "disabled" not in classes:
            return True

    # Fallback
    page_text = soup.get_text(
        " ",
        strip=True
    ).lower()

    if "out of stock" in page_text:
        return False

    log.warning(
        "Could not determine product stock."
    )

    return None


def load_previous_status():

    if not STATE_FILE.exists():
        return None

    try:
        data = json.loads(
            STATE_FILE.read_text()
        )

        return data.get("in_stock")

    except Exception:
        return None


def save_status(status):

    STATE_FILE.write_text(
        json.dumps({
            "in_stock": status
        })
    )


def send_telegram_message(message):

    if not TELEGRAM_BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN is missing.")
        return

    if not TELEGRAM_CHAT_ID:
        log.error("TELEGRAM_CHAT_ID is missing.")
        return

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    try:

        response = requests.post(
            url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message
            },
            timeout=20
        )

        response.raise_for_status()

        log.info("Telegram notification sent.")

    except requests.RequestException as error:

        log.error(
            f"Telegram error: {error}"
        )


def main():

    log.info(
        f"Checking: {PRODUCT_NAME}"
    )

    current = check_stock()

    if current is None:
        return

    previous = load_previous_status()

    status = (
        "IN STOCK"
        if current
        else "OUT OF STOCK"
    )

    log.info(
        f"Current status: {status}"
    )

    # Notify only when product changes
    # from OUT OF STOCK to IN STOCK.

    if current is True and previous is False:

        message = (
            "🚨 PRODUCT BACK IN STOCK!\n\n"
            f"🧴 {PRODUCT_NAME}\n\n"
            "✅ Available now!\n\n"
            f"🛒 {PRODUCT_URL}"
        )

        send_telegram_message(message)

    save_status(current)


if __name__ == "__main__":
    main()
