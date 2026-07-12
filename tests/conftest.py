import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def reset_scheduler_state():
    from src.services import scheduler_service

    scheduler_service._reset_schedule_runtime_state()
    yield
    scheduler_service._reset_schedule_runtime_state()
