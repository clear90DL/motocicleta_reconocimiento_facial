import cv2
import os
import threading
from usuarios import guardar_usuario


def registrar_usuario_thread(nombre, user_id, frame_queue, progreso_queue, stop_event):
    """
    Corre en un hilo separado.
    - frame_queue   : frames BGR anotados para mostrar en la UI
    - progreso_queue: mensajes de progreso  ("30/30", "OK", "ERROR:...")
    - stop_event    : threading.Event para cancelar desde afuera
    """
    ruta = f"rostros/{user_id}"
    os.makedirs(ruta, exist_ok=True)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        progreso_queue.put("ERROR:No se pudo abrir la camara")
        return

    detector = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    contador = 0
    total    = 100

    while contador < total and not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            break

        gray   = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rostros = detector.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in rostros:
            rostro = cv2.resize(gray[y:y+h, x:x+w], (200, 200))
            cv2.imwrite(f"{ruta}/rostro_{contador}.jpg", rostro)
            contador += 1

            # Dibujar recuadro y contador
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 207, 255), 2)
            progreso_queue.put(f"{contador}/{total}")

            if contador >= total:
                break

        # Overlay de progreso en el frame
        pct  = int((contador / total) * 100)
        bar_w = int((contador / total) * (frame.shape[1] - 40))
        cv2.rectangle(frame, (20, frame.shape[0]-30),
                      (frame.shape[1]-20, frame.shape[0]-14),
                      (42, 42, 42), -1)
        cv2.rectangle(frame, (20, frame.shape[0]-30),
                      (20 + bar_w, frame.shape[0]-14),
                      (0, 207, 255), -1)
        cv2.putText(frame, f"Capturas: {contador}/{total}  ({pct}%)",
                    (20, frame.shape[0]-36),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 207, 255), 1)

        try:
            frame_queue.put_nowait(frame.copy())
        except Exception:
            pass

    cap.release()

    if stop_event.is_set():
        progreso_queue.put("CANCELADO")
        return

    # Guardar usuario y entrenar
    guardar_usuario(int(user_id), nombre)
    progreso_queue.put("ENTRENANDO")
