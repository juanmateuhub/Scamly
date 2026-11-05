"""Generate the extension icons (a white magnifier on a teal rounded square) without dependencies.

Usage: backend/.venv/Scripts/python scripts/make_icons.py
Writes extension/icons/icon-{16,32,48,128}.png.
"""

import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "extension" / "icons"
SIZES = (16, 32, 48, 128)
SUPERSAMPLING = 4

BACKGROUND = (14, 124, 102)  # teal
FOREGROUND = (255, 255, 255)

# Shapes in a 0-1 square.
CORNER = 0.22  # background corner radius
LENS_CENTER = (0.43, 0.43)
LENS_OUTER, LENS_INNER = 0.25, 0.16
HANDLE = ((0.60, 0.60), (0.80, 0.80))
HANDLE_HALF_WIDTH = 0.065


def in_rounded_square(x: float, y: float) -> bool:
    dx = max(abs(x - 0.5) - (0.5 - CORNER), 0.0)
    dy = max(abs(y - 0.5) - (0.5 - CORNER), 0.0)
    return math.hypot(dx, dy) <= CORNER


def in_magnifier(x: float, y: float) -> bool:
    r = math.hypot(x - LENS_CENTER[0], y - LENS_CENTER[1])
    if LENS_INNER <= r <= LENS_OUTER:
        return True
    (ax, ay), (bx, by) = HANDLE
    t = max(
        0.0,
        min(
            1.0,
            ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2),
        ),
    )
    return math.hypot(x - (ax + t * (bx - ax)), y - (ay + t * (by - ay))) <= HANDLE_HALF_WIDTH


def render(size: int) -> bytes:
    rows = []
    n = SUPERSAMPLING
    for py in range(size):
        row = bytearray([0])  # PNG filter type: none
        for px in range(size):
            bg = fg = 0
            for sy in range(n):
                for sx in range(n):
                    x, y = (px + (sx + 0.5) / n) / size, (py + (sy + 0.5) / n) / size
                    if in_rounded_square(x, y):
                        bg += 1
                        fg += in_magnifier(x, y)
            alpha = bg / (n * n)
            mix = fg / bg if bg else 0.0
            color = [round(b + (f - b) * mix) for b, f in zip(BACKGROUND, FOREGROUND, strict=True)]
            row += bytes([*color, round(alpha * 255)])
        rows.append(bytes(row))
    return png(size, b"".join(rows))


def png(size: int, raw: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        (OUT / f"icon-{size}.png").write_bytes(render(size))
        print(f"icon-{size}.png")


if __name__ == "__main__":
    main()
