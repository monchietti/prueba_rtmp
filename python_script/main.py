import cv2

hls_url = "http://localhost:5555/hls/my-stream.m3u8"

cap = cv2.VideoCapture(hls_url)

if not cap.isOpened():
    print("Error: no se pudo abrir el stream HLS")
    exit()

while True:
    ret, frame = cap.read()

    if not ret:
        print("No hay frame (buffering o corte)")
        break

    cv2.imshow("HLS Stream", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()