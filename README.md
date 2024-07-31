# Поднятие проекта

Для работы с telethon нужно указать API_ID и API_HASH которые можно [получить здесь.](https://my.telegram.org/apps)  
Эти переменные заполняются в .env.

1. Установить пакетный менеджер uv
   * Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   * Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
2. Создать вирт. окружение `uv venv && source .venv/bin/activate`
3. Установить зависимости `uv pip install -r requirements.txt`
4. Создать директорию для хранения БД:  
    * `mkdir -p volumes/psql-write`
    * `mkdir -p volumes/pgadmin`
5. Установить права доступа для докер контейнеров:  
   * `chown -R 1001:1001 volumes/`
   * `chown -R 5050:5050 volumes/pgadmin`
6. Создать .env окружение: `cp .env.example .env`  
7. Заполнить .env переменные
8. Поднять контейнеры: `docker compose up`

# Как работает
1. plugins определяет логику бота (заметки и регистрация)
2. models определяет логику работы с базой данных.
3. middleware делает инъекцию модели базы данных в роутер, а также отвечает за внесение входящих событий в БД.
4. member_watch - смотрит если бота добавляют в сторонние группы, в таком случае бот автоматически выходит из группы.
5. log - конфигурация логгера
6. main - инициализация aiogram и рассылка напоминаний через Telethon.

# Как зайти в админку pgadmin:
1. Зайти на http://127.0.0.1:9050/
2. Ввести логин и пароль из .env: `test@local.net @ 123`
3. ПКМ на "Servers"
4. Кликнуть на "Register" -> "Server"
