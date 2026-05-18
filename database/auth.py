from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from database.context import ALL_ESTABLISHMENTS_ID, default_establishment_id
from database.audit import log_audit_event
from database.db import get_connection
from utils.app_logging import log_info, log_warning

try:
    from flask import has_request_context, session as flask_session
except Exception:  # pragma: no cover - Flask is always available at runtime
    has_request_context = lambda: False  # type: ignore[assignment]
    flask_session = None  # type: ignore[assignment]

ADMIN_GLOBAL = "admin_global"
RESPONSABLE_ETABLISSEMENT = "responsable_etablissement"
DEFAULT_ADMIN_EMAIL = "admin@campflow.local"
DEFAULT_ADMIN_PASSWORD = "manager"
SESSION_HOURS = 8
MANAGER_SESSION_KEY = "campflow_manager_auth"

_HASH_PREFIX = "pbkdf2_sha256"
_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), _ITERATIONS)
    return f"{_HASH_PREFIX}${_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        prefix, iterations, salt, expected = password_hash.split("$", 3)
        if prefix != _HASH_PREFIX:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except (AttributeError, TypeError, ValueError):
        return False


def ensure_default_admin_user() -> None:
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
        if count:
            row = conn.execute(
                "SELECT id, password_hash, must_change_password FROM users WHERE lower(email) = lower(?)",
                (DEFAULT_ADMIN_EMAIL,),
            ).fetchone()
            if row and verify_password(DEFAULT_ADMIN_PASSWORD, row["password_hash"]) and not row["must_change_password"]:
                conn.execute("UPDATE users SET must_change_password = 1 WHERE id = ?", (row["id"],))
            return
        conn.execute(
            """
            INSERT INTO users
                (establishment_id, first_name, last_name, email, password_hash, role, active, must_change_password)
            VALUES (?, 'Admin', 'Campflow', ?, ?, ?, 1, 1)
            """,
            (
                default_establishment_id(),
                DEFAULT_ADMIN_EMAIL,
                hash_password(DEFAULT_ADMIN_PASSWORD),
                ADMIN_GLOBAL,
            ),
        )
    log_info(f"Compte responsable par défaut créé : {DEFAULT_ADMIN_EMAIL}")


def authenticate_user(email: str | None, password: str | None) -> dict | None:
    normalized_email = _normalize_email(email)
    if not normalized_email or not password:
        log_warning("Login responsable refusé : identifiants incomplets")
        return None
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT u.*, e.name AS establishment_name
            FROM users u
            LEFT JOIN establishments e ON e.id = u.establishment_id
            WHERE lower(u.email) = lower(?) AND u.active = 1
            """,
            (normalized_email,),
        ).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        log_warning(f"Login responsable refusé : {normalized_email}")
        return None
    user = _public_user(dict(row))
    user.update(_session_metadata())
    _save_manager_session(user)
    log_info(f"Login responsable réussi : {normalized_email}")
    return user


def list_manager_users(establishment_id: int | None = None) -> list[dict]:
    with get_connection() as conn:
        where = ""
        params: tuple = ()
        if establishment_id not in (None, ALL_ESTABLISHMENTS_ID):
            where = "WHERE u.establishment_id = ? OR u.role = ?"
            params = (establishment_id, ADMIN_GLOBAL)
        rows = conn.execute(
            f"""
            SELECT u.id, u.establishment_id, e.name AS establishment_name,
                   u.first_name, u.last_name, u.email, u.role, u.active, u.created_at
            FROM users u
            LEFT JOIN establishments e ON e.id = u.establishment_id
            {where}
            ORDER BY u.active DESC, u.last_name, u.first_name
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def create_manager_user(
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    establishment_id: int | None = None,
    actor_user_id: int | None = None,
) -> int:
    first_name = first_name.strip().title()
    last_name = last_name.strip().title()
    normalized_email = _normalize_email(email)
    if not first_name or not last_name or not normalized_email or not password:
        raise ValueError("Tous les champs responsable sont obligatoires.")
    establishment_id = establishment_id or default_establishment_id()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO users
                (establishment_id, first_name, last_name, email, password_hash, role, active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (
                establishment_id,
                first_name,
                last_name,
                normalized_email,
                hash_password(password),
                RESPONSABLE_ETABLISSEMENT,
            ),
        )
        user_id = int(cur.lastrowid)
    log_info(f"Responsable créé : {normalized_email}")
    log_audit_event(
        action="manager_user_created",
        entity_type="user",
        entity_id=user_id,
        establishment_id=establishment_id,
        actor_user_id=actor_user_id,
        new_value={
            "email": normalized_email,
            "first_name": first_name,
            "last_name": last_name,
            "role": RESPONSABLE_ETABLISSEMENT,
            "active": 1,
        },
    )
    return user_id


def deactivate_manager_user(
    user_id: int,
    establishment_id: int | None = None,
    actor_user_id: int | None = None,
) -> None:
    with get_connection() as conn:
        if establishment_id in (None, ALL_ESTABLISHMENTS_ID):
            row = conn.execute("SELECT id, establishment_id, email, active FROM users WHERE id = ?", (user_id,)).fetchone()
            conn.execute("UPDATE users SET active = 0 WHERE id = ?", (user_id,))
        else:
            row = conn.execute(
                "SELECT id, establishment_id, email, active FROM users WHERE id = ? AND establishment_id = ?",
                (user_id, establishment_id),
            ).fetchone()
            conn.execute(
                "UPDATE users SET active = 0 WHERE id = ? AND establishment_id = ? AND role != ?",
                (user_id, establishment_id, ADMIN_GLOBAL),
            )
    if row:
        log_info(f"Responsable désactivé : {row['email']}")
        log_audit_event(
            action="manager_user_deactivated",
            entity_type="user",
            entity_id=user_id,
            establishment_id=row["establishment_id"],
            actor_user_id=actor_user_id,
            old_value={"email": row["email"], "active": row["active"]},
            new_value={"active": 0},
        )


def change_manager_password(user_id: int, new_password: str, establishment_id: int | None = None) -> None:
    if not is_password_allowed(new_password):
        log_warning(f"Tentative changement mot de passe refusée : user {user_id}")
        raise ValueError(password_policy_message(new_password))
    with get_connection() as conn:
        if establishment_id in (None, ALL_ESTABLISHMENTS_ID):
            row = conn.execute("SELECT email, password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
            if row and verify_password(new_password, row["password_hash"]):
                log_warning(f"Tentative changement mot de passe refusée : mot de passe identique pour {row['email']}")
                raise ValueError("Le nouveau mot de passe doit être différent de l’ancien.")
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_password), user_id))
        else:
            row = conn.execute(
                "SELECT email, password_hash FROM users WHERE id = ? AND establishment_id = ?",
                (user_id, establishment_id),
            ).fetchone()
            if row and verify_password(new_password, row["password_hash"]):
                log_warning(f"Tentative changement mot de passe refusée : mot de passe identique pour {row['email']}")
                raise ValueError("Le nouveau mot de passe doit être différent de l’ancien.")
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ? AND establishment_id = ?",
                (hash_password(new_password), user_id, establishment_id),
            )
    if row:
        log_info(f"Mot de passe responsable modifié : {row['email']}")


def change_own_password(user_id: int, current_password: str | None, new_password: str | None) -> dict:
    if not is_password_allowed(new_password):
        log_warning(f"Tentative changement mot de passe refusée : user {user_id}")
        raise ValueError(password_policy_message(new_password))
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT u.*, e.name AS establishment_name
            FROM users u
            LEFT JOIN establishments e ON e.id = u.establishment_id
            WHERE u.id = ? AND u.active = 1
            """,
            (user_id,),
        ).fetchone()
        if not row:
            log_warning(f"Tentative changement mot de passe refusée : user inconnu {user_id}")
            raise ValueError("Session invalide.")
        if not verify_password(current_password or "", row["password_hash"]):
            log_warning(f"Tentative changement mot de passe refusée : ancien mot de passe invalide pour {row['email']}")
            raise ValueError("Ancien mot de passe incorrect.")
        if verify_password(new_password or "", row["password_hash"]):
            log_warning(f"Tentative changement mot de passe refusée : mot de passe identique pour {row['email']}")
            raise ValueError("Le nouveau mot de passe doit être différent de l’ancien.")
        conn.execute(
            """
            UPDATE users
            SET password_hash = ?, must_change_password = 0
            WHERE id = ?
            """,
            (updated_hash := hash_password(new_password or ""), user_id),
        )
        updated = dict(row)
        updated["password_hash"] = updated_hash
        updated["must_change_password"] = 0
    user = _public_user(updated)
    user.update(_session_metadata())
    _save_manager_session(user)
    log_info(f"Changement mot de passe réussi : {user['email']}")
    return user


def is_password_allowed(password: str | None) -> bool:
    text = str(password or "")
    return len(text) >= 8 and text != DEFAULT_ADMIN_PASSWORD


def password_policy_message(password: str | None) -> str:
    text = str(password or "")
    if text == DEFAULT_ADMIN_PASSWORD:
        return "Le mot de passe temporaire “manager” est interdit."
    if len(text) < 8:
        return "Le mot de passe doit contenir au moins 8 caractères."
    return "Mot de passe refusé."


def is_session_valid(user: dict | None) -> bool:
    if not user or not user.get("authenticated"):
        return False
    expires_at = user.get("expires_at")
    if not expires_at:
        return False
    try:
        if datetime.fromisoformat(expires_at) <= datetime.utcnow():
            log_warning(f"Session responsable expirée : {user.get('email', 'inconnu')}")
            return False
    except (TypeError, ValueError):
        return False
    return True


def is_manager_access_allowed(user: dict | None) -> bool:
    return is_session_valid(user) and not bool(user.get("must_change_password"))


def logout_user(user: dict | None) -> None:
    if user and user.get("email"):
        log_info(f"Déconnexion responsable : {user['email']}")
    _clear_manager_session()


def user_establishment_scope(user: dict | None) -> int:
    if not user:
        return default_establishment_id()
    if user.get("role") == ADMIN_GLOBAL:
        return ALL_ESTABLISHMENTS_ID
    return int(user.get("establishment_id") or default_establishment_id())


def _public_user(row: dict) -> dict:
    row.pop("password_hash", None)
    return {
        "id": int(row["id"]),
        "establishment_id": row.get("establishment_id"),
        "establishment_name": row.get("establishment_name") or "",
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "email": row["email"],
        "role": row["role"],
        "active": bool(row["active"]),
        "must_change_password": bool(row.get("must_change_password")),
    }


def _normalize_email(email: str | None) -> str:
    return str(email or "").strip().lower()


def _session_metadata() -> dict:
    now = datetime.utcnow()
    return {
        "authenticated": True,
        "login_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=SESSION_HOURS)).isoformat(),
    }


def _save_manager_session(user: dict) -> None:
    if not has_request_context() or flask_session is None:
        return
    flask_session[MANAGER_SESSION_KEY] = {
        key: user.get(key)
        for key in (
            "id",
            "establishment_id",
            "establishment_name",
            "first_name",
            "last_name",
            "email",
            "role",
            "active",
            "must_change_password",
            "authenticated",
            "login_at",
            "expires_at",
        )
    }


def load_manager_session() -> dict | None:
    if not has_request_context() or flask_session is None:
        return None
    data = flask_session.get(MANAGER_SESSION_KEY)
    return dict(data) if data else None


def _clear_manager_session() -> None:
    if not has_request_context() or flask_session is None:
        return
    flask_session.pop(MANAGER_SESSION_KEY, None)
