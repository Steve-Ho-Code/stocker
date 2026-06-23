# 架構改善實施計畫

本文件旨在為 `comprehensive-architecture-review.md` 中提出的 P0 和 P1 建議提供一個更詳細的實施步驟。

## P0：緊急修復與短期速贏 (Critical Fixes & Short-Term Wins)

### 1. 持久化動態設定
*   **[x] 目標：** 讓 `SYMBOL` 和 `TIMER_INTERVAL` 的設定在應用程式重新啟動後依然有效。
*   **步驟：**
    1.  建立一個名為 `settings.json` 的檔案，用於統一儲存所有動態設定。
    2.  修改 `src/config.py`，在應用程式啟動時從 `settings.json` 讀取 `SYMBOL` 和 `TIMER_INTERVAL` 的值作為預設值。如果檔案不存在，則使用系統預設值。
    3.  修改 `update_symbol` 和 `update_timer_interval` 函式，在更新記憶體中的設定值後，將整個設定物件寫回 `settings.json`，以確保資料持久化。
*   **實作備註：**
    *   **併發控制:** 在實作寫入 `settings.json` 的邏輯時，必須使用 `asyncio.Lock()` 來防止多個非同步任務同時寫入檔案，導致資料損毀。
    *   **Docker Volume:** 在 `docker-compose.yml` 或 `docker run` 指令中，必須將 `settings.json` 掛載為 Volume (e.g., `./settings.json:/app/settings.json`)，否則容器重啟後設定將會遺失。

### 2. 新增基本測試
*   **[x] 目標：** 為核心功能建立初步的單元測試，以確保程式碼的穩定性。
*   **步驟：**
    1.  在 `tests/` 目錄下，建立 `test_providers.py` 和 `test_handlers.py` 兩個檔案。
    2.  在 `test_providers.py` 中，使用 `pytest-mock` 來模擬 `httpx.AsyncClient`，並為 `get_asset_price` 函式撰寫測試，驗證其在成功和失敗情況下的行為。
    3.  在 `test_handlers.py` 中，為 `manual_update`、`set_symbol` 和 `set_timer` 函式撰寫測試，驗證其授權邏輯和基本功能。

### 3. 改善錯誤處理
*   **[x] 目標：** 在 API 請求失敗時，向使用者提供更友善的回饋。
*   **步驟：**
    1.  修改 `src/bot/handlers.py` 中的 `send_price_update` 函式。
    2.  在 `get_asset_price` 回傳 `None` 的情況下，除了記錄錯誤日誌外，還透過機器人向指定的頻道發送一條錯誤訊息，例如：「無法獲取最新的股價資訊，請稍後再試。」

## P1：架構與流程優化 (Architecture & Process Improvements)

### 1. 增強 CI/CD 流程
*   **[x] 目標：** 在 CI 流程中加入自動化測試，以提早發現錯誤。
*   **步驟：**
    1.  修改 `.github/workflows/ci.yml` 檔案。
    2.  在 `Lint with flake8` 步驟之後，新增一個名為 `Run tests` 的步驟。
    3.  在這個新步驟中，執行 `pytest` 來運行專案中的所有測試。
*   **實作備註：**
    *   **安裝依賴:** 在執行 `pytest` 之前，必須先在 CI 的 YAML 腳本中執行 `pip install -r requirements.txt`，以確保 `pytest`, `pytest-mock`, 和 `aiocache` 等測試相關的套件都已被安裝。

### 2. 引入具備 TTL 的 API 快取
*   **[x] 目標：** 減少對外部 API 的請求次數，避免觸及頻率限制，並提高效能和可靠性。
*   **步驟：**
    1.  修改 `src/providers/alpha_vantage.py`。
    2.  由於股價資料具有時效性，我們需要一個基於時間的快取 (TTL)，而不是單純的 LRU 快取。我們將引入 `aiocache` 這個功能強大的非同步快取函式庫。
    3.  在 `requirements.txt` 中新增 `aiocache`。
    4.  使用 `@aiocache.cached(ttl=60)` 裝飾器來為 `get_asset_price` 函式新增一個 60 秒過期的快取。這將確保在 60 秒內的重複請求會直接從快取中回傳，而不會真的去呼叫 Alpha Vantage API。
*   **實作備註：**
    *   **後端選擇:** `aiocache` 預設使用記憶體 (`SimpleMemoryCache`) 作為快取後端，對於單一節點的應用程式來說，這已足夠且效能最佳。未來若擴展為多節點部署，可無縫切換至 Redis 等外部快取後端。

### 3. 確保 API 金鑰的儲存與載入安全
*   **[x] 目標：** 確保 `FINANCIAL_API_KEY` 等機密資訊不會被洩漏。
*   **步驟：**
    1.  確認 `src/config.py` 中的 `Settings` 類別是透過 `pydantic-settings` 從 `.env` 檔案或環境變數中讀取 `FINANCIAL_API_KEY`。
    2.  確認 `.gitignore` 檔案中包含了 `.env`，防止該檔案被提交到版本控制系統中。
    3.  在日誌設定中，確保不會意外地將包含 API 金鑰的完整 URL 記錄到公開的日誌中。
