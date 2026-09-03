# AnjurXBot

Telegram group protection and moderation bot powered by aiogram 3, Firebase Firestore, and Render Background Worker.

## Features

- Force Subscribe with multiple channels
- Guard: anti-spam, anti-flood, anti-link, anti-advertisement, anti-repeat
- Bad-word and new-member protection
- Warning and moderation history
- Aggregate and daily statistics
- Inline admin panel and setup wizard
- Permission checks, callback security, rate limiting, and TTL caches

## Installation

```bash
git clone https://github.com/muhammadmirzoasqarov41-ai/anjurxbot.git
cd anjurxbot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` with real values. Never commit `.env`, Firebase JSON files, or tokens.

Required environment variables:

```env
BOT_TOKEN=
ADMIN_IDS=
FIREBASE_PROJECT_ID=
FIREBASE_PRIVATE_KEY_ID=
FIREBASE_PRIVATE_KEY=
FIREBASE_CLIENT_EMAIL=
FIREBASE_CLIENT_ID=
FIREBASE_CLIENT_X509_CERT_URL=
LOG_LEVEL=INFO
TIMEZONE=Asia/Tashkent
```

`FIREBASE_PRIVATE_KEY` may contain literal `\\n`; the application converts those sequences to newlines. Optional rate-limit variables are documented in `.env.example`.

## Run

```bash
python main.py
```

Do not run a local polling instance while the Render production worker is running, because Telegram allows only one active polling consumer for a bot token.

## Commands

General:

- `/start` — start the bot
- `/help` — usage help

Group administrator commands:

- `/setup` — verify bot status and permissions
- `/panel` — open the inline admin panel
- `/guard` — manage Guard
- `/fsub` — manage Force Subscribe
- `/stats` — view group statistics
- `/clearwarns` — clear warnings for a replied-to user or numeric user ID

## Render deployment

Create a **Background Worker** connected to this repository.

- Build command: `pip install -r requirements.txt`
- Start command: `python main.py`
- Python version: `3.11.9` (configured in `render.yaml`)

Set these variables in the Render dashboard only:

```text
BOT_TOKEN
ADMIN_IDS
FIREBASE_PROJECT_ID
FIREBASE_PRIVATE_KEY_ID
FIREBASE_PRIVATE_KEY
FIREBASE_CLIENT_EMAIL
FIREBASE_CLIENT_ID
FIREBASE_CLIENT_X509_CERT_URL
LOG_LEVEL
TIMEZONE
```

Never place real values in `README.md`, `render.yaml`, `.env.example`, source code, or logs.

## Verification before deployment

```bash
python -m compileall main.py app
pytest -q  # when a test suite is present
python main.py
```

The startup command requires valid environment variables and network access to Telegram and Firebase.
