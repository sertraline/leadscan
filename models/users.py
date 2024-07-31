from asyncio import get_event_loop
from .basemodel import BaseModel
from .postgres import PostgresInterface
from typing import Callable, Optional
import asyncpg
import json


class UserAnonymous:
    pass


class User:

    def __init__(self, sql: PostgresInterface, data: dict, user_manager: "UserManager"):
        super().__init__()
        self.sql = sql
        # id отвечает id записи в базе данных
        self._id = data["id"]
        # telegram_id соответствует id пользователя в телеграме
        self._telegram_id = data["telegram_id"]
        self._username = data["username"]
        self._name = data["name"].strip()
        self._email = data["email"]
        self.user_manager = user_manager

    def set_column(self, col, value):
        get_event_loop().run_until_complete(
            self.sql.exec(
                f"""
            UPDATE users SET {col} = $1
        """,
                value,
            )
        )

    def __repr__(self):
        self.__str__()

    def __str__(self):
        return str(
            ["Instance of User", self.id, self.telegram_id, self.username, self.email]
        )

    @property
    def id(self):
        return self._id

    @property
    def telegram_id(self):
        return self._telegram_id

    @property
    def username(self):
        return self._username

    @username.setter
    def username(self, value):
        self.set_column("username", value)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self.set_column("name", value)

    @property
    def email(self):
        return self._email

    @email.setter
    def email(self, value):
        self.set_column("email", value)


class UserManager(BaseModel):

    def __init__(self, sql: PostgresInterface, debug: Callable):
        super().__init__()
        self.sql = sql
        self.debug = debug

    async def _init_table(self):
        await self.sql.exec(
            """
        CREATE TABLE IF NOT EXISTS users (
            id                  SERIAL PRIMARY KEY,
            telegram_id         BIGINT NOT NULL UNIQUE,
            username            VARCHAR DEFAULT '',
            name                VARCHAR(255) NOT NULL,
            email               VARCHAR(255)
        );

        CREATE TABLE IF NOT EXISTS notes (
            id                  SERIAL PRIMARY KEY,
            user_id             INTEGER NOT NULL,
            text                TEXT,
            processed           BOOL DEFAULT false,
            reminder_time       TIMESTAMP WITH TIME ZONE NOT NULL,
            CONSTRAINT notes_user_fk
                FOREIGN KEY(user_id)
                REFERENCES users(id)
        );

        CREATE INDEX IF NOT EXISTS i_users
        ON users(telegram_id, name, email);

        CREATE INDEX IF NOT EXISTS i_notes
        ON notes(user_id, reminder_time);
        """
        )

    async def user_entry(
        self,
        username: Optional[str],
        telegram_id: int,
        name: str,
    ) -> User | UserAnonymous:
        res = await self.sql.fetch(
            """
            WITH ins1 AS (
                INSERT INTO users(telegram_id, username, name)
                VALUES ($1, $2, $3)
                ON CONFLICT (telegram_id) DO UPDATE SET
                username = $2, name = $3
                RETURNING id, telegram_id, username, name, email
            )
            SELECT * from ins1
        """,
            telegram_id,
            username,
            name,
        )

        d = {
            'uid': telegram_id,
            'username': username,
            'name': name
        }
        self.debug(
            (
                json.dumps(d, sort_keys=True, indent=4, ensure_ascii=False).encode(
                    "utf-8"
                )
            ).decode("utf-8")
        )

        if len(res) > 0:
            return User(self.sql, dict(res[0]), self)
        else:
            return UserAnonymous()

    async def get_user(self, telegram_id: int) -> User | UserAnonymous:
        user = None
        conn: asyncpg.pool.Pool
        async with self.sql.pool.acquire() as conn:  # type: ignore
            user = await conn.fetchrow(
                """
                SELECT *  
                FROM users WHERE telegram_id = $1
            """,
                telegram_id,
            )
        if not user:
            return UserAnonymous()
        return User(self.sql, dict(user), self)

    async def find_user_by_username(self, username: str) -> User | UserAnonymous:
        conn: asyncpg.pool.Pool
        async with self.sql.pool.acquire() as conn:  # type: ignore
            user = await conn.fetchrow(
                """
                SELECT * FROM users WHERE username LIKE $1
            """,
                f"%{username}%",
            )
            if not user:
                return UserAnonymous()
            return User(self.sql, dict(user), self)
