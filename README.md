# Stocker

Stocker is a Telegram bot that provides real-time stock price updates. It fetches data from financial APIs and sends periodic updates to a specified Telegram channel.

## 🚀 Tech Stack
*   **Language/Framework:** Python 3.10
*   **Database:** PostgreSQL
*   **Cache & In-Memory Store:** Redis
*   **Other Key Tools:** Docker, SQLAlchemy, Alembic, python-telegram-bot, APScheduler

## 📋 Prerequisites
*   Docker & Docker Compose
*   Python 3.10+

## 🛠️ Local Development Setup

### 1. Clone the repository
```bash
git clone https://github.com/your-username/stocker.git
cd stocker
```

### 2. Environment Configuration
Create a `.env` file in the root directory by copying the `.env.example` file.

```bash
cp .env.example .env
```

Update the `.env` file with your specific configurations:
*   `API_TOKEN`: Your Telegram Bot API token.
*   `CHANNEL_ID`: The ID of the Telegram channel where the bot will send messages.
*   `FINANCIAL_API_KEY`: Your API key for the financial data provider (e.g., Alpha Vantage).
*   `SUPER_ADMIN_TELEGRAM_ID`: The Telegram User ID of the super admin, who can grant admin rights.
*   `DATABASE_URL`: The connection string for your PostgreSQL database (e.g., `postgresql://user:password@localhost/stocker`).
*   `REDIS_URL`: The connection string for your Redis instance (e.g., `redis://localhost`).
*   `LOG_LEVEL`: (Optional) The logging level for the bot (e.g., DEBUG, INFO, WARNING, ERROR). Defaults to INFO.

### 3. Installation & Running

#### With Docker (Recommended)
This is the easiest way to get started, as it will spin up the bot, a PostgreSQL database, and a Redis instance for you.

1.  **Build and Run:**
    ```bash
    docker-compose up --build
    ```
2.  **Apply Database Migrations (First time only):**
    In a separate terminal, run:
    ```bash
    docker exec -it stocker_bot alembic upgrade head
    ```

#### Without Docker
1.  **Install dependencies:**
    ```bash
    pip install -r requirements-dev.txt
    ```
2.  **Set up the database:**
    Ensure you have a running PostgreSQL server. Then, apply the database migrations:
    ```bash
    alembic upgrade head
    ```
3.  **Run the bot:**
    ```bash
    python -m src.main
    ```

## 📊 Logging
The bot is configured to output structured JSON logs to the console using `pythonjsonlogger`. This is designed for easy integration with log aggregation tools (e.g., ELK stack, AWS CloudWatch). You may see JSON objects in your terminal instead of plain text during local development. You can adjust the verbosity by changing the `LOG_LEVEL` in your `.env` file.

## 💬 Usage
*   `/start` - Starts the bot and displays a welcome message.
*   `/update` - (Admin only) Manually triggers a price update.
*   `/set_symbol [SYMBOL]` - (Admin only) Sets the stock symbol to track. If used without an argument, starts an interactive prompt that times out after 60 seconds.
*   `/set_timer [minutes]` - (Admin only) Sets the timer interval for price updates (maximum 1440 minutes / 24 hours). If used without an argument, starts an interactive prompt that times out after 60 seconds.
*   `/config_status` - (Admin only) Displays the current settings for the symbol and timer.
*   `/grant_admin <user_id>` - (Super Admin only) Grants admin privileges to a user. **Note:** The target user must have interacted with the bot at least once (e.g., by sending `/start`) to be registered in the database before they can be granted admin rights.
*   `/cancel` - Cancels an ongoing conversation (e.g., after using `/set_symbol` without an argument).

## 🧪 Testing
To run the automated tests, first install the development dependencies:

```bash
pip install -r requirements-dev.txt
```

Then, run pytest from the root directory:

```bash
pytest
```

## 🏗️ Project Structure
```
.
├── .github/            # GitHub Actions workflows
├── alembic/            # Alembic database migration scripts
├── docs/               # Project documentation
├── src/                # Source code
│   ├── bot/            # Telegram bot handlers
│   ├── providers/      # Financial data providers
│   ├── services/       # Business logic services
│   ├── config.py       # Configuration loading
│   ├── database.py     # Database session management
│   ├── main.py         # Application entry point
│   └── models.py       # SQLAlchemy data models
├── tests/              # Test files
├── .env.example        # Example environment variables
├── alembic.ini         # Alembic configuration
├── Dockerfile          # Docker configuration
├── requirements.txt    # Python production dependencies
└── requirements-dev.txt # Python development dependencies
```

## 🤝 Contributing
Before submitting a pull request, please ensure your code is formatted and linted according to the project's standards.
