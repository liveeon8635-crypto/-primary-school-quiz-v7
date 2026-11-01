"""Keep application imports isolated in each pytest worker.

The app creates tables during import. Parallel collectors must never share the
default SQLite file, and tests must never inherit a production database URL.
Subprocess tests can still explicitly supply their own temporary database.
"""
import os
from pathlib import Path
import tempfile

_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="changying-pytest-"))
os.environ["DATABASE_URL"] = "sqlite:///" + (_TEST_DB_DIR / "app.sqlite3").as_posix()
