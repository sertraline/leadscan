import asyncpg
import traceback
from typing import Callable, Any
from os import getenv


class PostgresInterface:

    def __init__(self, debug: Callable):
        self.debug = debug

    async def init_db(self):
        auth = f"{getenv('POSTGRESQL_USERNAME')}:{getenv('POSTGRESQL_PASSWORD')}@{getenv('POSTGRESQL_HOST')}:{getenv('POSTGRESQL_WRITE_PORT')}"
        try:
            self.pool = await asyncpg.create_pool(
                f"postgresql://{auth}/{getenv('POSTGRESQL_DATABASE')}"
            )
        except ConnectionRefusedError as e:
            self.debug(traceback.format_exc())
            print(e)
            exit(1)
        self.debug("PG CONNECT")

    async def exec(self, query, *args):
        self.debug("%s %s" % (query, str(args)[:600]))

        conn: asyncpg.pool.Pool
        async with self.pool.acquire() as conn:  # type: ignore
            await conn.execute(query, *args)

    async def fetch(self, query, *args) -> list[Any]:
        self.debug("%s %s" % (query, str(args)[:600]))

        conn: asyncpg.pool.Pool
        async with self.pool.acquire() as conn:  # type: ignore
            return await conn.fetch(query, *args)

    async def fetchrow(self, query, *args) -> Any:
        self.debug("%s %s" % (query, str(args)[:600]))

        conn: asyncpg.pool.Pool
        async with self.pool.acquire() as conn:  # type: ignore
            return await conn.fetchrow(query, *args)
