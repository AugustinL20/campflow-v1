from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import qrcode

from config import BASE_URL, pointage_url
from database.queries import list_services, rotate_service_qr_token

EXPORT_DIR = Path(__file__).resolve().parents[1] / "exports"
QR_DIR = EXPORT_DIR / "qr_codes"
PRINTABLE_PATH = EXPORT_DIR / "campflow_qr_codes_printable.html"


def make_qr_image(url: str):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=3,
    )
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")


def qr_data_uri(url: str) -> str:
    buffer = BytesIO()
    make_qr_image(url).save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def generate_qr_codes(base_url: str = BASE_URL) -> list[dict]:
    QR_DIR.mkdir(parents=True, exist_ok=True)
    generated = []
    for service in list_services():
        generated.append(generate_qr_code_for_service(service["qr_slug"], base_url))
    return generated


def generate_qr_code_for_service(service_slug: str, base_url: str = BASE_URL) -> dict:
    QR_DIR.mkdir(parents=True, exist_ok=True)
    service = rotate_service_qr_token(service_slug)
    url = pointage_url(service, base_url)
    path = QR_DIR / f"campflow_{service['qr_slug']}.png"
    make_qr_image(url).save(path)
    return {"service": service, "url": url, "path": path}


def printable_cards(base_url: str = BASE_URL) -> list[dict]:
    return [
        {
            "service": service,
            "url": pointage_url(service, base_url),
            "qr_src": qr_data_uri(pointage_url(service, base_url)),
        }
        for service in list_services()
    ]


def service_label(service: dict) -> str:
    return str(service.get("label") or service.get("name") or "Service").capitalize()


def generate_printable_html(base_url: str = BASE_URL) -> Path:
    EXPORT_DIR.mkdir(exist_ok=True)
    cards = printable_cards(base_url)
    pages = "\n".join(
        f"""
        <section class="print-page">
            <p class="app-title">CAMPFLOW V1</p>
            <h1>{service_label(card['service'])}</h1>
            <img src="{card['qr_src']}" alt="Code QR {service_label(card['service'])}">
            <p class="instruction">Scannez ce QR code pour commencer ou terminer votre service.</p>
            <p class="fallback">En cas d'oubli, utilisez le formulaire 'J'ai oublié de scanner' sur la page de pointage.</p>
            <p class="url">{card['url']}</p>
        </section>
        """
        for card in cards
    )
    html = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>CAMPFLOW V1 - Codes QR imprimables</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #172126; }}
    .print-page {{
      min-height: 277mm;
      padding: 20mm;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      page-break-after: always;
    }}
    .app-title {{ font-size: 24px; font-weight: 800; margin: 0 0 16px; }}
    h1 {{ font-size: 54px; margin: 0 0 28px; }}
    img {{ width: 135mm; height: 135mm; }}
    .instruction {{ font-size: 24px; max-width: 150mm; margin: 26px 0 12px; }}
    .fallback {{ font-size: 17px; max-width: 150mm; color: #45545c; }}
    .url {{ font-size: 12px; color: #66747c; margin-top: 22px; word-break: break-all; }}
    @page {{ size: A4; margin: 0; }}
    @media print {{ .print-page {{ min-height: 257mm; }} }}
  </style>
</head>
<body>
{pages}
</body>
</html>
"""
    PRINTABLE_PATH.write_text(html, encoding="utf-8")
    return PRINTABLE_PATH
