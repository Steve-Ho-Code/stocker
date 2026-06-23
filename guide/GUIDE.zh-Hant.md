# 完整專案指南：從零到生產環境

本指南將提供一個完整的、步驟清晰的演練，說明如何設定、執行、測試和部署 Stocker 專案。本指南的設計旨在讓即使只有基本命令列知識的使用者也能輕鬆上手。

### 部署策略：雲端優先，本地兼容

本專案圍繞 Docker 容器進行架構，使其具有高度的可攜性。主要且推薦的部署路徑是**雲端的虛擬私人伺服器 (VPS)**，這能確保 24/7 的可用性和高效能。本指南將專注於這條路徑。

然而，同樣基於 Docker 的設定也可以幾乎無縫地應用於本地的家庭伺服器（例如一台 N100 Mini PC）。複製儲存庫、設定 `.env` 檔案和執行 `docker-compose` 的核心步驟，無論在哪種環境下都保持不變。

## 第一部分：初始環境設定 (從零開始)

本節將涵蓋如何在您的本機電腦上準備一個乾淨的開發環境。

### 1.1. 核心依賴工具

在開始之前，您需要在您的系統上安裝以下工具。請遵循您作業系統的官方安裝說明。

*   **Git:** 用於版本控制，我們將用它來下載程式碼。
    *   [官方指南](https://git-scm.com/book/zh/v2)
*   **Python:** 我們使用 Python 3.10 或更高版本。
    *   [官方網站](https://www.python.org/downloads/)
*   **Docker & Docker Compose:** 這是最關鍵的部分。它讓我們可以在隔離的容器中執行應用程式及其資料庫/快取服務。**強烈建議**為您的作業系統安裝 **Docker Desktop**，因为它同時包含了 Docker 和 Docker Compose。
    *   [官方指南](https://docs.docker.com/get-docker/)

### 1.2. 複製儲存庫

安裝完核心依賴工具後，打開您的終端機，導航到您想儲存專案的目錄，然後執行以下指令來下載程式碼並進入專案資料夾。

```bash
git clone https://github.com/your-username/stocker.git
cd stocker
```

### 1.3. 獲取密鑰與 ID

在我們執行專案之前，需要收集一些必要的憑證。

1.  **Telegram 機器人權杖 (`API_TOKEN`):**
    *   打開 Telegram 並搜尋使用者 `BotFather`（它有一個藍色勾號）。
    *   開始對話並輸入 `/newbot`。
    *   按照提示操作，為您的機器人取一個名字和一個使用者名稱。
    *   `BotFather` 將會回覆一長串字元。這就是您的 `API_TOKEN`。請複製它。

2.  **頻道 ID (`CHANNEL_ID`):
    *   建立一個新的**公開** Telegram 頻道。
    *   頻道 ID 就是它的使用者名稱，包含 `@` 符號（例如 `@my_stocker_channel`）。

3.  **超級管理員 Telegram ID (`SUPER_ADMIN_TELEGRAM_ID`):
    *   在您的 Telegram 應用程式中，搜尋機器人 `@userinfobot`。
    *   與它開始對話。
    *   它會立即回覆您的帳號資訊。請複製 `Id:` 旁邊的那一串數字。這就是您的**純數字**使用者 ID。

4.  **財經 API 金鑰 (`FINANCIAL_API_KEY`):
    *   本專案設定為使用 [Alpha Vantage](https://www.alphavantage.co/)。
    *   前往他們的網站並申請您的免費 API 金鑰。

### 1.4. 環境設定

現在我們將建立一個 `.env` 檔案，用來安全地儲存我們剛剛收集到的憑證。

1.  **建立 `.env` 檔案：**
    在您的終端機中，位於 `stocker` 專案的根目錄下，執行：
    ```bash
    cp .env.example .env
    ```

2.  **編輯 `.env` 檔案：**
    用任何文字編輯器打開新建立的 `.env` 檔案，並貼上您複製的數值。

    ```dotenv
    API_TOKEN="在這裡貼上您的TELEGRAM_BOT_TOKEN"
    CHANNEL_ID="@your_channel_name"
    FINANCIAL_API_KEY="在這裡貼上您的ALPHA_VANTAGE_KEY"
    SUPER_ADMIN_TELEGRAM_ID="在這裡貼上您的TELEGRAM_ID"

    # 以下數值已為 docker-compose 設定預先配置好。在本地開發時請勿更改。
    DATABASE_URL="postgresql://user:password@db:5432/stocker"
    REDIS_URL="redis://redis:6379"

    # 可選：日誌級別設定
    # LOG_LEVEL="INFO" # 例如：DEBUG, INFO, WARNING, ERROR
    ```

    **關於 `LOG_LEVEL` 的說明：**
    *   **生產環境 (在 VPS 上)：** 建議設定 `LOG_LEVEL="INFO"`。這能在記錄日常操作與捕捉警告/錯誤之間取得良好平衡，而不會被過多的除錯訊息淹沒。
    *   **開發環境 (在您的本機)：** 如果您正在除錯問題，可以設定 `LOG_LEVEL="DEBUG"` 以獲取最詳細的輸出。如果留空不設，應用程式將預設使用 `INFO` 級別。

**至此，您的本地環境已完全設定好。**

---

## 第二部分：使用 Docker 執行專案 (達成 50%)

這是**推薦**的執行專案的方式。它確保應用程式、資料庫和快取都在一個一致、隔離的環境中執行。

### 2.1. 建置並執行服務

在您的電腦上執行 Docker Desktop 後，導航到專案的根目錄並執行：

```bash
docker-compose up --build
```

*   **這是在做什麼？**
    *   `--build`: Docker Compose 會讀取 `Dockerfile`，將您的 Python 應用程式建置成一個容器映像，同時也會下載 PostgreSQL 和 Redis 的官方映像。
    *   `up`: 接著，它會基於這些映像啟動三個容器，並將它們連接到一個共享的虛擬網路上。
*   **預期輸出：** 您將看到來自所有三個服務（`db`, `redis`, 和 `bot`）的日誌流。請等到日誌輸出穩定下來。您可能會看到一些資料庫初始化的訊息。

### 2.2. 套用資料庫遷移 (僅限首次)

當您第一次啟動服務時，`db` 容器會建立一個空的資料庫。您需要將我們專案的資料庫綱要 (schema) 套用到它上面。

1.  **打開一個新的終端機視窗**（讓 `docker-compose` 的視窗繼續執行）。
2.  **列出執行中的容器**以找到您的機器人容器的名稱。它通常是 `stocker_bot`。
    ```bash
    docker ps
    ```
3.  **在執行中的機器人容器內執行 `alembic upgrade head` 指令**。請將 `stocker_bot` 替換為上一個指令回傳的實際名稱（如果不同的話）。
    ```bash
    docker exec -it stocker_bot alembic upgrade head
    ```
    *   **這是在做什麼？**
        *   `docker exec -it`: 這個指令讓您可以在一個執行中的容器內部執行指令。
        *   `/usr/local/bin/alembic upgrade head`: 在容器內部，我們使用 `alembic` 工具的絕對路徑，告訴它套用所有可用的遷移腳本。
    *   **預期輸出：** 您應該會看到來自 Alembic 的日誌，表示它正在執行遷移並套用變更。

    > **深入理解：建立資料庫 vs. 建立表格**
    > 您可能會好奇 `CREATE TABLE` 的 SQL 程式碼在哪裡。這是一個關鍵概念：
    > 1.  **Docker Compose 負責建立「資料庫」**：`docker-compose.yml` 中的 `db` 服務會啟動 PostgreSQL 軟體，並根據環境變數，建立一個名為 `stocker` 的**空資料庫**。
    > 2.  **Alembic 負責建立「表格」**：我們執行的 `alembic upgrade head` 指令，才是真正在 `stocker` 資料庫**內部**建立 `users` 表格的步驟。它透過讀取 `src/models.py` 中的 Python 程式碼，並執行 `alembic/versions/` 中的遷移腳本來完成這項工作。

### 2.3. 授予第一位管理員權限

現在機器人已經執行且資料庫也已設定好，您需要授予您自己的使用者管理員權限。

1.  **在 Telegram 上找到您的機器人**並發送任何訊息給它（例如 `/start`）。這個動作會在資料庫中註冊您的使用者。
2.  **使用 `/grant_admin` 指令：** 作為超級管理員（在您的 `.env` 檔案中定義的），您現在可以授予管理員權限。發送這個指令給您的機器人：
    ```
    /grant_admin YOUR_TELEGRAM_USER_ID
    ```
    （將 `YOUR_TELEGRAM_USER_ID` 替換為您填入 `SUPER_ADMIN_TELEGRAM_ID` 變數的同一個**數字 ID**）。
3.  機器人應該會回覆確認已授予管理員權限。

**您的應用程式現在已完全執行、設定好並可以使用了。** 您現在可以使用僅限管理員的指令，如 `/update` 和 `/set_symbol`。

### 2.4. 停止服務

若要停止所有執行中的服務，請在執行 `docker-compose up` 的終端機中按下 `Ctrl+C`。若要移除容器和網路，您可以執行：

```bash
docker-compose down
```

---

## 第三部分：部署到 VPS (達成 100%)

部署到虛擬私人伺服器 (VPS) 的步驟與在本地執行的步驟幾乎完全相同，這就是 Docker 的強大之處。

### 3.1. 伺服器準備

1.  **購買 VPS：** 從雲端服務提供商（例如 DigitalOcean, Linode, AWS EC2）獲取一台新的伺服器。
2.  **安裝 Docker, Docker Compose, 和 Git：** 遵循官方指南在您的伺服器上安裝這三個工具。

### 3.2. 部署步驟

1.  **透過 SSH 登入您的 VPS。**
2.  **複製儲存庫。**
3.  **建立並設定 `.env` 檔案**，填入您的生產環境密鑰，就像您在本地做的一樣。
4.  **在分離模式下執行應用程式：**
    ```bash
    docker-compose up --build -d
    ```
    *   `-d`: 這個關鍵的旗標會在**分離模式**下執行容器，這意味著在您登出後，它們將繼續在背景執行。
5.  **套用資料庫遷移：**
    ```bash
    docker exec -it stocker_bot alembic upgrade head
    ```

### 3.3. 管理線上應用程式

*   **查看日誌：** `docker-compose logs -f`
*   **停止服務：** `docker-compose down`
*   **更新應用程式：** 拉取最新的程式碼（`git pull`），然後再次執行 `docker-compose up --build -d`。Docker 只會重新建立有變更的服務。

---

## 附錄 A：理解 GitHub Actions

我們在 `.github/workflows/ci.yml` 中設定了一個持續整合 (CI) 流程。這個流程扮演著一個自動化的品質守門員的角色，在您每次推送程式碼時執行。

它會自動執行：**依賴安裝**、**程式碼風格檢查**、**測試**、**安全性掃描**和**Docker 建置驗證**。

作為開發者，您的工作流程是：
1.  為您的功能建立一個新的分支。
2.  將您的程式碼推送到 GitHub。
3.  發起一個拉取請求。
4.  在拉取請求頁面上檢查是否有一個**綠色勾號**，表示所有自動化檢查都已通過。
5.  合併您的程式碼。

這個過程確保了 `main` 分支總是保持穩定和高品質。

---

## 附錄 C：除錯技巧

### 獨立運行服務

有時候，您可能只想運行資料庫和快取而無需啟動機器人應用程式，例如，為了在本地測試資料庫遷移。您可以使用 Docker Compose 來做到這一點。

1.  **僅啟動基礎設施服務：**
    ```bash
    docker-compose up -d db redis
    ```
    這個指令會在背景啟動 PostgreSQL 和 Redis 容器，使它們分別在 `localhost:5432` 和 `localhost:6379` 上可用。

2.  **在本地執行遷移：**
    現在資料庫正在運行，您可以從您的本機電腦執行 `alembic`（前提是您已經用 `pip install -r requirements-dev.txt` 安裝了依賴）。
    ```bash
    # 確保您的 .env 檔案已設定為指向 localhost
    # DATABASE_URL="postgresql://user:password@localhost:5432/stocker"

    # 在本地執行 alembic
    python -m alembic upgrade head
    ```
    這是一個絕佳的方法，可以在無需運行主機器人應用程式的情況下，測試您的遷移腳本是否能對真實資料庫正常工作。

### 如何安全地重置資料庫

在開發過程中，有時您可能希望完全清除資料庫並從頭開始。**不要**透過圖形化介面客戶端手動 `drop table`。正確且最安全的方法是使用 Docker Compose。

1.  **停止並移除所有服務：**
    首先，您必須停止並移除容器。這會釋放對資料卷的鎖定。
    ```bash
    docker-compose down
    ```
2.  **移除資料庫資料卷：**
    現在資料卷已不再被使用，您可以安全地刪除它。這個指令會永久刪除所有的資料庫資料。
    ```bash
    docker volume rm stocker_postgres_data
    ```
    *（注意：`stocker_` 是根據您專案目錄名稱生成的前綴，可能會略有不同。）*

3.  **重新啟動服務：**
    ```bash
    docker-compose up --build -d
    ```
    Docker 現在會建立一個全新的、空的資料卷，PostgreSQL 也會因此初始化一個全新的、空的 `stocker` 資料庫。

4.  **重新套用遷移：**
    您現在有了一個乾淨的資料庫，必須再次執行遷移指令來建立表格。
    ```bash
    docker exec -it stocker_bot alembic upgrade head
    ```

---

## 附錄 B：檢查資料庫內容

學會如何查看資料庫的內部狀態，對於開發和除錯來說至關重要。這裡提供了兩種方法來檢查在您 Docker 容器中運行的 PostgreSQL 資料庫。

### 方法一：使用命令列工具 (psql)

這種方法最直接，但需要對命令列有一定的熟悉度。

1.  **確保服務正在運行：** `docker-compose up`
2.  **打開一個新的終端機視窗。**
3.  **進入資料庫容器：**
    ```bash
    docker exec -it stocker_db bash
    ```
4.  **使用 psql 連接到資料庫：**
    在容器的 shell 內部，以 `user` 使用者身份連接到 `stocker` 資料庫。
    ```bash
    psql -U user -d stocker
    ```
5.  **執行 SQL 指令：** 您現在已經進入 psql 的互動式終端機。
    *   列出所有表格： `\dt`
    *   描述 users 表格結構： `\d users`
    *   查詢 users 表格中的所有資料： `SELECT * FROM users;`
    *   退出 psql： `\q`
6.  **退出容器 shell：** `exit`

### 方法二：使用圖形化介面客戶端 (DBeaver)

這種方法對初學者來說更推薦，因為它更加視覺化。

1.  **確保服務正在運行。** `docker-compose.yml` 中的 `ports: - "5432:5432"` 這一行至關重要，它將資料庫的埠暴露給了您的本機電腦。
2.  **下載並安裝** 一個資料庫客戶端，例如 [DBeaver](https://dbeaver.io/)。
3.  **建立新連線：**
    *   打開 DBeaver 並點擊「新增資料庫連線」圖示。
    *   選擇 **PostgreSQL**。
    *   在連線設定中，填入以下資訊：
        *   **主機 (Host):** `localhost`
        *   **埠 (Port):** `5432`
        *   **資料庫 (Database):** `stocker`
        *   **使用者 (Username):** `user`
        *   **密碼 (Password):** `password` (這些值都來自 `docker-compose.yml`)
4.  **測試並儲存：** 點擊「測試連線」。如果成功，就儲存該連線。
5.  **瀏覽資料：** 在左側的「資料庫導覽」面板中，展開您的新連線，然後依序展開 `stocker` > `Schemas` > `public` > `Tables`。雙擊 `users` 表格，即可在一個像電子表格一樣的介面中查看其資料。
