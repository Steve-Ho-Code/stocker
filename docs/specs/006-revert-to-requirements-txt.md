# Spec 006: Revert Dependency Management to requirements.txt

**Goal:** To revert the project's Python dependency management mécanisme from Poetry back to the traditional `pip` and `requirements.txt` format.

## 1. Rationale

While Poetry offers advanced features like deterministic dependency resolution and clear dependency grouping, the team has expressed a preference for the simplicity and wider familiarity of the `pip` and `requirements.txt` workflow. This change prioritizes team comfort and reduces the learning curve for new contributors who may not be familiar with Poetry. The goal is to maintain a robust dependency management system while adhering to the team's preferred toolset.

## 2. Functional Requirements

- The project MUST use `requirements.txt` as the single source of truth for Python dependencies.
- The `Dockerfile` MUST be updated to use `pip install -r requirements.txt` for installing dependencies.
- The CI/CD pipeline (`.github/workflows/ci.yml`) MUST be updated to use `pip` for installing dependencies and running scripts.
- Poetry-specific files (`pyproject.toml`, `poetry.lock`) MUST be removed from the project.
- The project MUST be able to generate separate `requirements.txt` and `requirements-dev.txt` files to distinguish between production and development dependencies.

## 3. Implementation Steps

1.  **Generate `requirements.txt` from Poetry:**
    -   Execute `poetry export -f requirements.txt --output requirements.txt --without-hashes` to generate a production `requirements.txt` file containing only the main dependencies.

2.  **Generate `requirements-dev.txt` from Poetry:**
    -   Execute `poetry export -f requirements.txt --output requirements-dev.txt --without-hashes --with dev` to generate a `requirements-dev.txt` file containing both main and development dependencies.

3.  **Update `Dockerfile`:**
    -   Modify the `Dockerfile` to revert to a single-stage build process.
    -   Remove all `poetry` related commands.
    -   Add a `COPY requirements.txt .` command.
    -   Add a `RUN pip install -r requirements.txt` command.

4.  **Update `.github/workflows/ci.yml`:**
    -   Remove the "Install Poetry" step.
    -   Modify the "Install dependencies" step to run `pip install -r requirements-dev.txt` (to ensure testing tools are installed).
    -   Modify all subsequent script-running steps (Lint, Test, Scan) to be executed directly (e.g., `pytest`) instead of using `poetry run`.

5.  **Update Documentation:**
    -   Modify `README.md`, `GUIDE.md`, and `GUIDE.zh-Hant.md` to reflect the change back to `pip` and `requirements.txt`. This includes updating the installation, running, and testing commands.

6.  **Cleanup:**
    -   Add `poetry.lock` to the `.gitignore` file to prevent it from being accidentally re-committed.
    -   Delete the `pyproject.toml` file from the project root.

## 4. Validation

- After the changes are implemented, the CI/CD pipeline in GitHub Actions must pass successfully.
- A local build using `docker build .` must complete without errors.
- The application, when run locally using `pip` and the new `Dockerfile`, must be fully functional.
