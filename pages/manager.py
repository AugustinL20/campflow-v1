from __future__ import annotations

import pandas as pd
from dash import ALL, Input, Output, State, ctx, dcc, html

from config import BASE_URL, is_local_base_url
from components.cards import message, metric_card
from components.layout import section
from components.tables import data_table
from database.audit import log_audit_event, recent_audit_logs
from database.auth import (
    ADMIN_GLOBAL,
    authenticate_user,
    change_own_password,
    change_manager_password,
    create_manager_user,
    deactivate_manager_user,
    is_manager_access_allowed,
    is_session_valid,
    list_manager_users,
    load_manager_session,
    logout_user,
    restore_manager_session_from_store,
    user_establishment_scope,
)
from database.context import ALL_ESTABLISHMENTS_ID, default_establishment_id
from database.queries import (
    CORRECTED,
    PENDING_MANUAL,
    PENDING_SCAN,
    REFUSED,
    VALIDATED,
    create_employee,
    create_manager_work_session,
    dashboard_metrics,
    deactivate_employee,
    decide_manual_request,
    decide_session,
    list_active_employees,
    list_services,
    manual_requests_df,
    pending_sessions_df,
    sessions_for_week,
    update_employee_weekly_target,
)
from utils.anomaly_detection import detect_anomalies
from utils.app_logging import log_error, log_warning
from utils.backups import create_database_backup
from utils.export_excel import export_weekly_csv, export_weekly_excel
from utils.qr_generator import generate_printable_html, generate_qr_code_for_service, generate_qr_codes, printable_cards
from utils.rate_limit import is_rate_limited


def layout():
    return html.Div(
        [
            dcc.Store(id="manager-auth", storage_type="session"),
            html.Div(id="manager-login"),
            html.Div(id="manager-content"),
        ]
    )


def login_panel():
    return section(
        "Espace responsable",
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Email"),
                        dcc.Input(id="manager-email", type="email", placeholder="admin@campflow.local"),
                    ],
                    className="field",
                ),
                html.Div(
                    [
                        html.Label("Mot de passe"),
                        dcc.Input(id="manager-password", type="password", placeholder="Mot de passe"),
                    ],
                    className="field",
                ),
                html.Button("Entrer", id="manager-login-button", className="primary full-width"),
                html.Div(id="manager-login-error"),
            ],
            className="login-card",
        ),
        "Compte par défaut : admin@campflow.local / manager.",
    )


def change_password_panel(auth: dict | None, feedback=None):
    name = f"{(auth or {}).get('first_name', '')} {(auth or {}).get('last_name', '')}".strip()
    return section(
        "Changer mon mot de passe",
        html.Div(
            [
                html.P(
                    f"Compte : {name or (auth or {}).get('email', '')}",
                    className="manager-help",
                ),
                html.Div(
                    [
                        html.Label("Mot de passe actuel"),
                        dcc.Input(id="current-password", type="password", placeholder="Mot de passe actuel"),
                    ],
                    className="field",
                ),
                html.Div(
                    [
                        html.Label("Nouveau mot de passe"),
                        dcc.Input(id="new-password", type="password", placeholder="8 caractères minimum"),
                    ],
                    className="field",
                ),
                html.Button("Changer mon mot de passe", id="change-own-password-button", className="primary full-width"),
                html.Button("Déconnexion", id="manager-logout-button", className="secondary full-width"),
                html.Div(feedback or "", id="change-password-feedback"),
            ],
            className="login-card",
        ),
        "Le mot de passe temporaire doit être remplacé avant d’accéder à l’espace responsable.",
    )


def manager_access_header(auth: dict | None):
    name = f"{(auth or {}).get('first_name', '')} {(auth or {}).get('last_name', '')}".strip()
    return html.Div(
        [
            html.Span(name or (auth or {}).get("email", ""), className="manager-help"),
            html.Button("Déconnexion", id="manager-logout-button", className="secondary small"),
        ],
        className="manager-session-bar",
    )


def resolve_manager_auth(auth: dict | None, allow_store_fallback: bool = False) -> dict | None:
    persisted = load_manager_session()
    if persisted and persisted.get("authenticated"):
        return persisted
    restored = restore_manager_session_from_store(auth)
    if restored and restored.get("authenticated"):
        return restored
    if allow_store_fallback and is_session_valid(auth):
        return auth
    return None


def manager_page_for(pathname: str | None, auth: dict | None = None):
    if pathname == "/manager/qrcodes":
        return html.Div([manager_access_header(auth), qr_codes_page()])
    return html.Div([manager_access_header(auth), manager_dashboard(pathname=pathname, auth=auth)])


def manager_dashboard(feedback=None, pathname: str | None = None, auth: dict | None = None):
    return html.Div(id="manager-dashboard-body", children=manager_dashboard_body(feedback, pathname, auth))


def manager_dashboard_body(feedback=None, pathname: str | None = None, auth: dict | None = None):
    auth = resolve_manager_auth(auth)
    scope = manager_scope(auth)
    metrics = dashboard_metrics(scope)
    sessions = metrics["sessions"]
    manual = metrics["manual"]
    anomalies = detect_anomalies(sessions, manual)
    weekly_tracking, daily_tracking, hour_alerts, hour_counts = weekly_hours_views(scope)
    validated = sessions[sessions["validation_status"].isin(["Validé", "Corrigé"])] if not sessions.empty else sessions
    if validated.empty:
        hours = 0
    else:
        hours = round(sum(_duration_value(row) for row in validated.itertuples(index=False)), 2)

    summary = summary_section(metrics, anomalies, hours, hour_counts)
    status = html.Div(feedback, id="manager-action-status") if feedback else html.Div(id="manager-action-status")
    menu = manager_menu_buttons()
    pathname = pathname or "/manager"

    if pathname == "/manager/suivi":
        return html.Div([hidden_admin_callback_fields(), menu, status, follow_up_sections(weekly_tracking, daily_tracking, hour_alerts)])
    if pathname == "/manager/actions":
        return html.Div([hidden_admin_callback_fields(), menu, status, actions_sections(anomalies, scope)])
    if pathname == "/manager/ajouter":
        return html.Div([menu, status, add_people_hours_section(scope)])
    if pathname == "/manager/parametres":
        return html.Div([hidden_admin_callback_fields(include_remove=False, include_manager=False), menu, status, employee_settings_section(scope, auth)])
    if pathname == "/manager/exports":
        return html.Div([hidden_admin_callback_fields(), menu, status, exports_section()])

    return html.Div(
        [
            hidden_admin_callback_fields(),
            summary,
            status,
            section("Que voulez-vous faire ?", menu, "Choisissez une action pour afficher uniquement la partie utile."),
        ]
    )


def weekly_hours_views(establishment_id: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame, list[str], dict[str, int]]:
    employees = pd.DataFrame(list_active_employees(establishment_id))
    columns = ["Employé", "Objectif semaine", "Heures validées", "Écart", "Statut", "Services travaillés"]
    daily_columns = ["Employé", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche", "Total semaine"]
    counts = {"Conforme": 0, "Trop d’heures": 0, "Pas assez d’heures": 0}
    if employees.empty:
        return pd.DataFrame(columns=columns), pd.DataFrame(columns=daily_columns), [], counts

    sessions = sessions_for_week(establishment_id=establishment_id)
    payable = sessions[sessions["validation_status"].isin(["Validé", "Corrigé"])].copy() if not sessions.empty else sessions
    if not payable.empty:
        payable.loc[:, "paid_hours"] = [_duration_value(row) for row in payable.itertuples(index=False)]
        payable.loc[:, "date"] = payable["start_time"].map(_date)
        payable.loc[:, "day"] = payable["date"].map(_day_name)

    tracking_rows = []
    daily_rows = []
    alerts = []
    for employee in employees.itertuples(index=False):
        employee_name = f"{employee.first_name} {employee.last_name}"
        employee_sessions = payable[payable["employee_id"] == employee.id] if not payable.empty else payable
        target = _number_value(getattr(employee, "weekly_target_hours", 35), 35)
        validated_hours = round(float(employee_sessions["paid_hours"].sum()), 2) if not employee_sessions.empty else 0.0
        diff = round(validated_hours - target, 2)
        status = _hours_status(diff)
        counts[status] += 1
        services = ""
        if not employee_sessions.empty:
            services = ", ".join(sorted({str(value) for value in employee_sessions["service"] if str(value).strip()}))
        tracking_rows.append(
            {
                "Employé": employee_name,
                "Objectif semaine": _hours_compact(target),
                "Heures validées": _hours_compact(validated_hours),
                "Écart": _signed_hours(diff),
                "Statut": status,
                "Services travaillés": services,
            }
        )
        daily_row = {"Employé": employee_name}
        for day in _week_days():
            day_hours = employee_sessions[employee_sessions["day"] == day]["paid_hours"].sum() if not employee_sessions.empty else 0
            daily_row[day] = _hours_compact(day_hours)
        daily_row["Total semaine"] = _hours_compact(validated_hours)
        daily_rows.append(daily_row)
        if status == "Trop d’heures":
            alerts.append(f"{employee_name} : {_signed_hours(diff)} au-dessus de son objectif")
        elif status == "Pas assez d’heures":
            alerts.append(f"{employee_name} : {_signed_hours(diff)} sous son objectif")

    return pd.DataFrame(tracking_rows, columns=columns), pd.DataFrame(daily_rows, columns=daily_columns), alerts, counts


def summary_section(metrics: dict, anomalies: pd.DataFrame, hours: float, hour_counts: dict[str, int]):
    return section(
        "Résumé semaine",
        html.Div(
            [
                metric_card("Créneaux à valider", metrics["pending_count"], "warning"),
                metric_card("Demandes manuelles", len(metrics["manual"][metrics["manual"]["status"].eq("Demande manuelle en attente")] if not metrics["manual"].empty else []), "neutral"),
                metric_card("Anomalies", len(anomalies), "danger" if len(anomalies) else "neutral"),
                metric_card("Heures validées", hours, "neutral"),
                metric_card("Employés conformes", hour_counts["Conforme"], "neutral"),
                metric_card("Trop d’heures", hour_counts["Trop d’heures"], "danger"),
                metric_card("Pas assez d’heures", hour_counts["Pas assez d’heures"], "warning"),
            ],
            className="metrics-grid",
        ),
    )


def manager_menu_buttons():
    items = [
        ("Suivi semaine", "Voir objectifs, heures validées et alertes.", "/manager/suivi"),
        ("Actions à valider", "Contrôler les pointages, demandes et anomalies.", "/manager/actions"),
        ("Ajouter", "Ajouter une personne ou un créneau.", "/manager/ajouter"),
        ("Paramètres employés", "Modifier les objectifs hebdomadaires.", "/manager/parametres"),
        ("Exports", "Générer Excel et CSV.", "/manager/exports"),
        ("Codes QR", "Générer les codes QR imprimables.", "/manager/qrcodes"),
    ]
    return html.Div(
        [
            dcc.Link(
                [html.Strong(title), html.Span(description)],
                href=href,
                className="manager-menu-button",
            )
            for title, description, href in items
        ],
        className="manager-menu-grid",
    )


def hidden_admin_callback_fields(include_remove: bool = True, include_manager: bool = True):
    fields = [
        html.Button("", id="add-employee-button", n_clicks=0),
        html.Button("", id="add-session-button", n_clicks=0),
        dcc.Input(id="new-employee-first-name", value=""),
        dcc.Input(id="new-employee-last-name", value=""),
        dcc.Input(id="new-employee-role", value="saisonnier"),
        dcc.Input(id="new-employee-target", type="number", value=35),
        dcc.Input(id="admin-session-employee", value=""),
        dcc.Input(id="admin-session-service", value=""),
        dcc.Input(id="admin-session-date", value=""),
        dcc.Input(id="admin-session-start", value=""),
        dcc.Input(id="admin-session-end", value=""),
        dcc.Input(id="admin-session-status", value=VALIDATED),
        dcc.Input(id="admin-session-corrected-hours", type="number", value=None),
        dcc.Input(id="admin-session-comment", value=""),
    ]
    if include_manager:
        fields.extend(
            [
                html.Button("", id="add-manager-user-button", n_clicks=0),
                dcc.Input(id="new-manager-first-name", value=""),
                dcc.Input(id="new-manager-last-name", value=""),
                dcc.Input(id="new-manager-email", value=""),
                dcc.Input(id="new-manager-password", value=""),
            ]
        )
    if include_remove:
        fields.extend([html.Button("", id="remove-employee-button", n_clicks=0), dcc.Input(id="remove-employee-id", value="")])
    return html.Div(
        fields,
        className="visually-hidden",
    )


def follow_up_sections(weekly_tracking: pd.DataFrame, daily_tracking: pd.DataFrame, hour_alerts: list[str]):
    return html.Div(
        [
            section(
                "Suivi heures semaine",
                html.Div(
                    [
                        html.P(
                            "Compare les heures validées avec l’objectif hebdomadaire de chaque employé.",
                            className="manager-help",
                        ),
                        weekly_hours_table(weekly_tracking),
                    ],
                    className="manager-stack",
                ),
            ),
            section("Suivi journalier", data_table(daily_tracking, "daily-hours-tracking", page_size=8)),
            section("Alertes heures", hour_alert_cards(hour_alerts)),
        ]
    )


def actions_sections(anomalies: pd.DataFrame, establishment_id: int | None = None):
    return html.Div(
        [
            section(
                "Actions à faire",
                html.Div(
                    [
                        html.Div(
                            [
                                html.Strong("Durée corrigée (heures)"),
                                html.Span("Exemple : 1.5 = 1h30, 2 = 2h00"),
                            ],
                            className="correction-help-card",
                        ),
                        html.H3("Pointages QR à valider"),
                        html.P("Heures issues des scans QR, à contrôler avant validation.", className="manager-help"),
                        session_action_cards(pending_sessions_df(establishment_id)),
                        html.H3("Demandes d’heures à valider"),
                        html.P("Demandes ajoutées par un saisonnier après un oubli de scan.", className="manager-help"),
                        manual_action_cards(manual_requests_df(PENDING_MANUAL, establishment_id)),
                        html.H3("Anomalies"),
                        anomaly_cards(anomalies),
                    ],
                    className="manager-stack",
                ),
            ),
            section(
                "Heures déjà traitées",
                data_table(history_sessions_table(establishment_id), "history-sessions"),
                "Historique des heures validées, corrigées ou refusées.",
            ),
        ]
    )


def add_people_hours_section(establishment_id: int | None = None):
    return section(
        "Ajouter une personne ou des heures",
        people_and_hours_admin_section(establishment_id),
        "Ajoutez un saisonnier, puis saisissez un créneau avec le service concerné et les heures à retenir.",
    )


def employee_settings_section(establishment_id: int | None = None, auth: dict | None = None):
    return section(
        "Paramètres employés",
        html.Div(
            [
                employee_target_cards(establishment_id),
                remove_employee_card(establishment_id),
                managers_settings_section(establishment_id, auth),
                activity_log_section(establishment_id),
            ],
            className="manager-stack",
        ),
        "Modifiez l’objectif hebdomadaire en heures décimales, par exemple 24.5 pour 24h30.",
    )


def exports_section():
    return section(
        "Exports semaine",
        html.Div(
            [
                html.Button("Exporter la semaine en Excel", id="export-week", className="primary"),
                dcc.Download(id="excel-download"),
                html.Div(id="export-feedback"),
                html.Button("Exporter le CSV pour tableur Google", id="export-csv-week", className="secondary"),
                html.Div(id="csv-export-feedback"),
                html.Button("Créer une sauvegarde", id="create-backup", className="secondary"),
                html.Div(id="backup-feedback"),
            ],
            className="form-card export-actions",
        ),
    )


def weekly_hours_table(df: pd.DataFrame):
    if df.empty:
        return html.Div("Aucun employé actif à afficher.", className="empty-state")
    headers = [html.Div(column, className="weekly-hours-cell weekly-hours-header") for column in df.columns]
    rows = []
    for row in df.to_dict("records"):
        status = row["Statut"]
        rows.extend(
            [
                html.Div(row["Employé"], className="weekly-hours-cell employee-cell"),
                html.Div(row["Objectif semaine"], className="weekly-hours-cell"),
                html.Div(row["Heures validées"], className="weekly-hours-cell"),
                html.Div(row["Écart"], className="weekly-hours-cell"),
                html.Div(html.Span(status, className=f"hours-status-badge {hours_status_class(status)}"), className="weekly-hours-cell"),
                html.Div(row["Services travaillés"] or "-", className="weekly-hours-cell"),
            ]
        )
    return html.Div([*headers, *rows], className="weekly-hours-grid")


def hour_alert_cards(alerts: list[str]):
    if not alerts:
        return html.Div("Aucune alerte heures cette semaine.", className="empty-state")
    return html.Div([html.Div(alert, className="hour-alert") for alert in alerts], className="hour-alert-list")


def employee_target_cards(establishment_id: int | None = None):
    employees = list_active_employees(establishment_id)
    if not employees:
        return html.Div("Aucun employé actif.", className="empty-state")
    cards = []
    for employee in employees:
        employee_id = int(employee["id"])
        target = _number_value(employee.get("weekly_target_hours"), 35)
        cards.append(
            html.Article(
                [
                    html.Div(
                        [
                            html.H4(f"{employee['first_name']} {employee['last_name']}"),
                            html.P(_role_label(employee.get("role"))),
                        ],
                        className="manager-card-title",
                    ),
                    html.Div(
                        [
                            html.Label("Objectif semaine"),
                            dcc.Input(
                                id={"type": "employee-target-hours", "id": employee_id},
                                type="number",
                                min=0,
                                step=0.25,
                                value=target,
                            ),
                        ],
                        className="employee-target-field",
                    ),
                    html.Button(
                        "Enregistrer",
                        id={"type": "employee-target-save", "id": employee_id},
                        className="secondary small",
                    ),
                ],
                className="employee-target-card",
            )
        )
    return html.Div(cards, className="employee-target-grid")


def people_and_hours_admin_section(establishment_id: int | None = None):
    return html.Div(
        [
            html.Div(
                [
                    html.H3("Ajouter une personne"),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Prénom"),
                                    dcc.Input(id="new-employee-first-name", type="text", placeholder="Prénom"),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Nom"),
                                    dcc.Input(id="new-employee-last-name", type="text", placeholder="Nom"),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Rôle"),
                                    dcc.Dropdown(
                                        id="new-employee-role",
                                        options=[
                                            {"label": "Saisonnier", "value": "saisonnier"},
                                            {"label": "Responsable", "value": "responsable"},
                                        ],
                                        value="saisonnier",
                                        clearable=False,
                                    ),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Objectif semaine"),
                                    dcc.Input(id="new-employee-target", type="number", min=0, step=0.25, value=35),
                                ],
                                className="field",
                            ),
                        ],
                        className="admin-form-grid",
                    ),
                    html.Button("Ajouter la personne", id="add-employee-button", className="secondary"),
                ],
                className="form-card admin-form-card",
            ),
            html.Div(
                [
                    html.H3("Ajouter un créneau"),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Personne"),
                                    dcc.Dropdown(id="admin-session-employee", options=employee_options(establishment_id), placeholder="Choisir une personne"),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Service concerné"),
                                    dcc.Dropdown(id="admin-session-service", options=service_options(establishment_id), placeholder="Choisir un service"),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Date"),
                                    dcc.Input(id="admin-session-date", type="text", placeholder="AAAA-MM-JJ"),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Heure début"),
                                    dcc.Input(id="admin-session-start", type="text", placeholder="HH:MM"),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Heure fin"),
                                    dcc.Input(id="admin-session-end", type="text", placeholder="HH:MM"),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Statut"),
                                    dcc.Dropdown(
                                        id="admin-session-status",
                                        options=[
                                            {"label": "Validé", "value": VALIDATED},
                                            {"label": "Corrigé", "value": CORRECTED},
                                            {"label": "En attente", "value": PENDING_SCAN},
                                            {"label": "Refusé", "value": REFUSED},
                                        ],
                                        value=VALIDATED,
                                        clearable=False,
                                    ),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Durée retenue"),
                                    dcc.Input(id="admin-session-corrected-hours", type="number", min=0, step=0.01, placeholder="Facultatif"),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Commentaire responsable"),
                                    dcc.Input(id="admin-session-comment", type="text", placeholder="Commentaire"),
                                ],
                                className="field",
                            ),
                        ],
                        className="admin-form-grid",
                    ),
                    html.Button("Ajouter le créneau", id="add-session-button", className="primary"),
                ],
                className="form-card admin-form-card",
            ),
        ],
        className="admin-forms-grid",
    )


def remove_employee_card(establishment_id: int | None = None):
    return html.Div(
        [
            html.H3("Retirer une personne"),
            html.P(
                "La personne ne sera plus proposée dans les listes, mais son historique sera conservé.",
                className="manager-help",
            ),
            html.Div(
                [
                    html.Label("Personne à retirer"),
                    dcc.Dropdown(id="remove-employee-id", options=employee_options(establishment_id), placeholder="Choisir une personne"),
                ],
                className="field",
            ),
            html.Button("Retirer la personne", id="remove-employee-button", className="danger"),
        ],
        className="form-card admin-form-card",
    )


def managers_settings_section(establishment_id: int | None = None, auth: dict | None = None):
    managers = list_manager_users(establishment_id)
    rows = []
    for manager in managers:
        rows.append(
            html.Article(
                [
                    html.Div(
                        [
                            html.H4(f"{manager['first_name']} {manager['last_name']}"),
                            html.P(manager["email"]),
                        ],
                        className="manager-card-title",
                    ),
                    html.Div(
                        [
                            manager_detail("Rôle", _user_role_label(manager["role"])),
                            manager_detail("Établissement", manager.get("establishment_name") or "Tous"),
                            manager_detail("Statut", "Actif" if manager["active"] else "Désactivé"),
                        ],
                        className="manager-card-details",
                    ),
                    html.Button(
                        "Désactiver",
                        id={"type": "manager-user-disable", "id": int(manager["id"])},
                        className="danger small",
                        disabled=not manager["active"] or int(manager["id"]) == int((auth or {}).get("id") or 0),
                    ),
                    html.Div(
                        [
                            dcc.Input(
                                id={"type": "manager-user-password", "id": int(manager["id"])},
                                type="password",
                                placeholder="Nouveau mot de passe",
                            ),
                            html.Button(
                                "Changer mot de passe",
                                id={"type": "manager-user-password-save", "id": int(manager["id"])},
                                className="secondary small",
                                disabled=not manager["active"],
                            ),
                        ],
                        className="manager-card-correction",
                    ),
                ],
                className="employee-target-card",
            )
        )

    return html.Div(
        [
            html.H3("Responsables"),
            html.Div(rows or [html.Div("Aucun responsable.", className="empty-state")], className="employee-target-grid"),
            html.Div(
                [
                    html.H3("Créer un responsable établissement"),
                    html.Div(
                        [
                            html.Div([html.Label("Prénom"), dcc.Input(id="new-manager-first-name", type="text")], className="field"),
                            html.Div([html.Label("Nom"), dcc.Input(id="new-manager-last-name", type="text")], className="field"),
                            html.Div([html.Label("Email"), dcc.Input(id="new-manager-email", type="email")], className="field"),
                            html.Div([html.Label("Mot de passe temporaire"), dcc.Input(id="new-manager-password", type="password")], className="field"),
                        ],
                        className="admin-form-grid",
                    ),
                    html.Button("Créer le responsable", id="add-manager-user-button", className="secondary"),
                ],
                className="form-card admin-form-card",
            ),
        ],
        className="manager-stack",
    )


def activity_log_section(establishment_id: int | None = None):
    df = activity_log_table(establishment_id)
    return html.Div(
        [
            html.H3("Journal d’activité"),
            data_table(df, "activity-log", page_size=10),
        ],
        className="form-card admin-form-card",
    )


def activity_log_table(establishment_id: int | None = None) -> pd.DataFrame:
    logs = recent_audit_logs(establishment_id, limit=50)
    columns = ["Date", "Responsable", "Action", "Élément", "Commentaire"]
    if logs.empty:
        return pd.DataFrame(columns=columns)
    rows = []
    for row in logs.itertuples(index=False):
        rows.append(
            {
                "Date": _datetime_label(row.created_at),
                "Responsable": row.actor,
                "Action": _audit_action_label(row.action),
                "Élément": _audit_entity_label(row.entity_type, row.entity_id),
                "Commentaire": row.comment or "",
            }
        )
    return pd.DataFrame(rows, columns=columns)


def employee_options(establishment_id: int | None = None):
    return [
        {"label": f"{employee['first_name']} {employee['last_name']}", "value": int(employee["id"])}
        for employee in list_active_employees(establishment_id)
    ]


def service_options(establishment_id: int | None = None):
    return [{"label": str(service["name"]).capitalize(), "value": int(service["id"])} for service in list_services(establishment_id)]


def session_action_cards(df):
    if df.empty:
        return html.Div("Aucun créneau QR à valider.", className="empty-state")
    cards = []
    for row in df.itertuples(index=False):
        cards.append(
            manager_action_card(
                title=row.employee,
                subtitle=row.service,
                details=[
                    ("Date", _date(row.start_time)),
                    ("Début", _time(row.start_time)),
                    ("Fin", _time(row.end_time)),
                    ("Durée", _hours(row.duration_hours)),
                    ("Origine", row.source),
                    ("Statut", row.validation_status),
                ],
                comment=row.manager_comment,
                correction_target="session",
                item_id=int(row.id),
                primary_label="Valider",
                primary_action="validate",
                refuse_action="refuse",
            )
        )
    return html.Div(cards, className="manager-card-grid")


def manual_action_cards(df):
    if df.empty:
        return html.Div("Aucune demande manuelle en attente.", className="empty-state")
    cards = []
    for row in df.itertuples(index=False):
        cards.append(
            manager_action_card(
                title=row.employee,
                subtitle=row.service,
                details=[
                    ("Date", _date(row.requested_start_time)),
                    ("Début", _time(row.requested_start_time)),
                    ("Fin", _time(row.requested_end_time)),
                    ("Durée", _hours(row.requested_duration_hours)),
                    ("Origine", "Demande manuelle"),
                    ("Statut", row.status),
                ],
                comment=row.manager_comment,
                correction_target="manual",
                item_id=int(row.id),
                primary_label="Accepter",
                primary_action="accept",
                refuse_action="refuse",
            )
        )
    return html.Div(cards, className="manager-card-grid")


def manager_action_card(
    title: str,
    subtitle: str,
    details: list[tuple[str, str]],
    comment: str | None,
    correction_target: str,
    item_id: int,
    primary_label: str,
    primary_action: str,
    refuse_action: str,
):
    return html.Article(
        [
            html.Div(
                [
                    html.Div([html.H4(title), html.P(subtitle)], className="manager-card-title"),
                    html.Div(
                        [
                            html.Button(
                                primary_label,
                                id={"type": "manager-action", "target": correction_target, "action": primary_action, "id": item_id},
                                className="primary small",
                            ),
                            html.Button(
                                "Refuser",
                                id={"type": "manager-action", "target": correction_target, "action": refuse_action, "id": item_id},
                                className="danger small",
                            ),
                        ],
                        className="manager-card-actions quick-actions",
                    ),
                ],
                className="manager-card-header",
            ),
            html.Div([manager_detail(label, value) for label, value in details], className="manager-card-details"),
            html.Div(
                [
                    correction_duration_field(correction_target, item_id),
                    html.Div(
                        [
                            html.Label("Commentaire responsable"),
                            dcc.Input(
                                id={"type": "manager-comment", "target": correction_target, "id": item_id},
                                type="text",
                                placeholder="Commentaire",
                            ),
                        ],
                        className="manager-comment-field",
                    ),
                    html.Button(
                        "Corriger",
                        id={"type": "manager-action", "target": correction_target, "action": "correct", "id": item_id},
                        className="secondary small",
                    ),
                ],
                className="manager-card-correction",
            ),
            html.Div([html.Strong("Commentaire"), html.Span(comment)], className="manager-card-comment") if comment else None,
        ],
        className="manager-action-card",
    )


def manager_detail(label: str, value) -> html.Div:
    return html.Div([html.Span(label), html.Strong(value or "-")], className="manager-detail")


def anomaly_cards(df):
    if df.empty:
        return html.Div("Aucune anomalie détectée.", className="empty-state")
    cards = []
    for row in df.itertuples(index=False):
        start = getattr(row, "start_time", "")
        end = getattr(row, "end_time", "")
        duration = getattr(row, "duration_hours", "")
        cards.append(
            html.Article(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.H4(getattr(row, "employee", "")),
                                    html.P(getattr(row, "service", "")),
                                ],
                                className="manager-card-title",
                            ),
                            html.Span(getattr(row, "anomaly", "Anomalie"), className="anomaly-badge"),
                        ],
                        className="manager-card-header",
                    ),
                    html.Div(
                        [
                            manager_detail("Date", _date(start)),
                            manager_detail("Début", _time(start)),
                            manager_detail("Fin", _time(end)),
                            manager_detail("Durée", _hours(duration)),
                            manager_detail("Origine", getattr(row, "source", "")),
                        ],
                        className="manager-card-details",
                    ),
                    html.Div(
                        [
                            html.Strong("Action recommandée"),
                            html.Span("Vérifier puis corriger ou refuser."),
                        ],
                        className="manager-card-comment",
                    ),
                ],
                className="manager-action-card anomaly-card",
            )
        )
    return html.Div(cards, className="manager-card-grid")


def correction_duration_field(target: str, item_id: int):
    return html.Div(
        [
            html.Label("Durée corrigée (heures)"),
            dcc.Input(
                id={"type": "corrected-hours", "target": target, "id": item_id},
                type="number",
                placeholder="Ex : 1.5",
                min=0,
                step=0.01,
            ),
            html.Small("1.5 = 1h30"),
        ],
        className="correction-duration-field",
    )


def history_sessions(establishment_id: int | None = None):
    df = sessions_for_week(establishment_id=establishment_id)
    if df.empty:
        return df
    return df[df["validation_status"].isin(["Validé", "Corrigé", "Refusé"])]


def history_sessions_table(establishment_id: int | None = None):
    df = history_sessions(establishment_id)
    columns = [
        "Employé",
        "Service",
        "Date",
        "Début",
        "Fin",
        "Durée",
        "Durée corrigée (heures)",
        "Origine",
        "Statut",
        "Commentaire responsable",
    ]
    if df.empty:
        return pd.DataFrame(columns=columns)

    rows = []
    for row in df.itertuples(index=False):
        rows.append(
            {
                "Employé": row.employee,
                "Service": row.service,
                "Date": _date(row.start_time),
                "Début": _time(row.start_time),
                "Fin": _time(row.end_time),
                "Durée": _hours(row.duration_hours),
                "Durée corrigée (heures)": _hours(row.corrected_duration_hours),
                "Origine": row.source,
                "Statut": row.validation_status,
                "Commentaire responsable": row.manager_comment or "",
            }
        )
    return pd.DataFrame(rows, columns=columns)


def qr_codes_page():
    return html.Div([qr_codes_section()], className="qr-page")


def qr_codes_section():
    return section(
        "Codes QR imprimables",
        html.Div(
            [
                html.Div([html.Label("Adresse de base"), dcc.Input(id="qr-base-url", type="text", value=BASE_URL)], className="field"),
                html.Div(
                    "Les QR codes locaux ne fonctionneront pas hors de cet ordinateur."
                    if is_local_base_url(BASE_URL)
                    else "Les QR codes utilisent l'adresse publique configurée.",
                    className="manager-help",
                ),
                html.Div("Après chaque déploiement ou changement d’URL, régénérez les QR codes.", className="message warning"),
                html.Button("Régénérer tous les QR codes publics", id="generate-qr-codes", className="secondary"),
                html.Button("Imprimer cette page", id="print-qr-page", className="primary print-button", n_clicks=0),
                html.Div(id="print-trigger-output", className="visually-hidden"),
                html.Div(id="qr-generation-feedback"),
                html.Div(id="qr-print-preview", children=qr_preview(BASE_URL), className="qr-print-preview"),
            ],
            className="form-card",
        ),
        "Une page A4 par service, prête à imprimer et plastifier.",
    )


def qr_preview(base_url: str):
    return html.Div(
        [
            html.Div(
                [
                    html.P("CAMPFLOW V1", className="qr-print-title"),
                    html.H3(_service_display_label(card["service"])),
                    html.Img(src=card["qr_src"], alt=f"Code QR {_service_display_label(card['service'])}"),
                    html.P("Scannez ce QR code pour commencer ou terminer votre service."),
                    html.Small("En cas d'oubli, utilisez le formulaire 'J'ai oublié de scanner' sur la page de pointage."),
                    html.Code(card["url"]),
                    html.Button(
                        f"Générer le code QR {_service_display_label(card['service'])}",
                        id={"type": "generate-service-qr", "slug": card["service"]["qr_slug"]},
                        className="secondary small",
                    ),
                ],
                className="qr-print-card",
            )
            for card in printable_cards(base_url)
        ]
    )


def _service_display_label(service: dict) -> str:
    return str(service.get("label") or service.get("name") or "Service").capitalize()


def register_callbacks(app):
    app.clientside_callback(
        """
        function(n_clicks) {
            if (n_clicks) {
                window.print();
            }
            return "";
        }
        """,
        Output("print-trigger-output", "children"),
        Input("print-qr-page", "n_clicks"),
        prevent_initial_call=True,
    )

    @app.callback(
        Output("manager-auth", "data"),
        Output("manager-login-error", "children"),
        Input("manager-login-button", "n_clicks"),
        State("manager-email", "value"),
        State("manager-password", "value"),
        prevent_initial_call=True,
    )
    def login(_login_clicks, email, password):
        try:
            from flask import request as flask_request
            ip = flask_request.remote_addr or "unknown"
        except Exception:
            ip = "unknown"
        if is_rate_limited(f"login:{ip}", max_requests=5, window_seconds=60):
            log_warning(f"Login rate limit dépassé : IP {ip}")
            return {"authenticated": False}, html.Div("Trop de tentatives de connexion. Réessayez dans une minute.", className="message error")
        user = authenticate_user(email, password)
        if user:
            return user, ""
        return {"authenticated": False}, html.Div("Email ou mot de passe incorrect.", className="message error")

    @app.callback(
        Output("manager-auth", "data", allow_duplicate=True),
        Output("change-password-feedback", "children"),
        Input("change-own-password-button", "n_clicks"),
        State("current-password", "value"),
        State("new-password", "value"),
        State("manager-auth", "data"),
        prevent_initial_call=True,
    )
    def change_password(_password_clicks, current_password, new_password, auth):
        auth = resolve_manager_auth(auth, allow_store_fallback=True)
        if not is_session_valid(auth):
            return {"authenticated": False}, html.Div("Connectez-vous pour changer le mot de passe.", className="message error")
        try:
            updated = change_own_password(int(auth["id"]), current_password, new_password)
        except ValueError as exc:
            return auth, html.Div(str(exc), className="message error")
        return updated, html.Div("Mot de passe changé.", className="message success")

    @app.callback(
        Output("manager-auth", "data", allow_duplicate=True),
        Input("manager-logout-button", "n_clicks"),
        State("manager-auth", "data"),
        prevent_initial_call=True,
    )
    def logout(_logout_clicks, auth):
        auth = resolve_manager_auth(auth)
        logout_user(auth)
        return {"authenticated": False}

    @app.callback(
        Output("manager-login", "children"),
        Output("manager-content", "children"),
        Input("manager-auth", "data"),
        Input("url", "pathname"),
        prevent_initial_call=False,
    )
    def render_manager(auth, pathname):
        auth = resolve_manager_auth(auth, allow_store_fallback=True)
        if auth and auth.get("authenticated") and auth.get("must_change_password"):
            return "", change_password_panel(auth)
        if is_manager_access_allowed(auth):
            return "", manager_page_for(pathname, auth)
        return login_panel(), ""

    @app.callback(
        Output("manager-dashboard-body", "children"),
        Input({"type": "manager-action", "target": ALL, "action": ALL, "id": ALL}, "n_clicks"),
        Input({"type": "employee-target-save", "id": ALL}, "n_clicks"),
        Input("add-employee-button", "n_clicks"),
        Input("remove-employee-button", "n_clicks"),
        Input("add-session-button", "n_clicks"),
        Input("add-manager-user-button", "n_clicks"),
        Input({"type": "manager-user-disable", "id": ALL}, "n_clicks"),
        Input({"type": "manager-user-password-save", "id": ALL}, "n_clicks"),
        State({"type": "corrected-hours", "target": ALL, "id": ALL}, "value"),
        State({"type": "corrected-hours", "target": ALL, "id": ALL}, "id"),
        State({"type": "manager-comment", "target": ALL, "id": ALL}, "value"),
        State({"type": "manager-comment", "target": ALL, "id": ALL}, "id"),
        State({"type": "employee-target-hours", "id": ALL}, "value"),
        State({"type": "employee-target-hours", "id": ALL}, "id"),
        State("new-employee-first-name", "value"),
        State("new-employee-last-name", "value"),
        State("new-employee-role", "value"),
        State("new-employee-target", "value"),
        State("remove-employee-id", "value"),
        State("admin-session-employee", "value"),
        State("admin-session-service", "value"),
        State("admin-session-date", "value"),
        State("admin-session-start", "value"),
        State("admin-session-end", "value"),
        State("admin-session-status", "value"),
        State("admin-session-corrected-hours", "value"),
        State("admin-session-comment", "value"),
        State("new-manager-first-name", "value"),
        State("new-manager-last-name", "value"),
        State("new-manager-email", "value"),
        State("new-manager-password", "value"),
        State({"type": "manager-user-password", "id": ALL}, "value"),
        State({"type": "manager-user-password", "id": ALL}, "id"),
        State("manager-auth", "data"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def handle_manager_action(
        _action_clicks,
        _target_clicks,
        _add_employee_clicks,
        _remove_employee_clicks,
        _add_session_clicks,
        _add_manager_clicks,
        _disable_manager_clicks,
        _password_manager_clicks,
        corrected_values,
        corrected_ids,
        comment_values,
        comment_ids,
        target_values,
        target_ids,
        new_first_name,
        new_last_name,
        new_role,
        new_target,
        remove_employee_id,
        session_employee_id,
        session_service_id,
        session_date,
        session_start,
        session_end,
        session_status,
        session_corrected_hours,
        session_comment,
        new_manager_first_name,
        new_manager_last_name,
        new_manager_email,
        new_manager_password,
        manager_password_values,
        manager_password_ids,
        auth,
        pathname,
    ):
        auth = resolve_manager_auth(auth)
        if not is_manager_access_allowed(auth):
            return html.Div("Connectez-vous pour continuer.", className="message error")
        scope = manager_scope(auth)
        triggered = ctx.triggered_id
        if not triggered:
            return manager_dashboard_body(auth=auth)

        if triggered == "add-employee-button":
            if not new_first_name or not new_last_name:
                return manager_dashboard_body(message("Indiquez le prénom et le nom.", "error"), pathname, auth)
            target = _number_value(new_target, 35)
            if target < 0:
                return manager_dashboard_body(message("L’objectif semaine doit être positif.", "error"), pathname, auth)
            try:
                create_employee(new_first_name, new_last_name, new_role or "saisonnier", target, _write_establishment_id(scope))
            except Exception as exc:
                log_error("Erreur ajout personne", exc)
                return manager_dashboard_body(message("La personne n’a pas pu être enregistrée. Réessayez dans un instant.", "error"), pathname, auth)
            return manager_dashboard_body(
                message(f"Personne ajoutée ou mise à jour : {new_first_name.strip().title()} {new_last_name.strip().title()}.", "success"),
                pathname,
                auth,
            )

        if triggered == "remove-employee-button":
            if not remove_employee_id:
                return manager_dashboard_body(message("Choisissez une personne à retirer.", "error"), pathname, auth)
            try:
                deactivate_employee(int(remove_employee_id), scope, actor_user_id(auth))
            except Exception as exc:
                log_error("Erreur retrait personne", exc)
                return manager_dashboard_body(message("La personne n’a pas pu être retirée. Réessayez dans un instant.", "error"), pathname, auth)
            return manager_dashboard_body(message("Personne retirée des listes actives.", "success"), pathname, auth)

        if triggered == "add-session-button":
            if not all([session_employee_id, session_service_id, session_date, session_start, session_end, session_status]):
                return manager_dashboard_body(message("Complétez la personne, le service, la date, les heures et le statut.", "error"), pathname, auth)
            try:
                session_id = create_manager_work_session(
                    int(session_employee_id),
                    int(session_service_id),
                    session_date,
                    session_start,
                    session_end,
                    session_status,
                    session_corrected_hours,
                    session_comment or "",
                    scope,
                    actor_user_id(auth),
                )
            except ValueError as exc:
                return manager_dashboard_body(message(f"Créneau non ajouté : {exc}", "error"), pathname, auth)
            except Exception as exc:
                log_error("Erreur ajout créneau responsable", exc)
                return manager_dashboard_body(message("Le créneau n’a pas pu être ajouté. Réessayez dans un instant.", "error"), pathname, auth)
            return manager_dashboard_body(message(f"Créneau ajouté : #{session_id}.", "success"), pathname, auth)

        if triggered == "add-manager-user-button":
            try:
                create_manager_user(
                    new_manager_first_name or "",
                    new_manager_last_name or "",
                    new_manager_email or "",
                    new_manager_password or "",
                    _write_establishment_id(scope),
                    actor_user_id(auth),
                )
            except ValueError as exc:
                return manager_dashboard_body(message(str(exc), "error"), pathname, auth)
            except Exception as exc:
                log_error("Erreur création responsable", exc)
                return manager_dashboard_body(message("Le responsable n’a pas pu être créé. Vérifiez que l’email n’existe pas déjà.", "error"), pathname, auth)
            return manager_dashboard_body(message("Responsable créé.", "success"), pathname, auth)

        if isinstance(triggered, dict) and triggered.get("type") == "employee-target-save":
            employee_id = int(triggered["id"])
            target = _value_for_employee_id(target_values, target_ids, employee_id)
            if target is None or target < 0:
                return manager_dashboard_body(message("Indiquez un objectif hebdomadaire valide.", "error"), pathname, auth)
            try:
                update_employee_weekly_target(employee_id, float(target), scope, actor_user_id(auth))
            except Exception as exc:
                log_error("Erreur modification objectif hebdomadaire", exc)
                return manager_dashboard_body(message("L’objectif n’a pas pu être enregistré. Réessayez dans un instant.", "error"), pathname, auth)
            return manager_dashboard_body(message("Objectif hebdomadaire enregistré.", "success"), pathname, auth)

        if isinstance(triggered, dict) and triggered.get("type") == "manager-user-disable":
            try:
                deactivate_manager_user(int(triggered["id"]), scope, actor_user_id(auth))
            except Exception as exc:
                log_error("Erreur désactivation responsable", exc)
                return manager_dashboard_body(message("Le responsable n’a pas pu être désactivé.", "error"), pathname, auth)
            return manager_dashboard_body(message("Responsable désactivé.", "success"), pathname, auth)

        if isinstance(triggered, dict) and triggered.get("type") == "manager-user-password-save":
            user_id = int(triggered["id"])
            password = _value_for_manager_user_id(manager_password_values, manager_password_ids, user_id)
            if not password:
                return manager_dashboard_body(message("Indiquez un nouveau mot de passe.", "error"), pathname, auth)
            try:
                change_manager_password(user_id, password, scope)
            except Exception as exc:
                log_error("Erreur modification mot de passe responsable", exc)
                return manager_dashboard_body(message("Le mot de passe n’a pas pu être modifié.", "error"), pathname, auth)
            return manager_dashboard_body(message("Mot de passe responsable modifié.", "success"), pathname, auth)

        if not isinstance(triggered, dict):
            return manager_dashboard_body(pathname=pathname, auth=auth)

        target = triggered["target"]
        action = triggered["action"]
        item_id = int(triggered["id"])
        corrected = _value_for_id(corrected_values, corrected_ids, item_id, target)
        comment = _value_for_id(comment_values, comment_ids, item_id, target) or ""

        if action == "correct" and corrected is None:
            return manager_dashboard_body(message("Indiquez une durée corrigée avant de cliquer Corriger.", "error"), pathname, auth)

        if target == "session":
            row = _row_by_id(pending_sessions_df(scope), item_id)
            try:
                decide_session(item_id, action, corrected, comment, scope, actor_user_id(auth))
            except Exception as exc:
                log_error("Erreur action responsable sur créneau", exc)
                return manager_dashboard_body(message("L’action n’a pas pu être enregistrée. Réessayez dans un instant.", "error"), pathname, auth)
            employee = row.get("employee", "Créneau") if row else "Créneau"
            action_label = {"validate": "validé", "correct": "corrigé", "refuse": "refusé"}[action]
            return manager_dashboard_body(message(f"Créneau d’{employee} {action_label}", "success"), pathname, auth)

        row = _row_by_id(manual_requests_df(PENDING_MANUAL, scope), item_id)
        try:
            decide_manual_request(item_id, action, corrected, comment, scope, actor_user_id(auth))
        except Exception as exc:
            log_error("Erreur action responsable sur demande manuelle", exc)
            return manager_dashboard_body(message("L’action n’a pas pu être enregistrée. Réessayez dans un instant.", "error"), pathname, auth)
        employee = row.get("employee", "Demande") if row else "Demande"
        action_label = {"accept": "acceptée", "correct": "corrigée", "refuse": "refusée"}[action]
        return manager_dashboard_body(message(f"Demande de {employee} {action_label}", "success"), pathname, auth)

    @app.callback(
        Output("excel-download", "data"),
        Output("export-feedback", "children"),
        Input("export-week", "n_clicks"),
        State("manager-auth", "data"),
        prevent_initial_call=True,
    )
    def export_excel(_, auth):
        auth = resolve_manager_auth(auth)
        if not is_manager_access_allowed(auth):
            return None, html.Div("Connectez-vous pour générer l’export.", className="message error")
        try:
            log_audit_event(
                action="export_excel_generated",
                entity_type="export",
                establishment_id=_audit_scope_establishment_id(manager_scope(auth)),
                actor_user_id=actor_user_id(auth),
                new_value={"format": "xlsx"},
            )
            path = export_weekly_excel(manager_scope(auth))
        except Exception as exc:
            log_error("Erreur export Excel", exc)
            return None, html.Div("L’export Excel n’a pas pu être généré. Réessayez dans un instant.", className="message error")
        return (
            dcc.send_file(path),
            html.Div(f"Export Excel prêt : {path.name}", className="message success"),
        )

    @app.callback(
        Output("csv-export-feedback", "children"),
        Input("export-csv-week", "n_clicks"),
        State("manager-auth", "data"),
        prevent_initial_call=True,
    )
    def export_csv(_, auth):
        auth = resolve_manager_auth(auth)
        if not is_manager_access_allowed(auth):
            return html.Div("Connectez-vous pour générer l’export.", className="message error")
        try:
            log_audit_event(
                action="export_csv_generated",
                entity_type="export",
                establishment_id=_audit_scope_establishment_id(manager_scope(auth)),
                actor_user_id=actor_user_id(auth),
                new_value={"format": "csv"},
            )
            paths = export_weekly_csv(manager_scope(auth))
        except Exception as exc:
            log_error("Erreur export CSV", exc)
            return html.Div("Le CSV n’a pas pu être généré. Réessayez dans un instant.", className="message error")
        return html.Div(
            [
                html.Div("Fichiers CSV générés. Vous pouvez les importer dans un tableur Google.", className="message success"),
                html.Ul([html.Li(str(path)) for path in paths]),
            ]
        )

    @app.callback(
        Output("backup-feedback", "children"),
        Input("create-backup", "n_clicks"),
        State("manager-auth", "data"),
        prevent_initial_call=True,
    )
    def create_backup(_, auth):
        auth = resolve_manager_auth(auth)
        if not is_manager_access_allowed(auth):
            return html.Div("Connectez-vous pour créer une sauvegarde.", className="message error")
        try:
            path = create_database_backup()
            log_audit_event(
                action="backup_created",
                entity_type="backup",
                establishment_id=_audit_scope_establishment_id(manager_scope(auth)),
                actor_user_id=actor_user_id(auth),
                new_value={"filename": path.name},
            )
        except Exception as exc:
            log_error("Erreur sauvegarde locale", exc)
            return html.Div("La sauvegarde n’a pas pu être créée. Réessayez dans un instant.", className="message error")
        return html.Div(f"Sauvegarde créée : {path.name}", className="message success")

    @app.callback(
        Output("qr-generation-feedback", "children"),
        Output("qr-print-preview", "children"),
        Input("generate-qr-codes", "n_clicks"),
        Input({"type": "generate-service-qr", "slug": ALL}, "n_clicks"),
        State("qr-base-url", "value"),
        State("manager-auth", "data"),
        prevent_initial_call=True,
    )
    def generate_qr_assets(_all_clicks, _service_clicks, base_url, auth):
        auth = resolve_manager_auth(auth)
        if not is_manager_access_allowed(auth):
            return html.Div("Connectez-vous pour régénérer les QR codes.", className="message error"), qr_preview((base_url or BASE_URL).rstrip("/"))
        base_url = (base_url or BASE_URL).rstrip("/")
        try:
            triggered = ctx.triggered_id
            if isinstance(triggered, dict) and triggered.get("type") == "generate-service-qr":
                generated = [generate_qr_code_for_service(triggered["slug"], base_url)]
            else:
                generated = generate_qr_codes(base_url)
            printable = generate_printable_html(base_url)
            for item in generated:
                service = item["service"]
                log_audit_event(
                    action="qr_code_regenerated",
                    entity_type="qr_code",
                    entity_id=int(service["id"]),
                    establishment_id=int(service["establishment_id"]),
                    actor_user_id=actor_user_id(auth),
                    new_value={"service": service["name"], "url": item["url"]},
                )
        except Exception as exc:
            log_error("Erreur génération code QR", exc)
            return html.Div("Le code QR n’a pas pu être généré. Réessayez dans un instant.", className="message error"), qr_preview(base_url)
        lines = [html.Div(f"{_service_display_label(item['service'])} : {item['url']}") for item in generated]
        service_label = _service_display_label(generated[0]["service"]) if len(generated) == 1 else "tous les services"
        success_text = (
            f"QR code régénéré avec l’URL publique : {base_url}"
            if len(generated) == 1
            else f"QR codes régénérés avec l’URL publique : {base_url}"
        )
        return (
            html.Div(
                [
                    html.Div(success_text, className="message success"),
                    html.Div(f"Service concerné : {service_label}.", className="message success"),
                    html.Div(f"Fichier enregistré dans : {generated[0]['path'].parent}", className="message success"),
                    html.Div(f"Page imprimable : {printable}", className="message success"),
                    html.Div(lines, className="qr-url-list"),
                ]
            ),
            qr_preview(base_url),
        )


def _value_for_id(values, ids, item_id: int, target: str):
    for value, id_data in zip(values or [], ids or []):
        if int(id_data.get("id")) == item_id and id_data.get("target") == target:
            return value
    return None


def _value_for_employee_id(values, ids, employee_id: int):
    for value, id_data in zip(values or [], ids or []):
        if int(id_data.get("id")) == employee_id:
            return value
    return None


def _value_for_manager_user_id(values, ids, user_id: int):
    for value, id_data in zip(values or [], ids or []):
        if int(id_data.get("id")) == user_id:
            return value
    return None


def _row_by_id(df, item_id: int):
    if df.empty:
        return None
    match = df[df["id"] == item_id]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def _time(value) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value)
    return text[11:16] if len(text) >= 16 else text


def _date(value) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value)
    return text[:10] if len(text) >= 10 else text


def _hours(value) -> str:
    if value is None or pd.isna(value):
        return ""
    try:
        return f"{float(value):.2f} h"
    except (TypeError, ValueError):
        return ""


def _hours_compact(value) -> str:
    return f"{_number_value(value, 0):.2f}h"


def _signed_hours(value) -> str:
    number = _number_value(value, 0)
    return f"{number:+.2f}h"


def _number_value(value, default: float = 0) -> float:
    if value is None or pd.isna(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _role_label(role: str | None) -> str:
    return {
        "manager": "responsable",
        "responsable": "responsable",
        "saisonnier": "saisonnier",
    }.get(str(role or "").lower(), role or "saisonnier")


def _user_role_label(role: str | None) -> str:
    return {
        "admin_global": "admin global",
        "responsable_etablissement": "responsable établissement",
    }.get(str(role or "").lower(), role or "")


def _audit_action_label(action: str | None) -> str:
    return {
        "work_session_validated": "Créneau validé",
        "work_session_corrected": "Créneau corrigé",
        "work_session_refused": "Créneau refusé",
        "manual_request_accepted": "Demande manuelle acceptée",
        "manual_request_corrected": "Demande manuelle corrigée",
        "manual_request_refused": "Demande manuelle refusée",
        "manager_work_session_created": "Créneau manuel créé",
        "employee_weekly_target_updated": "Objectif hebdomadaire modifié",
        "employee_deactivated": "Personne désactivée",
        "manager_user_created": "Responsable créé",
        "manager_user_deactivated": "Responsable désactivé",
        "export_excel_generated": "Export Excel généré",
        "export_csv_generated": "Export CSV généré",
        "backup_created": "Sauvegarde créée",
        "qr_code_regenerated": "QR code régénéré",
    }.get(str(action or ""), action or "")


def _audit_entity_label(entity_type: str | None, entity_id) -> str:
    entity = {
        "work_session": "Créneau",
        "manual_time_request": "Demande manuelle",
        "employee": "Personne",
        "user": "Responsable",
        "export": "Export",
        "backup": "Sauvegarde",
        "qr_code": "QR code",
    }.get(str(entity_type or ""), entity_type or "Élément")
    return f"{entity} #{entity_id}" if entity_id not in (None, "") else entity


def manager_scope(auth: dict | None) -> int:
    return user_establishment_scope(auth)


def actor_user_id(auth: dict | None) -> int | None:
    if not auth or not auth.get("id"):
        return None
    return int(auth["id"])


def _audit_scope_establishment_id(scope: int | None) -> int | None:
    return None if scope == ALL_ESTABLISHMENTS_ID else int(scope or default_establishment_id())


def _write_establishment_id(scope: int | None) -> int:
    return default_establishment_id() if scope == ALL_ESTABLISHMENTS_ID else int(scope or default_establishment_id())


def _hours_status(diff: float) -> str:
    if diff < -2:
        return "Pas assez d’heures"
    if diff > 2:
        return "Trop d’heures"
    return "Conforme"


def hours_status_class(status: str) -> str:
    return {
        "Conforme": "ok",
        "Pas assez d’heures": "low",
        "Trop d’heures": "high",
    }.get(status, "ok")


def _week_days() -> list[str]:
    return ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def _day_name(date_value: str) -> str:
    days = _week_days()
    try:
        return days[pd.to_datetime(date_value).weekday()]
    except (TypeError, ValueError):
        return ""


def _duration_value(row) -> float:
    corrected = getattr(row, "corrected_duration_hours", None)
    duration = getattr(row, "duration_hours", None)
    value = corrected if corrected not in (None, "") else duration
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0
