# 未來發展藍圖 (Future Development Roadmap)

本文件概述了 Stocker 專案潛在的未來改進方向與策略藍圖。在成功完成初步的重構任務後，本專案現在已具備穩健且現代化的架構。以下想法代表了邁向企業級、雲端原生 (cloud-native) 服務的後續步驟，並依優先級 (P0 至 P3) 進行分類。

---

## P0: 關鍵基礎設施與安全性 (Critical Infrastructure & Security)
*這些是防止資料遺失並確保基本營運安全的強制性步驟。*

### 1. 整合 Finnhub API (Finnhub API Integration)
*   **目前狀態：** 系統寫死使用 Alpha Vantage，這會導致嚴格的速率限制 (一天 25 次請求)，使得預設的 1 分鐘更新計時器無法正常運作。
*   **下一步：**
    - [x] **可配置的供應商 (Configurable Providers)：** 在環境設定中加入 `ACTIVE_PROVIDER`，允許動態切換 API。
    - [x] **實作 Finnhub：** 建立 `finnhub.py`，使用 `httpx` 從 Finnhub 的 `/quote` API 抓取資料 (每分鐘 60 次請求)。
    - [x] **供應商路由器 (Provider Router)：** 更新 `providers/__init__.py`，根據配置將請求路由至對應的 API，且保留舊有的 Alpha Vantage 程式碼。

### 2. 進階時間管理與排程 (Advanced Time Management & Scheduling)
*   **目前狀態：** 系統目前僅支援基於固定間隔的簡單計時器。
*   **下一步：** 實作更具彈性的時間排程機制。
    - [x] **精確時間觸發 (Exact Time Triggering)：** 支援在每個整點或每 10 分鐘的倍數時間點觸發 API 呼叫 (可利用 `APScheduler` 的 `CronTrigger`)。
    - [x] **可配置的頻率 (Configurable Frequency)：** 允許使用者設定每小時、每 30 分鐘、每 10 分鐘或每 1 分鐘觸發一次。
    - [x] **每日開始與結束時間 (Daily Start/End Time)：** 新增設定選項，允許配置每日開始與停止執行 API 呼叫的特定時間，避免在休市期間浪費 API 額度並防止洗版。
    - [x] **時區支援 (Timezone Support)：** 確保排程器使用明確的目標市場時區 (例如美股使用 `America/New_York`)，以正確處理夏令/冬令時間轉換。

### 3. 穩健的資料庫備份與還原策略
*   **目前狀態：** 資料庫目前持久化儲存於 Docker Volume 中，綁定於主機 (host machine) 上。
*   **下一步：** 實作可靠且自動化的備份解決方案。
    - [ ] **自動化備份：** 在 VPS 上設定每晚執行的 `cron job`，透過 `pg_dump` 建立 PostgreSQL 資料庫的壓縮備份。
    - [ ] **異地儲存 (Off-site Storage)：** 備份腳本應將備份檔安全地上傳至雲端儲存服務 (例如 AWS S3、Google Cloud Storage)，以利災難復原。
    - [ ] **保留策略 (Retention Policy)：** 定義保留規則 (例如：每日備份保留 7 天，每週備份保留 1 個月，每月備份保留 1 年)。
    - [ ] **還原演練：** 定期將備份還原至 Staging 環境進行測試，確保備份檔有效且還原流程正常運作。

---

## P1: 高優先級 (開發工作流程與 CI/CD)
*這些改進將大幅提升開發速度，並確保程式碼在進入 Production 環境前的品質。*

### 2. 完整的測試覆蓋率 (Test Coverage)
*   **目前狀態：** 我們已在 CI pipeline 中整合了基礎的測試框架。
*   **下一步：**
    - [ ] **整合測試 (Integration Tests)：** 為 `handlers.py` 中的所有指令撰寫詳細的整合測試。這些測試應該 Mock 掉 Telegram API，但與真實的測試資料庫互動，以驗證完整的指令邏輯 (包含資料庫操作)。強烈建議在 CI 環境中使用 `testcontainers-python` 來自動啟動與管理測試專用的 PostgreSQL 容器，確保測試環境與 Production 一致。
    - [ ] **Service 層單元測試 (Unit Tests)：** 為 `services/` 內的邏輯撰寫單元測試。例如，測試 `settings_service.py` 確保其與 Redis 互動正確 (這將需要一個 Mock 的 Redis 實例)。
    - [ ] **測量與強制覆蓋率：** 導入如 `pytest-cov` 的工具來測量測試覆蓋率。在 CI pipeline 中設定最低覆蓋率門檻 (例如 85%)，確保所有新程式碼都經過充分測試。

### 3. 完整的持續部署 (Continuous Deployment, CD)
*   **目前狀態：** 我們的 CI pipeline 在所有檢查成功通過後會建置 Docker 映像檔 (Docker image)，但尚未進行部署。
*   **下一步：**
    - [ ] **建立 `deploy.yml` Workflow：** 建立一個新的 GitHub Actions workflow，可手動觸發或在 merge 到 `main` 分支時自動觸發。
    - [ ] **Container Registry：** 設定一個 Container Registry (例如 GitHub Container Registry (GHCR)、Docker Hub 或 AWS ECR) 來儲存我們標有版本號的 Docker 映像檔。
    - [ ] **部署腳本 (Deployment Script)：** `deploy.yml` workflow 應該執行以下操作：
        1.  登入 Container Registry。
        2.  將新建立的 Docker 映像檔推送到 Registry，並使用 Git commit SHA 作為 Tag。
        3.  透過 SSH 連線至 Production VPS。
        4.  在伺服器上執行腳本，拉取最新映像檔並重啟 `docker-compose` 服務 (`docker-compose pull && docker-compose up -d`)。
        5.  執行任何必要的資料庫遷移 (`docker exec -it stocker_bot alembic upgrade head`)。

---

## P2: 中優先級 (可觀測性與穩定度)
*對於 Production 環境中的主動維護與掌握系統健康狀況是必要的。*

### 4. 進階監控與警報 (Monitoring & Alerting)
*   **目前狀態：** 我們擁有結構化的 JSON logging，非常適合被動式的除錯 (reactive debugging)。
*   **下一步：** 邁向主動式監控 (proactive monitoring)。
    - [ ] **應用程式埋點 (Instrument)：** 整合如 `prometheus-client` 的函式庫，透過 HTTP endpoint (例如 `/metrics`) 暴露關鍵的應用程式指標 (metrics)。
        *   **要追蹤的 Metrics：**
            *   `requests_total`: 處理指令的計數器 (Counter)，包含指令名稱與成功狀態的 labels。
            *   `request_duration_seconds`: 指令處理時間的直方圖 (Histogram)。
            *   `external_api_errors_total`: 來自金融 API 錯誤的計數器。
    - [ ] **建立監控架構 (Monitoring Stack)：**
        1.  **Prometheus:** 部署一個 Prometheus 實例來爬取 (scrape) 應用程式的 `/metrics` endpoint。
        2.  **Grafana:** 部署一個 Grafana 實例並連接至 Prometheus。建立 Dashboard 以即時視覺化我們的關鍵 metrics。
        3.  **Alertmanager:** 設定 Alertmanager 來定義警報規則。例如，如果 `external_api_errors_total` 在短時間內顯著增加，則觸發警報。將這些警報發送至 Slack 或 Telegram 的專屬頻道。

### 5. 產品體驗提升 (User Experience Enhancement)
*   **目前狀態：** 使用者必須手動輸入文字來完成設定 (例如 `/set_timer` 與 `/set_symbol`)。
*   **下一步：** 導入更直覺的互動介面。
    - [ ] **導入 Inline Keyboard (按鈕介面)：** 針對常用設定提供 Inline Buttons。例如 `/set_timer` 彈出選項按鈕，或 `/set_symbol` 提供熱門 ETF 快速選擇。這將大幅提升行動裝置上的操作體驗。

---

## P3: 低優先級 / 加分項目 (擴展性與企業級功能)
*只有當系統擴展到更大規模的使用者基礎或微服務架構 (microservices architecture) 時才變得必要的功能。*

### 6. 配置即服務 (Configuration as a Service)
*   **目前狀態：** 動態配置儲存於 Redis 中。
*   **下一步：** 針對更複雜的情境，特別是在微服務架構中，考慮採用專屬的配置管理服務。
    - [ ] **探索工具：** 評估如 [HashiCorp Consul](https://www.consul.io/) 或 [AWS AppConfig](https://aws.amazon.com/systems-manager/features/appconfig/) 等工具。
    - [ ] **優勢：** 這些工具提供以下進階功能：
        *   **Feature Flags:** 在 Runtime 啟用或停用功能，而無需重新部署程式碼。
        *   **Staged Rollouts:** 將配置變更逐步 rollout 給部分使用者或實例 (instances)。
        *   **Validation and History:** 強制執行配置變更的驗證規則，並保留所有變更的歷史紀錄。
