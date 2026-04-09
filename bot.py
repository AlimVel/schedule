#!/usr/bin/env python3
"""
GoShiet Telegram Bot — интеграция с Django БД
==============================================

Функции:
  1. Показ расписания (сегодня, завтра, по дням) из БД Django
  2. Преподаватели, свободные кабинеты, PDF
  3. Уведомление за 15 минут до начала пары (вкл/выкл)
  4. Уведомление при изменении расписания (автоматическое)

Установка:
  pip install aiogram apscheduler fpdf2 django

Запуск:
  Из корня Django-проекта:
    python schedule_bot.py
"""

import asyncio
import json
import os
import sys
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict

# ── Django Setup (ОБЯЗАТЕЛЬНО ДО импорта моделей) ────────────
# Путь к корню Django-проекта (где manage.py)
DJANGO_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DJANGO_PROJECT_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "goshiet.settings")

import django
django.setup()

from asgiref.sync import sync_to_async

# Теперь можно импортировать модели
from core.models import (
    University, User, Group, Classroom, Subject,
    ScheduleEntry, TeacherPreference, UniversitySettings,
    Direction, Course,
)

# ── Telegram библиотеки ──────────────────────────────────────
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# PDF
from fpdf import FPDF, XPos, YPos

# ══════════════════════════════════════════════════════════════
#  НАСТРОЙКИ
# ══════════════════════════════════════════════════════════════

TOKEN = "8531162533:AAEWtrsq4SZNMcoOrPGxncSXveEzGyV3exg"

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_DR = os.path.join(CURRENT_DIR, "fonts")
USERS_DB_PATH = os.path.join(CURRENT_DIR, "bot_users.json")
FONT_PATH = os.path.join(FONT_DR, "arial.ttf")

# Хранилище хэшей расписания для отслеживания изменений
SCHEDULE_HASH_PATH = os.path.join(CURRENT_DIR, "schedule_hashes.json")

DAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
NUM_EMOJI = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]

DAY_MAPPING = {
    "Понедельник": "Пн", "Вторник": "Вт", "Среда": "Ср",
    "Четверг": "Чт", "Пятница": "Пт", "Суббота": "Сб", "Воскресенье": "Вс",
}

WEEKDAY_TO_INT = {"Пн": 0, "Вт": 1, "Ср": 2, "Чт": 3, "Пт": 4, "Сб": 5}
INT_TO_SHORT = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб"}

DAYS_PREP = {
    "Понедельник": "на понедельник", "Вторник": "на вторник", "Среда": "на среду",
    "Четверг": "на четверг", "Пятница": "на пятницу", "Суббота": "на субботу",
}

# Стандартное время начала пар (час, минута)
SLOT_START_TIMES = {
    1: (8, 30),
    2: (10, 15),
    3: (12, 0),
    4: (13, 45),
    5: (15, 30),
    6: (17, 15),
}

SLOT_TIME_STRINGS = {
    1: "08:30–10:05", 2: "10:15–11:50", 3: "12:00–13:35",
    4: "13:45–15:20", 5: "15:30–17:05", 6: "17:15–18:50",
}

LESSON_TYPE_LABELS = {
    "lecture": "Лекция", "practice": "Практика", "lab": "Лаба",
    "seminar": "Семинар", "online": "Онлайн",
}

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# ══════════════════════════════════════════════════════════════
#  USERS DB (JSON-файл для хранения настроек Telegram-юзеров)
# ══════════════════════════════════════════════════════════════

def load_users():
    if os.path.exists(USERS_DB_PATH):
        with open(USERS_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_users(data):
    with open(USERS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user(user_id):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "group": None,
            "university_id": None,
            "auto_mail": False,
            "notify_before_pair": True,   # уведомление за 15 мин до пары
            "notify_changes": True,        # уведомление об изменениях
        }
        save_users(users)
    return users[uid]


def update_user(user_id, **kwargs):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "group": None, "university_id": None,
            "auto_mail": False, "notify_before_pair": True, "notify_changes": True,
        }
    users[uid].update(kwargs)
    save_users(users)


# ══════════════════════════════════════════════════════════════
#  ЧТЕНИЕ РАСПИСАНИЯ ИЗ DJANGO БД
#  (все функции синхронные — вызываются через sync_to_async)
# ══════════════════════════════════════════════════════════════

def _current_week_number_sync():
    """Определяет текущую учебную неделю (упрощённо: из SemesterState)."""
    from core.models import SemesterState
    state = SemesterState.objects.order_by("-current_week").first()
    if state and state.current_week > 0:
        return state.current_week
    return 1


def _get_schedule_for_group_sync(group_name, week=None):
    """
    Возвращает расписание группы из Django БД.
    Формат: {weekday_int: [{num, time, subject, teacher, room, groups, lesson_type}, ...]}
    """
    if week is None:
        week = _current_week_number_sync()

    try:
        group = Group.objects.get(name=group_name)
    except Group.DoesNotExist:
        return {}

    entries = list(
        ScheduleEntry.objects
        .filter(groups=group, week_number=week)
        .select_related("subject", "teacher", "classroom")
        .prefetch_related("groups")
    )

    schedule = defaultdict(list)
    for e in entries:
        teacher_name = (
            f"{e.teacher.last_name} {e.teacher.first_name}".strip()
            or e.teacher.username
        )
        group_names = [g.name for g in e.groups.all()]

        schedule[e.weekday].append({
            "id": e.id,
            "num": e.slot_number,
            "time": SLOT_TIME_STRINGS.get(e.slot_number, ""),
            "subject": e.subject.name,
            "teacher": teacher_name,
            "room": e.classroom.name if e.classroom else "—",
            "groups": group_names,
            "lesson_type": e.lesson_type,
            "is_approved": e.is_approved,
        })

    for day in schedule:
        schedule[day].sort(key=lambda x: x["num"])

    return dict(schedule)


def _get_schedule_for_teacher_sync(teacher_name, week=None):
    """Расписание преподавателя из БД."""
    if week is None:
        week = _current_week_number_sync()

    entries = list(
        ScheduleEntry.objects
        .filter(week_number=week)
        .select_related("subject", "teacher", "classroom")
        .prefetch_related("groups")
    )

    schedule = defaultdict(list)
    for e in entries:
        t_name = f"{e.teacher.last_name} {e.teacher.first_name}".strip() or e.teacher.username
        if t_name != teacher_name:
            continue

        schedule[e.weekday].append({
            "num": e.slot_number,
            "time": SLOT_TIME_STRINGS.get(e.slot_number, ""),
            "subject": e.subject.name,
            "teacher": t_name,
            "room": e.classroom.name if e.classroom else "—",
            "groups": [g.name for g in e.groups.all()],
            "lesson_type": e.lesson_type,
        })

    for day in schedule:
        schedule[day].sort(key=lambda x: x["num"])

    return dict(schedule)


def _get_all_groups_sync():
    """Все группы из БД."""
    return list(Group.objects.values_list("name", flat=True).order_by("name"))


def _get_all_teachers_sync():
    """Все преподаватели из БД."""
    teachers = set()
    for u in User.objects.filter(is_teacher=True):
        name = f"{u.last_name} {u.first_name}".strip() or u.username
        teachers.add(name)
    return sorted(teachers)


def _get_all_rooms_sync():
    """Все аудитории из БД."""
    return list(Classroom.objects.values_list("name", flat=True).order_by("name"))


def _get_occupied_rooms_sync(weekday_int, week=None):
    """Занятые аудитории по слотам на конкретный день."""
    if week is None:
        week = _current_week_number_sync()

    entries = list(
        ScheduleEntry.objects
        .filter(weekday=weekday_int, week_number=week)
        .select_related("classroom")
    )

    occupied = defaultdict(set)
    for e in entries:
        if e.classroom:
            occupied[e.slot_number].add(e.classroom.name)

    return dict(occupied)


# ── Async-обёртки (вызывайте эти в хэндлерах) ────────────────

get_current_week = sync_to_async(_current_week_number_sync, thread_sensitive=True)
get_schedule_for_group = sync_to_async(_get_schedule_for_group_sync, thread_sensitive=True)
get_schedule_for_teacher_from_db = sync_to_async(_get_schedule_for_teacher_sync, thread_sensitive=True)
get_all_groups_from_db = sync_to_async(_get_all_groups_sync, thread_sensitive=True)
get_all_teachers_from_db = sync_to_async(_get_all_teachers_sync, thread_sensitive=True)
get_all_rooms_from_db = sync_to_async(_get_all_rooms_sync, thread_sensitive=True)
get_occupied_rooms_for_day = sync_to_async(_get_occupied_rooms_sync, thread_sensitive=True)


# ══════════════════════════════════════════════════════════════
#  ФОРМАТИРОВАНИЕ
# ══════════════════════════════════════════════════════════════

def format_schedule_day(day_name, lessons):
    """Форматирует расписание дня в красивый текст."""
    if not lessons:
        day_prep = DAYS_PREP.get(day_name, day_name.lower())
        return f"🎉 {day_prep} пар нет! Отдыхаем 😴"

    day_prep = DAYS_PREP.get(day_name, day_name.lower())
    text = f"📅 <b>Расписание {day_prep}</b>\n\n"

    for l in lessons:
        num = l["num"]
        emoji = NUM_EMOJI[num] if num < len(NUM_EMOJI) else str(num)
        lt = LESSON_TYPE_LABELS.get(l.get("lesson_type", ""), "")
        lt_str = f" · <i>{lt}</i>" if lt else ""

        text += f"<blockquote><b>{emoji} {l['time']}</b>{lt_str}\n"
        text += f"📚 <b>{l['subject']}</b>\n"
        text += f"👨‍🏫 {l['teacher']}\n"
        text += f"🚪 Аудитория: <code>{l['room']}</code></blockquote>\n"

    return text


# ══════════════════════════════════════════════════════════════
#  КЛАВИАТУРЫ
# ══════════════════════════════════════════════════════════════

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧾 Сегодня"), KeyboardButton(text="🔜 Завтра")],
            [KeyboardButton(text="📅 По дням"), KeyboardButton(text="👨‍🏫 Преподаватели")],
            [KeyboardButton(text="🛋 Свободные кабинеты"), KeyboardButton(text="📥 Скачать PDF")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="🔔 Уведомления")],
        ],
        resize_keyboard=True,
    )


def get_days_keyboard():
    buttons = [
        InlineKeyboardButton(text=short, callback_data=f"day_{full}")
        for full, short in DAY_MAPPING.items()
        if short != "Вс"
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            buttons[:3], buttons[3:],
            [InlineKeyboardButton(text="❌ Скрыть", callback_data="delete_msg")],
        ]
    )


async def get_groups_keyboard():
    groups = await get_all_groups_from_db()
    buttons = [InlineKeyboardButton(text=g, callback_data=f"group_{g}") for g in groups]
    rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="delete_msg")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def get_teachers_keyboard():
    teachers = await get_all_teachers_from_db()
    if not teachers:
        return None
    buttons = [InlineKeyboardButton(text=t, callback_data=f"tchr_{t}") for t in teachers]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="❌ Скрыть", callback_data="delete_msg")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_notifications_keyboard(user_data):
    """Клавиатура настройки уведомлений."""
    pair_status = "✅" if user_data.get("notify_before_pair", True) else "❌"
    changes_status = "✅" if user_data.get("notify_changes", True) else "❌"
    morning_status = "✅" if user_data.get("auto_mail", False) else "❌"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{pair_status} За 15 мин до пары",
                callback_data="toggle_notify_pair",
            )],
            [InlineKeyboardButton(
                text=f"{changes_status} Изменения в расписании",
                callback_data="toggle_notify_changes",
            )],
            [InlineKeyboardButton(
                text=f"{morning_status} Утренняя рассылка (07:00)",
                callback_data="toggle_auto_mail",
            )],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data="delete_msg")],
        ]
    )


# ══════════════════════════════════════════════════════════════
#  ХЭНДЛЕРЫ
# ══════════════════════════════════════════════════════════════

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    get_user(message.from_user.id)  # создаём запись
    await message.answer(
        "👋 <b>Привет! Я GoShiet Bot</b>\n\n"
        "Я показываю расписание прямо из базы данных университета.\n\n"
        "❗️ <b>Сначала нажми «⚙️ Настройки»</b>, чтобы выбрать свою группу!\n"
        "Затем настрой <b>«🔔 Уведомления»</b> — я буду напоминать о парах.\n\n"
        "Пользуйся меню ниже 👇",
        reply_markup=get_main_keyboard(),
    )


# ── Сегодня / Завтра ─────────────────────────────────────────

@dp.message(F.text.in_({"🧾 Сегодня", "🔜 Завтра"}))
async def handle_today_tomorrow(message: types.Message):
    user = get_user(message.from_user.id)
    group_name = user.get("group")

    if not group_name:
        await message.answer("⚠️ Выбери свою группу в разделе «⚙️ Настройки»!")
        return

    is_tomorrow = message.text == "🔜 Завтра"
    target_date = datetime.now() + (timedelta(days=1) if is_tomorrow else timedelta(days=0))
    weekday_int = target_date.weekday()

    if weekday_int >= 6:  # Воскресенье
        await message.answer("🎉 В воскресенье пар нет! Отдыхай 😴")
        return

    day_name = DAYS_RU[weekday_int]
    schedule = await get_schedule_for_group(group_name)
    lessons = schedule.get(weekday_int, [])

    text = f"🎓 Группа: <b>{group_name}</b>\n"
    text += format_schedule_day(day_name, lessons)
    await message.answer(text)


# ── По дням ───────────────────────────────────────────────────

@dp.message(F.text == "📅 По дням")
async def handle_by_days(message: types.Message):
    await message.answer("📅 Выбери день недели:", reply_markup=get_days_keyboard())


@dp.callback_query(F.data.startswith("day_"))
async def callback_day(call: types.CallbackQuery):
    selected_day = call.data.split("_", 1)[1]
    user = get_user(call.from_user.id)
    group_name = user.get("group")

    if not group_name:
        await call.message.edit_text("⚠️ Выбери свою группу в разделе «⚙️ Настройки»!")
        await call.answer()
        return

    weekday_int = WEEKDAY_TO_INT.get(DAY_MAPPING.get(selected_day))
    if weekday_int is None:
        await call.answer("Ошибка")
        return

    schedule = await get_schedule_for_group(group_name)
    lessons = schedule.get(weekday_int, [])

    text = f"🎓 Группа: <b>{group_name}</b>\n"
    text += format_schedule_day(selected_day, lessons)

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к дням", callback_data="back_to_days")],
            [InlineKeyboardButton(text="❌ Скрыть", callback_data="delete_msg")],
        ]
    )
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer()


@dp.callback_query(F.data == "back_to_days")
async def callback_back_to_days(call: types.CallbackQuery):
    await call.message.edit_text("📅 Выбери день недели:", reply_markup=get_days_keyboard())
    await call.answer()


# ── Преподаватели ─────────────────────────────────────────────

@dp.message(F.text == "👨‍🏫 Преподаватели")
async def handle_teachers(message: types.Message):
    markup = await get_teachers_keyboard()
    if not markup:
        await message.answer("В базе пока нет преподавателей.")
        return
    await message.answer("👨‍🏫 <b>Выбери преподавателя:</b>", reply_markup=markup)


@dp.callback_query(F.data == "back_to_teachers")
async def callback_back_to_teachers(call: types.CallbackQuery):
    markup = await get_teachers_keyboard()
    if markup:
        await call.message.edit_text("👨‍🏫 <b>Выбери преподавателя:</b>", reply_markup=markup)
    else:
        await call.message.edit_text("В базе пока нет преподавателей.")
    await call.answer()


@dp.callback_query(F.data.startswith("tchr_"))
async def callback_teacher_days(call: types.CallbackQuery):
    teacher_name = call.data.split("_", 1)[1]

    buttons = [
        InlineKeyboardButton(text=short, callback_data=f"tchd_{teacher_name}_{short}")
        for full, short in DAY_MAPPING.items()
        if short != "Вс"
    ]
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            buttons[:3], buttons[3:],
            [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="back_to_teachers")],
            [InlineKeyboardButton(text="❌ Скрыть", callback_data="delete_msg")],
        ]
    )
    await call.message.edit_text(
        f"👨‍🏫 Преподаватель: <b>{teacher_name}</b>\n📅 Выбери день недели:", reply_markup=markup
    )
    await call.answer()


@dp.callback_query(F.data.startswith("tchd_"))
async def callback_teacher_day_schedule(call: types.CallbackQuery):
    parts = call.data.split("_", 2)
    teacher_name = parts[1]
    short_day = parts[2]

    full_day = [k for k, v in DAY_MAPPING.items() if v == short_day][0]
    day_prep = DAYS_PREP.get(full_day, full_day.lower())
    weekday_int = WEEKDAY_TO_INT.get(short_day)

    schedule = await get_schedule_for_teacher_from_db(teacher_name)
    lessons = schedule.get(weekday_int, [])

    if lessons:
        result = ""
        for l in lessons:
            emoji = NUM_EMOJI[l["num"]] if l["num"] < len(NUM_EMOJI) else str(l["num"])
            result += f"<blockquote><b>{emoji} {l['time']} | {l['subject']}</b>\n"
            result += f"🚪 Аудитория: <code>{l['room']}</code>\n"
            result += f"👥 Группы: {', '.join(l.get('groups', []))}</blockquote>\n"
        text = f"👨‍🏫 <b>{teacher_name}</b>\n📅 Расписание {day_prep}:\n\n{result}"
    else:
        text = f"👨‍🏫 <b>{teacher_name}</b>\n🎉 {full_day} пар нет! Отдыхаем 😴"

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к дням", callback_data=f"tchr_{teacher_name}")],
            [InlineKeyboardButton(text="❌ Скрыть", callback_data="delete_msg")],
        ]
    )
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer()


# ── Свободные кабинеты ────────────────────────────────────────

@dp.message(F.text == "🛋 Свободные кабинеты")
async def handle_free_rooms(message: types.Message):
    weekday_int = datetime.now().weekday()
    if weekday_int >= 6:
        await message.answer("🎉 Сегодня пар нет, <b>ВСЕ</b> аудитории свободны!")
        return

    day_name = DAYS_RU[weekday_int]
    day_prep = DAYS_PREP.get(day_name, day_name.lower())
    all_rooms = await get_all_rooms_from_db()
    occupied = await get_occupied_rooms_for_day(weekday_int)

    if not all_rooms:
        await message.answer("В базе пока нет аудиторий.")
        return

    text = f"🛋 <b>Свободные аудитории {day_prep}</b>\n\n"

    for slot in range(1, 7):
        time_str = SLOT_TIME_STRINGS.get(slot, "")
        emoji = NUM_EMOJI[slot] if slot < len(NUM_EMOJI) else str(slot)
        occ = occupied.get(slot, set())
        free = [r for r in all_rooms if r not in occ]

        if free:
            rooms_fmt = " • ".join([f"<code>{r}</code>" for r in free])
            text += f"<blockquote><b>{emoji} {time_str}</b>\n🚪 {rooms_fmt}</blockquote>\n"
        else:
            text += f"<blockquote><b>{emoji} {time_str}</b>\n🔴 <i>Все аудитории заняты</i></blockquote>\n"

    await message.answer(text)


# ── Настройки (выбор группы) ──────────────────────────────────

@dp.message(F.text == "⚙️ Настройки")
async def handle_settings(message: types.Message):
    markup = await get_groups_keyboard()
    user = get_user(message.from_user.id)
    current = user.get("group", "не выбрана")
    await message.answer(
        f"Текущая группа: <b>{current}</b>\n\n🎓 <b>Выбери свою группу:</b>",
        reply_markup=markup,
    )


@dp.callback_query(F.data.startswith("group_"))
async def callback_group(call: types.CallbackQuery):
    selected_group = call.data.split("_", 1)[1]
    update_user(call.from_user.id, group=selected_group)

    await call.message.edit_text(
        f"✅ Готово! Твоя группа: <b>{selected_group}</b>\n"
        "Теперь расписание будет показываться для этой группы."
    )
    await call.answer()


# ── Уведомления (новый раздел) ────────────────────────────────

@dp.message(F.text == "🔔 Уведомления")
async def handle_notifications(message: types.Message):
    user = get_user(message.from_user.id)

    if not user.get("group"):
        await message.answer("⚠️ Сначала выбери группу в «⚙️ Настройки»!")
        return

    markup = get_notifications_keyboard(user)
    await message.answer(
        "🔔 <b>Настройка уведомлений</b>\n\n"
        "Нажми на кнопку, чтобы включить или выключить опцию:",
        reply_markup=markup,
    )


@dp.callback_query(F.data == "toggle_notify_pair")
async def toggle_notify_pair(call: types.CallbackQuery):
    user = get_user(call.from_user.id)
    new_val = not user.get("notify_before_pair", True)
    update_user(call.from_user.id, notify_before_pair=new_val)

    user = get_user(call.from_user.id)
    markup = get_notifications_keyboard(user)
    status = "ВКЛЮЧЕНЫ 🟢" if new_val else "ВЫКЛЮЧЕНЫ 🔴"
    await call.message.edit_text(
        f"🔔 <b>Настройка уведомлений</b>\n\n"
        f"⏰ Напоминания за 15 мин до пары: <b>{status}</b>\n\n"
        "Нажми на кнопку, чтобы изменить:",
        reply_markup=markup,
    )
    await call.answer()


@dp.callback_query(F.data == "toggle_notify_changes")
async def toggle_notify_changes(call: types.CallbackQuery):
    user = get_user(call.from_user.id)
    new_val = not user.get("notify_changes", True)
    update_user(call.from_user.id, notify_changes=new_val)

    user = get_user(call.from_user.id)
    markup = get_notifications_keyboard(user)
    status = "ВКЛЮЧЕНЫ 🟢" if new_val else "ВЫКЛЮЧЕНЫ 🔴"
    await call.message.edit_text(
        f"🔔 <b>Настройка уведомлений</b>\n\n"
        f"📋 Уведомления об изменениях: <b>{status}</b>\n\n"
        "Нажми на кнопку, чтобы изменить:",
        reply_markup=markup,
    )
    await call.answer()


@dp.callback_query(F.data == "toggle_auto_mail")
async def toggle_auto_mail(call: types.CallbackQuery):
    user = get_user(call.from_user.id)
    new_val = not user.get("auto_mail", False)
    update_user(call.from_user.id, auto_mail=new_val)

    user = get_user(call.from_user.id)
    markup = get_notifications_keyboard(user)
    status = "ВКЛЮЧЕНА 🟢" if new_val else "ВЫКЛЮЧЕНА 🔴"
    await call.message.edit_text(
        f"🔔 <b>Настройка уведомлений</b>\n\n"
        f"🌅 Утренняя рассылка: <b>{status}</b>\n\n"
        "Нажми на кнопку, чтобы изменить:",
        reply_markup=markup,
    )
    await call.answer()


# ── Скачать PDF ───────────────────────────────────────────────

@dp.message(F.text == "📥 Скачать PDF")
async def handle_download_pdf(message: types.Message):
    user = get_user(message.from_user.id)
    group_name = user.get("group")

    if not group_name:
        await message.answer("⚠️ Сначала выбери группу в «⚙️ Настройки»!")
        return

    if not os.path.exists(FONT_PATH):
        await message.answer("❌ Файл шрифта (arial.ttf) не найден. Обратитесь к администратору.")
        return

    await message.answer("⏳ Создаю PDF-файл, подожди секунду...")

    schedule = await get_schedule_for_group(group_name)
    pdf_path = await sync_to_async(generate_pdf_from_db, thread_sensitive=True)(schedule, group_name)

    if pdf_path and os.path.exists(pdf_path):
        document = FSInputFile(pdf_path)
        await message.answer_document(
            document, caption=f"📄 Расписание для группы <b>{group_name}</b>"
        )
        os.remove(pdf_path)
    else:
        await message.answer("❌ Произошла ошибка при создании файла.")


def generate_pdf_from_db(schedule_dict, group_name):
    """Генерация PDF расписания — всё строго на 1 странице A4 Landscape."""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)  # Запрет авто-перехода на новую страницу
    pdf.add_page()
    pdf.set_margins(5, 5, 5)

    if os.path.exists(FONT_PATH):
        pdf.add_font("F", "", FONT_PATH)
        pdf.add_font("F", "B", FONT_PATH)
        fn = "F"
    else:
        fn = "Helvetica"

    # ── Размеры страницы: 297 × 210 мм (landscape A4) ────────
    page_w = 297
    page_h = 210
    margin = 5
    usable_w = page_w - 2 * margin   # 287
    usable_h = page_h - 2 * margin   # 200

    # ── Заголовок (компактный) ────────────────────────────────
    pdf.set_xy(margin, margin)
    pdf.set_font(fn, "B", 12)
    pdf.cell(usable_w, 6, f"Расписание  |  Группа: {group_name}  |  Неделя {_current_week_number_sync()}", align="C")
    title_h = 7  # высота заголовка + отступ

    # ── Параметры таблицы ─────────────────────────────────────
    PAIR_TIMES = {
        1: "08:30-10:05", 2: "10:15-11:50", 3: "12:00-13:35",
        4: "13:45-15:20", 5: "15:30-17:05", 6: "17:15-18:50",
    }
    max_pairs = 6
    num_days = 6

    table_top = margin + title_h
    table_h = usable_h - title_h       # всё оставшееся место
    h_head = 10                          # шапка таблицы
    h_row = (table_h - h_head) / num_days  # ~30.5 мм на строку

    w_day = 16                           # колонка "День"
    w_pair = (usable_w - w_day) / max_pairs  # ~45.2 мм на пару

    sx = margin  # start x
    sy = table_top  # start y

    # ── Шапка таблицы ─────────────────────────────────────────
    # Ячейка "День"
    pdf.set_fill_color(235, 235, 245)
    pdf.rect(sx, sy, w_day, h_head, "FD")
    pdf.set_font(fn, "B", 7)
    pdf.set_xy(sx, sy + 3)
    pdf.cell(w_day, 4, "День", align="C")

    # Ячейки пар 1..6
    for p in range(1, max_pairs + 1):
        px = sx + w_day + (p - 1) * w_pair
        pdf.rect(px, sy, w_pair, h_head, "FD")
        pdf.set_font(fn, "B", 11)
        pdf.set_xy(px, sy + 0.5)
        pdf.cell(w_pair, 5, str(p), align="C")
        pdf.set_font(fn, "", 6.5)
        pdf.set_xy(px, sy + 5.5)
        pdf.cell(w_pair, 4, PAIR_TIMES.get(p, ""), align="C")

    # ── Строки дней ───────────────────────────────────────────
    days_short = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]

    for i, d in enumerate(days_short):
        y = sy + h_head + i * h_row
        weekday_int = WEEKDAY_TO_INT[d]

        # Ячейка дня недели
        pdf.set_fill_color(245, 245, 252)
        pdf.rect(sx, y, w_day, h_row, "FD")
        pdf.set_font(fn, "B", 12)
        pdf.set_xy(sx, y + h_row / 2 - 3)
        pdf.cell(w_day, 6, d, align="C")

        lessons = schedule_dict.get(weekday_int, [])

        for p in range(1, max_pairs + 1):
            px = sx + w_day + (p - 1) * w_pair
            pair_lessons = [l for l in lessons if l["num"] == p]

            if not pair_lessons:
                # Пустая ячейка
                pdf.set_draw_color(200, 200, 200)
                pdf.rect(px, y, w_pair, h_row)
                pdf.set_draw_color(0, 0, 0)
                continue

            # Заполненная ячейка
            pdf.rect(px, y, w_pair, h_row)
            c = pair_lessons[0]

            room = _truncate(str(c.get("room", "")), 12)
            subject = _truncate(str(c.get("subject", "")), 42)
            teacher = _truncate(str(c.get("teacher", "")), 28)

            cell_pad = 1.2
            inner_w = w_pair - 2 * cell_pad

            # Строка 1: аудитория (верх, слева, мелко)
            pdf.set_font(fn, "B", 6.5)
            pdf.set_xy(px + cell_pad, y + 1)
            pdf.cell(inner_w, 3.5, room, align="L")

            # Строка 2-3: предмет (центр, жирный)
            # Разбиваем на 2 строки если длинный
            pdf.set_font(fn, "B", 7.5)
            subj_lines = _split_text(subject, 24)
            subj_block_h = len(subj_lines) * 3.8
            subj_start_y = y + (h_row - subj_block_h) / 2 - 1
            for li, line in enumerate(subj_lines[:2]):  # макс 2 строки
                pdf.set_xy(px + cell_pad, subj_start_y + li * 3.8)
                pdf.cell(inner_w, 3.8, line, align="C")

            # Строка 4: преподаватель (низ, справа, мелко)
            pdf.set_font(fn, "", 6)
            pdf.set_xy(px + cell_pad, y + h_row - 4.5)
            pdf.cell(inner_w, 3.5, teacher, align="R")

    file_path = os.path.join(CURRENT_DIR, f"schedule_{group_name}.pdf")
    pdf.output(file_path)
    return file_path


def _truncate(text, max_len):
    """Обрезает текст с многоточием если слишком длинный."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _split_text(text, chars_per_line):
    """Разбивает текст на строки по chars_per_line символов, по словам."""
    words = text.split()
    lines = []
    current = ""
    for w in words:
        if current and len(current) + 1 + len(w) > chars_per_line:
            lines.append(current)
            current = w
        else:
            current = f"{current} {w}".strip() if current else w
    if current:
        lines.append(current)
    return lines if lines else [text]


# ── Утилиты ───────────────────────────────────────────────────

@dp.callback_query(F.data == "delete_msg")
async def delete_message(call: types.CallbackQuery):
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer()


# ══════════════════════════════════════════════════════════════
#  ФОНОВЫЕ ЗАДАЧИ
# ══════════════════════════════════════════════════════════════

# ── 1. Утренняя рассылка ─────────────────────────────────────

async def daily_mailing():
    """Рассылка расписания в 07:00 подписавшимся пользователям."""
    users = load_users()
    weekday_int = datetime.now().weekday()

    if weekday_int >= 6:
        return

    day_name = DAYS_RU[weekday_int]

    for user_id, data in users.items():
        if data.get("auto_mail") and data.get("group"):
            group_name = data["group"]
            schedule = await get_schedule_for_group(group_name)
            lessons = schedule.get(weekday_int, [])

            text = f"🌅 <b>Доброе утро! Расписание на сегодня:</b>\n"
            text += f"🎓 Группа: <b>{group_name}</b>\n\n"
            text += format_schedule_day(day_name, lessons)

            try:
                await bot.send_message(chat_id=int(user_id), text=text)
            except Exception as e:
                print(f"[mailing] Не удалось отправить {user_id}: {e}")


# ── 2. Напоминание за 15 минут до пары ────────────────────────

async def check_pair_reminders():
    """
    Проверяет каждую минуту: если через 15 минут начинается пара —
    отправляет уведомление пользователю.
    """
    now = datetime.now()
    weekday_int = now.weekday()
    if weekday_int >= 6:
        return

    # Целевое время = текущее + 15 минут
    target = now + timedelta(minutes=15)
    target_hour = target.hour
    target_minute = target.minute

    # Находим, какой слот начинается в это время
    matching_slot = None
    for slot, (h, m) in SLOT_START_TIMES.items():
        if h == target_hour and m == target_minute:
            matching_slot = slot
            break

    if matching_slot is None:
        return

    users = load_users()

    for user_id, data in users.items():
        if not data.get("notify_before_pair", True):
            continue
        if not data.get("group"):
            continue

        group_name = data["group"]
        schedule = await get_schedule_for_group(group_name)
        lessons = schedule.get(weekday_int, [])
        pair_lessons = [l for l in lessons if l["num"] == matching_slot]

        if not pair_lessons:
            continue

        l = pair_lessons[0]
        emoji = NUM_EMOJI[l["num"]] if l["num"] < len(NUM_EMOJI) else str(l["num"])
        lt = LESSON_TYPE_LABELS.get(l.get("lesson_type", ""), "")

        text = (
            f"⏰ <b>Через 15 минут начинается пара!</b>\n\n"
            f"{emoji} <b>{l['time']}</b>"
            f"{' · ' + lt if lt else ''}\n"
            f"📚 <b>{l['subject']}</b>\n"
            f"👨‍🏫 {l['teacher']}\n"
            f"🚪 Аудитория: <code>{l['room']}</code>"
        )

        try:
            await bot.send_message(chat_id=int(user_id), text=text)
        except Exception as e:
            print(f"[reminder] Не удалось отправить {user_id}: {e}")


# ── 3. Отслеживание изменений в расписании ────────────────────

def _load_hashes():
    if os.path.exists(SCHEDULE_HASH_PATH):
        with open(SCHEDULE_HASH_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_hashes(data):
    with open(SCHEDULE_HASH_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _compute_schedule_hash_sync(group_name):
    """Вычисляет хэш расписания группы (синхронно, вызывает ORM)."""
    schedule = _get_schedule_for_group_sync(group_name)
    entries = []
    for day, lessons in sorted(schedule.items()):
        for l in lessons:
            entries.append(f"{day}:{l['num']}:{l['subject']}:{l['teacher']}:{l['room']}")
    raw = "|".join(entries)
    return hashlib.md5(raw.encode()).hexdigest()

compute_schedule_hash = sync_to_async(_compute_schedule_hash_sync, thread_sensitive=True)


async def check_schedule_changes():
    """
    Каждые 5 минут проверяет, изменилось ли расписание для каждой группы.
    Если да — отправляет уведомление подписанным пользователям.
    """
    users = load_users()
    hashes = _load_hashes()

    # Собираем уникальные группы, у которых есть подписчики
    groups_to_check = set()
    for user_id, data in users.items():
        if data.get("notify_changes", True) and data.get("group"):
            groups_to_check.add(data["group"])

    changed_groups = set()

    for group_name in groups_to_check:
        new_hash = await compute_schedule_hash(group_name)
        old_hash = hashes.get(group_name)

        if old_hash is not None and old_hash != new_hash:
            changed_groups.add(group_name)

        hashes[group_name] = new_hash

    _save_hashes(hashes)

    if not changed_groups:
        return

    # Получаем текущую неделю (async)
    current_week = await get_current_week()

    # Рассылка уведомлений об изменениях
    for user_id, data in users.items():
        if not data.get("notify_changes", True):
            continue
        group_name = data.get("group")
        if group_name not in changed_groups:
            continue

        text = (
            f"📋 <b>Расписание изменилось!</b>\n\n"
            f"🎓 Группа: <b>{group_name}</b>\n"
            f"Обнаружены изменения в расписании на неделю {current_week}.\n\n"
            f"Нажми <b>«🧾 Сегодня»</b> или <b>«📅 По дням»</b>, чтобы посмотреть обновлённое расписание."
        )

        try:
            await bot.send_message(chat_id=int(user_id), text=text)
        except Exception as e:
            print(f"[changes] Не удалось отправить {user_id}: {e}")

    print(f"[changes] Обнаружены изменения для групп: {changed_groups}")


# ══════════════════════════════════════════════════════════════
#  ЗАПУСК БОТА
# ══════════════════════════════════════════════════════════════

async def main():
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")

    # Утренняя рассылка — каждый день в 07:00
    scheduler.add_job(daily_mailing, "cron", hour=7, minute=0)

    # Проверка напоминаний о парах — каждую минуту
    scheduler.add_job(check_pair_reminders, "cron", minute="*")

    # Проверка изменений расписания — каждые 5 минут
    scheduler.add_job(check_schedule_changes, "interval", minutes=5)

    scheduler.start()

    print("=" * 50)
    print("  ✅ GoShiet Bot запущен!")
    print("  📡 Данные: Django БД")
    print("  ⏰ Напоминания о парах: каждую минуту")
    print("  📋 Проверка изменений: каждые 5 мин")
    print("  🌅 Утренняя рассылка: 07:00")
    print("=" * 50)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())