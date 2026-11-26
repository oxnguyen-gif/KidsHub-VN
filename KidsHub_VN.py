#!/usr/bin/env python3
# -*- coding: utf-8
"""KidsHub VN - safe Telegram community bot foundation.

This is a clean replacement foundation based on the original project's
Python/async + SQLite approach. It intentionally excludes gambling prediction,
betting-site connectors, VIP prediction sales, bank QR/deposit automation,
and old owner credentials.

Install: pip install "python-telegram-bot>=21.6,<22"
Run:     set BOT_TOKEN=...          (Windows PowerShell: $env:BOT_TOKEN="...")
         set ADMIN_IDS=7330307381   (optional; defaults to the new owner ID)
         python KidsHub_VN.py
"""
from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes,
    MessageHandler, filters,
)

APP_NAME = "KidsHub VN"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("KIDSHUB_DB_PATH", str(BASE_DIR / "kidshub_vn.sqlite3")))
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {
    int(part.strip())
    for part in os.getenv("ADMIN_IDS", "7330307381").split(",")
    if part.strip().isdigit()
}

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(APP_NAME)


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def db_init() -> None:
    with db_connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT NOT NULL DEFAULT '',
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            is_banned INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bot_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def upsert_user(user) -> None:
    stamp = now_iso()
    full_name = " ".join(x for x in [user.first_name, user.last_name] if x)
    with db_connect() as conn:
        conn.execute("""
            INSERT INTO users(user_id, username, full_name, first_seen, last_seen)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                full_name=excluded.full_name,
                last_seen=excluded.last_seen
        """, (user.id, user.username, full_name, stamp, stamp))
        conn.execute("INSERT INTO bot_events(event, created_at) VALUES(?, ?)", ("user_seen", stamp))


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def is_banned(user_id: int) -> bool:
    with db_connect() as conn:
        row = conn.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,)).fetchone()
    return bool(row and row["is_banned"])


def home_keyboard(is_owner: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("👤 Tài khoản", callback_data="profile"),
         InlineKeyboardButton("💬 Gửi góp ý", callback_data="feedback")],
        [InlineKeyboardButton("ℹ️ Hướng dẫn", callback_data="help"),
         InlineKeyboardButton("🛟 Hỗ trợ", callback_data="support")],
    ]
    if is_owner:
        rows.append([InlineKeyboardButton("⚙️ Quản trị", callback_data="admin")])
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.effective_chat:
        return
    upsert_user(user)
    if is_banned(user.id):
        await update.effective_message.reply_text("Tài khoản hiện không thể sử dụng bot. Nếu cần hỗ trợ, hãy liên hệ quản trị viên.")
        return
    text = (
        f"<b>👋 Chào mừng đến với {APP_NAME}!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Đây là bot cộng đồng dùng để hỗ trợ thành viên, tiếp nhận góp ý "
        "và cung cấp các tiện ích quản trị.\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        "Chọn chức năng bên dưới để tiếp tục."
    )
    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.HTML,
        reply_markup=home_keyboard(is_admin(user.id)),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        f"{APP_NAME} hỗ trợ các lệnh:\n"
        "/start - Mở trang chủ\n"
        "/help - Xem hướng dẫn\n"
        "/feedback nội_dung - Gửi góp ý\n"
        "/admin - Bảng quản trị (chỉ Admin)"
    )


async def feedback_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    upsert_user(user)
    message = " ".join(context.args).strip()
    if not message:
        await update.effective_message.reply_text("Cú pháp: /feedback nội dung góp ý")
        return
    with db_connect() as conn:
        conn.execute(
            "INSERT INTO feedback(user_id, message, created_at) VALUES(?, ?, ?)",
            (user.id, message[:4000], now_iso()),
        )
    await update.effective_message.reply_text("Đã nhận góp ý. Cảm ơn bạn!")
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"💬 Góp ý mới từ <code>{user.id}</code> (@{user.username or 'không có username'}):\n"
                f"{message[:3500]}",
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            log.warning("Could not notify admin %s: %s", admin_id, exc)


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.effective_message.reply_text("Bạn không có quyền sử dụng lệnh này.")
        return
    with db_connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        active = conn.execute("SELECT COUNT(*) AS n FROM users WHERE is_banned=0").fetchone()["n"]
        feedback_count = conn.execute("SELECT COUNT(*) AS n FROM feedback").fetchone()["n"]
    await update.effective_message.reply_text(
        f"<b>⚙️ {APP_NAME} — ADMIN</b>\n"
        f"Tổng thành viên: <b>{total}</b>\n"
        f"Đang hoạt động: <b>{active}</b>\n"
        f"Góp ý đã nhận: <b>{feedback_count}</b>\n\n"
        "Lệnh quản trị:\n"
        "/broadcast nội_dung - Gửi thông báo cho thành viên\n"
        "/ban user_id - Khóa tài khoản\n"
        "/unban user_id - Mở khóa tài khoản",
        parse_mode=ParseMode.HTML,
    )


async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not is_admin(user.id):
        return
    message = " ".join(context.args).strip()
    if not message:
        await update.effective_message.reply_text("Cú pháp: /broadcast nội dung")
        return
    with db_connect() as conn:
        rows = conn.execute("SELECT user_id FROM users WHERE is_banned=0").fetchall()
    sent = failed = 0
    for row in rows:
        try:
            await context.bot.send_message(row["user_id"], message[:4000])
            sent += 1
        except Exception:
            failed += 1
    await update.effective_message.reply_text(f"Đã gửi: {sent}. Không gửi được: {failed}.")


async def set_ban(update: Update, context: ContextTypes.DEFAULT_TYPE, banned: bool) -> None:
    user = update.effective_user
    if not user or not is_admin(user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("Cần cung cấp user_id dạng số.")
        return
    target = int(context.args[0])
    with db_connect() as conn:
        cur = conn.execute("UPDATE users SET is_banned=? WHERE user_id=?", (int(banned), target))
    await update.effective_message.reply_text(
        ("Đã khóa" if banned else "Đã mở khóa") + (" tài khoản." if cur.rowcount else "; không tìm thấy thành viên.")
    )


async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await set_ban(update, context, True)


async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await set_ban(update, context, False)


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.from_user:
        return
    await query.answer()
    uid = query.from_user.id
    if query.data == "profile":
        with db_connect() as conn:
            row = conn.execute("SELECT first_seen, last_seen FROM users WHERE user_id=?", (uid,)).fetchone()
        text = f"<b>Tài khoản</b>\nID: <code>{uid}</code>\nTham gia: {row['first_seen'] if row else 'N/A'}"
    elif query.data == "feedback":
        text = "Gửi góp ý bằng lệnh:\n<code>/feedback Nội dung góp ý</code>"
    elif query.data == "help":
        text = "Dùng /help để xem danh sách lệnh."
    elif query.data == "support":
        text = "Kênh hỗ trợ sẽ được cập nhật sau khi chủ bot cấu hình."
    elif query.data == "admin" and is_admin(uid):
        with db_connect() as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        text = f"<b>Admin {APP_NAME}</b>\nThành viên: {total}\nDùng /admin để xem công cụ quản trị."
    else:
        text = "Chức năng không khả dụng."
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=home_keyboard(is_admin(uid)))


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Unhandled bot error", exc_info=context.error)


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("Thiếu BOT_TOKEN. Hãy đặt BOT_TOKEN trong Environment Variables; không ghi token vào file.")
    if not ADMIN_IDS:
        raise SystemExit("Thiếu ADMIN_IDS. Hãy đặt ADMIN_IDS là Telegram ID của chủ bot.")
    db_init()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("feedback", feedback_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_error_handler(on_error)
    log.info("%s is starting; database=%s", APP_NAME, DB_PATH)
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
