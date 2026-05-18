import cv2
import time
import os
import threading
import numpy as np
from usuarios import cargar_usuarios

# ─── GPIO ──────────────────────────────────────────────────────────────
try:
    import RPi.GPIO as GPIO
    RPI = True
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(18, GPIO.OUT)
    GPIO.output(18, GPIO.HIGH)  # HIGH = apagado (LOW level relay)
    print("[GPIO] Listo en pin 18 - LOW level")
except:
    RPI = False
    print("[GPIO] Sin RPi - modo simulacion")


def rele_encender():
    """Enciende el relé y lo deja encendido."""
    if RPI:
        GPIO.output(18, GPIO.LOW)
        print("[GPIO] RELE ENCENDIDO")
    else:
        print("[SIMULACION] Rele encendido")


def rele_apagar():
    """Apaga el relé."""
    if RPI:
        GPIO.output(18, GPIO.HIGH)
        print("[GPIO] RELE APAGADO")
    else:
        print("[SIMULACION] Rele apagado")


# ─── Parámetros ────────────────────────────────────────────────────────
PARPADEOS_REQUERIDOS = 3
FRAMES_OJO_CERRADO   = 1
FRAMES_OJO_ABIERTO   = 2
TIMEOUT_PARPADEO     = 30
MAX_NO_AUTH          = 5

EYE_CASCADE = cv2.data.haarcascades + "haarcascade_eye.xml"


def guardar_log(nombre):
    with open("logs.txt", "a") as f:
        f.write(f"{time.ctime()} - {nombre}\n")


def _contar_ojos(gray, face_rect, eye_det):
    x, y, w, h = face_rect
    roi = gray[y: y + h // 2, x: x + w]
    ojos = eye_det.detectMultiScale(roi, 1.1, 4, minSize=(15, 15))
    return len(ojos)


def iniciar_sesion_thread(frame_queue, result_queue, stop_event):
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
    face_det = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    eye_det = cv2.CascadeClassifier(EYE_CASCADE)

    fase               = "RECONOCIMIENTO"
    nombre_reconocido  = None
    intentos_no_auth   = 0

    parpadeos          = 0
    frames_sin_ojos    = 0
    frames_con_ojos    = 0
    esperando_apertura = False
    t_inicio           = None

    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            break

        gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rostros = face_det.detectMultiScale(gray, 1.3, 5)

        # ── FASE 1: RECONOCIMIENTO ──────────────────────────────────────
        if fase == "RECONOCIMIENTO":
            no_auth_frame = False

            for (x, y, w, h) in rostros:
                rostro  = cv2.resize(gray[y:y + h, x:x + w], (200, 200))
                label, confianza = recognizer.predict(rostro)
                real_id = label_map.get(label, None)
                nombre  = usuarios.get(real_id, "Desconocido")

                if confianza < 70:
                    nombre_reconocido  = nombre
                    fase               = "PARPADEOS"
                    t_inicio           = time.time()
                    parpadeos          = 0
                    frames_sin_ojos    = 0
                    frames_con_ojos    = 0
                    esperando_apertura = False
                    print(f"[OK] Reconocido: {nombre}  (confianza: {int(confianza)})")
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(frame,
                                f"{nombre} - Parpadea {PARPADEOS_REQUERIDOS}x",
                                (x, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    break
                else:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                    cv2.putText(frame, "No autorizado", (x, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    no_auth_frame = True

            if no_auth_frame:
                intentos_no_auth += 1

            cv2.putText(frame, "Acerca tu rostro",
                        (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)

            if intentos_no_auth >= MAX_NO_AUTH:
                try:
                    frame_queue.put_nowait(frame.copy())
                except Exception:
                    pass
                cap.release()
                result_queue.put("Acceso denegado")
                return

        # ── FASE 2: CONTAR PARPADEOS ────────────────────────────────────
        elif fase == "PARPADEOS":
            elapsed = time.time() - t_inicio

            if elapsed > TIMEOUT_PARPADEO:
                cap.release()
                result_queue.put("Tiempo agotado - parpadea 3 veces para acceder")
                return

            n_ojos        = _contar_ojos(gray, rostros[0], eye_det) if len(rostros) > 0 else 0
            ojos_visibles = n_ojos >= 1

            if not esperando_apertura:
                if ojos_visibles:
                    frames_sin_ojos = 0
                    frames_con_ojos += 1
                else:
                    frames_sin_ojos += 1
                    frames_con_ojos  = 0
                    if frames_sin_ojos >= FRAMES_OJO_CERRADO:
                        esperando_apertura = True
                        frames_con_ojos    = 0
            else:
                if ojos_visibles:
                    frames_con_ojos += 1
                    if frames_con_ojos >= FRAMES_OJO_ABIERTO:
                        parpadeos         += 1
                        esperando_apertura = False
                        frames_sin_ojos    = 0
                        frames_con_ojos    = 0
                        print(f"[PARPADEO] {parpadeos}/{PARPADEOS_REQUERIDOS}")
                else:
                    frames_con_ojos = 0

            color      = (0, 207, 255)
            estado_txt = "CIERRA ojos" if not esperando_apertura else "ABRE  ojos"
            cv2.putText(frame,
                        f"{nombre_reconocido}  [{parpadeos}/{PARPADEOS_REQUERIDOS}]",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(frame,
                        f"{estado_txt}  ({int(TIMEOUT_PARPADEO - elapsed)}s)",
                        (10, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)
            ojo_color = (0, 255, 100) if ojos_visibles else (0, 60, 255)
            cv2.putText(frame,
                        f"ojos={'SI' if ojos_visibles else 'NO'} ({n_ojos})",
                        (10, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.5, ojo_color, 1)

            bw   = frame.shape[1] - 40
            prog = int((parpadeos / PARPADEOS_REQUERIDOS) * bw)
            cv2.rectangle(frame,
                          (20, frame.shape[0] - 18),
                          (frame.shape[1] - 20, frame.shape[0] - 6),
                          (42, 42, 42), -1)
            cv2.rectangle(frame,
                          (20, frame.shape[0] - 18),
                          (20 + prog, frame.shape[0] - 6),
                          color, -1)

            if len(rostros) > 0:
                x, y, w, h = rostros[0]
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

            # ¡Parpadeos completos! — encender relé y dejarlo encendido
            if parpadeos >= PARPADEOS_REQUERIDOS:
                try:
                    frame_queue.put_nowait(frame.copy())
                except Exception:
                    pass
                cap.release()
                guardar_log(nombre_reconocido)
                print(f"[ACCESO] Bienvenido {nombre_reconocido} - encendiendo rele...")
                rele_encender()   # se queda encendido hasta apagar el sistema
                result_queue.put(f"Bienvenido {nombre_reconocido}")
                return

        try:
            frame_queue.put_nowait(frame.copy())
        except Exception:
            pass

    cap.release()
    result_queue.put("Cancelado")
