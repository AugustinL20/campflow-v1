from __future__ import annotations

from dash import dcc, html

from config import pointage_url
from database.queries import list_services


def app_shell(content):
    return html.Div(
        [
            html.Header(
                [
                    html.Div(
                        [
                            html.H1("CAMPFLOW V1"),
                            html.P("Camping La Peyrugue - suivi simple des heures saisonniers"),
                        ],
                        className="brand",
                    ),
                    html.Nav(
                        [
                            *[
                                dcc.Link(str(service["name"]).capitalize(), href=pointage_url(service))
                                for service in list_services()
                            ],
                            dcc.Link("Responsable", href="/manager", className="manager-discreet-link"),
                        ],
                        className="nav",
                    ),
                ],
                className="topbar",
            ),
            html.Main(content, className="page"),
        ],
        className="app",
    )


def home_shell(content):
    return html.Div(
        [
            html.Main(content, className="page home-page"),
        ],
        className="app home-app",
    )


def worker_shell(content):
    return html.Div(
        [
            html.Header(
                [
                    html.Div(
                        [
                            html.H1("CAMPFLOW"),
                            html.P("Pointage saisonnier"),
                        ],
                        className="brand",
                    ),
                ],
                className="topbar worker-topbar",
            ),
            html.Main(content, className="page worker-page-wrap"),
        ],
        className="app worker-app",
    )


def manager_shell(content):
    return html.Div(
        [
            html.Header(
                [
                    html.Div(
                        [
                            html.H1("CAMPFLOW Responsable"),
                            html.P("Validation hebdomadaire, corrections et exports"),
                        ],
                        className="brand",
                    ),
                    html.Nav(
                        [
                            dcc.Link("Responsable", href="/manager"),
                            dcc.Link("Codes QR", href="/manager/qrcodes"),
                            *[
                                dcc.Link(f"Pointage {service['name'].lower()}", href=pointage_url(service))
                                for service in list_services()
                            ],
                        ],
                        className="nav",
                    ),
                ],
                className="topbar manager-topbar",
            ),
            html.Main(content, className="page manager-page"),
        ],
        className="app",
    )


def section(title: str, children, subtitle: str | None = None):
    return html.Section(
        [
            html.Div(
                [html.H2(title), html.P(subtitle) if subtitle else None],
                className="section-heading",
            ),
            children,
        ],
        className="section",
    )
