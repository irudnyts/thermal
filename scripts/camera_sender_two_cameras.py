import os
import re
import socket
import threading
import time
from collections import deque
from fractions import Fraction
from pathlib import Path
from queue import Empty, Full, Queue

import av
import cv2
from picamera2 import Picamera2
from dotenv import load_dotenv


FRAME_SIZE = (640, 480)
FRAME_RATE = 30
THERMAL_CAMERA_INDEX = 16
MAX_TIME_DIFFERENCE = 0.050
QUEUE_SIZE = 2
FPS_WINDOW_SECONDS = 1.0
FOOTER_HEIGHT = 80
STREAM_FRAME_SIZE = (FRAME_SIZE[0] * 2, FRAME_SIZE[1] + FOOTER_HEIGHT)
TEXT_FONT = cv2.FONT_HERSHEY_SIMPLEX
TEXT_SCALE = 0.6
TEXT_THICKNESS = 1
TEXT_COLOR = (255, 255, 255)
STREAM_BIT_RATE = 2_000_000
STREAM_PACKET_SIZE = 1316
CAPTURE_COMMAND = b"CAPTURE"
CAPTURE_PORT = 5001
DATA_DIRECTORY = Path("data")
BATCH_DIRECTORY_PATTERN = re.compile(r"batch_(\d+)")


class UDPVideoSender:
    def __init__(self, host, port, frame_size, frame_rate=FRAME_RATE):
        self.frame_size = frame_size
        self.frame_rate = frame_rate
        self.container = None
        self.stream = None
        self.next_pts = 0

        url = f"udp://{host}:{port}?pkt_size={STREAM_PACKET_SIZE}"
        try:
            self.container = av.open(url, mode="w", format="mpegts")
            self.stream = self.container.add_stream("libx264", rate=frame_rate)
            self.stream.width = frame_size[0]
            self.stream.height = frame_size[1]
            self.stream.pix_fmt = "yuv420p"
            self.stream.bit_rate = STREAM_BIT_RATE
            self.stream.gop_size = frame_rate
            self.stream.codec_context.max_b_frames = 0
            self.stream.codec_context.options = {
                "preset": "ultrafast",
                "tune": "zerolatency",
                "x264-params": "repeat-headers=1",
            }
        except Exception as error:
            if self.container is not None:
                self.container.close()
                self.container = None
            raise RuntimeError(f"cannot start H.264 UDP sender: {error}") from error

    def send(self, frame):
        if self.container is None:
            raise RuntimeError("UDP video sender is closed")

        expected_shape = (self.frame_size[1], self.frame_size[0], 3)
        if frame.shape != expected_shape:
            raise ValueError(
                f"expected BGR frame shape {expected_shape}, got {frame.shape}"
            )

        video_frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = self.next_pts
        video_frame.time_base = Fraction(1, self.frame_rate)
        self.next_pts += 1

        for packet in self.stream.encode(video_frame):
            self.container.mux(packet)

    def close(self):
        if self.container is None:
            return

        container = self.container
        stream = self.stream
        self.container = None
        self.stream = None

        try:
            for packet in stream.encode():
                container.mux(packet)
        finally:
            container.close()


class RollingFPS:
    def __init__(self, window_seconds=FPS_WINDOW_SECONDS):
        self.window_seconds = window_seconds
        self.timestamps = deque()

    def add(self, timestamp):
        self.timestamps.append(timestamp)

        while timestamp - self.timestamps[0] > self.window_seconds:
            self.timestamps.popleft()

        if len(self.timestamps) < 2:
            return None

        elapsed = self.timestamps[-1] - self.timestamps[0]
        if elapsed <= 0:
            return None

        return (len(self.timestamps) - 1) / elapsed


def format_fps(fps):
    if fps is None:
        return "--"
    return f"{fps:.1f}"


def put_centered_text(frame, text, center_x, baseline_y):
    text_size, _ = cv2.getTextSize(
        text,
        TEXT_FONT,
        TEXT_SCALE,
        TEXT_THICKNESS,
    )
    origin = (center_x - text_size[0] // 2, baseline_y)
    cv2.putText(
        frame,
        text,
        origin,
        TEXT_FONT,
        TEXT_SCALE,
        TEXT_COLOR,
        TEXT_THICKNESS,
        cv2.LINE_AA,
    )


def add_telemetry_footer(
    combined_frame,
    pi_fps,
    thermal_fps,
    synchronized_fps,
    time_difference,
):
    frame_with_footer = cv2.copyMakeBorder(
        combined_frame,
        0,
        FOOTER_HEIGHT,
        0,
        0,
        cv2.BORDER_CONSTANT,
        value=(0, 0, 0),
    )
    frame_width = combined_frame.shape[1]
    stream_bottom = combined_frame.shape[0]

    put_centered_text(
        frame_with_footer,
        f"Pi Camera: {format_fps(pi_fps)} FPS",
        frame_width // 4,
        stream_bottom + 28,
    )
    put_centered_text(
        frame_with_footer,
        f"Thermal Camera: {format_fps(thermal_fps)} FPS",
        3 * frame_width // 4,
        stream_bottom + 28,
    )
    put_centered_text(
        frame_with_footer,
        (
            f"Synchronized: {format_fps(synchronized_fps)} FPS | "
            f"Pi-Thermal: {time_difference * 1000:+.1f} ms"
        ),
        frame_width // 2,
        stream_bottom + 62,
    )

    return frame_with_footer


def put_latest(frames, item):
    try:
        frames.put_nowait(item)
    except Full:
        try:
            frames.get_nowait()
        except Empty:
            pass
        try:
            frames.put_nowait(item)
        except Full:
            pass


def create_batch_directory(data_directory=DATA_DIRECTORY):
    data_directory.mkdir(parents=True, exist_ok=True)
    batch_numbers = [
        int(match.group(1))
        for path in data_directory.iterdir()
        if path.is_dir()
        if (match := BATCH_DIRECTORY_PATTERN.fullmatch(path.name)) is not None
    ]
    batch_number = max(batch_numbers, default=-1) + 1
    batch_directory = data_directory / f"batch_{batch_number:03d}"
    batch_directory.mkdir()
    return batch_directory


def create_capture_socket(port=CAPTURE_PORT):
    capture_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    capture_socket.bind(("0.0.0.0", port))
    capture_socket.setblocking(False)
    return capture_socket


def receive_capture_requests(capture_socket):
    request_count = 0

    while True:
        try:
            message, _ = capture_socket.recvfrom(1024)
        except BlockingIOError:
            return request_count

        if message == CAPTURE_COMMAND:
            request_count += 1


def save_capture_pair(batch_directory, image_number, pi_frame, thermal_frame):
    prefix = f"{image_number:04d}"
    rgb_path = batch_directory / f"{prefix}_rgb.png"
    thermal_path = batch_directory / f"{prefix}_trm.png"
    rgb_temporary_path = batch_directory / f".{prefix}_rgb.tmp.png"
    thermal_temporary_path = batch_directory / f".{prefix}_trm.tmp.png"

    try:
        rgb_written = cv2.imwrite(str(rgb_temporary_path), pi_frame)
        thermal_written = cv2.imwrite(str(thermal_temporary_path), thermal_frame)
        if not rgb_written or not thermal_written:
            raise OSError("OpenCV could not encode both PNG files")

        os.replace(rgb_temporary_path, rgb_path)
        os.replace(thermal_temporary_path, thermal_path)
    except (OSError, cv2.error) as error:
        for path in (
            rgb_temporary_path,
            thermal_temporary_path,
            rgb_path,
            thermal_path,
        ):
            path.unlink(missing_ok=True)
        print(f"Cannot save capture {prefix}: {error}")
        return False

    print(f"Saved capture {prefix} in {batch_directory}")
    return True


def capture_pi_camera(frames, stop_event):
    picam2 = None
    fps = RollingFPS()

    try:
        picam2 = Picamera2()
        config = picam2.create_video_configuration(
            main={"size": FRAME_SIZE, "format": "RGB888"},
            controls={"FrameRate": FRAME_RATE},
        )
        picam2.configure(config)
        picam2.start()

        while not stop_event.is_set():
            frame = picam2.capture_array("main")
            timestamp = time.monotonic()
            put_latest(frames, (timestamp, frame, fps.add(timestamp)))
    except Exception as error:
        print(f"Raspberry Pi camera error: {error}")
        stop_event.set()
    finally:
        if picam2 is not None:
            picam2.stop()


def capture_thermal_camera(frames, stop_event):
    camera = None
    fps = RollingFPS()

    try:
        camera = cv2.VideoCapture(THERMAL_CAMERA_INDEX, cv2.CAP_V4L2)
        if not camera.isOpened():
            raise RuntimeError("cannot open thermal camera")

        while not stop_event.is_set():
            received, frame = camera.read()
            if not received:
                raise RuntimeError("cannot read thermal camera frame")
            timestamp = time.monotonic()
            put_latest(frames, (timestamp, frame, fps.add(timestamp)))
    except Exception as error:
        print(f"Thermal camera error: {error}")
        stop_event.set()
    finally:
        if camera is not None:
            camera.release()


def main():
    load_dotenv()
    host = os.environ["MAC_IP"]
    port = int(os.environ["PORT"])
    sender = UDPVideoSender(host, port, STREAM_FRAME_SIZE)
    batch_directory = create_batch_directory()

    try:
        capture_socket = create_capture_socket()
    except Exception:
        sender.close()
        raise

    pi_frames = Queue(maxsize=QUEUE_SIZE)
    thermal_frames = Queue(maxsize=QUEUE_SIZE)
    stop_event = threading.Event()

    threads = [
        threading.Thread(target=capture_pi_camera, args=(pi_frames, stop_event)),
        threading.Thread(
            target=capture_thermal_camera,
            args=(thermal_frames, stop_event),
        ),
    ]

    for thread in threads:
        thread.start()

    pi_item = None
    thermal_item = None
    synchronized_fps = RollingFPS()
    pending_captures = 0
    image_number = 0

    try:
        while not stop_event.is_set():
            pending_captures += receive_capture_requests(capture_socket)

            try:
                if pi_item is None:
                    pi_item = pi_frames.get(timeout=0.1)
                if thermal_item is None:
                    thermal_item = thermal_frames.get(timeout=0.1)
            except Empty:
                continue

            time_difference = pi_item[0] - thermal_item[0]

            if abs(time_difference) <= MAX_TIME_DIFFERENCE:
                pair_fps = synchronized_fps.add(time.monotonic())
                if pending_captures > 0:
                    if save_capture_pair(
                        batch_directory,
                        image_number,
                        pi_item[1],
                        thermal_item[1],
                    ):
                        image_number += 1
                    pending_captures -= 1

                thermal_frame = cv2.resize(thermal_item[1], FRAME_SIZE)
                combined_frame = cv2.hconcat([pi_item[1], thermal_frame])
                display_frame = add_telemetry_footer(
                    combined_frame,
                    pi_item[2],
                    thermal_item[2],
                    pair_fps,
                    time_difference,
                )
                sender.send(display_frame)
                cv2.imshow("Pi and Thermal Cameras", display_frame)
                pi_item = None
                thermal_item = None
            elif time_difference < 0:
                pi_item = None
            else:
                thermal_item = None

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        for thread in threads:
            thread.join()
        capture_socket.close()
        sender.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
