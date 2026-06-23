# 架構改善實施計畫 (v4)

本文件旨在為 `docs/reviews/004-comprehensive-architecture-review.md` 中提出的建議，制定一個詳細的實施計畫。

## P0：緊急修復與短期速贏 (Critical Fixes & Short-Term Wins)

### 1. 重構授權邏輯
*   **狀態：** <span style="color:green;">**已完成**</span>.
*   **目標：** 將重複的授權檢查重構為一個 Python 裝飾器。
*   **驗證：**
    *   `src/bot/handlers.py` 中已有名為 `@authorized_users_only` 的裝飾器。
    *   該裝飾器已應用於 `manual_update`, `set_symbol`, `set_timer`, 和 `config_status` 等多個處理函式。

### 2. 增強日誌記錄
*   **狀態：** <span style="color:green;">**已完成**</span>.
*   **目標：** 為日誌訊息添加關鍵上下文（如使用者 ID），並確保 `jsonlogger` 在整個應用程式中一致使用。
*   **實施細節：**
    *   修改了 `authorized_users_only` 裝飾器，在拒絕存取時，使用 `logger.warning` 記錄嘗試操作的使用者 ID。
    *   修改了 `send_price_update` 函式，在記錄 API 錯誤時，包含觸發該操作的 `user_id`。

### 3. 修正輸入驗證
*   **狀態：** <span style="color:green;">**已完成**</span>.
*   **目標：** 對使用者輸入的 `new_interval` 進行更嚴格的驗證，增加最大值限制。
*   **實施細節：**
    *   在 `src/config.py` 的 `Settings` 中新增了 `MAX_TIMER_INTERVAL` 變數。
    *   修改了 `src/bot/handlers.py` 中的 `set_timer` 和 `receive_timer` 函式，確保輸入的間隔不超過最大值。

## P1：架構與流程優化 (Architecture & Process Improvements)

### 1. 引入依賴項漏洞掃描
*   **狀態：** <span style="color:green;">**已完成**</span>.
*   **目標：** 在 CI 流程中加入漏洞掃描步驟，以提早發現潛在的安全風險。
*   **實施細節：**
    *   已將 `pip-audit` 新增至 `pyproject.toml` 的開發依賴中。
    *   已在 `.github/workflows/ci.yml` 中新增 `Security Scan with pip-audit` 步驟。

### 2. 優化 Dockerfile
*   **狀態：** <span style="color:green;">**已完成**</span>.
*   **目標：** 使用多階段建構 (multi-stage build) 來減小最終生產映像檔的大小。
*   **實施細節：**
    *   `Dockerfile` 已重構為使用多階段建構。
    *   專案依賴管理已從 `requirements.txt` 遷移至 Poetry (`pyproject.toml`)。

### 3. 遷移設定儲存至 Redis
*   **狀態：** <span style="color:green;">**已完成**</span>.
*   **目標：** 將動態設定從 `settings.json` 遷移到 Redis，以解決水平擴展時的狀態不一致問題。
*   **實施細節：**
    *   已將 `redis` 和 `aioredis` 新增至 `pyproject.toml`。
    *   `src/config.py` 和 `src/main.py` 已重構為使用 Redis 進行動態設定的儲存和讀取。
    *   已刪除不再需要的 `settings.json` 檔案。

## P2：長期策略性變更 (Long-Term Strategic Changes)

### 1. 引入資料庫
*   **目標：** 為了支援更複雜的功能（如使用者角色、權限管理），規劃引入一個輕量級資料庫。
*   **執行建議：**
    1.  選擇一個資料庫 (例如 SQLite 或 PostgreSQL)。
    2.  使用 `poetry add sqlalchemy` 指令，在 `pyproject.toml` 中新增 ORM 函式庫。
    3.  設計資料模型 (schema)，用於儲存使用者、角色和權限。
    4.  將目前的授權邏輯從檢查環境變數中的 ID 列表，重構為查詢資料庫中的使用者角色和權限。

### 2. 建立完整的 CI/CD 流程
*   **目標：** 擴展 GitHub Actions，實現從測試、建置到自動部署的完整流程。
*   **執行建議：**
    1.  在 `.github/workflows/ci.yml` 的結尾，新增一個 `Build Docker Image` 步驟，該步驟僅在所有先前的步驟都成功時執行。
    2.  建立一個新的 `deploy.yml` 工作流程，該流程可手動觸發，用於將已建置的映像部署到伺服器。

### 3. 模組解耦
*   **目標：** 將 `config.py` 中的 Redis 操作邏輯分離出來，使其職責更單一。
*   **執行建議：**
    1.  建立一個新的 `src/services/settings_service.py` 模組。
    2.  將 `update_symbol` 和 `update_timer_interval` 等函式從 `config.py` 移至新模組中。
    3.  `config.py` 應只負責載入設定和初始化 Redis 客戶端。
    4.  在 `handlers.py` 中，呼叫新的 `settings_service` 來更新設定。
