#!/usr/bin/env python3
"""Genera la librería de marca Spitwise desde el logo master.

Todo se deriva de `source/logo-master.png` (llama espresso en tile redondeado
+ wordmark). Reproducible: `python3 build_brand.py`.

Salidas:
  public/brand/*      -> variantes para la app y la guía de marca
  public/{favicon,icon,apple}* -> favicon + PWA regenerados

Sin dependencias externas más allá de Pillow + numpy (no scipy): el recorte de
fondo usa flood-fill por dilatación vectorizada.
"""
from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "source", "logo-master.png")
PUB = os.path.abspath(os.path.join(HERE, "..", "public"))
BRAND = os.path.join(PUB, "brand")
os.makedirs(BRAND, exist_ok=True)

# --- Paleta muestreada del master ---------------------------------------
ESPRESSO = (52, 33, 18)      # fondo del tile
CREAM = (253, 249, 241)      # fondo de página del master
ESPRESSO_HEX = "#342112"


def dist(a: np.ndarray, color) -> np.ndarray:
    c = np.array(color, dtype=np.int32)
    d = a.astype(np.int32) - c
    return np.sqrt((d * d).sum(axis=2))


def flood_from_border(allowed: np.ndarray) -> np.ndarray:
    """Región de `allowed` conectada al borde de la imagen (4-vecinos)."""
    seed = np.zeros_like(allowed)
    seed[0, :] = allowed[0, :]
    seed[-1, :] = allowed[-1, :]
    seed[:, 0] = allowed[:, 0]
    seed[:, -1] = allowed[:, -1]
    reached = seed.copy()
    while True:
        grown = reached.copy()
        grown[1:, :] |= reached[:-1, :]
        grown[:-1, :] |= reached[1:, :]
        grown[:, 1:] |= reached[:, :-1]
        grown[:, :-1] |= reached[:, 1:]
        grown &= allowed
        if grown.sum() == reached.sum():
            return grown
        reached = grown


def flood_from_seed(allowed: np.ndarray, sy: int, sx: int) -> np.ndarray:
    """Componente de `allowed` conectado al punto (sy, sx)."""
    reached = np.zeros_like(allowed)
    reached[sy, sx] = True
    while True:
        grown = reached.copy()
        grown[1:, :] |= reached[:-1, :]
        grown[:-1, :] |= reached[1:, :]
        grown[:, 1:] |= reached[:, :-1]
        grown[:, :-1] |= reached[:, 1:]
        grown &= allowed
        if grown.sum() == reached.sum():
            return grown
        reached = grown


def alpha_smooth(mask_bool: np.ndarray) -> Image.Image:
    """Alpha 8-bit con un leve blur para bordes anti-aliased."""
    a = (mask_bool * 255).astype(np.uint8)
    img = Image.fromarray(a, "L").filter(ImageFilter.GaussianBlur(0.6))
    return img


def bbox_of(mask_bool: np.ndarray, pad: int = 0, shape=None):
    ys, xs = np.where(mask_bool)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    if pad:
        H, W = shape
        y0 = max(0, y0 - pad); x0 = max(0, x0 - pad)
        y1 = min(H - 1, y1 + pad); x1 = min(W - 1, x1 + pad)
    return x0, y0, x1 + 1, y1 + 1


def save(img: Image.Image, name: str, root=BRAND):
    p = os.path.join(root, name)
    img.save(p)
    print(f"  {os.path.relpath(p, PUB)}  {img.size[0]}x{img.size[1]}")


# --- Cargar master -------------------------------------------------------
master = Image.open(SRC).convert("RGB")
arr = np.array(master)
H, W, _ = arr.shape

d_cream = dist(arr, CREAM)
d_esp = dist(arr, ESPRESSO)

# --- 1) Localizar el tile (banda oscura superior) -----------------------
lum = arr.mean(axis=2)
darkrow = (lum < 90).mean(axis=1)
rows = [y for y in range(H) if darkrow[y] > 0.15]
bands = []
start = prev = rows[0]
for y in rows[1:]:
    if y - prev > 8:
        bands.append((start, prev)); start = y
    prev = y
bands.append((start, prev))
tile_top, tile_bot = bands[0]
cols = [x for x in range(W) if (lum[tile_top:tile_bot, x] < 90).mean() > 0.15]
tile_x0, tile_x1 = cols[0], cols[-1]
# margen para incluir el anti-aliasing del borde del tile
m = 12
TB = (max(0, tile_x0 - m), max(0, tile_top - m),
      min(W, tile_x1 + m), min(H, tile_bot + m))
print("tile box", TB)


def _trim_bottom_seam(mask, ca):
    """Limpia el 'seam' claro del borde inferior (fila tan que quedó del corte
    del cuello contra el tile). No toca el hocico (centro)."""
    rows_any = np.where(mask.any(axis=1))[0]
    if len(rows_any):
        for y in range(rows_any.max(), rows_any.max() - 14, -1):
            px = ca[y][mask[y]]
            if len(px) and px[:, 1].mean() > 120:   # verde alto => seam claro
                mask[y] = False
            else:
                break
    return mask


def segment():
    """Segmenta el master en máscaras (coordenadas del crop TB):
    llama (componente central) y dots (el escupitajo, interior)."""
    crop = master.crop(TB)
    ca = np.array(crop)
    cd_cream = dist(ca, CREAM)
    cd_esp = dist(ca, ESPRESSO)
    bg = flood_from_border((cd_cream < 40) | (cd_esp < 30))
    fg = ~bg
    ys, xs = np.where(fg)
    cy, cx = int(ys.mean()), int(xs.mean())
    if not fg[cy, cx]:
        cy, cx = int(np.median(ys)), int(np.median(xs))
    llama = _trim_bottom_seam(flood_from_seed(fg, cy, cx), ca)
    # dots = interior (excluye el rim del borde) menos la llama
    B = 48
    interior = fg.copy()
    interior[:B, :] = interior[-B:, :] = False
    interior[:, :B] = interior[:, -B:] = False
    dots = interior & ~llama
    return crop, llama, dots


_SEG = segment()


def build_mark(with_spit: bool):
    """Llama sobre fondo transparente (crop ajustado)."""
    crop, llama, dots = _SEG
    mask = (llama | dots) if with_spit else llama
    out = crop.convert("RGBA")
    out.putalpha(alpha_smooth(mask))
    return out.crop(bbox_of(mask, pad=8, shape=mask.shape))


def compose_tile(size, target_h=0.9, shift_x=-0.05, rounded=True, radius_frac=0.225, bg=ESPRESSO):
    """Tile cuadrado espresso con la llama escalada a `target_h` de la altura
    (grande, aprovechando el cuadro) y los puntitos como acento, preservando su
    geometría relativa. `shift_x` corre el conjunto para dejar aire a los dots."""
    crop, llama, dots = _SEG
    lx0, ly0, lx1, ly1 = bbox_of(llama, shape=llama.shape)
    lh = ly1 - ly0
    sc = (size * target_h) / lh
    base = crop.convert("RGBA")
    llama_img = base.copy(); llama_img.putalpha(alpha_smooth(llama))
    dots_img = base.copy(); dots_img.putalpha(alpha_smooth(dots))
    ns = (max(1, int(crop.width * sc)), max(1, int(crop.height * sc)))
    llama_s = llama_img.resize(ns, Image.LANCZOS)
    dots_s = dots_img.resize(ns, Image.LANCZOS)
    lcx = ((lx0 + lx1) / 2) * sc
    lcy = ((ly0 + ly1) / 2) * sc
    offx = int(size / 2 + shift_x * size - lcx)
    offy = int(size / 2 - lcy)
    canvas = Image.new("RGBA", (size, size), (*bg, 255))
    canvas.alpha_composite(dots_s, (offx, offy))
    canvas.alpha_composite(llama_s, (offx, offy))
    if rounded:
        r = int(size * radius_frac)
        m = Image.new("L", (size, size), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=255)
        canvas.putalpha(m)
    return canvas


def resized(img, size):
    return img.resize((size, size), Image.LANCZOS)


# ========================================================================
print("mark-tile / mark …")
mark = build_mark(with_spit=False)      # llama sola (usos inline compactos)
mark_spit = build_mark(with_spit=True)  # llama + escupitajo (transparente)
# Tile: espresso redondeado prístino, llama grande (90% del alto) + dots acento.
mark_tile = compose_tile(1024, target_h=0.82, shift_x=-0.05)
save(resized(mark_tile, 512), "mark-tile.png")
save(resized(mark_tile, 192), "mark-tile-192.png")
save(resized(mark_tile, 96), "mark-tile-96.png")
save(mark, "mark.png")
save(mark_spit, "mark-spit.png")

# cara: crop cuadrado centrado en la cara (parte superior de la llama)
mw, mh = mark.size
face_side = int(mw * 0.82)
fx = (mw - face_side) // 2
fy = int(mh * 0.06)
face = mark.crop((fx, fy, fx + face_side, min(mh, fy + face_side)))
save(resized(face, 256), "mark-face.png")

# silueta blanca (watermark decorativo)
sil = Image.new("RGBA", mark.size, (0, 0, 0, 0))
white = Image.new("RGBA", mark.size, (255, 255, 255, 255))
sil.paste(white, (0, 0), mark)
save(sil, "mark-silhouette-white.png")

# --- Favicon + PWA (tile redondeado para tab; cuadrado full-bleed para OS) ---
print("favicon / PWA …")
save(resized(mark_tile, 48), "favicon.png", root=PUB)
save(resized(mark_tile, 32), "favicon-32.png", root=PUB)
# apple-touch e icon-*: cuadrado sólido espresso con la llama + escupitajo
# (firma de marca), esquinas las redondea el SO.
save(compose_tile(180, target_h=0.82, shift_x=-0.05, rounded=False), "apple-touch-icon.png", root=PUB)
save(compose_tile(192, target_h=0.82, shift_x=-0.05, rounded=False), "icon-192.png", root=PUB)
save(compose_tile(512, target_h=0.82, shift_x=-0.05, rounded=False), "icon-512.png", root=PUB)
# maskable: llama algo más chica por la safe-zone del launcher, pero sin quedar diminuta
save(compose_tile(192, target_h=0.72, shift_x=-0.04, rounded=False), "icon-maskable-192.png", root=PUB)
save(compose_tile(512, target_h=0.72, shift_x=-0.04, rounded=False), "icon-maskable-512.png", root=PUB)

# --- Wordmark transparente (crop del master, crema -> alpha) -------------
print("wordmark / lockups / og …")
wm_top, wm_bot = bands[1]
WB = (140, max(0, wm_top - 10), 920, min(H, wm_bot + 10))
wm_crop = master.crop(WB)
wa = np.array(wm_crop)
wm_bg = flood_from_border(dist(wa, CREAM) < 30)
wm_img = wm_crop.convert("RGBA")
wm_img.putalpha(alpha_smooth(~wm_bg))
wm_img = wm_img.crop(bbox_of(~wm_bg, pad=6, shape=wm_bg.shape))
save(wm_img, "wordmark.png")

# lockup horizontal: mark-tile + wordmark sobre crema
def lockup_horizontal():
    pad = 60
    gap = 48
    th = 200  # alto del mark
    tile = resized(mark_tile, th)
    wscale = (th * 0.42) / wm_img.size[1]
    wm = wm_img.resize((int(wm_img.size[0] * wscale), int(wm_img.size[1] * wscale)), Image.LANCZOS)
    w = pad + th + gap + wm.size[0] + pad
    h = pad + th + pad
    canvas = Image.new("RGBA", (w, h), (*CREAM, 255))
    canvas.paste(tile, (pad, pad), tile)
    canvas.paste(wm, (pad + th + gap, (h - wm.size[1]) // 2), wm)
    return canvas

def lockup_vertical():
    pad = 60
    gap = 40
    th = 260
    tile = resized(mark_tile, th)
    wscale = (th * 0.34) / wm_img.size[1]
    wm = wm_img.resize((int(wm_img.size[0] * wscale), int(wm_img.size[1] * wscale)), Image.LANCZOS)
    w = pad + max(th, wm.size[0]) + pad
    h = pad + th + gap + wm.size[1] + pad
    canvas = Image.new("RGBA", (w, h), (*CREAM, 255))
    canvas.paste(tile, ((w - th) // 2, pad), tile)
    canvas.paste(wm, ((w - wm.size[0]) // 2, pad + th + gap), wm)
    return canvas

save(lockup_horizontal(), "lockup-horizontal.png")
save(lockup_vertical(), "lockup-vertical.png")

# og-image 1200x630 sobre crema, lockup horizontal centrado
og = Image.new("RGBA", (1200, 630), (*CREAM, 255))
lh = lockup_horizontal()
lh.thumbnail((1000, 480), Image.LANCZOS)
og.paste(lh, ((1200 - lh.size[0]) // 2, (630 - lh.size[1]) // 2), lh)
save(og.convert("RGB"), "og-image.png")

print("OK")
