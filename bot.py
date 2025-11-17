import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
import os

# Sozlamalar
BOT_TOKEN = os.getenv('BOT_TOKEN', '8227647066:AAHVzzhMSgDCYz3pLqg96N8iQKlYcplhAuo')
BOT_OWNER_ID = int(os.getenv('BOT_OWNER_ID', '1373647'))

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Ma'lumotlar bazasi
def init_db():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS group_settings
                 (group_id INTEGER PRIMARY KEY,
                  channel_username TEXT,
                  welcome_message TEXT,
                  owner_id INTEGER)''')
    conn.commit()
    conn.close()

def get_group_settings(group_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('SELECT * FROM group_settings WHERE group_id = ?', (group_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        return {
            'group_id': result[0],
            'channel_username': result[1],
            'welcome_message': result[2],
            'owner_id': result[3]
        }
    return None

def save_group_settings(group_id, channel_username, welcome_message, owner_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO group_settings 
                 (group_id, channel_username, welcome_message, owner_id) 
                 VALUES (?, ?, ?, ?)''',
              (group_id, channel_username, welcome_message, owner_id))
    conn.commit()
    conn.close()

async def check_channel_membership(user_id, channel_username, context):
    try:
        if not channel_username:
            return True
        channel_username = channel_username.replace('@', '')
        chat_member = await context.bot.get_chat_member(f"@{channel_username}", user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Kanal a'zoligini tekshirishda xato: {e}")
        return False

# Command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type == "private":
        if user.id == BOT_OWNER_ID:
            await update.message.reply_text(
                "👑 Salom Owner!\n\n"
                "📋 Maxsus buyruqlar:\n"
                "/stats - Bot statistika\n"
                "/broadcast - Barcha guruhlarga xabar\n"
                "/myid - ID ni ko'rish\n\n"
                "🤖 Botni guruhga qo'shing va ADMIN qiling.\n"
                "Keyin /settings buyrug'i bilan sozlamalarni o'rnating."
            )
        else:
            await update.message.reply_text(
                "👋 Botga xush kelibsiz!\n\n"
                "Botni guruhga qo'shing va ADMIN qiling.\n"
                "Keyin /settings buyrug'i bilan sozlamalarni o'rnating."
            )
    else:
        await update.message.reply_text(
            "✅ Bot faollashtirildi!\n"
            "Sozlamalarni /settings buyrug'i bilan o'rnating."
        )

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type == "private":
        await update.message.reply_text("❌ Bu buyruq faqat guruhlarda ishlaydi!")
        return
    
    try:
        member = await chat.get_member(user.id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Bu buyruq faqat adminlar uchun!")
            return
    except Exception as e:
        logger.error(f"Adminlik tekshirish xatosi: {e}")
        await update.message.reply_text("❌ Adminlikni tekshirishda xatolik!")
        return
    
    keyboard = [
        [InlineKeyboardButton("📢 Kanal username o'rnatish", callback_data="set_channel")],
        [InlineKeyboardButton("👋 Xush kelib xabari", callback_data="set_welcome")],
        [InlineKeyboardButton("📊 Sozlamalarni ko'rish", callback_data="view_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⚙️ **Bot Sozlamalari**\n\n"
        "Quyidagi sozlamalarni o'zgartirishingiz mumkin:",
        reply_markup=reply_markup
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != BOT_OWNER_ID:
        await update.message.reply_text("❌ Bu buyruq faqat bot owneri uchun!")
        return
    
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM group_settings')
    group_count = c.fetchone()[0]
    conn.close()
    
    await update.message.reply_text(
        f"📊 **Bot Statistikasi**\n\n"
        f"• Faol guruhlar: {group_count}\n"
        f"• Owner ID: {BOT_OWNER_ID}"
    )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != BOT_OWNER_ID:
        await update.message.reply_text("❌ Bu buyruq faqat bot owneri uchun!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Xabar kiriting: /broadcast Salom!")
        return
    
    message = " ".join(context.args)
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('SELECT group_id FROM group_settings')
    groups = c.fetchall()
    conn.close()
    
    success = 0
    failed = 0
    
    for group in groups:
        try:
            await context.bot.send_message(group[0], f"📢 Broadcast:\n\n{message}")
            success += 1
        except Exception as e:
            failed += 1
            logger.error(f"Broadcast xatosi {group[0]}: {e}")
    
    await update.message.reply_text(
        f"✅ Broadcast natijasi:\n"
        f"• Muvaffaqiyatli: {success}\n"
        f"• Xatolik: {failed}"
    )

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    
    await update.message.reply_text(
        f"🆔 **Sizning IDlaringiz:**\n\n"
        f"• User ID: `{user.id}`\n"
        f"• Chat ID: `{chat.id}`\n"
        f"• Bot Owner ID: `{BOT_OWNER_ID}`",
        parse_mode='Markdown'
    )

# Button handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    chat = query.message.chat
    user = query.from_user
    
    if data == "set_channel":
        context.user_data['waiting_for_channel'] = True
        await query.edit_message_text(
            "📢 Kanal username yuboring (@ belgisiz):\n\n"
            "Masalan: kanal_nomi\n\n"
            "Bekor qilish uchun /cancel"
        )
    
    elif data == "set_welcome":
        context.user_data['waiting_for_welcome'] = True
        await query.edit_message_text(
            "👋 Xush kelib xabarini yuboring:\n\n"
            "Masalan: Iltimos, kanalga a'zo bo'ling!\n\n"
            "Bekor qilish uchun /cancel"
        )
    
    elif data == "view_settings":
        settings = get_group_settings(chat.id)
        if settings:
            text = (
                f"⚙️ **Joriy Sozlamalar**\n\n"
                f"• Kanal: @{settings['channel_username'] or 'Belgilanmagan'}\n"
                f"• Xush kelib xabari: {settings['welcome_message'] or 'Belgilanmagan'}\n"
                f"• Owner ID: {settings['owner_id']}"
            )
        else:
            text = "❌ Sozlamalar hali o'rnatilmagan!"
        
        await query.edit_message_text(text)

# Message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    message_text = update.message.text
    
    if chat.type == "private":
        return
    
    if context.user_data.get('waiting_for_channel'):
        try:
            channel_username = message_text.strip()
            settings = get_group_settings(chat.id)
            
            if settings:
                save_group_settings(chat.id, channel_username, settings['welcome_message'], settings['owner_id'])
            else:
                save_group_settings(chat.id, channel_username, "Iltimos, kanalga a'zo bo'ling!", user.id)
            
            await update.message.reply_text("✅ Kanal username saqlandi!")
        except Exception as e:
            logger.error(f"Kanal saqlash xatosi: {e}")
            await update.message.reply_text("❌ Xatolik yuz berdi!")
        
        context.user_data.pop('waiting_for_channel', None)
        return
    
    elif context.user_data.get('waiting_for_welcome'):
        try:
            welcome_message = message_text.strip()
            settings = get_group_settings(chat.id)
            
            if settings:
                save_group_settings(chat.id, settings['channel_username'], welcome_message, settings['owner_id'])
                await update.message.reply_text("✅ Xabar saqlandi!")
            else:
                await update.message.reply_text("❌ Avval kanal sozlamalarini o'rnating!")
        except Exception as e:
            logger.error(f"Xabar saqlash xatosi: {e}")
            await update.message.reply_text("❌ Xatolik yuz berdi!")
        
        context.user_data.pop('waiting_for_welcome', None)
        return
    
    # Oddiy xabarlarni tekshirish
    settings = get_group_settings(chat.id)
    if not settings:
        return
    
    try:
        member = await chat.get_member(user.id)
        if member.status in ['administrator', 'creator']:
            return
    except Exception as e:
        logger.error(f"❌ Adminlik tekshirish xatosi: {e}")
        return
    
    is_member = await check_channel_membership(user.id, settings['channel_username'], context)
    
    if not is_member and settings['channel_username']:
        try:
            await update.message.delete()
            
            welcome_msg = settings['welcome_message'] or "Iltimos, kanalga a'zo bo'ling!"
            warning_msg = await context.bot.send_message(
                chat_id=chat.id,
                text=f"👋 {user.mention_html()}\n{welcome_msg}\n\nKanal: @{settings['channel_username']}",
                parse_mode='HTML'
            )
            
            # Ogohlantirishni 10 soniyadan keyin o'chirish
            async def delete_warning(job_context):
                data = job_context.job.data
                try:
                    await context.bot.delete_message(
                        chat_id=data['chat_id'],
                        message_id=data['message_id']
                    )
                except Exception as e:
                    logger.error(f"❌ Ogohlantirishni o'chirish xatosi: {e}")
            
            await context.job_queue.run_once(
                delete_warning,
                when=10,
                data={'chat_id': warning_msg.chat_id, 'message_id': warning_msg.message_id},
                name=f"delete_warning_{warning_msg.message_id}"
            )
        except Exception as e:
            logger.error(f"❌ Xabarni o'chirish yoki ogohlantirish xatosi: {e}")

# Xatolik handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"❌ Xatolik: {context.error}", exc_info=context.error)

# Asosiy funksiya
def main():
    if not BOT_TOKEN or BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        logger.error("❌ BOT_TOKEN topilmadi!")
        return
    
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CommandHandler("cancel", start_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    logger.info("🤖 Bot ishga tushdi...")
    logger.info(f"👑 Owner ID: {BOT_OWNER_ID}")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
