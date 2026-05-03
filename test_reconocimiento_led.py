import cv2
import time
import os
import numpy as np

# ─── GPIO ──────────────────────────────────────────────────────────────
try:
    import RPi.GPIO as GPIO
    RPI = True
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(21, GPIO.OUT)
    GPIO.output(21, GPIO.LOW)
    print("[GPIO] Listo en pin 21")
except:
    RPI = False
    print("[GPIO] Sin RPi - modo simulacion")


def activar_led(segundos=3):
    if RPI:
        GPIO.output(21, GPIO.HIGH)
        print(f"[GPIO] LED/RELE ENCENDIDO por {segundos}s")
        time.sleep(segundos)
        GPIO.output(21, GPIO.LOW)
        print("[GPIO] LED/RELE APAGADO")
    else:
        print(f"[SIMULACION] LED/RELE activado por {segundos}s")
        time.sleep(segundos)
        print("[SIMULACION] LED/RELE apagado")


# ─── Cargar modelo ────────────────────────────────────────────────────
if not os.path.exists("modelo.yml"):
    print("[ERROR] No hay modelo entrenado. Registra un usuario primero.")
    exit()

if os.path.exists("label_map.npy"):
    label_map = np.load("label_map.npy", allow_pickle=True).item()
else:
    label_map = {}

# Cargar usuarios
usuarios = {}
if os.path.exists("usuarios.txt"):
    with open("usuarios.txt", "r") as f:
        for linea in f:
            partes = linea.strip().split(",")
            if len(partes) == 2:
                usuarios[int(partes[0])] = partes[1]

recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.read("modelo.yml")
detector = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

print("[INFO] Camara iniciada. Presiona ESC para salir.")
print("[INFO] Acerca tu rostro a la camara...")

cap = cv2.VideoCapture(0)
intentos = 0
activado = False   # evita activar multiples veces seguidas

while True:
    ret, frame = cap.read()
    if not ret:
        print("[ERROR] No se pudo leer la camara")
        break

    gray   = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    rostros = detector.detectMultiScale(gray, 1.3, 5)

    for (x, y, w, h) in rostros:
        rostro = cv2.resize(gray[y:y+h, x:x+w], (200, 200))
        label, confianza = recognizer.predict(rostro)

        real_id = label_map.get(label, None)
        nombre  = usuarios.get(real_id, "Desconocido")

        if confianza < 70:
            # ── ROSTRO RECONOCIDO ──
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(frame, f"{nombre}  conf:{int(confianza)}",
                        (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (0, 255, 0), 2)
            cv2.putText(frame, "ACCESO OK - LED ON",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (0, 255, 0), 2)

            if not activado:
                activado = True
                print(f"[OK] Reconocido: {nombre}  (confianza: {int(confianza)})")
                # Activar LED en hilo separado para no congelar la camara
                import threading
                threading.Thread(
                    target=activar_led,
                    args=(3,),
                    daemon=True
                ).start()

        else:
            # ── NO RECONOCIDO ──
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
            cv2.putText(frame, f"Desconocido  conf:{int(confianza)}",
                        (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (0, 0, 255), 2)
            cv2.putText(frame, "NO AUTORIZADO",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (0, 0, 255), 2)
            activado = False   # resetear si deja de reconocer

    # Mostrar confianza en consola cada frame (util para calibrar)
    if len(rostros) == 0:
        activado = False

    cv2.imshow("Prueba Reconocimiento + LED", frame)

    if cv2.waitKey(1) == 27:   # ESC para salir
        break

cap.release()
cv2.destroyAllWindows()

if RPI:
    GPIO.output(21, GPIO.LOW)
    GPIO.cleanup()

print("[INFO] Prueba finalizada")
