# Stocker 完整專案指南：從零到生產環境

本指南說明如何設定、執行、測試、部署與維護 Stocker。Stocker 是一個 Telegram 機器人，可定期或手動將股票與 ETF 價格更新發送到指定 Telegram 頻道。

本指南以 Docker 部署為主，因為 Docker Compose 會同時啟動 bot、PostgreSQL 和 Redis，最接近實際生產環境。若您只要在本機開發，也可以只用 Docker 啟動資料庫與 Redis，再直接用 Python 執行 bot。

## 1. 系統需求

請先安裝以下工具：

* **Git**：用來取得程式碼。
* **Docker 與 Docker Compose**：推薦安裝 Docker Desktop；VPS 上可安裝 Docker Engine 與 Compose plugin。
* **Python 3.10+**：只在本機直接執行或跑測試時需要。
* **Telegram 帳號**：用來建立 bot、頻道，以及取得管理員 ID。
* **Finnhub 或 Alpha Vantage API key**：用來取得價格資料。

## 2. 取得必要憑證

### 2.1 Telegram Bot Token

1. 在 Telegram 搜尋 `BotFather`。
2. 傳送 `/newbot`。
3. 依提示輸入 bot 名稱與 username。
4. BotFather 會回覆一串 token，這就是 `.env` 的 `API_TOKEN`。

### 2.2 Telegram Channel ID

若使用公開頻道，`CHANNEL_ID` 可以填頻道 username，例如：

```text
@my_stocker_channel
```

請確認 bot 已被加入頻道，且有發送訊息的權限。

### 2.3 Super Admin Telegram ID

1. 在 Telegram 搜尋 `@userinfobot`。
2. 對它傳送任意訊息。
3. 複製回覆中的數字 ID，填入 `SUPER_ADMIN_TELEGRAM_ID`。

超級管理員只能用來執行 `/grant_admin`，一般 admin 指令仍需要先授權。

### 2.4 財經資料 Provider API Key

Stocker 支援兩個 provider：

* `finnhub`：使用 `FINNHUB_API_KEY`。
* `alpha_vantage`：使用 `ALPHA_VANTAGE_API_KEY`。

預設 provider 是 `finnhub`。如果您要使用 Alpha Vantage，請在 `.env` 設定：

```dotenv
ACTIVE_PROVIDER="alpha_vantage"
```

## 3. 建立 `.env`

在專案根目錄複製範本：

```bash
cp .env.example .env
```

Windows PowerShell 可使用：

```powershell
Copy-Item .env.example .env
```

建議最少填入以下內容：

```dotenv
# Telegram Bot Configuration
API_TOKEN="在這裡填入 BotFather 給您的 token"
CHANNEL_ID="@your_channel_name"
SUPER_ADMIN_TELEGRAM_ID="在這裡填入您的 Telegram 數字 ID"

# External Services
FINNHUB_API_KEY="在這裡填入 Finnhub API key"
ALPHA_VANTAGE_API_KEY=""
ACTIVE_PROVIDER="finnhub"

# Infrastructure Configuration
# Docker Compose 環境請使用以下預設值。
DATABASE_URL="postgresql://user:password@db:5432/stocker"
REDIS_URL="redis://redis:6379"

# Schedule Configuration
SCHEDULE_FREQUENCY_MINUTES="1"
SCHEDULE_START_TIME="00:00"
SCHEDULE_END_TIME="23:59"
SCHEDULE_TIMEZONE="America/New_York"

# Optional: Logging Configuration
# LOG_LEVEL="INFO"
```

### 3.1 設定值說明

| 變數 | 必填 | 說明 |
| --- | --- | --- |
| `API_TOKEN` | 是 | Telegram Bot API token。 |
| `CHANNEL_ID` | 是 | bot 發送排程更新的 Telegram 頻道 username 或 chat ID。 |
| `SUPER_ADMIN_TELEGRAM_ID` | 是 | 可授予 admin 權限的 Telegram 使用者 ID。 |
| `FINNHUB_API_KEY` | 視 provider 而定 | `ACTIVE_PROVIDER=finnhub` 時必填。 |
| `ALPHA_VANTAGE_API_KEY` | 視 provider 而定 | `ACTIVE_PROVIDER=alpha_vantage` 時必填。 |
| `ACTIVE_PROVIDER` | 否 | `finnhub` 或 `alpha_vantage`，預設為 `finnhub`。 |
| `DATABASE_URL` | 否 | PostgreSQL 連線字串。Docker Compose 預設為 `postgresql://user:password@db:5432/stocker`。 |
| `REDIS_URL` | 否 | Redis 連線字串。Docker Compose 預設為 `redis://redis:6379`。 |
| `SCHEDULE_FREQUENCY_MINUTES` | 否 | 排程頻率，支援 `1`、`5`、`10`、`15`、`30`、`60` 分鐘。 |
| `SCHEDULE_START_TIME` | 否 | 每日排程啟用時間，格式為 `HH:MM`。 |
| `SCHEDULE_END_TIME` | 否 | 每日排程停止時間，格式為 `HH:MM`。 |
| `SCHEDULE_TIMEZONE` | 否 | IANA timezone，例如 `America/New_York`、`Asia/Hong_Kong`、`UTC`。 |
| `LOG_LEVEL` | 否 | 日誌級別，例如 `DEBUG`、`INFO`、`WARNING`、`ERROR`。 |

`TIMER_INTERVAL` 仍可作為舊版啟動設定使用，單位是秒；但新部署應改用 `SCHEDULE_FREQUENCY_MINUTES`。

## 4. 使用 Docker 執行

Docker Compose 會啟動三個服務：

* `bot`：Stocker Telegram bot。
* `db`：PostgreSQL。
* `redis`：Redis，用於動態設定。

啟動服務：

```bash
docker-compose up --build
```

如果您的環境使用 Docker Compose v2，也可以使用：

```bash
docker compose up --build
```

第一次啟動新資料庫後，需要套用資料庫遷移：

```bash
docker exec -it stocker_bot alembic upgrade head
```

停止服務：

```bash
docker-compose down
```

背景執行：

```bash
docker-compose up --build -d
```

查看日誌：

```bash
docker-compose logs -f
```

## 5. 授權第一位管理員

資料庫遷移完成後，請先讓目標使用者在 Telegram 對 bot 傳送：

```text
/start
```

這會在資料庫建立使用者紀錄。接著由 `SUPER_ADMIN_TELEGRAM_ID` 對應的帳號執行：

```text
/grant_admin YOUR_TELEGRAM_USER_ID
```

授權成功後，該使用者即可執行 admin 指令，例如 `/update`、`/set_symbol`、`/set_timer`。

## 6. 排程設定

Stocker 使用 APScheduler 的 cron-style trigger，在固定的牆上時間邊界觸發更新。例如頻率為 15 分鐘時，會在每小時的 `00`、`15`、`30`、`45` 分觸發。

排程由三個設定控制：

* **頻率**：`1`、`5`、`10`、`15`、`30`、`60` 分鐘。
* **每日時間窗**：`SCHEDULE_START_TIME` 到 `SCHEDULE_END_TIME`。
* **時區**：`SCHEDULE_TIMEZONE`。

如果 start time 晚於 end time，系統會視為跨日時間窗。例如 `22:00` 到 `02:00` 代表晚上 10 點到隔天凌晨 2 點。

排程設定可透過 `.env` 提供啟動預設值，也可在 bot 執行期間用指令更新。透過指令更新後，設定會寫入 Redis，重啟後仍會保留；Redis 值會覆蓋 `.env` 預設值。

手動 `/update` 不受排程時間窗限制。

## 7. Bot 指令

| 指令 | 權限 | 說明 |
| --- | --- | --- |
| `/start` | 所有人 | 註冊使用者並顯示目前追蹤標的與頻率。 |
| `/update` | Admin | 立即發送一次價格更新。 |
| `/set_symbol [SYMBOL]` | Admin | 更新追蹤標的；不帶參數時進入互動輸入。 |
| `/set_timer [minutes]` | Admin | 更新排程頻率；支援 `1`、`5`、`10`、`15`、`30`、`60`。 |
| `/set_schedule_window <START_HH:MM> <END_HH:MM>` | Admin | 更新每日排程時間窗。 |
| `/set_schedule_timezone <IANA_TIMEZONE>` | Admin | 更新排程使用的 timezone。 |
| `/config_status` | Admin | 顯示目前 symbol、頻率、時間窗與 timezone。 |
| `/grant_admin <user_id>` | Super admin | 授予已註冊使用者 admin 權限。 |
| `/cancel` | 互動流程中使用 | 取消目前互動輸入。 |

## 8. 本機開發流程

如果您不想用 Docker 執行 bot，可只用 Docker 啟動 PostgreSQL 和 Redis：

```bash
docker-compose up -d db redis
```

接著在 `.env` 將連線改成本機：

```dotenv
DATABASE_URL="postgresql://user:password@localhost:5432/stocker"
REDIS_URL="redis://localhost:6379"
```

安裝開發依賴：

```bash
pip install -r requirements-dev.txt
```

套用遷移：

```bash
python -m alembic upgrade head
```

啟動 bot：

```bash
python -m src.main
```

## 9. 測試

安裝開發依賴後，在專案根目錄執行：

```bash
pytest
```

建議在提交 PR 前至少執行一次完整測試。

## 10. 部署到 VPS

部署到 VPS 的流程與本機 Docker 執行類似：

1. 在 VPS 安裝 Docker、Docker Compose 和 Git。
2. 複製 repository。
3. 建立 `.env` 並填入生產環境設定。
4. 啟動服務：

```bash
docker-compose up --build -d
```

5. 第一次部署或有新 migration 時執行：

```bash
docker exec -it stocker_bot alembic upgrade head
```

6. 查看日誌確認 bot 正常啟動：

```bash
docker-compose logs -f bot
```

更新部署時，通常執行：

```bash
git pull
docker-compose up --build -d
docker exec -it stocker_bot alembic upgrade head
```

## 11. 檢查資料庫

### 11.1 使用 psql

確保服務正在執行後，進入 PostgreSQL 容器：

```bash
docker exec -it stocker_db bash
```

連線到資料庫：

```bash
psql -U user -d stocker
```

常用指令：

```sql
\dt
\d users
SELECT * FROM users;
\q
```

離開容器 shell：

```bash
exit
```

### 11.2 使用 DBeaver

若使用 Docker Compose，PostgreSQL 會暴露在 `localhost:5432`。DBeaver 連線資訊如下：

* Host: `localhost`
* Port: `5432`
* Database: `stocker`
* Username: `user`
* Password: `password`

## 12. 重置開發資料庫

以下操作會刪除本機 Docker volume 中的 PostgreSQL 資料，只適合開發環境。

停止服務：

```bash
docker-compose down
```

刪除資料庫 volume：

```bash
docker volume rm stocker_postgres_data
```

如果您的專案資料夾名稱不同，volume 前綴可能不是 `stocker_`。可先用以下指令確認：

```bash
docker volume ls
```

重新啟動並套用遷移：

```bash
docker-compose up --build -d
docker exec -it stocker_bot alembic upgrade head
```

## 13. 常見問題

### Bot 啟動後沒有發送排程更新

請檢查：

* bot 是否已加入 `CHANNEL_ID` 指定的頻道。
* bot 是否有發送訊息權限。
* `/config_status` 顯示的時間窗與 timezone 是否包含目前時間。
* Redis 中是否有舊的動態設定覆蓋 `.env`。
* provider API key 是否有效。

### `/update` 可用，但排程沒有動作

手動 `/update` 不受排程限制；排程更新會受 `SCHEDULE_START_TIME`、`SCHEDULE_END_TIME` 和 `SCHEDULE_TIMEZONE` 控制。先用 `/config_status` 確認目前設定。

### `.env` 改了但設定沒有變

`SYMBOL` 與排程設定可能已透過 bot 指令寫入 Redis。應用程式啟動時會優先使用 Redis 中的動態設定。若要改回 `.env` 預設值，需要清除對應 Redis key 或透過 bot 指令更新。

### Alpha Vantage 回傳頻率限制或錯誤

可考慮改用 `ACTIVE_PROVIDER="finnhub"`，並設定 `FINNHUB_API_KEY`。Finnhub provider 目前是預設選項。
