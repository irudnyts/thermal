import threading
import time
from queue import Empty, Full, Queue

import cv2
from picamera2 import Picamera2


FRAME_SIZE = (640, 480)
FRAME_RATE = 30
THERMAL_CAMERA_INDEX = 16
MAX_TIME_DIFFERENCE = 0.050
QUEUE_SIZE = 2


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
            put_latest(frames, (time.monotonic(), frame))
    except Exception as error:
        print(f"Raspberry Pi camera error: {error}")
        stop_event.set()
    finally:
        if picam2 is not None:
            picam2.stop()


def capture_thermal_camera(frames, stop_event):
    camera = None

    try:
        camera = cv2.VideoCapture(THERMAL_CAMERA_INDEX, cv2.CAP_V4L2)
        if not camera.isOpened():
            raise RuntimeError("cannot open thermal camera")

        while not stop_event.is_set():
            received, frame = camera.read()
            if not received:
                raise RuntimeError("cannot read thermal camera frame")
            put_latest(frames, (time.monotonic(), frame))
    except Exception as error:
        print(f"Thermal camera error: {error}")
        stop_event.set()
    finally:
        if camera is not None:
            camera.release()


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
            thermal_frame = cv2.resize(thermal_item[1], FRAME_SIZE)
            combined_frame = cv2.hconcat([pi_item[1], thermal_frame])
            cv2.imshow("Pi and Thermal Cameras", combined_frame)
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
