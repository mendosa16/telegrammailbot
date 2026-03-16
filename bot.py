import logging
import os
from typing import List, Tuple

import psycopg
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = ""
ADMIN_CHAT_ID = ""
DATABASE_URL = ""

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def get_connection():
    return psycopg.connect(DATABASE_URL)


def init_db() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS stock_items (
                    id SERIAL PRIMARY KEY,
                    record_text TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS stock_logs (
                    id SERIAL PRIMARY KEY,
                    action TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    delivered TEXT,
                    chat_id BIGINT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        conn.commit()


def is_admin(chat_id: int) -> bool:
    return str(chat_id) == str(ADMIN_CHAT_ID)


def parse_amount(args: List[str]) -> Tuple[bool, int, str]:
    if not args:
        return False, 0, "Adet yazman lazim. Ornek: /ver 10"

    try:
        amount = int(args[0])
    except ValueError:
        return False, 0, "Adet sadece sayi olmali. Ornek: /ver 10"

    if amount <= 0:
        return False, 0, "Adet 0'dan buyuk olmali."

    return True, amount, ""


def stock_count() -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM stock_items")
            return cur.fetchone()[0]


def add_record(record_text: str) -> Tuple[bool, str]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO stock_items (record_text) VALUES (%s)",
                    (record_text,)
                )
            conn.commit()
        return True, "Kayit eklendi."
    except psycopg.errors.UniqueViolation:
        return False, "Bu kayit zaten stokta var."
    except Exception as e:
        logger.exception("Kayit ekleme hatasi")
        return False, f"Hata olustu: {e}"


def remove_record(record_text: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM stock_items WHERE LOWER(record_text) = LOWER(%s)",
                (record_text,)
            )
            deleted = cur.rowcount
        conn.commit()
    return deleted > 0


def list_records(limit: int = 20) -> List[str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT record_text FROM stock_items ORDER BY id ASC LIMIT %s",
                (limit,)
            )
            rows = cur.fetchall()
    return [row[0] for row in rows]


def total_records() -> int:
    return stock_count()


def take_records(amount: int) -> List[str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, record_text FROM stock_items ORDER BY id ASC LIMIT %s",
                (amount,)
            )
            rows = cur.fetchall()

            if not rows:
                return []

            ids = [row[0] for row in rows]
            records = [row[1] for row in rows]

            cur.execute(
                "DELETE FROM stock_items WHERE id = ANY(%s)",
                (ids,)
            )
        conn.commit()
    return records


def write_log(action: str, amount: int, delivered: List[str], chat_id: int) -> None:
    delivered_text = "\n".join(delivered)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO stock_logs (action, amount, delivered, chat_id)
                VALUES (%s, %s, %s, %s)
                """,
                (action, amount, delivered_text, chat_id)
            )
        conn.commit()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id

    if not is_admin(chat_id):
        await update.message.reply_text("Bu bot sadece yetkili kullanici icindir.")
        return

    text = (
        "Merhaba. Kullanilabilir komutlar:\n\n"
        "/stok - Kalan stok sayisini gosterir\n"
        "/ver 10 - Stoktan 10 kayit verir\n"
        "/ekle kayit_006 - Stoga tek kayit ekler\n"
        "/kaldir kayit_006 - Belirli kaydi stoktan siler\n"
        "/liste - Ilk 20 kaydi gosterir\n"
    )
    await update.message.reply_text(text)


async def stok(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not is_admin(chat_id):
        await update.message.reply_text("Yetkisiz kullanim.")
        return

    count = total_records()
    await update.message.reply_text(f"Kalan stok: {count} adet")


async def liste(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not is_admin(chat_id):
        await update.message.reply_text("Yetkisiz kullanim.")
        return

    records = list_records(20)
    total = total_records()

    if not records:
        await update.message.reply_text("Stok bos.")
        return

    message = "Ilk kayitlar:\n\n" + "\n".join(records)
    if total > 20:
        message += f"\n\n... ve {total - 20} kayit daha var."

    await update.message.reply_text(message)


async def ekle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not is_admin(chat_id):
        await update.message.reply_text("Yetkisiz kullanim.")
        return

    if not context.args:
        await update.message.reply_text("Eklemek icin bir kayit yaz. Ornek: /ekle kayit_123")
        return

    record_text = " ".join(context.args).strip()
    ok, msg = add_record(record_text)

    if ok:
        await update.message.reply_text(f"{msg} Yeni stok: {total_records()}")
    else:
        await update.message.reply_text(msg)


async def kaldir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not is_admin(chat_id):
        await update.message.reply_text("Yetkisiz kullanim.")
        return

    if not context.args:
        await update.message.reply_text("Kaldirmak icin kayit yaz. Ornek: /kaldir kayit_001")
        return

    record_text = " ".join(context.args).strip()
    removed = remove_record(record_text)

    if removed:
        await update.message.reply_text(f"Kayit kaldirildi: {record_text}")
    else:
        await update.message.reply_text("Boyle bir kayit bulunamadi.")


async def ver(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not is_admin(chat_id):
        await update.message.reply_text("Yetkisiz kullanim.")
        return

    ok, amount, error = parse_amount(context.args)
    if not ok:
        await update.message.reply_text(error)
        return

    current_count = total_records()

    if current_count == 0:
        await update.message.reply_text("Stok bos.")
        return

    if amount > current_count:
        await update.message.reply_text(
            f"Yeterli stok yok. Istenen: {amount}, Kalan: {current_count}"
        )
        return

    delivered = take_records(amount)

    if not delivered:
        await update.message.reply_text("Teslim edilecek kayit bulunamadi.")
        return

    write_log("ver", amount, delivered, chat_id)

    message = "Teslim edilen kayitlar:\n\n" + "\n".join(delivered)
    message += f"\n\nKalan stok: {total_records()}"
    await update.message.reply_text(message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


def main() -> None:
    global BOT_TOKEN, ADMIN_CHAT_ID, DATABASE_URL

    BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
    ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "").strip()
    DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

    logger.info("BOT_TOKEN mevcut mu?: %s", bool(BOT_TOKEN))
    logger.info("ADMIN_CHAT_ID mevcut mu?: %s", bool(ADMIN_CHAT_ID))
    logger.info("DATABASE_URL mevcut mu?: %s", bool(DATABASE_URL))

    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN eksik.")

    if not ADMIN_CHAT_ID:
        raise ValueError("ADMIN_CHAT_ID eksik.")

    if not DATABASE_URL:
        raise ValueError("DATABASE_URL eksik.")

    init_db()

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stok", stok))
    application.add_handler(CommandHandler("liste", liste))
    application.add_handler(CommandHandler("ekle", ekle))
    application.add_handler(CommandHandler("kaldir", kaldir))
    application.add_handler(CommandHandler("ver", ver))

    logger.info("Bot baslatiliyor...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
