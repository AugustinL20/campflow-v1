from __future__ import annotations

import sys
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.auth import ADMIN_GLOBAL, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD, hash_password
from database.db import DEFAULT_ESTABLISHMENT_ID, get_connection, init_db


def reset_admin() -> None:
    init_db()
    temporary_password = os.getenv("CAMPFLOW_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE lower(email) = lower(?)",
            (DEFAULT_ADMIN_EMAIL,),
        ).fetchone()
        password_hash = hash_password(temporary_password)
        if row:
            conn.execute(
                """
                UPDATE users
                SET establishment_id = ?,
                    first_name = 'Admin',
                    last_name = 'Campflow',
                    password_hash = ?,
                    role = ?,
                    active = 1,
                    must_change_password = 1
                WHERE id = ?
                """,
                (DEFAULT_ESTABLISHMENT_ID, password_hash, ADMIN_GLOBAL, row["id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO users
                    (establishment_id, first_name, last_name, email, password_hash,
                     role, active, must_change_password)
                VALUES (?, 'Admin', 'Campflow', ?, ?, ?, 1, 1)
                """,
                (DEFAULT_ESTABLISHMENT_ID, DEFAULT_ADMIN_EMAIL, password_hash, ADMIN_GLOBAL),
            )


if __name__ == "__main__":
    reset_admin()
    print(f"Compte admin réinitialisé : {DEFAULT_ADMIN_EMAIL}")
    print("Mot de passe temporaire : variable CAMPFLOW_ADMIN_PASSWORD ou 'manager' par défaut.")
