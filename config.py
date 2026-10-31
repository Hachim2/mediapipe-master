"""Réglages du projet : modifier ici, puis relancer le programme.

Les noms en MAJUSCULES sont des constantes par convention en Python.
Le dessin est calibré pour 32 × 32 : changer la taille exige aussi
d'adapter les positions des yeux et de la bouche. Les indices anatomiques
sont liés au modèle MediaPipe et ne sont normalement pas à modifier.
"""

from pathlib import Path

# SELPHY : vide = aperçu/export seulement. Utiliser le nom exact de la file CUPS.
PRINTER_QUEUE = ""
# Copier uniquement les clés/valeurs exposées par lpoptions -p NOM -l.
# Configurer le format carte postale RP-108 et le mode couleur avant utilisation.
PRINTER_OPTIONS = {}
PRINT_SAFETY_MARGIN_MM = 4.0
CUPS_TIMEOUT_SECONDS = 20

# ==============================================================================
# CONFIGURATION MATRICE
# ==============================================================================
MATRIX_W = 32          # 32 colonnes
MATRIX_H = 32          # 32 lignes
LED_RENDER_SIZE = 16   # 512 pixels à l'écran

# Zones mortes autour de la dernière mesure acceptée (0 désactive le filtre).
# Augmenter ces valeurs réduit les tremblements, mais demande plus de mouvement.
# Les distances sont exprimées en LEDs logiques, pas en pixels de la caméra.
DEADZONE_PUPIL = 0.30
DEADZONE_EYE_OPEN = 0.08  # Fraction de l'ouverture des paupières (0 à 1).
DEADZONE_MOUTH_OPEN = 0.45
DEADZONE_MOUTH_WIDTH = 0.50
DEADZONE_SMILE = 0.20

MODEL_PATH = str(Path(__file__).resolve().parent / "face_landmarker.task")
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

# ==============================================================================
# POINTS ANATOMIQUES REQUIS (YEUX + IRIS + BOUCHE)
# ==============================================================================
EYE_1_C1, EYE_1_C2 = 33, 133
EYE_1_TOP, EYE_1_BOTTOM = 159, 145
EYE_1_IRIS = 468

EYE_2_C1, EYE_2_C2 = 362, 263
EYE_2_TOP, EYE_2_BOTTOM = 386, 374
EYE_2_IRIS = 473

MOUTH_C1, MOUTH_C2 = 61, 291
MOUTH_IN_TOP, MOUTH_IN_BOTTOM = 13, 14
MOUTH_OUT_TOP, MOUTH_OUT_BOTTOM = 0, 17

ALL_POINTS = [
    EYE_1_C1, EYE_1_C2, EYE_1_TOP, EYE_1_BOTTOM, EYE_1_IRIS,
    EYE_2_C1, EYE_2_C2, EYE_2_TOP, EYE_2_BOTTOM, EYE_2_IRIS,
    MOUTH_C1, MOUTH_C2, MOUTH_IN_TOP, MOUTH_IN_BOTTOM, MOUTH_OUT_TOP, MOUTH_OUT_BOTTOM
]


# Caméra USB / périphérique accessible à OpenCV.
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_MIRROR = True
WINDOW_TITLE = "Visage - Animation Stylisee & Vivante"
WINDOW_WIDTH = 1160
WINDOW_HEIGHT = 520

# Détection : seuils de confiance entre 0 et 1.
NUM_FACES = 1
DETECTION_CONFIDENCE = 0.5
PRESENCE_CONFIDENCE = 0.5
TRACKING_CONFIDENCE = 0.5

# Calibration et limites des mouvements (distances en LEDs logiques).
EYE_CLOSED_RATIO = 0.14
EYE_OPEN_RATIO = 0.28
PUPIL_X_GAIN = 2.3
PUPIL_X_LIMIT = 2.2
PUPIL_Y_GAIN = 1.5
PUPIL_Y_LIMIT = 1.3
MOUTH_WIDTH_GAIN = 16.0
MOUTH_WIDTH_MIN = 6.0
MOUTH_WIDTH_MAX = 15.0
MOUTH_WIDTH_INITIAL = 11.0
MOUTH_OPEN_RATIO = 0.028
MOUTH_OPEN_GAIN = 32.0
MOUTH_OPEN_MIN = 0.5
MOUTH_OPEN_MAX = 7.5
SMILE_GAIN = 40.0
SMILE_MIN = -1.5
SMILE_MAX = 3.0

# Lissage : plus proche de 1 = plus réactif, plus proche de 0 = plus lent.
A_PUPIL = 0.55
A_EYE = 0.70
A_MOUTH = 0.65

# Rendu : couleurs OpenCV au format BGR (bleu, vert, rouge).
COLOR_AMBER = (0, 180, 255)
COLOR_PUPIL = (255, 255, 255)
COLOR_DIM = (0, 60, 100)
COLOR_IDLE_EYES = (50, 50, 50)
COLOR_IDLE_MOUTH = (40, 40, 40)
EYE_LEFT_X = 8
EYE_RIGHT_X = 23
EYE_Y = 11
EYE_HALF_WIDTH = 3
EYE_HALF_HEIGHT = 2.5
EYE_CLOSED_RENDER_THRESHOLD = 0.15
PUPIL_VISIBLE_THRESHOLD = 0.40
MOUTH_CENTER_X = 15.5
MOUTH_CENTER_Y = 23.0
MOUTH_HALF_WIDTH_MIN = 3.5
MOUTH_CLOSED_RENDER_THRESHOLD = 0.8
MOUTH_FILL_THRESHOLD = 2.5
SMILE_CORNER_GAIN = 0.7
SMILE_CLOSED_CENTER_GAIN = 0.3
SMILE_OPEN_CENTER_GAIN = 0.4
BEZIER_CLOSED_SAMPLES = 25
BEZIER_OPEN_SAMPLES = 20
LED_BACKGROUND = 10
LED_OFF_COLOR = (20, 20, 20)
LED_RADIUS_PADDING = 2
LED_HALO_RADIUS = 3
LED_HALO_GAIN = 0.3
LED_HIGHLIGHT_GAIN = 1.4
