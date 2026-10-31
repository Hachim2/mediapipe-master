"""Parcours de borne testable sans interface graphique ni materiel."""

from collections import deque
from dataclasses import dataclass
from enum import Enum
import math


class State(str, Enum):
    STARTUP = "lancement"
    HOME = "accueil"
    STABILIZING = "stabilisation"
    PREVIEW = "prise_de_vue"
    COUNTDOWN = "compte_a_rebours"
    PROCESSING = "traitement"
    CHOICE = "choix"
    PRINTING = "impression"
    PRINTED = "pris_en_charge"
    DRAW = "dessin_indisponible"
    ERROR = "erreur"


@dataclass
class Settings:
    splash: float = 4.0
    stable: float = 1.5
    smoothing: float = 0.18
    center: float = 0.025
    size: float = 0.09
    min_width: float = 0.18
    min_height: float = 0.22
    margin: float = 0.02
    fresh: float = 1.2
    preview: float = 1.5
    countdown: float = 3.0
    inactivity: float = 60.0
    success: float = 15.0
    departure: float = 1.0

    def __post_init__(self):
        for name, value in vars(self).items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"Reglage invalide : {name}")
        if not 3 <= self.splash <= 5 or min(self.stable, self.fresh, self.countdown) <= 0:
            raise ValueError("Lancement : 3 a 5 s ; stabilite, fraicheur et compte a rebours > 0.")


class Stability:
    """Geometrie normalisee et EMA temporelle ; ancrage empechant une derive lente."""

    def __init__(self, settings):
        self.s = settings
        self.reset()

    def reset(self):
        self.history = deque()
        self.filtered = self.anchor = None
        self.since = self.last = None
        self.message = "Placez-vous devant la caméra"

    def update(self, faces, timestamp):
        if self.last is not None and timestamp <= self.last:
            return False
        if len(faces) != 1:
            self.reset()
            self.message = "Une seule personne devant la caméra" if faces else "Placez-vous devant la caméra"
            return False
        points = faces[0]
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        if not xs or not all(math.isfinite(v) for v in xs + ys):
            self.reset()
            return False
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        width, height = x1 - x0, y1 - y0
        if (x0 < self.s.margin or y0 < self.s.margin or x1 > 1 - self.s.margin
                or y1 > 1 - self.s.margin or width < self.s.min_width or height < self.s.min_height):
            self.reset()
            self.message = "Placez votre visage au centre, bien visible"
            return False
        current = ((x0 + x1) / 2, (y0 + y1) / 2, width, height)
        gap = self.last is None or timestamp - self.last > self.s.fresh
        alpha = 1 if gap or self.s.smoothing == 0 else 1 - math.exp(-(timestamp - self.last) / self.s.smoothing)
        filtered = current if gap else tuple(a + alpha * (b - a) for a, b in zip(self.filtered, current))

        def moved(value):
            return (max(abs(value[i] - self.anchor[i]) for i in (0, 1)) > self.s.center
                    or max(abs(value[i] / self.anchor[i] - 1) for i in (2, 3)) > self.s.size)

        if gap or self.anchor is None or moved(current) or moved(filtered):
            self.anchor = filtered = current
            self.since = timestamp
            self.history.clear()
        self.filtered, self.last = filtered, timestamp
        self.history.append(timestamp)
        while len(self.history) > 2 and self.history[1] < timestamp - self.s.stable:
            self.history.popleft()
        self.message = "Gardez la pose, c’est parfait"
        return timestamp - self.since >= self.s.stable and len(self.history) >= 2


class Flow:
    capture_states = {State.HOME, State.STABILIZING, State.PREVIEW, State.COUNTDOWN}

    def __init__(self, now, settings=None):
        self.s = settings or Settings()
        self.state = State.STARTUP
        self.entered = self.activity = now
        self.started = now
        self.ready = False
        self.last_frame = None
        self.last_observation = None
        self.stability = Stability(self.s)
        self.stable = False
        self.armed = True
        self.absent_since = None
        self.session = 0
        self.error_kind = None
        self.print_retry = False

    def go(self, state, now):
        self.state, self.entered, self.activity = state, now, now

    def observe(self, faces, timestamp, now):
        if now - timestamp > self.s.fresh or (self.last_frame is not None and timestamp <= self.last_frame):
            return
        self.last_frame = timestamp
        self.ready = True
        self.last_observation = faces
        if self.state not in self.capture_states:
            return
        if not self.armed:
            if faces:
                self.absent_since = None
            else:
                if self.absent_since is None:
                    self.absent_since = timestamp
                if timestamp - self.absent_since >= self.s.departure:
                    self.armed = True
            return
        self.stable = self.stability.update(faces, timestamp)
        if self.state in {State.PREVIEW, State.COUNTDOWN} and not self.stable:
            self.go(State.STABILIZING, now)
        elif self.state == State.HOME and faces:
            self.go(State.STABILIZING, now)
        elif self.state == State.STABILIZING and self.stable:
            self.go(State.PREVIEW, now)

    def tick(self, now):
        fresh = self.last_frame is not None and now - self.last_frame <= self.s.fresh
        if self.state == State.STARTUP:
            if now - self.started >= self.s.splash and self.ready and fresh:
                self.go(State.HOME, now)
                self.stability.reset()
        elif self.state in self.capture_states and not fresh:
            self.camera_error(now)
        elif self.state == State.PREVIEW and now - self.entered >= self.s.preview:
            self.go(State.COUNTDOWN, now)
        elif (self.state == State.COUNTDOWN and now - self.entered >= self.s.countdown
              and self.last_frame >= self.entered + self.s.countdown):
            self.go(State.PROCESSING, now)
            self.session += 1
            return "capture"
        elif self.state in {State.CHOICE, State.DRAW} and now - self.activity >= self.s.inactivity:
            self.finish(now)
        elif self.state == State.PRINTED and now - self.entered >= self.s.success:
            self.finish(now)
        return None

    def camera_error(self, now):
        self.ready = self.stable = False
        self.stability.reset()
        if self.state in self.capture_states:
            self.error_kind = "camera"
            self.go(State.ERROR, now)

    def generated(self, now):
        if self.state == State.PROCESSING:
            self.go(State.CHOICE, now)

    def request_print(self, now):
        if self.state != State.CHOICE:
            return False
        self.go(State.PRINTING, now)
        return True

    def print_result(self, now, success, retry=False):
        if self.state != State.PRINTING:
            return
        if success:
            self.go(State.PRINTED, now)
        else:
            self.error_kind, self.print_retry = "print", retry
            self.go(State.ERROR, now)

    def restart(self, now):
        if self.state == State.PRINTING:
            return
        self.session += 1
        self.stability.reset()
        self.stable = False
        self.armed = True
        self.go(State.HOME, now)

    def finish(self, now):
        if self.state == State.PRINTING:
            return
        self.restart(now)
        self.armed = False
        self.absent_since = None


def request_robot_drawing():
    """Point d'integration futur : aucune commande materielle aujourd'hui."""
    return "Le dessin robotisé sera bientôt disponible"
