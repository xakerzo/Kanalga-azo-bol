import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from telegram.error import TelegramError

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class GroupControlBot:
    def __init__(self, token):
        self.application = Application.builder().token(token).build()
        self.init_db()
        self.setup_handlers()
    
    def init_db(self):
        """Ma'lumotlar bazasini yaratish"""
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
        """Handlerlarni sozlash"""
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
    
    def get_group_settings(self, group_id):
        """Guruh sozlamalarini olish"""
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
        """Guruh sozlamalarini saqlash"""
        conn = sqlite3.connect('group_manager.db')
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO group_settings 
                    (group_id, min_members, owner_id, is_active) 
                    VALUES (?, ?, ?, ?)''', 
                 (group_id, min_members, owner_id, is_active))
        conn.commit()
        conn.close()
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        chat = update.effective_chat
        user = update.effective_user
        
        if chat.type == "private":
            await update.message.reply_text(
                "👋 Guruh Control Botiga xush kelibsiz!\n\n"
                "Botni guruhga qo'shing va ADMIN qiling.\n"
                "Keyin /settings buyrug'i bilan sozlamalarni o'rnating."
            )
        else:
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
                    f"Sozlamalarni /settings orqali o'zgartiring."
                )
    
    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sozlamalar menyusi"""
        chat = update.effective_chat
        user = update.effective_user
        
        if chat.type == "private":
            await update.message.reply_text("❌ Bu buyruq faqat guruhlarda ishlaydi!")
            return
        
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Bu buyruq faqat adminlar uchun!")
            return
        
        settings = self.get_group_settings(chat.id)
        if not settings:
            self.save_group_settings(chat.id, 5, user.id)
            settings = self.get_group_settings(chat.id)
        
        keyboard = [
            [InlineKeyboardButton(f"Minimal a'zolar: {settings['min_members']}", callback_data="change_min_members")],
            [InlineKeyboardButton("Botni o'chirish", callback_data="disable_bot")],
            [InlineKeyboardButton("Botni yoqish", callback_data="enable_bot")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"⚙️ **Guruh Sozlamalari**\n\n"
            f"• Minimal a'zolar: {settings['min_members']}\n"
            f"• Bot holati: {'✅ Faol' if settings['is_active'] else '❌ O'chirilgan'}\n"
            f"• Owner ID: {settings['owner_id']}",
            reply_markup=reply_markup
        )
    
    async def set_members(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Minimal a'zolar sonini o'rnatish"""
        chat = update.effective_chat
        user = update.effective_user
        
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Bu buyruq faqat adminlar uchun!")
            return
        
        if context.args and context.args[0].isdigit():
            min_members = int(context.args[0])
            if min_members < 2:
                await update.message.reply_text("❌ Minimal a'zolar soni 2 dan katta bo'lishi kerak!")
                return
            
            settings = self.get_group_settings(chat.id)
            if settings:
                self.save_group_settings(chat.id, min_members, settings['owner_id'])
            else:
                self.save_group_settings(chat.id, min_members, user.id)
            
            await update.message.reply_text(f"✅ Minimal a'zolar soni {min_members} ga sozlandi!")
        else:
            await update.message.reply_text("❌ Iltimos, son kiriting: /set_members 10")
    
    async def broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Owner uchun xabar yuborish"""
        chat = update.effective_chat
        user = update.effective_user
        
        if not await self.is_owner(update, context):
            await update.message.reply_text("❌ Bu buyruq faqat owner uchun!")
            return
        
        if not context.args:
            await update.message.reply_text("❌ Xabar kiriting: /broadcast Salom hammaga!")
            return
        
        message = " ".join(context.args)
        await update.message.reply_text(f"📢 Owner xabari:\n\n{message}")
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Bot holatini ko'rsatish"""
        chat = update.effective_chat
        
        settings = self.get_group_settings(chat.id)
        if not settings:
            await update.message.reply_text("❌ Bot sozlanmagan. Iltimos, /start buyrug'ini ishlating.")
            return
        
        try:
            member_count = await chat.get_member_count()
        except:
            member_count = "Noma'lum"
        
        status_text = (
            f"📊 **Bot Holati**\n\n"
            f"• Minimal a'zolar: {settings['min_members']}\n"
            f"• Hozirgi a'zolar: {member_count}\n"
            f"• Bot holati: {'✅ Faol' if settings['is_active'] else '❌ O'chirilgan'}\n"
            f"• Owner ID: {settings['owner_id']}"
        )
        
        await update.message.reply_text(status_text)
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inline tugmalarni boshqarish"""
        query = update.callback_query
        await query.answer()
        
        chat = query.message.chat
        data = query.data
        
        if data == "change_min_members":
            await query.edit_message_text(
                "Minimal a'zolar sonini o'zgartirish uchun:\n"
                "/set_members [son]\n\n"
                "Masalan: /set_members 10"
            )
        elif data == "disable_bot":
            settings = self.get_group_settings(chat.id)
            if settings:
                self.save_group_settings(chat.id, settings['min_members'], settings['owner_id'], 0)
                await query.edit_message_text("✅ Bot o'chirildi! Endi hamma yozishi mumkin.")
        elif data == "enable_bot":
            settings = self.get_group_settings(chat.id)
            if settings:
                self.save_group_settings(chat.id, settings['min_members'], settings['owner_id'], 1)
                await query.edit_message_text("✅ Bot yoqildi! Endi minimal a'zolar cheklovi qo'llaniladi.")
    
    async def new_chat_members(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Yangi a'zolar qo'shilganda"""
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:
                chat = update.effective_chat
                user = update.effective_user
                
                self.save_group_settings(chat.id, 5, user.id)
                
                await update.message.reply_text(
                    "🤖 Guruh Control Botiga xush kelibsiz!\n\n"
                    "Avtomatik sozlamalar yaratildi:\n"
                    "• Minimal a'zolar soni: 5\n"
                    "• Owner: siz\n\n"
                    "Sozlamalarni /settings orqali o'zgartiring.\n"
                    "Bot to'liq ishlashi uchun ADMIN huquqlarini bering!"
                )
    
    async def left_chat_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """A'zo chiqib ketganda"""
        if update.message.left_chat_member.id == context.bot.id:
            chat_id = update.message.chat.id
            self.cleanup_group_data(chat_id)
    
    def cleanup_group_data(self, group_id):
        """Guruh ma'lumotlarini tozalash"""
        conn = sqlite3.connect('group_manager.db')
        c = conn.cursor()
        c.execute('DELETE FROM group_settings WHERE group_id = ?', (group_id,))
        conn.commit()
        conn.close()
    
    async def handle_group_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Guruh xabarlarini boshqarish"""
        try:
            chat = update.effective_chat
            user = update.effective_user
            message = update.effective_message
            
            if user and user.id == context.bot.id:
                return
            
            settings = self.get_group_settings(chat.id)
            if not settings:
                return
            
            if not settings['is_active']:
                return
            
            if await self.is_admin(update, context) or await self.is_owner(update, context):
                return
            
            member_count = await chat.get_member_count()
            min_members = settings['min_members']
            
            if member_count < min_members:
                try:
                    await message.delete()
                    warning = await message.reply_text(
                        f"❌ Hozir guruhda {member_count} ta a'zo bor. "
                        f"Minimal {min_members} ta a'zo bo'lgachgina xabar yozish mumkin!"
                    )
                    await context.job_queue.run_once(
                        self.delete_warning, 5, 
                        data=warning.chat_id, 
                        name=str(warning.message_id)
                    )
                except TelegramError as e:
                    logger.error(f"Xabarni o'chirishda xato: {e}")
        
        except Exception as e:
            logger.error(f"Xatolik handle_group_message: {e}")
    
    async def delete_warning(self, context: ContextTypes.DEFAULT_TYPE):
        """Ogohlantirish xabarini o'chirish"""
        try:
            chat_id = context.job.data
            message_id = int(context.job.name)
            await context.bot.delete_message(chat_id, message_id)
        except TelegramError as e:
            logger.error(f"Ogohlantirishni o'chirishda xato: {e}")
    
    async def is_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin tekshirish"""
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
        """Owner tekshirish"""
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
        """Yordam buyrug'i"""
        help_text = """
🤖 **Guruh Control Bot - Yordam**

**Buyruqlar:**
/start - Botni ishga tushirish
/settings - Sozlamalar menyusi
/set_members [son] - Minimal a'zolar sonini o'rnatish
/status - Bot holatini ko'rish
/broadcast [xabar] - Owner uchun xabar yuborish
/help - Yordam

**Ishlash tartibi:**
1. Botni guruhga qo'shing
2. Admin qiling (barcha huquqlar bilan)
3. /settings orqali sozlamalarni o'rnating
4. Bot avtomatik ishlay boshlaydi
        """
        await update.message.reply_text(help_text)

# Ishga tushirish
if __name__ == "__main__":
    TOKEN = "8227647066:AAHVzzhMSgDCYz3pLqg96N8iQKlYcplhAuo"  # O'z bot tokeningizni qo'ying
    bot = GroupControlBot(TOKEN)
    bot.application.run_polling()
