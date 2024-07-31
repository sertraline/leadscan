from aiogram import F, types, Dispatcher, Bot, filters
from models.postgres import PostgresInterface
from typing import Callable, cast, Iterable, NamedTuple
from models.users import User
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
import re
from traceback import format_exc
from datetime import datetime, timedelta


class Duration(NamedTuple):
    duration: datetime | None


class Form(StatesGroup):
    date_set = State()
    text_set = State()


kb = [
    [
        types.KeyboardButton(text="1м"),
        types.KeyboardButton(text="10м"),
        types.KeyboardButton(text="15м"),
    ],
    [types.KeyboardButton(text="30м"), types.KeyboardButton(text="1ч"), types.KeyboardButton(text="1д")],
]
DATES_KB = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


class Notes:
    command = "addnote"

    def __init__(
        self,
        dp: Dispatcher,
        sql: PostgresInterface,
        bot: Bot,
        debug: Callable,
        prefix: str,
        **_,
    ):
        self.dp = dp
        self.sql = sql
        self.bot = bot
        self.debug = debug
        self.prefix = prefix

        self.dp.message.register(
            self.note_entry,
            filters.Command(commands=[self.command], prefix=self.prefix),
        )
        self.dp.message.register(self.date_entered, Form.date_set)
        self.dp.message.register(self.text_entered, Form.text_set)

    def get_duration(self, arg: str) -> Duration:
        units = {
            "days": "д",
            "weeks": "н",
            "minutes": "м",
            "hours": "ч",
        }

        has_suffix = filter(arg.endswith, cast(Iterable, tuple(units.values())))
        try:
            has_suffix = list(has_suffix)
        except TypeError:
            return Duration(None)
        if not has_suffix:
            return Duration(None)

        try:
            length = int(arg[:-1])
        except (TypeError, ValueError):
            return Duration(None)

        key = [x for x in units.keys() if units[x] == has_suffix[0]]
        if not key:
            return Duration(None)

        date = datetime.now() + timedelta(**{key[0]: length})
        return Duration(duration=date)

    async def note_entry(self, message: types.Message, user: User, state: FSMContext):
        if not message.from_user:
            return
        if not user.email:
            return await message.reply("Вы не зарегистрированы! Пройдите регистрацию через команду /start")

        chat_id = message.chat.id
        user_id = message.from_user.id

        await state.set_state(Form.date_set)

        await self.bot.send_message(
            chat_id,
            text="На какую дату Вы хотите установить заметку? Вы можете выбрать одно из значений ниже или ввести произвольную дату типа ДД-ММ-ГГГГ Ч:М.",
            reply_markup=DATES_KB,
        )

    async def date_entered(self, message: types.Message, user: User, state: FSMContext):
        current_state = await state.get_state()
        if current_state is None:
            return

        if not message.text:
            return
        if not message.from_user:
            return

        err_msg = "Введите дату вида ДД-ММ-ГГГ Ч:М (01-08-2024 12:00) или выберите одно из значений ниже."

        date = message.text.strip()
        final = None
        check = date.split('-')
        if len(check) == 3:
            # произвольная дата
            try:
                final = datetime.strptime(date, '%d-%m-%Y %H:%M')
            except Exception:
                self.debug(format_exc())

                await state.set_state(Form.date_set)
                return await self.bot.send_message(
                    message.chat.id,
                    text=err_msg,
                    reply_markup=DATES_KB,
                )
        else:
            md = self.get_duration(date)
            if not md.duration:
                await state.set_state(Form.date_set)
                return await self.bot.send_message(
                    message.chat.id,
                    text=err_msg,
                    reply_markup=DATES_KB,
                )
            final = md.duration

        await state.set_state(Form.text_set)
        await state.set_data({"final": datetime.strftime(final, '%d-%m-%Y %H:%M')})

        await self.bot.send_message(
            message.chat.id,
            text="Отлично! Введите текст Вашей заметки.",
            reply_markup=types.ReplyKeyboardRemove()
        )

    async def text_entered(self, message: types.Message, user: User, state: FSMContext):
        current_state = await state.get_state()
        if current_state is None:
            return

        if not message.text:
            return
        if not message.from_user:
            return

        data = await state.get_data()
        if not data:
            return
        final = data.get('final')
        if not final:
            return
        final = datetime.strptime(final, '%d-%m-%Y %H:%M')

        query = "INSERT INTO notes(user_id, text, reminder_time) VALUES ($1, $2, $3);"
        try:
            await self.sql.exec(query, user.id, message.text, final)
        except Exception:
            self.debug(format_exc())
            return await self.bot.send_message(
                message.chat.id, "Не удалось сохранить заметку."
            )

        await self.bot.send_message(
            message.chat.id,
            text="Заметка сохранена. Я пришлю напоминание о заметке за 10 минут или ранее до установленной даты.",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        await state.clear()
