# Comprehensive Project Guide: From Zero to Production

This guide provides a complete, step-by-step walkthrough for setting up, running, testing, and deploying the Stocker project. It is designed to be clear enough for users with a basic understanding of the command line.

### Deployment Strategy: Cloud-First, Local-Ready

This project is architected around Docker containers, making it highly portable. The primary and recommended deployment path is a **cloud-based Virtual Private Server (VPS)**, which ensures 24/7 availability and high performance. This guide focuses on that path.

However, the same Docker-based setup can be used on a local home server (like an N100 Mini PC) with almost no changes. The core steps of cloning the repository, setting up the `.env` file, and running `docker-compose` remain the same regardless of the environment.

## Part 1: Initial Environment Setup (The "Zero")

This section covers how to get a clean development environment ready on your local machine.

### 1.1. Core Dependencies

Before you begin, you need to install the following tools on your system. Please follow the official installation instructions for your operating system.

*   **Git:** For version control. We'll use it to download the code.
    *   [Official Guide](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
*   **Python:** We use Python 3.10 or higher.
    *   [Official Website](https://www.python.org/downloads/)
*   **Docker & Docker Compose:** This is the most critical piece. It allows us to run the application and its database/cache services in isolated containers. It is **highly recommended** to install **Docker Desktop** for your OS, as it includes both Docker and Docker Compose.
    *   [Official Guide](https://docs.docker.com/get-docker/)

### 1.2. Cloning the Repository

Once the core dependencies are installed, open your terminal, navigate to a directory where you want to store the project, and run the following commands to download the code and enter the project folder.

```bash
git clone https://github.com/your-username/stocker.git
cd stocker
```

### 1.3. Acquiring Secrets and IDs

Before we can run the project, we need to gather some essential credentials. 

1.  **Telegram Bot Token (`API_TOKEN`):**
    *   Open Telegram and search for the user `BotFather` (it has a blue checkmark).
    *   Start a chat and type `/newbot`.
    *   Follow the prompts. Give your bot a name and a username.
    *   `BotFather` will reply with a long string of characters. This is your `API_TOKEN`. Copy it.

2.  **Channel ID (`CHANNEL_ID`):
    *   Create a new **public** Telegram channel.
    *   The channel ID is simply its username, including the `@` symbol (e.g., `@my_stocker_channel`).

3.  **Super Admin Telegram ID (`SUPER_ADMIN_TELEGRAM_ID`):
    *   On your Telegram app, search for the bot `@userinfobot`.
    *   Start a chat with it.
    *   It will immediately reply with your account information. Copy the number next to `Id:`. This is your **purely numeric** User ID.

4.  **Financial API Key (`FINANCIAL_API_KEY`):
    *   This project is configured to use [Alpha Vantage](https://www.alphavantage.co/).
    *   Go to their website and claim your free API key.

### 1.4. Environment Configuration

Now we will create a `.env` file to securely store the credentials we just gathered.

1.  **Create the `.env` file:**
    In your terminal, at the root of the `stocker` project, run:
    ```bash
    cp .env.example .env
    ```

2.  **Edit the `.env` file:**
    Open the newly created `.env` file with any text editor and paste the values you copied.

    ```dotenv
    API_TOKEN="PASTE_YOUR_TELEGRAM_BOT_TOKEN_HERE"
    CHANNEL_ID="@your_channel_name"
    FINANCIAL_API_KEY="PASTE_YOUR_ALPHA_VANTAGE_KEY_HERE"
    SUPER_ADMIN_TELEGRAM_ID="PASTE_YOUR_TELEGRAM_ID_HERE"

    # These values are pre-configured for the docker-compose setup. Do not change them for local development.
    DATABASE_URL="postgresql://user:password@db:5432/stocker"
    REDIS_URL="redis://redis:6379"

    # Optional: Logging Configuration
    # LOG_LEVEL="INFO" # e.g., DEBUG, INFO, WARNING, ERROR
    ```

    **A Note on `LOG_LEVEL`:**
    *   **For Production (on a VPS):** It is recommended to set `LOG_LEVEL="INFO"`. This provides a good balance of information, showing routine operations as well as any warnings or errors, without being cluttered by excessive debug messages.
    *   **For Development (on your local machine):** If you are debugging an issue, you can set `LOG_LEVEL="DEBUG"` to get the most detailed output possible. If left unset, the application defaults to `INFO`.

**At this point, your local environment is fully configured.**

---

## Part 2: Running the Project with Docker (The "50")

This is the **recommended** way to run the project. It ensures that the application, database, and cache all run in a consistent, isolated environment.

### 2.1. Building and Running the Services

With Docker Desktop running on your machine, navigate to the root of the project directory and run:

```bash
docker-compose up --build
```

*   **What's happening?**
    *   `--build`: Docker Compose reads the `Dockerfile`, builds your Python application into a container image, and also downloads the official images for PostgreSQL and Redis.
    *   `up`: It then starts three containers based on these images and connects them to a shared virtual network.
*   **Expected Output:** You will see a stream of logs from all three services (`db`, `redis`, and `bot`). Wait until the log output stabilizes. You might see some database initialization messages.

### 2.2. Applying Database Migrations (First Time Only)

The first time you start the services, the `db` container creates an empty database. You need to apply our project's database schema to it.

1.  **Open a new terminal window** (leave the `docker-compose` one running).
2.  **List the running containers** to find the name of your bot container. It is usually `stocker_bot`.
    ```bash
    docker ps
    ```
3.  **Execute the `alembic upgrade head` command** inside the running bot container. Replace `stocker_bot` with the actual name if it's different.
    ```bash
    docker exec -it stocker_bot alembic upgrade head
    ```
    *   **What's happening?**
        *   `docker exec -it`: This command allows you to run a command inside a running container.
        *   `/usr/local/bin/alembic upgrade head`: Inside the container, we execute the `alembic` tool using its absolute path, telling it to apply all available migration scripts.
    *   **Expected Output:** You should see logs from Alembic indicating that it's running the migration and applying the changes.

    > **Deep Dive: Database vs. Table Creation**
    > You might wonder where the `CREATE TABLE` SQL code is. This is a key concept:
    > 1.  **Docker Compose creates the *database***: The `db` service in `docker-compose.yml` starts the PostgreSQL software and, based on the environment variables, creates an empty database named `stocker`.
    > 2.  **Alembic creates the *tables***: The `alembic upgrade head` command is what actually creates the `users` table *inside* the `stocker` database. It does this by reading the Python code in `src/models.py` and executing the migration script in `alembic/versions/`.

### 2.3. Granting First Admin Privileges

Now that the bot is running and the database is set up, you need to grant your own user admin rights.

1.  **Find your bot on Telegram** and send it a message (any message, like `/start`). This action registers your user in the database.
2.  **Use the `/grant_admin` command:** As the Super Admin (defined in your `.env` file), you can now grant admin rights. Send this command to your bot:
    ```
    /grant_admin YOUR_TELEGRAM_USER_ID
    ```
    (Replace `YOUR_TELEGRAM_USER_ID` with the same **numeric ID** you put in the `SUPER_ADMIN_TELEGRAM_ID` variable).
3.  The bot should reply confirming that admin privileges have been granted.

**Your application is now fully running, configured, and ready to use.** You can now use the admin-only commands like `/update` and `/set_symbol`.

### 2.4. Stopping the Services

To stop all the running services, press `Ctrl+C` in the terminal where `docker-compose up` is running. To remove the containers and the network, you can run:

```bash
docker-compose down
```

---

## Part 3: Deploying to a VPS (The "100")

Deploying to a Virtual Private Server (VPS) follows almost the exact same steps as running locally, which is the power of Docker.

### 3.1. Server Preparation

1.  **Provision a VPS:** Get a new server from a cloud provider (e.g., DigitalOcean, Linode, AWS EC2).
2.  **Install Docker, Docker Compose, and Git:** Follow official guides to install these three tools on your server.

### 3.2. Deployment Steps

1.  **SSH into your VPS.**
2.  **Clone the repository.**
3.  **Create and configure the `.env` file** with your production secrets, just as you did locally.
4.  **Run the Application in Detached Mode:**
    ```bash
    docker-compose up --build -d
    ```
    *   `-d`: This crucial flag runs the containers in **detached mode**, meaning they will continue to run in the background after you log out.
5.  **Apply Database Migrations:**
    ```bash
    docker exec -it stocker_bot alembic upgrade head
    ```

### 3.3. Managing the Live Application

*   **To view logs:** `docker-compose logs -f`
*   **To stop services:** `docker-compose down`
*   **To update the application:** Pull the latest code (`git pull`) and then run `docker-compose up --build -d` again. Docker will recreate only the services that have changed.

---

## Appendix A: Understanding GitHub Actions

We have a Continuous Integration (CI) pipeline configured in `.github/workflows/ci.yml`. This pipeline acts as an automated quality gate whenever you push code.

It automatically performs: **Dependency Installation**, **Linting**, **Testing**, **Security Scanning**, and **Docker Build Validation**.

As a developer, your workflow is:
1.  Create a new branch for your feature.
2.  Push your code to GitHub.
3.  Open a Pull Request.
4.  Check for a **green checkmark** on the Pull Request page, indicating all automated checks have passed.
5.  Merge your code.

This process ensures that the `main` branch always remains stable and high-quality.

---

## Appendix C: Debugging Tips

### Running Services Independently

Sometimes, you may want to run only the database and cache without starting the bot application, for example, to test database migrations locally. You can do this with Docker Compose.

1.  **Start only the infrastructure services:**
    ```bash
    docker-compose up -d db redis
    ```
    This command will start the PostgreSQL and Redis containers in the background, making them available on `localhost:5432` and `localhost:6379` respectively.

2.  **Run Migrations Locally:**
    Now that the database is running, you can run `alembic` from your local machine (as long as you have installed the dependencies with `pip install -r requirements-dev.txt`).
    ```bash
    # Ensure your .env file is configured to point to localhost
    # DATABASE_URL="postgresql://user:password@localhost:5432/stocker"

    # Run alembic locally
    python -m alembic upgrade head
    ```
    This is an excellent way to test that your migration scripts work correctly against a real database without needing to run the main bot application.

### How to Safely Reset the Database

Sometimes in development, you might want to completely wipe your database and start from scratch. **Do not** do this by manually dropping tables in a GUI client. The correct and safest way is to use Docker Compose.

1.  **Stop and Remove All Services:**
    First, you must stop and remove the containers. This releases the lock on the volume.
    ```bash
    docker-compose down
    ```
2.  **Remove the Database Volume:**
    Now that the volume is no longer in use, you can safely delete it. This command permanently deletes all database data.
    ```bash
    docker volume rm stocker_postgres_data
    ```
    *(Note: `stocker_` is a prefix based on your project's directory name and may vary slightly.)*

3.  **Restart Services:**
    ```bash
    docker-compose up --build -d
    ```
    Docker will now create a fresh, empty volume, and PostgreSQL will initialize a brand new, empty `stocker` database.

4.  **Re-apply Migrations:**
    You now have a clean database and must run the migration command again to create the tables.
    ```bash
    docker exec -it stocker_bot alembic upgrade head
    ```

---

## Appendix B: Inspecting the Database

Knowing how to look inside your database is crucial for development and debugging. Here are two methods to inspect the PostgreSQL database running in your Docker container.

### Method 1: Using the Command-Line (psql)

This method is direct but requires comfort with the command line.

1.  **Ensure services are running:** `docker-compose up`
2.  **Open a new terminal.**
3.  **Enter the database container:**
    ```bash
    docker exec -it stocker_db bash
    ```
4.  **Connect to the database using psql:**
    Inside the container's shell, connect to the `stocker` database as the `user` user.
    ```bash
    psql -U user -d stocker
    ```
5.  **Run SQL commands:** You are now in the psql interactive terminal.
    *   List all tables: `\dt`
    *   Describe the users table: `\d users`
    *   Select all data from the users table: `SELECT * FROM users;`
    *   Exit psql: `\q`
6.  **Exit the container shell:** `exit`

### Method 2: Using a GUI Client (DBeaver)

This method is highly recommended for beginners as it's much more visual.

1.  **Ensure services are running.** The `ports: - "5432:5432"` line in `docker-compose.yml` is essential as it exposes the database to your local machine.
2.  **Download and install** a database client like [DBeaver](https://dbeaver.io/).
3.  **Create a New Connection:**
    *   Open DBeaver and click the "New Database Connection" icon.
    *   Select **PostgreSQL**.
    *   In the connection settings, fill in the following:
        *   **Host:** `localhost`
        *   **Port:** `5432`
        *   **Database:** `stocker`
        *   **Username:** `user`
        *   **Password:** `password` (These values come from `docker-compose.yml`)
4.  **Test and Save:** Click "Test Connection". If successful, save the connection.
5.  **Browse Data:** In the Database Navigator panel, expand your new connection, then navigate through `stocker` > `Schemas` > `public` > `Tables`. Double-click the `users` table to view its data in a spreadsheet-like interface.
