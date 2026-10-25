import cv2
from inputs.video_source import VideoSource

VIDEO_PATH = "data/video_clean/run01_clean.mp4"  # adjust if needed

source = VideoSource(VIDEO_PATH)

while True:
    success, frame = source.read()

    if not success:
        print("End of video")
        break

    cv2.imshow("Forrest – video input", frame)

    if cv2.waitKey(30) & 0xFF == 27:
        break

source.release()
cv2.destroyAllWindows()