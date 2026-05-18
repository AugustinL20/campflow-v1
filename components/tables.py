from __future__ import annotations

import pandas as pd
from dash import dash_table, html


COLUMN_LABELS = {
    "id": "ID",
    "employee": "Employé",
    "service": "Service",
    "start_time": "Début",
    "end_time": "Fin",
    "duration_hours": "Durée",
    "corrected_duration_hours": "Durée corrigée (heures)",
    "source": "Origine",
    "validation_status": "Statut",
    "manager_comment": "Commentaire responsable",
    "requested_start_time": "Début demandé",
    "requested_end_time": "Fin demandée",
    "requested_duration_hours": "Durée demandée",
    "reason": "Raison",
    "status": "Statut",
    "created_at": "Créée le",
    "reviewed_at": "Traitée le",
    "action": "Action",
    "old_value": "Ancienne valeur",
    "new_value": "Nouvelle valeur",
    "timestamp": "Horodatage",
    "anomaly": "Anomalie",
    "work_session_id": "ID créneau",
    "manual_request_id": "ID demande manuelle",
}


def data_table(df: pd.DataFrame, table_id: str, page_size: int = 10):
    if df is None or df.empty:
        return html.Div("Aucune donnée à afficher.", className="empty-state")
    style_data_conditional = [{"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"}]
    if "validation_status" in df.columns:
        style_data_conditional.extend(
            [
                {"if": {"filter_query": "{validation_status} = 'Validé'"}, "borderLeft": "5px solid #1f7a4d"},
                {"if": {"filter_query": "{validation_status} = 'En attente'"}, "borderLeft": "5px solid #c47a00"},
                {"if": {"filter_query": "{validation_status} = 'Incomplet'"}, "borderLeft": "5px solid #b93636"},
                {"if": {"filter_query": "{validation_status} = 'Refusé'"}, "borderLeft": "5px solid #b93636"},
                {"if": {"filter_query": "{validation_status} = 'Corrigé'"}, "borderLeft": "5px solid #246b8f"},
            ]
        )
    if "status" in df.columns:
        style_data_conditional.extend(
            [
                {"if": {"filter_query": "{status} = 'Validé'"}, "borderLeft": "5px solid #1f7a4d"},
                {"if": {"filter_query": "{status} = 'En attente'"}, "borderLeft": "5px solid #c47a00"},
                {"if": {"filter_query": "{status} = 'Demande manuelle en attente'"}, "borderLeft": "5px solid #c47a00"},
                {"if": {"filter_query": "{status} = 'Refusé'"}, "borderLeft": "5px solid #b93636"},
                {"if": {"filter_query": "{status} = 'Corrigé'"}, "borderLeft": "5px solid #246b8f"},
            ]
        )
    if "source" in df.columns:
        style_data_conditional.extend(
            [
                {
                    "if": {"filter_query": "{source} = 'Scan QR'", "column_id": "source"},
                    "backgroundColor": "#e5f4ec",
                    "color": "#155a39",
                    "fontWeight": "700",
                },
                {
                    "if": {"filter_query": "{source} = 'Demande manuelle'", "column_id": "source"},
                    "backgroundColor": "#fff3d1",
                    "color": "#7a5300",
                    "fontWeight": "700",
                },
                {
                    "if": {"filter_query": "{source} = 'Correction responsable'", "column_id": "source"},
                    "backgroundColor": "#e5f0f6",
                    "color": "#174f6c",
                    "fontWeight": "700",
                },
            ]
        )
    if "Total semaine" in df.columns:
        style_data_conditional.append(
            {"if": {"column_id": "Total semaine"}, "fontWeight": "800", "backgroundColor": "#f7fafb"}
        )
    if "Statut" in df.columns:
        style_data_conditional.extend(
            [
                {"if": {"filter_query": "{Statut} = 'Conforme'", "column_id": "Statut"}, "backgroundColor": "#e5f4ec", "color": "#155a39", "fontWeight": "800"},
                {
                    "if": {"filter_query": "{Statut} = 'Pas assez d’heures'", "column_id": "Statut"},
                    "backgroundColor": "#fff3d1",
                    "color": "#9a6a00",
                    "fontWeight": "800",
                },
                {
                    "if": {"filter_query": "{Statut} = 'Trop d’heures'", "column_id": "Statut"},
                    "backgroundColor": "#f8e6e6",
                    "color": "#b93636",
                    "fontWeight": "800",
                },
            ]
        )
    return html.Div(
        dash_table.DataTable(
            id=table_id,
            data=df.to_dict("records"),
            columns=[{"name": COLUMN_LABELS.get(col, col.replace("_", " ").title()), "id": col} for col in df.columns],
            page_size=page_size,
            sort_action="native",
            filter_action="native",
            row_selectable="single",
            style_as_list_view=True,
            style_table={"overflowX": "auto", "maxWidth": "100%"},
            style_cell={
                "fontFamily": "Inter, system-ui, sans-serif",
                "fontSize": "14px",
                "padding": "10px",
                "whiteSpace": "normal",
                "height": "auto",
                "textAlign": "left",
                "minWidth": "110px",
                "maxWidth": "220px",
            },
            style_header={"fontWeight": "700", "backgroundColor": "#eef2f4"},
            style_data_conditional=style_data_conditional,
        ),
        className="table-scroll",
    )
