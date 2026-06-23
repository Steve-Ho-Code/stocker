# 架構修復與行動計畫 (Architecture Remediation Plan)

## 執行摘要 (Execution Summary)
本計畫旨在解決先前架構審查中發現的關鍵風險，並為專案的長期健康發展奠定基礎。計畫的核心目標是：首先，立即修補嚴重的安全漏洞，防止機密資訊外洩；其次，引入 DevOps 最佳實踐，實現自動化與標準化；最後，透過策略性重構，提升系統的可擴展性和可維護性。我們建議在接下來的 1-2 個 Sprint 內集中資源解決所有 P0 級別的緊急任務。P1 級別的任務應納入下一季度的產品路線圖，而 P2 的長期重構則應作為技術債償還的重點項目進行規劃。

---

## 階段一：緊急修復與速贏 (Phase 1: Critical Fixes & Short-Term Wins - P0)

### [Task-1.1] 移除硬編碼的機密資訊並改用環境變數
* **目標檔案/模組**：`config.py`, `main.py`
* **任務描述**：目前，Telegram 和 Alpha Vantage 的 API 金鑰被硬編碼在 `config.py` 中，這是一個嚴重的安全風險。此任務要求將這些機密資訊從程式碼中移除，改為從環境變數中讀取。這將確保金鑰不會被提交到版本控制系統中，從而保護它們不被未經授權的存取。
* **預估工作量**：S (幾小時)
* **驗收標準 (Acceptance Criteria)**：
  * [x] `config.py` 中不再包含任何實際的 API 金鑰或機密字串。
  * [x] 應用程式啟動時會從環境變數 (`API_TOKEN`, `FINANCIAL_API_KEY`, `CHANNEL_ID`) 讀取設定。
  * [x] 專案根目錄下建立一個 `.env.example` 檔案，其中包含所有必要的環境變數名稱及其用途說明，但不包含實際值。
  * [x] 更新 `.gitignore` 檔案，確保 `.env` 檔案不會被 Git 追蹤。

### [Task-1.2] 建立基礎的 .gitignore 檔案
* **目標檔案/模組**：`.gitignore`
* **任務描述**：為了維持程式碼庫的整潔並避免提交不必要的檔案，需要建立或完善 `.gitignore` 檔案。這應包括 Python 專案的通用規則，以及特定於本地開發的檔案 (如 `.env` 和 `__pycache__/`)。
* **預估工作量**：S (幾小時)
* **驗收標準 (Acceptance Criteria)**：
  * [x] 專案根目錄下存在一個 `.gitignore` 檔案。
  * [x] 該檔案至少忽略了 `__pycache__/`, `*.pyc`, `.env` 和常見的作業系統檔案 (如 `.DS_Store`)。
  * [x] 執行 `git status` 時，不應顯示任何應被忽略的檔案。

---

## 階段二：架構與流程優化 (Phase 2: Architecture & Process Improvements - P1)

### [Task-2.1] 引入 Docker 進行容器化
* **目標檔案/模組**：`Dockerfile`, `docker-compose.yml` (可選)
* **任務描述**：為了實現環境一致性並簡化部署流程，需要將此應用程式容器化。建立一個 `Dockerfile`，它能定義一個包含所有必要相依性並能執行應用程式的輕量級 Python 映像。
* **預估工作量**：M (幾天)
* **驗收標準 (Acceptance Criteria)**：
  * [x] 專案根目錄下存在一個 `Dockerfile`。
  * [x] `docker build` 指令可以成功建立一個無錯誤的容器映像。
  * [x] 建立的容器可以成功啟動，並透過傳遞環境變數來設定 API 金鑰。
  * [x] 容器內的應用程式能夠成功連接到 Telegram 和 Alpha Vantage API，並按預期執行。

### [Task-2.2] 建立基礎的 CI/CD 自動化流程
* **目標檔案/模組**：`.github/workflows/ci.yml`
* **任務描述**：為了提升程式碼品質和開發效率，需要建立一個基本的持續整合 (CI) 流程。此流程應在每次有新的程式碼提交到 `main` 分支或發起 Pull Request 時自動觸發。流程應至少包括程式碼風格檢查 (linting) 和單元測試 (如果有的話)。
* **預估工作量**：M (幾天)
* **驗收標準 (Acceptance Criteria)**：
  * [x] `.github/workflows/` 目錄下存在一個 CI 設定檔 (例如 `ci.yml`)。
  * [x] CI 流程在 Pull Request 和推送到 `main` 分支時會自動執行。
  * [x] CI 流程中包含一個步驟，用於安裝 `requirements.txt` 中的相依性。
  * [x] CI 流程中包含一個 linter 步驟 (例如，使用 `flake8` 或 `black`)，並且能夠在發現程式碼風格問題時失敗。

### [Task-2.3] 引入結構化日誌
* **目標檔案/模組**：`main.py`
* **任務描述**：目前的日誌是簡單的文字格式，不利於在生產環境中進行機器解析和查詢。此任務要求將日誌系統升級為結構化日誌 (例如 JSON 格式)，以便能輕鬆地與 Datadog, Splunk 等日誌聚合工具整合。
* **預估工作量**：S (幾小時)
* **驗收標準 (Acceptance Criteria)**：
  * [x] 專案引入一個支援 JSON 格式的日誌函式庫 (例如 `python-json-logger`)。
  * [x] 應用程式的所有日誌輸出 (包括錯誤和一般資訊) 均為 JSON 格式。
  * [x] 日誌級別可以透過環境變數 `LOG_LEVEL` 進行設定。

---

## 階段三：長期策略性重構 (Phase 3: Long-Term Strategic Refactoring - P2)

### [Epic-3.1] 應用程式模組化重構
* **影響範圍**：`main.py` 以及所有新建立的模組。
* **任務描述**：為了提升程式碼的可維護性和可擴展性，需要將目前單體式的 `main.py` 檔案分解為多個功能內聚的模組。這將建立清晰的領域邊界，降低耦合度，並使未來的開發工作更加輕鬆。此 Epic 旨在將應用程式重構為一個更具彈性的結構，為未來的功能擴展 (如支援多種股票、多種通知渠道) 做好準備。
* **執行建議與拆解**：
    1.  **建立 `app` 目錄**：建立一個 `app` 目錄來存放所有應用程式程式碼，並在根目錄保留 `main.py` 作為啟動腳本。
    2.  **抽象化數據提供者**：建立 `app/providers/` 目錄，並將 `get_asset_price` 相關邏輯移入，定義一個通用的 `DataProvider` 介面。
    3.  **分離 Bot 邏輯**：建立 `app/bot/` 目錄，將所有 `python-telegram-bot` 相關的指令處理和訊息發送邏輯移入。
    4.  **重構設定管理**：建立 `app/core/config.py`，使用 Pydantic 或類似工具來管理設定，提供類型檢查和預設值。
* **預估工作量**：L (一週以上)
* **成功指標 (Success Metrics)**：
  * [x] `main.py` 的行數顯著減少，其主要職責是初始化和啟動應用程式。
  * [x] 業務邏輯 (獲取價格) 與框架邏輯 (Telegram Bot) 完全分離。
  * [x] 新增一個數據提供者 (例如，從另一個 API 獲取數據) 不需要修改 `bot` 模組的程式碼。
