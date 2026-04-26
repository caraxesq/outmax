# Outmax Telegram Automation

Outmax is an asyncio-based Telegram communication automation system for warm outreach, follow-ups, and ongoing user conversations. It is designed for users who have previously interacted with your service, with pacing, limits, opt-out handling, and operator visibility built in.

## Features

- Multiple Telegram user accounts via Telethon session files.
- Central aiogram control bot.
- CSV recipient import with validation, deduplication, metadata, batching, and segments.
- Jinja2 template rendering with optional AI phrasing variation.
- Async queue workers with randomized delays, cooldowns, daily limits, and FloodWait handling.
- Incoming reply listeners across active accounts.
- SQLite by default with SQLAlchemy models that are PostgreSQL-ready.
- Docker Compose deployment for VPS.

## Local Setup

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m app.db.init
python -m app.main
```

Fill `.env` before starting:

- `BOT_TOKEN` from BotFather.
- `ADMIN_IDS` as comma-separated Telegram numeric IDs.
- `API_ID` and `API_HASH` from https://my.telegram.org. The control bot can start without these, but account login, sending, and reply listeners require them.

## Adding Accounts

Recommended local CLI flow:

```bash
python -m app.accounts.login
```

This creates a Telethon session under `sessions/`. You can also place existing `.session` files in `sessions/`; the app scans and registers them automatically.

The control bot supports `/add_account` if `ENABLE_BOT_LOGIN=true`. This is admin-only and does not log login codes or 2FA passwords.

## Bot Controls

The control bot uses a Russian button menu. Send `/start` once, then use the persistent buttons:

- `Статус`
- `Аккаунты`
- `Загрузить CSV`
- `Шаблон`
- `Запустить кампанию`
- `Остановить кампании`
- `Добавить аккаунт`
- `Помощь`

For `/upload_list`, send a CSV document after the command. CSV must include `user_id` or `username`; optional columns such as `name`, `niche`, `context`, and `segment` become template variables.

For `/set_template`, send the template text after the command:

```text
/set_template Привет, {{ name }}! Видел ваш интерес к {{ niche }}.
```

## Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
```

Persistent directories:

- `data/`
- `sessions/`
- `logs/`

## VPS Deploy

On the server:

```bash
git clone git@github.com:caraxesq/outmax.git
cd outmax
cp .env.example .env
nano .env
bash scripts/deploy_vps.sh
```

The deploy script runs `git pull`, creates persistent directories, and restarts Docker Compose.

## Tests

```bash
pytest
docker compose config
docker compose build
```
