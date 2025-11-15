import logging
import os
import sqlite3
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

# 🔑 BOT OWNER ID - O'ZINGIZNING TELEGRAM ID
BOT_OWNER_ID = 1373647

# Ma'lumotlar bazasini yaratish
def init_db():
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

# Guruh sozlamalarini olish
def get_group_settings(group_id):
    conn = sqlite3.connect('channel_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'SELECT channel_username, welcome_message FROM group_settings WHERE group_id = ?',
        (group_id,)
    )
    result = cursor.fetchone()
    conn.close()
    if result:
        return {
            'channel_username': result[0],
            'welcome_message': result[1]
        }
    return None

# Guruh sozlamalarini saqlash
def save_group_settings(group_id, channel_username, welcome_message=None):
    if welcome_message is None:
        welcome_message = '❗️ Iltimos, avval kanalga obuna boʻling!'
    conn = sqlite3.connect('channel_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT OR REPLACE INTO group_settings (group_id, channel_username, welcome_message)
           VALUES (?, ?, ?)''',
        (group_id, channel_username, welcome_message)
    )
    conn.commit()
    conn.close()
    logger.info(f"Guruh {group_id} sozlamalari saqlandi")

# Sozlamalarni o'chirish
def delete_group_settings(group_id):
    conn = sqlite3.connect('channel_bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM group_settings WHERE group_id = ?', (group_id,))
    conn.commit()
    conn.close()
    logger.info(f"Guruh {group_id} sozlamalari o'chirildi")

# Kanal a'zoligini tekshirish
async def check_channel_membership(user_id, channel_username, context):
    try:
        if not channel_username.startswith('@'):
            channel_username = '@' + channel_username
        member = await context.bot.get_chat_member(channel_username, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"A'zolik tekshirish xatosi: {e}")
        return False

# Owner ekanligini tekshirish
def is_owner(user_id):
    return user_id == BOT_OWNER_ID

# Broadcast xabari
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("❌ Bu buyruq faqat bot owneri uchun!")
        return
    if not context.args:
        await update.message.reply_text("ℹ️ Foydalanish: /broadcast <xabar matni>")
        return
    message_text = ' '.join(context.args)
    conn = sqlite3.connect('channel_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT group_id FROM group_settings')
    groups = cursor.fetchall()
    conn.close()
    sent_count = 0
    failed_count = 0
    for group in groups:
        try:
            await context.bot.send_message(chat_id=group[0], text=f"📢 Bot yangiligi:\n\n{message_text}")
            sent_count += 1
        except Exception as e:
            logger.error(f"Guruh {group[0]} ga xabar yuborish xatosi: {e}")
            failed_count += 1
    await update.message.reply_text(
        f"✅ Xabar yuborildi!\n✔️ Muvaffaqiyatli: {sent_count}\n❌ Xatolik: {failed_count}"
    )

# Stats komandasi
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("❌ Bu buyruq faqat bot owneri uchun!")
        return
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
    stats_text = f"🤖 Bot Statistika (Owner)\n\n🔧 Faol guruhlar: {groups_count}\n\n📈 Top kanallar:\n"
    for channel, count in popular_channels:
        stats_text += f"• {channel}: {count} guruh\n"
    await update.message.reply_text(stats_text)

# My ID komandasi
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

# Start komandasi
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type == 'private':
        if is_owner(user.id):
            await update.message.reply_text(
                f"👑 Salom Owner!\n\nMaxsus buyruqlar:\n"
                f"/stats - Bot statistika\n"
                f"/broadcast - Barcha guruhlarga xabar\n"
                f"/myid - ID ni ko'rish"
            )
        else:
            await update.message.reply_text(
                f"👋 Salom {user.first_name}!\n\n"
                "🤖 Men - guruhlarda faqat ma'lum kanalga obuna bo'lgan foydalanuvchilarga "
                "yozishga ruxsat beruvchi botman.\n\n"
                "📋 Botdan foydalanish:\n"
                "1. Botni guruhga qo'shing\n"
                "2. Admin qiling\n"
                "3. /settings buyrug'i orqali kanal sozlang\n"
                "4. Bot avtomatik tekshiradi!"
            )
    else:
        try:
            member = await chat.get_member(user.id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Faqat adminlar sozlamalarni o'zgartirishi mumkin!")
                return
        except Exception as e:
            logger.error(f"Adminlik tekshirish xatosi: {e}")
            await update.message.reply_text("❌ Xatolik yuz berdi!")
            return
        await update.message.reply_text(
            "⚙️ Guruh sozlamalari\n\nQuyidagi tugmalar orqali sozlamalarni boshqaring:",
            reply_markup=get_settings_keyboard()
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
        logger.error(f"Adminlik tekshirish xatosi: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi!")
        return
    settings = get_group_settings(chat.id)
    if settings:
        text = (
            f"📋 Joriy sozlamalar:\n\n📢 Kanal: {settings['channel_username']}\n"
            f"💬 Xabar: {settings['welcome_message']}\n\nQuyidagi tugmalar orqali o'zgartiring:"
        )
    else:
        text = (
            "⚠️ Hech qanday sozlama topilmadi.\n\n"
            "Bot hozir barcha foydalanuvchilarga yozishga ruxsat beradi.\n"
            "Kanal sozlamalarini o'rnatish uchun quyidagi tugmalardan foydalaning:"
        )
    await update.message.reply_text(text, reply_markup=get_settings_keyboard())

# Tugmalarni boshqarish
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id
    message_id = query.message.message_id

    if data == "add_channel":
        await query.edit_message_text(
            "📢 Qaysi kanalga obuna bo'lishni talab qilmoqchisiz?\n\n"
            "Kanal username ni yuboring (@ belgisi bilan):\nMasalan: @my_channel\n\n"
            "ℹ️ Eslatma: Bot kanalda admin bo'lishi shart emas, faqat a'zolikni tekshiradi."
        )
        context.user_data['waiting_for_channel'] = True
        context.user_data['editing_message_id'] = message_id

    elif data == "set_welcome":
        await query.edit_message_text(
            "✏️ Foydalanuvchi kanalga obuna bo'lmaganda chiqadigan xabarni yozing:\n\n"
            "Masalan: ❗️ Iltimos, avval @my_channel kanaliga obuna bo'ling!"
        )
        context.user_data['waiting_for_welcome'] = True
        context.user_data['editing_message_id'] = message_id

    elif data == "remove_settings":
        delete_group_settings(chat_id)
        await query.edit_message_text(
            "✅ Sozlamalar o'chirildi!\n\nEndi barcha foydalanuvchilar guruhda yozishi mumkin."
        )

    elif data == "view_settings":
        settings = get_group_settings(chat_id)
        if settings:
            text = f"📋 Sozlamalar:\n\n📢 Kanal: {settings['channel_username']}\n💬 Xabar: {settings['welcome_message']}"
        else:
            text = "⚠️ Hech qanday sozlama topilmadi."
        await query.edit_message_text(text, reply_markup=get_settings_keyboard())

# Xabarlarni qayta ishlash
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return
    chat = update.effective_chat
    user = update.effective_user

    # Guruhda sozlash rejimi
    if 'waiting_for_channel' in context.user_data and context.user_data['waiting_for_channel']:
        channel_username = update.message.text.strip()
        if not channel_username.startswith('@'):
            await update.message.reply_text("❌ Kanal username @ belgisi bilan boshlanishi kerak!")
            return
        try:
            chat_info = await context.bot.get_chat(channel_username)
            if chat_info.type != 'channel':
                await update.message.reply_text("❌ Bu kanal emas! Iltimos, kanal username ni yuboring.")
                return
            save_group_settings(chat.id, channel_username)
            try:
                await context.bot.delete_message(chat.id, context.user_data['editing_message_id'])
            except: pass
            await update.message.reply_text(f"✅ Sozlamalar saqlandi!\nEndi faqat {channel_username} kanaliga obuna bo'lgan foydalanuvchilar guruhda yozishi mumkin.")
            context.user_data.pop('waiting_for_channel', None)
            context.user_data.pop('editing_message_id', None)
        except Exception as e:
            logger.error(f"Kanal tekshirish xatosi: {e}")
            await update.message.reply_text("❌ Kanal topilmadi yoki bot kanalga kirish huquqiga ega emas!\nIltimos, kanal username ni to'g'ri kiriting.")

    elif 'waiting_for_welcome' in context.user_data and context.user_data['waiting_for_welcome']:
        welcome_message = update.message.text
        settings = get_group_settings(chat.id)
        if settings:
            save_group_settings(chat.id, settings['channel_username'], welcome_message)
            try:
                await context.bot.delete_message(chat.id, context.user_data['editing_message_id'])
            except: pass
            await update.message.reply_text("✅ Xabar saqlandi!")
        else:
            await update.message.reply_text("❌ Avval kanal sozlamalarini o'rnating!")
        context.user_data.pop('waiting_for_welcome', None)
        context.user_data.pop('editing_message_id', None)

    else:
        settings = get_group_settings(chat.id)
        if not settings:
            return
        try:
            member = await chat.get_member(user.id)
            if member.status in ['administrator', 'creator']:
                return
        except: pass
        is_member = await check_channel_membership(user.id, settings['channel_username'], context)
        if not is_member:
            try:
                await update.message.delete()
                warning_msg = await update.message.reply_text(
                    f"👋 {user.mention_html()}\n{settings['welcome_message']}",
                    parse_mode='HTML'
                )
                async def delete_warning(context: ContextTypes.DEFAULT_TYPE):
                    try:
                        await context.bot.delete_message(warning_msg.chat_id, warning_msg.message_id)
                    except: pass
                await context.job_queue.run_once(delete_warning, 10, name=f"delete_warning_{warning_msg.message_id}")
            except Exception as e:
                logger.error(f"Xabarni o'chirish xatosi: {e}")

# Xatolik handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Xatolik: {context.error}", exc_info=context.error)

# Asosiy funksiya
def main():
    init_db()
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    RAILWAY_URL = "https://kanalga-azo-bol.up.railway.app"  # To'g'ridan-to'g'ri URL

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
    print(f"👑 Owner ID: {BOT_OWNER_ID}")
    print("⏳ Bot ishlamoqda...")

    # ✅ TO'G'RI WEBHOOK SOZLASH
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        url_path="webhook",  # ✅ MUHIM: webhook endpoint path
        webhook_url=f"{RAILWAY_URL}/webhook",  # ✅ MUHIM: /webhook qo'shildi
        secret_token='WEBHOOK_SECRET'  # ✅ Xavfsizlik uchun
    )

if __name__ == "__main__":
    main()
