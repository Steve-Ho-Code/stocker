# 架構修復與行動計畫 (Architecture Remediation Plan)

## 執行摘要 (Execution Summary)
本計畫旨在將先前架構審查中識別出的風險轉化為可執行的工程任務。我們的目標是透過分階段的方法，系統性地提升專案的安全性、可維護性、可擴展性與 DevOps 成熟度。我們建議在接下來的 1-2 個 Sprint 內集中資源解決所有 P0 級別的緊急任務，以立即降低安全風險。P1 級別的任務應納入下一季度的產品路線圖，而 P2 的長期重構則應作為技術債償還的重點項目進行策略性規劃。

---

## 階段一：緊急修復與速贏 (Phase 1: Critical Fixes & Short-Term Wins - P0)

### [Task-1.1] 為手動觸發的指令增加授權檢查
* **目標檔案/模組**：`src/bot/handlers.py`, `src/config.py`, `.env.example`
* **任務描述**：目前，任何人都可以透過 Telegram 指令 (如 `/update`) 觸發機器人，這存在濫用風險。此任務要求實作一個基本的授權機制，只允許在設定中指定的授權使用者執行這些敏感操作。
* **預估工作量**：S (幾小時)
* **驗收標準 (Acceptance Criteria)**：
  * [x] `src/config.py` 中新增一個 `AUTHORIZED_USER_IDS` 設定，從環境變數讀取，其值為一個以逗號分隔的 Telegram 使用者 ID 列表。
  * [x] `.env.example` 檔案中需包含 `AUTHORIZED_USER_IDS` 變數的說明。
  * [x] `src/bot/handlers.py` 中的 `manual_update` 函式會檢查指令發送者的 `update.message.from_user.id` 是否存在於 `AUTHORIZED_USER_IDS` 列表中。
  * [x] 如果使用者未經授權，機器人應回覆一條拒絕訊息，且不會觸發價格更新。

---

## 階段二：架構與流程優化 (Phase 2: Architecture & Process Improvements - P1)

### [Task-2.1] 在 CI 流程中增加自動化單元測試
* **目標檔案/模組**：`.github/workflows/ci.yml`, `tests/providers/test_alpha_vantage.py` (新檔案)
* **任務描述**：目前的 CI 流程僅包含 linter 檢查，缺乏自動化測試來確保程式碼變更的正確性。此任務要求為核心業務邏輯 (獲取資產價格) 編寫單元測試，並將其整合到 CI 流程中。
* **預估工作量**：M (幾天)
* **驗收標準 (Acceptance Criteria)**：
  * [ ] 專案中新增 `pytest` 和 `pytest-asyncio` 到 `requirements-dev.txt`。
  * [ ] 建立 `tests/providers/test_alpha_vantage.py` 檔案，其中包含對 `get_asset_price` 函式的單元測試。
  * [ ] 測試應使用 `unittest.mock` 或類似工具來模擬 `httpx.AsyncClient` 的行為，以避免實際的網路請求。
  * [ ] `.github/workflows/ci.yml` 中增加一個新的步驟，用於安裝開發依賴並執行 `pytest`。
  * [ ] 如果測試失敗，CI 流程必須失敗。

### [Task-2.2] 抽象化數據提供者介面
* **目標檔案/模組**：`src/providers/__init__.py` (新檔案或修改), `src/providers/alpha_vantage.py`
* **任務描述**：為了降低與特定數據提供者 (Alpha Vantage) 的耦合度，並為未來支援多個數據源做準備，此任務要求定義一個通用的數據提供者介面。
* **預估工作量**：M (幾天)
* **驗收標準 (Acceptance Criteria)**：
  * [ ] 在 `src/providers/__init__.py` 中定義一個名為 `DataProvider` 的抽象基礎類別 (ABC)。
  * [ ] `DataProvider` 介面需包含一個非同步的抽象方法 `get_price(self, symbol: str) -> Optional[str]`。
  * [ ] `src/providers/alpha_vantage.py` 中的邏輯被重構為一個 `AlphaVantageProvider` 類別，該類別繼承自 `DataProvider` 並實作 `get_price` 方法。
  * [ ] `src/bot/handlers.py` 中使用 `AlphaVantageProvider` 實例來獲取價格，而不是直接呼叫函式。

### [Task-2.3] 豐富結構化日誌的上下文資訊
* **目標檔案/模組**：`src/bot/handlers.py`, `src/providers/alpha_vantage.py`
* **任務描述**：目前的日誌雖然是結構化的，但缺乏足夠的上下文資訊，不利於問題排查。此任務要求在關鍵的日誌輸出中增加額外的上下文資訊。
* **預估工作量**：S (幾小時)
* **驗收標準 (Acceptance Criteria)**：
  * [ ] 在 `send_price_update` 函式中，日誌應包含正在查詢的股票代碼 (`symbol`)。
  * [ ] 在 `get_asset_price` 函式中，當 API 請求失敗時，日誌應包含 HTTP 狀態碼和目標 URL。
  * [ ] 考慮為每個請求或操作生成一個唯一的追蹤 ID (trace ID)，並將其包含在所有相關的日誌訊息中。

---

## 階段三：長期策略性重構 (Phase 3: Long-Term Strategic Refactoring - P2)

### [Epic-3.1] 支援多目標與多頻道的動態設定
* **影響範圍**：`src/config.py`, `src/main.py`, `src/bot/handlers.py`
* **任務描述**：將專案從目前追蹤單一股票並發送到單一頻道的靜態設定，重構為一個能夠動態管理多個追蹤目標和通知渠道的系統。這將是專案從一個簡單機器人轉變為一個可設定平台的關鍵一步。
* **執行建議與拆解**：
    1.  **設定模型擴展**：修改 `src/config.py`，使其能夠從一個 YAML 檔案 (例如 `targets.yaml`) 或一個簡單的資料庫表中讀取一個追蹤目標列表，每個目標包含 `symbol` 和 `channel_id`。
    2.  **排程器重構**：修改 `src/main.py` 中的排程器邏輯，使其在啟動時遍歷所有追蹤目標，並為每個目標動態地建立一個獨立的 `send_price_update` 排程任務。
    3.  **指令擴展**：考慮增加新的 Telegram 指令，例如 `/add_target <symbol> <channel_id>` 和 `/remove_target <symbol>`，以允許管理員在執行階段動態管理追蹤目標 (這可能需要一個簡單的持久化儲存)。
* **預估工作量**：L (一週以上)
* **成功指標 (Success Metrics)**：
  * [ ] 應用程式能夠同時監控和更新多個不同的股票代碼到不同的 Telegram 頻道。
  * [ ] 新增或移除追蹤目標不需要重新部署應用程式 (如果實作了動態指令)。
  * [ ] 系統的複雜度被有效地管理在各自的模組中，核心邏輯保持清晰。

### [Epic-3.2] 實作完整的 CI/CD 流程
* **影響範圍**：`.github/workflows/cd.yml` (新檔案), `Dockerfile`
* **任務描述**：建立一個完整的持續整合與持續部署 (CI/CD) 流程，實現從程式碼提交到生產環境部署的全自動化，以提高交付速度和可靠性。
* **執行建議與拆解**：
    1.  **建立容器註冊中心**：設定一個容器註冊中心 (例如 Docker Hub, GitHub Container Registry, AWS ECR) 來儲存應用程式的 Docker 映像檔。
    2.  **擴展 CI 流程**：在現有的 CI 流程 (`ci.yml`) 的基礎上，增加一個步驟，在測試通過後建置 Docker 映像檔並將其推送到容器註冊中心，並使用 Git SHA 作為標籤。
    3.  **建立 CD 工作流程**：建立一個新的 GitHub Actions 工作流程 (`cd.yml`)，該工作流程由手動觸發 (或在建立 release tag 時觸發)。
    4.  **部署步驟**：CD 工作流程應包含從容器註冊中心拉取指定版本的映像檔，並將其部署到目標環境 (例如，透過 SSH 連線到伺服器並執行 `docker-compose up -d`，或更新 Kubernetes 的部署設定)。
* **預估工作量**：L (一週以上)
* **成功指標 (Success Metrics)**：
  * [ ] 開發人員可以透過單一指令或點擊按鈕，將通過測試的程式碼版本部署到生產環境。
  * [ ] 部署過程完全自動化，無需手動介入。
  * [ ] 能夠輕鬆地追蹤哪個版本的程式碼正在哪個環境中執行，並支援快速回滾。
