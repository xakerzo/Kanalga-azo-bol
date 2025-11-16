import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from telegram.error import TelegramError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FixedGroupControlBot:
    def __init__(self, token):
        self.application = Application.builder().token(token).build()
        self.init_db()
        self.setup_handlers()
    
    def init_db(self):
        conn = sqlite3.connect('group_manager.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS group_settings
                    (group_id INTEGER PRIMARY KEY, 
                     min_members INTEGER DEFAULT 5,
                     owner_id INTEGER,
                     is_active INTEGER DEFAULT 1)''')
        conn.commit()
        conn.close()
    
    def setup_handlers(self):
        handlers = [
            CommandHandler("start", self.start),
            CommandHandler("settings", self.settings),
            CommandHandler("set_members", self.set_members),
            CommandHandler("broadcast", self.broadcast),
            CommandHandler("status", self.status),
            CommandHandler("help", self.help_command),
            MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.new_chat_members),
            MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, self.left_chat_member),
            MessageHandler(filters.TEXT & filters.ChatType.GROUPS, self.handle_group_message),
            CallbackQueryHandler(self.button_handler)
        ]
        
        for handler in handlers:
            self.application.add_handler(handler)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        user = update.effective_user
        
        if chat.type == "private":
            await update.message.reply_text(
                "👋 Guruh Control Botiga xush kelibsiz!\n\n"
                "Botni guruhga qo'shing va ADMIN qiling.\n"
                "Keyin /settings buyrug'i bilan sozlamalarni o'rnating."
            )
        else:
            # Guruhda start bosilganda sozlamalarni avtomatik yaratish
            settings = self.get_group_settings(chat.id)
            if not settings:
                self.save_group_settings(chat.id, 5, user.id)
                await update.message.reply_text(
                    "✅ Bot faollashtirildi! Avtomatik sozlamalar yaratildi.\n"
                    "Minimal a'zolar soni: 5\n"
                    "Sozlamalarni /settings orqali o'zgartirishingiz mumkin."
                )
            else:
                await update.message.reply_text(
                    f"✅ Bot allaqachon faol!\n"
                    f"Minimal a'zolar: {settings['min_members']}\n"
                    f"Owner: {settings['owner_id']}"
                )
    
    async def new_chat_members(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:
                chat = update.effective_chat
                user = update.effective_user
                
                # Avtomatik sozlamalarni yaratish
                self.save_group_settings(chat.id, 5, user.id)
                
                await update.message.reply_text(
                    "🤖 Guruh Control Botiga xush kelibsiz!\n\n"
                    "Avtomatik sozlamalar yaratildi:\n"
                    "• Minimal a'zolar soni: 5\n"
                    "• Owner: siz\n\n"
                    "Sozlamalarni /settings orqali o'zgartiring.\n"
                    "Bot to'liq ishlashi uchun ADMIN huquqlarini bering!"
                )
    
    async def handle_group_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            chat = update.effective_chat
            user = update.effective_user
            message = update.effective_message
            
            # Botning o'z xabarlariga tekshirmaymiz
            if user and user.id == context.bot.id:
                return
            
            # Guruh sozlamalarini olish yoki yaratish
            settings = self.get_group_settings(chat.id)
            if not settings:
                self.save_group_settings(chat.id, 5, user.id)
                settings = self.get_group_settings(chat.id)
                logger.info(f"Avtomatik sozlamalar yaratildi: {chat.id}")
            
            # Adminlar va owner uchun cheklov yo'q
            if await self.is_admin(update, context) or await self.is_owner(update, context):
                return
            
            # Minimal a'zolar sonini tekshirish
            member_count = await self.get_chat_member_count(chat.id, context)
            min_members = settings['min_members']
            
            if member_count < min_members:
                try:
                    await message.delete()
                    warning = await message.reply_text(
                        f"❌ Hozir guruhda {member_count} ta a'zo bor. "
                        f"Minimal {min_members} ta a'zo bo'lgachgina xabar yozish mumkin!"
                    )
                    # Ogohlantirish xabarini 5 soniyadan keyin o'chirish
                    await context.job_queue.run_once(
                        self.delete_warning, 5, 
                        data=warning.chat_id, 
                        name=str(warning.message_id)
                    )
                except TelegramError as e:
                    logger.error(f"Xabarni o'chirishda xato: {e}")
        
        except Exception as e:
            logger.error(f"Xatolik handle_group_message: {e}")
    
    async def get_chat_member_count(self, chat_id, context):
        try:
            chat = await context.bot.get_chat(chat_id)
            return chat.get_member_count()
        except TelegramError as e:
            logger.error(f"Chat member count olishda xato: {e}")
            return 0
    
    async def delete_warning(self, context: ContextTypes.DEFAULT_TYPE):
        try:
            chat_id = context.job.data
            message_id = int(context.job.name)
            await context.bot.delete_message(chat_id, message_id)
        except TelegramError as e:
            logger.error(f"Ogohlantirishni o'chirishda xato: {e}")
    
    # Qolgan funksiyalar oldingi kabi...
    def get_group_settings(self, group_id):
        conn = sqlite3.connect('group_manager.db')
        c = conn.cursor()
        c.execute('SELECT * FROM group_settings WHERE group_id = ?', (group_id,))
        result = c.fetchone()
        conn.close()
        
        if result:
            return {
                'group_id': result[0],
                'min_members': result[1],
                'owner_id': result[2],
                'is_active': result[3]
            }
        return None
    
    def save_group_settings(self, group_id, min_members, owner_id, is_active=1):
        conn = sqlite3.connect('group_manager.db')
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO group_settings 
                    (group_id, min_members, owner_id, is_active) 
                    VALUES (?, ?, ?, ?)''', 
                 (group_id, min_members, owner_id, is_active))
        conn.commit()
        conn.close()
    
    async def is_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            chat = update.effective_chat
            user = update.effective_user
            if not user:
                return False
            
            member = await chat.get_member(user.id)
            return member.status in ['administrator', 'creator']
        except TelegramError as e:
            logger.error(f"Admin tekshirishda xato: {e}")
            return False
    
    async def is_owner(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            chat = update.effective_chat
            user = update.effective_user
            if not user:
                return False
            
            settings = self.get_group_settings(chat.id)
            return settings and settings['owner_id'] == user.id
        except Exception as e:
            logger.error(f"Owner tekshirishda xato: {e}")
            return False

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
🤖 **Guruh Control Bot - Yordam**

**Buyruqlar:**
/start - Botni ishga tushirish
/settings - Sozlamalar menyusi
/set_members [son] - Minimal a'zolar sonini o'rnatish
/status - Bot holatini ko'rish
/broadcast [xabar] - Owner uchun xabar yuborish

**Ishlash tartibi:**
1. Botni guruhga qo'shing
2. Admin qiling (barcha huquqlar bilan)
3. /settings orqali sozlamalarni o'rnating
4. Bot avtomatik ishlay boshlaydi
        """
        await update.message.reply_text(help_text)

# Ishga tushirish
if __name__ == "__main__":
    TOKEN = "8227647066:AAHVzzhMSgDCYz3pLqg96N8iQKlYcplhAuo"
    bot = FixedGroupControlBot(TOKEN)
    bot.application.run_polling()
