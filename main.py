from os import getenv
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from redis.asyncio import Redis
from log import DebugLogging
from models.postgres import PostgresInterface
from models.users import UserManager
from typing import Optional
from middlewares import user_middleware
from member_watch import MemberWatch
from telethon import TelegramClient
from pytz import timezone
from datetime import datetime

import plugins
import asyncio
import sys
import uvloop


# подтянуть переменные из .env
load_dotenv()
TOKEN = getenv("BOT_TOKEN") or ""
API_ID = int(getenv("API_ID") or 0)
API_HASH = getenv("API_HASH") or ""
log = DebugLogging(getenv("DEBUG") == "true").logger

r = Redis(
    host=getenv("REDIS_HOST") or "localhost",
    port=int(getenv("REDIS_PORT") or 6379),
    db=getenv("REDIS_DB") or "0",
)
# Редис будет использоваться aiogram для хранилища стейтов
storage = RedisStorage(redis=r)

client = TelegramClient("bot_session", API_ID, API_HASH)


async def check_pending_notes(payload: dict) -> None:
    sql: Optional[PostgresInterface] = payload.get("sql")
    if not sql:
        print("Unable to fetch the SQL interface.")
        sys.exit(1)

    bot: Optional[Bot] = payload.get("bot")
    if not bot:
        print("Unable to fetch bot instance.")
        sys.exit(1)

    async with client:
        await client.start(bot_token=TOKEN) # type: ignore
        while True:
            await asyncio.sleep(60)
            # проверка каждую минуту

            # вытягиваем записи где дата <= текущая+10мин
            query = """
            SELECT * FROM notes WHERE reminder_time <= (now()::timestamp + INTERVAL '10 min')::timestamp;
            """

            res = await sql.fetch(query)
            if not res:
                continue
            for record in res:
                serialized = dict(record)
                if serialized['processed']:
                    continue
                uid = serialized["user_id"]

                user_query = "SELECT * FROM users WHERE id = $1"
                user = await sql.fetchrow(user_query, uid)
                if not user:
                    continue
                user = dict(user)
                chat_id: int = user["telegram_id"]
                reminder_time: datetime = serialized["reminder_time"]
                to_timezone = reminder_time.astimezone(timezone("Europe/Moscow"))
                text: str = serialized["text"]

                result_text = f"Напоминание о заметке назначенной на {to_timezone}. Текст Вашей заметки: {text}"

                await client.send_message(chat_id, result_text)
                # здесь я отошел от поставленных требований и добавил лишнее bool поле в таблицу notes.
                # заявка помечается как обработанная, таким образом уведомление никогда не придет дважды.
                set_processed_query = "UPDATE notes SET processed = true WHERE id = $1"
                await sql.exec(set_processed_query, serialized['id'])

async def main() -> None:
    sql = PostgresInterface(log.debug)
    await sql.init_db()

    # UserManager это обертка вокруг таблицы с пользователями в базе данных
    user_manager = UserManager(sql, log.debug)
    await user_manager.create()

    # бот может использовать локальный bot-api сервер если LOCAL_API=1
    if getenv("LOCAL_API"):
        session = AiohttpSession(api=TelegramAPIServer.from_base("http://127.0.0.1:81"))
        bot = Bot(
            token=TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            session=session,
        )
    else:
        bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    dp = Dispatcher(storage=storage)

    # Мидлварь отслеживает взаимодействия с ботом и вносит данные в базу данных
    dp.update.outer_middleware(
        user_middleware.StructLoggingMiddleware(user_manager, log)
    )

    # watcher будет отслеживать добавление бота в группы
    # если бот был добавлен в группу он автоматически из нее выйдет
    watcher = MemberWatch(
        log=log,
        bot=bot,
        user_manager=user_manager,
        redis=r,
    )

    # префикс с которого будет начинаться команда в боте (/start)
    prefix = getenv("COMMAND_PREFIX") or "/"
    # инъекция зависимостей в плагины
    payload = {
        "dp": dp,
        "sql": sql,
        "debug": log.debug,
        "bot": bot,
        "redis": r,
        "prefix": prefix,
        "user_manager": user_manager,
    }
    plugin_list = plugins.init_plugins(payload)

    asyncio.create_task(check_pending_notes(payload))
    dp.include_router(watcher.router)

    await bot.delete_webhook(True)
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    uvloop.run(main())
