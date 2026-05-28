from __future__ import annotations

import os

BASE_URL = os.getenv("CAMPFLOW_BASE_URL", "http://127.0.0.1:8050").rstrip("/")

SERVICES = [
    {"name": "restaurant", "label": "Restaurant", "qr_slug": "restaurant"},
    {"name": "ménage", "label": "Ménage", "qr_slug": "menage"},
    {"name": "entretien", "label": "Entretien", "qr_slug": "entretien"},
]


def pointage_url(service: dict, base_url: str | None = None) -> str:
    root = (base_url or BASE_URL).rstrip("/")
    qr_value = service.get("qr_token") or service["qr_slug"]
    return f"{root}/pointage?token={qr_value}"


def is_local_base_url(base_url: str | None = None) -> bool:
    root = (base_url or BASE_URL).strip().lower()
    return root.startswith("http://127.0.0.1") or root.startswith("http://localhost") or root.startswith("http://0.0.0.0")
