from __future__ import annotations

import os

from dash import Dash, Input, Output, dcc, html

from components.layout import home_shell, manager_shell, worker_shell
from database.auth import ensure_default_admin_user
from database.db import init_db
from database.queries import list_services
from pages import dashboard, manager, pointage

init_db()
ensure_default_admin_user()

app = Dash(__name__, suppress_callback_exceptions=True, title="CAMPFLOW V1")
server = app.server
server.secret_key = os.getenv("CAMPFLOW_SECRET_KEY", "campflow-dev-secret-change-me")

app.layout = html.Div([dcc.Location(id="url"), html.Div(id="page-content")])


@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname: str | None):
    pathname = pathname or "/"
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
                                    dcc.Link(str(service["name"]).capitalize(), href=f"/pointage/{service['qr_token']}", className="quick-link")
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


pointage.register_callbacks(app)
manager.register_callbacks(app)
dashboard.register_callbacks(app)


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8050)
