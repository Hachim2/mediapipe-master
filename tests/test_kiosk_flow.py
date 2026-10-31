"""Temps simule, sans camera, interface graphique ni CUPS."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kiosk_flow import Flow, Settings, Stability, State, request_robot_drawing


def face(cx=.5, cy=.5, width=.4, height=.5):
    return [(cx-width/2,cy-height/2),(cx+width/2,cy+height/2),
            (cx,cy), (cx-width*.25,cy-height*.1), (cx+width*.25,cy-height*.1)]


class StabilityTests(unittest.TestCase):
    def test_duration_not_frame_count_and_natural_expressions(self):
        for interval in (.05, .2):
            gate = Stability(Settings(stable=1))
            for i in range(round(.8/interval)+1):
                points = face()
                points[-1] = (.59, .45 + .01*(i%2))  # Yeux / clignement dans l'enveloppe.
                self.assertFalse(gate.update([points], i*interval))
            self.assertTrue(gate.update([face()], 1.01))

    def test_slow_drift_does_not_accumulate_stability(self):
        gate = Stability(Settings(stable=1))
        for i in range(30):
            self.assertFalse(gate.update([face(cx=.4+i*.004)], i*.1))

    def test_invalid_visibility_multiple_people_and_size_change(self):
        for faces in ([], [face(), face()], [face(cx=.05)], [face(width=.05)],
                      [[(float("nan"),.5)]], [face(height=.05)]):
            gate = Stability(Settings(stable=.5))
            gate.update([face()],0)
            self.assertTrue(gate.update([face()],.6))
            self.assertFalse(gate.update(faces,.7))
        gate = Stability(Settings(stable=.5))
        gate.update([face()],0)
        self.assertTrue(gate.update([face()],.6))
        self.assertFalse(gate.update([face(width=.5)],.7))

    def test_gap_and_duplicate_packets_do_not_qualify(self):
        gate = Stability(Settings(stable=1,fresh=.5))
        gate.update([face()],0)
        self.assertFalse(gate.update([face()],0))
        self.assertFalse(gate.update([face()],2))


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.flow = Flow(0, Settings(stable=.3,preview=.2,countdown=3))

    def feed(self, t, faces=None):
        self.flow.observe([face()] if faces is None else faces,t,t)
        return self.flow.tick(t)

    def to_countdown(self):
        self.feed(3.9)
        self.assertEqual(self.flow.state,State.STARTUP)
        self.feed(4)
        self.assertEqual(self.flow.state,State.HOME)
        self.feed(4.1)
        self.feed(4.5)
        self.assertEqual(self.flow.state,State.PREVIEW)
        self.feed(4.8)
        self.assertEqual(self.flow.state,State.COUNTDOWN)

    def test_loading_waits_for_fresh_camera_and_logo_duration(self):
        self.flow.tick(5)
        self.assertEqual(self.flow.state,State.STARTUP)
        self.flow.observe([face()],1,5)
        self.flow.tick(5)
        self.assertEqual(self.flow.state,State.STARTUP)
        self.feed(5.1)
        self.assertEqual(self.flow.state,State.HOME)

    def test_full_capture_once_then_print_once(self):
        self.to_countdown()
        self.feed(5.5)
        self.feed(6.5)
        self.feed(7.5)
        self.assertEqual(self.feed(7.9),"capture")
        self.assertEqual(self.flow.state,State.PROCESSING)
        self.assertIsNone(self.feed(8))
        self.flow.generated(8)
        self.assertTrue(self.flow.request_print(8.1))
        self.assertFalse(self.flow.request_print(8.11))
        self.flow.finish(200)
        self.assertEqual(self.flow.state,State.PRINTING)
        self.flow.tick(300)
        self.assertEqual(self.flow.state,State.PRINTING)
        self.flow.print_result(301,True)
        self.flow.tick(317)
        self.assertEqual(self.flow.state,State.HOME)
        self.assertFalse(self.flow.armed)

    def test_countdown_cancels_on_loss_motion_or_multiple_faces(self):
        for faces in ([],[face(cx=.6)],[face(),face()]):
            self.setUp()
            self.to_countdown()
            self.feed(5,faces)
            self.assertEqual(self.flow.state,State.STABILIZING)

    def test_stale_frame_and_disconnect_never_capture(self):
        self.to_countdown()
        self.assertIsNone(self.flow.tick(8))
        self.assertEqual(self.flow.state,State.ERROR)
        self.assertEqual(self.flow.error_kind,"camera")

    def test_capture_waits_for_a_new_image_at_end_of_countdown(self):
        self.to_countdown()
        self.feed(5.5)
        self.feed(6.5)
        self.feed(7.5)
        self.assertIsNone(self.flow.tick(7.9))
        self.assertEqual(self.flow.state,State.COUNTDOWN)
        self.assertEqual(self.feed(8),"capture")

    def test_end_requires_departure_or_explicit_new_action(self):
        self.flow.finish(4)
        for t in (4.1,4.5,5,5.5):
            self.feed(t)
            self.assertEqual(self.flow.state,State.HOME)
        self.feed(6,[])
        self.feed(7.1,[])
        self.assertTrue(self.flow.armed)
        self.feed(7.2)
        self.assertEqual(self.flow.state,State.STABILIZING)
        self.flow.finish(8)
        self.flow.restart(8.1)
        self.assertTrue(self.flow.armed)

    def test_error_preserves_choice_retry_and_idle_reset(self):
        self.flow.go(State.CHOICE,5)
        self.flow.request_print(5.1)
        self.flow.print_result(6,False,retry=True)
        self.assertEqual(self.flow.state,State.ERROR)
        self.assertTrue(self.flow.print_retry)
        self.flow.go(State.CHOICE,7)
        self.flow.tick(68)
        self.assertEqual(self.flow.state,State.HOME)
        self.assertFalse(self.flow.armed)

    def test_robot_hook_is_unavailable(self):
        self.assertIn("bientôt disponible",request_robot_drawing())

    def test_demo_print_cannot_call_hardware(self):
        # Le point d'entree importe Tk mais ne cree aucune fenetre a l'import.
        from kiosk import print_session
        with patch("kiosk.submit_print") as cups:
            self.assertEqual(print_session(Path("absent.png"),True),"demonstration")
            cups.assert_not_called()

    def test_demo_camera_never_opens_camera_or_model(self):
        from kiosk_camera import camera_worker
        from queue import Queue
        from unittest.mock import Mock
        stop = Mock()
        stop.is_set.side_effect = [False,True]
        queue = Queue()
        with patch("cv2.VideoCapture") as camera:
            camera_worker(queue,stop,demo=True)
            camera.assert_not_called()
        self.assertEqual(len(queue.get_nowait()["faces"]),1)

    def test_splash_configuration_is_bounded(self):
        for value in (2,6,float("nan")):
            with self.assertRaises(ValueError):
                Settings(splash=value)
