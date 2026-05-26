import os
import logging
from typing import Any, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from aliexpress_api import AliexpressApi, models
from deep_translator import GoogleTranslator


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALIEXPRESS_APP_KEY = os.getenv("ALIEXPRESS_APP_KEY")
ALIEXPRESS_APP_SECRET = os.getenv("ALIEXPRESS_APP_SECRET")
ALIEXPRESS_TRACKING_ID = os.getenv("ALIEXPRESS_TRACKING_ID", "telegram_bot")

DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "USD")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "EN")
PRODUCTS_COUNT = int(os.getenv("PRODUCTS_COUNT", "3"))


def required_env() -> None:
    missing = [
        name for name, value in {
            "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
            "ALIEXPRESS_APP_KEY": ALIEXPRESS_APP_KEY,
            "ALIEXPRESS_APP_SECRET": ALIEXPRESS_APP_SECRET,
            "ALIEXPRESS_TRACKING_ID": ALIEXPRESS_TRACKING_ID,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")


def has_hebrew(text: str) -> bool:
    return any("\u0590" <= ch <= "\u05FF" for ch in text)


def translate_if_needed(query: str) -> str:
    q = query.strip().lower()

    hebrew_intents = {
        "מטען נייד": "power bank portable charger battery pack",
        "כבל לאייפון": "iphone charging cable lightning cable",
        "אוזניות בלוטוס": "bluetooth earbuds wireless earphones",
        "עכבר גיימינג": "gaming mouse",
        "מקלדת גיימינג": "gaming keyboard",
        "שעון חכם": "smart watch",
        "מצלמת אבטחה": "security camera",
        "מטען לרכב": "car charger",
    }

    for hebrew, english in hebrew_intents.items():
        if hebrew in q:
            return english

    if has_hebrew(query):
        try:
            return GoogleTranslator(source="auto", target="en").translate(query)
        except Exception:
            return query

    return query


def get_model_enum(enum_class: Any, value: str, fallback: Any) -> Any:
    try:
        return getattr(enum_class, value.upper())
    except Exception:
        return fallback


def product_attr(product: Any, names: List[str], default: str = "") -> str:
    for name in names:
        value = getattr(product, name, None)
        if value:
            return str(value)
    return default


def normalize_text(text: str) -> str:
    return (
        text.lower()
        .replace("-", " ")
        .replace("_", " ")
        .replace("/", " ")
        .replace(",", " ")
        .replace(".", " ")
        .strip()
    )


def product_matches_query(product: Any, query: str) -> bool:
    title = normalize_text(product_attr(product, ["product_title", "title"]))
    q = normalize_text(query)

    bad_words = [
        "solar panel", "phone holder", "car holder", "stand", "mount",
        "bracket", "case", "cover", "carplay", "magsafe holder",
        "screen protector", "film", "bag", "strap"
    ]

    if any(bad in title for bad in bad_words):
        return False

    if "power bank" in q or "portable charger" in q or "battery pack" in q:
        must_have_any = [
            "power bank",
            "portable charger",
            "battery pack",
            "external battery",
            "mobile power"
        ]
        return any(term in title for term in must_have_any)

    if "iphone charging cable" in q or "lightning cable" in q:
        must_have_any = [
            "iphone cable",
            "lightning cable",
            "charging cable",
            "usb cable"
        ]
        return any(term in title for term in must_have_any)

    words = [w for w in q.split() if len(w) > 2]

    if not words:
        return True

    matched_words = sum(1 for word in words if word in title)
    return matched_words >= max(1, len(words) - 1)


def clean_and_filter_products(products: List[Any], query: str, limit: int) -> List[Any]:
    filtered = []

    for product in products:
        title = product_attr(product, ["product_title", "title"])
        price = product_attr(product, ["target_sale_price", "sale_price", "app_sale_price"])
        url = get_product_url(product)
        image = product_attr(product, ["product_main_image_url", "image_url"])

        if not title or not price or not url or not image:
            continue

        if product_matches_query(product, query):
            filtered.append(product)

    return filtered[:limit]


def get_product_url(product: Any) -> str:
    return product_attr(product, [
        "product_detail_url",
        "product_url",
        "promotion_link",
        "target_url",
    ])


def get_affiliate_url(api: AliexpressApi, product_url: str) -> str:
    if not product_url:
        return ""

    try:
        links = api.get_affiliate_links(product_url)
        if links:
            return product_attr(
                links[0],
                ["promotion_link", "affiliate_url", "url"],
                product_url
            )
    except Exception as exc:
        logging.warning("Affiliate link conversion failed: %s", exc)

    return product_url


def build_api() -> AliexpressApi:
    currency = get_model_enum(models.Currency, DEFAULT_CURRENCY, models.Currency.USD)
    language = get_model_enum(models.Language, DEFAULT_LANGUAGE, models.Language.EN)

    return AliexpressApi(
        ALIEXPRESS_APP_KEY,
        ALIEXPRESS_APP_SECRET,
        language,
        currency,
        ALIEXPRESS_TRACKING_ID,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📸 CREDIT: @TALCOHEN105",
                url="https://instagram.com/talcohen105"
            )
        ]
    ])

    await update.message.reply_text(
        "🔥 *Welcome to AliDeals* 🔥\n\n"
        "🛍 Find trending AliExpress products instantly 🚀\n"
        "דילים חמים ומוצרים ויראליים — ישר לטלגרם.\n\n"
        "💡 *Search in Hebrew or English:*\n\n"
        "🔎 Examples:\n"
        "• iphone charger\n"
        "• gaming mouse\n"
        "• מטען נייד\n"
        "• אוזניות בלוטוס\n\n"
        "⚡ *What you'll get:*\n"
        "• Trending products\n"
        "• Direct AliExpress links\n"
        "• Smart matching deals\n"
        "• Fast results in seconds\n\n"
        "🌍 Hebrew + English support\n"
        "💸 Smart shopping starts here 🛒",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📌 *How to use AliDeals*\n\n"
        "Type any product name in Hebrew or English 👇\n"
        "שלחו שם של מוצר — בעברית או באנגלית.\n\n"
        "🔎 Examples:\n"
        "• iphone charger\n"
        "• smartwatch\n"
        "• מטען לאייפון\n"
        "• אוזניות גיימינג\n\n"
        "🚀 AliDeals instantly finds:\n"
        "• Viral AliExpress products\n"
        "• Direct shopping links\n"
        "• Trending gadgets\n"
        "• Best matching deals\n\n"
        "⚡ Fast • Smart • Simple",
        parse_mode="Markdown"
    )


async def search_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    original_query = (update.message.text or "").strip()

    if not original_query:
        return

    waiting_msg = await update.message.reply_text(
        "🔎 Searching smart AliExpress deals..."
    )

    try:
        query = translate_if_needed(original_query)
        api = build_api()

        response = api.get_products(
            keywords=query,
            page_no=1,
            page_size=50,
        )

        products = getattr(response, "products", []) or []
        products = clean_and_filter_products(products, query, PRODUCTS_COUNT)

        if not products:
            await waiting_msg.edit_text(
                "❌ No accurate matching products found.\n"
                "Try a more specific search, for example: power bank 20000mah"
            )
            return

        await waiting_msg.edit_text(
            f"🔥 Best AliExpress finds for: {original_query}"
        )

        for product in products[:PRODUCTS_COUNT]:
            title = product_attr(product, ["product_title", "title"], "AliExpress product")
            price = product_attr(product, ["target_sale_price", "sale_price", "app_sale_price"], "")
            currency = product_attr(product, ["target_sale_price_currency", "currency"], DEFAULT_CURRENCY)
            image_url = product_attr(product, ["product_main_image_url", "image_url"], "")
            product_url = get_product_url(product)
            affiliate_url = get_affiliate_url(api, product_url)

            caption = f"🛒 {title}"

            if price:
                caption += f"\n💰 {price} {currency}"

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🛒 Open on AliExpress",
                        url=affiliate_url or product_url
                    )
                ]
            ])

            if image_url:
                await update.message.reply_photo(
                    photo=image_url,
                    caption=caption[:1024],
                    reply_markup=keyboard,
                )
            else:
                await update.message.reply_text(
                    caption,
                    reply_markup=keyboard,
                )

    except Exception as exc:
        logging.exception("Search failed")
        await waiting_msg.edit_text(
            "❌ Something went wrong while searching.\n\n"
            f"Error: {type(exc).__name__}"
        )


def main() -> None:
    required_env()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_products))

    logging.info("AliDeals bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
