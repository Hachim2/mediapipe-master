"""Acquisition isolee ; seul le paquet le plus recent est conserve."""

import math
from queue import Empty, Full
import time


def publish(queue, packet):
    try:
        queue.put_nowait(packet)
    except Full:
        try:
            queue.get_nowait()
        except Empty:
            pass
        try:
            queue.put_nowait(packet)
        except Full:
            pass


def demo_frame():
    """Illustration de demonstration, jamais une capture d'un visiteur."""
    import cv2
    import numpy as np
    frame = np.full((600, 800, 3), (67, 44, 26), np.uint8)
    cv2.circle(frame, (400, 300), 235, (100, 77, 45), -1)
    cv2.ellipse(frame, (400, 605), (200, 180), 0, 0, 360, (175, 210, 100), -1)
    cv2.ellipse(frame, (400, 285), (125, 168), 0, 0, 360, (150, 194, 232), -1)
    cv2.ellipse(frame, (400, 170), (130, 78), 0, 180, 360, (45, 35, 30), -1)
    for x in (350, 450):
        cv2.circle(frame, (x, 270), 13, (42, 35, 30), -1)
        cv2.circle(frame, (x - 3, 266), 4, (255, 255, 255), -1)
    cv2.ellipse(frame, (400, 330), (45, 32), 0, 0, 180, (75, 65, 155), 9)
    points = [(0.5 + 0.16 * math.cos(i * math.tau / 64),
               0.48 + 0.29 * math.sin(i * math.tau / 64)) for i in range(64)]
    return frame, [points]


def camera_worker(queue, stop, demo=False):
    """Aucune API graphique. Fermeture normale ou terminaison bornee par le parent."""
    cap = detector = None
    try:
        if demo:
            frame, faces = demo_frame()
            while not stop.is_set():
                publish(queue, {"frame": frame, "faces": faces, "time": time.monotonic()})
                stop.wait(0.08)
            return

        import sys
        import cv2
        from config import CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT, KIOSK_MIRROR
        from face_landmarks_camera import create_face_detector
        import mediapipe as mp
        detector = create_face_detector(num_faces=3)
        while not stop.is_set():
            if cap is None:
                cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            if not cap.isOpened():
                publish(queue, {"error": "camera"})
                cap.release()
                cap = None
                stop.wait(1)
                continue
            ok, frame = cap.read()
            captured = time.monotonic()
            if not ok or frame is None:
                publish(queue, {"error": "camera"})
                cap.release()
                cap = None
                stop.wait(0.5)
                continue
            if KIOSK_MIRROR:
                frame = cv2.flip(frame, 1)
            result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                                              data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
            faces = [[(p.x, p.y) for p in face] for face in result.face_landmarks]
            publish(queue, {"frame": frame, "faces": faces, "time": captured})
    except Exception:
        import traceback
        publish(queue, {"error": "initialization", "detail": traceback.format_exc()})
    finally:
        if cap is not None:
            cap.release()
        if detector is not None:
            detector.close()
