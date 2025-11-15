import logging
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, 
    CommandHandler, 
    MessageHandler, 
    CallbackContext, 
    CallbackQueryHandler,
    Filters
)

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_OWNER_ID = int(os.getenv('BOT_OWNER_ID', '1373647'))
BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN topilmadi! Environment variable ni o'rnating.")
    exit(1)

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
    
    cursor.execute('''
        INSERT OR REPLACE INTO group_settings 
        (group_id, channel_username, welcome_message) 
        VALUES (?, ?, ?)
    ''', (group_id, channel_username, welcome_message))
    
    conn.commit()
    conn.close()

# Sozlamalarni o'chirish
def delete_group_settings(group_id):
    conn = sqlite3.connect('channel_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM group_settings WHERE group_id = ?', (group_id,))
    
    conn.commit()
    conn.close()

# Kanal a'zoligini tekshirish
def check_channel_membership(user_id, channel_username, context):
    try:
        if not channel_username.startswith('@'):
            channel_username = '@' + channel_username
        
        member = context.bot.get_chat_member(channel_username, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"A'zolik tekshirish xatosi: {e}")
        return False

# Owner ekanligini tekshirish
def is_owner(user_id):
    return user_id == BOT_OWNER_ID

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
def start_command(update: Update, context: CallbackContext):
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type == 'private':
        if is_owner(user.id):
            update.message.reply_text(
                f"👑 Salom Owner!\n\n"
                f"Maxsus buyruqlar:\n"
                f"/stats - Bot statistika\n"
                f"/broadcast - Barcha guruhlarga xabar\n"
                f"/myid - ID ni ko'rish"
            )
        else:
            update.message.reply_text(
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
            member = chat.get_member(user.id)
            if member.status not in ['administrator', 'creator']:
                update.message.reply_text("❌ Faqat adminlar sozlamalarni o'zgartirishi mumkin!")
                return
        except Exception as e:
            logger.error(f"Adminlik tekshirish xatosi: {e}")
            update.message.reply_text("❌ Xatolik yuz berdi!")
            return
        
        update.message.reply_text(
            "⚙️ Guruh sozlamalari\n\n"
            "Quyidagi tugmalar orqali sozlamalarni boshqaring:",
            reply_markup=get_settings_keyboard()
        )

# Sozlamalar komandasi
def settings_command(update: Update, context: CallbackContext):
    chat = update.effective_chat
    
    if chat.type not in ['group', 'supergroup']:
        update.message.reply_text("❌ Bu buyruq faqat guruhlarda ishlaydi!")
        return
    
    try:
        user = update.effective_user
        member = chat.get_member(user.id)
        if member.status not in ['administrator', 'creator']:
            update.message.reply_text("❌ Faqat adminlar sozlamalarni o'zgartirishi mumkin!")
            return
    except Exception as e:
        logger.error(f"Adminlik tekshirish xatosi: {e}")
        update.message.reply_text("❌ Xatolik yuz berdi!")
        return
    
    settings = get_group_settings(chat.id)
    
    if settings:
        text = (
            f"📋 Joriy sozlamalar:\n\n"
            f"📢 Kanal: {settings['channel_username']}\n"
            f"💬 Xabar: {settings['welcome_message']}\n\n"
            f"Quyidagi tugmalar orqali o'zgartiring:"
        )
    else:
        text = (
            "⚠️ Hech qanday sozlama topilmadi.\n\n"
            "Bot hozir barcha foydalanuvchilarga yozishga ruxsat beradi.\n"
            "Kanal sozlamalarini o'rnatish uchun quyidagi tugmalardan foydalaning:"
        )
    
    update.message.reply_text(text, reply_markup=get_settings_keyboard())

# Tugmalarni boshqarish
def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    data = query.data
    chat_id = query.message.chat_id
    
    if data == "add_channel":
        query.edit_message_text(
            "📢 Qaysi kanalga obuna bo'lishni talab qilmoqchisiz?\n\n"
            "Kanal username ni yuboring (@ belgisi bilan):\n"
            "Masalan: @my_channel"
        )
        context.user_data['waiting_for_channel'] = True
        
    elif data == "set_welcome":
        query.edit_message_text(
            "✏️ Foydalanuvchi kanalga obuna bo'lmaganda chiqadigan xabarni yozing:\n\n"
            "Masalan: ❗️ Iltimos, avval @my_channel kanaliga obuna bo'ling!"
        )
        context.user_data['waiting_for_welcome'] = True
        
    elif data == "remove_settings":
        delete_group_settings(chat_id)
        query.edit_message_text(
            "✅ Sozlamalar o'chirildi!\n\n"
            "Endi barcha foydalanuvchilar guruhda yozishi mumkin."
        )
        
    elif data == "view_settings":
        settings = get_group_settings(chat_id)
        if settings:
            text = (
                f"📋 Sozlamalar:\n\n"
                f"📢 Kanal: {settings['channel_username']}\n"
                f"💬 Xabar: {settings['welcome_message']}"
            )
        else:
            text = "⚠️ Hech qanday sozlama topilmadi."
        query.edit_message_text(text, reply_markup=get_settings_keyboard())

# Broadcast komandasi
def broadcast_command(update: Update, context: CallbackContext):
    user = update.effective_user
    
    if not is_owner(user.id):
        update.message.reply_text("❌ Bu buyruq faqat bot owneri uchun!")
        return
    
    if not context.args:
        update.message.reply_text("ℹ️ Foydalanish: /broadcast <xabar matni>")
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
            context.bot.send_message(
                chat_id=group[0], 
                text=f"📢 Bot yangiligi:\n\n{message_text}"
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Guruh {group[0]} ga xabar yuborish xatosi: {e}")
            failed_count += 1
    
    update.message.reply_text(
        f"✅ Xabar yuborildi!\n"
        f"✔️ Muvaffaqiyatli: {sent_count}\n"
        f"❌ Xatolik: {failed_count}"
    )

# Stats komandasi
def stats_command(update: Update, context: CallbackContext):
    user = update.effective_user
    
    if not is_owner(user.id):
        update.message.reply_text("❌ Bu buyruq faqat bot owneri uchun!")
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
    
    stats_text = f"🤖 Bot Statistika\n\n"
    stats_text += f"🔧 Faol guruhlar: {groups_count}\n\n"
    stats_text += "📈 Top kanallar:\n"
    
    for channel, count in popular_channels:
        stats_text += f"• {channel}: {count} guruh\n"
    
    update.message.reply_text(stats_text)

# MyID komandasi
def myid_command(update: Update, context: CallbackContext):
    user = update.effective_user
    update.message.reply_text(f"Sizning ID: {user.id}")

# Xabarlarni qayta ishlash
def handle_message(update: Update, context: CallbackContext):
    if update.message.from_user.is_bot:
        return
    
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type == 'private':
        update.message.reply_text("Botni guruhga qo'shing va /settings orqali sozlang!")
        return
    
    # Sozlash rejimi
    if 'waiting_for_channel' in context.user_data and context.user_data['waiting_for_channel']:
        channel_username = update.message.text.strip()
        
        if not channel_username.startswith('@'):
            update.message.reply_text("❌ Kanal username @ belgisi bilan boshlanishi kerak!")
            return
        
        try:
            chat_info = context.bot.get_chat(channel_username)
            if chat_info.type != 'channel':
                update.message.reply_text("❌ Bu kanal emas! Iltimos, kanal username ni yuboring.")
                return
            
            save_group_settings(chat.id, channel_username)
            update.message.reply_text(
                f"✅ Sozlamalar saqlandi!\n\n"
                f"Endi faqat {channel_username} kanaliga obuna bo'lgan foydalanuvchilar "
                f"guruhda yozishi mumkin."
            )
            
            context.user_data.pop('waiting_for_channel', None)
            
        except Exception as e:
            logger.error(f"Kanal tekshirish xatosi: {e}")
            update.message.reply_text("❌ Kanal topilmadi yoki bot kanalga kirish huquqiga ega emas!")
    
    elif 'waiting_for_welcome' in context.user_data and context.user_data['waiting_for_welcome']:
        welcome_message = update.message.text
        
        settings = get_group_settings(chat.id)
        if settings:
            save_group_settings(chat.id, settings['channel_username'], welcome_message)
            update.message.reply_text("✅ Xabar saqlandi!")
        else:
            update.message.reply_text("❌ Avval kanal sozlamalarini o'rnating!")
        
        context.user_data.pop('waiting_for_welcome', None)
    
    else:
        # Oddiy xabarlarni tekshirish
        settings = get_group_settings(chat.id)
        
        if not settings:
            return
        
        # Adminlarni tekshirmaslik
        try:
            member = chat.get_member(user.id)
            if member.status in ['administrator', 'creator']:
                return
        except:
            pass
        
        # A'zolikni tekshirish
        is_member = check_channel_membership(user.id, settings['channel_username'], context)
        
        if not is_member:
            try:
                update.message.delete()
                warning_msg = update.message.reply_text(
                    f"👋 {user.mention_html()}\n{settings['welcome_message']}",
                    parse_mode='HTML'
                )
                
                # Warning o'chirish
                def delete_warning(context):
                    try:
                        context.bot.delete_message(
                            chat_id=warning_msg.chat_id,
                            message_id=warning_msg.message_id
                        )
                    except:
                        pass
                
                context.job_queue.run_once(delete_warning, 10, context=context)
                
            except Exception as e:
                logger.error(f"Xabarni o'chirish xatosi: {e}")

# Asosiy funksiya
def main():
    init_db()
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN topilmadi!")
        return
    
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Handlerlar
    dp.add_handler(CommandHandler("start", start_command))
    dp.add_handler(CommandHandler("settings", settings_command))
    dp.add_handler(CommandHandler("stats", stats_command))
    dp.add_handler(CommandHandler("broadcast", broadcast_command))
    dp.add_handler(CommandHandler("myid", myid_command))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    logger.info("🤖 Bot ishga tushdi...")
    logger.info(f"👑 Owner ID: {BOT_OWNER_ID}")
    
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
