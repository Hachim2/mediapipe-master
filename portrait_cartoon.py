"""Capture locale, caricature OpenCV et document A4 autonome."""

import base64
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


def crop_face(frame, landmarks):
    """Recadre le visage avec une marge, sans modifier la photo source."""
    if not landmarks:
        raise ValueError("Aucun visage detecte : capture impossible.")
    h, w = frame.shape[:2]
    points = np.array([(p.x * w, p.y * h) for p in landmarks])
    if not np.isfinite(points).all():
        raise ValueError("Coordonnees du visage invalides.")
    low, high = points.min(axis=0), points.max(axis=0)
    size = high - low
    if min(size) < 2:
        raise ValueError("Visage trop petit pour la capture.")
    low = np.maximum(0, np.floor(low - size * (0.25, 0.35))).astype(int)
    high = np.minimum((w, h), np.ceil(high + size * (0.25, 0.25))).astype(int)
    x0, y0 = low
    x1, y1 = high
    if x1 <= x0 or y1 <= y0:
        raise ValueError("Visage hors du cadre.")
    return frame[y0:y1, x0:x1].copy()


def cartoonize(photo):
    """Grossit doucement le centre du portrait, simplifie les couleurs et trace les contours."""
    h, w = photo.shape[:2]
    # Limiter le travail sur le Pi et garder un rapport largeur/hauteur intact.
    scale = min(1.0, 900 / max(h, w))
    photo = cv2.resize(photo, (max(3, round(w * scale)), max(3, round(h * scale))))
    h, w = photo.shape[:2]
    y, x = np.mgrid[:h, :w].astype(np.float32)
    nx = (x - (w - 1) / 2) / (w / 2)
    ny = (y - (h - 1) / 2) / (h / 2)
    bulge = 1 - 0.30 * np.exp(-2.5 * (nx * nx + ny * ny))
    warped = cv2.remap(photo, (w - 1) / 2 + nx * bulge * w / 2,
                       (h - 1) / 2 + ny * bulge * h / 2,
                       cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    colors = cv2.bilateralFilter(warped, 9, 90, 90)
    colors = ((colors.astype(np.uint16) // 32) * 32 + 16).clip(0, 255).astype(np.uint8)
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    edges = cv2.adaptiveThreshold(cv2.medianBlur(gray, 5), 255,
                                  cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 7)
    return cv2.bitwise_and(colors, colors, mask=edges)


def encode_png(image):
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise OSError("Impossible d'encoder le portrait en PNG.")
    return encoded.tobytes()


def save_portrait(frame, landmarks, output_dir):
    """Sauvegarde photo, cartoon et HTML imprimable dans un dossier unique."""
    photo = crop_face(frame, landmarks)
    cartoon = cartoonize(photo)
    photo_bytes, cartoon_bytes = encode_png(photo), encode_png(cartoon)
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    folder = root / datetime.now().strftime("portrait-%Y%m%d-%H%M%S-%f")
    folder.mkdir()
    (folder / "photo.png").write_bytes(photo_bytes)
    (folder / "cartoon.png").write_bytes(cartoon_bytes)
    data = base64.b64encode(cartoon_bytes).decode("ascii")
    page = folder / "imprimer.html"
    page.write_text("""<!doctype html>
<html lang="fr"><meta charset="utf-8">
<title>Mon portrait cartoon</title>
<style>
@page { size: A4 portrait; margin: 15mm; }
* { box-sizing: border-box; }
body { margin: 0; background: #eee; font-family: sans-serif; text-align: center; }
main { background: white; max-width: 210mm; margin: 20px auto; padding: 15mm; }
h1 { margin: 0 0 8mm; font-size: 24pt; }
img { display: block; max-width: 100%; width: auto; height: auto;
      max-height: 225mm; margin: auto; object-fit: contain; }
button { margin: 16px; padding: 12px 24px; font-size: 16px; cursor: pointer; }
@media print {
  body { background: white; }
  main { margin: 0; padding: 0; max-width: none; }
  .controls { display: none; }
}
</style>
<div class="controls"><button onclick="window.print()">Imprimer / Enregistrer en PDF</button>
<p>Choisissez le format A4 dans la boîte d’impression.</p></div>
<main><h1>Mon portrait cartoon</h1>
<img alt="Portrait avec effet cartoon et déformation amusante" src="data:image/png;base64,"""
                    + data + '\"></main></html>', encoding="utf-8")
    return page
