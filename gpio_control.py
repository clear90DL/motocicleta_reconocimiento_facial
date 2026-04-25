import time
try:
    import RPi.GPIO as GPIO  # type: ignore
    RPI = True
except:
    RPI = False
def activar_rele():
    if not RPI:
        print('Simulación: Relé activado')
        return

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(17, GPIO.OUT)

    GPIO.output(17, GPIO.HIGH)
    time.sleep(3)
    GPIO.output(17, GPIO.LOW)

    GPIO.cleanup()
