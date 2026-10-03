import pytest
import os
from pathlib import Path
from app.config import settings
from app.db.seed import seed_database
from app.agent.graph import task_store

@pytest.fixture(autouse=True)
def reset_db_before_test():
    """Ensure every test runs against a cleanly seeded database and clean task store."""
    seed_database(settings.DATABASE_PATH)
    task_store.clear()
    yield
    # Cleanup task store
    task_store.clear()
