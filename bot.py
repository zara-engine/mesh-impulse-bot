import asyncio
import os
from datetime import datetime, timezone, timedelta

import aiosqlite
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import BotCommand, Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from cryptography.fernet import Fernet

from mesh_api import fetch_profile, fetch_events  # сетевой слой (в демо — mock)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")


class Registration(StatesGroup):
    waiting_for_token = State()


def get_main_keyboard():
    btn_next_lesson = KeyboardButton(text="🏃‍♂️ Следующий урок")
    btn_debts = KeyboardButton(text="🚨 Долги")
    return ReplyKeyboardMarkup(
        keyboard=[[btn_next_lesson, btn_debts]], resize_keyboard=True
    )


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                token TEXT NOT NULL,
                profile_id TEXT,
                person_id TEXT
            )
        ''')
        await db.commit()


async def setup_bot_commands(bot: Bot):
    bot_commands = [
        BotCommand(command="/start", description="Запустить бота / Ввести токен"),
        BotCommand(command="/help", description="Справка и Политика конфиденциальности"),
        BotCommand(command="/logout", description="Выйти и удалить данные"),
    ]
    await bot.set_my_commands(bot_commands)


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    welcome_text = (
        "Привет! 👋 Я — <b>МЭШ.Импульс</b>, твой сверхбыстрый личный помощник.\n\n"
        "Я помогу за секунду узнать, в какой кабинет бежать на следующий урок, "
        "и покажу, где висят долги.\n\n"
        "Чтобы подключить дневник, мне нужен токен доступа МЭШ.\n"
        "Инструкция по получению токена выдаётся пользователям отдельно.\n\n"
        "🔒 <i>Отправляя токен, ты соглашаешься с "
        "<a href=\"https://telegra.ph/Politika-konfidencialnosti-Telegram-bota-MEHSHImpuls-02-26\">"
        "Политикой конфиденциальности</a>.</i> "
        "Твои данные надёжно зашифрованы."
    )
    await message.answer(welcome_text, parse_mode="HTML", disable_web_page_preview=True)
    await state.set_state(Registration.waiting_for_token)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📖 <b>Справка МЭШ.Импульс</b>\n\n"
        "Я создан, чтобы экономить твоё время.\n\n"
        "🔹 <b>Функции:</b>\n"
        "— Выдача следующего урока с кабинетом и этажом.\n"
        "— Поиск долгов (НВ и двойки (в том числе с точкой) с комментариями).\n\n"
        "🔹 <b>Команды:</b>\n"
        "/start — Перезапустить бота или ввести новый токен\n"
        "/logout — Удалить свой токен из моей памяти навсегда\n\n"
        "🔒 Твои данные надёжно зашифрованы. Подробнее в "
        "<a href=\"https://telegra.ph/Politika-konfidencialnosti-Telegram-bota-MEHSHImpuls-02-26\">"
        "Политике конфиденциальности</a>."
    )
    await message.answer(help_text, parse_mode="HTML", disable_web_page_preview=True)


@dp.message(Command("logout"))
async def cmd_logout(message: Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        await db.commit()
    await message.answer(
        "🚪 <b>Твои данные успешно удалены!</b>\n"
        "Токен стёрт из базы. Чтобы начать работу заново, нажми /start",
        parse_mode="HTML",
    )


@dp.message(Registration.waiting_for_token)
async def process_token(message: Message, state: FSMContext):
    raw_token = message.text.strip()
    if len(raw_token) < 20:
        await message.answer(
            "❌ Это не похоже на токен. Пожалуйста, скопируй весь длинный текст и пришли мне."
        )
        return

    status_msg = await message.answer("🔄 Проверяю токен и получаю профиль...")
    try:
        profile_data = await fetch_profile(raw_token)
        if profile_data is None:
            await status_msg.edit_text(
                "❌ Ошибка авторизации. Токен устарел или скопирован не полностью."
            )
            return

        profile_info = profile_data.get("profile", {})
        profile_id = str(profile_info.get("id", ""))

        person_id = ""
        children_info = profile_data.get("children", [])
        if children_info and isinstance(children_info, list):
            person_id = str(children_info[0].get("contingent_guid", ""))

        if not profile_id or not person_id:
            await status_msg.edit_text("❌ Не удалось найти ID ученика в профиле МЭШ.")
            return

        encrypted_token = cipher_suite.encrypt(raw_token.encode()).decode()
        user_id = message.from_user.id
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                'INSERT OR REPLACE INTO users (user_id, token, profile_id, person_id) '
                'VALUES (?, ?, ?, ?)',
                (user_id, encrypted_token, profile_id, person_id),
            )
            await db.commit()

        await state.clear()
        await status_msg.delete()
        await message.answer(
            "✅ <b>Авторизация успешна!</b>\n\n"
            "Твой профиль найден, а токен надёжно зашифрован. Теперь ты можешь пользоваться ботом.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard(),
        )
    except Exception as e:
        await status_msg.edit_text("❌ Не удалось подключиться к серверу МЭШ. Попробуй позже.")
        print(f"Ошибка получения профиля: {e}")


@dp.message(F.text == "🏃‍♂️ Следующий урок")
async def get_next_lesson(message: Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT token, profile_id, person_id FROM users WHERE user_id = ?', (user_id,)
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        await message.answer("⚠️ Сначала нужно авторизоваться! Нажми /start")
        return

    encrypted_token, profile_id, person_id = row
    decrypted_token = cipher_suite.decrypt(encrypted_token.encode()).decode()
    status_msg = await message.answer("🔄 Подключаюсь к дневнику...")

    tz_msk = timezone(timedelta(hours=3))
    now = datetime.now(tz_msk)
    today_str = now.strftime("%Y-%m-%d")

    try:
        schedule_data = await fetch_events(
            decrypted_token, profile_id, person_id, today_str, today_str
        )
        if schedule_data is None:
            await status_msg.edit_text("❌ Ошибка авторизации. Токен устарел. Нажми /start")
            return

        events = schedule_data.get("response", [])
        valid_sources = ["PLAN", "EC", "AE"]
        lessons = [e for e in events if e.get("source") in valid_sources]
        if not lessons:
            await status_msg.edit_text("🎉 На сегодня уроков нет! Отдыхай.")
            return

        lessons.sort(key=lambda x: x.get("start_at", ""))
        current_lesson = None
        next_lesson = None
        for i, lesson in enumerate(lessons):
            if not lesson.get("finish_at") or not lesson.get("start_at"):
                continue
            start_time = datetime.fromisoformat(lesson.get("start_at"))
            finish_time = datetime.fromisoformat(lesson.get("finish_at"))
            if start_time <= now <= finish_time:
                current_lesson = lesson
                if i + 1 < len(lessons):
                    next_lesson = lessons[i + 1]
                break
            elif now < start_time:
                next_lesson = lesson
                break

        if current_lesson:
            await status_msg.edit_text(
                "🤫 <b>Сейчас идёт урок, учись давай!</b>\n"
                "Куда бежать дальше — узнаешь на перемене!",
                parse_mode="HTML",
            )
            return

        if not next_lesson:
            await status_msg.edit_text("🎉 Все уроки на сегодня закончились!")
            return

        subject = next_lesson.get('subject_name', 'Неизвестный предмет')
        room_num = str(next_lesson.get('room_number') or '?')
        room_name = next_lesson.get('room_name') or ''
        start_dt = datetime.fromisoformat(next_lesson.get('start_at'))
        finish_dt = datetime.fromisoformat(next_lesson.get('finish_at'))
        time_str = f"{start_dt.strftime('%H:%M')} — {finish_dt.strftime('%H:%M')}"
        floor = room_num[0] if room_num.isdigit() and len(room_num) == 3 else "?"

        answer_text = (
            f"🏃‍♂️ <b>Следующий урок:</b>\n\n"
            f"📚 <b>{subject}</b>\n"
            f"🕒 {time_str}\n"
            f"🚪 Кабинет: {room_num} ({room_name})\n"
            f"🏢 Этаж: {floor}"
        )
        await status_msg.edit_text(answer_text, parse_mode="HTML")
    except Exception as e:
        await status_msg.edit_text("❌ Не удалось подключиться к серверу МЭШ. Попробуй позже.")
        print(f"Ошибка получения расписания: {e}")


@dp.message(F.text == "🚨 Долги")
async def get_debts(message: Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT token, profile_id, person_id FROM users WHERE user_id = ?', (user_id,)
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        await message.answer("⚠️ Сначала нужно авторизоваться! Нажми /start")
        return

    encrypted_token, profile_id, person_id = row
    decrypted_token = cipher_suite.decrypt(encrypted_token.encode()).decode()
    status_msg = await message.answer("🔄 Сканирую дневник за последний месяц...")

    now = datetime.now()
    start_date = now - timedelta(days=30)
    begin_str = start_date.strftime("%Y-%m-%d")
    end_str = now.strftime("%Y-%m-%d")

    try:
        data = await fetch_events(decrypted_token, profile_id, person_id, begin_str, end_str)
        if data is None:
            await status_msg.edit_text("❌ Ошибка авторизации. Токен устарел. Нажми /start")
            return

        events_list = data.get("response", [])
        debts = []
        for lesson in events_list:
            marks = lesson.get("marks")
            if marks and isinstance(marks, list):
                for m in marks:
                    val = str(m.get("value", ""))
                    is_point = m.get("is_point", False)
                    if val == "2" or val == "НВ" or is_point:
                        subject = lesson.get("subject_name", "Неизвестный предмет")
                        is_exam = m.get("is_exam", False)
                        form = m.get("control_form_name", "Работа")
                        if is_exam:
                            form = "Контрольная работа (вес 2)"
                        raw_date = m.get("date") or lesson.get("start_at", "")[:10]
                        raw_comment = m.get("comment")
                        comment = raw_comment.strip() if raw_comment else ""
                        debts.append({
                            "subject": subject,
                            "form": form,
                            "value": val,
                            "is_point": is_point,
                            "date": raw_date,
                            "comment": comment,
                        })

        if not debts:
            await status_msg.edit_text(
                "🎉 <b>Отличные новости!</b>\n"
                "За последний месяц у тебя нет ни двоек, ни невыполненных заданий.",
                parse_mode="HTML",
            )
            return

        debts.sort(key=lambda x: x.get("date", ""))
        answer_text = "🚨 <b>Твои текущие задолженности и двойки:</b>\n\n"
        for d in debts:
            pretty_date = ""
            if d["date"]:
                dt = datetime.strptime(d["date"], "%Y-%m-%d")
                pretty_date = dt.strftime("%d.%m")
            point_str = " (с точкой)" if d["is_point"] else ""
            answer_text += f"• <b>{d['subject']}</b> ({pretty_date})\n"
            answer_text += f"  └ {d['form']}: <b>{d['value']}{point_str}</b>\n"
            if d.get("comment"):
                answer_text += f"  💬 <i>{d['comment']}</i>\n"
            answer_text += "\n"
        answer_text += "💡 <i>Постарайся закрыть их как можно скорее!</i>"
        await status_msg.edit_text(answer_text, parse_mode="HTML")
    except Exception as e:
        await status_msg.edit_text("❌ Не удалось подключиться к серверу. Попробуй позже.")
        print(f"Ошибка получения долгов: {e}")


async def main():
    await init_db()
    await setup_bot_commands(bot)
    print("🚀 МЭШ.Импульс успешно запущен!")
    print(f"📁 База данных находится здесь: {DB_PATH}")
    await dp.start_polling(bot, drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
