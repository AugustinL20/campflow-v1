from __future__ import annotations

import json
from typing import Any

import pandas as pd

from database.context import ALL_ESTABLISHMENTS_ID, default_establishment_id, is_all_establishments_scope
from database.db import get_connection


def audit_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def log_audit_event(
    *,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    establishment_id: int | None = None,
    actor_user_id: int | None = None,
    old_value: Any = None,
    new_value: Any = None,
    comment: str | None = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO audit_logs
                (establishment_id, actor_user_id, action, entity_type, entity_id,
                 old_value, new_value, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _audit_establishment_id(establishment_id),
                actor_user_id,
                action,
                entity_type,
                entity_id,
                audit_value(old_value),
                audit_value(new_value),
                (comment or "").strip() or None,
            ),
        )


def recent_audit_logs(establishment_id: int | None = None, limit: int = 50) -> pd.DataFrame:
    establishment_id = establishment_id or default_establishment_id()
    limit = max(1, min(int(limit), 200))
    scope = "" if is_all_establishments_scope(establishment_id) else "WHERE a.establishment_id = ?"
    params: tuple = (limit,) if is_all_establishments_scope(establishment_id) else (establishment_id, limit)
    with get_connection() as conn:
        return pd.read_sql_query(
            f"""
            SELECT
                a.created_at,
                COALESCE(u.email, 'Utilisateur inconnu') AS actor,
                COALESCE(e.name, 'Tous établissements') AS establishment,
                a.action,
                a.entity_type,
                a.entity_id,
                a.old_value,
                a.new_value,
                a.comment
            FROM audit_logs a
            LEFT JOIN users u ON u.id = a.actor_user_id
            LEFT JOIN establishments e ON e.id = a.establishment_id
            {scope}
            ORDER BY a.created_at DESC
            LIMIT ?
            """,
            conn,
            params=params,
        )


def _audit_establishment_id(establishment_id: int | None) -> int | None:
    if establishment_id is None or establishment_id == ALL_ESTABLISHMENTS_ID:
        return None
    return establishment_id

