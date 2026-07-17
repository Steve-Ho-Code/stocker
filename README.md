# Stocker

Stocker is a Telegram bot that sends stock and ETF price updates to a Telegram channel. It supports manual updates, scheduled updates on wall-clock boundaries, admin-only configuration commands, Redis-backed runtime settings, and PostgreSQL-backed user/admin records.

## Tech Stack

* **Language:** Python 3.10+
* **Bot framework:** python-telegram-bot
* **Scheduling:** APScheduler
* **Database:** PostgreSQL, SQLAlchemy, Alembic
* **Cache and runtime settings:** Redis
* **Deployment:** Docker and Docker Compose

## Prerequisites

* Docker and Docker Compose for the recommended setup.
* Python 3.10+ for local development without Docker.
* A Telegram bot token from BotFather.
* A Telegram channel or chat where the bot can send messages.
* A Finnhub or Alpha Vantage API key.

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/your-username/stocker.git
cd stocker
```

### 2. Create your environment file

Copy the example file and fill in the required values:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

At minimum, set `API_TOKEN`, `CHANNEL_ID`, `SUPER_ADMIN_TELEGRAM_ID`, and the API key for the provider selected by `ACTIVE_PROVIDER`.

### 3. Run with Docker

Docker Compose starts the bot, PostgreSQL, and Redis:

```bash
docker compose up --build
```

Apply database migrations the first time you start a new database:

```bash
docker exec -it stocker_bot alembic upgrade head
```

### 4. Synchronize the Telegram command menu

After deployment, synchronize the visible command menu manually:

```bash
docker compose exec bot python -m src.scripts.sync_bot_commands
```

When command definitions have changed, rebuild the image before synchronizing:

```bash
docker compose up -d --build
docker compose exec bot python -m src.scripts.sync_bot_commands
```

The synchronization is intentionally separate from normal bot startup and the
Docker command, so container restarts do not make unnecessary Telegram API
requests. Run it only after deployment or after changing command definitions.

### 5. Run without Docker

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

Ensure PostgreSQL and Redis are running, then update `DATABASE_URL` and `REDIS_URL` in `.env` for your local services.

Apply migrations:

```bash
alembic upgrade head
```

Start the bot:

```bash
python -m src.main
```

## Configuration

Static startup configuration is loaded from environment variables, including `.env`. Runtime settings such as the tracked symbol and schedule values are persisted in Redis after they are changed through bot commands. On startup, Redis values override environment defaults when present.

| Variable | Required | Description |
| --- | --- | --- |
| `API_TOKEN` | Yes | Telegram Bot API token. |
| `CHANNEL_ID` | Yes | Telegram channel username or chat ID where scheduled updates are sent. |
| `SUPER_ADMIN_TELEGRAM_ID` | Yes | Telegram user ID allowed to grant admin rights. |
| `FINNHUB_API_KEY` | Provider-dependent | Finnhub API key. Required when `ACTIVE_PROVIDER=finnhub`. |
| `ALPHA_VANTAGE_API_KEY` | Provider-dependent | Alpha Vantage API key. Required when `ACTIVE_PROVIDER=alpha_vantage`. |
| `ACTIVE_PROVIDER` | No | Price provider. Supported values are `finnhub` and `alpha_vantage`. Defaults to `finnhub`. |
| `DATABASE_URL` | No | PostgreSQL connection string. The Docker default is `postgresql://user:password@db:5432/stocker`. |
| `REDIS_URL` | No | Redis connection string. The Docker default is `redis://redis:6379`. |
| `SCHEDULE_FREQUENCY_MINUTES` | No | Startup default for scheduled update frequency. Supported values are `1`, `5`, `10`, `15`, `30`, and `60`. Defaults to `1`. |
| `SCHEDULE_START_TIME` | No | Startup default for the daily active window start in `HH:MM` format. Defaults to `00:00`. |
| `SCHEDULE_END_TIME` | No | Startup default for the daily active window end in `HH:MM` format. Defaults to `23:59`. |
| `SCHEDULE_TIMEZONE` | No | IANA timezone used for schedule evaluation. Defaults to `America/New_York`. |
| `LOG_LEVEL` | No | Logging level such as `DEBUG`, `INFO`, `WARNING`, or `ERROR`. Defaults to `INFO`. |

`TIMER_INTERVAL` is still accepted as a legacy startup setting in seconds when `SCHEDULE_FREQUENCY_MINUTES` is not set. New deployments should use `SCHEDULE_FREQUENCY_MINUTES`.

## Scheduling

Scheduled updates run on exact wall-clock boundaries instead of drifting from application startup time. For example, a 15-minute frequency triggers at `00`, `15`, `30`, and `45` minutes past the hour.

The schedule has three parts:

* Frequency: `1`, `5`, `10`, `15`, `30`, or `60` minutes.
* Daily active window: `SCHEDULE_START_TIME` through `SCHEDULE_END_TIME`.
* Timezone: an IANA timezone such as `America/New_York`, `Asia/Hong_Kong`, or `UTC`.

Manual `/update` commands are not restricted by the schedule window.

## Bot Commands

| Command | Access | Description |
| --- | --- | --- |
| `/start` | Anyone | Registers the user if needed and shows the current tracked symbol and schedule frequency. |
| `/update` | Admin | Sends a price update immediately. |
| `/set_symbol [SYMBOL]` | Admin | Updates the tracked symbol. Without an argument, starts an interactive prompt. |
| `/set_timer [minutes]` | Admin | Updates scheduled update frequency. Supported values are `1`, `5`, `10`, `15`, `30`, and `60`. Without an argument, starts an interactive prompt. |
| `/set_schedule_window <START_HH:MM> <END_HH:MM>` | Admin | Updates the daily active window for scheduled updates. Overnight windows are supported. |
| `/set_schedule_timezone <IANA_TIMEZONE>` | Admin | Updates the timezone used by scheduled updates. |
| `/config_status` | Admin | Shows the current symbol, frequency, schedule window, and timezone. |
| `/grant_admin <user_id>` | Super admin | Grants admin privileges to a registered user. The target user must run `/start` at least once first. |
| `/cancel` | Anyone in prompt | Cancels an active interactive prompt. |

`/grant_admin` and `/cancel` remain available to their existing handlers but are
intentionally excluded from Telegram's visible command menu.

## Logging

The bot writes structured JSON logs to stdout using `python-json-logger`.
Credential-bearing query parameters and configured secrets are redacted before
output. Change `LOG_LEVEL` in `.env` to adjust verbosity.

## Testing

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

Run the test suite:

```bash
pytest
```

## Project Structure

```text
.
|-- .env.example          # Example environment variables
|-- alembic/              # Alembic migration scripts
|-- docs/                 # Project documentation, specs, plans, and reviews
|-- src/
|   |-- bot/              # Telegram handlers and command-menu definitions
|   |-- providers/        # Financial data providers
|   |-- scripts/          # Manually executed maintenance scripts
|   |-- services/         # Settings and scheduling services
|   |-- config.py         # Configuration loading and Redis-backed settings
|   |-- database.py       # Database session setup
|   |-- logging_config.py # JSON logging and credential redaction
|   |-- main.py           # Application entry point
|   `-- models.py         # SQLAlchemy models
|-- tests/                # Automated tests
|-- Dockerfile
|-- docker-compose.yml
|-- requirements.txt      # Production dependencies
`-- requirements-dev.txt  # Development and test dependencies
```

## Contributing

Before submitting a pull request, run the test suite and keep documentation in sync with command, configuration, and deployment changes.
