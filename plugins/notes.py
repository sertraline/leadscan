from aiogram import F, types, Dispatcher, Bot, filters
from models.postgres import PostgresInterface
from typing import Callable, cast, Iterable, NamedTuple
from models.users import User
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from traceback import format_exc
from datetime import datetime, timedelta
import json
from redis.asyncio import Redis
from pytz import timezone


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
    items_per_page = 4

    def __init__(
        self,
        dp: Dispatcher,
        sql: PostgresInterface,
        bot: Bot,
        debug: Callable,
        prefix: str,
        redis: Redis,
        **_,
    ):
        self.dp = dp
        self.sql = sql
        self.bot = bot
        self.debug = debug
        self.prefix = prefix
        self.redis = redis

        self.dp.message.register(
            self.note_entry,
            filters.Command(commands=[self.command], prefix=self.prefix),
        )
        self.dp.message.register(self.date_entered, Form.date_set)
        self.dp.message.register(self.text_entered, Form.text_set)
        self.dp.message.register(self.my_notes, filters.Command(commands=['mynotes'], prefix=self.prefix))
        self.dp.callback_query.register(self.next_page, F.data.startswith("nextpage_"))
        self.dp.callback_query.register(self.prev_page, F.data.startswith("prevpage_"))

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

    async def my_notes(self, message: types.Message, user: User, state: FSMContext):
        if not message.from_user:
            return
        if not user.email:
            return await message.reply(
                "Вы не зарегистрированы! Пройдите регистрацию через команду /start"
            )

        chat_id = message.chat.id
        user_id = message.from_user.id

        query = "SELECT * FROM notes WHERE user_id = $1"
        records = await self.sql.fetch(query, user.id)
        if not records:
            await message.reply("Заметок нет.")

        records = [dict(i) for i in records]
        for rec in records:
            for key in rec.keys():
                # сериализация дат
                if key == "reminder_time":
                    d = rec[key].astimezone(timezone("Europe/Moscow"))
                    rec[key] = datetime.strftime(d, '%d-%m-%Y %H:%M')

        kb = InlineKeyboardBuilder()
        total_items = len(records)
        page = 1
        pages = total_items // self.items_per_page

        offset = (page - 1) * self.items_per_page
        current = records[offset : offset + self.items_per_page]

        text = ""
        for i, item in enumerate(current, start=1):
            txt = item["text"]
            d = item["reminder_time"]
            if len(txt) > 200:
                txt = txt[:200] + "..."
            k = f"{i}. <b>{d}</b>\n{txt}\n"
            text += k

        if pages > 1:
            kb.row(
                types.InlineKeyboardButton(
                    text=f"Далее (1/{pages})",
                    callback_data=f"nextpage_{chat_id}_{user_id}_{page+1}_{message.message_id}",
                ),
            )

        await self.redis.set(f"{chat_id}_{user_id}", json.dumps(records))
        await message.reply(text, reply_markup=kb.as_markup(), parse_mode="HTML")

    async def next_page(self, cb: types.CallbackQuery):
        data = cb.data
        if not data:
            return
        data = data.split("_")
        # str, chat_id, user_id, page, message_id
        chat_id = int(data[1])
        user_id = int(data[2])
        page = int(data[3])
        m_id = int(data[4])

        if cb.from_user.id != user_id:
            return await cb.answer("Это не для вас")

        parsed = await self.redis.get(f"{chat_id}_{user_id}")
        if not parsed:
            return await cb.answer("Нет данных")
        parsed = json.loads(parsed)

        kb = InlineKeyboardBuilder()
        total_items = len(parsed)
        pages = total_items // self.items_per_page

        offset = (page - 1) * self.items_per_page
        current = parsed[offset : offset + self.items_per_page]

        text = ""
        for i, item in enumerate(current, start=1):
            txt = item["text"]
            d = item["reminder_time"]
            if len(txt) > 200:
                txt = txt[:200] + "..."
            k = f"{i}. <b>{d}</b>\n{txt}\n"
            text += k

        if page + 1 <= pages:
            kb.row(
                types.InlineKeyboardButton(
                    text="Назад",
                    callback_data=f"prevpage_{chat_id}_{user_id}_{page-1}_{m_id}",
                ),
                types.InlineKeyboardButton(
                    text=f"Далее ({page}/{pages})",
                    callback_data=f"nextpage_{chat_id}_{user_id}_{page+1}_{m_id}",
                ),
            )
        else:
            kb.row(
                types.InlineKeyboardButton(
                    text="Назад",
                    callback_data=f"prevpage_{chat_id}_{user_id}_{page-1}_{m_id}",
                ),
            )

        if cb.message:
            await self.bot.delete_message(
                chat_id=chat_id, message_id=cb.message.message_id
            )
        await self.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=m_id,
            text=text,
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )

    async def prev_page(self, cb: types.CallbackQuery):
        data = cb.data
        if not data:
            return
        data = data.split("_")
        # str, chat_id, user_id, page, message_id
        chat_id = int(data[1])
        user_id = int(data[2])
        page = int(data[3])
        m_id = int(data[4])

        if cb.from_user.id != user_id:
            return await cb.answer("Nuh-uh")

        parsed = await self.redis.get(f"{chat_id}_{user_id}")
        if not parsed:
            return await cb.answer("Uh-oh")
        parsed = json.loads(parsed)

        kb = InlineKeyboardBuilder()
        total_items = len(parsed)
        pages = total_items // self.items_per_page

        offset = (page - 1) * self.items_per_page
        current = parsed[offset : offset + self.items_per_page]

        text = ""
        for i, item in enumerate(current, start=1):
            txt = item["text"]
            d = item["reminder_time"]
            if len(txt) > 200:
                txt = txt[:200] + "..."
            k = f"{i}. <b>{d}</b>\n{txt}\n"
            text += k

        if page >= 2:
            kb.row(
                types.InlineKeyboardButton(
                    text="Назад",
                    callback_data=f"prevpage_{chat_id}_{user_id}_{page-1}_{m_id}",
                ),
                types.InlineKeyboardButton(
                    text=f"Далее ({page}/{pages})",
                    callback_data=f"nextpage_{chat_id}_{user_id}_{page+1}_{m_id}",
                ),
            )
        else:
            kb.row(
                types.InlineKeyboardButton(
                    text=f"Далее ({page}/{pages})",
                    callback_data=f"nextpage_{chat_id}_{user_id}_{page+1}_{m_id}",
                ),
            )

        if cb.message:
            await self.bot.delete_message(
                chat_id=chat_id, message_id=cb.message.message_id
            )
        await self.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=m_id,
            text=text,
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )

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
