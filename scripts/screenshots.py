"""Capture the README screenshots: the real panel rendering invented listings (no third-party data).

Needs the backend on :8000 and the panel preview on :5173 (`npm run dev` in extension/), and
Google Chrome. Usage: backend/.venv/Scripts/python scripts/screenshots.py
Writes docs/screenshots/panel-{rojo,amarillo,verde}.png, cropped to their content.
"""

import json
import struct
import subprocess
import tempfile
import time
import zlib
from pathlib import Path
from typing import Any
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PREVIEW = "http://localhost:5173/dev/panel-preview.html"

SIMILAR_IPHONES = [
    {"title": title, "price_eur": price}
    for title, price in [
        ("iPhone 17 256GB", 720),
        ("iPhone 17 negro", 690),
        ("Apple iPhone 17 256GB azul", 750),
        ("iPhone 17 como nuevo", 700),
        ("iPhone 17 256 GB", 680),
        ("iPhone 17 blanco", 740),
        ("iPhone 17 con factura", 710),
        ("iPhone 17 256GB verde", 730),
        ("iPhone 17 Pro", 900),  # other variant: ignored by the backend
    ]
]

CASES: dict[str, dict[str, Any]] = {
    "panel-rojo": {
        "platform": "wallapop",
        "listing_id": "demo-rojo",
        "title": "iPhone 17 256GB",
        "description": (
            "Me voy del país el viernes, solo Bizum. Escríbeme por WhatsApp y te lo envío."
        ),
        "price_eur": 290,
        "category": "Smartphones",
        "condition": "Sin abrir",
        "seller": {"account_age_days": 3, "ratings_count": 0, "sales_count": 0},
        "shipping_available": False,
        "image_count": 2,
        "comparables": SIMILAR_IPHONES,
    },
    "panel-amarillo": {
        "platform": "wallapop",
        "listing_id": "demo-amarillo",
        "title": "Nintendo Switch OLED",
        "description": "Precio fijo. Envío por la app.",
        "price_eur": 170,
        "category": "Consolas",
        "condition": "Como nuevo",
        "seller": {"account_age_days": 6, "ratings_count": 0, "sales_count": 0},
        "shipping_available": True,
        "image_count": 3,
    },
    "panel-verde": {
        "platform": "wallapop",
        "listing_id": "demo-verde",
        "title": "iPhone 17 256GB",
        "description": (
            "Comprado en septiembre, con factura y garantía de Apple. Batería al 100 %, siempre "
            "con funda y protector. Incluye caja y cable. Envío por Wallapop o en mano en Valencia."
        ),
        "price_eur": 715,
        "category": "Smartphones",
        "condition": "Como nuevo",
        "seller": {
            "account_age_days": 1400,
            "ratings_count": 64,
            "ratings_avg": 4.9,
            "sales_count": 41,
        },
        "shipping_available": True,
        "image_count": 6,
        "comparables": SIMILAR_IPHONES,
    },
}


def capture(listing: dict[str, Any], target: Path, profile: str) -> None:
    url = f"{PREVIEW}?t={time.time_ns()}#{quote(json.dumps(listing))}"
    subprocess.run(
        [
            CHROME,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--user-data-dir={profile}",
            "--window-size=372,700",
            "--force-device-scale-factor=2",
            "--virtual-time-budget=10000",  # wait for the backend's answer
            f"--screenshot={target}",
            url,
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )


# --- crop the white space below the panel (minimal PNG decoder and encoder) ------------------


def _unfilter(raw: bytes, height: int, stride: int, channels: int) -> list[bytearray]:
    rows: list[bytearray] = []
    previous = bytearray(stride)
    for y in range(height):
        kind = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1 : (y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b = previous[i]
            c = previous[i - channels] if i >= channels else 0
            if kind == 1:
                line[i] = (line[i] + a) & 255
            elif kind == 2:
                line[i] = (line[i] + b) & 255
            elif kind == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                predictor = a if pa <= pb and pa <= pc else b if pb <= pc else c
                line[i] = (line[i] + predictor) & 255
        rows.append(line)
        previous = line
    return rows


def read_png(path: Path) -> tuple[int, int, list[bytearray]]:
    """(width, channels, rows) of an 8-bit RGB or RGBA PNG."""
    data = path.read_bytes()
    pos, idat = 8, b""
    width = height = channels = 0
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind, body = data[pos + 4 : pos + 8], data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color = struct.unpack(">IIBB", body[:10])
            if depth != 8 or color not in (2, 6):
                raise ValueError(f"unsupported PNG: depth {depth}, color type {color}")
            channels = 3 if color == 2 else 4
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    return width, channels, _unfilter(zlib.decompress(idat), height, width * channels, channels)


def write_png(path: Path, width: int, channels: int, rows: list[bytearray]) -> None:
    def chunk(kind: bytes, body: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(kind + body))
        return struct.pack(">I", len(body)) + kind + body + crc

    header = struct.pack(">IIBBBBB", width, len(rows), 8, 2 if channels == 3 else 6, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def crop_bottom(path: Path, margin: int = 32) -> int:
    width, channels, rows = read_png(path)
    content = [
        y
        for y, row in enumerate(rows)
        if any(value < 245 for i, value in enumerate(row) if i % channels < 3)
    ]
    keep = min(len(rows), max(content) + margin)
    write_png(path, width, channels, rows[:keep])
    return keep


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as profile:
        for name, listing in CASES.items():
            target = OUT / f"{name}.png"
            capture(listing, target, profile)
            print(f"{target.relative_to(ROOT)}: {crop_bottom(target)} px high")


if __name__ == "__main__":
    main()
