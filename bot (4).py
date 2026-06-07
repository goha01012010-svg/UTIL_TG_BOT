import asyncio
import json
import os
import random
import string
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.error import TelegramError

# ===== CONFIG =====
BOT_TOKEN = "8104965032:AAHVg0LtJFm7rzrqHWhXhb5QEYlkYmRd_5Q"
ADMIN_IDS = [8189622055, 8064942862]
PAYMENT_LINK = "http://t.me/send?start=IVT1TqIpUvBO"
DATA_DIR = "data"
DB_FILE = os.path.join(DATA_DIR, "database.json")
LOGO_PATH = "logo.png"

# ===== DATABASE =====
DEFAULT_CHANNELS = [
    {"link": "https://t.me/+ivQsuvnsmh4xNDAy", "title": "Канал 1", "chat_id": -1003594114095},
    {"link": "https://t.me/+e-xhMMTMondiZmNi",  "title": "Канал 2", "chat_id": -1003693383185},
    {"link": "https://t.me/+0AfWmwBQTcU2NGEy",  "title": "Канал 3", "chat_id": -1003983524031},
]

def load_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
        # Ensure all keys exist
        db.setdefault("users", {})
        db.setdefault("channels", DEFAULT_CHANNELS)
        db.setdefault("promo_codes", {})
        db.setdefault("pending_payments", {})
        return db
    # First run — create with defaults
    db = {
        "users": {},
        "channels": DEFAULT_CHANNELS,
        "promo_codes": {},
        "pending_payments": {}
    }
    save_db(db)
    return db

def save_db(db):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def get_user(db, user_id):
    uid = str(user_id)
    if uid not in db["users"]:
        db["users"][uid] = {
            "balance": 0,
            "subscribed": False,
            "referral_code": ''.join(random.choices(string.ascii_uppercase + string.digits, k=8)),
            "referred_by": None,
            "username": "",
            "joined": datetime.now().isoformat()
        }
    return db["users"][uid]

# ===== SUBSCRIPTION CHECK =====
async def check_user_subscribed(bot, user_id: int, db: dict):
    """Returns (all_ok, not_subscribed_list)"""
    not_subscribed = []
    for ch in db["channels"]:
        chat_id = ch.get("chat_id")
        if not chat_id:
            continue
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in ["left", "kicked", "banned"]:
                not_subscribed.append(ch)
        except TelegramError:
            not_subscribed.append(ch)
    return len(not_subscribed) == 0, not_subscribed

# ===== LOGO SENDER =====
async def send_logo(chat_id, bot, text, keyboard=None):
    kwargs = {"caption": text, "parse_mode": "Markdown"}
    if keyboard:
        kwargs["reply_markup"] = keyboard
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as photo:
            return await bot.send_photo(chat_id=chat_id, photo=photo, **kwargs)
    else:
        return await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=keyboard)

async def edit_or_send(query, text, keyboard=None):
    try:
        await query.message.delete()
    except:
        pass
    await send_logo(query.message.chat_id, query.get_bot(), text, keyboard)

# ===== KEYBOARDS =====
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("⚡ Утилизировать", callback_data="utilize")],
        [InlineKeyboardButton("👥 Рефералы", callback_data="referrals")],
    ])

def subscription_keyboard(db):
    buttons = []
    for ch in db["channels"]:
        buttons.append([InlineKeyboardButton(f"📢 {ch['title']}", url=ch["link"])])
    buttons.append([InlineKeyboardButton("✅ Проверить подписки", callback_data="check_subs")])
    return InlineKeyboardMarkup(buttons)

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Добавить канал", callback_data="admin_add_channel")],
        [InlineKeyboardButton("🗑 Удалить канал", callback_data="admin_del_channel")],
        [InlineKeyboardButton("📋 Список каналов", callback_data="admin_list_channels")],
        [InlineKeyboardButton("🎟 Промокоды", callback_data="admin_promos")],
        [InlineKeyboardButton("👤 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton("💎 Начислить монеты", callback_data="admin_add_coins")],
    ])

def back_keyboard(cb="back_main"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=cb)]])

def topup_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Оплатить через CryptoBot", url=PAYMENT_LINK)],
        [InlineKeyboardButton("✅ Я оплатил", callback_data="paid_confirm")],
        [InlineKeyboardButton("🎟 У меня промокод", callback_data="use_promo")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_main")],
    ])

# ===== USER HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    db = load_db()
    user = update.effective_user
    uid = str(user.id)
    u = get_user(db, user.id)
    u["username"] = user.username or user.first_name or str(user.id)

    if context.args and context.args[0].startswith("ref_"):
        ref_code = context.args[0][4:]
        if not u["referred_by"]:
            for other_uid, other_user in db["users"].items():
                if other_user.get("referral_code") == ref_code and other_uid != uid:
                    u["referred_by"] = other_uid
                    break
    save_db(db)

    text = (
        f"👋 Добро пожаловать, *{user.first_name}*!\n\n"
        f"Для использования бота необходимо подписаться на наши каналы.\n\n"
        f"👇 Нажмите на каналы, подпишитесь, затем нажмите «Проверить подписки»"
    )
    await send_logo(update.effective_chat.id, context.bot, text, subscription_keyboard(db))

async def check_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_db()
    u = get_user(db, query.from_user.id)

    all_ok, not_subbed = await check_user_subscribed(context.bot, query.from_user.id, db)

    if not all_ok and not_subbed:
        ch_list = "\n".join([f"• {ch['title']}" for ch in not_subbed])
        await edit_or_send(query,
            f"❌ *Вы не подписаны на все каналы!*\n\nНе подписаны:\n{ch_list}\n\nПодпишитесь и нажмите «Проверить подписки» снова.",
            subscription_keyboard(db)
        )
        return

    u["subscribed"] = True
    save_db(db)
    await edit_or_send(query, "✅ *Доступ открыт!*\n\nДобро пожаловать! Выберите действие:", main_menu_keyboard())

async def balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_db()
    u = get_user(db, query.from_user.id)
    text = (
        f"💰 *Ваш баланс*\n\n"
        f"🪙 Монеты: *{u['balance']}*\n\n"
        f"💡 1 утилизация = 5 монет\n\n"
        f"📦 *Прайс-лист:*\n"
        f"• 15 монет (1 утилизация) — 0.3$\n"
        f"• 30 монет (2 утилизации) — 0.5$\n"
        f"• 90 монет (6 утилизаций) — 1.10$\n"
        f"• 180 монет (12 утилизаций) — 2$"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Пополнить баланс", callback_data="topup")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_main")],
    ])
    await edit_or_send(query, text, keyboard)

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
        "1️⃣ Нажмите «Оплатить через CryptoBot»\n"
        "2️⃣ Выполните оплату нужного пакета\n"
        "3️⃣ Нажмите «Я оплатил»"
    )
    await edit_or_send(query, text, topup_keyboard())

async def paid_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_db()
    u = get_user(db, query.from_user.id)
    uid = str(query.from_user.id)
    db["pending_payments"][uid] = {"user_id": uid, "username": u["username"], "time": datetime.now().isoformat()}
    save_db(db)
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id,
                f"💳 *Новая заявка на пополнение!*\n\n"
                f"👤 @{u['username']} (ID: `{uid}`)\n"
                f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"Начислите монеты через /admin → Начислить монеты",
                parse_mode="Markdown")
        except:
            pass
    await edit_or_send(query,
        "✅ *Заявка отправлена!*\n\nАдминистратор проверит оплату и начислит монеты. 🙏",
        back_keyboard()
    )

async def use_promo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await edit_or_send(query,
        "🎟 *Введите промокод:*",
        InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="back_main")]])
    )
    context.user_data["waiting_for"] = "promo_code"

async def utilize_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_db()
    u = get_user(db, query.from_user.id)
    if u["balance"] < 5:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Пополнить", callback_data="topup")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_main")],
        ])
        await edit_or_send(query,
            f"❌ *Недостаточно монет!*\n\nУ вас: *{u['balance']}* монет\nНужно: *5* монет\n\n"
            f"📦 *Прайс-лист:*\n• 15 монет — 0.3$\n• 30 монет — 0.5$\n• 90 монет — 1.10$\n• 180 монет — 2$",
            keyboard
        )
        return
    await edit_or_send(query,
        "⚡ *Утилизация*\n\nПришлите юз (username или данные) для обработки:",
        InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="back_main")]])
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
    ref_count = sum(1 for usr in db["users"].values() if usr.get("referred_by") == uid)
    text = (
        f"👥 *Реферальная программа*\n\n"
        f"🔗 Ваша ссылка:\n`{ref_link}`\n\n"
        f"👫 Приглашено: *{ref_count}* чел.\n\n"
        f"💡 За каждого приглашённого вы получаете *5%* от суммы их пополнения! 🚀"
    )
    await edit_or_send(query, text, back_keyboard())

async def back_main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await edit_or_send(query, "🏠 *Главное меню*\n\nВыберите действие:", main_menu_keyboard())

# ===== ADMIN HANDLERS =====
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа")
        return
    await send_logo(update.effective_chat.id, context.bot, "🔧 *Панель администратора*", admin_keyboard())

async def admin_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await edit_or_send(query,
        "📢 *Шаг 1 из 3*\n\nПришлите ссылку на канал:\nНапример: `https://t.me/+xxxxx`",
        InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_back")]])
    )
    context.user_data["admin_waiting"] = "channel_link"

async def admin_del_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_db()
    if not db["channels"]:
        await edit_or_send(query, "📋 Каналов нет", back_keyboard("admin_back"))
        return
    buttons = []
    for i, ch in enumerate(db["channels"]):
        buttons.append([InlineKeyboardButton(f"🗑 {ch['title']}", callback_data=f"del_ch_{i}")])
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_back")])
    await edit_or_send(query, "🗑 *Выберите канал для удаления:*", InlineKeyboardMarkup(buttons))

async def del_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split("_")[-1])
    db = load_db()
    if idx < len(db["channels"]):
        removed = db["channels"].pop(idx)
        save_db(db)
        await edit_or_send(query, f"✅ Канал *{removed['title']}* удалён.", back_keyboard("admin_back"))
    else:
        await edit_or_send(query, "❌ Канал не найден", back_keyboard("admin_back"))

async def admin_list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_db()
    if not db["channels"]:
        text = "📋 Каналов нет"
    else:
        lines = ["📋 *Список каналов:*\n"]
        for i, ch in enumerate(db["channels"], 1):
            chat_id = ch.get("chat_id") or "не указан"
            lines.append(f"{i}. *{ch['title']}*\n   `{ch['link']}`\n   chat\\_id: `{chat_id}`")
        text = "\n\n".join(lines)
    await edit_or_send(query, text, InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить", callback_data="admin_add_channel")],
        [InlineKeyboardButton("🗑 Удалить", callback_data="admin_del_channel")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")],
    ]))

async def admin_promos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_db()
    promos = db.get("promo_codes", {})
    if promos:
        lines = ["🎟 *Промокоды:*\n"]
        for code, data in promos.items():
            lines.append(f"• `{code}` — {data['coins']} монет ({data['used']}/{data['limit']} исп.)")
        text = "\n".join(lines)
    else:
        text = "🎟 *Промокодов нет*"
    await edit_or_send(query, text, InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Создать промокод", callback_data="admin_create_promo")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")],
    ]))

async def admin_create_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await edit_or_send(query,
        "🎟 Введите промокод в формате:\n`КОД МОНЕТЫ ЛИМИТ`\n\nПример:\n`BLICH2024 30 100`",
        InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_back")]])
    )
    context.user_data["admin_waiting"] = "create_promo"

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_db()
    total = len(db["users"])
    subscribed = sum(1 for u in db["users"].values() if u.get("subscribed"))
    await edit_or_send(query,
        f"👤 *Статистика*\n\nВсего пользователей: *{total}*\nПодписались: *{subscribed}*",
        back_keyboard("admin_back")
    )

async def admin_add_coins_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await edit_or_send(query,
        "💎 Введите: `ID количество_монет`\nПример: `123456789 30`",
        InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_back")]])
    )
    context.user_data["admin_waiting"] = "add_coins"

async def admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await edit_or_send(query, "🔧 *Панель администратора*", admin_keyboard())

async def admin_confirm_channel_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = context.user_data.pop("pending_channel", None)
    context.user_data.clear()
    if data:
        db = load_db()
        db["channels"].append(data)
        save_db(db)
        await edit_or_send(query, f"✅ Канал *{data['title']}* добавлен!\n\n⚠️ Не забудьте добавить бота как администратора в канал для работы проверки подписки.", back_keyboard("admin_back"))
    else:
        await edit_or_send(query, "❌ Ошибка", back_keyboard("admin_back"))

async def admin_confirm_channel_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await edit_or_send(query, "❌ Отменено", back_keyboard("admin_back"))

# ===== MESSAGE HANDLER =====
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # ===== ADMIN MESSAGES =====
    if user_id in ADMIN_IDS:
        admin_waiting = context.user_data.get("admin_waiting")

        if admin_waiting == "channel_link":
            context.user_data["pending_channel_link"] = text
            context.user_data["admin_waiting"] = "channel_title"
            await send_logo(update.effective_chat.id, context.bot,
                f"✅ Ссылка сохранена!\n\n📢 *Шаг 2 из 3*\n\nВведите название кнопки:\nНапример: `Канал новостей`",
                InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_back")]])
            )
            return

        if admin_waiting == "channel_title":
            context.user_data["pending_channel_title"] = text
            context.user_data["admin_waiting"] = "channel_chatid"
            await send_logo(update.effective_chat.id, context.bot,
                f"✅ Название сохранено!\n\n📢 *Шаг 3 из 3*\n\nВведите chat\\_id канала для проверки подписки:\nНапример: `-1001234567890`\n\nЕсли не знаете — отправьте `0` (проверка подписки работать не будет)",
                InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_back")]])
            )
            return

        if admin_waiting == "channel_chatid":
            context.user_data.pop("admin_waiting", None)
            link = context.user_data.pop("pending_channel_link", "")
            title = context.user_data.pop("pending_channel_title", "Канал")
            try:
                chat_id = int(text)
                if chat_id == 0:
                    chat_id = None
            except:
                chat_id = None

            channel_data = {"link": link, "title": title, "chat_id": chat_id}
            context.user_data["pending_channel"] = channel_data

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Да", callback_data="admin_confirm_channel_yes"),
                 InlineKeyboardButton("❌ Нет", callback_data="admin_confirm_channel_no")]
            ])
            chat_id_display = chat_id or "не указан (без проверки)"
            await send_logo(update.effective_chat.id, context.bot,
                f"Добавить канал?\n\n🔗 `{link}`\n📌 Название: *{title}*\n🆔 chat\\_id: `{chat_id_display}`\n\nВы уверены?",
                keyboard
            )
            return

        if admin_waiting == "add_coins":
            context.user_data.pop("admin_waiting", None)
            parts = text.split()
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
                                await context.bot.send_message(int(ref_by),
                                    f"🎁 Реферальный бонус: *+{bonus} монет!*\nВаш реферал пополнил баланс.",
                                    parse_mode="Markdown")
                            except:
                                pass
                    save_db(db)
                    uname = db["users"][target_uid].get("username", target_uid)
                    await update.message.reply_text(f"✅ Начислено *{amount}* монет → @{uname}", parse_mode="Markdown")
                    try:
                        await send_logo(int(target_uid), context.bot,
                            f"✅ Вам начислено *{amount}* монет!\n💰 Баланс: *{db['users'][target_uid]['balance']}* монет",
                            main_menu_keyboard()
                        )
                    except:
                        pass
                else:
                    await update.message.reply_text("❌ Пользователь не найден")
            else:
                await update.message.reply_text("❌ Формат: `ID количество`", parse_mode="Markdown")
            return

        if admin_waiting == "create_promo":
            context.user_data.pop("admin_waiting", None)
            parts = text.split()
            if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
                code = parts[0].upper()
                coins = int(parts[1])
                limit = int(parts[2])
                db = load_db()
                db["promo_codes"][code] = {"coins": coins, "limit": limit, "used": 0, "users": []}
                save_db(db)
                await update.message.reply_text(
                    f"✅ Промокод создан!\n\n🎟 `{code}`\n💰 {coins} монет\n👥 Лимит: {limit} раз",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("❌ Формат: `КОД МОНЕТЫ ЛИМИТ`", parse_mode="Markdown")
            return

    # ===== USER MESSAGES =====
    waiting = context.user_data.get("waiting_for")

    if waiting == "promo_code":
        context.user_data.pop("waiting_for", None)
        db = load_db()
        uid = str(user_id)
        code = text.upper()
        promos = db.get("promo_codes", {})
        if code not in promos:
            await send_logo(update.effective_chat.id, context.bot, "❌ *Неверный промокод!*", back_keyboard())
        elif uid in promos[code].get("users", []):
            await send_logo(update.effective_chat.id, context.bot, "❌ *Вы уже использовали этот промокод!*", back_keyboard())
        elif promos[code]["used"] >= promos[code]["limit"]:
            await send_logo(update.effective_chat.id, context.bot, "❌ *Промокод исчерпан!*", back_keyboard())
        else:
            u = get_user(db, user_id)
            u["balance"] += promos[code]["coins"]
            promos[code]["used"] += 1
            promos[code]["users"].append(uid)
            save_db(db)
            await send_logo(update.effective_chat.id, context.bot,
                f"✅ *Промокод активирован!*\n\n🎁 +{promos[code]['coins']} монет\n💰 Баланс: *{u['balance']}* монет",
                main_menu_keyboard()
            )
        return

    if waiting == "username_utilize":
        context.user_data.pop("waiting_for", None)
        db = load_db()
        u = get_user(db, user_id)
        if u["balance"] < 5:
            await send_logo(update.effective_chat.id, context.bot, "❌ *Недостаточно монет!*", main_menu_keyboard())
            return
        u["balance"] -= 5
        save_db(db)
        msg = await send_logo(update.effective_chat.id, context.bot, "⚙️ *Процесс запущен...*")
        await asyncio.sleep(random.uniform(3, 6))
        try:
            await msg.delete()
        except:
            pass
        await send_logo(update.effective_chat.id, context.bot,
            f"✅ *Готово!*\n\nЮз `{text}` успешно утилизирован.\n💰 Списано 5 монет. Остаток: *{u['balance']}* монет.",
            main_menu_keyboard()
        )
        return

    # Default
    db = load_db()
    u = get_user(db, user_id)
    if u.get("subscribed"):
        await send_logo(update.effective_chat.id, context.bot, "🏠 *Главное меню*", main_menu_keyboard())
    else:
        await send_logo(update.effective_chat.id, context.bot,
            "Сначала подпишитесь на каналы:",
            subscription_keyboard(db)
        )

# ===== MAIN =====
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))

    app.add_handler(CallbackQueryHandler(check_subscriptions, pattern="^check_subs$"))
    app.add_handler(CallbackQueryHandler(balance_handler, pattern="^balance$"))
    app.add_handler(CallbackQueryHandler(topup_handler, pattern="^topup$"))
    app.add_handler(CallbackQueryHandler(paid_confirm_handler, pattern="^paid_confirm$"))
    app.add_handler(CallbackQueryHandler(use_promo_handler, pattern="^use_promo$"))
    app.add_handler(CallbackQueryHandler(utilize_handler, pattern="^utilize$"))
    app.add_handler(CallbackQueryHandler(referrals_handler, pattern="^referrals$"))
    app.add_handler(CallbackQueryHandler(back_main_handler, pattern="^back_main$"))

    app.add_handler(CallbackQueryHandler(admin_add_channel, pattern="^admin_add_channel$"))
    app.add_handler(CallbackQueryHandler(admin_del_channel, pattern="^admin_del_channel$"))
    app.add_handler(CallbackQueryHandler(del_channel_handler, pattern="^del_ch_\\d+$"))
    app.add_handler(CallbackQueryHandler(admin_list_channels, pattern="^admin_list_channels$"))
    app.add_handler(CallbackQueryHandler(admin_promos, pattern="^admin_promos$"))
    app.add_handler(CallbackQueryHandler(admin_create_promo, pattern="^admin_create_promo$"))
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
