"""Borne tactile locale : python kiosk.py [--demo] [--fullscreen|--windowed]."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import logging
import math
import multiprocessing as multiprocessing
from pathlib import Path
from queue import Empty
import time
from types import SimpleNamespace

import tkinter as tk
from PIL import Image, ImageTk

import config as cfg
from kiosk_camera import camera_worker
from kiosk_flow import Flow, Settings, State, request_robot_drawing
from portrait_cartoon import save_portrait
from portrait_printing import submit_print


ROOT = Path(__file__).resolve().parent


def settings_from_config():
    return Settings(**{name: getattr(cfg, constant) for name, constant in {
        "splash": "KIOSK_SPLASH_SECONDS", "stable": "KIOSK_STABLE_SECONDS",
        "smoothing": "KIOSK_SMOOTHING_SECONDS", "center": "KIOSK_CENTER_THRESHOLD",
        "size": "KIOSK_SIZE_THRESHOLD", "min_width": "KIOSK_MIN_FACE_WIDTH",
        "min_height": "KIOSK_MIN_FACE_HEIGHT", "margin": "KIOSK_FRAME_MARGIN",
        "fresh": "KIOSK_FRAME_TIMEOUT_SECONDS", "preview": "KIOSK_PREVIEW_SECONDS",
        "countdown": "KIOSK_COUNTDOWN_SECONDS", "inactivity": "KIOSK_CHOICE_TIMEOUT_SECONDS",
        "success": "KIOSK_SUCCESS_TIMEOUT_SECONDS", "departure": "KIOSK_DEPARTURE_SECONDS",
    }.items()})


def load_logos():
    logos = []
    for path in (cfg.KIOSK_STARTUP_LOGO, cfg.KIOSK_HOME_LOGO):
        try:
            with Image.open(path) as image:
                logos.append(image.convert("RGBA"))
        except (OSError, ValueError):
            logging.info("Logo absent/illisible : %s ; visuel de remplacement", path)
            logos.append(None)
    return logos


def generate_portrait(packet, demo):
    points = [SimpleNamespace(x=x, y=y) for x, y in packet["faces"][0]]
    page = save_portrait(packet["frame"], points, ROOT / "portraits" / ("demo" if demo else "visiteurs"),
                         cfg.PRINT_SAFETY_MARGIN_MM)
    with Image.open(page.parent / "tirage.png") as image:
        return page.parent / "tirage.png", image.convert("RGB")


def print_session(path, demo):
    # Barriere materielle aussi dans la tache : le mode demo ne peut pas appeler CUPS.
    if demo:
        return "demonstration"
    return submit_print(path, cfg.PRINTER_QUEUE, dict(cfg.PRINTER_OPTIONS), cfg.CUPS_TIMEOUT_SECONDS)


class Kiosk:
    def __init__(self, root, demo=False, fullscreen=False):
        self.root, self.demo = root, demo
        self.colors = cfg.KIOSK_COLORS
        self.flow = Flow(time.monotonic(), settings_from_config())
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.logos_future = self.pool.submit(load_logos)
        self.logos = [None, None]
        self.job = None
        self.job_kind = None
        self.packet = None
        self.portrait_path = self.portrait = None
        self.camera_image = None
        self.image_cache = {}
        self.references = []
        self.buttons = []
        self.flash_until = 0
        self.camera_problem = False
        self.closed = False
        self.fullscreen = fullscreen
        self.context = multiprocessing.get_context("spawn")
        self.queue = self.context.Queue(maxsize=2)
        self.stop = self.context.Event()
        self.camera = self.context.Process(target=camera_worker, args=(self.queue, self.stop, demo), daemon=True)
        self.camera.start()
        root.title("Atelier Portrait — borne cartoon")
        root.geometry(cfg.KIOSK_WINDOW_SIZE)
        root.minsize(480, 480)
        root.configure(bg=self.colors["background"])
        root.attributes("-fullscreen", fullscreen)
        self.canvas = tk.Canvas(root, bg=self.colors["background"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonRelease-1>", self.clicked)
        root.bind("<F11>", self.toggle_fullscreen)
        root.bind("<Escape>", self.leave_fullscreen)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.timer = root.after(20, self.update)

    def toggle_fullscreen(self, event=None):
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

    def leave_fullscreen(self, event=None):
        self.fullscreen = False
        self.root.attributes("-fullscreen", False)

    def clear_portrait(self):
        self.portrait_path = self.portrait = None
        self.image_cache.clear()

    def action(self, action):
        now, state = time.monotonic(), self.flow.state
        self.flow.activity = now
        if action == "restart" and state != State.PRINTING:
            if not self.camera.is_alive():
                self.camera.join(timeout=0)
                self.camera = self.context.Process(target=camera_worker,
                    args=(self.queue, self.stop, self.demo), daemon=True)
                self.camera.start()
            self.clear_portrait()
            self.flow.restart(now)
        elif action == "finish" and state != State.PRINTING:
            self.clear_portrait()
            self.flow.finish(now)
        elif action == "draw" and state == State.CHOICE:
            self.flow.go(State.DRAW, now)
        elif action == "back" and state in {State.DRAW, State.ERROR} and self.portrait is not None:
            self.flow.go(State.CHOICE, now)
        elif action == "retry_print" and state == State.ERROR and self.flow.print_retry:
            self.flow.go(State.CHOICE, now)
            self.action("print")
        elif action == "print" and self.portrait_path and self.job is None:
            if self.flow.request_print(now):
                self.job_kind = "print"
                self.job = self.pool.submit(print_session, self.portrait_path, self.demo)
        self.render(now)

    def clicked(self, event):
        for (x0, y0, x1, y1), action in self.buttons:
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                self.action(action)
                break

    def update(self):
        if self.closed:
            return
        now = time.monotonic()
        if self.logos_future is not None and self.logos_future.done():
            self.logos = self.logos_future.result()
            self.logos_future = None
        # File bornee ; aucune attente du producteur dans le fil graphique.
        newest = None
        for _ in range(4):
            try:
                newest = self.queue.get_nowait()
            except Empty:
                break
        if newest is not None:
            if "error" in newest:
                self.camera_problem = True
                if "detail" in newest:
                    logging.error(newest["detail"])
                self.flow.camera_error(now)
            elif now - newest["time"] <= self.flow.s.fresh:
                self.camera_problem = False
                self.packet = newest
                self.flow.observe(newest["faces"], newest["time"], now)
                # La conversion BGR -> RGB ne modifie jamais la capture source.
                self.camera_image = Image.fromarray(newest["frame"][:, :, ::-1])
                self.image_cache.pop("camera", None)
        if self.job is not None and self.job.done():
            try:
                result = self.job.result()
                if self.job_kind == "generate":
                    self.portrait_path, self.portrait = result
                    self.flow.generated(now)
                else:
                    logging.info("Envoi : %s", result)
                    self.flow.print_result(now, True)
            except Exception:
                logging.exception("Echec de la tache %s", self.job_kind)
                if self.job_kind == "print":
                    retry = not self.portrait_path.with_suffix(".cups-submission").exists()
                    self.flow.print_result(now, False, retry=retry)
                else:
                    self.flow.error_kind = "generation"
                    self.flow.go(State.ERROR, now)
            self.job = self.job_kind = None
        previous = self.flow.state
        effect = self.flow.tick(now)
        if effect == "capture" and self.packet is not None and self.job is None:
            self.flash_until = now + cfg.KIOSK_FLASH_SECONDS
            self.job_kind = "generate"
            self.job = self.pool.submit(generate_portrait, self.packet, self.demo)
        if previous != State.HOME and self.flow.state == State.HOME:
            self.clear_portrait()
        if (self.flow.state == State.ERROR and self.flow.error_kind == "print"
                and now - self.flow.activity >= self.flow.s.inactivity):
            self.clear_portrait()
            self.flow.finish(now)
        self.render(now)
        self.timer = self.root.after(40, self.update)

    def text(self, x, y, text, size=20, color=None, anchor="center", width=None, bold=False):
        return self.canvas.create_text(x, y, text=text, fill=color or self.colors["text"],
            font=(cfg.KIOSK_FONT, max(10, round(size)), "bold" if bold else "normal"),
            anchor=anchor, width=width or self.canvas.winfo_width() * 0.88, justify="center")

    def rounded(self, box, fill, radius=24):
        x0, y0, x1, y1 = box
        r = min(radius, (y1 - y0) / 2, (x1 - x0) / 2)
        return self.canvas.create_polygon(x0+r,y0, x1-r,y0, x1,y0, x1,y0+r,
            x1,y1-r, x1,y1, x1-r,y1, x0+r,y1, x0,y1, x0,y1-r,
            x0,y0+r, x0,y0, smooth=True, splinesteps=16, fill=fill)

    def button(self, box, label, action, primary=False):
        self.rounded(box, self.colors["accent"] if primary else self.colors["secondary"])
        self.text((box[0]+box[2])/2, (box[1]+box[3])/2, label, self.font_size * 0.72,
                  self.colors["accent_text"] if primary else None, bold=True, width=box[2]-box[0]-24)
        self.buttons.append((box, action))

    def image(self, image, box, key):
        if image is None:
            return
        width, height = max(1, int(box[2]-box[0])), max(1, int(box[3]-box[1]))
        cache_key = (id(image), width, height)
        cached = self.image_cache.get(key)
        if cached is None or cached[0] != cache_key:
            copy = image.copy()
            copy.thumbnail((width, height), Image.Resampling.BILINEAR)
            cached = (cache_key, ImageTk.PhotoImage(copy))
            self.image_cache[key] = cached
        self.references.append(cached[1])
        self.canvas.create_image((box[0]+box[2])/2, (box[1]+box[3])/2, image=cached[1])

    def logo(self, index, box):
        if self.logos[index] is not None:
            self.image(self.logos[index], box, f"logo{index}")
            return
        cx, cy = (box[0]+box[2])/2, (box[1]+box[3])/2
        r = min(box[2]-box[0], box[3]-box[1]) * 0.30
        if index == 0:
            self.canvas.create_oval(cx-r,cy-r,cx+r,cy+r, outline=self.colors["accent"], width=3)
            self.canvas.create_line(cx-r*.55,cy,cx,cy+r*.45,cx+r*.55,cy-r*.45,
                                    fill=self.colors["accent"], width=5, smooth=True)
        else:
            self.rounded((cx-r,cy-r,cx+r,cy+r), self.colors["accent"], r*.5)
            for dx in (-.34, .34):
                self.canvas.create_oval(cx+r*dx-r*.09,cy-r*.28,cx+r*dx+r*.09,cy-r*.05,
                                        fill=self.colors["accent_text"], outline="")
            self.canvas.create_arc(cx-r*.43,cy-r*.18,cx+r*.43,cy+r*.56,start=190,extent=160,
                                    style="arc",outline=self.colors["accent_text"],width=4)

    def render(self, now):
        c = self.canvas
        c.delete("all")
        self.buttons, self.references = [], []
        w, h = max(1, c.winfo_width()), max(1, c.winfo_height())
        self.font_size = max(20, min(34, min(w, h) * .04))
        state = self.flow.state
        pad = min(w, h) * .055
        self.text(pad, pad, "ATELIER / PORTRAIT", self.font_size*.48, anchor="w", bold=True, width=w*.48)
        self.text(w-pad, pad, "DÉMONSTRATION · SANS MATÉRIEL" if self.demo else "VOTRE SOUVENIR EN COULEUR",
                  self.font_size*.38, self.colors["accent"], anchor="e", width=w*.44)
        if state == State.STARTUP:
            self.logo(0, (w*.25,h*.19,w*.75,h*.56))
            self.text(w*.5,h*.64,"Un sourire, un souvenir.",self.font_size*1.2,bold=True)
            elapsed = now-self.flow.started
            loading = "Préparation de votre atelier…" if elapsed < self.flow.s.splash else (
                "Caméra indisponible · nous essayons de la reconnecter" if self.camera_problem else
                "Chargement de la caméra et du modèle…")
            self.text(w*.5,h*.75,loading,self.font_size*.6,self.colors["muted"])
            if self.camera_problem and elapsed >= self.flow.s.splash:
                self.button((w*.3,h*.87,w*.7,h*.97),"Réessayer","restart",True)
            # Apparition progressive, sans attente bloquante.
            progress = min(1, elapsed/self.flow.s.splash)
            self.rounded((w*.35,h*.84,w*.65,h*.847),self.colors["secondary"],4)
            if progress > 0:
                self.rounded((w*.35,h*.84,w*(.35+.3*progress),h*.847),self.colors["accent"],4)
        elif state in {State.HOME, State.STABILIZING}:
            self.logo(1,(w*.32,h*.16,w*.68,h*.45))
            self.text(w*.5,h*.52,"Placez-vous devant la caméra",self.font_size,bold=True)
            message = (self.flow.stability.message if self.flow.armed else
                       "Merci ! Laissez la place au prochain sourire")
            self.text(w*.5,h*.63,message,self.font_size*.65,self.colors["muted"])
            self.text(w*.5,h*.73,"Un portrait cartoon. Un souvenir à emporter.",self.font_size*.52,self.colors["muted"])
            if not self.flow.armed:
                self.button((w*.22,h*.81,w*.78,h*.91),"Nouveau portrait","restart",True)
        elif state in {State.PREVIEW, State.COUNTDOWN}:
            title = "Installez-vous confortablement" if state == State.PREVIEW else "Votre plus beau sourire !"
            self.text(w*.5,h*.14,title,self.font_size*.85,bold=True)
            self.image(self.camera_image,(pad,h*.22,w-pad,h*.87),"camera")
            if state == State.COUNTDOWN:
                number = max(1, math.ceil(self.flow.s.countdown-(now-self.flow.entered)))
                r = min(w,h)*.095
                c.create_oval(w*.5-r,h*.52-r,w*.5+r,h*.52+r,fill=self.colors["background"],outline=self.colors["accent"],width=3)
                self.text(w*.5,h*.52,str(number),self.font_size*2.7,bold=True)
            self.text(w*.5,h*.94,"Restez bien en place",self.font_size*.55,self.colors["muted"])
        elif state == State.PROCESSING:
            self.logo(1,(w*.35,h*.22,w*.65,h*.5))
            self.text(w*.5,h*.59,"Un peu de magie…",self.font_size*1.2,bold=True)
            self.text(w*.5,h*.7,"Votre portrait prend des couleurs",self.font_size*.65,self.colors["muted"])
            self.text(w*.5,h*.8,"●" * (1+int(now*2)%3),self.font_size,self.colors["accent"])
        else:
            self.render_result(w,h,pad,now)
        # Apparition progressive et petit glissement, sans attente ni texture de tramage.
        duration = max(.01, cfg.KIOSK_TRANSITION_SECONDS)
        if state == State.HOME and now-self.flow.entered < duration:
            progress = 1-(1-(now-self.flow.entered)/duration)**3
            c.move("all",0,(1-progress)*h*.025)
            background = self.root.winfo_rgb(self.colors["background"])
            for item in c.find_all():
                if c.type(item) == "image":
                    continue
                for option in ("fill", "outline"):
                    try:
                        original = c.itemcget(item,option)
                        if original:
                            rgb = self.root.winfo_rgb(original)
                            mixed = tuple(round((a+(b-a)*progress)/257) for a,b in zip(background,rgb))
                            c.itemconfigure(item,**{option:"#%02x%02x%02x" % mixed})
                    except tk.TclError:
                        pass
        if now < self.flash_until:
            c.create_rectangle(0,0,w,h,fill="white",outline="")

    def render_result(self,w,h,pad,now):
        state, fs = self.flow.state, self.font_size
        if state == State.ERROR and self.flow.error_kind != "print":
            camera = self.flow.error_kind == "camera"
            self.text(w*.5,h*.38,"Un petit instant…" if camera else "Essayons une nouvelle photo",fs*1.1,bold=True)
            self.text(w*.5,h*.52,"La caméra n’est pas disponible. Réessayez dans un instant." if camera else
                      "Le portrait n’a pas pu être créé.",fs*.65,self.colors["muted"])
            self.button((w*.22,h*.68,w*.78,h*.8),"Réessayer","restart",True)
            return
        titles = {State.CHOICE:"Votre sourire, version cartoon",State.PRINTING:"Préparation de l’impression…",
                  State.PRINTED:"Démonstration terminée" if self.demo else "Votre demande est prise en charge",
                  State.DRAW:"Bientôt, un autre souvenir",State.ERROR:"Votre portrait est conservé"}
        self.text(w*.5,h*.14,titles.get(state,"Votre portrait"),fs*.92,bold=True)
        landscape = w/h > 1.15
        if landscape:
            image_box = (pad,h*.22,w*.56,h*.91)
            x0,x1,top,bottom = w*.61,w-pad,h*.30,h*.88
        else:
            image_box = (pad,h*.21,w-pad,h*.64)
            x0,x1,top,bottom = w*.12,w*.88,min(h*.69,h-220),h*.95
            image_box = (pad,h*.21,w-pad,top-20)
        self.image(self.portrait,image_box,"portrait")
        available = bottom-top
        if state == State.CHOICE:
            gap = available*.04
            bh = (available-2*gap)/3
            for i,(label,action) in enumerate((("Impression","print"),("Dessin","draw"),("Reprendre la photo","restart"))):
                self.button((x0,top+i*(bh+gap),x1,top+i*(bh+gap)+bh),label,action,i==0)
        else:
            messages = {
                State.PRINTING:"Simulation uniquement…" if self.demo else "Nous envoyons votre portrait. Merci de patienter.",
                State.PRINTED:"Aucune impression réelle n’a été lancée." if self.demo else
                    "Demande d’impression acceptée. La sortie de la photo n’est pas encore confirmée.",
                State.DRAW:request_robot_drawing(),
                State.ERROR:("L’impression n’a pas pu être envoyée. Vous pouvez réessayer." if self.flow.print_retry else
                    "L’envoi doit être vérifié par un responsable avant une nouvelle impression."),
            }
            self.text((x0+x1)/2,top+available*.20,messages.get(state,""),fs*.61,
                      self.colors["muted"],width=x1-x0)
            if state == State.PRINTING:
                self.text((x0+x1)/2,top+available*.70,"●"*(1+int(now*2)%3),fs,self.colors["accent"])
            elif state == State.PRINTED:
                self.button((x0,top+available*.65,x1,bottom),"Terminer","finish",True)
            elif state == State.DRAW:
                self.button((x0,top+available*.65,x1,bottom),"Revenir au portrait","back",True)
            elif state == State.ERROR:
                if self.flow.print_retry:
                    self.button((x0,bottom-126,x1,bottom-70),"Réessayer","retry_print",True)
                self.button((x0,bottom-56,x1,bottom),"Revenir au portrait","back")

    def close(self):
        self.closed = True
        self.root.after_cancel(self.timer)
        self.stop.set()
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()

    def cleanup(self):
        self.stop.set()
        self.camera.join(timeout=2)
        if self.camera.is_alive():
            self.camera.terminate()
            self.camera.join(timeout=2)
        self.queue.close()
        self.queue.cancel_join_thread()
        # Les envois deja engages se terminent ; ne jamais les relancer a la fermeture.
        self.pool.shutdown(wait=True, cancel_futures=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Illustration, sans camera ni appel CUPS")
    display = parser.add_mutually_exclusive_group()
    display.add_argument("--fullscreen", action="store_true")
    display.add_argument("--windowed", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(filename=ROOT/"kiosk.log",level=logging.INFO,encoding="utf-8")
    root = tk.Tk()
    app = Kiosk(root,args.demo,args.fullscreen or (cfg.KIOSK_FULLSCREEN and not args.windowed))
    try:
        root.mainloop()
    finally:
        app.cleanup()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
