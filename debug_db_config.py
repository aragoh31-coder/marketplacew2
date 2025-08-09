import os
from pathlib import Path

import environ

BASE_DIR = Path("/app")
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

try:
    db_config = env.db()
    print("Database config:", db_config)
except Exception as e:
    print("Database config error:", e)
    print("DATABASE_URL:", os.getenv("DATABASE_URL", "NOT_SET"))
