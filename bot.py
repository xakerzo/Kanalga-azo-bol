import logging
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_OWNER_ID = int(os.getenv('BOT_OWNER_ID', '1373647'))
BOT_TOKEN = os.getenv('BOT_TOKEN', '8227647066:AAHVl028wisNavIs1f8e-CYB97NDTB6RAhU')

# Ma'lumotlar bazasini yaratish
def init_db():
    conn = sqlite3.connect('channel_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_settings (
            group_id INTEGER PRIMARY KEY,
            channel_username TEXT,
            welcome_message TEXT DEFAULT '❗️ Iltimos, avval kanalga obuna boʻling!'
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("Ma'lumotlar bazasi yaratildi")

def get_group_settings(group_id):
    conn = sqlite3.connect('channel_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT channel_username, welcome_message FROM group_settings WHERE group_id = ?', (group_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {'channel_username': result[0], 'welcome_message': result[1]}
    return None

def save_group_settings(group_id, channel_username, welcome_message=None):
    if welcome_message is None:
        welcome_message = '❗️ Iltimos, avval kanalga obuna boʻling!'
    conn = sqlite3.connect('channel_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO group_settings (group_id, channel_username, welcome_message) VALUES (?, ?, ?)', 
                   (group_id, channel_username, welcome_message))
    conn.commit()
    conn.close()

def delete_group_settings(group_id):
    conn = sqlite3.connect('channel_bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM group_settings WHERE group_id = ?', (group_id,))
    conn.commit()
    conn.close()

async def check_channel_membership(user_id, channel_username, context):
    try:
        if not channel_username.startswith('@'):
            channel_username = '@' + channel_username
        member = await context.bot.get_chat_member(channel_username, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"A'zolik tekshirish xatosi: {e}")
        return False

def is_owner(user_id):
    return user_id == BOT_OWNER_ID

def get_settings_keyboard():
    keyboard = [
        [InlineKeyboardButton("📢 Kanal qo'shish", callback_data="add_channel")],
        [InlineKeyboardButton("✏️ Xabarni o'zgartirish", callback_data="set_welcome")],
        [InlineKeyboardButton("🗑 Sozlamalarni o'chirish", callback_data="remove_settings")],
        [InlineKeyboardButton("ℹ️ Sozlamalarni ko'rish", callback_data="view_settings")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type == 'private':
        if is_owner(user.id):
            await update.message.reply_text("👑 Salom Owner!\n\nMaxsus buyruqlar:\n/stats - Bot statistika\n/broadcast - Barcha guruhlarga xabar\n/myid - ID ni ko'rish")
        else:
            await update.message.reply_text(f"👋 Salom {user.first_name}!\n\n🤖 Men - guruhlarda faqat ma'lum kanalga obuna bo'lgan foydalanuvchilarga yozishga ruxsat beruvchi botman.\n\n📋 Botdan foydalanish:\n1. Botni guruhga qo'shing\n2. Admin qiling\n3. /settings buyrug'i orqali kanal sozlang\n4. Bot avtomatik tekshiradi!")
    else:
        try:
            member = await chat.get_member(user.id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Faqat adminlar sozlamalarni o'zgartirishi mumkin!")
                return
        except:
            await update.message.reply_text("❌ Xatolik yuz berdi!")
            return
        
        await update.message.reply_text("⚙️ Guruh sozlamalari\n\nQuyidagi tugmalar orqali sozlamalarni boshqaring:", reply_markup=get_settings_keyboard())

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
    except:
        await update.message.reply_text("❌ Xatolik yuz berdi!")
        return
    
    settings = get_group_settings(chat.id)
    
    if settings:
        text = f"📋 Joriy sozlamalar:\n\n📢 Kanal: {settings['channel_username']}\n💬 Xabar: {settings['welcome_message']}\n\nQuyidagi tugmalar orqali o'zgartiring:"
    else:
        text = "⚠️ Hech qanday sozlama topilmadi.\n\nBot hozir barcha foydalanuvchilarga yozishga ruxsat beradi.\nKanal sozlamalarini o'rnatish uchun quyidagi tugmalardan foydalaning:"
    
    await update.message.reply_text(text, reply_markup=get_settings_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    chat_id = query.message.chat_id
    
    if data == "add_channel":
        await query.edit_message_text("📢 Qaysi kanalga obuna bo'lishni talab qilmoqchisiz?\n\nKanal username ni yuboring (@ belgisi bilan):\nMasalan: @my_channel")
        context.user_data['waiting_for_channel'] = True
        
    elif data == "set_welcome":
        await query.edit_message_text("✏️ Foydalanuvchi kanalga obuna bo'lmaganda chiqadigan xabarni yozing:\n\nMasalan: ❗️ Iltimos, avval @my_channel kanaliga obuna bo'ling!")
        context.user_data['waiting_for_welcome'] = True
        
    elif data == "remove_settings":
        delete_group_settings(chat_id)
        await query.edit_message_text("✅ Sozlamalar o'chirildi!\n\nEndi barcha foydalanuvchilar guruhda yozishi mumkin.")
        
    elif data == "view_settings":
        settings = get_group_settings(chat_id)
        if settings:
            text = f"📋 Sozlamalar:\n\n📢 Kanal: {settings['channel_username']}\n💬 Xabar: {settings['welcome_message']}"
        else:
            text = "⚠️ Hech qanday sozlama topilmadi."
        await query.edit_message_text(text, reply_markup=get_settings_keyboard())

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
    
    await update.message.reply_text(f"✅ Xabar yuborildi!\n✔️ Muvaffaqiyatli: {sent_count}\n❌ Xatolik: {failed_count}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_owner(user.id):
        await update.message.reply_text("❌ Bu buyruq faqat bot owneri uchun!")
        return
    
    conn = sqlite3.connect('channel_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM group_settings')
    groups_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT channel_username, COUNT(*) as count FROM group_settings GROUP BY channel_username ORDER BY count DESC LIMIT 5')
    popular_channels = cursor.fetchall()
    conn.close()
    
    stats_text = f"🤖 Bot Statistika\n\n🔧 Faol guruhlar: {groups_count}\n\n📈 Top kanallar:\n"
    
    for channel, count in popular_channels:
        stats_text += f"• {channel}: {count} guruh\n"
    
    await update.message.reply_text(stats_text)

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"Sizning ID: {user.id}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return
    
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type == 'private':
        await update.message.reply_text("Botni guruhga qo'shing va /settings orqali sozlang!")
        return
    
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
            await update.message.reply_text(f"✅ Sozlamalar saqlandi!\n\nEndi faqat {channel_username} kanaliga obuna bo'lgan foydalanuvchilar guruhda yozishi mumkin.")
            context.user_data.pop('waiting_for_channel', None)
            
        except Exception as e:
            logger.error(f"Kanal tekshirish xatosi: {e}")
            await update.message.reply_text("❌ Kanal topilmadi yoki bot kanalga kirish huquqiga ega emas!")
    
    elif 'waiting_for_welcome' in context.user_data and context.user_data['waiting_for_welcome']:
        welcome_message = update.message.text
        
        settings = get_group_settings(chat.id)
        if settings:
            save_group_settings(chat.id, settings['channel_username'], welcome_message)
            await update.message.reply_text("✅ Xabar saqlandi!")
        else:
            await update.message.reply_text("❌ Avval kanal sozlamalarini o'rnating!")
        
        context.user_data.pop('waiting_for_welcome', None)
    
    else:
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
                await update.message.delete()
                warning_msg = await update.message.reply_text(f"👋 {user.mention_html()}\n{settings['welcome_message']}", parse_mode='HTML')
                
                async def delete_warning(context: ContextTypes.DEFAULT_TYPE):
                    try:
                        await context.bot.delete_message(chat_id=warning_msg.chat_id, message_id=warning_msg.message_id)
                    except:
                        pass
                
                await context.job_queue.run_once(delete_warning, 10)
                
            except Exception as e:
                logger.error(f"Xabarni o'chirish xatosi: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Xatolik: {context.error}")

def main():
    init_db()
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN topilmadi!")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    logger.info("🤖 Bot ishga tushdi...")
    logger.info(f"👑 Owner ID: {BOT_OWNER_ID}")
    
    application.run_polling()

if __name__ == "__main__":
    main()
