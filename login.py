import cv2
import time
import os
import threading
import numpy as np
from gpio_control import activar_rele
from usuarios import cargar_usuarios


def guardar_log(nombre):
    with open("logs.txt", "a") as f:
        f.write(f"{time.ctime()} - {nombre}\n")


def iniciar_sesion_thread(frame_queue, result_queue, stop_event):
    """
    Corre en un hilo separado.
    - frame_queue  : pone frames BGR para que tkinter los muestre
    - result_queue : pone el resultado final (string)
    - stop_event   : threading.Event — se setea para cancelar desde afuera
    """
    if not os.path.exists("modelo.yml"):
        result_queue.put("No hay modelo entrenado")
        return

    label_map = {}
    if os.path.exists("label_map.npy"):
        label_map = np.load("label_map.npy", allow_pickle=True).item()

    usuarios = cargar_usuarios()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        result_queue.put("Error: no se pudo abrir la camara")
        return

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read("modelo.yml")
    detector = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    intentos_frame = 0

    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            break

        gray   = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rostros = detector.detectMultiScale(gray, 1.3, 5)

        no_autorizado_en_frame = False

        for (x, y, w, h) in rostros:
            rostro = cv2.resize(gray[y:y+h, x:x+w], (200, 200))
            label, confianza = recognizer.predict(rostro)

            real_id = label_map.get(label, None)
            nombre  = usuarios.get(real_id, "Desconocido")

            if confianza < 70:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(frame, f"{nombre} - OK", (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                # Mandamos el frame con el recuadro verde antes de cerrar
                try:
                    frame_queue.put_nowait(frame.copy())
                except Exception:
                    pass
                cap.release()
                guardar_log(nombre)
                activar_rele()
                result_queue.put(f"Bienvenido {nombre}")
                return
            else:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
                cv2.putText(frame, "No autorizado", (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                no_autorizado_en_frame = True

        if no_autorizado_en_frame:
            intentos_frame += 1

        # Enviamos el frame a la cola (sin bloquear si está llena)
        try:
            frame_queue.put_nowait(frame.copy())
        except Exception:
            pass

        if intentos_frame >= 5:
            cap.release()
            result_queue.put("Acceso denegado")
            return

    cap.release()
    result_queue.put("Cancelado")
