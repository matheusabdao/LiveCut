"""Generate ``packaging/assets/livecut.ico`` with only the standard library.

The icon is a dark rounded square with an accent play glyph, rendered with 4x
supersampling for smooth edges. Run it whenever the icon needs regenerating:

    python packaging/make_icon.py
"""

from __future__ import annotations

import struct
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent / "assets" / "livecut.ico"
SIZES = [256, 128, 64, 48, 32, 16]
SUPERSAMPLE = 4

# Background rounded square and accent play triangle (normalized 0..1 coords).
BG_COLOR = (15, 17, 21)       # near-black charcoal
ACCENT_COLOR = (255, 71, 87)  # warm red
RECT = (0.05, 0.95, 0.05, 0.95, 0.22)  # x0, x1, y0, y1, corner radius
TRIANGLE = ((0.42, 0.32), (0.42, 0.68), (0.72, 0.50))


def _inside_round_rect(u: float, v: float,
                       x0: float, x1: float, y0: float, y1: float,
                       radius: float) -> bool:
    if u < x0 or u > x1 or v < y0 or v > y1:
        return False
    cx = min(max(u, x0 + radius), x1 - radius)
    cy = min(max(v, y0 + radius), y1 - radius)
    dx, dy = u - cx, v - cy
    return dx * dx + dy * dy <= radius * radius


def _sign(px: float, py: float, a, b) -> float:
    return (px - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (py - b[1])


def _inside_triangle(px: float, py: float) -> bool:
    a, b, c = TRIANGLE
    d1 = _sign(px, py, a, b)
    d2 = _sign(px, py, b, c)
    d3 = _sign(px, py, c, a)
    has_neg = d1 < 0 or d2 < 0 or d3 < 0
    has_pos = d1 > 0 or d2 > 0 or d3 > 0
    return not (has_neg and has_pos)


def _render(size: int) -> list:
    """Return a ``size``x``size`` RGBA image as a flat list of (r, g, b, a)."""
    big = size * SUPERSAMPLE
    pixels = []
    for y in range(big):
        v = (y + 0.5) / big
        for x in range(big):
            u = (x + 0.5) / big
            if not _inside_round_rect(u, v, *RECT):
                pixels.append((0, 0, 0, 0))
            elif _inside_triangle(u, v):
                pixels.append(ACCENT_COLOR + (255,))
            else:
                pixels.append(BG_COLOR + (255,))
    return pixels


def _downsample(pixels: list, size: int) -> list:
    """Box-filter the supersampled image down to ``size``x``size`` (premultiplied)."""
    big = size * SUPERSAMPLE
    out = []
    area = SUPERSAMPLE * SUPERSAMPLE
    for oy in range(size):
        for ox in range(size):
            ar = ag = ab = aa = 0
            for sy in range(oy * SUPERSAMPLE, (oy + 1) * SUPERSAMPLE):
                base = sy * big + ox * SUPERSAMPLE
                for sx in range(base, base + SUPERSAMPLE):
                    r, g, b, a = pixels[sx]
                    ar += r * a
                    ag += g * a
                    ab += b * a
                    aa += a
            if aa == 0:
                out.append((0, 0, 0, 0))
            else:
                out.append((ar // aa, ag // aa, ab // aa, aa // area))
    return out


def _bmp_bytes(pixels: list, size: int) -> bytes:
    header = struct.pack(
        "<IiiHHIIiiII",
        40, size, size * 2, 1, 32, 0, size * size * 4, 0, 0, 0, 0,
    )
    body = bytearray()
    for y in range(size - 1, -1, -1):  # bottom-up
        for x in range(size):
            r, g, b, a = pixels[y * size + x]
            body += bytes((b, g, r, a))
    mask_row = ((size + 31) // 32) * 4  # 1bpp rows padded to 4 bytes
    body += b"\x00" * (mask_row * size)
    return header + bytes(body)


def build_ico() -> bytes:
    images = []
    for size in SIZES:
        images.append((size, _bmp_bytes(_downsample(_render(size), size), size)))

    directory = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = bytearray()
    payload = bytearray()

    for size, data in images:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        payload += data
        offset += len(data)

    return bytes(directory) + bytes(entries) + bytes(payload)


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(build_ico())
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes, sizes={SIZES})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
