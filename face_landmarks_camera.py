# -*- coding: utf-8 -*-
"""
Matrice LED Stylisée & Vivante (Style Robot / Herman)
====================================================
Architecture :
1. DÉTECTION (MediaPipe) : Extraction des iris, des paupières et des lèvres.
2. ANIMATION CONTINUE :
   - Pupilles qui glissent en temps réel dans les yeux (regard fluide à 360°).
   - Clignement souple (l'œil s'écrase progressivement jusqu'au trait fermé).
   - Bouche géométrique vivante (ouverture, largeur et sourire s'animent en direct).
   - Formes 100% symétriques, régulières et sans scintillement.
"""

import sys
import os
import math

# This file lives next to a MediaPipe source checkout.  Do not let that
# unbuilt checkout shadow the installed `mediapipe` Python package.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path = [
    path for path in sys.path
    if os.path.abspath(path or os.getcwd()) != SCRIPT_DIR
]

import cv2
import numpy as np
import urllib.request
import serial
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

sys.stdout.reconfigure(encoding="utf-8")

# ==============================================================================
# CONFIGURATION MATRICE
# ==============================================================================
MATRIX_W = 32          # 32 colonnes
MATRIX_H = 32          # 32 lignes
LED_RENDER_SIZE = 16   # 512 pixels à l'écran
SERIAL_PORT = "COM5"   # Port USB virtuel de la Nucleo; mettre None pour desactiver
SERIAL_BAUDRATE = 115200

MODEL_PATH = os.path.join(SCRIPT_DIR, "face_landmarker.task")
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


# ==============================================================================
# CHARGEMENT DU DETECTEUR
# ==============================================================================
if not os.path.exists(MODEL_PATH):
    print("Telechargement du modele FaceLandmarker...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Modele telecharge.")

base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    output_face_blendshapes=False,
    output_facial_transformation_matrixes=False,
    num_faces=1,
    min_face_detection_confidence=0.5,
    min_face_presence_confidence=0.5,
    min_tracking_confidence=0.5,
)
detector = vision.FaceLandmarker.create_from_options(options)


# ==============================================================================
# MOTEUR D'ANIMATION FACIALE CONTINUE
# ==============================================================================
class RobotFaceAnimator:
    def __init__(self):
        # Paramètres d'interpolation lissés (EMA réactif)
        self.pupil_x = 0.0      # Décalage pupille en LEDs (-2.5 à +2.5)
        self.pupil_y = 0.0      # Décalage vertical pupille (-1.5 à +1.5)
        self.eye_l_open = 1.0   # Ouverture œil G (0.0 fermé à 1.0 ouvert)
        self.eye_r_open = 1.0   # Ouverture œil D (0.0 fermé à 1.0 ouvert)

        self.mouth_open = 0.0   # Hauteur d'ouverture bouche en LEDs (0.0 à 7.0)
        self.mouth_width = 11.0 # Largeur bouche en LEDs (6.0 à 15.0)
        self.smile_curve = 0.0  # Courbure du sourire (-2.0 à +3.0)

    def update(self, landmarks, w, h):
        pts = {i: np.array([landmarks[i].x * w, landmarks[i].y * h], dtype=np.float32) for i in ALL_POINTS}

        # 1. Repère local des yeux
        c1 = (pts[EYE_1_C1] + pts[EYE_1_C2]) / 2.0
        c2 = (pts[EYE_2_C1] + pts[EYE_2_C2]) / 2.0

        if c1[0] < c2[0]:
            eye_l = (pts[EYE_1_C1], pts[EYE_1_C2], pts[EYE_1_TOP], pts[EYE_1_BOTTOM], pts[EYE_1_IRIS])
            eye_r = (pts[EYE_2_C1], pts[EYE_2_C2], pts[EYE_2_TOP], pts[EYE_2_BOTTOM], pts[EYE_2_IRIS])
            c_left, c_right = c1, c2
        else:
            eye_l = (pts[EYE_2_C1], pts[EYE_2_C2], pts[EYE_2_TOP], pts[EYE_2_BOTTOM], pts[EYE_2_IRIS])
            eye_r = (pts[EYE_1_C1], pts[EYE_1_C2], pts[EYE_1_TOP], pts[EYE_1_BOTTOM], pts[EYE_1_IRIS])
            c_left, c_right = c2, c1

        vec_eyes = c_right - c_left
        dist_eyes = np.linalg.norm(vec_eyes)
        if dist_eyes < 1e-4:
            return None

        u_h = vec_eyes / dist_eyes
        u_v = np.array([-u_h[1], u_h[0]], dtype=np.float32)

        # 2. Ouverture continue des yeux (normalisée entre 0.0 et 1.0)
        def get_openness(eye):
            w_e = abs(np.dot(eye[1] - eye[0], u_h))
            h_e = abs(np.dot(eye[3] - eye[2], u_v))
            ear = h_e / (w_e + 1e-5)
            # 0.14 = fermé, 0.28+ = grand ouvert
            return float(np.clip((ear - 0.14) / (0.28 - 0.14), 0.0, 1.0))

        raw_open_l = get_openness(eye_l)
        raw_open_r = get_openness(eye_r)

        # 3. Position continue du regard (Pupilles)
        def get_iris_offset(eye):
            min_x, max_x = min(eye[0][0], eye[1][0]), max(eye[0][0], eye[1][0])
            min_y, max_y = min(eye[2][1], eye[3][1]), max(eye[2][1], eye[3][1])
            # Centré à 0.0 (-1.0 à gauche, +1.0 à droite)
            norm_x = (eye[4][0] - (min_x + max_x) / 2.0) / ((max_x - min_x) / 2.0 + 1e-5)
            norm_y = (eye[4][1] - (min_y + max_y) / 2.0) / ((max_y - min_y) / 2.0 + 1e-5)
            return np.clip(norm_x, -1.0, 1.0), np.clip(norm_y, -1.0, 1.0)

        gx_l, gy_l = get_iris_offset(eye_l)
        gx_r, gy_r = get_iris_offset(eye_r)

        target_pupil_x = float(np.clip(((gx_l + gx_r) / 2.0) * 2.3, -2.2, 2.2))
        target_pupil_y = float(np.clip(((gy_l + gy_r) / 2.0) * 1.5, -1.3, 1.3))

        # 4. Paramètres continus de la bouche
        w_mouth_raw = abs(np.dot(pts[MOUTH_C2] - pts[MOUTH_C1], u_h)) / dist_eyes
        h_inner_raw = abs(np.dot(pts[MOUTH_IN_BOTTOM] - pts[MOUTH_IN_TOP], u_v)) / dist_eyes

        # Sourire : hauteur relative commissures vs centre
        mid_corners = (pts[MOUTH_C1] + pts[MOUTH_C2]) / 2.0
        mid_lips = (pts[MOUTH_OUT_TOP] + pts[MOUTH_OUT_BOTTOM]) / 2.0
        smile_val = np.dot(mid_lips - mid_corners, u_v) / dist_eyes

        # Mapping continu sur les dimensions de la matrice
        target_mouth_w = float(np.clip(w_mouth_raw * 16.0, 6.0, 15.0))
        # Seuil doux : commence à s'ouvrir dès 0.025
        if h_inner_raw < 0.028:
            target_mouth_h = 0.0
        else:
            target_mouth_h = float(np.clip((h_inner_raw - 0.028) * 32.0, 0.5, 7.5))

        target_smile = float(np.clip(smile_val * 40.0, -1.5, 3.0))

        # 5. Lissage exponentiel réactif (zéro latence, 100% organique)
        A_PUPIL = 0.55
        A_EYE = 0.70
        A_MOUTH = 0.65

        self.pupil_x = A_PUPIL * target_pupil_x + (1.0 - A_PUPIL) * self.pupil_x
        self.pupil_y = A_PUPIL * target_pupil_y + (1.0 - A_PUPIL) * self.pupil_y

        self.eye_l_open = A_EYE * raw_open_l + (1.0 - A_EYE) * self.eye_l_open
        self.eye_r_open = A_EYE * raw_open_r + (1.0 - A_EYE) * self.eye_r_open

        self.mouth_open = A_MOUTH * target_mouth_h + (1.0 - A_MOUTH) * self.mouth_open
        self.mouth_width = A_MOUTH * target_mouth_w + (1.0 - A_MOUTH) * self.mouth_width
        self.smile_curve = A_MOUTH * target_smile + (1.0 - A_MOUTH) * self.smile_curve

        return {
            "pupil_x": self.pupil_x,
            "pupil_y": self.pupil_y,
            "eye_l_open": self.eye_l_open,
            "eye_r_open": self.eye_r_open,
            "mouth_h": self.mouth_open,
            "mouth_w": self.mouth_width,
            "smile": self.smile_curve,
            "mouth_c1": pts[MOUTH_C1],
            "mouth_c2": pts[MOUTH_C2],
            "mouth_top": pts[MOUTH_IN_TOP],
            "mouth_bot": pts[MOUTH_IN_BOTTOM],
        }


def compute_quadratic_bezier(p0, p_mid, p2, num_samples=25):
    """
    Calcule une courbe de Bézier quadratique passant exactement par :
    - p0 à t = 0.0
    - p_mid à t = 0.5
    - p2 à t = 1.0
    Formule : B(t) = (1-t)² P₀ + 2(1-t)t P₁ + t² P₂
    avec P₁ = 2·P_mid - 0.5·(P₀ + P₂)
    """
    p1 = 2.0 * p_mid - 0.5 * (p0 + p2)
    t = np.linspace(0.0, 1.0, num_samples, dtype=np.float32)[:, None]
    return ((1.0 - t) ** 2) * p0 + 2.0 * (1.0 - t) * t * p1 + (t ** 2) * p2


# ==============================================================================
# RENDU STYLISÉ ET FLUIDE SUR MATRICE 32x32
# ==============================================================================
def render_living_robot_face(anim):
    grid = np.zeros((MATRIX_H, MATRIX_W, 3), dtype=np.uint8)

    COLOR_AMBER = (0, 180, 255)       # Jaune-orange ambré éclatant
    COLOR_PUPIL = (255, 255, 255)   # Blanc éclatant
    COLOR_DIM = (0, 60, 100)        # Intérieur tamisé

    if anim is None:
        grid[11, 6:12] = (50, 50, 50)
        grid[11, 20:26] = (50, 50, 50)
        grid[23, 11:21] = (40, 40, 40)
        return grid

    # --------------------------------------------------------------------------
    # 1. YEUX STYLISÉS ANIMÉS (CLIGNEMENT SOUPLE & PUPILLE FLUIDE)
    # --------------------------------------------------------------------------
    def draw_eye(cx, cy, open_ratio):
        # Si complètement fermé (< 0.15) : trait horizontal net de 7 LEDs
        if open_ratio < 0.15:
            grid[cy, cx - 3 : cx + 4] = COLOR_AMBER
            return

        # Hauteur de l'œil qui s'adapte en douceur (de 2 à 5 LEDs)
        half_h = max(1, int(round(open_ratio * 2.5)))
        half_w = 3

        # Forme arrondie stylisée de l'orbite
        for dy in range(-half_h, half_h + 1):
            # Arrondi aux coins supérieurs/inférieurs
            cur_w = half_w if abs(dy) < half_h else (half_w - 1)
            grid[cy + dy, cx - cur_w : cx + cur_w + 1] = COLOR_AMBER

        # Pupille blanche mobile (glisse continuellement)
        if open_ratio > 0.40:
            px = int(round(cx + anim["pupil_x"]))
            # Limiter le déplacement vertical selon l'ouverture
            py_limit = max(0, half_h - 1)
            py = int(round(cy + np.clip(anim["pupil_y"], -py_limit, py_limit)))

            # Pupille 2x2 lumineuse
            grid[py - 1 : py + 1, px - 1 : px + 1] = COLOR_PUPIL

    draw_eye(cx=8, cy=11, open_ratio=anim["eye_l_open"])
    draw_eye(cx=23, cy=11, open_ratio=anim["eye_r_open"])

    # --------------------------------------------------------------------------
    # 2. BOUCHE : TRACÉ EN COURBES DE BÉZIER QUADRATIQUES
    # --------------------------------------------------------------------------
    mouth_h = anim["mouth_h"]
    mouth_w = anim["mouth_w"]
    smile = anim["smile"]

    center_x = 15.5
    center_y = 23.0

    half_w = max(3.5, mouth_w / 2.0)
    p0 = np.array([center_x - half_w, center_y - smile * 0.7], dtype=np.float32)
    p2 = np.array([center_x + half_w, center_y - smile * 0.7], dtype=np.float32)

    if mouth_h < 0.8:
        # --- BOUCHE FERMÉE : Une seule courbe de Bézier quadratique continue ---
        p_mid = np.array([center_x, center_y + smile * 0.3], dtype=np.float32)
        curve = compute_quadratic_bezier(p0, p_mid, p2, num_samples=25)
        pts_curve = np.round(curve).astype(np.int32)
        cv2.polylines(grid, [pts_curve], isClosed=False, color=COLOR_AMBER, thickness=1)

    else:
        # --- BOUCHE OUVERTE : Deux courbes de Bézier (Lèvre supérieure & inférieure) ---
        p_top = np.array([center_x, center_y - mouth_h * 0.5 - smile * 0.4], dtype=np.float32)
        p_bot = np.array([center_x, center_y + mouth_h * 0.5 - smile * 0.4], dtype=np.float32)

        curve_top = compute_quadratic_bezier(p0, p_top, p2, num_samples=20)
        curve_bot = compute_quadratic_bezier(p2, p_bot, p0, num_samples=20)
        mouth_loop = np.vstack([curve_top, curve_bot])
        pts_loop = np.round(mouth_loop).astype(np.int32)

        if mouth_h >= 2.5:
            cv2.fillPoly(grid, [pts_loop], color=COLOR_DIM)
        cv2.polylines(grid, [pts_loop], isClosed=True, color=COLOR_AMBER, thickness=1)

    return grid


def create_led_display(grid_32x32):
    """
    Rendu d'écran rétro-éclairé (LEDs rondes, halo ambré chaud).
    """
    h = MATRIX_H * LED_RENDER_SIZE
    w = MATRIX_W * LED_RENDER_SIZE
    canvas = np.full((h, w, 3), 10, dtype=np.uint8)

    radius = (LED_RENDER_SIZE // 2) - 2

    for y in range(MATRIX_H):
        for x in range(MATRIX_W):
            b, g, r = grid_32x32[y, x]
            center = (x * LED_RENDER_SIZE + LED_RENDER_SIZE // 2,
                      y * LED_RENDER_SIZE + LED_RENDER_SIZE // 2)

            if b == 0 and g == 0 and r == 0:
                cv2.circle(canvas, center, radius, (20, 20, 20), -1)
            else:
                cv2.circle(canvas, center, radius + 3, (int(b * 0.3), int(g * 0.3), int(r * 0.3)), -1)
                cv2.circle(canvas, center, radius, (int(b), int(g), int(r)), -1)
                cv2.circle(canvas, center, max(1, radius // 3),
                           (min(255, int(b * 1.4)), min(255, int(g * 1.4)), min(255, int(r * 1.4))), -1)

    return canvas


def send_face_to_stm32(serial_link, anim):
    """Convertit le visage 32x32 en coordonnees pour la matrice 64x64."""
    if serial_link is None or anim is None:
        return

    left_x = int(round((8.0 + anim["pupil_x"]) * 2.0))
    left_y = int(round((11.0 + anim["pupil_y"]) * 2.0))
    right_x = int(round((23.0 + anim["pupil_x"]) * 2.0))
    right_y = int(round((11.0 + anim["pupil_y"]) * 2.0))
    mouth_opening = int(round(anim["mouth_h"] * 2.0))

    values = (
        max(0, min(63, left_x)),
        max(0, min(63, left_y)),
        max(0, min(63, right_x)),
        max(0, min(63, right_y)),
        max(0, min(24, mouth_opening)),
    )
    serial_link.write(f"{values[0]},{values[1]},{values[2]},{values[3]},{values[4]}\n".encode("ascii"))


# ==============================================================================
# PROGRAMME PRINCIPAL
# ==============================================================================
def main():
    print("Initialisation de l'animation faciale stylisee...")
    serial_link = None

    if SERIAL_PORT:
        try:
            serial_link = serial.Serial(SERIAL_PORT, SERIAL_BAUDRATE, timeout=0)
            print(f"Connexion STM32 ouverte sur {SERIAL_PORT}.")
        except serial.SerialException as error:
            print(f"AVERTISSEMENT : STM32 indisponible sur {SERIAL_PORT} : {error}")

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("ERREUR : Impossible d'acceder a la camera.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    animator = RobotFaceAnimator()

    window_title = "Matrice LED - Animation Stylisee & Vivante"
    cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_title, 1160, 520)

    print("\n" + "=" * 65)
    print(" SYSTEME D'ANIMATION FLUIDE OPERATIONNEL :")
    print(" - Regard : pupille blanche glissant continuellement avec vos yeux")
    print(" - Clignement : transition douce vers le trait ferme")
    print(" - Bouche : morphing souple en direct (parole et sourire)")
    print(" Touche 'q' pour quitter.")
    print("=" * 65 + "\n")

    while cap.isOpened():
        success, frame = cap.read()
        if not success or frame is None:
            cv2.waitKey(10)
            continue

        frame = cv2.flip(frame, 1)  # Effet miroir
        h, w = frame.shape[:2]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = detector.detect(mp_image)

        anim_state = None

        if result.face_landmarks:
            landmarks = result.face_landmarks[0]
            anim_state = animator.update(landmarks, w, h)

            # Dessin repères simples sur la webcam
            for idx in ALL_POINTS:
                px = int(landmarks[idx].x * w)
                py = int(landmarks[idx].y * h)
                cv2.circle(frame, (px, py), 2, (0, 255, 0), -1)

            if anim_state:
                # Tracé direct de la courbe de Bézier quadratique sur la webcam
                c1_cam = anim_state["mouth_c1"]
                c2_cam = anim_state["mouth_c2"]
                top_cam = anim_state["mouth_top"]
                bot_cam = anim_state["mouth_bot"]

                if anim_state["mouth_h"] < 0.8:
                    mid_cam = (top_cam + bot_cam) / 2.0
                    bez_cam = compute_quadratic_bezier(c1_cam, mid_cam, c2_cam, num_samples=25)
                    cv2.polylines(frame, [np.round(bez_cam).astype(np.int32)], False, (0, 255, 255), 2)
                else:
                    bez_top_cam = compute_quadratic_bezier(c1_cam, top_cam, c2_cam, num_samples=20)
                    bez_bot_cam = compute_quadratic_bezier(c2_cam, bot_cam, c1_cam, num_samples=20)
                    bez_loop_cam = np.vstack([bez_top_cam, bez_bot_cam])
                    cv2.polylines(frame, [np.round(bez_loop_cam).astype(np.int32)], True, (0, 180, 255), 2)

                # Diagnostics d'animation en temps réel
                gaze_dir = "Centre"
                if anim_state["pupil_x"] < -0.8: gaze_dir = "Gauche"
                elif anim_state["pupil_x"] > 0.8: gaze_dir = "Droite"
                if anim_state["pupil_y"] < -0.6: gaze_dir += " / Haut"
                elif anim_state["pupil_y"] > 0.6: gaze_dir += " / Bas"

                cv2.putText(frame, f"Regard : {gaze_dir} (x={anim_state['pupil_x']:+.1f})", (15, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
                cv2.putText(frame, f"Yeux : G={anim_state['eye_l_open']*100:.0f}% | D={anim_state['eye_r_open']*100:.0f}%", (15, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
                cv2.putText(frame, f"Bouche : H={anim_state['mouth_h']:.1f} | W={anim_state['mouth_w']:.1f} | Sourire={anim_state['smile']:+.1f}", (15, 90),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 255), 2)
        else:
            cv2.putText(frame, "Aucun visage detecte", (15, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Génération du rendu stylisé vivant
        led_grid = render_living_robot_face(anim_state)
        led_display = create_led_display(led_grid)
        send_face_to_stm32(serial_link, anim_state)

        # Vue combinée
        frame_resized = cv2.resize(frame, (int(w * (led_display.shape[0] / h)), led_display.shape[0]))
        combined = np.hstack((frame_resized, led_display))

        cv2.imshow(window_title, combined)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    if serial_link is not None:
        serial_link.close()
    cv2.destroyAllWindows()
    detector.close()
    print("Fermeture propre.")


if __name__ == "__main__":
    main()
