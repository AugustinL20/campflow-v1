from __future__ import annotations

from datetime import datetime

import pandas as pd

from utils.time_utils import DATETIME_FORMAT


def _parse_dt(value):
    if value is None or pd.isna(value) or value == "":
        return None
    if isinstance(value, datetime):
        return value
    return datetime.strptime(str(value), DATETIME_FORMAT)


def detect_anomalies(sessions: pd.DataFrame, manual_requests: pd.DataFrame | None = None) -> pd.DataFrame:
    columns = ["id", "employee", "service", "start_time", "end_time", "duration_hours", "source", "anomaly"]
    rows = []

    if sessions is not None and not sessions.empty:
        for _, row in sessions.iterrows():
            duration = row.get("corrected_duration_hours")
            if duration is None or pd.isna(duration):
                duration = row.get("duration_hours")

            if pd.isna(row.get("end_time")):
                rows.append({**row.to_dict(), "anomaly": "Créneau sans fin"})
            elif duration is not None and not pd.isna(duration) and float(duration) < 0.25:
                rows.append({**row.to_dict(), "anomaly": "Durée inférieure à 15 minutes"})
            elif duration is not None and not pd.isna(duration) and float(duration) > 10:
                rows.append({**row.to_dict(), "anomaly": "Durée supérieure à 10 heures"})

        comparable = sessions.dropna(subset=["start_time", "end_time"]).copy()
        if "employee_id" in comparable.columns:
            for employee_id, group in comparable.groupby("employee_id"):
                ordered = group.sort_values("start_time")
                previous = None
                for _, current in ordered.iterrows():
                    if previous is not None:
                        previous_end = _parse_dt(previous.get("end_time"))
                        current_start = _parse_dt(current.get("start_time"))
                        if previous_end and current_start and current_start < previous_end:
                            rows.append(
                                {
                                    **current.to_dict(),
                                    "anomaly": (
                                        "Chevauchement avec "
                                        f"{previous.get('service')} commencé à {str(previous.get('start_time'))[11:16]}"
                                    ),
                                }
                            )
                    previous = current

    if manual_requests is not None and not manual_requests.empty:
        for _, row in manual_requests.iterrows():
            reason = str(row.get("reason") or "").strip()
            if not reason:
                rows.append(
                    {
                        "id": row.get("id"),
                        "employee": row.get("employee"),
                        "service": row.get("service"),
                        "start_time": row.get("requested_start_time"),
                        "end_time": row.get("requested_end_time"),
                        "duration_hours": row.get("requested_duration_hours"),
                        "source": "Demande manuelle",
                        "anomaly": "Demande manuelle sans raison",
                    }
                )

    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows)
