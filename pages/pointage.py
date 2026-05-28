from __future__ import annotations

from datetime import datetime

from dash import Input, Output, State, ctx, dcc, html

from components.cards import message
from components.layout import section
from database.queries import (
    create_manual_request_from_parts,
    get_any_open_session,
    get_next_punch_action,
    get_or_create_employee,
    get_service_by_id,
    get_service_by_slug,
    list_active_employees,
    list_services,
    record_smart_qr_punch,
    today_punches_for_employee,
)
from utils.app_logging import log_error, log_info, log_warning
from utils.rate_limit import is_rate_limited

MONTHS_FR = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]


def employee_options(establishment_id: int | None = None):
    return [
        {"label": f"{e['first_name']} {e['last_name']}", "value": e["id"]}
        for e in list_active_employees(establishment_id)
    ]


def service_options(establishment_id: int | None = None):
    return [{"label": s["name"], "value": s["id"]} for s in list_services(establishment_id)]


def action_label(action: str) -> str:
    return "Terminer mon service" if action == "terminer" else "Commencer mon service"


def current_day_label() -> str:
    now = datetime.now()
    return f"Aujourd'hui {now.day} {MONTHS_FR[now.month - 1]} — {now:%H:%M}"


def service_label(service: dict) -> str:
    return str(service["name"]).capitalize()


def confirmation_card(service_name: str, action_done: str, time_part: str):
    verb = "terminé" if action_done == "terminer" else "commencé"
    return html.Div(
        [
            html.Div(f"✅ Service {service_name} {verb}", className="confirmation-title"),
            html.Div(time_part, className="confirmation-time"),
        ],
        className="confirmation-card",
    )


def history_list(employee_id: int | None, establishment_id: int | None = None):
    if not employee_id:
        return html.Div("Aucun pointage aujourd'hui.", className="empty-state compact")
    try:
        punches = today_punches_for_employee(int(employee_id), establishment_id)
    except Exception as exc:
        log_error("Erreur lecture historique pointage", exc)
        return html.Div("Historique indisponible pour le moment.", className="empty-state compact")
    if punches.empty:
        return html.Div("Aucun pointage aujourd'hui.", className="empty-state compact")
    return html.Div(
        [
            html.Div(
                [
                    html.Strong(row.time),
                    html.Span(f" → {'début' if row.action == 'commencé' else 'fin'} {row.service}"),
                ],
                className="history-chip",
            )
            for row in punches.itertuples(index=False)
        ],
        className="today-list",
    )


def layout(service_slug: str | None = None):
    service = get_service_by_slug(service_slug) if service_slug else None
    if not service:
        return section(
            "Pointage indisponible",
            html.Div("Ce code QR n’est plus valide. Demandez au responsable le dernier code QR imprimé.", className="empty-state"),
        )

    return html.Div(
        [
            html.Section(
                [
                    dcc.Store(id="pointage-service-id", data=service["id"]),
                    dcc.Store(id="pointage-establishment-id", data=service["establishment_id"]),
                    html.Div(
                        [
                            html.Div(current_day_label(), className="current-time-badge"),
                            html.H2("Pointage"),
                            html.Div(f"Service : {service_label(service)}", className="service-name-line"),
                            html.Div(id="selected-employee", className="selected-employee"),
                        ],
                        className="worker-service-heading",
                    ),
                    html.Div(
                        [
                            html.Label("Je suis"),
                            dcc.Dropdown(
                                id="pointage-employee",
                                options=employee_options(service["establishment_id"]),
                                placeholder="Sélectionner mon profil",
                                className="worker-dropdown",
                            ),
                        ],
                        className="field",
                    ),
                    html.Div(
                        [
                            html.Label("Ou renseigner prénom / nom"),
                            html.Div(
                                [
                                    dcc.Input(id="pointage-first-name", placeholder="Prénom", type="text"),
                                    dcc.Input(id="pointage-last-name", placeholder="Nom", type="text"),
                                ],
                                className="inline-fields",
                            ),
                        ],
                        className="field secondary-identification",
                    ),
                    html.Button(
                        "Commencer mon service",
                        id="submit-punch",
                        className="big-action start",
                    ),
                    html.P(
                        "Un clic suffit. Attendez la confirmation avant de fermer la page.",
                        className="button-helper",
                    ),
                    html.Div(id="open-service-warning"),
                    html.Div(id="pointage-feedback"),
                    html.Div(
                        [
                            html.H3("Mes pointages aujourd'hui"),
                            html.Div(id="today-history", children=history_list(None, service["establishment_id"])),
                        ],
                        className="today-card",
                    ),
                ],
                className="worker-panel",
            ),
            manual_request_form(prefilled_service_id=service["id"], establishment_id=service["establishment_id"]),
        ],
        className="worker-page",
    )


def manual_request_form(prefilled_service_id: int | None = None, establishment_id: int | None = None):
    return html.Section(
        [
            html.Details(
                [
                    html.Summary("J'ai oublié de scanner"),
                    html.P(
                        "À utiliser uniquement en cas d'oubli. Cette demande devra être validée par un responsable.",
                        className="manual-helper",
                    ),
                    manual_request_fields(prefilled_service_id, establishment_id),
                ],
                className="manual-details",
            ),
        ],
        className="manual-section",
    )


def manual_request_fields(prefilled_service_id: int | None = None, establishment_id: int | None = None):
    return html.Div(
                [
                    html.Div(
                        [
                            html.Label("Saisonnier"),
                            dcc.Dropdown(
                                id="manual-employee",
                                options=employee_options(establishment_id),
                                placeholder="Sélectionner mon profil",
                            ),
                        ],
                        className="field",
                    ),
                    html.Div(
                        [
                            html.Label("Service concerné"),
                            dcc.Dropdown(
                                id="manual-service",
                                options=service_options(establishment_id),
                                value=prefilled_service_id,
                                clearable=False,
                            ),
                        ],
                        className="field",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Date"),
                                    dcc.Input(id="manual-date", type="text", placeholder="AAAA-MM-JJ"),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Heure de début"),
                                    dcc.Input(id="manual-start-time", type="text", placeholder="HH:MM"),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Heure de fin"),
                                    dcc.Input(id="manual-end-time", type="text", placeholder="HH:MM"),
                                ],
                                className="field",
                            ),
                        ],
                        className="manual-time-grid",
                    ),
                    html.Div(
                        [
                            html.Label("Raison obligatoire"),
                            dcc.Textarea(id="manual-reason", placeholder="Ex : j'ai oublié de scanner en fin de service"),
                        ],
                        className="field",
                    ),
                    html.Button("Envoyer la demande", id="submit-manual", className="secondary full-width"),
                    html.Div(id="manual-feedback"),
                ],
                className="manual-card",
            )


def worker_callback_response(feedback, employee_id: int | None, service_id: int | None, establishment_id: int | None = None):
    action = "commencer"
    warning = ""
    disabled = False

    if employee_id and service_id:
        action = get_next_punch_action(employee_id, service_id, establishment_id)
        open_session = get_any_open_session(employee_id, establishment_id)
        if open_session and int(open_session["service_id"]) != service_id:
            warning = message(
                "Attention : vous avez déjà un service "
                f"{open_session['service']} ouvert depuis {open_session['start_time'][11:16]}. "
                "Terminez-le avant de commencer un autre service.",
                "warning",
            )
            disabled = True

    button_class = "big-action finish" if action == "terminer" else "big-action start"
    employee_text = ""
    if employee_id:
        selected = next((option["label"] for option in employee_options(establishment_id) if option["value"] == employee_id), "")
        employee_text = f"Saisonnier sélectionné : {selected}" if selected else ""

    return (
        feedback or "",
        history_list(employee_id, establishment_id),
        action_label(action),
        button_class,
        disabled,
        employee_text,
        warning,
    )


def register_callbacks(app):
    @app.callback(
        Output("pointage-feedback", "children"),
        Output("today-history", "children"),
        Output("submit-punch", "children"),
        Output("submit-punch", "className"),
        Output("submit-punch", "disabled"),
        Output("selected-employee", "children"),
        Output("open-service-warning", "children"),
        Input("pointage-employee", "value"),
        Input("submit-punch", "n_clicks"),
        State("pointage-service-id", "data"),
        State("pointage-establishment-id", "data"),
        State("pointage-first-name", "value"),
        State("pointage-last-name", "value"),
        prevent_initial_call=False,
    )
    def sync_worker_action(employee_id, n_clicks, service_id, establishment_id, first_name, last_name):
        try:
            service_id = int(service_id) if service_id else None
            establishment_id = int(establishment_id) if establishment_id else None
            employee_id = int(employee_id) if employee_id else None
            service = get_service_by_id(service_id, establishment_id) if service_id else None
            triggered = ctx.triggered_id or ""
            feedback = ""

            if triggered == "submit-punch":
                try:
                    from flask import request as flask_request
                    ip = flask_request.remote_addr or "unknown"
                except Exception:
                    ip = "unknown"
                if is_rate_limited(f"qr_punch:{ip}", max_requests=20, window_seconds=60):
                    log_warning(f"Pointage QR rate limit dépassé : IP {ip}")
                    return worker_callback_response(
                        feedback=message("Trop de pointages en peu de temps. Attendez une minute.", "warning"),
                        employee_id=employee_id,
                        service_id=service_id,
                        establishment_id=establishment_id,
                    )
                if not employee_id:
                    if not first_name or not last_name:
                        return worker_callback_response(
                            feedback=message("Sélectionnez un profil ou renseignez prénom et nom.", "error"),
                            employee_id=None,
                            service_id=service_id,
                            establishment_id=establishment_id,
                        )
                    employee_id = get_or_create_employee(first_name, last_name, establishment_id)

                ok, text, action_done = record_smart_qr_punch(employee_id, service_id, establishment_id)
                service_name = service["name"] if service else "service"
                if ok:
                    time_part = text.split(" à ", 1)[1].split(".", 1)[0] if " à " in text else ""
                    feedback = confirmation_card(service_name, action_done, time_part)
                else:
                    feedback = message(text, "warning")

            return worker_callback_response(feedback=feedback, employee_id=employee_id, service_id=service_id, establishment_id=establishment_id)
        except Exception as exc:
            log_error("Erreur pointage saisonnier", exc)
            return (
                message("Le pointage est momentanément indisponible. Prévenez le responsable.", "error"),
                history_list(None),
                "Commencer mon service",
                "big-action start",
                False,
                "",
                "",
            )

    @app.callback(
        Output("manual-feedback", "children"),
        Input("submit-manual", "n_clicks"),
        State("manual-employee", "value"),
        State("manual-service", "value"),
        State("pointage-establishment-id", "data"),
        State("manual-date", "value"),
        State("manual-start-time", "value"),
        State("manual-end-time", "value"),
        State("manual-reason", "value"),
        prevent_initial_call=True,
    )
    def submit_manual(_, employee_id, service_id, establishment_id, date_value, start_time, end_time, reason):
        if not all([employee_id, service_id, date_value, start_time, end_time, reason]):
            return message("Tous les champs sont obligatoires pour une demande manuelle.", "error")
        try:
            establishment_id = int(establishment_id) if establishment_id else None
            service = get_service_by_id(int(service_id), establishment_id)
            if not service:
                return message("Service indisponible pour cet établissement.", "error")
            request_id = create_manual_request_from_parts(
                int(employee_id), int(service_id), date_value, start_time, end_time, reason, establishment_id
            )
        except ValueError:
            return message("Format attendu : date AAAA-MM-JJ et heures HH:MM.", "error")
        except Exception as exc:
            log_error("Erreur demande manuelle", exc)
            return message("La demande n’a pas pu être envoyée. Réessayez dans un instant.", "error")
        log_info(f"Demande manuelle créée : demande {request_id}, employé {employee_id}, service {service_id}")
        return message(f"Demande #{request_id} envoyée. Statut : Demande manuelle en attente.", "success")
