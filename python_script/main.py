import cv2

# Conectar al stream RTMP
rtmp_url = "rtmp://localhost:1935/hls/my-stream"

cap = cv2.VideoCapture(rtmp_url)

if not cap.isOpened():
    print("Error: No se pudo abrir el stream")
    exit()

while cap.isOpened():
    ret, frame = cap.read()

    if not ret:
        print("Fin del stream o error de conexión")
        break

    # Aquí puedes procesar el frame
    # Ejemplo: convertir a escala de grises
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Mostrar (opcional)
    cv2.imshow('Stream en vivo', frame)

    # Presionar 'q' para salir
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()