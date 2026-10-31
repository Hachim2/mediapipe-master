"""Verification graphique explicite : python tests/kiosk_smoke.py (demo seule)."""

from pathlib import Path
import sys
import time
import tkinter as tk

from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kiosk import Kiosk
from kiosk_flow import State


def main():
    root = tk.Tk()
    app = Kiosk(root, demo=True, fullscreen=False)
    destination = Path(__file__).resolve().parents[1] / "portraits" / "demo" / "interface"
    destination.mkdir(parents=True, exist_ok=True)
    seen = set()
    started = time.monotonic()
    checks = []

    def screenshot(name):
        root.update_idletasks()
        x, y = root.winfo_rootx(), root.winfo_rooty()
        ImageGrab.grab(bbox=(x, y, x+root.winfo_width(), y+root.winfo_height())).save(destination / f"{name}.png")

    def advance():
        if time.monotonic()-started > 35:
            checks.append("timeout")
            app.close()
            return
        state = app.flow.state
        if state not in seen:
            seen.add(state)
            screenshot(state.value)
        if state == State.CHOICE and "draw" not in checks:
            checks.append("draw")
            app.action("draw")
            root.after(250, advance)
            return
        if state == State.DRAW:
            app.action("back")
            root.geometry("600x900")
            root.after(300, portrait_check)
            return
        if state == State.PRINTED:
            app.action("finish")
            assert app.portrait is None and not app.flow.armed
            assert not list(destination.parent.rglob("*.cups-submission"))
            checks.append("success")
            app.close()
            return
        root.after(100, advance)

    def portrait_check():
        app.render(time.monotonic())
        screenshot("choix-portrait")
        for box, action in app.buttons:
            assert box[3]-box[1] >= 50, (action, box)
        app.action("print")
        app.action("print")  # Double clic simule : aucune deuxieme tache.
        root.after(150, advance)

    root.after(400, advance)
    try:
        root.mainloop()
    finally:
        app.cleanup()
    assert "success" in checks, checks
    print(f"Verification graphique demo reussie : {destination}")


if __name__ == "__main__":
    main()
