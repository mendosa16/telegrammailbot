import json
import logging
import os
from pathlib import Path
from typing import List, Tuple

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "stok.json"
LOG_FILE = BASE_DIR / "data" / "islem_loglari.json"

BOT_TOKEN = "8763896740:AAEWoDsgTcDjVLaHbsdjLQaJaLrw73HAI9M"
ADMIN_CHAT_ID = "7082029749"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def ensure_files() -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not DATA_FILE.exists():
        sample_data = {
            "stok": [
                "kayit_001",
                "kayit_002",
                "kayit_003",
                "kayit_004",
                "kayit_005",
            ]
        }
        DATA_FILE.write_text(
            json.dumps(sample_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if not LOG_FILE.exists():
        LOG_FILE.write_text("[]", encoding="utf-8")


def load_stock() -> List[str]:
    ensure_files()
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return data.get("stok", [])


def save_stock(stock: List[str]) -> None:
    DATA_FILE.write_text(
        json.dumps({"stok": stock}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_log(action: str, amount: int, delivered: List[str], chat_id: int) -> None:
    logs = json.loads(LOG_FILE.read_text(encoding="utf-8"))
    logs.append(
        {
            "action": action,
            "amount": amount,
            "delivered": delivered,
            "chat_id": chat_id,
        }
    )
    LOG_FILE.write_text(json.dumps(logs, ensure_ascii=False, indent=2), encoding="utf-8")


def is_admin(chat_id: int) -> bool:
    return str(chat_id) == str(ADMIN_CHAT_ID)


def parse_amount(args: List[str]) -> Tuple[bool, int, str]:
    if not args:
        return False, 0, "Adet yazman lazım. Örnek: /ver 10"

    try:
        amount = int(args[0])
    except ValueError:
        return False, 0, "Adet sadece sayı olmalı. Örnek: /ver 10"

    if amount <= 0:
        return False, 0, "Adet 0'dan büyük olmalı."

    return True, amount, ""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id

    if not is_admin(chat_id):
        await update.message.reply_text("Bu bot sadece yetkili kullanıcı içindir.")
        return

    text = (
        "Merhaba. Kullanılabilir komutlar:\n\n"
        "/stok - Kalan stok sayısını gösterir\n"
        "/ver 10 - Stoktan 10 kayıt verir\n"
        "/ekle kayit_006 - Stoğa tek kayıt ekler\n"
        "/liste - İlk 20 kaydı gösterir\n"
    )
    await update.message.reply_text(text)


async def stok(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not is_admin(chat_id):
        await update.message.reply_text("Yetkisiz kullanım.")
        return

    stock = load_stock()
    await update.message.reply_text(f"Kalan stok: {len(stock)} adet")


async def liste(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not is_admin(chat_id):
        await update.message.reply_text("Yetkisiz kullanım.")
        return

    stock = load_stock()
    if not stock:
        await update.message.reply_text("Stok boş.")
        return

    preview = stock[:20]
    message = "İlk kayıtlar:\n\n" + "\n".join(preview)
    if len(stock) > 20:
        message += f"\n\n... ve {len(stock) - 20} kayıt daha var."

    await update.message.reply_text(message)


async def ekle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not is_admin(chat_id):
        await update.message.reply_text("Yetkisiz kullanım.")
        return

    if not context.args:
        await update.message.reply_text("Eklemek için bir kayıt yaz. Örnek: /ekle kayit_123")
        return

    new_record = " ".join(context.args).strip()
    stock = load_stock()
    stock.append(new_record)
    save_stock(stock)

    await update.message.reply_text(f"Kayıt eklendi. Yeni stok: {len(stock)}")


async def ver(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not is_admin(chat_id):
        await update.message.reply_text("Yetkisiz kullanım.")
        return

    ok, amount, error = parse_amount(context.args)
    if not ok:
        await update.message.reply_text(error)
        return

    stock = load_stock()

    if len(stock) == 0:
        await update.message.reply_text("Stok boş.")
        return

    if amount > len(stock):
        await update.message.reply_text(
            f"Yeterli stok yok. İstenen: {amount}, Kalan: {len(stock)}"
        )
        return

    delivered = stock[:amount]
    remaining = stock[amount:]
    save_stock(remaining)
    write_log("ver", amount, delivered, chat_id)

    message = "Teslim edilen kayıtlar:\n\n" + "\n".join(delivered)
    message += f"\n\nKalan stok: {len(remaining)}"
    await update.message.reply_text(message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


def main() -> None:
    global BOT_TOKEN, ADMIN_CHAT_ID

    ensure_files()

    BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
    ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "").strip()

    logger.info("BOT_TOKEN mevcut mu?: %s", bool(BOT_TOKEN))
    logger.info("ADMIN_CHAT_ID mevcut mu?: %s", bool(ADMIN_CHAT_ID))

    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN ortam değişkeni eksik.")

    if not ADMIN_CHAT_ID:
        raise ValueError("ADMIN_CHAT_ID ortam değişkeni eksik.")

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stok", stok))
    application.add_handler(CommandHandler("liste", liste))
    application.add_handler(CommandHandler("ekle", ekle))
    application.add_handler(CommandHandler("ver", ver))

    logger.info("Bot başlatılıyor...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
