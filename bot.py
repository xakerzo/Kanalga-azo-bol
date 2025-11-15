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

# 🔑 BOT OWNER ID
BOT_OWNER_ID = 1373647

# Ma'lumotlar bazasini yaratish
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

# Guruh sozlamalarini olish
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

# Guruh sozlamalarini saqlash
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

# Sozlamalarni o'chirish
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

# Kanal a'zoligini tekshirish
async def check_channel_membership(user_id, channel_username, context):
    try:
        if not channel_username.startswith('@'):
            channel_username = '@' + channel_username
        member = await context.bot.get_chat_member(channel_username, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.warning(f"A'zolik tekshirish xatosi: {e}")
        return False

# Owner ekanligini tekshirish
def is_owner(user_id):
    return user_id == BOT_OWNER_ID

# Broadcast komandasi
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("❌ Bu buyruq faqat bot owneri uchun!")
        return
    if not context.args:
        await update.message.reply_text("ℹ️ Foydalanish: /broadcast <xabar matni>")
        return
    message_text = ' '.join(context.args)
    try:
        conn = sqlite3.connect('channel_bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT group_id FROM group_settings')
        groups = cursor.fetchall()
        conn.close()
    except sqlite3.OperationalError as e:
        logger.warning(f"Broadcast uchun guruhlarni olishda xatolik: {e}")
        groups = []

    sent_count = 0
    failed_count = 0
    for group in groups:
        try:
            await context.bot.send_message(chat_id=group[0], text=f"📢 Bot yangiligi:\n\n{message_text}")
            sent_count += 1
        except Exception as e:
            logger.warning(f"Guruh {group[0]} ga xabar yuborish xatosi: {e}")
            failed_count += 1

    await update.message.reply_text(
        f"✅ Xabar yuborildi!\n✔️ Muvaffaqiyatli: {sent_count}\n❌ Xatolik: {failed_count}"
    )

# Statistika komandasi
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("❌ Bu buyruq faqat bot owneri uchun!")
        return
    try:
        conn = sqlite3.connect('channel_bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM group_settings')
        groups_count = cursor.fetchone()[0]
        cursor.execute('''
            SELECT channel_username, COUNT(*) as count 
            FROM group_settings 
            GROUP BY channel_username 
            ORDER BY count DESC 
            LIMIT 5
        ''')
        popular_channels = cursor.fetchall()
        conn.close()
    except sqlite3.OperationalError as e:
        logger.warning(f"Statistika olishda xatolik: {e}")
        groups_count = 0
        popular_channels = []

    stats_text = f"🤖 Bot Statistika (Owner)\n\n🔧 Faol guruhlar: {groups_count}\n\n📈 Top kanallar:\n"
    for channel, count in popular_channels:
        stats_text += f"• {channel}: {count} guruh\n"
    await update.message.reply_text(stats_text)

# /myid komandasi
async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"Sizning ID: {user.id}")

# Sozlash tugmalari
def get_settings_keyboard():
    keyboard = [
        [InlineKeyboardButton("📢 Kanal qo'shish", callback_data="add_channel")],
        [InlineKeyboardButton("✏️ Xabarni o'zgartirish", callback_data="set_welcome")],
        [InlineKeyboardButton("🗑 Sozlamalarni o'chirish", callback_data="remove_settings")],
        [InlineKeyboardButton("ℹ️ Sozlamalarni ko'rish", callback_data="view_settings")]
    ]
    return InlineKeyboardMarkup(keyboard)

# /start komandasi
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type == 'private':
        if is_owner(user.id):
            await update.message.reply_text(
                f"👑 Salom Owner!\n\nMaxsus buyruqlar:\n/stats\n/broadcast\n/myid"
            )
        else:
            await update.message.reply_text(
                f"👋 Salom {user.first_name}!\nBot guruhda faqat kanalga obuna bo‘lganlarni tekshiradi."
            )
    else:
        try:
            member = await chat.get_member(user.id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Faqat adminlar sozlamalarni o'zgartirishi mumkin!")
                return
        except Exception as e:
            logger.warning(f"Adminlik tekshirish xatosi: {e}")
            await update.message.reply_text("❌ Xatolik yuz berdi!")
            return
        await update.message.reply_text(
            "⚙️ Guruh sozlamalari", reply_markup=get_settings_keyboard()
        )

# Sozlamalar komandasi
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ Bu buyruq faqat guruhlarda ishlaydi!")
        return
    try:
        user = update.effective_user
        member = await chat.get_member(user.id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Faqat adminlar sozlamalarni o'zgartirishi mumkin!")
            return
    except Exception as e:
        logger.warning(f"Adminlik tekshirish xatosi: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi!")
        return
    settings = get_group_settings(chat.id)
    if settings:
        text = f"📋 Joriy sozlamalar:\n📢 Kanal: {settings['channel_username']}\n💬 Xabar: {settings['welcome_message']}"
    else:
        text = "⚠️ Hech qanday sozlama topilmadi."
    await update.message.reply_text(text, reply_markup=get_settings_keyboard())

# Tugma handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id
    message_id = query.message.message_id

    if data == "add_channel":
        await query.edit_message_text("📢 Kanal username ni yuboring (@ bilan):")
        context.user_data['waiting_for_channel'] = True
        context.user_data['editing_message_id'] = message_id

    elif data == "set_welcome":
        await query.edit_message_text("✏️ Xabarni yozing:")
        context.user_data['waiting_for_welcome'] = True
        context.user_data['editing_message_id'] = message_id

    elif data == "remove_settings":
        delete_group_settings(chat_id)
        await query.edit_message_text("✅ Sozlamalar o'chirildi!")

    elif data == "view_settings":
        settings = get_group_settings(chat_id)
        if settings:
            text = f"📢 Kanal: {settings['channel_username']}\n💬 Xabar: {settings['welcome_message']}"
        else:
            text = "⚠️ Hech qanday sozlama topilmadi."
        await query.edit_message_text(text, reply_markup=get_settings_keyboard())

# Kanal username inputni qabul qilish va saqlash
async def handle_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_channel'):
        chat_id = update.effective_chat.id
        channel_username = update.message.text.strip()
        if not channel_username.startswith('@'):
            channel_username = '@' + channel_username
        save_group_settings(chat_id, channel_username)
        await update.message.reply_text(
            f"✅ Sozlamalar saqlandi!\nEndi faqat kanalga obuna bo‘lgan foydalanuvchilar guruhda yozishi mumkin."
        )
        context.user_data['waiting_for_channel'] = False

# Xabarlarni qayta ishlash (foydalanuvchi xabari 2s, ogohlantirish 20s)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return

    chat = update.effective_chat
    user = update.effective_user

    # Kanal username inputni kutayotgan admin
    if context.user_data.get('waiting_for_channel'):
        await handle_channel_input(update, context)
        return

    settings = get_group_settings(chat.id)
    if not settings:
        return

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
                f"👋 {user.mention_html()}\n{settings['welcome_message']}",
                parse_mode='HTML'
            )

            # Foydalanuvchi xabarini 2 soniyadan keyin o'chirish
            async def delete_user(ctx):
                try:
                    await context.bot.delete_message(update.message.chat_id, update.message.message_id)
                except:
                    pass
            await context.job_queue.run_once(delete_user, 2)

            # Ogohlantirishni 20 soniyadan keyin o'chirish
            async def delete_warning(ctx):
                try:
                    await context.bot.delete_message(warning_msg.chat_id, warning_msg.message_id)
                except:
                    pass
            await context.job_queue.run_once(delete_warning, 20)

        except Exception as e:
            logger.warning(f"Xabarni o'chirish yoki ogohlantirish xatosi: {e}")

# Xatolik handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.warning(f"Xatolik: {context.error}")

# Asosiy funksiya
def main():
    init_db()
    BOT_TOKEN = "8227647066:AAHVl028wisNavIs1f8e-CYB97NDTB6RAhU"  # o'zingiz token qo'ying
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    print("🤖 Bot ishga tushdi...")
    application.run_polling()

if __name__ == "__main__":
    main()
