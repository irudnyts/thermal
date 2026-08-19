import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np


SCRIPT_PATH = (
    Path(__file__).parents[1] / "scripts" / "camera_sender_two_cameras.py"
)


class FakeCV2(types.ModuleType):
    FONT_HERSHEY_SIMPLEX = 0
    LINE_AA = 16
    BORDER_CONSTANT = 0
    CAP_V4L2 = 200

    def __init__(self):
        super().__init__("cv2")
        self.rendered_text = []

    def copyMakeBorder(self, frame, top, bottom, left, right, border_type, value):
        height, width, channels = frame.shape
        result = np.zeros(
            (height + top + bottom, width + left + right, channels),
            dtype=frame.dtype,
        )
        result[top : top + height, left : left + width] = frame
        return result

    def getTextSize(self, text, font, scale, thickness):
        return (len(text) * 10, 20), 5

    def putText(self, frame, text, origin, font, scale, color, thickness, line_type):
        self.rendered_text.append((text, origin))
        return frame


def load_camera_script(fake_cv2):
    fake_picamera2 = types.ModuleType("picamera2")
    fake_picamera2.Picamera2 = object
    spec = importlib.util.spec_from_file_location("camera_sender_two_cameras", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)

    with patch.dict(
        sys.modules,
        {"cv2": fake_cv2, "picamera2": fake_picamera2},
    ):
        spec.loader.exec_module(module)

    return module


class RollingFPSTests(unittest.TestCase):
    def setUp(self):
        self.fake_cv2 = FakeCV2()
        self.camera_script = load_camera_script(self.fake_cv2)

    def test_reports_warmup_then_rate(self):
        fps = self.camera_script.RollingFPS()

        self.assertIsNone(fps.add(10.0))
        self.assertAlmostEqual(fps.add(10.5), 2.0)
        self.assertAlmostEqual(fps.add(11.0), 2.0)

    def test_removes_samples_older_than_one_second(self):
        fps = self.camera_script.RollingFPS()

        fps.add(10.0)
        fps.add(10.5)
        fps.add(11.0)

        self.assertAlmostEqual(fps.add(11.5), 2.0)
        self.assertEqual(list(fps.timestamps), [10.5, 11.0, 11.5])

    def test_footer_adds_black_space_and_renders_metrics(self):
        frame = np.full((480, 1280, 3), 127, dtype=np.uint8)

        result = self.camera_script.add_telemetry_footer(
            frame,
            pi_fps=None,
            thermal_fps=29.85,
            synchronized_fps=27.24,
            time_difference=-0.01234,
        )

        self.assertEqual(result.shape, (560, 1280, 3))
        np.testing.assert_array_equal(result[:480], frame)
        self.assertFalse(result[480:].any())
        self.assertEqual(
            [text for text, _ in self.fake_cv2.rendered_text],
            [
                "Pi Camera: -- FPS",
                "Thermal Camera: 29.9 FPS",
                "Synchronized: 27.2 FPS | Pi-Thermal: -12.3 ms",
            ],
        )
        self.assertEqual(
            [origin[1] for _, origin in self.fake_cv2.rendered_text],
            [508, 508, 542],
        )
        self.assertEqual(
            [
                origin[0] + len(text) * 5
                for text, origin in self.fake_cv2.rendered_text
            ],
            [320, 960, 640],
        )


if __name__ == "__main__":
    unittest.main()
