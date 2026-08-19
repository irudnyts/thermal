import threading
import time
from collections import deque
from queue import Empty, Full, Queue

import cv2
from picamera2 import Picamera2


FRAME_SIZE = (640, 480)
FRAME_RATE = 30
THERMAL_CAMERA_INDEX = 16
MAX_TIME_DIFFERENCE = 0.050
QUEUE_SIZE = 2
FPS_WINDOW_SECONDS = 1.0
FOOTER_HEIGHT = 80
TEXT_FONT = cv2.FONT_HERSHEY_SIMPLEX
TEXT_SCALE = 0.6
TEXT_THICKNESS = 1
TEXT_COLOR = (255, 255, 255)


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

    try:
        while not stop_event.is_set():
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
                thermal_frame = cv2.resize(thermal_item[1], FRAME_SIZE)
                combined_frame = cv2.hconcat([pi_item[1], thermal_frame])
                display_frame = add_telemetry_footer(
                    combined_frame,
                    pi_item[2],
                    thermal_item[2],
                    pair_fps,
                    time_difference,
                )
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
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
