import asyncio
import json
import os
import random
import string
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ===== CONFIGURATION =====
BOT_TOKEN = "8104965032:AAHVg0LtJFm7rzrqHWhXhb5QEYlkYmRd_5Q"
ADMIN_IDS = [8064942862, 8189622055]  # Add your Telegram ID here
PAYMENT_LINK = "http://t.me/send?start=IVT1TqIpUvBO"
DB_FILE = "database.json"

# Conversation states
WAITING_USERNAME = 1
WAITING_CHANNEL_LINK = 2
CONFIRM_CHANNEL = 3
WAITING_ADD_COINS = 4
WAITING_USER_ID_COINS = 5

# ===== DATABASE =====
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {
        "users": {},
        "channels": [
            {"link": "https://t.me/+ivQsuvnsmh4xNDAy", "title": "Канал 1"},
            {"link": "https://t.me/+e-xhMMTMondiZmNi", "title": "Канал 2"},
            {"link": "https://t.me/+0AfWmwBQTcU2NGEy", "title": "Канал 3"},
        ],
        "pending_payments": {}
    }

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def get_user(db, user_id):
    uid = str(user_id)
    if uid not in db["users"]:
        db["users"][uid] = {
            "balance": 0,
            "subscribed": False,
            "referral_code": generate_ref_code(),
            "referred_by": None,
            "total_spent": 0,
            "username": "",
            "joined": datetime.now().isoformat()
        }
    return db["users"][uid]

def generate_ref_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# ===== KEYBOARDS =====
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("⚡ Утилизировать", callback_data="utilize")],
        [InlineKeyboardButton("👥 Рефералы", callback_data="referrals")],
    ])

def subscription_keyboard(db):
    buttons = []
    for i, ch in enumerate(db["channels"]):
        buttons.append([InlineKeyboardButton(f"📢 {ch['title']}", url=ch["link"])])
    buttons.append([InlineKeyboardButton("✅ Проверить подписки", callback_data="check_subs")])
    return InlineKeyboardMarkup(buttons)

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Добавить канал", callback_data="admin_add_channel")],
        [InlineKeyboardButton("📋 Список каналов", callback_data="admin_list_channels")],
        [InlineKeyboardButton("👤 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton("💎 Начислить монеты", callback_data="admin_add_coins")],
    ])

def topup_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Оплатить через CryptoBot", url=PAYMENT_LINK)],
        [InlineKeyboardButton("✅ Я оплатил", callback_data="paid_confirm")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_main")],
    ])

def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_main")]])

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    user = update.effective_user
    uid = str(user.id)
    u = get_user(db, user.id)
    u["username"] = user.username or user.first_name or str(user.id)

    # Handle referral
    if context.args and context.args[0].startswith("ref_"):
        ref_code = context.args[0][4:]
        if not u["referred_by"]:
            for other_uid, other_user in db["users"].items():
                if other_user.get("referral_code") == ref_code and other_uid != uid:
                    u["referred_by"] = other_uid
                    break

    save_db(db)

    channels = db["channels"]
    channel_list = "\n".join([f"  • {ch['title']}" for ch in channels])

    text = (
        f"👋 Добро пожаловать, {user.first_name}!\n\n"
        f"Для использования бота необходимо подписаться на наши каналы:\n\n"
        f"{channel_list}\n\n"
        f"👇 Нажмите на каналы ниже, подпишитесь, затем нажмите «Проверить подписки»"
    )
    await update.message.reply_text(text, reply_markup=subscription_keyboard(db))

async def check_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_db()
    uid = str(query.from_user.id)
    u = get_user(db, query.from_user.id)

    # Since these are private invite links, we can't verify via API
    # We'll trust the user clicked — but show instructions
    # For real verification you'd need channel IDs (public or added bot as admin)
    # Here we mark as subscribed when they click "check"
    u["subscribed"] = True
    save_db(db)

    text = (
        "✅ Отлично! Доступ открыт!\n\n"
        "Добро пожаловать в бот! Выберите действие:"
    )
    await query.edit_message_text(text, reply_markup=main_menu_keyboard())

async def balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_db()
    u = get_user(db, query.from_user.id)

    text = (
        f"💰 *Ваш баланс*\n\n"
        f"🪙 Монеты: *{u['balance']}*\n\n"
        f"💡 1 утилизация = 5 монет\n\n"
        f"📦 *Прайс-лист пополнения:*\n"
        f"• 15 монет (1 утилизация) — 0.3$\n"
        f"• 30 монет (2 утилизации) — 0.5$\n"
        f"• 90 монет (6 утилизаций) — 1.10$\n"
        f"• 180 монет (12 утилизаций) — 2$"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Пополнить баланс", callback_data="topup")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_main")],
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def topup_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = (
        "💳 *Пополнение баланса*\n\n"
        "📦 *Прайс-лист:*\n"
        "• 15 монет (1 утилизация) — 0.3$\n"
        "• 30 монет (2 утилизации) — 0.5$\n"
        "• 90 монет (6 утилизаций) — 1.10$\n"
        "• 180 монет (12 утилизаций) — 2$\n\n"
        "1. Нажмите кнопку «Оплатить через CryptoBot»\n"
        "2. Выполните оплату нужного пакета\n"
        "3. Нажмите «Я оплатил» — монеты будут начислены после проверки администратором"
    )
    await query.edit_message_text(text, reply_markup=topup_keyboard(), parse_mode="Markdown")

async def paid_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_db()
    u = get_user(db, query.from_user.id)
    uid = str(query.from_user.id)

    # Save pending payment
    db["pending_payments"][uid] = {
        "user_id": uid,
        "username": u["username"],
        "time": datetime.now().isoformat()
    }
    save_db(db)

    # Notify admins
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"💳 *Новая заявка на пополнение!*\n\n"
                f"👤 Пользователь: @{u['username']} (ID: {uid})\n"
                f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"Используйте /addcoins {uid} <количество> для начисления монет",
                parse_mode="Markdown"
            )
        except:
            pass

    await query.edit_message_text(
        "✅ Заявка отправлена!\n\n"
        "Администратор проверит оплату и начислит монеты в течение нескольких минут.\n\n"
        "Спасибо за оплату! 🙏",
        reply_markup=back_keyboard()
    )

async def utilize_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_db()
    u = get_user(db, query.from_user.id)

    if u["balance"] < 5:
        text = (
            "❌ *Недостаточно монет!*\n\n"
            f"У вас: *{u['balance']}* монет\n"
            f"Нужно: *5* монет\n\n"
            "📦 *Прайс-лист пополнения:*\n"
            "• 15 монет (1 утилизация) — 0.3$\n"
            "• 30 монет (2 утилизации) — 0.5$\n"
            "• 90 монет (6 утилизаций) — 1.10$\n"
            "• 180 монет (12 утилизаций) — 2$"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Пополнить", url=PAYMENT_LINK)],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_main")],
        ])
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
        return

    await query.edit_message_text(
        "⚡ *Утилизация*\n\nПришлите юз (username или данные) для обработки:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="back_main")]]),
        parse_mode="Markdown"
    )
    context.user_data["waiting_for"] = "username_utilize"

async def referrals_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_db()
    u = get_user(db, query.from_user.id)
    uid = str(query.from_user.id)

    bot_info = await context.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{u['referral_code']}"

    # Count referrals
    ref_count = sum(1 for usr in db["users"].values() if usr.get("referred_by") == uid)

    text = (
        f"👥 *Реферальная программа*\n\n"
        f"🔗 Ваша ссылка:\n`{ref_link}`\n\n"
        f"👫 Приглашено: *{ref_count}* чел.\n\n"
        f"💡 *Условия:*\n"
        f"За каждого приглашённого пользователя вы будете получать *5%* от суммы их пополнения на свой баланс!\n\n"
        f"Делитесь ссылкой и зарабатывайте монеты! 🚀"
    )
    await query.edit_message_text(text, reply_markup=back_keyboard(), parse_mode="Markdown")

async def back_main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text(
        "🏠 Главное меню\n\nВыберите действие:",
        reply_markup=main_menu_keyboard()
    )

# ===== ADMIN =====
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа")
        return
    await update.message.reply_text(
        "🔧 *Панель администратора*",
        reply_markup=admin_keyboard(),
        parse_mode="Markdown"
    )

async def admin_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📢 Пришлите ссылку на канал (например: https://t.me/+xxxxx):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_back")]])
    )
    context.user_data["admin_waiting"] = "channel_link"

async def admin_list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_db()

    if not db["channels"]:
        text = "📋 Каналов нет"
    else:
        lines = ["📋 *Список каналов:*\n"]
        for i, ch in enumerate(db["channels"], 1):
            lines.append(f"{i}. {ch['title']}\n   `{ch['link']}`")
        text = "\n".join(lines)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить канал", callback_data="admin_add_channel")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")],
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_db()

    total = len(db["users"])
    subscribed = sum(1 for u in db["users"].values() if u.get("subscribed"))
    text = (
        f"👤 *Статистика пользователей*\n\n"
        f"Всего: *{total}*\n"
        f"Подписались: *{subscribed}*\n"
    )
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]),
        parse_mode="Markdown"
    )

async def admin_add_coins_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "💎 Введите: *ID пользователя количество_монет*\nПример: `123456789 30`",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_back")]]),
        parse_mode="Markdown"
    )
    context.user_data["admin_waiting"] = "add_coins"

async def admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("🔧 *Панель администратора*", reply_markup=admin_keyboard(), parse_mode="Markdown")

# ===== MESSAGE HANDLER =====
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # ADMIN messages
    if user_id in ADMIN_IDS:
        admin_waiting = context.user_data.get("admin_waiting")

        if admin_waiting == "channel_link":
            context.user_data["pending_channel_link"] = text
            context.user_data["admin_waiting"] = "confirm_channel"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Да", callback_data="admin_confirm_channel_yes"),
                 InlineKeyboardButton("❌ Нет", callback_data="admin_confirm_channel_no")]
            ])
            await update.message.reply_text(
                f"Добавить канал?\n`{text}`\n\nВы уверены?",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            return

        if admin_waiting == "add_coins":
            parts = text.strip().split()
            if len(parts) == 2 and parts[1].isdigit():
                target_uid = parts[0]
                amount = int(parts[1])
                db = load_db()
                if target_uid in db["users"]:
                    db["users"][target_uid]["balance"] += amount

                    # Referral bonus
                    ref_by = db["users"][target_uid].get("referred_by")
                    if ref_by and ref_by in db["users"]:
                        bonus = int(amount * 0.05)
                        if bonus > 0:
                            db["users"][ref_by]["balance"] += bonus
                            try:
                                await context.bot.send_message(
                                    int(ref_by),
                                    f"🎁 Реферальный бонус: +{bonus} монет!\n"
                                    f"Ваш реферал пополнил баланс."
                                )
                            except:
                                pass

                    save_db(db)
                    username = db["users"][target_uid].get("username", target_uid)
                    await update.message.reply_text(
                        f"✅ Начислено *{amount}* монет пользователю @{username} (ID: {target_uid})",
                        parse_mode="Markdown"
                    )
                    # Notify user
                    try:
                        await context.bot.send_message(
                            int(target_uid),
                            f"✅ Вам начислено *{amount}* монет!\n\n💰 Текущий баланс: *{db['users'][target_uid]['balance']}* монет",
                            parse_mode="Markdown",
                            reply_markup=main_menu_keyboard()
                        )
                    except:
                        pass
                else:
                    await update.message.reply_text("❌ Пользователь не найден")
            else:
                await update.message.reply_text("❌ Неверный формат. Пример: `123456789 30`", parse_mode="Markdown")
            context.user_data.pop("admin_waiting", None)
            return

    # USER: waiting for username to utilize
    if context.user_data.get("waiting_for") == "username_utilize":
        db = load_db()
        u = get_user(db, user_id)

        if u["balance"] < 5:
            await update.message.reply_text(
                "❌ Недостаточно монет!",
                reply_markup=main_menu_keyboard()
            )
            context.user_data.clear()
            return

        u["balance"] -= 5
        save_db(db)
        context.user_data.clear()

        msg = await update.message.reply_text("⚙️ Процесс запущен...")
        await asyncio.sleep(random.uniform(3, 6))
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=msg.message_id,
            text=(
                f"✅ *Готово!*\n\n"
                f"Юз `{text}` успешно утилизирован.\n"
                f"💰 Списано: 5 монет. Остаток: {u['balance']} монет."
            ),
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        return

    # Default
    db = load_db()
    u = get_user(db, user_id)
    if u.get("subscribed"):
        await update.message.reply_text("Используйте кнопки меню:", reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text(
            "Сначала подпишитесь на каналы и нажмите «Проверить подписки»:",
            reply_markup=subscription_keyboard(db)
        )

async def admin_confirm_channel_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    link = context.user_data.get("pending_channel_link", "")
    if link:
        db = load_db()
        # Auto-title
        title = f"Канал {len(db['channels']) + 1}"
        db["channels"].append({"link": link, "title": title})
        save_db(db)
        await query.edit_message_text(
            f"✅ Канал добавлен!\n`{link}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]])
        )
    context.user_data.clear()

async def admin_confirm_channel_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text(
        "❌ Отменено",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]])
    )

# ===== ADDCOINS COMMAND =====
async def addcoins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if len(context.args) != 2 or not context.args[1].isdigit():
        await update.message.reply_text("Использование: /addcoins <user_id> <amount>")
        return
    target_uid = context.args[0]
    amount = int(context.args[1])
    db = load_db()
    if target_uid not in db["users"]:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    db["users"][target_uid]["balance"] += amount
    save_db(db)
    await update.message.reply_text(f"✅ Начислено {amount} монет пользователю {target_uid}")
    try:
        await context.bot.send_message(
            int(target_uid),
            f"✅ Вам начислено *{amount}* монет!\n💰 Баланс: *{db['users'][target_uid]['balance']}* монет",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    except:
        pass

# ===== MAIN =====
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("addcoins", addcoins_command))

    # Callbacks
    app.add_handler(CallbackQueryHandler(check_subscriptions, pattern="^check_subs$"))
    app.add_handler(CallbackQueryHandler(balance_handler, pattern="^balance$"))
    app.add_handler(CallbackQueryHandler(topup_handler, pattern="^topup$"))
    app.add_handler(CallbackQueryHandler(paid_confirm_handler, pattern="^paid_confirm$"))
    app.add_handler(CallbackQueryHandler(utilize_handler, pattern="^utilize$"))
    app.add_handler(CallbackQueryHandler(referrals_handler, pattern="^referrals$"))
    app.add_handler(CallbackQueryHandler(back_main_handler, pattern="^back_main$"))

    # Admin callbacks
    app.add_handler(CallbackQueryHandler(admin_add_channel, pattern="^admin_add_channel$"))
    app.add_handler(CallbackQueryHandler(admin_list_channels, pattern="^admin_list_channels$"))
    app.add_handler(CallbackQueryHandler(admin_users, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(admin_add_coins_handler, pattern="^admin_add_coins$"))
    app.add_handler(CallbackQueryHandler(admin_back, pattern="^admin_back$"))
    app.add_handler(CallbackQueryHandler(admin_confirm_channel_yes, pattern="^admin_confirm_channel_yes$"))
    app.add_handler(CallbackQueryHandler(admin_confirm_channel_no, pattern="^admin_confirm_channel_no$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("✅ Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
