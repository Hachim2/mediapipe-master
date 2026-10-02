"""Deadzone regressions without a camera, detector, or network."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import face_landmarks_camera as face


def landmarks_for_pose(
    pupil_x=0.0,
    pupil_y=0.0,
    eye_open=0.85,
    mouth_ratio=0.027,
    mouth_width=11.0,
    smile=0.4,
):
    """Construct independent pixel geometry for a face in a 640x480 frame."""
    points = [SimpleNamespace(x=0.0, y=0.0) for _ in range(478)]

    def put(index, x, y):
        points[index] = SimpleNamespace(x=x / 640.0, y=y / 480.0)

    eye_width = 60.0
    eye_height = eye_width * (0.14 + eye_open * 0.14)
    for cx, indexes in (
        (200.0, (33, 133, 159, 145, 468)),
        (400.0, (362, 263, 386, 374, 473)),
    ):
        left, right, top, bottom, iris = indexes
        put(left, cx - eye_width / 2.0, 200.0)
        put(right, cx + eye_width / 2.0, 200.0)
        put(top, cx, 200.0 - eye_height / 2.0)
        put(bottom, cx, 200.0 + eye_height / 2.0)
        put(iris, cx + pupil_x / 2.3 * eye_width / 2.0,
            200.0 + pupil_y / 1.5 * eye_height / 2.0)

    eye_distance = 200.0
    mouth_pixel_width = mouth_width / 16.0 * eye_distance
    lip_center_y = 310.0 + smile / 40.0 * eye_distance
    mouth_pixel_height = mouth_ratio * eye_distance
    put(61, 300.0 - mouth_pixel_width / 2.0, 310.0)
    put(291, 300.0 + mouth_pixel_width / 2.0, 310.0)
    put(13, 300.0, lip_center_y - mouth_pixel_height / 2.0)
    put(14, 300.0, lip_center_y + mouth_pixel_height / 2.0)
    put(0, 300.0, lip_center_y - 10.0)
    put(17, 300.0, lip_center_y + 10.0)
    return points


def settle(animator, points, frames=50):
    for _ in range(frames):
        state = animator.update(points, 640, 480)
    return state


class DeadzoneFilterTests(unittest.TestCase):
    def test_first_observation_is_accepted(self):
        animator = face.RobotFaceAnimator()
        self.assertEqual(animator._stabilize("pupil_x", 1.7, 0.3), 1.7)

    def test_noise_on_both_sides_of_nonzero_anchor_is_held(self):
        animator = face.RobotFaceAnimator()
        animator._stabilize("pupil_x", 1.2, 0.3)
        for sample in [1.01, 1.39] * 100:
            self.assertEqual(animator._stabilize("pupil_x", sample, 0.3), 1.2)

    def test_slow_motion_accumulates_against_last_accepted_position(self):
        animator = face.RobotFaceAnimator()
        animator._stabilize("pupil_x", 0.0, 0.3)
        for sample in (0.1, 0.2, 0.29):
            self.assertEqual(animator._stabilize("pupil_x", sample, 0.3), 0.0)
        self.assertEqual(animator._stabilize("pupil_x", 0.31, 0.3), 0.31)
        for sample in (0.21, 0.11, 0.02):
            self.assertEqual(animator._stabilize("pupil_x", sample, 0.3), 0.31)
        self.assertEqual(animator._stabilize("pupil_x", -0.01, 0.3), -0.01)

    def test_threshold_is_inclusive_and_crossing_is_symmetric(self):
        for direction in (-1.0, 1.0):
            with self.subTest(direction=direction):
                animator = face.RobotFaceAnimator()
                animator._stabilize("pupil_x", 1.0, 0.25)
                self.assertEqual(
                    animator._stabilize("pupil_x", 1.0 + direction * 0.25, 0.25),
                    1.0,
                )
                sample = 1.0 + direction * 0.26
                self.assertEqual(animator._stabilize("pupil_x", sample, 0.25), sample)

    def test_zero_disables_deadzone(self):
        animator = face.RobotFaceAnimator()
        for sample in (0.0, 0.0001, -0.0001, 1.0, 1.0):
            self.assertEqual(animator._stabilize("pupil_x", sample, 0.0), sample)

    def test_channels_have_independent_anchors(self):
        animator = face.RobotFaceAnimator()
        animator._stabilize("pupil_x", 1.0, 0.3)
        animator._stabilize("pupil_y", -1.0, 0.3)
        self.assertEqual(animator._stabilize("pupil_x", 1.5, 0.3), 1.5)
        self.assertEqual(animator._stabilize("pupil_y", -0.9, 0.3), -1.0)


class FaceOutputTests(unittest.TestCase):
    def test_landmark_noise_keeps_preview_stable(self):
        # Exercise two positions near pixel rounding boundaries.
        for pupil_x in (0.49, 0.249):
            with self.subTest(pupil_x=pupil_x):
                animator = face.RobotFaceAnimator()
                mouth_ratio = 0.028 + 1.249 / 32.0
                baseline = settle(animator, landmarks_for_pose(
                    pupil_x=pupil_x, pupil_y=0.24, mouth_ratio=mouth_ratio,
                ))
                baseline_grid = face.render_living_robot_face(baseline)

                for direction in (-1.0, 1.0) * 25:
                    state = animator.update(landmarks_for_pose(
                        pupil_x=pupil_x + direction * 0.10,
                        pupil_y=0.24 + direction * 0.08,
                        eye_open=0.85 + direction * 0.025,
                        mouth_ratio=mouth_ratio + direction * 0.10 / 32.0,
                        mouth_width=11.0 + direction * 0.15,
                        smile=0.4 + direction * 0.05,
                    ), 640, 480)
                    np.testing.assert_array_equal(
                        face.render_living_robot_face(state), baseline_grid,
                    )

    def test_mouth_cutoff_noise_does_not_toggle_output(self):
        for initial_ratio in (0.027, 0.029):
            with self.subTest(initial_ratio=initial_ratio):
                animator = face.RobotFaceAnimator()
                baseline = settle(animator, landmarks_for_pose(mouth_ratio=initial_ratio))
                baseline_grid = face.render_living_robot_face(baseline)
                for mouth_ratio in (0.027, 0.029) * 25:
                    state = animator.update(landmarks_for_pose(mouth_ratio=mouth_ratio), 640, 480)
                    self.assertAlmostEqual(state["mouth_h"], baseline["mouth_h"])
                    np.testing.assert_array_equal(
                        face.render_living_robot_face(state), baseline_grid,
                    )

    def test_deliberate_mouth_opening_and_closure_still_reach_output(self):
        animator = face.RobotFaceAnimator()
        baseline = settle(animator, landmarks_for_pose(mouth_ratio=0.027))
        opened = settle(animator, landmarks_for_pose(mouth_ratio=0.10))
        closed = settle(animator, landmarks_for_pose(mouth_ratio=0.005))
        self.assertGreater(opened["mouth_h"], 2.0)
        self.assertAlmostEqual(closed["mouth_h"], 0.0)
        self.assertFalse(np.array_equal(
            face.render_living_robot_face(opened), face.render_living_robot_face(baseline),
        ))

    def test_slow_gaze_motion_crosses_deadzone_and_changes_leds(self):
        animator = face.RobotFaceAnimator()
        baseline = settle(animator, landmarks_for_pose())
        for pupil_x in (0.1, 0.2, 0.29):
            state = settle(animator, landmarks_for_pose(pupil_x=pupil_x))
            self.assertAlmostEqual(state["pupil_x"], baseline["pupil_x"])
        crossed = animator.update(landmarks_for_pose(pupil_x=0.4), 640, 480)
        self.assertGreater(crossed["pupil_x"], baseline["pupil_x"] + 0.1)
        moved = settle(animator, landmarks_for_pose(pupil_x=1.2))
        self.assertGreater(moved["pupil_x"], 1.0)
        self.assertFalse(np.array_equal(
            face.render_living_robot_face(moved), face.render_living_robot_face(baseline),
        ))


if __name__ == "__main__":
    unittest.main()
