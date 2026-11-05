"""Generate the Scamly logo (a white geometric "S" on a green rounded square) without dependencies.

Usage: backend/.venv/Scripts/python scripts/make_icons.py
Writes extension/icons/icon-{16,32,48,128}.png and docs/logo.png (256 px).
"""

import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICONS = {ROOT / "extension" / "icons" / f"icon-{size}.png": size for size in (16, 32, 48, 128)}
ICONS[ROOT / "docs" / "logo.png"] = 256
SUPERSAMPLING = 4

# Diagonal green gradient (top-left -> bottom-right) and white letter.
GREEN_LIGHT = (34, 197, 94)
GREEN_DARK = (21, 128, 61)
WHITE = (255, 255, 255)

CORNER = 0.24  # background corner radius (unit square)

# The "S": two circular arcs of the same radius, one above the other, with round caps.
# Angles in degrees, screen coordinates (y down): 0 = right, 90 = bottom, 180 = left, 270 = top.
S_RADIUS = 0.135
S_HALF_STROKE = 0.062
S_UPPER = ((0.5, 0.5 - S_RADIUS), 90.0, 330.0)  # from the joint, over the top, to upper right
S_LOWER = ((0.5, 0.5 + S_RADIUS), -90.0, 150.0)  # from the joint, round the bottom, to lower left


def in_rounded_square(x: float, y: float) -> bool:
    dx = max(abs(x - 0.5) - (0.5 - CORNER), 0.0)
    dy = max(abs(y - 0.5) - (0.5 - CORNER), 0.0)
    return math.hypot(dx, dy) <= CORNER


def arc_distance(x: float, y: float, arc: tuple[tuple[float, float], float, float]) -> float:
    (cx, cy), start, end = arc
    angle = math.degrees(math.atan2(y - cy, x - cx))
    # Bring the angle into [start, start + 360) to test whether it lies on the arc.
    while angle < start:
        angle += 360
    while angle >= start + 360:
        angle -= 360
    if angle <= end:
        return abs(math.hypot(x - cx, y - cy) - S_RADIUS)
    caps = [
        (cx + S_RADIUS * math.cos(math.radians(a)), cy + S_RADIUS * math.sin(math.radians(a)))
        for a in (start, end)
    ]
    return min(math.hypot(x - px, y - py) for px, py in caps)


def in_letter(x: float, y: float) -> bool:
    return min(arc_distance(x, y, S_UPPER), arc_distance(x, y, S_LOWER)) <= S_HALF_STROKE


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
                        fg += in_letter(x, y)
            t = (px + py) / (2 * (size - 1))  # gradient position
            background = [
                round(a + (b - a) * t) for a, b in zip(GREEN_LIGHT, GREEN_DARK, strict=True)
            ]
            mix = fg / bg if bg else 0.0
            color = [round(b + (w - b) * mix) for b, w in zip(background, WHITE, strict=True)]
            row += bytes([*color, round(bg / (n * n) * 255)])
        rows.append(bytes(row))
    return png(size, b"".join(rows))


def png(size: int, raw: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(kind + data))
        return struct.pack(">I", len(data)) + kind + data + crc

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    for path, size in ICONS.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(render(size))
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
