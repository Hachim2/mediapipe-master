"""Fenetre de borne dans un processus distinct de la camera."""

import base64
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

import cv2
import numpy as np

from config import PRINTER_QUEUE, PRINTER_OPTIONS, CUPS_TIMEOUT_SECONDS
from portrait_printing import submit_print


def main(image_path):
    import tkinter as tk
    from tkinter import ttk

    image_path = Path(image_path).resolve()
    image = cv2.imdecode(np.frombuffer(image_path.read_bytes(), dtype=np.uint8), 1)
    if image is None:
        raise ValueError("Apercu illisible.")
    root = tk.Tk()
    root.title("Aperçu du portrait — 100 × 148 mm")
    scale = min(1, (root.winfo_screenheight() - 220) / image.shape[0],
                (root.winfo_screenwidth() - 60) / image.shape[1])
    image = cv2.resize(image, (max(1, round(image.shape[1] * scale)), max(1, round(image.shape[0] * scale))))
    encoded = cv2.imencode(".png", image)[1].tobytes()
    preview = tk.PhotoImage(data=base64.b64encode(encoded))
    ttk.Label(root, image=preview).pack(padx=12, pady=12)
    status = tk.StringVar(value="Vérifiez le cadrage avant d’imprimer." if PRINTER_QUEUE else
                          "Mode aperçu/export : aucune imprimante configurée.")
    ttk.Label(root, textvariable=status, wraplength=450).pack(padx=12)
    pool = ThreadPoolExecutor(max_workers=1)
    future = None

    def poll():
        if not future.done():
            root.after(100, poll)
            return
        try:
            status.set(future.result())
        except Exception as exc:
            status.set(str(exc))
            if not image_path.with_suffix(".cups-submission").exists():
                button.configure(state="normal")

    def print_clicked():
        nonlocal future
        button.configure(state="disabled")
        status.set("Envoi à CUPS en cours…")
        future = pool.submit(submit_print, image_path, PRINTER_QUEUE,
                             dict(PRINTER_OPTIONS), CUPS_TIMEOUT_SECONDS)
        root.after(100, poll)

    button = ttk.Button(root, text="Imprimer", command=print_clicked)
    button.pack(pady=12)
    if not PRINTER_QUEUE or image_path.with_suffix(".cups-submission").exists():
        button.configure(state="disabled")
    if image_path.with_suffix(".cups-submission").exists():
        status.set("Envoi déjà tenté pour ce portrait. Vérifiez CUPS avant toute réimpression.")
    ttk.Label(root, text=f"Export : {image_path}", wraplength=450).pack(padx=12, pady=6)
    root.mainloop()
    pool.shutdown(wait=False)


if __name__ == "__main__":
    main(sys.argv[1])
