# bot.py
import os
import logging
import sqlite3
from typing import Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ----------------- CONFIG ----------------- #
# Tavsiya: Railway da environment variables sifatida saqlang
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8227647066:AAHVl028wisNavIs1f8e-CYB97NDTB6RAhU")
# Agar OWNER ID ni env dan olmoqchi bo'lsangiz: os.environ.get("BOT_OWNER_ID")
BOT_OWNER_ID = int(os.environ.get("BOT_OWNER_ID", "1373647"))

# DB fayl nomi
DB_FILENAME = "channel_bot.db"

# Ogohlantirish xabari uchun default matn (har guruh uchun alohida saqlanadi)
DEFAULT_WELCOME = "❗️ Iltimos, avval kanalga obuna boʻling!"

# Ogohlantirish qancha sekunddan keyin o'chadi
WARNING_DELETE_SECONDS = 10
# ------------------------------------------ #

# Logging sozlamalari
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ----------------- DATABASE HELPERS ----------------- #
def init_db() -> None:
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS group_settings (
            group_id INTEGER PRIMARY KEY,
            channel_username TEXT,
            welcome_message TEXT DEFAULT ?
        )
        """,
        (DEFAULT_WELCOME,),
    )
    conn.commit()
    conn.close()
    logger.info("Ma'lumotlar bazasi ishga tushdi va tekshirildi.")


def get_group_settings(group_id: int) -> Optional[dict]:
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT channel_username, welcome_message FROM group_settings WHERE group_id = ?",
        (group_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"channel_username": row[0], "welcome_message": row[1]}
    return None


def save_group_settings(group_id: int, channel_username: str, welcome_message: Optional[str] = None) -> None:
    if welcome_message is None:
        welcome_message = DEFAULT_WELCOME
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO group_settings (group_id, channel_username, welcome_message)
        VALUES (?, ?, ?)
        """,
        (group_id, channel_username, welcome_message),
    )
    conn.commit()
    conn.close()
    logger.info("Guruh %s uchun sozlamalar saqlandi: %s", group_id, channel_username)


def delete_group_settings(group_id: int) -> None:
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM group_settings WHERE group_id = ?", (group_id,))
    conn.commit()
    conn.close()
    logger.info("Guruh %s uchun sozlamalar o'chirildi", group_id)


# ----------------- HELPERS ----------------- #
async def check_channel_membership(user_id: int, channel_username: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    channel_username shu ko'rinishda bo'lishi mumkin: '@channelname' yoki 'channelname'
    """
    try:
        if not channel_username.startswith("@"):
            channel_username = "@" + channel_username
        member = await context.bot.get_chat_member(channel_username, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.debug("A'zolikni tekshirish xatosi: %s", e)
        return False


def is_owner(user_id: int) -> bool:
    return user_id == BOT_OWNER_ID


def get_settings_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📢 Kanal qo'shish", callback_data="add_channel")],
        [InlineKeyboardButton("✏️ Xabarni o'zgartirish", callback_data="set_welcome")],
        [InlineKeyboardButton("🗑 Sozlamalarni o'chirish", callback_data="remove_settings")],
        [InlineKeyboardButton("ℹ️ Sozlamalarni ko'rish", callback_data="view_settings")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ----------------- COMMAND HANDLERS ----------------- #
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat

    if chat.type == "private":
        if is_owner(user.id):
            await update.message.reply_text(
                "👑 Salom Owner!\n\n"
                "/stats - Bot statistika\n"
                "/broadcast - Barcha guruhlarga xabar\n"
                "/myid - ID ni ko'rish"
            )
        else:
            await update.message.reply_text(
                "👋 Salom!\n\n"
                "Men — guruhda faqat belgilangan kanalga a'zo bo'lganlar yozishiga ruxsat beruvchi botman.\n"
                "Botni guruhga qoʻshing va admin qiling, soʻng /settings orqali kanalni belgilang."
            )
        return

    # Guruhda: faqat adminlarga panel ko'rinishini ko'rsatamiz
    try:
        member = await chat.get_member(user.id)
        if member.status not in ["administrator", "creator"]:
            await update.message.reply_text("❌ Faqat adminlar sozlamalarni o'zgartirishi mumkin!")
            return
    except Exception as e:
        logger.error("Admin tekshiruvi xatosi: %s", e)
        await update.message.reply_text("❌ Xatolik yuz berdi!")
        return

    await update.message.reply_text("⚙️ Guruh sozlamalari", reply_markup=get_settings_keyboard())


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Bu buyruq faqat guruhlarda ishlaydi!")
        return

    # admin tekshiruv
    user = update.effective_user
    try:
        member = await chat.get_member(user.id)
        if member.status not in ["administrator", "creator"]:
            await update.message.reply_text("❌ Faqat adminlar sozlamalarni o'zgartirishi mumkin!")
            return
    except Exception as e:
        logger.error("Admin tekshiruvi xatosi: %s", e)
        await update.message.reply_text("❌ Xatolik yuz berdi!")
        return

    settings = get_group_settings(chat.id)
    if settings:
        text = (
            f"📋 Joriy sozlamalar:\n\n"
            f"📢 Kanal: {settings['channel_username']}\n"
            f"💬 Xabar: {settings['welcome_message']}\n\n"
            "Quyidagi tugmalar orqali o'zgartiring:"
        )
    else:
        text = (
            "⚠️ Hech qanday sozlama topilmadi.\n\n"
            "Bot hozir barcha foydalanuvchilarga yozishga ruxsat beradi.\n"
            "Kanal sozlamalarini o'rnatish uchun quyidagi tugmalardan foydalaning:"
        )

    await update.message.reply_text(text, reply_markup=get_settings_keyboard())


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("❌ Bu buyruq faqat bot owneri uchun!")
        return

    if not context.args:
        await update.message.reply_text("ℹ️ Foydalanish: /broadcast <xabar matni>")
        return

    message_text = " ".join(context.args)

    conn = sqlite3.connect(DB_FILENAME)
    cur = conn.cursor()
    cur.execute("SELECT group_id FROM group_settings")
    groups = cur.fetchall()
    conn.close()

    sent = 0
    failed = 0
    for g in groups:
        gid = g[0]
        try:
            await context.bot.send_message(chat_id=gid, text=f"📢 Bot yangiligi:\n\n{message_text}")
            sent += 1
        except Exception as e:
            logger.error("Broadcast xatosi %s: %s", gid, e)
            failed += 1

    await update.message.reply_text(f"✅ Yuborildi: {sent}\n❌ Xatolik: {failed}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("❌ Bu buyruq faqat bot owneri uchun!")
        return

    conn = sqlite3.connect(DB_FILENAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM group_settings")
    groups_count = cur.fetchone()[0]

    cur.execute(
        """
        SELECT channel_username, COUNT(*) as cnt
        FROM group_settings
        GROUP BY channel_username
        ORDER BY cnt DESC
        LIMIT 5
        """
    )
    top = cur.fetchall()
    conn.close()

    text = f"🤖 Bot statistika\n\n🔧 Faol guruhlar: {groups_count}\n\n📈 Top kanallar:\n"
    for ch, cnt in top:
        text += f"• {ch}: {cnt} guruh\n"
    await update.message.reply_text(text)


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(f"Sizning ID: {user.id}")


# ----------------- CALLBACK QUERY HANDLER (BUTTONS) ----------------- #
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id
    message_id = query.message.message_id

    # set waiting flags in chat_data (so only admins can use)
    if data == "add_channel":
        await query.edit_message_text(
            "📢 Kanal username ni yuboring (@ bilan). Masalan: @MyChannel\n"
            "Eslatma: Bot kanalga admin bo'lishi shart emas, faqat a'zolik tekshiriladi."
        )
        context.chat_data["waiting_for_channel"] = True
        context.chat_data["editing_message_id"] = message_id

    elif data == "set_welcome":
        await query.edit_message_text(
            "✏️ Iltimos, chiqariladigan ogohlantirish matnini yozing.\n"
            "Masalan: ❗️ Iltimos, avval @MyChannel kanaliga obuna bo'ling!"
        )
        context.chat_data["waiting_for_welcome"] = True
        context.chat_data["editing_message_id"] = message_id

    elif data == "remove_settings":
        delete_group_settings(chat_id)
        await query.edit_message_text("✅ Sozlamalar o'chirildi! Endi barcha yozishi mumkin.")

    elif data == "view_settings":
        settings = get_group_settings(chat_id)
        if settings:
            text = f"📋 Sozlamalar:\n\n📢 Kanal: {settings['channel_username']}\n💬 Xabar: {settings['welcome_message']}"
        else:
            text = "⚠️ Sozlama topilmadi."
        await query.edit_message_text(text, reply_markup=get_settings_keyboard())


# ----------------- MESSAGE HANDLER ----------------- #
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Agar xabar bot tomonidan yuborilgan bo'lsa o'tkazib yuborish
    if update.message is None or update.message.from_user is None:
        return
    if update.message.from_user.is_bot:
        return

    chat = update.effective_chat
    user = update.effective_user

    # Agar shaxsiy chat bo'lsa - ko'rsatma beramiz
    if chat.type == "private":
        await update.message.reply_text("Botni guruhga qo'shing va /settings orqali kanalni sozlang.")
        return

    # Agar guruhda adminlar sozlash jarayonida bo'lsa (chat_data dan)
    if context.chat_data.get("waiting_for_channel"):
        # Admin yuborgan yangi kanal username
        text = update.message.text.strip()
        if not text.startswith("@"):
            await update.message.reply_text("❌ Iltimos, kanal username @ bilan boshlansin (masalan: @MyChannel).")
            return
        try:
            chat_info = await context.bot.get_chat(text)
            if chat_info.type != "channel":
                await update.message.reply_text("❌ Bu kanal emas. Iltimos haqiqiy kanal username yuboring.")
                return
            save_group_settings(chat.id, text)
            # har holda tahrir xabarini o'chirishga harakat qilamiz
            try:
                editing_id = context.chat_data.get("editing_message_id")
                if editing_id:
                    await context.bot.delete_message(chat.id, editing_id)
            except Exception:
                pass
            await update.message.reply_text(f"✅ Kanal saqlandi: {text}")
        except Exception as e:
            logger.error("Kanal tekshirish xatosi: %s", e)
            await update.message.reply_text("❌ Kanal topilmadi yoki bot uni ko'rolmadi.")
        # tozalash
        context.chat_data.pop("waiting_for_channel", None)
        context.chat_data.pop("editing_message_id", None)
        return

    if context.chat_data.get("waiting_for_welcome"):
        text = update.message.text
        settings = get_group_settings(chat.id)
        if not settings:
            await update.message.reply_text("❌ Avval kanalni sozlang (📢 Kanal qo'shish).")
            context.chat_data.pop("waiting_for_welcome", None)
            context.chat_data.pop("editing_message_id", None)
            return
        save_group_settings(chat.id, settings["channel_username"], text)
        try:
            editing_id = context.chat_data.get("editing_message_id")
            if editing_id:
                await context.bot.delete_message(chat.id, editing_id)
        except Exception:
            pass
        await update.message.reply_text("✅ Xabar saqlandi!")
        context.chat_data.pop("waiting_for_welcome", None)
        context.chat_data.pop("editing_message_id", None)
        return

    # Oddiy xabarlarni tekshirish uchun sozlamalarni olish
    settings = get_group_settings(chat.id)
    if not settings:
        # Agar sozlama yo'q bo'lsa - hech qanday cheklov yo'q
        return

    # Adminlarni chetlab o'tish (ularga ruxsat beramiz)
    try:
        member = await chat.get_member(user.id)
        if member.status in ["administrator", "creator"]:
            return
    except Exception:
        # Agar tekshirishda xato bo'lsa davom etamiz (safe default)
        pass

    # A'zolikni tekshirish
    is_member = await check_channel_membership(user.id, settings["channel_username"], context)
    if is_member:
        # a'zo bo'lsa - hech qanday cheklov yo'q
        return

    # Agar a'zo bo'lmasa: xabarni O'CHIRISH, ogohlantirish yuborish va 10s keyin o'chirish
    try:
        await update.message.delete()
    except Exception as e:
        logger.debug("Xabarni o'chirishda muammo: %s", e)

    try:
        # Ogohlantirishni bot orqali yuborish (reply emas, chunki original xabar o'chirilgan)
        warning_msg = await context.bot.send_message(
            chat_id=chat.id,
            text=f"👋 {user.mention_html()}\n{settings['welcome_message']}",
            parse_mode=ParseMode.HTML,
        )

        # Job qo'yamiz: WARNING_DELETE_SECONDS dan keyin ogohlantirishni o'chiramiz
        async def delete_warning_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
            try:
                await ctx.bot.delete_message(warning_msg.chat_id, warning_msg.message_id)
            except Exception:
                pass

        context.job_queue.run_once(delete_warning_job, WARNING_DELETE_SECONDS)

    except Exception as e:
        logger.error("Ogohlantirish yuborishda xato: %s", e)


# ----------------- ERROR HANDLER ----------------- #
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled error: %s", context.error, exc_info=context.error)


# ----------------- MAIN ----------------- #
async def main() -> None:
    # DB init
    init_db()

    # Application
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("myid", myid_command))

    # Callback / buttons
    app.add_handler(CallbackQueryHandler(button_handler))

    # Messages (faqat matn, komandalar tashqari)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Error handler
    app.add_error_handler(error_handler)

    logger.info("Bot ishga tushmoqda...")
    # run_polling() ni await qilyapmiz - asyncio kontekstida ishlaydi
    await app.run_polling()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
