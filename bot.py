import logging
import os
import sqlite3
from typing import List, Tuple

import psycopg
from psycopg import errors as psycopg_errors
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_TOKEN = ""
ADMIN_CHAT_ID = ""
DATABASE_URL = ""
DB_MODE = "sqlite"  # "postgres" or "sqlite"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def using_postgres() -> bool:
    return DB_MODE == "postgres"


def get_connection():
    if using_postgres():
        return psycopg.connect(DATABASE_URL)
    return sqlite3.connect("data.db")


def init_db() -> None:
    with get_connection() as conn:
        cur = conn.cursor()

        if using_postgres():
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_items (
                    id SERIAL PRIMARY KEY,
                    record_text TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_logs (
                    id SERIAL PRIMARY KEY,
                    action TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    delivered TEXT,
                    chat_id BIGINT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_text TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    delivered TEXT,
                    chat_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

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


def total_records() -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM stock_items")
        return cur.fetchone()[0]


def add_record(record_text: str) -> Tuple[bool, str]:
    cleaned = record_text.strip()
    if not cleaned:
        return False, "Bos kayit eklenemez."

    try:
        with get_connection() as conn:
            cur = conn.cursor()
            if using_postgres():
                cur.execute(
                    "INSERT INTO stock_items (record_text) VALUES (%s)",
                    (cleaned,),
                )
            else:
                cur.execute(
                    "INSERT INTO stock_items (record_text) VALUES (?)",
                    (cleaned,),
                )
            conn.commit()
        return True, "Kayit eklendi."
    except (psycopg_errors.UniqueViolation, sqlite3.IntegrityError):
        return False, "Bu kayit zaten stokta var."
    except Exception as e:
        logger.exception("Kayit ekleme hatasi")
        return False, f"Hata olustu: {e}"


def add_records_bulk(records: List[str]) -> Tuple[int, int]:
    cleaned_records = []
    seen = set()

    for record in records:
        item = record.strip()
        if not item:
            continue

        lowered = item.lower()
        if lowered in seen:
            continue

        seen.add(lowered)
        cleaned_records.append(item)

    if not cleaned_records:
        return 0, 0

    inserted_count = 0

    with get_connection() as conn:
        cur = conn.cursor()

        for record in cleaned_records:
            if using_postgres():
                cur.execute(
                    """
                    INSERT INTO stock_items (record_text)
                    VALUES (%s)
                    ON CONFLICT (record_text) DO NOTHING
                    """,
                    (record,),
                )
            else:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO stock_items (record_text)
                    VALUES (?)
                    """,
                    (record,),
                )

            inserted_count += cur.rowcount

        conn.commit()

    skipped_count = len(cleaned_records) - inserted_count
    return inserted_count, skipped_count


def remove_record(record_text: str) -> bool:
    with get_connection() as conn:
        cur = conn.cursor()
        if using_postgres():
            cur.execute(
                "DELETE FROM stock_items WHERE LOWER(record_text) = LOWER(%s)",
                (record_text.strip(),),
            )
        else:
            cur.execute(
                "DELETE FROM stock_items WHERE LOWER(record_text) = LOWER(?)",
                (record_text.strip(),),
            )
        deleted = cur.rowcount
        conn.commit()
    return deleted > 0


def list_records(limit: int = 20) -> List[str]:
    with get_connection() as conn:
        cur = conn.cursor()
        if using_postgres():
            cur.execute(
                "SELECT record_text FROM stock_items ORDER BY id ASC LIMIT %s",
                (limit,),
            )
        else:
            cur.execute(
                "SELECT record_text FROM stock_items ORDER BY id ASC LIMIT ?",
                (limit,),
            )
        rows = cur.fetchall()
    return [row[0] for row in rows]


def take_records(amount: int) -> List[str]:
    with get_connection() as conn:
        cur = conn.cursor()

        if using_postgres():
            cur.execute(
                "SELECT id, record_text FROM stock_items ORDER BY id ASC LIMIT %s",
                (amount,),
            )
        else:
            cur.execute(
                "SELECT id, record_text FROM stock_items ORDER BY id ASC LIMIT ?",
                (amount,),
            )

        rows = cur.fetchall()

        if not rows:
            return []

        ids = [row[0] for row in rows]
        records = [row[1] for row in rows]

        if using_postgres():
            cur.execute(
                "DELETE FROM stock_items WHERE id = ANY(%s)",
                (ids,),
            )
        else:
            placeholders = ",".join("?" for _ in ids)
            cur.execute(
                f"DELETE FROM stock_items WHERE id IN ({placeholders})",
                ids,
            )

        conn.commit()

    return records


def write_log(action: str, amount: int, delivered: List[str], chat_id: int) -> None:
    delivered_text = "\n".join(delivered)

    with get_connection() as conn:
        cur = conn.cursor()
        if using_postgres():
            cur.execute(
                """
                INSERT INTO stock_logs (action, amount, delivered, chat_id)
                VALUES (%s, %s, %s, %s)
                """,
                (action, amount, delivered_text, chat_id),
            )
        else:
            cur.execute(
                """
                INSERT INTO stock_logs (action, amount, delivered, chat_id)
                VALUES (?, ?, ?, ?)
                """,
                (action, amount, delivered_text, chat_id),
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
        "/ekle mail@gmail.com 123456 - Stoga tek kayit ekler\n"
        "/kaldir mail@gmail.com 123456 - Kaydi stoktan siler\n"
        "/liste - Ilk 20 kaydi gosterir\n"
        "Txt dosyasi gonder - Toplu kayit yukler\n"
    )
    await update.message.reply_text(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


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
        await update.message.reply_text(
            "Eklemek icin bir kayit yaz. Ornek: /ekle mail@gmail.com 123456"
        )
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
        await update.message.reply_text(
            "Kaldirmak icin kayit yaz. Ornek: /kaldir mail@gmail.com 123456"
        )
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


async def txt_yukle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id

    if not is_admin(chat_id):
        await update.message.reply_text("Yetkisiz kullanim.")
        return

    if not update.message or not update.message.document:
        await update.message.reply_text("Bir txt dosyasi gondermen lazim.")
        return

    document = update.message.document

    if not document.file_name or not document.file_name.lower().endswith(".txt"):
        await update.message.reply_text("Sadece .txt dosyasi kabul ediliyor.")
        return

    try:
        telegram_file = await context.bot.get_file(document.file_id)
        file_bytes = await telegram_file.download_as_bytearray()
        content = file_bytes.decode("utf-8", errors="ignore")

        lines = [line.strip() for line in content.splitlines() if line.strip()]

        if not lines:
            await update.message.reply_text("Txt dosyasi bos.")
            return

        inserted_count, skipped_count = add_records_bulk(lines)

        await update.message.reply_text(
            "Toplu yukleme tamamlandi.\n\n"
            f"Eklendi: {inserted_count}\n"
            f"Atlanan(tekrar/bos): {skipped_count}\n"
            f"Guncel stok: {total_records()}"
        )

    except Exception as e:
        logger.exception("Txt yukleme hatasi")
        await update.message.reply_text(f"Yukleme sirasinda hata olustu: {e}")


def main() -> None:
    global BOT_TOKEN, ADMIN_CHAT_ID, DATABASE_URL, DB_MODE

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

    if DATABASE_URL:
        DB_MODE = "postgres"
        logger.info("Postgres kullanilacak.")
    else:
        DB_MODE = "sqlite"
        logger.info("DATABASE_URL yok, sqlite kullanilacak.")

    init_db()

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stok", stok))
    application.add_handler(CommandHandler("liste", liste))
    application.add_handler(CommandHandler("ekle", ekle))
    application.add_handler(CommandHandler("kaldir", kaldir))
    application.add_handler(CommandHandler("ver", ver))
    application.add_handler(
        MessageHandler(filters.Document.FileExtension("txt"), txt_yukle)
    )

    logger.info("Bot baslatiliyor...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
