import os
import logging
import json
import re
from datetime import datetime
from typing import Dict, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes, ConversationHandler
)

# ==================== НАСТРОЙКА ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота (ЗАМЕНИТЕ НА СВОЙ!)
BOT_TOKEN = "8508544328:AAEc-lYux_hf8pn1e-v0I9MS8Xh7MdWEzW0"

# ID владельца (ВАШ ID)
OWNER_ID = 8050595279

# Состояния
LINK, REASON, DESCRIPTION = range(3)

# ==================== ДАННЫЕ ====================
class Database:
    def __init__(self):
        self.data_dir = "data"
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.reports_file = os.path.join(self.data_dir, "reports.json")
        self.admins_file = os.path.join(self.data_dir, "admins.json")
        
        self.reports = self.load_json(self.reports_file)
        self.admins = self.load_json(self.admins_file)
        
        # Автоматически добавляем владельца
        if str(OWNER_ID) not in self.admins:
            self.admins[str(OWNER_ID)] = {
                "user_id": OWNER_ID,
                "role": "owner",
                "display_name": "👑 Владелец системы"
            }
            self.save_admins()
    
    def load_json(self, filename):
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_json(self, data, filename):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def save_reports(self):
        self.save_json(self.reports, self.reports_file)
    
    def save_admins(self):
        self.save_json(self.admins, self.admins_file)
    
    def add_report(self, report_id, report_data):
        self.reports[report_id] = report_data
        self.save_reports()
    
    def is_admin(self, user_id):
        return str(user_id) in self.admins

# Инициализация базы данных
db = Database()

# ==================== ПРИЧИНЫ ЖАЛОБ ====================
REASONS = [
    {"id": "spam", "name": "📨 Спам и навязчивая реклама", "severity": "medium"},
    {"id": "violence", "name": "⚔️ Насилие и угрозы", "severity": "high"},
    {"id": "pornography", "name": "🔞 Порнография", "severity": "high"},
    {"id": "drugs", "name": "💊 Пропаганда наркотиков", "severity": "critical"},
    {"id": "fraud", "name": "🎭 Мошенничество", "severity": "high"},
    {"id": "terrorism", "name": "🚨 Терроризм", "severity": "critical"},
    {"id": "child_abuse", "name": "👶 Жестокость к детям", "severity": "critical"},
    {"id": "illegal_goods", "name": "🚫 Незаконные товары", "severity": "high"},
    {"id": "copyright", "name": "©️ Нарушение авторских прав", "severity": "medium"},
    {"id": "personal_dislike", "name": "👎 Не нравится контент", "severity": "low"},
    {"id": "remove_request", "name": "🗑️ Запрос на удаление", "severity": "low"},
    {"id": "personal_data", "name": "📱 Персональные данные", "severity": "high"}
]

# ==================== ОСНОВНЫЕ КОМАНДЫ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    
    text = """
🏛️ *Государственная система модерации контента*

*Официальный бот для подачи жалоб на контент в Telegram*

📋 *Функции:*
• Подача жалоб на нарушающий контент
• Рассмотрение жалоб администраторами
• Система уведомлений о статусе

⚖️ *Правовая основа:*
Федеральный закон №149-ФЗ «Об информации»
Федеральный закон №436-ФЗ «О защите детей»

👇 *Выберите действие:*
"""
    
    buttons = [
        [InlineKeyboardButton("📨 Подать жалобу", callback_data="submit_report")],
        [InlineKeyboardButton("📊 Статус жалоб", callback_data="check_status")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    
    # Добавляем админ-панель если пользователь админ
    if db.is_admin(user.id):
        buttons.append([InlineKeyboardButton("🛡️ Админ-панель", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(buttons)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    
    return LINK

async def submit_report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало подачи жалобы"""
    text = """
📋 *Подача официальной жалобы*

🔗 *Отправьте ссылку в формате:*
• @username
• t.me/username
• https://t.me/username

⚠️ *Требования:*
• Минимум 5 символов
• Только латинские буквы и цифры

👇 *Отправьте ссылку:*
"""
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")
    
    return LINK

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ссылки"""
    link = update.message.text.strip()
    
    # Простая валидация
    pattern = r'^(?:@[A-Za-z0-9_]{5,}|(?:https?://)?t\.me/[A-Za-z0-9_]{5,})$'
    
    if not re.match(pattern, link):
        await update.message.reply_text(
            "❌ *Неверный формат ссылки!*\n\n"
            "Примеры правильных ссылок:\n"
            "• @telegram\n"
            "• t.me/telegram\n"
            "• https://t.me/telegram\n\n"
            "Повторите ввод:",
            parse_mode="Markdown"
        )
        return LINK
    
    context.user_data['link'] = link
    
    # Показываем выбор причины
    buttons = []
    for reason in REASONS:
        buttons.append([InlineKeyboardButton(reason['name'], callback_data=f"reason_{reason['id']}")])
    
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    
    reply_markup = InlineKeyboardMarkup(buttons)
    
    await update.message.reply_text(
        "✅ *Ссылка принята!*\n\n"
        "👇 *Выберите причину жалобы:*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
    return REASON

async def handle_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора причины"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("❌ *Жалоба отменена*", parse_mode="Markdown")
        return ConversationHandler.END
    
    reason_id = query.data.replace("reason_", "")
    
    # Находим выбранную причину
    selected_reason = None
    for reason in REASONS:
        if reason['id'] == reason_id:
            selected_reason = reason
            break
    
    if not selected_reason:
        await query.edit_message_text("❌ *Ошибка выбора причины*", parse_mode="Markdown")
        return ConversationHandler.END
    
    context.user_data['reason'] = selected_reason
    
    await query.edit_message_text(
        f"📝 *Причина: {selected_reason['name']}*\n\n"
        "👇 *Опишите подробно нарушение:*\n\n"
        "Укажите:\n"
        "• Что именно нарушает правила\n"
        "• Когда было опубликовано\n"
        "• Дополнительные детали\n\n"
        "*Максимум 1000 символов*",
        parse_mode="Markdown"
    )
    
    return DESCRIPTION

async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка описания"""
    description = update.message.text.strip()
    
    if len(description) > 1000:
        await update.message.reply_text(
            "❌ *Слишком длинное описание!*\n"
            "Сократите до 1000 символов и отправьте снова:",
            parse_mode="Markdown"
        )
        return DESCRIPTION
    
    if len(description) < 10:
        await update.message.reply_text(
            "❌ *Слишком короткое описание!*\n"
            "Опишите нарушение подробнее (минимум 10 символов):",
            parse_mode="Markdown"
        )
        return DESCRIPTION
    
    user = update.effective_user
    link = context.user_data['link']
    reason = context.user_data['reason']
    
    # Создаем ID жалобы
    report_id = f"REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Сохраняем жалобу
    report_data = {
        "id": report_id,
        "user_id": user.id,
        "username": user.username,
        "link": link,
        "reason": reason['name'],
        "description": description,
        "status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    db.add_report(report_id, report_data)
    
    # Уведомляем администраторов
    await notify_admins(context.bot, report_data)
    
    await update.message.reply_text(
        f"✅ *Жалоба #{report_id} отправлена!*\n\n"
        f"📋 *Детали:*\n"
        f"• Причина: {reason['name']}\n"
        f"• Ссылка: {link}\n"
        f"• Статус: На рассмотрении\n\n"
        f"⏱️ *Срок рассмотрения:* 24-48 часов\n"
        f"📞 *Поддержка:* @aurieza",
        parse_mode="Markdown"
    )
    
    # Очищаем данные
    context.user_data.clear()
    
    return ConversationHandler.END

async def notify_admins(bot, report):
    """Уведомление администраторов о новой жалобе"""
    for admin_id_str in db.admins:
        try:
            admin_id = int(admin_id_str)
            text = f"""
🚨 *НОВАЯ ЖАЛОБА #{report['id']}*

📋 *Детали:*
• От: @{report.get('username', 'без username')}
• Ссылка: {report['link']}
• Причина: {report['reason']}
• Описание: {report['description'][:200]}...

⏰ *Дата:* {report['created_at']}
"""
            
            # Кнопки для администратора
            keyboard = [
                [
                    InlineKeyboardButton("✅ Принять", callback_data=f"approve_{report['id']}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{report['id']}")
                ],
                [
                    InlineKeyboardButton("📝 Ответить", callback_data=f"reply_{report['id']}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Не удалось уведомить администратора {admin_id_str}: {e}")

# ==================== АДМИН-ПАНЕЛЬ ====================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ-панель"""
    user = update.effective_user
    
    if not db.is_admin(user.id):
        await update.message.reply_text("❌ *Доступ запрещен!*", parse_mode="Markdown")
        return
    
    # Статистика
    total_reports = len(db.reports)
    pending_reports = len([r for r in db.reports.values() if r['status'] == 'pending'])
    
    text = f"""
🛡️ *АДМИН-ПАНЕЛЬ*

👤 *Администратор:* {db.admins.get(str(user.id), {}).get('display_name', 'Админ')}
📊 *Статистика:*
• Всего жалоб: {total_reports}
• Ожидают: {pending_reports}
• Админов: {len(db.admins)}

👇 *Выберите действие:*
"""
    
    buttons = [
        [InlineKeyboardButton("📋 Ожидающие жалобы", callback_data="admin_pending")],
        [InlineKeyboardButton("📊 Полная статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Управление админами", callback_data="admin_manage")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(buttons)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def admin_pending_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр ожидающих жалоб"""
    query = update.callback_query
    await query.answer()
    
    pending_reports = [r for r in db.reports.values() if r['status'] == 'pending']
    
    if not pending_reports:
        await query.edit_message_text("📭 *Нет ожидающих жалоб*", parse_mode="Markdown")
        return
    
    # Показываем первую жалобу
    context.user_data['admin_reports'] = pending_reports
    context.user_data['current_report'] = 0
    
    await show_report_to_admin(update, context, pending_reports[0])

async def show_report_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, report):
    """Показ жалобы администратору"""
    query = update.callback_query
    
    text = f"""
📋 *ЖАЛОБА #{report['id']}*

👤 *От:* @{report.get('username', 'без username')} (ID: {report['user_id']})
🔗 *Ссылка:* {report['link']}
📌 *Причина:* {report['reason']}
📝 *Описание:* {report['description']}
⏰ *Дата:* {report['created_at']}

👇 *Выберите действие:*
"""
    
    current_idx = context.user_data.get('current_report', 0)
    total_reports = len(context.user_data.get('admin_reports', []))
    
    buttons = [
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"approve_{report['id']}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{report['id']}")
        ],
        [
            InlineKeyboardButton("◀️", callback_data="admin_prev"),
            InlineKeyboardButton(f"{current_idx + 1}/{total_reports}", callback_data="page_info"),
            InlineKeyboardButton("▶️", callback_data="admin_next")
        ],
        [
            InlineKeyboardButton("🛡️ Назад в панель", callback_data="admin_panel")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(buttons)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def handle_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    """Обработка действий администратора"""
    query = update.callback_query
    await query.answer()
    
    if action == "approve":
        report_id = query.data.replace("approve_", "")
        message = "✅ *Жалоба принята*"
        status = "approved"
    else:
        report_id = query.data.replace("reject_", "")
        message = "❌ *Жалоба отклонена*"
        status = "rejected"
    
    # Обновляем статус жалобы
    if report_id in db.reports:
        db.reports[report_id]['status'] = status
        db.reports[report_id]['processed_by'] = query.from_user.id
        db.reports[report_id]['processed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.save_reports()
        
        # Уведомляем пользователя
        report = db.reports[report_id]
        try:
            await context.bot.send_message(
                chat_id=report['user_id'],
                text=f"📢 *Обновление по вашей жалобе #{report_id}*\n\n"
                     f"Статус: {message}\n"
                     f"Дата обработки: {report['processed_at']}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя: {e}")
    
    await query.edit_message_text(message, parse_mode="Markdown")

# ==================== ОБРАБОТЧИКИ CALLBACK ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка всех callback запросов"""
    query = update.callback_query
    data = query.data
    
    try:
        # Главное меню
        if data == "main_menu":
            await start(update, context)
        
        # Подача жалобы
        elif data == "submit_report":
            await submit_report_start(update, context)
        
        # Админ-панель
        elif data == "admin_panel":
            await admin_panel(update, context)
        
        # Ожидающие жалобы
        elif data == "admin_pending":
            await admin_pending_reports(update, context)
        
        # Навигация по жалобам
        elif data == "admin_next":
            await navigate_reports(update, context, "next")
        elif data == "admin_prev":
            await navigate_reports(update, context, "prev")
        
        # Действия с жалобами
        elif data.startswith("approve_"):
            await handle_admin_action(update, context, "approve")
        elif data.startswith("reject_"):
            await handle_admin_action(update, context, "reject")
        
        # Помощь
        elif data == "help":
            await show_help(update, context)
        
        # Отмена
        elif data == "cancel":
            await query.edit_message_text("❌ *Действие отменено*", parse_mode="Markdown")
            return ConversationHandler.END
        
        else:
            await query.answer(f"Команда: {data}")
            
    except Exception as e:
        logger.error(f"Ошибка в callback: {e}")
        await query.answer("⚠️ Ошибка обработки")

async def navigate_reports(update: Update, context: ContextTypes.DEFAULT_TYPE, direction: str):
    """Навигация по жалобам"""
    query = update.callback_query
    await query.answer()
    
    if 'admin_reports' not in context.user_data:
        return
    
    reports = context.user_data['admin_reports']
    current = context.user_data.get('current_report', 0)
    
    if direction == "next":
        current = (current + 1) % len(reports)
    else:
        current = (current - 1) % len(reports)
    
    context.user_data['current_report'] = current
    await show_report_to_admin(update, context, reports[current])

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать помощь"""
    text = """
❓ *ПОМОЩЬ*

📋 *Как подать жалобу:*
1. Нажмите "Подать жалобу"
2. Отправьте ссылку на канал/чат
3. Выберите причину
4. Опишите нарушение

⚖️ *Категории нарушений:*
• Критические (наркотики, терроризм, дети)
• Серьезные (насилие, мошенничество)
• Средние (спам, авторские права)
• Низкие (личные предпочтения)

⏱️ *Сроки рассмотрения:*
• Критические: до 24 часов
• Обычные: 24-48 часов

📞 *Поддержка:*
По всем вопросам: @aurieza
"""
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена"""
    await update.message.reply_text("❌ *Действие отменено*", parse_mode="Markdown")
    return ConversationHandler.END

# ==================== ОБРАБОТЧИК ОШИБОК ====================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}")
    
    if update and update.effective_chat:
        try:
            await update.effective_chat.send_message(
                "⚠️ *Произошла ошибка*\n\n"
                "Пожалуйста, попробуйте позже или используйте команду /start",
                parse_mode="Markdown"
            )
        except:
            pass

# ==================== ГЛАВНАЯ ФУНКЦИЯ ====================
def main():
    """Запуск бота"""
    print("=" * 50)
    print("🏛️  ГОСУДАРСТВЕННАЯ СИСТЕМА МОДЕРАЦИИ")
    print("=" * 50)
    
    try:
        # Создаем приложение
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Проверяем владельца
        if db.is_admin(OWNER_ID):
            print(f"✅ Владелец настроен: ID {OWNER_ID}")
        else:
            print(f"❌ Ошибка: владелец не добавлен!")
        
        # Добавляем обработчики команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("admin", admin_panel))
        application.add_handler(CommandHandler("help", show_help))
        
        # ConversationHandler для подачи жалоб
        conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(submit_report_start, pattern="^submit_report$")
            ],
            states={
                LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link)],
                REASON: [CallbackQueryHandler(handle_reason, pattern="^(reason_|cancel)")],
                DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description)]
            },
            fallbacks=[CommandHandler("cancel", cancel)]
        )
        
        application.add_handler(conv_handler)
        
        # Обработчик callback запросов
        application.add_handler(CallbackQueryHandler(handle_callback))
        
        # Обработчик ошибок
        application.add_error_handler(error_handler)
        
        # Запуск бота
        print(f"\n✅ Бот запускается...")
        print(f"🔗 Токен: {BOT_TOKEN[:10]}...")
        print(f"👑 Владелец: ID {OWNER_ID}")
        print(f"📊 Отчетов в базе: {len(db.reports)}")
        print(f"👥 Администраторов: {len(db.admins)}")
        print("\n" + "=" * 50)
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        print("\nВозможные причины:")
        print("1. Неверный токен бота")
        print("2. Библиотека не установлена")
        print("3. Нет интернет соединения")
        print("\nРешение:")
        print("1. Проверьте токен в BOT_TOKEN")
        print("2. Установите: pip install python-telegram-bot")
        print("3. Проверьте подключение к интернету")

if __name__ == "__main__":
    # Установите библиотеку: pip install python-telegram-bot
    main()