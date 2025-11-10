import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    ChatMemberUpdated
)
from aiogram.filters import ChatMemberUpdatedFilter, JOIN_TRANSITION

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Токен бота и ID администратора
BOT_TOKEN = 
ADMIN_ID = 


# Определяем состояния FSM для пошагового ввода
class WinrateCalc(StatesGroup):
    waiting_for_matches = State()
    waiting_for_current_wr = State()
    waiting_for_desired_wr = State()


# Состояния для отправки сообщения администратору
class AdminMessage(StatesGroup):
    waiting_for_message = State()
    waiting_for_confirmation = State()


# Состояния для ответа админа пользователю
class AdminReply(StatesGroup):
    waiting_for_reply = State()


# Функции для создания клавиатур
def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создание главной Reply-клавиатуры"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🎯 Рассчитать винрейт"),
                KeyboardButton(text="📖 Справка")
            ],
            [
                KeyboardButton(text="ℹ️ О боте")
            ]
        ],
        resize_keyboard=True,
    )
    return keyboard


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Создание Reply-клавиатуры с кнопкой отмены расчёта"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отменить расчет")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Введите значение или отмените..."
    )
    return keyboard


def get_cancel_admin_keyboard() -> ReplyKeyboardMarkup:
    """Создание Reply-клавиатуры с кнопкой отмены отправки сообщения админу"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отменить отправку")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Напишите ваше сообщение..."
    )
    return keyboard


def get_start_inline_keyboard() -> InlineKeyboardMarkup:
    """Создание inline-клавиатуры для стартового сообщения"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎯 Начать расчёт", callback_data="start_calc"),
                InlineKeyboardButton(text="📖 Помощь", callback_data="show_help")
            ],
            [
                InlineKeyboardButton(text="ℹ️ О боте", callback_data="about_bot")
            ]
        ]
    )
    return keyboard


def get_result_keyboard() -> InlineKeyboardMarkup:
    """Создание inline-клавиатуры для результатов"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Новый расчёт", callback_data="start_calc"),
                InlineKeyboardButton(text="📊 Справка", callback_data="show_help")
            ]
        ]
    )
    return keyboard


def create_progress_bar(current: float, goal: float, length: int = 10) -> str:
    """Создание визуального прогресс-бара"""
    percentage = min(current / goal * 100, 100) if goal > 0 else 0
    filled = int(length * percentage / 100)
    bar = "🟩" * filled + "⬜" * (length - filled)
    return f"{bar} {percentage:.1f}%"


def calculate_wins_needed(total_matches: int, current_wr: float, desired_wr: float) -> dict:
    """
    Рассчитывает количество побед подряд, необходимых для достижения желаемого винрейта.
    """
    if desired_wr > 100 or desired_wr < 0 or current_wr > 100 or current_wr < 0:
        return {'error': 'Винрейт должен быть от 0 до 100%'}
    if total_matches <= 0:
        return {'error': 'Количество матчей должно быть больше 0'}
    if desired_wr >= 100:
        return {'error': 'Невозможно достичь 100% винрейта (нужно не иметь ниодного поражения)'}
    if desired_wr <= current_wr:
        return {'error': 'Желаемый винрейт должен быть выше текущего'}
    
    wins_needed = (total_matches * (desired_wr - current_wr)) / (100 - desired_wr)
    wins_needed = int(wins_needed) + (1 if wins_needed % 1 > 0 else 0)
    
    current_wins = int(total_matches * current_wr / 100)
    new_total_matches = total_matches + wins_needed
    new_total_wins = current_wins + wins_needed
    actual_new_wr = (new_total_wins / new_total_matches) * 100
    
    return {
        'wins_needed': wins_needed,
        'current_wins': current_wins,
        'new_total_matches': new_total_matches,
        'new_total_wins': new_total_wins,
        'actual_new_wr': actual_new_wr
    }


# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

@dp.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def bot_added_to_chat(event: ChatMemberUpdated):
    """Обработчик добавления бота в группу"""
    if event.chat.type in ['group', 'supergroup']:
        welcome_text = (
            "🎮 <b>MLBB Winrate Calculator</b>\n\n"
            "👋 Привет! Я бот-калькулятор винрейта для Mobile Legends!\n\n"
            "💡 <b>Как использовать:</b>\n"
            "Напишите <code>@" + (await bot.me()).username + " 100 55 60</code>\n\n"
            "📋 <b>Формат:</b> <code>матчи текущий_WR желаемый_WR</code>\n\n"
            "📝 <b>Пример:</b> <code>@" + (await bot.me()).username + " 150 52.5 60</code>\n\n"
            "💡 Для полного функционала (с кнопками, подробной справкой, связью с админом) напишите боту в личные сообщения!"
        )
        await bot.send_message(
            chat_id=event.chat.id,
            text=welcome_text,
            parse_mode="HTML"
        )
        logger.info(f"Бот добавлен в группу: {event.chat.title} (ID: {event.chat.id})")


@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start - только в личке"""
    # В группах не работает
    if message.chat.type in ['group', 'supergroup']:
        return
    
    # Только в личных сообщениях
    welcome_text = (
        "┏━━━━━━━━━━━━━━━━━━━━━━\n"
        "┃  🎮 <b>MLBB CALCULATOR</b> 🎮  ┃\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👋 Привет! Я бот-калькулятор винрейта для <b>Mobile Legends: Bang Bang</b>!\n\n"
        "🎯 <b>Что я умею:</b>\n"
        "• Рассчитываю необходимое количество побед\n"
        "• Показываю детальную статистику\n"
        "• Работаю быстро и точно\n"
        "• Работаю в групповых чатах (inline-режим)!\n\n"
        "📊 Узнай, сколько побед подряд нужно одержать для достижения желаемого винрейта!\n\n"
        "💡 Используй кнопки ниже для навигации ⬇️"
    )
    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )
    await message.answer(
        "🚀 <b>Быстрый старт:</b>",
        parse_mode="HTML",
        reply_markup=get_start_inline_keyboard()
    )


@dp.message(Command('help'))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    # В группах не работает - только inline-режим
    if message.chat.type in ['group', 'supergroup']:
        return
    
    help_text = (
        "╔═══════════════════╗\n"
        "║  📖 <b>ИНСТРУКЦИЯ</b> 📖  ║\n"
        "╚═══════════════════╝\n\n"
        "<b>🎯 Как пользоваться ботом:</b>\n\n"
        "1️⃣ Нажми кнопку <b>\"🎯 Рассчитать винрейт\"</b> или /calc\n"
        "2️⃣ Введи <b>количество матчей</b> на герое (например: 100)\n"
        "3️⃣ Введи <b>текущий винрейт</b> в % (например: 55.5)\n"
        "4️⃣ Введи <b>желаемый винрейт</b> в % (например: 60)\n\n"
        "✅ Бот мгновенно рассчитает результат!\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>📱 Где найти статистику в MLBB:</b>\n\n"
        "🎮 <b>Для героя:</b>\n"
        "   • Профиль → Поле боя → Фавориты\n\n"
        "📊 <b>Для аккаунта:</b>\n"
        "   • Профиль → Поле боя → Статистика\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>💡 Полезные команды:</b>\n"
        "   /calc - Начать расчёт\n"
        "   /cancel - Отменить текущий расчёт\n"
        "   /help - Показать эту справку\n"
        "   /start - Главное меню"
    )
    
    await message.answer(
        help_text,
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )


@dp.message(Command('calc'))
async def cmd_calc(message: Message, state: FSMContext):
    """Обработчик команды /calc - начало расчета винрейта"""
    # В группах не работает - только inline-режим
    if message.chat.type in ['group', 'supergroup']:
        return
    
    await state.set_state(WinrateCalc.waiting_for_matches)
    calc_start_text = (
        "╔═══════════════════════╗\n"
        "║  🎮 <b>РАСЧЁТ ВИНРЕЙТА</b> 🎮  ║\n"
        "╚═══════════════════════╝\n\n"
        "📊 <b>Шаг 1 из 3</b>\n\n"
        "Введи <b>текущее количество матчей</b> на герое 🎯\n\n"
        "📝 <i>Пример:</i> <code>100</code>\n\n"
        "💡 Это можно найти в профиле героя во вкладке \"Избранное\""
    )
    await message.answer(
        calc_start_text,
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )


@dp.message(Command('cancel'))
async def cmd_cancel(message: Message, state: FSMContext):
    """Обработчик команды /cancel - отмена текущего расчета"""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer(
            "⚠️ Нет активного расчета для отмены.",
            reply_markup=get_main_keyboard()
        )
        return
    
    await state.clear()
    await message.answer(
        "❌ <b>Расчет отменен</b>\n\n"
        "Нажми кнопку ниже, чтобы начать заново 👇",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )


@dp.message(Command('admin'))
async def cmd_admin(message: Message, state: FSMContext):
    """Обработчик команды /admin - связь с администратором"""
    # В группах не работает
    if message.chat.type in ['group', 'supergroup']:
        return
    
    admin_text = (
        "╔════════════════════════╗\n"
        "║  💬 <b>СВЯЗЬ С АДМИНОМ</b> 💬  ║\n"
        "╚════════════════════════╝\n\n"
        "👋 Привет! Если у тебя есть вопросы или предложения, я всегда на связи.\n\n"
        "✍️ <b>Жду твоё сообщение...</b>"
    )
    
    await state.set_state(AdminMessage.waiting_for_message)
    await message.answer(
        admin_text,
        parse_mode="HTML",
        reply_markup=get_cancel_admin_keyboard()
    )


@dp.message(AdminMessage.waiting_for_message)
async def process_admin_message(message: Message, state: FSMContext):
    """Обработка сообщения пользователя для отправки администратору"""
    if message.text == "❌ Отменить отправку":
        await state.clear()
        await message.answer(
            "❌ <b>Отправка сообщения отменена</b>\n\n"
            "Если понадоблюсь - нажми /admin",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
        return
    
    await state.update_data(user_message=message.text, user_id=message.from_user.id, 
                           username=message.from_user.username or "Без username",
                           full_name=message.from_user.full_name)
    
    confirm_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, отправить", callback_data="admin_confirm_yes"),
                InlineKeyboardButton(text="❌ Нет, отменить", callback_data="admin_confirm_no")
            ]
        ]
    )
    
    preview_text = (
        "📬 <b>Предпросмотр сообщения:</b>\n\n"
        f"<i>{message.text}</i>\n\n"
        "❓ <b>Отправить это админу?</b>"
    )
    
    await message.answer(
        preview_text,
        parse_mode="HTML",
        reply_markup=confirm_keyboard
    )


@dp.callback_query(F.data == "admin_confirm_yes")
async def callback_admin_confirm_yes(callback: CallbackQuery, state: FSMContext):
    """Подтверждение отправки сообщения администратору"""
    await callback.answer()
    
    data = await state.get_data()
    user_message = data.get('user_message')
    user_id = data.get('user_id')
    username = data.get('username')
    full_name = data.get('full_name')
    
    admin_notification = (
        "📨 <b>НОВОЕ СООБЩЕНИЕ ОТ ПОЛЬЗОВАТЕЛЯ</b>\n\n"
        f"👤 <b>От:</b> {full_name}\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"📝 <b>Username:</b> @{username}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💬 <b>Сообщение:</b>\n\n{user_message}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    # Создаем кнопку "Ответить" для админа
    reply_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Ответить пользователю", callback_data=f"reply_to_{user_id}")]
        ]
    )
    
    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_notification,
            parse_mode="HTML",
            reply_markup=reply_keyboard
        )
        await callback.message.edit_text(
            "✅ <b>Сообщение успешно отправлено!</b>\n\n"
            "Спасибо за обратную связь! 🙏",
            parse_mode="HTML"
        )
        logger.info(f"Сообщение от пользователя {user_id} ({username}) отправлено администратору")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения админу: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка при отправке!</b> Попробуйте позже.",
            parse_mode="HTML"
        )
    finally:
        await state.clear()
        await callback.message.answer(
            "Возвращаюсь в главное меню...",
            reply_markup=get_main_keyboard()
        )


@dp.callback_query(F.data == "admin_confirm_no")
async def callback_admin_confirm_no(callback: CallbackQuery, state: FSMContext):
    """Отмена отправки сообщения администратору"""
    await callback.answer()
    await callback.message.edit_text(
        "❌ <b>Отправка отменена</b>.",
        parse_mode="HTML"
    )
    await callback.message.answer(
        "Возвращаюсь в главное меню...",
        reply_markup=get_main_keyboard()
    )
    await state.clear()


@dp.callback_query(F.data.startswith("reply_to_"))
async def callback_reply_to_user(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Ответить пользователю' для админа"""
    await callback.answer()
    
    # Извлекаем user_id из callback_data
    user_id = int(callback.data.split("_")[-1])
    
    # Сохраняем user_id в состояние
    await state.update_data(reply_to_user_id=user_id)
    await state.set_state(AdminReply.waiting_for_reply)
    
    await callback.message.answer(
        f"💬 <b>Режим ответа пользователю</b>\n\n"
        f"🆔 User ID: <code>{user_id}</code>\n\n"
        f"✍️ Напишите ваш ответ следующим сообщением.\n"
        f"Пользователь получит ваше сообщение в боте.\n\n"
        f"Для отмены используйте /cancel",
        parse_mode="HTML"
    )
    
    logger.info(f"Админ начал отвечать пользователю {user_id}")


@dp.message(AdminReply.waiting_for_reply)
async def process_admin_reply(message: Message, state: FSMContext):
    """Обработка ответа админа пользователю"""
    # Проверяем, не отменяет ли админ
    if message.text == "/cancel":
        await state.clear()
        await message.answer(
            "❌ <b>Ответ отменён</b>",
            parse_mode="HTML"
        )
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    user_id = data.get('reply_to_user_id')
    
    if not user_id:
        await message.answer("❌ Ошибка: ID пользователя не найден")
        await state.clear()
        return
    
    # Формируем сообщение для пользователя
    user_notification = (
        "📬 <b>ОТВЕТ ОТ АДМИНИСТРАТОРА</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{message.text}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💡 <i>Если у вас остались вопросы, используйте /admin</i>"
    )
    
    try:
        # Отправляем ответ пользователю
        await bot.send_message(
            chat_id=user_id,
            text=user_notification,
            parse_mode="HTML"
        )
        
        # Уведомляем админа об успешной отправке
        await message.answer(
            f"✅ <b>Ответ успешно отправлен!</b>\n\n"
            f"🆔 User ID: <code>{user_id}</code>\n\n"
            f"📤 Ваше сообщение:\n{message.text}",
            parse_mode="HTML"
        )
        
        logger.info(f"Админ ответил пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке ответа пользователю {user_id}: {e}")
        await message.answer(
            f"❌ <b>Ошибка при отправке!</b>\n\n"
            f"Возможно, пользователь заблокировал бота.\n"
            f"Ошибка: {str(e)}",
            parse_mode="HTML"
        )
    
    await state.clear()


@dp.message(WinrateCalc.waiting_for_matches)
async def process_matches(message: Message, state: FSMContext):
    """Обработка ввода количества матчей"""
    if message.text in ["❌ Отменить", "❌ Отменить расчет"]:
        await cmd_cancel(message, state)
        return
    
    try:
        matches = int(message.text)
        if matches <= 0:
            await message.answer("⚠️ Количество матчей должно быть <b>больше 0</b>.", parse_mode="HTML")
            return
        
        await state.update_data(total_matches=matches)
        await state.set_state(WinrateCalc.waiting_for_current_wr)
        
        step2_text = (
            f"✅ <b>Принято!</b> Матчей: <code>{matches}</code>\n\n"
            f"📊 <b>Шаг 2 из 3:</b> Введи <b>текущий винрейт</b> в % 📈\n"
            f"📝 <i>Пример:</i> <code>55.5</code>"
        )
        await message.answer(step2_text, parse_mode="HTML", reply_markup=get_cancel_keyboard())
    except ValueError:
        await message.answer("⚠️ <b>Неверный формат!</b> Введи <b>целое число</b>.", parse_mode="HTML")


@dp.message(WinrateCalc.waiting_for_current_wr)
async def process_current_wr(message: Message, state: FSMContext):
    """Обработка ввода текущего винрейта"""
    if message.text in ["❌ Отменить", "❌ Отменить расчет"]:
        await cmd_cancel(message, state)
        return
    
    try:
        current_wr = float(message.text.replace(',', '.'))
        if not 0 <= current_wr <= 100:
            await message.answer("⚠️ Винрейт должен быть от <b>0</b> до <b>100%</b>.", parse_mode="HTML")
            return
        
        await state.update_data(current_wr=current_wr)
        await state.set_state(WinrateCalc.waiting_for_desired_wr)
        
        step3_text = (
            f"✅ <b>Принято!</b> Текущий WR: <code>{current_wr:.1f}%</code>\n\n"
            f"📊 <b>Шаг 3 из 3:</b> Введи <b>желаемый винрейт</b> в % 🎯\n"
            f"📝 <i>Пример:</i> <code>60</code>"
        )
        await message.answer(step3_text, parse_mode="HTML", reply_markup=get_cancel_keyboard())
    except ValueError:
        await message.answer("⚠️ <b>Неверный формат!</b> Введи <b>число</b>.", parse_mode="HTML")


@dp.message(WinrateCalc.waiting_for_desired_wr)
async def process_desired_wr(message: Message, state: FSMContext):
    """Обработка ввода желаемого винрейта и выполнение расчета"""
    if message.text in ["❌ Отменить", "❌ Отменить расчет"]:
        await cmd_cancel(message, state)
        return
    
    try:
        desired_wr = float(message.text.replace(',', '.'))
        data = await state.get_data()
        result = calculate_wins_needed(data['total_matches'], data['current_wr'], desired_wr)
        
        if 'error' in result:
            await message.answer(f"❌ <b>Ошибка:</b> {result['error']}", parse_mode="HTML")
            await state.clear()
            return
        
        progress_bar = create_progress_bar(data['current_wr'], desired_wr)
        response = (
            "╔════════════════════════╗\n"
            "║  ✅ <b>РАСЧЁТ ЗАВЕРШЁН!</b> ✅  ║\n"
            "╚════════════════════════╝\n\n"
            f"📊 <b>ИСХОДНЫЕ ДАННЫЕ:</b>\n"
            f"┣ Матчей: <code>{data['total_matches']}</code>\n"
            f"┣ Текущий WR: <code>{data['current_wr']:.1f}%</code>\n\n"
            f"{progress_bar}\n\n"
            f"🎯 <b>ЦЕЛЬ: {desired_wr:.1f}%</b>\n\n"
            f"🏆 <b>НУЖНО ВЫИГРАТЬ ПОДРЯД:</b>\n"
            f"<b><u>{result['wins_needed']} матч(ей)</u></b> 🔥\n\n"
            f"📈 <b>ИТОГОВАЯ СТАТИСТИКА:</b>\n"
            f"┣ Всего матчей: <code>{result['new_total_matches']}</code>\n"
            f"┗ Итоговый WR: <code>{result['actual_new_wr']:.2f}%</code>\n\n"
            f"💪 <b>Удачи на поле боя!</b> 🎮"
        )
        
        await message.answer(response, parse_mode="HTML", reply_markup=get_main_keyboard())
        await message.answer("🔄 <b>Что дальше?</b>", parse_mode="HTML", reply_markup=get_result_keyboard())
        await state.clear()
        
    except ValueError:
        await message.answer("⚠️ <b>Неверный формат!</b> Введи <b>число</b>.", parse_mode="HTML")


@dp.callback_query(F.data == "start_calc")
async def callback_start_calc(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await cmd_calc(callback.message, state)


@dp.callback_query(F.data == "show_help")
async def callback_show_help(callback: CallbackQuery):
    await callback.answer()
    await cmd_help(callback.message)


@dp.callback_query(F.data == "about_bot")
async def callback_about_bot(callback: CallbackQuery):
    await callback.answer()
    await text_about_button(callback.message)


@dp.message(F.text == "🎯 Рассчитать винрейт")
async def text_calc_button(message: Message, state: FSMContext):
    await cmd_calc(message, state)


@dp.message(F.text == "📖 Справка")
async def text_help_button(message: Message):
    await cmd_help(message)


@dp.message(F.text == "ℹ️ О боте")
async def text_about_button(message: Message):
    """Обработчик кнопки 'О боте'"""
    about_text = (
        "╔═══════════════════╗\n"
        "║  ℹ️ <b>О БОТЕ</b> ℹ️  ║\n"
        "╚═══════════════════╝\n\n"
        "🎮 <b>MLBB Winrate Calculator</b>\n\n"
        "Умный калькулятор для игроков Mobile Legends, "
        "который помогает планировать свой путь к желаемому винрейту.\n\n"
        "💪 <b>Удачи на поле боя!</b> 🏆"
    )
    await message.answer(about_text, parse_mode="HTML", reply_markup=get_main_keyboard())


@dp.message(F.text.in_({"❌ Отменить расчет", "❌ Отменить отправку"}))
async def text_cancel_button(message: Message, state: FSMContext):
    await cmd_cancel(message, state)


@dp.message()
async def unknown_message(message: Message):
    """Обработчик неизвестных сообщений - только для личных сообщений"""
    # Игнорируем сообщения в группах
    if message.chat.type in ['group', 'supergroup']:
        return
    
    # Отвечаем только в личных сообщениях
    await message.answer(
        "❓ <b>Не понимаю...</b>\n\n"
        "Используй кнопки ниже 👇",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )


@dp.inline_query()
async def inline_calc(inline_query: InlineQuery):
    """Обработчик inline-запросов для использования бота в любом чате"""
    query = inline_query.query.strip()
    
    if not query:
        # Подсказка если пусто
        result = InlineQueryResultArticle(
            id="help",
            title="📊 MLBB Winrate Calculator",
            description="Введите: матчи текущий_WR желаемый_WR (пример: 100 55 60)",
            input_message_content=InputTextMessageContent(
                message_text=(
                    "🎮 <b>MLBB Winrate Calculator</b>\n\n"
                    "💡 <b>Как использовать:</b>\n"
                    f"Напишите: <code>@{(await bot.me()).username} 100 55 60</code>\n\n"
                    "Формат: <b>матчи текущий_WR желаемый_WR</b>\n"
                    "Пример: 100 55 60"
                ),
                parse_mode="HTML"
            ),
            thumb_url="https://i.imgur.com/7XhGpwU.png"
        )
        await inline_query.answer([result], cache_time=1, is_personal=True)
        return
    
    # Парсим данные
    try:
        parts = query.split()
        if len(parts) != 3:
            raise ValueError("Нужно 3 числа")
        
        matches = int(parts[0])
        current_wr = float(parts[1].replace(',', '.'))
        desired_wr = float(parts[2].replace(',', '.'))
        
        # Вычисляем
        result_data = calculate_wins_needed(matches, current_wr, desired_wr)
        
        if 'error' in result_data:
            result_text = f"❌ <b>Ошибка:</b> {result_data['error']}"
            title = "❌ Ошибка в данных"
            description = result_data['error']
        else:
            # Формируем красивый результат как в личных сообщениях
            wins = result_data['wins_needed']
            new_matches = result_data['new_total_matches']
            new_wr = result_data['actual_new_wr']
            
            # Создаем прогресс-бар
            progress_bar = create_progress_bar(current_wr, desired_wr)
            
            result_text = (
                "╔════════════════════════╗\n"
                "║  ✅ <b>РАСЧЁТ ЗАВЕРШЁН!</b> ✅  ║\n"
                "╚════════════════════════╝\n\n"
                f"📊 <b>ИСХОДНЫЕ ДАННЫЕ:</b>\n"
                f"┣ Матчей: <code>{matches}</code>\n"
                f"┣ Текущий WR: <code>{current_wr:.1f}%</code>\n\n"
                f"{progress_bar}\n\n"
                f"🎯 <b>ЦЕЛЬ: {desired_wr:.1f}%</b>\n\n"
                f"🏆 <b>НУЖНО ВЫИГРАТЬ ПОДРЯД:</b>\n"
                f"<b><u>{wins} матч(ей)</u></b> 🔥\n\n"
                f"📈 <b>ИТОГОВАЯ СТАТИСТИКА:</b>\n"
                f"┣ Всего матчей: <code>{new_matches}</code>\n"
                f"┗ Итоговый WR: <code>{new_wr:.2f}%</code>\n\n"
                f"💪 <b>Удачи на поле боя!</b> 🎮"
            )
            title = f"✅ Нужно {wins} побед"
            description = f"Из {matches} матчей ({current_wr}% → {desired_wr}%)"
        
        result = InlineQueryResultArticle(
            id=query,
            title=title,
            description=description,
            input_message_content=InputTextMessageContent(
                message_text=result_text,
                parse_mode="HTML"
            ),
            thumb_url="https://i.imgur.com/7XhGpwU.png"
        )
        
        await inline_query.answer([result], cache_time=1, is_personal=True)
        logger.info(f"Inline-запрос обработан: {query}")
        
    except (ValueError, IndexError) as e:
        result = InlineQueryResultArticle(
            id="error",
            title="❌ Неверный формат",
            description="Используйте: матчи текущий_WR желаемый_WR (пример: 100 55 60)",
            input_message_content=InputTextMessageContent(
                message_text=(
                    "❌ <b>Неверный формат данных</b>\n\n"
                    "💡 <b>Правильный формат:</b>\n"
                    f"<code>@{(await bot.me()).username} матчи текущий_WR желаемый_WR</code>\n\n"
                    "<b>Пример:</b>\n"
                    f"<code>@{(await bot.me()).username} 100 55 60</code>\n\n"
                    "Где:\n"
                    "• <b>100</b> - количество сыгранных матчей\n"
                    "• <b>55</b> - текущий винрейт в %\n"
                    "• <b>60</b> - желаемый винрейт в %"
                ),
                parse_mode="HTML"
            ),
            thumb_url="https://i.imgur.com/7XhGpwU.png"
        )
        await inline_query.answer([result], cache_time=1, is_personal=True)
        logger.warning(f"Ошибка в inline-запросе: {query}, ошибка: {e}")


async def set_bot_commands():
    """Установка команд бота в меню"""
    # Команды для личных сообщений
    private_commands = [
        BotCommand(command="start", description="🏠 Главное меню"),
        BotCommand(command="admin", description="💬 Написать админу")
    ]
    await bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())
    
    # Для групп - пустой список (без команд)
    await bot.set_my_commands([], scope=BotCommandScopeAllGroupChats())
    
    logger.info("Команды бота установлены: только для личных сообщений")


async def main():
    """Главная функция запуска бота"""
    logger.info("Запуск бота...")
    
    try:
        await set_bot_commands()
        
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
