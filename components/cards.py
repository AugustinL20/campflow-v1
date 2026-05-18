from __future__ import annotations

from dash import html


def metric_card(label: str, value, tone: str = "neutral"):
    return html.Div(
        [html.Span(label), html.Strong(str(value))],
        className=f"metric-card {tone}",
    )


def message(text: str, kind: str = "info"):
    if not text:
        return None
    return html.Div(text, className=f"message {kind}")
