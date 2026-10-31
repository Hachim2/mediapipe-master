"""Capture locale, caricature OpenCV et tirage photo 100 × 148 mm."""

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


def prepare_print_image(cartoon, safety_margin_mm=4.0):
    """Contain, jamais crop : proportions conservees sur fond blanc a 300 ppp."""
    if not np.isfinite(safety_margin_mm) or not 0 <= safety_margin_mm < 50:
        raise ValueError("La marge doit etre comprise entre 0 et 50 mm exclus.")
    width, height = 1181, 1748
    margin = round(safety_margin_mm * 300 / 25.4)
    h, w = cartoon.shape[:2]
    if min(h, w) == 0:
        raise ValueError("Image vide.")
    scale = min((width - 2 * margin) / w, (height - 2 * margin) / h)
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    resized = cv2.resize(cartoon, size, interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA)
    canvas = np.full((height, width, 3), 255, dtype=np.uint8)
    x, y = (width - size[0]) // 2, (height - size[1]) // 2
    canvas[y:y + size[1], x:x + size[0]] = resized
    return canvas


def print_png(image):
    """Ajoute la densite PNG pHYs (300 ppp) sans dependance supplementaire."""
    import struct
    import zlib
    png = encode_png(image)
    payload = b"pHYs" + struct.pack(">IIB", 11811, 11811, 1)
    chunk = struct.pack(">I", 9) + payload + struct.pack(">I", zlib.crc32(payload))
    return png[:33] + chunk + png[33:]


def save_portrait(frame, landmarks, output_dir, safety_margin_mm=4.0):
    """Conserve les sources et exporte le tirage et une page photo autonome."""
    photo = crop_face(frame, landmarks)
    cartoon = cartoonize(photo)
    printable = prepare_print_image(cartoon, safety_margin_mm)
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    folder = root / datetime.now().strftime("portrait-%Y%m%d-%H%M%S-%f")
    folder.mkdir()
    (folder / "photo.png").write_bytes(encode_png(photo))
    (folder / "cartoon.png").write_bytes(encode_png(cartoon))
    printable_bytes = print_png(printable)
    (folder / "tirage.png").write_bytes(printable_bytes)
    data = base64.b64encode(printable_bytes).decode("ascii")
    page = folder / "imprimer.html"
    page.write_text("""<!doctype html>
<html lang="fr"><meta charset="utf-8"><title>Aperçu du portrait</title>
<style>
@page { size: 100mm 148mm; margin: 0; }
body { margin: 0; background: #ddd; text-align: center; font-family: sans-serif; }
img { display: block; width: 100mm; height: 148mm; margin: auto; }
button { padding: 12px; margin: 12px; }
@media print { .controls { display: none; } body { background: white; } }
</style>
<div class="controls"><button onclick="window.print()">Imprimer / Exporter PDF</button>
<p>Export navigateur : sélectionner 100 × 148 mm, sans en-têtes ni pieds de page.
Pour la borne, utiliser le bouton Imprimer de la fenêtre d’aperçu CUPS.</p></div>
<img alt="Portrait cartoon" src="data:image/png;base64,"""
                    + data + '\"></html>', encoding="utf-8")
    return page
