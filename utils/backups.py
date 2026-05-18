from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from database.db import BACKUPS_DIR, DB_PATH, ensure_runtime_dirs
from utils.app_logging import log_info


def create_database_backup() -> Path:
    ensure_runtime_dirs()
    if not DB_PATH.exists():
        raise FileNotFoundError("La base de données n'existe pas encore.")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    destination = BACKUPS_DIR / f"campflow_backup_{timestamp}.sqlite3"
    shutil.copy2(DB_PATH, destination)
    log_info(f"Sauvegarde locale créée : {destination.name}")
    return destination
