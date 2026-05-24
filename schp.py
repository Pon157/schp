#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════╗
║  СЧП — Самые Честные Проверки               ║
║  Telegram Bot                                ║
╚══════════════════════════════════════════════╝
"""

import asyncio
import logging
import sqlite3
import os
from datetime import datetime
from typing import Optional

import aiohttp
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, ReactionTypeEmoji
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession

# Загружаем переменные окружения из .env файла
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ╔══════════════════════════════════════════════╗
# ║                  CONFIG                    ║
# ╚══════════════════════════════════════════════╝
BOT_TOKEN = os.getenv("BOT_TOKEN")
PROXY_URL = os.getenv("PROXY_URL")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден! Пожалуйста, добавьте его в файл .env")

# Supergroup ID с включёнными темами (Topics/Forum)
ADMIN_CHAT_ID = -1003536281255

# ╔══════════════════════════════════════════════╗
# ║              PREMIUM EMOJI                 ║
# ╚══════════════════════════════════════════════╝
def p_emoji(fallback: str, emoji_id: str) -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


E = {
    "star":      p_emoji("⭐️", "5438496463044752972"),
    "success":   p_emoji("✔️",  "5206607081334906820"),
    "error":     p_emoji("❌",  "5416076321442777828"),
    "warn":      p_emoji("⚠️",  "5240241223632954241"),
    "flash":     p_emoji("⚡️",  "5456606106748983383"),
    "eyes":      p_emoji("👀",  "5240241223632954241"),
    "chart":     p_emoji("📈",  "5325547803936572038"),
    "arrow":     p_emoji("➡️",  "5244837092042750681"),
    "green":     p_emoji("🟢",  "5416081784641168838"),
    "sparkles":  p_emoji("✨",  "5438496463044752972"),
    "calendar":  p_emoji("🗓",  "5413879192267805083"),
    "siren":     p_emoji("🚨",  "5395695537687123235"),
    "ban":       p_emoji("⛔️",  "5456302074604035284"),
    "pencil":    p_emoji("✏️",  "5395444784611480792"),
    "flag":      p_emoji("🚩",  "5460755126761312667"),
    "hourglass": p_emoji("⌛️",  "5386367538735104399"),
    "id":        p_emoji("🆔",  "5965485570124681987"),
    "user":      p_emoji("👤",  "5974048815789903111"),
    "rocket":    p_emoji("🚀",  "5195033767969839232"),
    "lock":      p_emoji("🔒",  "5348223165380179822"),
    "tag":       p_emoji("🏷",  "5215499540538340336"),
}

# ID премиум эмодзи для кнопок
BTN_ICONS = {
    "PENCIL": "5395444784611480792",
    "EYES":   "5240241223632954241",
    "STAR":   "5438496463044752972",
    "CHART":  "5325547803936572038",
    "ARROW":  "5244837092042750681",
    "CHECK":  "5416076321442777828",
    "CROSS":  "5456302074604035284",
    "ROCKET": "5195033767969839232",
    "FLASH":  "5456606106748983383",
    "TAG":    "5215499540538340336",
    "LOCK":   "5348223165380179822",
}

# ╔══════════════════════════════════════════════╗
# ║                 DATABASE                     ║
# ╚══════════════════════════════════════════════╝
def init_db():
    conn = sqlite3.connect("schp.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_topics (
            user_id   INTEGER PRIMARY KEY,
            topic_id  INTEGER NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_username    TEXT NOT NULL,
            reviewers       TEXT NOT NULL,
            admins_checked  TEXT NOT NULL,
            review_link     TEXT NOT NULL,
            rating          TEXT NOT NULL,
            added_by        INTEGER NOT NULL,
            added_at        TEXT NOT NULL
        )
    """)
    
    # Добавляем колонку rating, если таблица была создана ранее без неё
    try:
        c.execute("ALTER TABLE reviews ADD COLUMN rating TEXT NOT NULL DEFAULT 'Не указана'")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()
    logger.info("Database initialized")


def get_user_topic(user_id: int) -> Optional[int]:
    conn = sqlite3.connect("schp.db")
    c = conn.cursor()
    c.execute("SELECT topic_id FROM user_topics WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_user_by_topic(topic_id: int) -> Optional[int]:
    conn = sqlite3.connect("schp.db")
    c = conn.cursor()
    c.execute("SELECT user_id FROM user_topics WHERE topic_id = ?", (topic_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def set_user_topic(user_id: int, topic_id: int):
    conn = sqlite3.connect("schp.db")
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO user_topics (user_id, topic_id) VALUES (?, ?)",
        (user_id, topic_id),
    )
    conn.commit()
    conn.close()


def db_add_review(
    bot_username: str,
    reviewers: str,
    admins_checked: str,
    review_link: str,
    rating: str,
    added_by: int,
):
    username = bot_username.lstrip("@").lower()
    conn = sqlite3.connect("schp.db")
    c = conn.cursor()
    c.execute(
        """INSERT INTO reviews
           (bot_username, reviewers, admins_checked, review_link, rating, added_by, added_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (username, reviewers, admins_checked, review_link, rating, added_by, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def db_find_reviews(bot_username: str):
    username = bot_username.lstrip("@").lower()
    conn = sqlite3.connect("schp.db")
    c = conn.cursor()
    c.execute("SELECT * FROM reviews WHERE bot_username = ?", (username,))
    rows = c.fetchall()
    conn.close()
    return rows


# ╔══════════════════════════════════════════════╗
# ║                RAW API HELPERS               ║
# ╚══════════════════════════════════════════════╝
http_session: Optional[aiohttp.ClientSession] = None
_base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"


async def api_call(method: str, payload: dict) -> dict:
    url = f"{_base_url}/{method}"
    kwargs = {}
    if PROXY_URL:
        kwargs['proxy'] = PROXY_URL
        
    async with http_session.post(url, json=payload, **kwargs) as resp:
        data = await resp.json()
        if not data.get("ok"):
            logger.warning("API %s failed: %s", method, data)
        return data


async def send_message(
    chat_id,
    text: str,
    parse_mode: str = "HTML",
    reply_markup: Optional[dict] = None,
    message_thread_id: Optional[int] = None,
) -> dict:
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if message_thread_id:
        payload["message_thread_id"] = message_thread_id
    return await api_call("sendMessage", payload)


async def send_photo(
    chat_id,
    photo: str,
    caption: Optional[str] = None,
    parse_mode: str = "HTML",
    reply_markup: Optional[dict] = None,
    message_thread_id: Optional[int] = None,
) -> dict:
    payload = {"chat_id": str(chat_id), "photo": photo, "parse_mode": parse_mode}
    if caption:
        payload["caption"] = caption
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if message_thread_id:
        payload["message_thread_id"] = message_thread_id
    return await api_call("sendPhoto", payload)


async def create_forum_topic(
    chat_id,
    name: str,
    icon_emoji_id: Optional[str] = None,
) -> Optional[int]:
    payload = {"chat_id": str(chat_id), "name": name[:128]}
    data = await api_call("createForumTopic", payload)
    if data.get("ok"):
        return data["result"]["message_thread_id"]
    return None


# ╔══════════════════════════════════════════════╗
# ║               KEYBOARD BUILDERS              ║
# ╚══════════════════════════════════════════════╝
def main_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Пожаловаться на бота",
                    "callback_data": "complaint",
                    "style": "danger",
                    "icon_custom_emoji_id": BTN_ICONS["PENCIL"],
                }
            ],
            [
                {
                    "text": "Написать руководству",
                    "callback_data": "management",
                    "style": "primary",
                    "icon_custom_emoji_id": BTN_ICONS["ROCKET"],
                }
            ],
            [
                {
                    "text": "Результаты проверки",
                    "callback_data": "search",
                    "style": "success",
                    "icon_custom_emoji_id": BTN_ICONS["CHART"],
                }
            ],
        ]
    }


def cancel_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Отмена",
                    "callback_data": "cancel",
                    "style": "danger",
                    "icon_custom_emoji_id": BTN_ICONS["CROSS"],
                }
            ]
        ]
    }


def back_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Главное меню",
                    "callback_data": "back_main",
                    "style": "primary",
                    "icon_custom_emoji_id": BTN_ICONS["ROCKET"],
                }
            ]
        ]
    }


# ╔══════════════════════════════════════════════╗
# ║                 FSM STATES                   ║
# ╚══════════════════════════════════════════════╝
class ComplaintStates(StatesGroup):
    waiting_bot_username = State()
    waiting_reason = State()


class ManagementStates(StatesGroup):
    waiting_message = State()


class SearchStates(StatesGroup):
    waiting_bot_username = State()


class AddReviewStates(StatesGroup):
    waiting_bot_username = State()
    waiting_reviewers = State()
    waiting_admins = State()
    waiting_link = State()
    waiting_rating = State()


# ╔══════════════════════════════════════════════╗
# ║                  ROUTER                      ║
# ╚══════════════════════════════════════════════╝
router = Router()


# ─── /start ────────────────────────────────────
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await show_main_menu(message.chat.id)


async def show_main_menu(chat_id):
    text = (
        f"{E['star']} <b>Главное меню</b>\n\n"
        f"{E['sparkles']} Здравствуйте, вы попали в бот канала\n"
        f"<b>СЧП — Самые Честные Проверки</b>\n\n"
        f"Здесь вы можете:\n"
        f"{E['pencil']} Подать жалобу на работу бота поддержки\n"
        f"{E['flag']} Написать старшему руководству\n"
        f"{E['chart']} Просмотреть и увидеть результаты проверки бота"
    )
    await send_message(chat_id, text, reply_markup=main_keyboard())


# ─── ЖАЛОБА НА БОТА ────────────────────────────
@router.callback_query(F.data == "complaint")
async def cb_complaint(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ComplaintStates.waiting_bot_username)
    text = (
        f"{E['siren']} <b>Подача жалобы на бота</b>\n\n"
        f"{E['id']} Отправьте <b>юзернейм бота</b>, на которого хотите пожаловаться\n\n"
        f"<i>Пример: @SomeBot</i>"
    )
    await send_message(callback.message.chat.id, text, reply_markup=cancel_keyboard())


@router.message(ComplaintStates.waiting_bot_username)
async def handle_complaint_username(message: Message, state: FSMContext):
    username = message.text.strip()
    if not username.startswith("@"):
        username = "@" + username

    await state.update_data(bot_username=username)
    await state.set_state(ComplaintStates.waiting_reason)

    text = (
        f"{E['pencil']} <b>Укажите причину жалобы</b>\n\n"
        f"Описываете проблему с ботом <b>{username}</b>\n\n"
        f"{E['flash']} Вы можете:\n"
        f"• Написать только текст\n"
        f"• Прикрепить фото с подписью"
    )
    await send_message(message.chat.id, text, reply_markup=cancel_keyboard())


@router.message(ComplaintStates.waiting_reason)
async def handle_complaint_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    bot_username = data.get("bot_username", "Неизвестно")

    user = message.from_user
    user_link = f'<a href="tg://user?id={user.id}">{user.full_name}</a>'
    user_uname = f"@{user.username}" if user.username else "—"
    reason_text = message.caption or message.text or "—"

    topic_id = get_user_topic(user.id)
    if not topic_id:
        topic_name = f"Жалоба | {user.full_name[:25]}"
        topic_id = await create_forum_topic(ADMIN_CHAT_ID, topic_name)
        if topic_id:
            set_user_topic(user.id, topic_id)

    header = (
        f"{E['siren']} <b>НОВАЯ ЖАЛОБА НА БОТА</b>\n"
        f"{'─' * 30}\n"
        f"{E['user']} Пользователь: {user_link}\n"
        f"{E['id']} ID: <code>{user.id}</code> | {user_uname}\n"
        f"{E['tag']} Бот: <b>{bot_username}</b>\n"
        f"{E['calendar']} Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"{'─' * 30}\n"
        f"{E['pencil']} <b>Причина:</b>\n{reason_text}"
    )

    if topic_id:
        if message.photo:
            await send_photo(
                ADMIN_CHAT_ID,
                message.photo[-1].file_id,
                caption=header,
                message_thread_id=topic_id,
            )
        else:
            await send_message(ADMIN_CHAT_ID, header, message_thread_id=topic_id)

    await state.clear()

    confirm = (
        f"{E['success']} <b>Жалоба успешно отправлена!</b>\n\n"
        f"{E['hourglass']} Ваше обращение передано администраторам <b>СЧП</b>.\n"
        f"{E['star']} Ожидайте ответа."
    )
    await send_message(message.chat.id, confirm, reply_markup=back_keyboard())


# ─── ОБРАЩЕНИЕ К РУКОВОДСТВУ ───────────────────
@router.callback_query(F.data == "management")
async def cb_management(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ManagementStates.waiting_message)
    text = (
        f"{E['flag']} <b>Связь с руководством</b>\n\n"
        f"{E['pencil']} Напишите ваше сообщение, и оно будет передано старшему руководству.\n\n"
        f"<i>Вы можете отправить текст или фото с подписью.</i>"
    )
    await send_message(callback.message.chat.id, text, reply_markup=cancel_keyboard())


@router.message(ManagementStates.waiting_message)
async def handle_management_message(message: Message, state: FSMContext):
    user = message.from_user
    user_link = f'<a href="tg://user?id={user.id}">{user.full_name}</a>'
    user_uname = f"@{user.username}" if user.username else "—"
    msg_text = message.text or message.caption or "—"

    topic_id = get_user_topic(user.id)
    if not topic_id:
        topic_name = f"Обращение | {user.full_name[:25]}"
        topic_id = await create_forum_topic(ADMIN_CHAT_ID, topic_name)
        if topic_id:
            set_user_topic(user.id, topic_id)

    if topic_id:
        admin_text = (
            f"{E['flag']} <b>ОБРАЩЕНИЕ К РУКОВОДСТВУ</b>\n"
            f"{'─' * 30}\n"
            f"{E['user']} От: {user_link}\n"
            f"{E['id']} ID: <code>{user.id}</code> | {user_uname}\n"
            f"{E['calendar']} Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"{'─' * 30}\n"
            f"{E['pencil']} <b>Сообщение:</b>\n{msg_text}"
        )
        if message.photo:
            await send_photo(
                ADMIN_CHAT_ID,
                message.photo[-1].file_id,
                caption=admin_text,
                message_thread_id=topic_id,
            )
        else:
            await send_message(ADMIN_CHAT_ID, admin_text, message_thread_id=topic_id)

    await state.clear()
    confirm = (
        f"{E['success']} <b>Обращение отправлено!</b>\n\n"
        f"{E['rocket']} Ваше сообщение передано старшему руководству.\n"
        f"{E['hourglass']} Ожидайте ответа."
    )
    await send_message(message.chat.id, confirm, reply_markup=back_keyboard())


@router.message(F.chat.id == ADMIN_CHAT_ID)
async def admin_reply_to_user(message: Message, bot: Bot):
    if not message.message_thread_id:
        return

    user_id = get_user_by_topic(message.message_thread_id)

    if user_id:
        # Сначала отправляем сообщение (основная логика)
        try:
            await bot.send_message(
                chat_id=user_id,
                text=f"<b>Ответ от руководства:</b>\n\n{message.text}"
            )
        except Exception as e:
            await message.reply(f"❌ Ошибка отправки пользователю: {e}")
            return

        # Пытаемся выставить реакцию. Если реакции в группе выключены, бот просто продолжит работу без ошибок
        try:
            await message.react(reactions=[ReactionTypeEmoji(emoji="✅")])
        except Exception:
            pass


# ─── ПОИСК РЕЗУЛЬТАТОВ ПРОВЕРКИ ────────────────
@router.callback_query(F.data == "search")
async def cb_search(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(SearchStates.waiting_bot_username)

    text = (
        f"{E['chart']} <b>Поиск результатов проверки</b>\n\n"
        f"{E['id']} Введите юзернейм бота для поиска\n\n"
        f"<i>Пример: @SomeBot</i>"
    )
    await send_message(callback.message.chat.id, text, reply_markup=cancel_keyboard())


@router.message(SearchStates.waiting_bot_username)
async def handle_search(message: Message, state: FSMContext):
    username = message.text.strip().lstrip("@").lower()
    reviews = db_find_reviews(username)
    await state.clear()

    if not reviews:
        text = (
            f"{E['error']} <b>Проверки не найдены</b>\n\n"
            f"{E['warn']} Бот <b>@{username}</b> ещё не проверялся\n"
            f"или данные ещё не внесены администраторами."
        )
    else:
        text = f"{E['chart']} <b>Результаты проверки @{username}</b>\n{'─' * 30}\n\n"
        for i, rev in enumerate(reviews, 1):
            _, _uname, reviewers, admins_checked, review_link, rating, _added_by, added_at = rev
            try:
                dt = datetime.fromisoformat(added_at).strftime("%d.%m.%Y %H:%M")
            except Exception:
                dt = added_at
                
            text += (
                f"{E['star']} <b>Проверка #{i}</b>\n"
                f"{E['user']} Проверяющие: {reviewers}\n"
                f"{E['eyes']} Проверенные админы: {admins_checked}\n"
                f"{E['chart']} Оценка: <b>{rating}</b>\n"
                f"{E['arrow']} Ссылка: {review_link}\n"
                f"{E['calendar']} Дата: {dt}\n\n"
            )

    await send_message(message.chat.id, text, reply_markup=back_keyboard())


# ─── /add — ДОБАВЛЕНИЕ ПРОВЕРКИ (ТОЛЬКО В АДМИН-ЧАТЕ) ─
@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    if message.chat.id != ADMIN_CHAT_ID and message.chat.type != "private":
        return

    args = message.text.split(None, 1)

    # Однострочный синтаксис: /add @bot | проверяющие | проверенные | ссылка | оценка
    if len(args) > 1:
        parts = [p.strip() for p in args[1].split("|")]
        if len(parts) >= 5:
            bot_uname, reviewers, admins, link, rating = parts[0], parts[1], parts[2], parts[3], parts[4]
            db_add_review(bot_uname, reviewers, admins, link, rating, message.from_user.id)
            clean_uname = bot_uname.lstrip("@")
            await send_message(
                message.chat.id,
                f"{E['success']} <b>Проверка добавлена!</b>\n\n"
                f"{E['tag']} Бот: <b>@{clean_uname}</b>\n"
                f"{E['user']} Проверяющие: {reviewers}\n"
                f"{E['eyes']} Проверенные: {admins}\n"
                f"{E['chart']} Оценка: <b>{rating}</b>\n"
                f"{E['arrow']} Ссылка: {link}",
            )
            return
        else:
            await send_message(
                message.chat.id,
                f"{E['warn']} Формат: /add @бот | проверяющие | проверенные | ссылка | оценка",
            )
            return

    # Пошаговый режим
    await state.set_state(AddReviewStates.waiting_bot_username)
    await send_message(
        message.chat.id,
        f"{E['pencil']} <b>Добавление проверки (шаг 1/5)</b>\n\n"
        f"{E['tag']} Введите юзернейм бота:",
    )


@router.message(AddReviewStates.waiting_bot_username)
async def add_step_username(message: Message, state: FSMContext):
    await state.update_data(bot_username=message.text.strip())
    await state.set_state(AddReviewStates.waiting_reviewers)
    await send_message(
        message.chat.id,
        f"{E['user']} <b>Шаг 2/5</b> — Введите имена проверяющих:",
    )


@router.message(AddReviewStates.waiting_reviewers)
async def add_step_reviewers(message: Message, state: FSMContext):
    await state.update_data(reviewers=message.text.strip())
    await state.set_state(AddReviewStates.waiting_admins)
    await send_message(
        message.chat.id,
        f"{E['eyes']} <b>Шаг 3/5</b> — Введите проверенных администраторов:",
    )


@router.message(AddReviewStates.waiting_admins)
async def add_step_admins(message: Message, state: FSMContext):
    await state.update_data(admins=message.text.strip())
    await state.set_state(AddReviewStates.waiting_link)
    await send_message(
        message.chat.id,
        f"{E['arrow']} <b>Шаг 4/5</b> — Введите ссылку на проверку:",
    )


@router.message(AddReviewStates.waiting_link)
async def add_step_link(message: Message, state: FSMContext):
    await state.update_data(link=message.text.strip())
    await state.set_state(AddReviewStates.waiting_rating)
    await send_message(
        message.chat.id,
        f"{E['chart']} <b>Шаг 5/5</b> — Введите оценку (например, 10/10):",
    )


@router.message(AddReviewStates.waiting_rating)
async def add_step_rating(message: Message, state: FSMContext):
    data = await state.get_data()
    rating = message.text.strip()
    
    db_add_review(
        data["bot_username"],
        data["reviewers"],
        data["admins"],
        data["link"],
        rating,
        message.from_user.id,
    )
    await state.clear()

    clean_uname = data["bot_username"].lstrip("@")
    await send_message(
        message.chat.id,
        f"{E['success']} <b>Проверка успешно добавлена!</b>\n"
        f"{'─' * 30}\n"
        f"{E['tag']} Бот: <b>@{clean_uname}</b>\n"
        f"{E['user']} Проверяющие: {data['reviewers']}\n"
        f"{E['eyes']} Проверенные: {data['admins']}\n"
        f"{E['chart']} Оценка: <b>{rating}</b>\n"
        f"{E['arrow']} Ссылка: {data['link']}",
    )


# ─── /list — СПИСОК ВСЕХ ПРОВЕРОК ──────────────
@router.message(Command("list"))
async def cmd_list(message: Message):
    if message.chat.id != ADMIN_CHAT_ID and message.chat.type != "private":
        return

    conn = sqlite3.connect("schp.db")
    c = conn.cursor()
    c.execute("SELECT bot_username, COUNT(*) FROM reviews GROUP BY bot_username")
    rows = c.fetchall()
    conn.close()

    if not rows:
        await send_message(message.chat.id, f"{E['warn']} Проверок пока нет.")
        return

    text = f"{E['chart']} <b>Все проверки ({len(rows)} ботов)</b>\n{'─' * 30}\n\n"
    for username, count in rows:
        text += f"{E['green']} @{username} — {count} проверок(ки)\n"

    await send_message(message.chat.id, text)


# ─── CANCEL / BACK ─────────────────────────────
@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Отменено")
    await state.clear()
    await show_main_menu(callback.message.chat.id)


@router.callback_query(F.data == "back_main")
async def cb_back_main(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await show_main_menu(callback.message.chat.id)


# ╔══════════════════════════════════════════════╗
# ║                    MAIN                      ║
# ╚══════════════════════════════════════════════╝
async def main():
    global http_session

    init_db()

    http_session = aiohttp.ClientSession()
    
    kwargs = {}
    if PROXY_URL:
        kwargs['proxy'] = PROXY_URL
    
    aiogram_session = AiohttpSession(**kwargs)
    
    bot = Bot(token=BOT_TOKEN, session=aiogram_session)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    if PROXY_URL:
        logger.info("🚀 СЧП Bot запущен через прокси %s", PROXY_URL)
    else:
        logger.info("🚀 СЧП Bot запущен (без прокси)")

    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await http_session.close()
        await aiogram_session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
