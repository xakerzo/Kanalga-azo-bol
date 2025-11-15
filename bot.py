import logging
import sqlite3
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters
)

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_OWNER_ID = 1373647

# DB yaratish
def init_db():
    try:
        conn = sqlite3.connect('channel_bot.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_settings (
                group_id INTEGER PRIMARY KEY,
                channel_username TEXT,
                welcome_message TEXT DEFAULT '❗️ Iltimos, avval kanalga obuna boʻling!',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("Ma'lumotlar bazasi yaratildi")
    except sqlite3.OperationalError as e:
        logger.warning(f"Ma'lumotlar bazasi yaratishda xatolik: {e}")

def get_group_settings(group_id):
    try:
        conn = sqlite3.connect('channel_bot.db')
        cursor = conn.cursor()
        cursor.execute(
            'SELECT channel_username, welcome_message FROM group_settings WHERE group_id = ?',
            (group_id,)
        )
        result = cursor.fetchone()
        conn.close()
        if result:
            return {'channel_username': result[0], 'welcome_message': result[1]}
    except sqlite3.OperationalError as e:
        logger.warning(f"Guruh sozlamalarini olishda xatolik: {e}")
    return None

def save_group_settings(group_id, channel_username, welcome_message=None):
    if welcome_message is None:
        welcome_message = '❗️ Iltimos, avval kanalga obuna boʻling!'
    try:
        conn = sqlite3.connect('channel_bot.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO group_settings
            (group_id, channel_username, welcome_message)
            VALUES (?, ?, ?)
        ''', (group_id, channel_username, welcome_message))
        conn.commit()
        conn.close()
        logger.info(f"Guruh {group_id} sozlamalari saqlandi")
    except sqlite3.OperationalError as e:
        logger.warning(f"Guruh sozlamalarini saqlashda xatolik: {e}")

def delete_group_settings(group_id):
    try:
        conn = sqlite3.connect('channel_bot.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM group_settings WHERE group_id = ?', (group_id,))
        conn.commit()
        conn.close()
        logger.info(f"Guruh {group_id} sozlamalari o'chirildi")
    except sqlite3.OperationalError as e:
        logger.warning(f"Sozlamalarni o'chirishda xatolik: {e}")

async def check_channel_membership(user_id, channel_username, context):
    try:
        if not channel_username.startswith('@'):
            channel_username = '@' + channel_username
        member = await context.bot.get_chat_member(channel_username, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.warning(f"A'zolik tekshirish xatosi: {e}")
        return False

def is_owner(user_id):
    return user_id == BOT_OWNER_ID

# --- Foydalanuvchi xabari va kanal tekshiruv --- #
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return

    chat = update.effective_chat
    user = update.effective_user
    settings = get_group_settings(chat.id)
    if not settings:
        return

    # Adminlar erkin
    try:
        member = await chat.get_member(user.id)
        if member.status in ['administrator', 'creator']:
            return
    except:
        pass

    is_member = await check_channel_membership(user.id, settings['channel_username'], context)
    if not is_member:
        try:
            warning_msg = await update.message.reply_text(
                f"👋 {user.mention_html()}\n{settings['welcome_message']}\n📢 Kanal: {settings['channel_username']}",
                parse_mode='HTML'
            )

            # foydalanuvchi xabarini 2s keyin o'chirish
            async def delete_user(ctx):
                try:
                    await context.bot.delete_message(update.message.chat_id, update.message.message_id)
                except: pass
            await context.job_queue.run_once(delete_user, 2)

            # ogohlantirish 20s keyin o'chiriladi
            async def delete_warning(ctx):
                try:
                    await context.bot.delete_message(warning_msg.chat_id, warning_msg.message_id)
                except: pass
            await context.job_queue.run_once(delete_warning, 20)

        except Exception as e:
            logger.warning(f"Xabarni o'chirish yoki ogohlantirish xatosi: {e}")

# --- Owner uchun broadcast --- #
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("❌ Bu buyruq faqat bot owneri uchun!")
        return
    if not context.args:
        await update.message.reply_text("ℹ️ Foydalanish: /broadcast <xabar matni>")
        return
    message_text = ' '.join(context.args)

    # Ownerga xabar berish
    await update.message.reply_text(f"📢 Broadcast yuborildi owner tomonidan:\n{message_text}")

    # Guruhlarga yuborish
    try:
        conn = sqlite3.connect('channel_bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT group_id FROM group_settings')
        groups = cursor.fetchall()
        conn.close()
    except sqlite3.OperationalError as e:
        logger.warning(f"Broadcast uchun guruhlarni olishda xatolik: {e}")
        groups = []

    for group in groups:
        try:
            await context.bot.send_message(chat_id=group[0], text=f"📢 Bot yangiligi:\n\n{message_text}")
        except Exception as e:
            logger.warning(f"Guruh {group[0]} ga xabar yuborish xatosi: {e}")

# --- Asosiy funksiya --- #
def main():
    init_db()
    BOT_TOKEN = "8227647066:AAHVl028wisNavIs1f8e-CYB97NDTB6RAhU"
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text("Bot ishga tushdi")))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    print("🤖 Bot ishga tushdi...")
    application.run_polling()

if __name__ == "__main__":
    main()
