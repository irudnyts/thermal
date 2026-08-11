import av
import cv2

PORT = 5000

url = (
    f"udp://0.0.0.0:{PORT}"
    "?fifo_size=1000000"
    "&overrun_nonfatal=1"
)

container = av.open(
    url,
    mode="r",
    format="mpegts"
)

for frame in container.decode(video=0):
    image = frame.to_ndarray(format="bgr24")

    cv2.imshow("Raspberry Pi Camera", image)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

container.close()
cv2.destroyAllWindows()