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
from config import (
    MATRIX_W,
    MATRIX_H,
    LED_RENDER_SIZE,
    DEADZONE_PUPIL,
    DEADZONE_EYE_OPEN,
    DEADZONE_MOUTH_OPEN,
    DEADZONE_MOUTH_WIDTH,
    DEADZONE_SMILE,
    MODEL_PATH,
    MODEL_URL,
    EYE_1_C1,
    EYE_1_C2,
    EYE_1_TOP,
    EYE_1_BOTTOM,
    EYE_1_IRIS,
    EYE_2_C1,
    EYE_2_C2,
    EYE_2_TOP,
    EYE_2_BOTTOM,
    EYE_2_IRIS,
    MOUTH_C1,
    MOUTH_C2,
    MOUTH_IN_TOP,
    MOUTH_IN_BOTTOM,
    MOUTH_OUT_TOP,
    MOUTH_OUT_BOTTOM,
    ALL_POINTS,
    CAMERA_INDEX,
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
    CAMERA_MIRROR,
    WINDOW_TITLE,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    NUM_FACES,
    DETECTION_CONFIDENCE,
    PRESENCE_CONFIDENCE,
    TRACKING_CONFIDENCE,
    EYE_CLOSED_RATIO,
    EYE_OPEN_RATIO,
    PUPIL_X_GAIN,
    PUPIL_X_LIMIT,
    PUPIL_Y_GAIN,
    PUPIL_Y_LIMIT,
    MOUTH_WIDTH_GAIN,
    MOUTH_WIDTH_MIN,
    MOUTH_WIDTH_MAX,
    MOUTH_WIDTH_INITIAL,
    MOUTH_OPEN_RATIO,
    MOUTH_OPEN_GAIN,
    MOUTH_OPEN_MIN,
    MOUTH_OPEN_MAX,
    SMILE_GAIN,
    SMILE_MIN,
    SMILE_MAX,
    A_PUPIL,
    A_EYE,
    A_MOUTH,
    COLOR_AMBER,
    COLOR_PUPIL,
    COLOR_DIM,
    COLOR_IDLE_EYES,
    COLOR_IDLE_MOUTH,
    EYE_LEFT_X,
    EYE_RIGHT_X,
    EYE_Y,
    EYE_HALF_WIDTH,
    EYE_HALF_HEIGHT,
    EYE_CLOSED_RENDER_THRESHOLD,
    PUPIL_VISIBLE_THRESHOLD,
    MOUTH_CENTER_X,
    MOUTH_CENTER_Y,
    MOUTH_HALF_WIDTH_MIN,
    MOUTH_CLOSED_RENDER_THRESHOLD,
    MOUTH_FILL_THRESHOLD,
    SMILE_CORNER_GAIN,
    SMILE_CLOSED_CENTER_GAIN,
    SMILE_OPEN_CENTER_GAIN,
    BEZIER_CLOSED_SAMPLES,
    BEZIER_OPEN_SAMPLES,
    LED_BACKGROUND,
    LED_OFF_COLOR,
    LED_RADIUS_PADDING,
    LED_HALO_RADIUS,
    LED_HALO_GAIN,
    LED_HIGHLIGHT_GAIN,
)

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
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# ==============================================================================
# CHARGEMENT DU DETECTEUR
# ==============================================================================
def create_face_detector():
    if not os.path.exists(MODEL_PATH):
        print("Telechargement du modele FaceLandmarker...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("Modele telecharge.")

    base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=False,
        num_faces=NUM_FACES,
        min_face_detection_confidence=DETECTION_CONFIDENCE,
        min_face_presence_confidence=PRESENCE_CONFIDENCE,
        min_tracking_confidence=TRACKING_CONFIDENCE,
    )
    return vision.FaceLandmarker.create_from_options(options)


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
        self.mouth_width = MOUTH_WIDTH_INITIAL # Largeur bouche en LEDs (6.0 à 15.0)
        self.smile_curve = 0.0  # Courbure du sourire (-2.0 à +3.0)

        self._stable_targets = {}

    def _stabilize(self, name, value, deadzone):
        """Conserve la cible tant que la mesure reste dans sa zone morte."""
        # Comparer à la dernière cible acceptée, jamais à la frame précédente :
        # un mouvement lent finit ainsi par dépasser le seuil et reste détecté.
        if name not in self._stable_targets or abs(value - self._stable_targets[name]) > deadzone:
            self._stable_targets[name] = value
        return self._stable_targets[name]

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
            return float(np.clip((ear - EYE_CLOSED_RATIO) / (EYE_OPEN_RATIO - EYE_CLOSED_RATIO), 0.0, 1.0))

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

        target_pupil_x = float(np.clip(((gx_l + gx_r) / 2.0) * PUPIL_X_GAIN, -PUPIL_X_LIMIT, PUPIL_X_LIMIT))
        target_pupil_y = float(np.clip(((gy_l + gy_r) / 2.0) * PUPIL_Y_GAIN, -PUPIL_Y_LIMIT, PUPIL_Y_LIMIT))

        # 4. Paramètres continus de la bouche
        w_mouth_raw = abs(np.dot(pts[MOUTH_C2] - pts[MOUTH_C1], u_h)) / dist_eyes
        h_inner_raw = abs(np.dot(pts[MOUTH_IN_BOTTOM] - pts[MOUTH_IN_TOP], u_v)) / dist_eyes
        # Filtrer avant le saut de 0 à 0.5 LED du seuil d'ouverture : sinon,
        # une minuscule variation autour de 0.028 ferait clignoter la bouche.
        h_inner_raw = self._stabilize("mouth_ratio", float(h_inner_raw), DEADZONE_MOUTH_OPEN / MOUTH_OPEN_GAIN)

        # Sourire : hauteur relative commissures vs centre
        mid_corners = (pts[MOUTH_C1] + pts[MOUTH_C2]) / 2.0
        mid_lips = (pts[MOUTH_OUT_TOP] + pts[MOUTH_OUT_BOTTOM]) / 2.0
        smile_val = np.dot(mid_lips - mid_corners, u_v) / dist_eyes

        # Mapping continu sur les dimensions de la matrice
        target_mouth_w = float(np.clip(w_mouth_raw * MOUTH_WIDTH_GAIN, MOUTH_WIDTH_MIN, MOUTH_WIDTH_MAX))
        # Commence à s'ouvrir dès 0.028, après stabilisation de la mesure.
        if h_inner_raw < MOUTH_OPEN_RATIO:
            target_mouth_h = 0.0
        else:
            target_mouth_h = float(np.clip((h_inner_raw - MOUTH_OPEN_RATIO) * MOUTH_OPEN_GAIN, MOUTH_OPEN_MIN, MOUTH_OPEN_MAX))

        target_smile = float(np.clip(smile_val * SMILE_GAIN, SMILE_MIN, SMILE_MAX))

        # 5. Zones mortes indépendantes, puis lissage des mouvements acceptés.
        target_pupil_x = self._stabilize("pupil_x", target_pupil_x, DEADZONE_PUPIL)
        target_pupil_y = self._stabilize("pupil_y", target_pupil_y, DEADZONE_PUPIL)
        raw_open_l = self._stabilize("eye_l_open", raw_open_l, DEADZONE_EYE_OPEN)
        raw_open_r = self._stabilize("eye_r_open", raw_open_r, DEADZONE_EYE_OPEN)
        target_mouth_w = self._stabilize("mouth_w", target_mouth_w, DEADZONE_MOUTH_WIDTH)
        target_smile = self._stabilize("smile", target_smile, DEADZONE_SMILE)


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


def compute_quadratic_bezier(p0, p_mid, p2, num_samples=BEZIER_CLOSED_SAMPLES):
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


    if anim is None:
        grid[11, 6:12] = COLOR_IDLE_EYES
        grid[11, 20:26] = COLOR_IDLE_EYES
        grid[23, 11:21] = COLOR_IDLE_MOUTH
        return grid

    # --------------------------------------------------------------------------
    # 1. YEUX STYLISÉS ANIMÉS (CLIGNEMENT SOUPLE & PUPILLE FLUIDE)
    # --------------------------------------------------------------------------
    def draw_eye(cx, cy, open_ratio):
        # Si complètement fermé (< 0.15) : trait horizontal net de 7 LEDs
        if open_ratio < EYE_CLOSED_RENDER_THRESHOLD:
            grid[cy, cx - EYE_HALF_WIDTH : cx + EYE_HALF_WIDTH + 1] = COLOR_AMBER
            return

        # Hauteur de l'œil qui s'adapte en douceur (de 2 à 5 LEDs)
        half_h = max(1, int(round(open_ratio * EYE_HALF_HEIGHT)))
        half_w = EYE_HALF_WIDTH

        # Forme arrondie stylisée de l'orbite
        for dy in range(-half_h, half_h + 1):
            # Arrondi aux coins supérieurs/inférieurs
            cur_w = half_w if abs(dy) < half_h else (half_w - 1)
            grid[cy + dy, cx - cur_w : cx + cur_w + 1] = COLOR_AMBER

        # Pupille blanche mobile (glisse continuellement)
        if open_ratio > PUPIL_VISIBLE_THRESHOLD:
            px = int(round(cx + anim["pupil_x"]))
            # Limiter le déplacement vertical selon l'ouverture
            py_limit = max(0, half_h - 1)
            py = int(round(cy + np.clip(anim["pupil_y"], -py_limit, py_limit)))

            # Pupille 2x2 lumineuse
            grid[py - 1 : py + 1, px - 1 : px + 1] = COLOR_PUPIL

    draw_eye(cx=EYE_LEFT_X, cy=EYE_Y, open_ratio=anim["eye_l_open"])
    draw_eye(cx=EYE_RIGHT_X, cy=EYE_Y, open_ratio=anim["eye_r_open"])

    # --------------------------------------------------------------------------
    # 2. BOUCHE : TRACÉ EN COURBES DE BÉZIER QUADRATIQUES
    # --------------------------------------------------------------------------
    mouth_h = anim["mouth_h"]
    mouth_w = anim["mouth_w"]
    smile = anim["smile"]

    center_x = MOUTH_CENTER_X
    center_y = MOUTH_CENTER_Y

    half_w = max(MOUTH_HALF_WIDTH_MIN, mouth_w / 2.0)
    p0 = np.array([center_x - half_w, center_y - smile * SMILE_CORNER_GAIN], dtype=np.float32)
    p2 = np.array([center_x + half_w, center_y - smile * SMILE_CORNER_GAIN], dtype=np.float32)

    if mouth_h < MOUTH_CLOSED_RENDER_THRESHOLD:
        # --- BOUCHE FERMÉE : Une seule courbe de Bézier quadratique continue ---
        p_mid = np.array([center_x, center_y + smile * SMILE_CLOSED_CENTER_GAIN], dtype=np.float32)
        curve = compute_quadratic_bezier(p0, p_mid, p2, num_samples=BEZIER_CLOSED_SAMPLES)
        pts_curve = np.round(curve).astype(np.int32)
        cv2.polylines(grid, [pts_curve], isClosed=False, color=COLOR_AMBER, thickness=1)

    else:
        # --- BOUCHE OUVERTE : Deux courbes de Bézier (Lèvre supérieure & inférieure) ---
        p_top = np.array([center_x, center_y - mouth_h * 0.5 - smile * SMILE_OPEN_CENTER_GAIN], dtype=np.float32)
        p_bot = np.array([center_x, center_y + mouth_h * 0.5 - smile * SMILE_OPEN_CENTER_GAIN], dtype=np.float32)

        curve_top = compute_quadratic_bezier(p0, p_top, p2, num_samples=BEZIER_OPEN_SAMPLES)
        curve_bot = compute_quadratic_bezier(p2, p_bot, p0, num_samples=BEZIER_OPEN_SAMPLES)
        mouth_loop = np.vstack([curve_top, curve_bot])
        pts_loop = np.round(mouth_loop).astype(np.int32)

        if mouth_h >= MOUTH_FILL_THRESHOLD:
            cv2.fillPoly(grid, [pts_loop], color=COLOR_DIM)
        cv2.polylines(grid, [pts_loop], isClosed=True, color=COLOR_AMBER, thickness=1)

    return grid


def create_led_display(grid_32x32):
    """
    Rendu d'écran rétro-éclairé (LEDs rondes, halo ambré chaud).
    """
    h = MATRIX_H * LED_RENDER_SIZE
    w = MATRIX_W * LED_RENDER_SIZE
    canvas = np.full((h, w, 3), LED_BACKGROUND, dtype=np.uint8)

    radius = (LED_RENDER_SIZE // 2) - LED_RADIUS_PADDING

    for y in range(MATRIX_H):
        for x in range(MATRIX_W):
            b, g, r = grid_32x32[y, x]
            center = (x * LED_RENDER_SIZE + LED_RENDER_SIZE // 2,
                      y * LED_RENDER_SIZE + LED_RENDER_SIZE // 2)

            if b == 0 and g == 0 and r == 0:
                cv2.circle(canvas, center, radius, LED_OFF_COLOR, -1)
            else:
                cv2.circle(canvas, center, radius + LED_HALO_RADIUS, (int(b * LED_HALO_GAIN), int(g * LED_HALO_GAIN), int(r * LED_HALO_GAIN)), -1)
                cv2.circle(canvas, center, radius, (int(b), int(g), int(r)), -1)
                cv2.circle(canvas, center, max(1, radius // 3),
                           (min(255, int(b * LED_HIGHLIGHT_GAIN)), min(255, int(g * LED_HIGHLIGHT_GAIN)), min(255, int(r * LED_HIGHLIGHT_GAIN))), -1)

    return canvas


# ==============================================================================
# PROGRAMME PRINCIPAL
# ==============================================================================
def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("Initialisation de l'animation faciale stylisee...")
    detector = create_face_detector()
    # DirectShow sous Windows, backend natif sous Linux (Raspberry Pi).
    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    cap = cv2.VideoCapture(CAMERA_INDEX, backend)

    if not cap.isOpened():
        print("ERREUR : Impossible d'acceder a la camera.")
        cap.release()
        detector.close()
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

    animator = RobotFaceAnimator()

    window_title = WINDOW_TITLE
    cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_title, WINDOW_WIDTH, WINDOW_HEIGHT)

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

        if CAMERA_MIRROR:
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

                if anim_state["mouth_h"] < MOUTH_CLOSED_RENDER_THRESHOLD:
                    mid_cam = (top_cam + bot_cam) / 2.0
                    bez_cam = compute_quadratic_bezier(c1_cam, mid_cam, c2_cam, num_samples=BEZIER_CLOSED_SAMPLES)
                    cv2.polylines(frame, [np.round(bez_cam).astype(np.int32)], False, (0, 255, 255), 2)
                else:
                    bez_top_cam = compute_quadratic_bezier(c1_cam, top_cam, c2_cam, num_samples=BEZIER_OPEN_SAMPLES)
                    bez_bot_cam = compute_quadratic_bezier(c2_cam, bot_cam, c1_cam, num_samples=BEZIER_OPEN_SAMPLES)
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

        # Vue combinée
        frame_resized = cv2.resize(frame, (int(w * (led_display.shape[0] / h)), led_display.shape[0]))
        combined = np.hstack((frame_resized, led_display))

        cv2.imshow(window_title, combined)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    detector.close()
    print("Fermeture propre.")


if __name__ == "__main__":
    main()
