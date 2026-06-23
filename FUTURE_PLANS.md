# Future Development Roadmap

This document outlines potential future improvements and strategic directions for the Stocker project. Having successfully completed the initial refactoring tasks, the project now has a solid and modern architecture. The ideas below represent the next steps toward building an enterprise-grade, cloud-native service, categorized by priority (P0 to P3).

---

## P0: Critical Infrastructure & Security
*These are mandatory steps to prevent data loss and ensure basic operational safety.*

### 1. Finnhub API Integration
*   **Current Status:** Alpha Vantage is hardcoded, which leads to strict rate limiting (25 requests/day), breaking the default 1-minute timer configuration.
*   **Next Steps:**
    - [x] **Configurable Providers:** Add `ACTIVE_PROVIDER` to environment settings to allow dynamic switching.
    - [x] **Finnhub Implementation:** Create `finnhub.py` using `httpx` to fetch data from Finnhub's `/quote` API (60 requests/minute).
    - [x] **Provider Router:** Update `providers/__init__.py` to route requests to the active provider based on the configuration. Do not overwrite Alpha Vantage.

### 2. Advanced Time Management & Scheduling
*   **Current Status:** The system only supports simple timers based on fixed intervals.
*   **Next Steps:** Implement a more flexible time scheduling mechanism.
    - [ ] **Exact Time Triggering:** Support triggering API calls at the top of the hour or at multiples of 10 minutes.
    - [ ] **Configurable Frequency:** Allow users to set the frequency to every hour, every 30 minutes, every 10 minutes, or every 1 minute.
    - [ ] **Daily Start Time:** Add a configuration option to set a specific time of day to start executing API calls.

### 3. Robust Database Backup & Recovery Strategy
*   **Current Status:** The database is persisted in a Docker Volume, which is tied to the host machine.
*   **Next Steps:** Implement a reliable, automated backup solution.
    - [ ] **Automated Backups:** Set up a nightly `cron job` on the VPS that executes `pg_dump` to create a compressed backup of the PostgreSQL database.
    - [ ] **Off-site Storage:** The backup script should securely upload the backup file to a cloud storage service (e.g., AWS S3, Google Cloud Storage) for disaster recovery.
    - [ ] **Retention Policy:** Define a retention policy (e.g., keep daily backups for 7 days, weekly for a month, and monthly for a year).
    - [ ] **Recovery Drill:** Periodically test the recovery process by restoring a backup to a staging environment to ensure the backups are valid and the process works as expected.

---

## P1: High Priority (Development Workflow & CI/CD)
*These improvements will drastically increase development speed and ensure code quality before reaching production.*

### 2. Comprehensive Test Coverage
*   **Current Status:** We have a basic testing foundation integrated into our CI pipeline.
*   **Next Steps:**
    - [ ] **Integration Tests:** Write detailed integration tests for all commands in `handlers.py`. These tests should mock the Telegram API but interact with a real test database to validate the full command logic, including database operations.
    - [ ] **Service-Layer Unit Tests:** Write unit tests for the logic within `services/`. For example, test the `settings_service.py` functions to ensure they interact with Redis correctly (this would involve a mock Redis instance).
    - [ ] **Measure and Enforce Coverage:** Introduce a tool like `pytest-cov` to measure test coverage. Set a minimum coverage threshold (e.g., 85%) in the CI pipeline to ensure all new code is adequately tested.

### 3. Full Continuous Deployment (CD)
*   **Current Status:** Our CI pipeline builds a Docker image upon successful completion of all checks but does not deploy it.
*   **Next Steps:**
    - [ ] **Create a `deploy.yml` Workflow:** Build a new GitHub Actions workflow that can be triggered manually or automatically on merges to the `main` branch.
    - [ ] **Container Registry:** Set up a container registry (e.g., GitHub Container Registry (GHCR), Docker Hub, or AWS ECR) to store our versioned Docker images.
    - [ ] **Deployment Script:** The `deploy.yml` workflow should:
        1.  Log in to the container registry.
        2.  Push the newly built Docker image to the registry, tagged with the Git commit SHA.
        3.  SSH into the production VPS.
        4.  Run a script on the server that pulls the latest image and restarts the `docker-compose` services (`docker-compose pull && docker-compose up -d`).
        5.  Run any necessary database migrations (`docker exec -it stocker_bot poetry run alembic upgrade head`).

---

## P2: Medium Priority (Observability & Stability)
*Necessary for proactive maintenance and understanding system health in a production environment.*

### 4. Advanced Monitoring & Alerting
*   **Current Status:** We have structured JSON logging, which is great for reactive debugging.
*   **Next Steps:** Move towards proactive monitoring.
    - [ ] **Instrument the Application:** Integrate a client library like `prometheus-client` to expose key application metrics via an HTTP endpoint (e.g., `/metrics`).
        *   **Metrics to Track:**
            *   `requests_total`: Counter for commands processed, with labels for command name and success status.
            *   `request_duration_seconds`: Histogram of command processing duration.
            *   `external_api_errors_total`: Counter for errors from financial APIs.
    - [ ] **Set up the Monitoring Stack:**
        1.  **Prometheus:** Deploy a Prometheus instance to scrape the `/metrics` endpoint of our application.
        2.  **Grafana:** Deploy a Grafana instance and connect it to Prometheus. Build dashboards to visualize our key metrics in real-time.
        3.  **Alertmanager:** Configure Alertmanager to define alerting rules. For example, set an alert to fire if the `external_api_errors_total` increases significantly in a short period. Send these alerts to a dedicated channel in Slack or Telegram.

---

## P3: Low Priority / Nice-to-Have (Scaling & Enterprise Features)
*Features that become necessary only when the system scales to a much larger user base or microservices architecture.*

### 5. Configuration as a Service
*   **Current Status:** Dynamic configuration is stored in Redis.
*   **Next Steps:** For even more complex scenarios, especially in a microservices architecture, consider adopting a dedicated configuration management service.
    - [ ] **Explore Tools:** Evaluate tools like [HashiCorp Consul](https://www.consul.io/) or [AWS AppConfig](https://aws.amazon.com/systems-manager/features/appconfig/).
    - [ ] **Benefits:** These tools provide advanced features like:
        *   **Feature Flags:** Enable or disable features at runtime without deploying new code.
        *   **Staged Rollouts:** Gradually roll out configuration changes to a subset of users or instances.
        *   **Validation and History:** Enforce validation rules on configuration changes and keep a history of all changes.