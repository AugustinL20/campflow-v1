from __future__ import annotations

import pandas as pd
import secrets

from database.audit import log_audit_event
from database.context import ALL_ESTABLISHMENTS_ID, default_establishment_id, is_all_establishments_scope
from database.db import get_connection
from utils.app_logging import log_info
from utils.time_utils import date_time_to_db, display_time, duration_hours, html_to_db, now_local, to_db, week_bounds

PENDING_SCAN = "En attente de validation"
PENDING_MANUAL = "Demande manuelle en attente"
VALIDATED = "Validé"
CORRECTED = "Corrigé"
REFUSED = "Refusé"


def fetch_df(query: str, params: tuple = ()) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def list_establishments() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM establishments WHERE active = 1 ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def list_services(establishment_id: int | None = None) -> list[dict]:
    establishment_id = establishment_id or default_establishment_id()
    with get_connection() as conn:
        if is_all_establishments_scope(establishment_id):
            rows = conn.execute("SELECT * FROM services ORDER BY establishment_id, id").fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM services
                WHERE establishment_id = ?
                ORDER BY id
                """,
                (establishment_id,),
            ).fetchall()
    return [dict(row) for row in rows]


def get_service_by_slug(slug: str, establishment_id: int | None = None) -> dict | None:
    params: tuple = (slug,)
    where_establishment = ""
    if establishment_id:
        where_establishment = "AND establishment_id = ?"
        params = (slug, establishment_id)
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT * FROM services WHERE qr_token = ? {where_establishment}",
            params,
        ).fetchone()
    return dict(row) if row else None


def get_service_by_id(service_id: int, establishment_id: int | None = None) -> dict | None:
    establishment_id = establishment_id or default_establishment_id()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM services WHERE id = ? AND establishment_id = ?",
            (service_id, establishment_id),
        ).fetchone()
    return dict(row) if row else None


def rotate_service_qr_token(service_slug: str, establishment_id: int | None = None) -> dict:
    establishment_id = establishment_id or default_establishment_id()
    token = secrets.token_urlsafe(16)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM services WHERE qr_slug = ? AND establishment_id = ?",
            (service_slug, establishment_id),
        ).fetchone()
        if not row:
            raise ValueError("Service inconnu.")
        conn.execute("UPDATE services SET qr_token = ? WHERE id = ?", (token, row["id"]))
        updated = conn.execute("SELECT * FROM services WHERE id = ?", (row["id"],)).fetchone()
    return dict(updated)


def list_active_employees(establishment_id: int | None = None) -> list[dict]:
    establishment_id = establishment_id or default_establishment_id()
    with get_connection() as conn:
        if is_all_establishments_scope(establishment_id):
            rows = conn.execute(
                """
                SELECT * FROM employees
                WHERE active = 1
                ORDER BY establishment_id, last_name, first_name
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM employees
                WHERE active = 1 AND establishment_id = ?
                ORDER BY last_name, first_name
                """,
                (establishment_id,),
            ).fetchall()
    return [dict(row) for row in rows]


def create_employee(
    first_name: str,
    last_name: str,
    role: str = "saisonnier",
    weekly_target_hours: float = 35,
    establishment_id: int | None = None,
) -> int:
    establishment_id = establishment_id or default_establishment_id()
    first_name = first_name.strip().title()
    last_name = last_name.strip().title()
    role = role if role in ("saisonnier", "responsable") else "saisonnier"
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id FROM employees
            WHERE establishment_id = ?
              AND lower(first_name) = lower(?)
              AND lower(last_name) = lower(?)
            """,
            (establishment_id, first_name, last_name),
        ).fetchone()
        if row:
            conn.execute(
                """
                UPDATE employees
                SET role = ?, active = 1, weekly_target_hours = ?
                WHERE id = ?
                """,
                (role, weekly_target_hours, row["id"]),
            )
            return int(row["id"])
        cur = conn.execute(
            """
            INSERT INTO employees (establishment_id, first_name, last_name, role, active, weekly_target_hours)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (establishment_id, first_name, last_name, role, weekly_target_hours),
        )
        return int(cur.lastrowid)


def deactivate_employee(
    employee_id: int,
    establishment_id: int | None = None,
    actor_user_id: int | None = None,
) -> None:
    establishment_id = establishment_id or default_establishment_id()
    with get_connection() as conn:
        if is_all_establishments_scope(establishment_id):
            old = conn.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
            conn.execute("UPDATE employees SET active = 0 WHERE id = ?", (employee_id,))
        else:
            old = conn.execute(
                "SELECT * FROM employees WHERE id = ? AND establishment_id = ?",
                (employee_id, establishment_id),
            ).fetchone()
            conn.execute(
                "UPDATE employees SET active = 0 WHERE id = ? AND establishment_id = ?",
                (employee_id, establishment_id),
            )
    if old:
        log_audit_event(
            action="employee_deactivated",
            entity_type="employee",
            entity_id=employee_id,
            establishment_id=int(old["establishment_id"]),
            actor_user_id=actor_user_id,
            old_value={"active": old["active"]},
            new_value={"active": 0},
        )


def update_employee_weekly_target(
    employee_id: int,
    weekly_target_hours: float,
    establishment_id: int | None = None,
    actor_user_id: int | None = None,
) -> None:
    establishment_id = establishment_id or default_establishment_id()
    with get_connection() as conn:
        if is_all_establishments_scope(establishment_id):
            old = conn.execute(
                "SELECT id, establishment_id, weekly_target_hours FROM employees WHERE id = ? AND active = 1",
                (employee_id,),
            ).fetchone()
            conn.execute(
                """
                UPDATE employees
                SET weekly_target_hours = ?
                WHERE id = ? AND active = 1
                """,
                (weekly_target_hours, employee_id),
            )
        else:
            old = conn.execute(
                """
                SELECT id, establishment_id, weekly_target_hours FROM employees
                WHERE id = ? AND active = 1 AND establishment_id = ?
                """,
                (employee_id, establishment_id),
            ).fetchone()
            conn.execute(
                """
                UPDATE employees
                SET weekly_target_hours = ?
                WHERE id = ? AND active = 1 AND establishment_id = ?
                """,
                (weekly_target_hours, employee_id, establishment_id),
            )
    if old:
        log_audit_event(
            action="employee_weekly_target_updated",
            entity_type="employee",
            entity_id=employee_id,
            establishment_id=int(old["establishment_id"]),
            actor_user_id=actor_user_id,
            old_value={"weekly_target_hours": old["weekly_target_hours"]},
            new_value={"weekly_target_hours": weekly_target_hours},
        )


def create_manager_work_session(
    employee_id: int,
    service_id: int,
    date_value: str,
    start_time: str,
    end_time: str,
    status: str,
    corrected_hours: float | None,
    comment: str,
    establishment_id: int | None = None,
    actor_user_id: int | None = None,
) -> int:
    establishment_id = establishment_id or default_establishment_id()
    start_db = date_time_to_db(date_value, start_time)
    end_db = date_time_to_db(date_value, end_time)
    hours = duration_hours(start_db, end_db)
    if hours <= 0:
        raise ValueError("La fin doit être après le début.")
    if status not in (PENDING_SCAN, VALIDATED, CORRECTED, REFUSED):
        status = VALIDATED
    if corrected_hours is not None:
        status = CORRECTED
    if status == CORRECTED and corrected_hours is None:
        corrected_hours = hours
    with get_connection() as conn:
        establishment_id = _ensure_employee_and_service_in_establishment(conn, employee_id, service_id, establishment_id)
        cur = conn.execute(
            """
            INSERT INTO work_sessions
                (establishment_id, employee_id, service_id, start_time, end_time, duration_hours, source,
                 validation_status, manager_comment, corrected_duration_hours)
            VALUES (?, ?, ?, ?, ?, ?, 'manual', ?, ?, ?)
            """,
            (
                establishment_id,
                employee_id,
                service_id,
                start_db,
                end_db,
                hours,
                status,
                comment.strip() or None,
                corrected_hours,
            ),
        )
        work_session_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO validation_logs
                (establishment_id, actor_user_id, work_session_id, action, old_value, new_value, manager_comment)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (establishment_id, actor_user_id, work_session_id, status, "", str(corrected_hours or hours), comment.strip()),
        )
    log_audit_event(
        action="manager_work_session_created",
        entity_type="work_session",
        entity_id=work_session_id,
        establishment_id=establishment_id,
        actor_user_id=actor_user_id,
        old_value=None,
        new_value={
            "employee_id": employee_id,
            "service_id": service_id,
            "start_time": start_db,
            "end_time": end_db,
            "duration_hours": hours,
            "corrected_duration_hours": corrected_hours,
            "validation_status": status,
        },
        comment=comment,
    )
    return work_session_id


def get_or_create_employee(first_name: str, last_name: str, establishment_id: int | None = None) -> int:
    establishment_id = establishment_id or default_establishment_id()
    first_name = first_name.strip().title()
    last_name = last_name.strip().title()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id FROM employees
            WHERE establishment_id = ?
              AND lower(first_name) = lower(?)
              AND lower(last_name) = lower(?)
            """,
            (establishment_id, first_name, last_name),
        ).fetchone()
        if row:
            return int(row["id"])
        cur = conn.execute(
            """
            INSERT INTO employees (establishment_id, first_name, last_name, role, active)
            VALUES (?, ?, ?, 'saisonnier', 1)
            """,
            (establishment_id, first_name, last_name),
        )
        return int(cur.lastrowid)


def get_open_session(employee_id: int, service_id: int, establishment_id: int | None = None) -> dict | None:
    establishment_id = establishment_id or default_establishment_id()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM work_sessions
            WHERE establishment_id = ?
              AND employee_id = ?
              AND service_id = ?
              AND source = 'qr_scan'
              AND end_time IS NULL
              AND validation_status = ?
            ORDER BY start_time DESC
            LIMIT 1
            """,
            (establishment_id, employee_id, service_id, PENDING_SCAN),
        ).fetchone()
    return dict(row) if row else None


def get_any_open_session(employee_id: int, establishment_id: int | None = None) -> dict | None:
    establishment_id = establishment_id or default_establishment_id()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT ws.*, s.name AS service
            FROM work_sessions ws
            JOIN services s ON s.id = ws.service_id
            WHERE ws.establishment_id = ?
              AND ws.employee_id = ?
              AND ws.source = 'qr_scan'
              AND ws.end_time IS NULL
              AND ws.validation_status = ?
            ORDER BY ws.start_time DESC
            LIMIT 1
            """,
            (establishment_id, employee_id, PENDING_SCAN),
        ).fetchone()
    return dict(row) if row else None


def get_next_punch_action(
    employee_id: int | None,
    service_id: int | None,
    establishment_id: int | None = None,
) -> str:
    if not employee_id or not service_id:
        return "commencer"
    return "terminer" if get_open_session(int(employee_id), int(service_id), establishment_id) else "commencer"


def record_qr_punch(
    employee_id: int,
    service_id: int,
    punch_type: str,
    establishment_id: int | None = None,
) -> tuple[bool, str]:
    establishment_id = establishment_id or default_establishment_id()
    timestamp = to_db(now_local())
    with get_connection() as conn:
        _ensure_employee_and_service_in_establishment(conn, employee_id, service_id, establishment_id)
        same_open_session = conn.execute(
            """
            SELECT id, start_time FROM work_sessions
            WHERE establishment_id = ?
              AND employee_id = ?
              AND service_id = ?
              AND source = 'qr_scan'
              AND end_time IS NULL
              AND validation_status = ?
            ORDER BY start_time DESC
            LIMIT 1
            """,
            (establishment_id, employee_id, service_id, PENDING_SCAN),
        ).fetchone()

        conn.execute(
            "BEGIN"
        )
        if punch_type == "arrivee":
            if same_open_session:
                return False, "Vous avez déjà commencé ce service. Terminez-le avant de le recommencer."

            other_open_session = conn.execute(
                """
                SELECT ws.start_time, s.name AS service
                FROM work_sessions ws
                JOIN services s ON s.id = ws.service_id
                WHERE ws.establishment_id = ?
                  AND ws.employee_id = ?
                  AND ws.service_id != ?
                  AND ws.source = 'qr_scan'
                  AND ws.end_time IS NULL
                  AND ws.validation_status = ?
                ORDER BY ws.start_time DESC
                LIMIT 1
                """,
                (establishment_id, employee_id, service_id, PENDING_SCAN),
            ).fetchone()
            if other_open_session:
                return (
                    False,
                    "Attention : vous avez déjà un service "
                    f"{other_open_session['service']} ouvert depuis {display_time(other_open_session['start_time'])}. "
                    "Terminez-le avant de commencer un autre service.",
                )

            conn.execute(
                """
                INSERT INTO punches (establishment_id, employee_id, service_id, punch_type, timestamp, source, status)
                VALUES (?, ?, ?, 'arrivee', ?, 'qr_scan', ?)
                """,
                (establishment_id, employee_id, service_id, timestamp, PENDING_SCAN),
            )
            conn.execute(
                """
                INSERT INTO work_sessions
                    (establishment_id, employee_id, service_id, start_time, source, validation_status)
                VALUES (?, ?, ?, ?, 'qr_scan', ?)
                """,
                (establishment_id, employee_id, service_id, timestamp, PENDING_SCAN),
            )
            log_info(f"Pointage créé : employé {employee_id}, service {service_id}, arrivée {timestamp}")
            return True, f"Service commencé à {display_time(timestamp)}."

        if not same_open_session:
            return False, "Impossible de terminer ce service : aucun service ouvert n'a été trouvé."

        conn.execute(
            """
            INSERT INTO punches (establishment_id, employee_id, service_id, punch_type, timestamp, source, status)
            VALUES (?, ?, ?, 'depart', ?, 'qr_scan', ?)
            """,
            (establishment_id, employee_id, service_id, timestamp, PENDING_SCAN),
        )
        hours = duration_hours(same_open_session["start_time"], timestamp)
        conn.execute(
            """
            UPDATE work_sessions
            SET end_time = ?, duration_hours = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (timestamp, hours, same_open_session["id"]),
        )
        log_info(
            "Pointage créé : "
            f"employé {employee_id}, service {service_id}, départ {timestamp}, durée {hours:.2f}h"
        )
        return True, f"Service terminé à {display_time(timestamp)}. Votre pointage a bien été enregistré."


def record_smart_qr_punch(
    employee_id: int,
    service_id: int,
    establishment_id: int | None = None,
) -> tuple[bool, str, str]:
    establishment_id = establishment_id or default_establishment_id()
    action = get_next_punch_action(employee_id, service_id, establishment_id)
    punch_type = "depart" if action == "terminer" else "arrivee"
    ok, text = record_qr_punch(employee_id, service_id, punch_type, establishment_id)
    return ok, text, action


def create_manual_request(
    employee_id: int,
    service_id: int,
    requested_start_time: str,
    requested_end_time: str,
    reason: str,
    establishment_id: int | None = None,
) -> int:
    establishment_id = establishment_id or default_establishment_id()
    start_db = html_to_db(requested_start_time)
    end_db = html_to_db(requested_end_time)
    hours = duration_hours(start_db, end_db)
    with get_connection() as conn:
        _ensure_employee_and_service_in_establishment(conn, employee_id, service_id, establishment_id)
        cur = conn.execute(
            """
            INSERT INTO manual_time_requests
                (establishment_id, employee_id, service_id, requested_start_time, requested_end_time,
                 requested_duration_hours, reason, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (establishment_id, employee_id, service_id, start_db, end_db, hours, reason.strip(), PENDING_MANUAL),
        )
        return int(cur.lastrowid)


def create_manual_request_from_parts(
    employee_id: int,
    service_id: int,
    date_value: str,
    start_time: str,
    end_time: str,
    reason: str,
    establishment_id: int | None = None,
) -> int:
    establishment_id = establishment_id or default_establishment_id()
    start_db = date_time_to_db(date_value, start_time)
    end_db = date_time_to_db(date_value, end_time)
    hours = duration_hours(start_db, end_db)
    with get_connection() as conn:
        _ensure_employee_and_service_in_establishment(conn, employee_id, service_id, establishment_id)
        cur = conn.execute(
            """
            INSERT INTO manual_time_requests
                (establishment_id, employee_id, service_id, requested_start_time, requested_end_time,
                 requested_duration_hours, reason, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (establishment_id, employee_id, service_id, start_db, end_db, hours, reason.strip(), PENDING_MANUAL),
        )
        return int(cur.lastrowid)


def today_punches_for_employee(employee_id: int | None, establishment_id: int | None = None) -> pd.DataFrame:
    if not employee_id:
        return pd.DataFrame(columns=["time", "service", "action"])
    establishment_id = establishment_id or default_establishment_id()
    today = now_local().strftime("%Y-%m-%d")
    return fetch_df(
        """
        SELECT substr(p.timestamp, 12, 5) AS time,
               s.name AS service,
               CASE
                   WHEN p.punch_type = 'arrivee' THEN 'commencé'
                   ELSE 'terminé'
               END AS action
        FROM punches p
        JOIN services s ON s.id = p.service_id
        WHERE p.establishment_id = ?
          AND p.employee_id = ?
          AND date(p.timestamp) = ?
        ORDER BY p.timestamp ASC
        """,
        (establishment_id, employee_id, today),
    )


def source_label(source: str, status: str | None = None) -> str:
    if status == CORRECTED:
        return "Correction responsable"
    if source == "manual":
        return "Demande manuelle"
    return "Scan QR"


def status_label(status: str) -> str:
    return {
        PENDING_SCAN: "En attente",
        PENDING_MANUAL: "Demande manuelle en attente",
        VALIDATED: "Validé",
        CORRECTED: "Corrigé",
        REFUSED: "Refusé",
    }.get(status, status)


def decorate_sessions(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    decorated = df.copy()
    decorated.loc[:, "source"] = decorated.apply(lambda row: source_label(row.get("source"), row.get("validation_status")), axis=1)
    decorated.loc[:, "validation_status"] = decorated["validation_status"].map(status_label).fillna(decorated["validation_status"])
    if "end_time" in decorated.columns:
        decorated.loc[decorated["end_time"].isna(), "validation_status"] = "Incomplet"
    return decorated


def decorate_manual_requests(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    decorated = df.copy()
    decorated.loc[:, "source"] = "Demande manuelle"
    decorated.loc[:, "status"] = decorated["status"].map(status_label).fillna(decorated["status"])
    return decorated


def pending_sessions_df(establishment_id: int | None = None) -> pd.DataFrame:
    establishment_id = establishment_id or default_establishment_id()
    where_scope = "WHERE" if is_all_establishments_scope(establishment_id) else "WHERE ws.establishment_id = ? AND"
    params = (PENDING_SCAN,) if is_all_establishments_scope(establishment_id) else (establishment_id, PENDING_SCAN)
    return decorate_sessions(fetch_df(
        f"""
        SELECT ws.id, e.first_name || ' ' || e.last_name AS employee, s.name AS service,
               ws.start_time, ws.end_time, ws.duration_hours, ws.source,
               ws.validation_status, ws.manager_comment, ws.corrected_duration_hours
        FROM work_sessions ws
        JOIN employees e ON e.id = ws.employee_id
        JOIN services s ON s.id = ws.service_id
        {where_scope} ws.validation_status = ?
        ORDER BY ws.start_time DESC
        """,
        params,
    ))


def manual_requests_df(status: str | None = None, establishment_id: int | None = None) -> pd.DataFrame:
    establishment_id = establishment_id or default_establishment_id()
    filters = []
    params = []
    if not is_all_establishments_scope(establishment_id):
        filters.append("m.establishment_id = ?")
        params.append(establishment_id)
    if status:
        filters.append("m.status = ?")
        params.append(status)
    where = "WHERE " + " AND ".join(filters) if filters else ""
    return decorate_manual_requests(fetch_df(
        f"""
        SELECT m.id, e.first_name || ' ' || e.last_name AS employee, s.name AS service,
               m.requested_start_time, m.requested_end_time, m.requested_duration_hours,
               m.reason, m.status, m.manager_comment, m.created_at, m.reviewed_at
        FROM manual_time_requests m
        JOIN employees e ON e.id = m.employee_id
        JOIN services s ON s.id = m.service_id
        {where}
        ORDER BY m.created_at DESC
        """,
        tuple(params),
    ))


def dashboard_metrics(establishment_id: int | None = None) -> dict[str, pd.DataFrame | int]:
    establishment_id = establishment_id or default_establishment_id()
    start, end = week_bounds()
    session_scope = "" if is_all_establishments_scope(establishment_id) else "ws.establishment_id = ? AND"
    session_params = (start, end) if is_all_establishments_scope(establishment_id) else (establishment_id, start, end)
    sessions = fetch_df(
        f"""
        SELECT ws.*, e.first_name || ' ' || e.last_name AS employee, s.name AS service
        FROM work_sessions ws
        JOIN employees e ON e.id = ws.employee_id
        JOIN services s ON s.id = ws.service_id
        WHERE {session_scope} ws.start_time >= ? AND ws.start_time < ?
        """,
        session_params,
    )
    manual = manual_requests_df(establishment_id=establishment_id)
    if is_all_establishments_scope(establishment_id):
        logs = fetch_df("SELECT * FROM validation_logs ORDER BY timestamp DESC LIMIT 50")
    else:
        logs = fetch_df(
            """
            SELECT * FROM validation_logs
            WHERE establishment_id = ?
            ORDER BY timestamp DESC
            LIMIT 50
            """,
            (establishment_id,),
        )
    pending = int((sessions["validation_status"] == PENDING_SCAN).sum()) if not sessions.empty else 0
    open_sessions = int(sessions["end_time"].isna().sum()) if not sessions.empty else 0
    return {
        "sessions": decorate_sessions(sessions),
        "manual": manual,
        "logs": logs,
        "pending_count": pending,
        "open_sessions_count": open_sessions,
    }


def sessions_for_week(status: str | None = None, establishment_id: int | None = None) -> pd.DataFrame:
    establishment_id = establishment_id or default_establishment_id()
    start, end = week_bounds()
    where_status = "AND ws.validation_status = ?" if status else ""
    where_scope = "" if is_all_establishments_scope(establishment_id) else "ws.establishment_id = ? AND"
    if is_all_establishments_scope(establishment_id):
        params = (start, end, status) if status else (start, end)
    else:
        params = (establishment_id, start, end, status) if status else (establishment_id, start, end)
    return decorate_sessions(fetch_df(
        f"""
        SELECT ws.id, ws.employee_id, e.first_name || ' ' || e.last_name AS employee, s.name AS service,
               ws.start_time, ws.end_time, ws.duration_hours, ws.corrected_duration_hours,
               ws.source, ws.validation_status, ws.manager_comment
        FROM work_sessions ws
        JOIN employees e ON e.id = ws.employee_id
        JOIN services s ON s.id = ws.service_id
        WHERE {where_scope} ws.start_time >= ? AND ws.start_time < ? {where_status}
        ORDER BY ws.start_time DESC
        """,
        params,
    ))


def decide_session(
    session_id: int,
    action: str,
    corrected_hours: float | None,
    comment: str,
    establishment_id: int | None = None,
    actor_user_id: int | None = None,
) -> None:
    establishment_id = establishment_id or default_establishment_id()
    status = {"validate": VALIDATED, "correct": CORRECTED, "refuse": REFUSED}[action]
    with get_connection() as conn:
        if is_all_establishments_scope(establishment_id):
            old = conn.execute("SELECT * FROM work_sessions WHERE id = ?", (session_id,)).fetchone()
            if old:
                establishment_id = int(old["establishment_id"])
        else:
            old = conn.execute(
                "SELECT * FROM work_sessions WHERE id = ? AND establishment_id = ?",
                (session_id, establishment_id),
            ).fetchone()
        if not old:
            return
        conn.execute(
            """
            UPDATE work_sessions
            SET validation_status = ?, corrected_duration_hours = ?, manager_comment = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND establishment_id = ?
            """,
            (status, corrected_hours, comment.strip() or None, session_id, establishment_id),
        )
        conn.execute(
            """
            INSERT INTO validation_logs
                (establishment_id, actor_user_id, work_session_id, action, old_value, new_value, manager_comment)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (establishment_id, actor_user_id, session_id, status, old["validation_status"], str(corrected_hours or ""), comment.strip()),
        )
        log_info(f"Action responsable : créneau {session_id} {status.lower()}")
    log_audit_event(
        action={
            "validate": "work_session_validated",
            "correct": "work_session_corrected",
            "refuse": "work_session_refused",
        }[action],
        entity_type="work_session",
        entity_id=session_id,
        establishment_id=establishment_id,
        actor_user_id=actor_user_id,
        old_value={
            "validation_status": old["validation_status"],
            "corrected_duration_hours": old["corrected_duration_hours"],
            "manager_comment": old["manager_comment"],
        },
        new_value={
            "validation_status": status,
            "corrected_duration_hours": corrected_hours,
            "manager_comment": comment.strip() or None,
        },
        comment=comment,
    )


def decide_manual_request(
    request_id: int,
    action: str,
    corrected_hours: float | None,
    comment: str,
    establishment_id: int | None = None,
    actor_user_id: int | None = None,
) -> None:
    establishment_id = establishment_id or default_establishment_id()
    status = {"accept": VALIDATED, "correct": CORRECTED, "refuse": REFUSED}[action]
    with get_connection() as conn:
        if is_all_establishments_scope(establishment_id):
            req = conn.execute("SELECT * FROM manual_time_requests WHERE id = ?", (request_id,)).fetchone()
            if req:
                establishment_id = int(req["establishment_id"])
        else:
            req = conn.execute(
                "SELECT * FROM manual_time_requests WHERE id = ? AND establishment_id = ?",
                (request_id, establishment_id),
            ).fetchone()
        if not req:
            return
        conn.execute(
            """
            UPDATE manual_time_requests
            SET status = ?, manager_comment = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ? AND establishment_id = ?
            """,
            (status, comment.strip() or None, request_id, establishment_id),
        )
        work_session_id = None
        if action in ("accept", "correct"):
            duration = corrected_hours if corrected_hours is not None else req["requested_duration_hours"]
            cur = conn.execute(
                """
                INSERT INTO work_sessions
                    (establishment_id, employee_id, service_id, start_time, end_time, duration_hours, source,
                     validation_status, employee_comment, manager_comment, corrected_duration_hours)
                VALUES (?, ?, ?, ?, ?, ?, 'manual', ?, ?, ?, ?)
                """,
                (
                    establishment_id,
                    req["employee_id"],
                    req["service_id"],
                    req["requested_start_time"],
                    req["requested_end_time"],
                    req["requested_duration_hours"],
                    status,
                    req["reason"],
                    comment.strip() or None,
                    corrected_hours,
                ),
            )
            work_session_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO validation_logs
                (establishment_id, actor_user_id, work_session_id, manual_request_id, action, old_value, new_value, manager_comment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (establishment_id, actor_user_id, work_session_id, request_id, status, req["status"], str(corrected_hours or ""), comment.strip()),
        )
        log_info(f"Action responsable : demande manuelle {request_id} {status.lower()}")
    log_audit_event(
        action={
            "accept": "manual_request_accepted",
            "correct": "manual_request_corrected",
            "refuse": "manual_request_refused",
        }[action],
        entity_type="manual_time_request",
        entity_id=request_id,
        establishment_id=establishment_id,
        actor_user_id=actor_user_id,
        old_value={
            "status": req["status"],
            "manager_comment": req["manager_comment"],
        },
        new_value={
            "status": status,
            "corrected_duration_hours": corrected_hours,
            "work_session_id": work_session_id,
            "manager_comment": comment.strip() or None,
        },
        comment=comment,
    )


def _ensure_employee_and_service_in_establishment(conn, employee_id: int, service_id: int, establishment_id: int) -> int:
    if is_all_establishments_scope(establishment_id):
        employee = conn.execute(
            "SELECT id, establishment_id FROM employees WHERE id = ? AND active = 1",
            (employee_id,),
        ).fetchone()
        service = conn.execute(
            "SELECT id, establishment_id FROM services WHERE id = ?",
            (service_id,),
        ).fetchone()
        if employee and service and int(employee["establishment_id"]) == int(service["establishment_id"]):
            return int(employee["establishment_id"])
        raise PermissionError("Employé ou service hors établissement autorisé.")
    employee = conn.execute(
        "SELECT id FROM employees WHERE id = ? AND establishment_id = ? AND active = 1",
        (employee_id, establishment_id),
    ).fetchone()
    service = conn.execute(
        "SELECT id FROM services WHERE id = ? AND establishment_id = ?",
        (service_id, establishment_id),
    ).fetchone()
    if not employee or not service:
        raise PermissionError("Employé ou service hors établissement autorisé.")
    return establishment_id
