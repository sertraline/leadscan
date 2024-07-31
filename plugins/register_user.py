from aiogram import F, types, Dispatcher, Bot, filters
from models.postgres import PostgresInterface
from typing import Callable
from models.users import User
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
import re
from traceback import format_exc


class Form(StatesGroup):
    email = State()


class Register:
    command = "start"

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
            self.start_entry,
            filters.Command(commands=[self.command], prefix=self.prefix),
        )
        self.dp.message.register(
            self.email_sent, Form.email
        )

    # точка входа
    async def start_entry(self, message: types.Message, user: User, state: FSMContext):
        if not message.from_user:
            return
        if user.email:
            return await message.reply("Вы уже зарегистрированы!")

        chat_id = message.chat.id
        user_id = message.from_user.id

        await state.set_state(Form.email)

        await self.bot.send_message(
            chat_id,
            text="Здравствуйте! Для работы с ботом Вам будет необходимо зарегистрироваться. Пожалуйста, отправьте свой email адрес ниже.",
        )

    async def email_sent(self, message: types.Message, user: User, state: FSMContext):
        current_state = await state.get_state()
        if current_state is None:
            return

        if not message.text:
            return
        if not message.from_user:
            return

        email = message.text.strip()
        # валидация адреса
        check = re.search(r"^[\w\.\+\-]+\@[\w]+\.[a-z]{2,3}$", email)
        if not check:
            await state.set_state(Form.email)
            return await message.reply("Введенный email адрес не является валидным. Проверьте свой адрес на ошибки и повторите еще раз.")

        await state.clear()

        query = "UPDATE users SET email = $1 WHERE telegram_id = $2"
        try:
            await self.sql.exec(query, email, message.from_user.id)
        except Exception:
            self.debug(format_exc())
            return await self.bot.send_message(
                message.chat.id, "Не удалось зарегистрировать пользователя."
            )

        await self.bot.send_message(
            message.chat.id,
            "Пользователь успешно зарегистрирован! Для добавления заметок используйте /addnote",
        )
