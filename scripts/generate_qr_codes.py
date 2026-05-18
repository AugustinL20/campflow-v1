from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.db import init_db
from utils.qr_generator import generate_printable_html, generate_qr_codes


if __name__ == "__main__":
    init_db()
    generated = generate_qr_codes()
    printable = generate_printable_html()
    for item in generated:
        print(f"{item['service']['label']}: {item['url']} -> {item['path']}")
    print(f"Printable HTML -> {printable}")
