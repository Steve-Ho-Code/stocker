# Stocker - Project Context

## Project Overview

Stocker is a Python-based Telegram bot designed to provide real-time stock price updates. It fetches financial data from external APIs and sends periodic updates to a designated Telegram channel. 

**Key Technologies & Architecture:**
*   **Language:** Python 3.10
*   **Core Frameworks:** `python-telegram-bot` for Telegram integration, `APScheduler` for scheduling tasks.
*   **Database:** PostgreSQL, accessed via SQLAlchemy (ORM) and Alembic for migrations.
*   **Cache:** Redis.
*   **Infrastructure:** Docker & Docker Compose are used for containerization and local development orchestration.
*   **Structure:** Source code is organized within the `src/` directory, separated into logical modules (`bot`, `providers`, `services`). Tests are located in the `tests/` directory.

## Building and Running

The project relies heavily on Docker for a streamlined development experience.

*   **Environment Setup:** Requires a `.env` file in the root directory (copy from `.env.example`).
*   **Run via Docker (Recommended):**
    ```bash
    docker-compose up --build
    ```
*   **Run Database Migrations (First time setup):**
    When running via Docker, execute the migration within the bot's container:
    ```bash
    docker exec -it stocker_bot alembic upgrade head
    ```
    *(If running locally without Docker, run `alembic upgrade head` directly).*
*   **Run Locally (Without Docker):**
    Ensure PostgreSQL and Redis are running, dependencies are installed (`pip install -r requirements-dev.txt`), and then start the application module:
    ```bash
    python -m src.main
    ```

## Testing

The project uses `pytest` for testing. The configuration is set up to automatically add the `src` directory to the Python path.

*   **Run Tests:**
    ```bash
    pytest
    ```

## Development Conventions

*   **Logging:** The application uses structured JSON logging via `pythonjsonlogger`. This is designed for log aggregation but means local console output will be in JSON format. Verbosity is controlled via the `LOG_LEVEL` environment variable.
*   **Configuration:** Handled primarily through environment variables mapped via `src/config.py`.
*   **Code Quality:** Contributors are expected to format and lint their code before submitting PRs.
*   **Database:** All schema changes must be accompanied by an Alembic migration script.
