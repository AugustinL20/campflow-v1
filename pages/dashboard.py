from __future__ import annotations

from dash import Input, Output, html

from components.cards import metric_card
from components.layout import section
from components.tables import data_table
from database.queries import dashboard_metrics, sessions_for_week
from utils.anomaly_detection import detect_anomalies
from utils.app_logging import log_error
from utils.export_excel import export_weekly_excel


def layout():
    metrics = dashboard_metrics()
    sessions = metrics["sessions"]
    manual = metrics["manual"]
    logs = metrics["logs"]
    anomalies = detect_anomalies(sessions)

    by_employee = sessions.groupby("employee", as_index=False)["duration_hours"].sum() if not sessions.empty else sessions
    by_service = sessions.groupby("service", as_index=False)["duration_hours"].sum() if not sessions.empty else sessions

    return html.Div(
        [
            section(
                "Tableau de bord responsable",
                html.Div(
                    [
                        metric_card("Pointages en attente", metrics["pending_count"], "warning"),
                        metric_card("Oublis de départ", metrics["open_sessions_count"], "danger"),
                        metric_card("Demandes manuelles", len(manual), "neutral"),
                        metric_card("Horaires anormaux", len(anomalies), "warning"),
                    ],
                    className="metrics-grid",
                ),
            ),
            section("Heures par employé", data_table(by_employee, "hours-by-employee")),
            section("Heures par service", data_table(by_service, "hours-by-service")),
            section("Pointages et sessions semaine", data_table(sessions_for_week(), "weekly-sessions")),
            section("Demandes manuelles", data_table(manual, "all-manual-requests")),
            section("Anomalies", data_table(anomalies, "anomalies-table")),
            section("Historique corrections/refus", data_table(logs, "validation-logs")),
            section(
                "Export Excel hebdomadaire",
                html.Div(
                    [
                        html.Button("Générer l'export Excel", id="dashboard-export-week", className="primary"),
                        html.Div(id="dashboard-export-feedback"),
                    ],
                    className="form-card",
                ),
            ),
        ]
    )


def register_callbacks(app):
    @app.callback(
        Output("dashboard-export-feedback", "children"),
        Input("dashboard-export-week", "n_clicks"),
        prevent_initial_call=True,
    )
    def export_week(_):
        try:
            path = export_weekly_excel()
        except Exception as exc:
            log_error("Erreur export Excel tableau de bord", exc)
            return html.Div("L’export Excel n’a pas pu être généré. Réessayez dans un instant.", className="message error")
        return html.Div(f"Export Excel généré avec succès : {path}", className="message success")
