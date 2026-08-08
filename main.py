# -*- coding: utf-8 -*-
"""
HyakkimaruBot — Render & GitHub Edition
Python 3.10+
Dependencies: python-telegram-bot

Render.com da 'Environment Variables' bo'limiga BOT_TOKEN ni qo'shing.
"""
import logging
import os
import re
import sqlite3
from contextlib import closing

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions
)
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# =========================================================
# 1. CONFIG & ENVIRONMENT
# =========================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8518958687:AAGitb97mgCN00yB24TDE5MPehklz6BlLHY")

DATABASE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "hyakkimaru.db"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("HyakkimaruBot")

# =========================================================
# 2. DATABASE
# =========================================================
def connect():
    c = sqlite3.connect(DATABASE_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    with closing(connect()) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS chats(
          chat_id INTEGER PRIMARY KEY, 
          title TEXT, 
          type TEXT,
          rules TEXT DEFAULT '', 
          welcome_enabled INTEGER DEFAULT 1,
          welcome_text TEXT DEFAULT '🩸 Xush kelibsiz, {user}!',
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS users(
          user_id INTEGER PRIMARY KEY, 
          username TEXT, 
          first_name TEXT,
          last_name TEXT, 
          xp INTEGER DEFAULT 0
        );
        
        CREATE TABLE IF NOT EXISTS chat_users(
          chat_id INTEGER, 
          user_id INTEGER, 
          messages INTEGER DEFAULT 0,
          games INTEGER DEFAULT 0, 
          warnings INTEGER DEFAULT 0,
          PRIMARY KEY(chat_id, user_id),
          FOREIGN KEY(chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE,
          FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS filters(
          id INTEGER PRIMARY KEY AUTOINCREMENT, 
          chat_id INTEGER,
          word TEXT, 
          response TEXT, 
          UNIQUE(chat_id, word)
        );
        
        CREATE TABLE IF NOT EXISTS locks(
          chat_id INTEGER, 
          feature TEXT, 
          enabled INTEGER DEFAULT 0,
          PRIMARY KEY(chat_id, feature)
        );
        
        CREATE TABLE IF NOT EXISTS game_sessions(
          chat_id INTEGER PRIMARY KEY,
          active INTEGER DEFAULT 0,
          started_at TEXT,
          players_count INTEGER DEFAULT 0,
          message_id INTEGER
        );
        
        CREATE TABLE IF NOT EXISTS game_players(
          chat_id INTEGER NOT NULL,
          user_id INTEGER NOT NULL,
          display_name TEXT,
          game_message_id INTEGER,
          PRIMARY KEY(chat_id, user_id)
        );
        
        CREATE TABLE IF NOT EXISTS game_results(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          chat_id INTEGER NOT NULL,
          user_id INTEGER NOT NULL,
          won INTEGER DEFAULT 0,
          alive INTEGER DEFAULT 0,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        c.commit()

def ensure_chat(chat_id, title, chat_type):
    with closing(connect()) as c:
        c.execute("""
            INSERT INTO chats(chat_id, title, type) VALUES(?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET 
            title=excluded.title, 
            type=excluded.type
        """, (chat_id, title, chat_type))
        c.commit()

def ensure_user(user_id, username, first_name, last_name):
    with closing(connect()) as c:
        c.execute("""
            INSERT INTO users(user_id, username, first_name, last_name)
            VALUES(?, ?, ?, ?) 
            ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name,
            last_name=excluded.last_name
        """, (user_id, username, first_name, last_name))
        c.commit()

def touch(chat_id, user_id):
    with closing(connect()) as c:
        c.execute("""
            INSERT INTO chat_users(chat_id, user_id) VALUES(?, ?)
            ON CONFLICT(chat_id, user_id) DO NOTHING
        """, (chat_id, user_id))
        c.commit()

def record_message(chat_id, user_id):
    with closing(connect()) as c:
        c.execute("""
            UPDATE chat_users 
            SET messages = messages + 1 
            WHERE chat_id = ? AND user_id = ?
        """, (chat_id, user_id))
        c.commit()

def profile(chat_id, user_id):
    with closing(connect()) as c:
        r = c.execute("""
            SELECT u.*, cu.messages, cu.games, cu.warnings 
            FROM chat_users cu
            JOIN users u ON u.user_id = cu.user_id 
            WHERE cu.chat_id = ? AND cu.user_id = ?
        """, (chat_id, user_id)).fetchone()
        return dict(r) if r else None

def rank(chat_id, user_id):
    with closing(connect()) as c:
        r = c.execute("""
            SELECT COUNT(*) + 1 AS rank 
            FROM chat_users
            WHERE chat_id = ? AND games > (
                SELECT games FROM chat_users WHERE chat_id = ? AND user_id = ?
            )
        """, (chat_id, chat_id, user_id)).fetchone()
        return r["rank"] if r else 1

def add_warning(chat_id, user_id):
    with closing(connect()) as c:
        c.execute("""
            UPDATE chat_users 
            SET warnings = warnings + 1 
            WHERE chat_id = ? AND user_id = ?
        """, (chat_id, user_id))
        c.commit()
        
        r = c.execute("""
            SELECT warnings 
            FROM chat_users 
            WHERE chat_id = ? AND user_id = ?
        """, (chat_id, user_id)).fetchone()
        return r["warnings"] if r else 1

def warnings_count(chat_id, user_id):
    with closing(connect()) as c:
        r = c.execute("""
            SELECT warnings 
            FROM chat_users 
            WHERE chat_id = ? AND user_id = ?
        """, (chat_id, user_id)).fetchone()
        return r["warnings"] if r else 0

def set_rules(chat_id, text):
    with closing(connect()) as c:
        c.execute("UPDATE chats SET rules = ? WHERE chat_id = ?", (text, chat_id))
        c.commit()

def get_rules(chat_id):
    with closing(connect()) as c:
        r = c.execute("SELECT rules FROM chats WHERE chat_id = ?", (chat_id,)).fetchone()
        return r["rules"] if r else ""

def set_welcome(chat_id, enabled, text=None):
    with closing(connect()) as c:
        if text is None:
            c.execute("UPDATE chats SET welcome_enabled = ? WHERE chat_id = ?", (int(enabled), chat_id))
        else:
            c.execute("UPDATE chats SET welcome_enabled = ?, welcome_text = ? WHERE chat_id = ?", (int(enabled), text, chat_id))
        c.commit()

def get_welcome(chat_id):
    with closing(connect()) as c:
        r = c.execute("SELECT welcome_enabled, welcome_text FROM chats WHERE chat_id = ?", (chat_id,)).fetchone()
        return dict(r) if r else {"welcome_enabled": 1, "welcome_text": "🩸 Xush kelibsiz, {user}!"}
def add_filter(chat_id, word, response):
    with closing(connect()) as c:
        c.execute("""
            INSERT INTO filters(chat_id, word, response) VALUES(?, ?, ?)
            ON CONFLICT(chat_id, word) DO UPDATE SET response = excluded.response
        """, (chat_id, word.lower(), response))
        c.commit()

def remove_filter(chat_id, word):
    with closing(connect()) as c:
        c.execute("DELETE FROM filters WHERE chat_id = ? AND word = ?", (chat_id, word.lower()))
        c.commit()

def get_filters(chat_id):
    with closing(connect()) as c:
        return [dict(r) for r in c.execute("SELECT word, response FROM filters WHERE chat_id = ? ORDER BY word", (chat_id,))]

def find_filter(chat_id, text):
    low = text.lower()
    with closing(connect()) as c:
        rows = c.execute("SELECT word, response FROM filters WHERE chat_id = ?", (chat_id,)).fetchall()
        for r in rows:
            if r["word"] in low:
                return r["response"]
    return None

def set_lock(chat_id, feature, enabled):
    with closing(connect()) as c:
        c.execute("""
            INSERT INTO locks(chat_id, feature, enabled) VALUES(?, ?, ?)
            ON CONFLICT(chat_id, feature) DO UPDATE SET enabled = excluded.enabled
        """, (chat_id, feature, int(enabled)))
        c.commit()

def get_lock(chat_id, feature):
    with closing(connect()) as c:
        r = c.execute("SELECT enabled FROM locks WHERE chat_id = ? AND feature = ?", (chat_id, feature)).fetchone()
        return bool(r["enabled"]) if r else False

def top_players(chat_id, limit=10):
    with closing(connect()) as c:
        return [dict(r) for r in c.execute("""
            SELECT u.username, u.first_name, cu.games, cu.messages
            FROM chat_users cu 
            JOIN users u ON u.user_id = cu.user_id
            WHERE cu.chat_id = ? 
            ORDER BY cu.games DESC, cu.user_id 
            LIMIT ?
        """, (chat_id, limit))]

# ---------------- GAME DATABASE ----------------
def game_start(chat_id, message_id, players):
    from datetime import datetime
    with closing(connect()) as c:
        c.execute("""
            INSERT INTO game_sessions(chat_id, active, started_at, players_count, message_id)
            VALUES(?, 1, ?, ?, ?) 
            ON CONFLICT(chat_id) DO UPDATE SET
            active = 1,
            started_at = excluded.started_at,
            players_count = excluded.players_count,
            message_id = excluded.message_id
        """, (chat_id, datetime.utcnow().isoformat(), len(players), message_id))
        
        c.execute("DELETE FROM game_players WHERE chat_id = ?", (chat_id,))
        for uid, name in players:
            c.execute("""
                INSERT OR REPLACE INTO game_players (chat_id, user_id, display_name, game_message_id) 
                VALUES(?, ?, ?, ?)
            """, (chat_id, uid, name, message_id))
            c.execute("""
                INSERT INTO chat_users(chat_id, user_id) VALUES(?, ?)
                ON CONFLICT(chat_id, user_id) DO NOTHING
            """, (chat_id, uid))
        c.commit()

def game_is_active(chat_id):
    with closing(connect()) as c:
        r = c.execute("SELECT active FROM game_sessions WHERE chat_id = ?", (chat_id,)).fetchone()
        return bool(r and r["active"])

def game_players(chat_id):
    with closing(connect()) as c:
        return [dict(r) for r in c.execute("SELECT user_id, display_name FROM game_players WHERE chat_id = ?", (chat_id,))]

def finish_game(chat_id, outcomes):
    with closing(connect()) as c:
        for uid, won, alive in outcomes:
            c.execute("UPDATE chat_users SET games = games + 1 WHERE chat_id = ? AND user_id = ?", (chat_id, uid))
            c.execute("INSERT INTO game_results(chat_id, user_id, won, alive) VALUES(?, ?, ?, ?)", (chat_id, uid, int(won), int(alive)))
        c.execute("UPDATE game_sessions SET active = 0 WHERE chat_id = ?", (chat_id,))
        c.execute("DELETE FROM game_players WHERE chat_id = ?", (chat_id,))
        c.commit()

def game_stats(chat_id, user_id):
    with closing(connect()) as c:
        r = c.execute("""
            SELECT COUNT(*) AS games,
            COALESCE(SUM(won), 0) AS wins,
            COALESCE(SUM(CASE WHEN alive = 0 THEN 1 ELSE 0 END), 0) AS deaths
            FROM game_results 
            WHERE chat_id = ? AND user_id = ?
        """, (chat_id, user_id)).fetchone()
        return dict(r)

# =========================================================
# 3. UTILS
# =========================================================
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id=None):
    chat = update.effective_chat
    uid = user_id or update.effective_user.id
    try:
        member = await context.bot.get_chat_member(chat.id, uid)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False

async def require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.effective_message.reply_text("🛡 Bu komanda faqat adminlar uchun.")
        return False
    return True

def display_user(p):
    if p.get("username"):
        return "@" + p["username"]
    elif p.get("first_name"):
        return p["first_name"]
    return "Unknown"

# =========================================================
# 4. GENERAL HANDLERS
# =========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username

    text = (
        f"🩸 <b>Salom, {user.first_name}!</b>\n\n"
        "Men <b>HyakkimaruBot</b> — guruhlarni boshqarish uchun "
        "professional botman.\n\n"
        "🛡️ <b>Imkoniyatlar:</b>\n"
        "• Guruh moderatsiyasi\n"
        "• Warn / Mute / Ban\n"
        "• Filtrlar\n"
        "• Qoidalar va Welcome\n"
        "• Statistika va profil\n\n"
        "Barcha komandalar ro'yxatini ko'rish uchun /help bosing."
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Meni guruhga qo'shish", 
                url=f"https://t.me/{bot_username}?startgroup=true"
            )
        ]
    ]

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🩸 <b>HyakkimaruBot Komandalar Ro'yxati:</b>\n\n"
        "<b>Asosiy:</b>\n"
        "/start - Botni ishga tushirish\n"
        "/help - Yordam va komandalar\n"
        "/settings - Bot sozlamalari\n"
        "/id - Siz va guruh ID si\n"
        "/info - User haqida ma'lumot\n\n"
        "<b>Moderatsiya:</b>\n"
        "/warn - Ogohlantirish berish (Reply)\n"
        "/warnings - Ogohlantirishlarni ko'rish\n"
        "/mute - Yozishni taqiqlash (Reply)\n"
        "/unmute - Taqiqni olib tashlash (Reply)\n"
        "/ban - Ban berish (Reply)\n"
        "/unban [user_id] - Bandan chiqarish\n"
        "/kick - Guruhdan chiqarish (Reply)\n"
        "/purge [soni] - Xabarlarni o'chirish\n"
        "/pin - Xabarni qasqichlash (Reply)\n"
        "/unpin - Qasqichni olib tashlash\n\n"
        "<b>Sozlamalar va Filtrlar:</b>\n"
        "/rules - Guruh qoidalari\n"
        "/setrules [matn] - Qoidalarni o'rnatish\n"
        "/welcome - Kirish xabarini sozlash\n"
        "/filter [so'z] [javob] - Filtr qo'shish\n"
        "/filters - Barcha filtrlar\n"
        "/filterdel [so'z] - Filtrni o'chirish\n"
        "/lock /unlock - Cheklovlar\n\n"
        "<b>Statistika:</b>\n"
        "/profile - Sizning profilingiz\n"
        "/top - Guruh reytingi\n"
        "<code>.active</code> - Reply qilingan foydalanuvchi statistikasi"
    )
    await update.effective_message.reply_text(text, parse_mode="HTML")

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        f"👤 <b>User ID:</b> <code>{update.effective_user.id}</code>\n"
        f"💬 <b>Chat ID:</b> <code>{update.effective_chat.id}</code>",
        parse_mode="HTML"
    )

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = get_rules(update.effective_chat.id)
    msg = r if r else "Ushbu guruhda hali qoidalar o'rnatilmagan."
    await update.effective_message.reply_text(f"📜 <b>Guruh qoidalari:</b>\n\n{msg}", parse_mode="HTML")

async def setrules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): 
        return
    if not context.args:
        await update.effective_message.reply_text("Foydalanish: /setrules Qoidalar matni")
        return
    text = " ".join(context.args)
    set_rules(update.effective_chat.id, text)
    await update.effective_message.reply_text("✅ Guruh qoidalari muvaffaqiyatli saqlandi.")

async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): 
        return
    if not update.effective_message.reply_to_message:
        await update.effective_message.reply_text("Reply qilib /pin yozing.")
        return
    await context.bot.pin_chat_message(
        update.effective_chat.id,
        update.effective_message.reply_to_message.message_id
    )
    await update.effective_message.reply_text("📌 Xabar qistirildi.")

async def unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): 
        return
    await context.bot.unpin_chat_message(update.effective_chat.id)
    await update.effective_message.reply_text("📌 Qasqich olib tashlandi.")

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = (update.effective_message.reply_to_message.from_user 
         if update.effective_message.reply_to_message else update.effective_user)
    text = f"👤 <b>Ism:</b> {u.full_name}\n🆔 <b>ID:</b> <code>{u.id}</code>"
    if u.username: 
        text += f"\n🌐 <b>Username:</b> @{u.username}"
    await update.effective_message.reply_text(text, parse_mode="HTML")
# =========================================================
# 5. MODERATION
# =========================================================
async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): 
        return
    m = update.effective_message
    if not m.reply_to_message:
        await m.reply_text("Foydalanish: foydalanuvchi xabariga reply qilib /warn")
        return
    u = m.reply_to_message.from_user
    ensure_user(u.id, u.username, u.first_name, u.last_name)
    ensure_chat(update.effective_chat.id, update.effective_chat.title or "", update.effective_chat.type)
    touch(update.effective_chat.id, u.id)
    n = add_warning(update.effective_chat.id, u.id)
    await m.reply_text(f"⚠️ {u.mention_html()} ogohlantirildi.\nUmumiy ogohlantirishlar: <b>{n}</b>", parse_mode="HTML")

async def warnings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.effective_message
    u = m.reply_to_message.from_user if m.reply_to_message else update.effective_user
    cnt = warnings_count(update.effective_chat.id, u.id)
    await m.reply_text(f"⚠️ {u.mention_html()} — ogohlantirishlar soni: <b>{cnt}</b>", parse_mode="HTML")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): 
        return
    m = update.effective_message
    if not m.reply_to_message:
        await m.reply_text("Reply qilib /mute yozing.")
        return
    u = m.reply_to_message.from_user
    await context.bot.restrict_chat_member(
        update.effective_chat.id, u.id,
        permissions=ChatPermissions(can_send_messages=False)
    )
    await m.reply_text(f"🔇 {u.mention_html()} yozishdan mahrum qilindi.", parse_mode="HTML")

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): 
        return
    m = update.effective_message
    if not m.reply_to_message:
        await m.reply_text("Reply qilib /unmute yozing.")
        return
    u = m.reply_to_message.from_user
    await context.bot.restrict_chat_member(
        update.effective_chat.id, u.id,
        permissions=ChatPermissions(
            can_send_messages=True, can_send_audios=True, can_send_documents=True,
            can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
            can_send_voice_notes=True, can_send_polls=True,
            can_send_other_messages=True, can_add_web_page_previews=True
        )
    )
    await m.reply_text(f"🔊 {u.mention_html()} yana yozishi mumkin.", parse_mode="HTML")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): 
        return
    m = update.effective_message
    if not m.reply_to_message:
        await m.reply_text("Reply qilib /ban yozing.")
        return
    u = m.reply_to_message.from_user
    await context.bot.ban_chat_member(update.effective_chat.id, u.id)
    await m.reply_text(f"🔨 {u.mention_html()} guruhdan ban qilindi.", parse_mode="HTML")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): 
        return
    if not context.args:
        await update.effective_message.reply_text("Foydalanish: /unban USER_ID")
        return
    try: 
        uid = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("USER_ID raqam bo'lishi kerak.")
        return
    await context.bot.unban_chat_member(update.effective_chat.id, uid, only_if_banned=True)
    await update.effective_message.reply_text("✅ Foydalanuvchi bandan chiqarildi.")

async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): 
        return
    m = update.effective_message
    if not m.reply_to_message:
        await m.reply_text("Reply qilib /kick yozing.")
        return
    u = m.reply_to_message.from_user
    await context.bot.ban_chat_member(update.effective_chat.id, u.id)
    await context.bot.unban_chat_member(update.effective_chat.id, u.id)
    await m.reply_text(f"👢 {u.mention_html()} guruhdan chiqarib yuborildi.", parse_mode="HTML")

async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): 
        return
    m = update.effective_message
    try: 
        n = int(context.args[0]) if context.args else 10
    except ValueError: 
        n = 10
    n = max(1, min(n, 100))
    for mid in range(max(1, m.message_id - n), m.message_id + 1):
        try: 
            await context.bot.delete_message(m.chat_id, mid)
        except Exception: 
            pass

# =========================================================
# 6. SETTINGS
# =========================================================
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): 
        return
    w = get_welcome(update.effective_chat.id)
    kb = [
        [InlineKeyboardButton("👋 Welcome ON/OFF", callback_data="set:welcome")],
        [InlineKeyboardButton("🔒 Lock links", callback_data="set:links")],
        [InlineKeyboardButton("🚫 Lock media", callback_data="set:media")]
    ]
    await update.effective_message.reply_text(
        f"⚙️ <b>HyakkimaruBot Sozlamalari</b>\n\nWelcome holati: <b>{'YOQILGAN' if w['welcome_enabled'] else 'O`CHIRILGAN'}</b>",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="HTML"
    )

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await is_admin(update, context):
        await q.answer("Faqat adminlar foydalana oladi.", show_alert=True)
        return
    chat_id = q.message.chat_id
    action = q.data.split(":")[1]
    if action == "welcome":
        w = get_welcome(chat_id)
        set_welcome(chat_id, not bool(w["welcome_enabled"]))
    else:
        set_lock(chat_id, action, not get_lock(chat_id, action))
    await q.edit_message_text("⚙️ Sozlama yangilandi. /settings orqali qayta tekshirishingiz mumkin.")

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): 
        return
    if not context.args:
        w = get_welcome(update.effective_chat.id)
        await update.effective_message.reply_text(
            f"👋 Welcome holati: <b>{'ON' if w['welcome_enabled'] else 'OFF'}</b>\n\n"
            "Buyruqlar:\n"
            "/welcome on\n"
            "/welcome off\n"
            "/welcome text Sizga xush kelibsiz, {user}!",
            parse_mode="HTML"
        )
        return
    arg = context.args[0].lower()
    if arg in ("on", "off"):
        set_welcome(update.effective_chat.id, arg == "on")
        await update.effective_message.reply_text("✅ Welcome holati saqlandi.")
    elif arg == "text" and len(context.args) > 1:
        text = " ".join(context.args[1:])
        set_welcome(update.effective_chat.id, True, text)
        await update.effective_message.reply_text("✅ Yangi welcome matni saqlandi.")

async def filter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): 
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Foydalanish: /filter [kalit_so'z] [javob_matni]")
        return
    add_filter(update.effective_chat.id, context.args[0], " ".join(context.args[1:]))
    await update.effective_message.reply_text("🚫 Yangi filtr muvaffaqiyatli saqlandi.")

async def filters_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_filters(update.effective_chat.id)
    if rows:
        msg = "\n".join(f"• <b>{r['word']}</b>" for r in rows)
    else:
        msg = "Hozircha hech qanday filtr yo'q."
    await update.effective_message.reply_text(f"🚫 <b>Guruh filtrlar ro'yxati:</b>\n\n{msg}", parse_mode="HTML")

async def filter_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): 
        return
    if not context.args:
        await update.effective_message.reply_text("Foydalanish: /filterdel [kalit_so'z]")
        return
    remove_filter(update.effective_chat.id, context.args[0])
    await update.effective_message.reply_text("✅ Filtr o'chirildi.")

async def lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): 
        return
    feature = context.args[0] if context.args else "links"
    set_lock(update.effective_chat.id, feature, True)
    await update.effective_message.reply_text(f"🔒 <b>{feature}</b> qulflandi.", parse_mode="HTML")

async def unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): 
        return
    feature = context.args[0] if context.args else "links"
    set_lock(update.effective_chat.id, feature, False)
    await update.effective_message.reply_text(f"🔓 <b>{feature}</b> qulfdan chiqarildi.", parse_mode="HTML")

# =========================================================
# 7. PROFILE / RANK
# =========================================================
async def active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.effective_message
    if not m.reply_to_message:
        await m.reply_text("🩸 <code>.active</code> buyrug'i boshqa foydalanuvchi xabariga reply qilib yoziladi.", parse_mode="HTML")
        return
    u = m.reply_to_message.from_user
    p = profile(update.effective_chat.id, u.id)
    if not p:
        await m.reply_text("Ushbu foydalanuvchi haqida guruhda ma'lumot topilmadi.")
        return
    gs = game_stats(update.effective_chat.id, u.id)
    await m.reply_text(
        f"🩸 <b>Foydalanuvchi:</b> {display_user(p)}\n\n"
        f"🎮 <b>O'yin Statistikasi:</b>\n"
        f"🎯 Jami o'yinlar: <b>{p['games']:,}</b>\n"
        f"🏆 G'alabalar: <b>{gs['wins']:,}</b>\n"
        f"💀 Mag'lubiyat/O'limlar: <b>{gs['deaths']:,}</b>\n\n"
        f"⚡ XP ballari: <b>{p['xp']:,}</b>\n"
        f"💬 Jami xabarlar: <b>{p['messages']:,}</b>\n"
        f"🏆 Guruhdagi o'rni: <b>#{rank(update.effective_chat.id, u.id)}</b>",
        parse_mode="HTML"
    )

async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = (update.effective_message.reply_to_message.from_user 
         if update.effective_message.reply_to_message else update.effective_user)
    p = profile(update.effective_chat.id, u.id)
    if not p:
        await update.effective_message.reply_text(f"👤 <b>{u.full_name}</b>\n🆔 ID: <code>{u.id}</code>", parse_mode="HTML")
        return
    gs = game_stats(update.effective_chat.id, u.id)
    await update.effective_message.reply_text(
        f"👤 <b>Foydalanuvchi:</b> {display_user(p)}\n"
        f"🆔 ID: <code>{u.id}</code>\n\n"
        f"🎮 O'yinlar: <b>{p['games']:,}</b>\n"
        f"🏆 G'alabalar: <b>{gs['wins']:,}</b>\n"
        f"💀 O'limlar: <b>{gs['deaths']:,}</b>\n"
        f"⚡ XP: <b>{p['xp']:,}</b>\n"
        f"💬 Xabarlar: <b>{p['messages']:,}</b>\n"
        f"🏆 Guruh Ranki: <b>#{rank(update.effective_chat.id, u.id)}</b>",
        parse_mode="HTML"
    )

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = top_players(update.effective_chat.id)
    if not rows:
        await update.effective_message.reply_text("🏆 Reyting ro'yxati hali bo'sh.")
        return
    lines = ["🏆 <b>GURUH TOP — O'YINLAR BO'YICHA REYTING:</b>\n"]
    for i, r in enumerate(rows, 1):
        name = "@" + r["username"] if r["username"] else r["first_name"]
        lines.append(f"<b>{i}.</b> {name} — 🎮 <b>{r['games']:,}</b> ta o'yin")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")

# =========================================================
# 8. EVENTS / MESSAGE TRACKING
# =========================================================
async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.effective_chat
    w = get_welcome(c.id)
    if not w["welcome_enabled"]: 
        return
    for u in update.effective_message.new_chat_members:
        text = w["welcome_text"].replace("{user}", u.mention_html()).replace("{name}", u.first_name or "")
        await update.effective_message.reply_text(text, parse_mode="HTML")

async def filter_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.effective_message
    if not m or not m.text or not update.effective_chat: 
        return
    response = find_filter(update.effective_chat.id, m.text)
    if response: 
        await m.reply_text(response)

async def track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.effective_message
    c = update.effective_chat
    u = update.effective_user
    if not m or not c or not u or c.type not in ("group", "supergroup"): 
        return
    ensure_chat(c.id, c.title or "", c.type)
    ensure_user(u.id, u.username, u.first_name, u.last_name)
    touch(c.id, u.id)
    record_message(c.id, u.id)

# =========================================================
# 9. BLACKWWROBOT GAME TRACKER
# =========================================================
PLAYERS_HEADER = re.compile(r"#players\s*:\s*(\d+)", re.I)
DURATION_RE = re.compile(r"O'yin davomiyligi\s*:\s*(\d{2}:\d{2}:\d{2})", re.I)
FINAL_HEADER = re.compile(r"Tirik o'yinchilar\s*:\s*(\d+)\s*/\s*(\d+)", re.I)
ID_RE = re.compile(r"\(ID:\s*(\d+)\)")
WIN_RE = re.compile(r"Yutdi|g'olib|g‘olib", re.I)
LOSE_RE = re.compile(r"Yutqazdi|mag'lub|mag‘lub", re.I)
DEAD_RE = re.compile(r"💀|O'lgan", re.I)
ALIVE_RE = re.compile(r"🙂|Tirik", re.I)

def clean_name(s):
    s = re.sub(r"\(ID:\s*\d+\)", "", s)
    s = re.sub(r"^\s*[•\-\d.]+\s*", "", s)
    return re.sub(r"\s+", " ", s).strip(" :.-")

def is_blackwwrobot(message):
    u = message.from_user
    if not u: 
        return False
    vals = ((u.username or "") + " " + (u.first_name or "")).lower()
    return "blackwwrobot" in vals or "blackwerewolf" in vals

async def track_blackwwrobot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.effective_message
    if not m or not m.text or not update.effective_chat or not is_blackwwrobot(m):
        return
    text = m.text
    chat_id = m.chat_id

    header = PLAYERS_HEADER.search(text)
    if header:
        expected = int(header.group(1))
        lines = [clean_name(x) for x in text.splitlines() if x.strip()]
        ids = [int(x) for x in ID_RE.findall(text)]
        names = []
        for line in lines:
            if line.lower().startswith("#players"): 
                continue
            if line and len(line) < 80 and any(x in line for x in ("🥇", "🥈", "🥉")):
                line = re.sub(r"[🥇🥈🥉]", "", line).strip()
                if line: 
                    names.append(line)

        players = []
        for i, name in enumerate(names[:expected]):
            if i < len(ids):
                uid = ids[i]
                ensure_user(uid, None, name, None)
                touch(chat_id, uid)
                players.append((uid, name))
        if players:
            game_start(chat_id, m.message_id, players)
        return

    if DURATION_RE.search(text) or (
        FINAL_HEADER.search(text) and ("Yutdi" in text or "Yutqazdi" in text)
    ):
        if not game_is_active(chat_id): 
            return
        registered = game_players(chat_id)
        if not registered: 
            return

        outcomes = []
        for p in registered:
            name = p["display_name"]
            matched = next(
                (line for line in text.splitlines()
                 if re.search(re.escape(name), line, re.I)), None
            )
            if matched:
                alive = bool(ALIVE_RE.search(matched)) and not bool(DEAD_RE.search(matched))
                won = bool(WIN_RE.search(matched)) and not bool(LOSE_RE.search(matched))
            else:
                alive, won = True, False
            outcomes.append((p["user_id"], won, alive))
        finish_game(chat_id, outcomes)

# =========================================================
# 10. CHAT MEMBER / ERRORS
# =========================================================
async def my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cm = update.my_chat_member
    if not cm: 
        return
    if cm.new_chat_member.status in ("member", "administrator"):
        ensure_chat(cm.chat.id, cm.chat.title or "", cm.chat.type)
        await context.bot.send_message(
            cm.chat.id, "🩸 HyakkimaruBot guruhga muvaffaqiyatli ulandi!\nKomandalar ro'yxati uchun /help deb yozing."
        )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Unhandled exception:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("🩸 Amalni bajarishda kutilmagan xatolik yuz berdi.")
        except Exception:
            pass

# =========================================================
# 11. BUILD / RUN
# =========================================================
def build():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(ChatMemberHandler(
        my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER
    ))

    commands = {
        "start": start, "help": help_cmd, "settings": settings,
        "warn": warn, "warnings": warnings_cmd, "mute": mute, "unmute": unmute,
        "ban": ban, "unban": unban, "kick": kick, "purge": purge,
        "pin": pin, "unpin": unpin, "id": id_cmd, "info": info,
        "rules": rules, "setrules": setrules_cmd, "welcome": welcome,
        "filter": filter_cmd, "filters": filters_cmd, "filterdel": filter_delete,
        "lock": lock, "unlock": unlock, "top": top, "profile": profile_cmd
    }
    for cmd, fn in commands.items():
        app.add_handler(CommandHandler(cmd, fn))

    app.add_handler(CallbackQueryHandler(settings_callback, pattern=r"^set:"))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & ~filters.COMMAND,
            filter_message
        ),
        group=5
    )

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & ~filters.COMMAND,
            track_blackwwrobot
        ),
        group=6
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"(?i)^\.active(?:@\w+)?$"),
            active
        )
    )

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & ~filters.COMMAND,
            track
        ),
        group=10
    )

    app.add_error_handler(error_handler)
    return app

if __name__ == "__main__":
    init_db()
    log.info("🩸 HyakkimaruBot started successfully")
    build().run_polling(allowed_updates=Update.ALL_TYPES)
