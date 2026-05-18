import time

try:
    import RPi.GPIO as GPIO  # type: ignore
    RPI = True
except ImportError:
    RPI = False


def activar_rele():
    if not RPI:
        print('Simulación: Relé activado')
        return

    GPIO.setmode(GPIO.BCM)

    PIN_RELE = 18
    GPIO.setup(PIN_RELE, GPIO.OUT)

    GPIO.output(PIN_RELE, GPIO.HIGH)
    time.sleep(3)
    GPIO.output(PIN_RELE, GPIO.LOW)

    GPIO.cleanup()
