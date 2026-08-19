import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np


SCRIPT_PATH = (
    Path(__file__).parents[1] / "scripts" / "camera_sender_two_cameras.py"
)


class FakeCV2(types.ModuleType):
    FONT_HERSHEY_SIMPLEX = 0
    LINE_AA = 16
    BORDER_CONSTANT = 0
    CAP_V4L2 = 200
    error = RuntimeError

    def __init__(self):
        super().__init__("cv2")
        self.rendered_text = []
        self.written_images = []
        self.failed_image_suffix = None
        self.wait_key_results = []

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

    def resize(self, frame, size):
        return np.resize(frame, (size[1], size[0], frame.shape[2]))

    def hconcat(self, frames):
        return np.concatenate(frames, axis=1)

    def imshow(self, title, frame):
        return None

    def waitKey(self, delay):
        if self.wait_key_results:
            return self.wait_key_results.pop(0)
        return ord("q")

    def destroyAllWindows(self):
        return None

    def imwrite(self, path, frame):
        self.written_images.append((path, frame))
        if self.failed_image_suffix and path.endswith(self.failed_image_suffix):
            return False
        Path(path).write_bytes(b"png")
        return True


def make_fake_av(fail_to_add_stream=False):
    fake_av = types.ModuleType("av")
    fake_av.container = MagicMock()
    fake_av.stream = MagicMock()
    fake_av.stream.codec_context = types.SimpleNamespace()
    fake_av.stream.encode.side_effect = lambda frame=None: [
        "flush-packet" if frame is None else "frame-packet"
    ]
    if fail_to_add_stream:
        fake_av.container.add_stream.side_effect = LookupError("libx264")
    else:
        fake_av.container.add_stream.return_value = fake_av.stream
    fake_av.open = MagicMock(return_value=fake_av.container)
    fake_av.VideoFrame = types.SimpleNamespace()
    fake_av.VideoFrame.from_ndarray = MagicMock(
        side_effect=lambda array, format: types.SimpleNamespace(
            array=array,
            pixel_format=format,
            pts=None,
            time_base=None,
        )
    )
    return fake_av


def load_camera_script(fake_cv2, fake_av=None):
    if fake_av is None:
        fake_av = make_fake_av()
    fake_picamera2 = types.ModuleType("picamera2")
    fake_picamera2.Picamera2 = object
    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = MagicMock()
    spec = importlib.util.spec_from_file_location("camera_sender_two_cameras", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)

    with patch.dict(
        sys.modules,
        {
            "av": fake_av,
            "cv2": fake_cv2,
            "dotenv": fake_dotenv,
            "picamera2": fake_picamera2,
        },
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


class UDPVideoSenderTests(unittest.TestCase):
    def setUp(self):
        self.fake_av = make_fake_av()
        self.camera_script = load_camera_script(FakeCV2(), self.fake_av)

    def test_configures_low_latency_h264_mpegts_stream(self):
        sender = self.camera_script.UDPVideoSender(
            "192.0.2.1",
            5000,
            (1280, 560),
        )
        stream = self.fake_av.stream

        self.fake_av.open.assert_called_once_with(
            "udp://192.0.2.1:5000?pkt_size=1316",
            mode="w",
            format="mpegts",
        )
        self.fake_av.container.add_stream.assert_called_once_with("libx264", rate=30)
        self.assertEqual((stream.width, stream.height), (1280, 560))
        self.assertEqual(stream.pix_fmt, "yuv420p")
        self.assertEqual(stream.bit_rate, 2_000_000)
        self.assertEqual(stream.gop_size, 30)
        self.assertEqual(stream.codec_context.max_b_frames, 0)
        self.assertEqual(
            stream.codec_context.options,
            {
                "preset": "ultrafast",
                "tune": "zerolatency",
                "x264-params": "repeat-headers=1",
            },
        )
        sender.close()

    def test_converts_bgr_frame_and_muxes_encoded_packet(self):
        sender = self.camera_script.UDPVideoSender(
            "192.0.2.1",
            5000,
            (1280, 560),
        )
        frame = np.zeros((560, 1280, 3), dtype=np.uint8)

        sender.send(frame)

        converted = self.fake_av.stream.encode.call_args.args[0]
        self.fake_av.VideoFrame.from_ndarray.assert_called_once_with(
            frame,
            format="bgr24",
        )
        self.assertIs(converted.array, frame)
        self.assertEqual(converted.pixel_format, "bgr24")
        self.assertEqual(converted.pts, 0)
        self.assertEqual(converted.time_base.numerator, 1)
        self.assertEqual(converted.time_base.denominator, 30)
        self.fake_av.container.mux.assert_called_once_with("frame-packet")

    def test_rejects_frame_with_unexpected_dimensions(self):
        sender = self.camera_script.UDPVideoSender(
            "192.0.2.1",
            5000,
            (1280, 560),
        )

        with self.assertRaisesRegex(ValueError, "expected BGR frame shape"):
            sender.send(np.zeros((480, 640, 3), dtype=np.uint8))

        sender.close()

    def test_close_flushes_once_and_prevents_further_sends(self):
        sender = self.camera_script.UDPVideoSender(
            "192.0.2.1",
            5000,
            (1280, 560),
        )

        sender.close()
        sender.close()

        self.fake_av.container.mux.assert_called_once_with("flush-packet")
        self.fake_av.container.close.assert_called_once_with()
        with self.assertRaisesRegex(RuntimeError, "sender is closed"):
            sender.send(np.zeros((560, 1280, 3), dtype=np.uint8))

    def test_reports_unavailable_h264_encoder_and_closes_container(self):
        fake_av = make_fake_av(fail_to_add_stream=True)
        camera_script = load_camera_script(FakeCV2(), fake_av)

        with self.assertRaisesRegex(RuntimeError, "cannot start H.264 UDP sender"):
            camera_script.UDPVideoSender("192.0.2.1", 5000, (1280, 560))

        fake_av.container.close.assert_called_once_with()


class CaptureStorageTests(unittest.TestCase):
    def setUp(self):
        self.fake_cv2 = FakeCV2()
        self.camera_script = load_camera_script(self.fake_cv2)

    def test_creates_next_batch_directory_without_overwriting_existing_batches(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_directory = Path(temporary_directory) / "data"
            (data_directory / "batch_002").mkdir(parents=True)
            (data_directory / "batch_010").mkdir()
            (data_directory / "notes").mkdir()

            result = self.camera_script.create_batch_directory(data_directory)

            self.assertEqual(result, data_directory / "batch_011")
            self.assertTrue(result.is_dir())

    def test_creates_data_and_first_batch_when_they_do_not_exist(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_directory = Path(temporary_directory) / "missing" / "data"

            result = self.camera_script.create_batch_directory(data_directory)

            self.assertEqual(result, data_directory / "batch_000")
            self.assertTrue(result.is_dir())

    def test_counts_only_exact_capture_messages(self):
        capture_socket = MagicMock()
        capture_socket.recvfrom.side_effect = [
            (b"CAPTURE", ("192.0.2.1", 1234)),
            (b"capture", ("192.0.2.1", 1234)),
            (b"CAPTURE\n", ("192.0.2.1", 1234)),
            (b"CAPTURE", ("192.0.2.1", 1234)),
            BlockingIOError,
        ]

        result = self.camera_script.receive_capture_requests(capture_socket)

        self.assertEqual(result, 2)

    def test_saves_numbered_pair_from_the_supplied_raw_frames(self):
        pi_frame = np.full((480, 640, 3), 10, dtype=np.uint8)
        thermal_frame = np.full((120, 160, 3), 20, dtype=np.uint8)

        with tempfile.TemporaryDirectory() as temporary_directory:
            batch_directory = Path(temporary_directory)

            result = self.camera_script.save_capture_pair(
                batch_directory,
                7,
                pi_frame,
                thermal_frame,
            )

            self.assertTrue(result)
            self.assertTrue((batch_directory / "0007_rgb.png").is_file())
            self.assertTrue((batch_directory / "0007_trm.png").is_file())
            self.assertIs(self.fake_cv2.written_images[0][1], pi_frame)
            self.assertIs(self.fake_cv2.written_images[1][1], thermal_frame)

    def test_removes_partial_output_when_either_image_cannot_be_written(self):
        self.fake_cv2.failed_image_suffix = "_trm.tmp.png"

        with tempfile.TemporaryDirectory() as temporary_directory:
            batch_directory = Path(temporary_directory)

            result = self.camera_script.save_capture_pair(
                batch_directory,
                0,
                np.zeros((2, 2, 3), dtype=np.uint8),
                np.zeros((1, 1, 3), dtype=np.uint8),
            )

            self.assertFalse(result)
            self.assertEqual(list(batch_directory.iterdir()), [])


class MainTests(unittest.TestCase):
    def test_sends_composite_and_saves_pending_raw_pairs(self):
        fake_cv2 = FakeCV2()
        fake_cv2.wait_key_results = [0, ord("q")]
        camera_script = load_camera_script(fake_cv2)
        pi_frame = np.full((480, 640, 3), 10, dtype=np.uint8)
        thermal_frame = np.full((120, 160, 3), 20, dtype=np.uint8)
        pi_frames = MagicMock()
        thermal_frames = MagicMock()
        pi_frames.get.return_value = (10.0, pi_frame, 29.8)
        thermal_frames.get.return_value = (10.01, thermal_frame, 29.7)
        sender = MagicMock()
        capture_socket = MagicMock()
        save_capture_pair = MagicMock(return_value=True)
        threads = [MagicMock(), MagicMock()]

        with (
            patch.dict(
                os.environ,
                {"MAC_IP": "192.0.2.1", "PORT": "5000"},
                clear=True,
            ),
            patch.object(camera_script, "load_dotenv") as load_dotenv,
            patch.object(
                camera_script,
                "UDPVideoSender",
                return_value=sender,
            ) as sender_type,
            patch.object(
                camera_script,
                "create_batch_directory",
                return_value=Path("data/batch_000"),
            ),
            patch.object(
                camera_script,
                "create_capture_socket",
                return_value=capture_socket,
            ),
            patch.object(
                camera_script,
                "receive_capture_requests",
                side_effect=[2, 0],
            ),
            patch.object(
                camera_script,
                "save_capture_pair",
                save_capture_pair,
            ),
            patch.object(
                camera_script,
                "Queue",
                side_effect=[pi_frames, thermal_frames],
            ),
            patch.object(
                camera_script.threading,
                "Thread",
                side_effect=threads,
            ),
        ):
            camera_script.main()

        load_dotenv.assert_called_once_with()
        sender_type.assert_called_once_with("192.0.2.1", 5000, (1280, 560))
        self.assertEqual(sender.send.call_count, 2)
        streamed_frame = sender.send.call_args_list[0].args[0]
        self.assertEqual(streamed_frame.shape, (560, 1280, 3))
        np.testing.assert_array_equal(streamed_frame[:480, :640], pi_frame)
        self.assertFalse(streamed_frame[480:].any())
        self.assertEqual(save_capture_pair.call_count, 2)
        for image_number, call in enumerate(save_capture_pair.call_args_list):
            self.assertEqual(call.args[1], image_number)
            self.assertIs(call.args[2], pi_frame)
            self.assertIs(call.args[3], thermal_frame)
        sender.close.assert_called_once_with()
        capture_socket.close.assert_called_once_with()
        for thread in threads:
            thread.start.assert_called_once_with()
            thread.join.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
