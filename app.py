from __future__ import annotations

import os
from datetime import timedelta
from urllib.parse import parse_qs

from dash import Dash, Input, Output, dcc, html

from components.layout import home_shell, manager_shell, worker_shell
from config import is_local_base_url, pointage_url
from database.auth import SESSION_HOURS, ensure_default_admin_user
from database.db import init_db
from database.queries import list_services
from pages import dashboard, manager, pointage

init_db()
ensure_default_admin_user()

app = Dash(__name__, suppress_callback_exceptions=True, title="CAMPFLOW V1")
server = app.server
server.secret_key = os.getenv("CAMPFLOW_SECRET_KEY", "campflow-dev-secret-change-me")

_is_production = not is_local_base_url()
server.config.update(
    PERMANENT_SESSION_LIFETIME=timedelta(hours=SESSION_HOURS),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=_is_production,
    SESSION_COOKIE_SAMESITE="Lax",
)

app.layout = html.Div([dcc.Location(id="url"), html.Div(id="page-content")])


@app.callback(Output("page-content", "children"), Input("url", "pathname"), Input("url", "search"))
def display_page(pathname: str | None, search: str | None):
    pathname = pathname or "/"
    if pathname == "/pointage":
        token = _query_param(search, "token")
        return worker_shell(pointage.layout(token))
    if pathname.startswith("/pointage/"):
        service_slug = pathname.rstrip("/").split("/")[-1]
        return worker_shell(pointage.layout(service_slug))
    if pathname in ("/dashboard",) or pathname.startswith("/manager"):
        return manager_shell(manager.layout())
    return home_shell(
        html.Div(
            [
                html.Section(
                    [
                        html.H2("CAMPFLOW V1"),
                        html.P("Camping La Peyrugue"),
                        html.Div(
                            [
                                *[
                                    dcc.Link(str(service["name"]).capitalize(), href=pointage_url(service), className="quick-link")
                                    for service in list_services()
                                ],
                            ],
                            className="quick-links",
                        ),
                        dcc.Link("Espace responsable", href="/manager", className="home-manager-link"),
                    ],
                    className="section hero",
                )
            ]
        )
    )


def _query_param(search: str | None, name: str) -> str | None:
    params = parse_qs((search or "").lstrip("?"))
    values = params.get(name) or []
    return values[0] if values else None


pointage.register_callbacks(app)
manager.register_callbacks(app)
dashboard.register_callbacks(app)


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8050)
