from machine import Pin, PWM
import sys, uselect, time

# =========================
# SERVOS TRACCIÓN
# =========================
s1 = PWM(Pin(26))   # izquierda
s2 = PWM(Pin(22))   # izquierda
s3 = PWM(Pin(18))   # derecha
s4 = PWM(Pin(19))   # derecha

# =========================
# DIRECCIÓN MECÁNICA
# =========================
dir1 = PWM(Pin(21))
dir2 = PWM(Pin(20))

for s in (s1, s2, s3, s4, dir1, dir2):
    s.freq(50)

# =========================
# STOP
# =========================
STOP1 = 4950
STOP2 = 5000
STOP3 = 4950
STOP4 = 4950

# =========================
# VELOCIDAD BASE
# =========================
FWD1 = 5660
FWD2 = 5900
FWD3 = 5800
FWD4 = 5850

# =========================
# DELTAS
# =========================
DELTA1_BASE = FWD1 - STOP1
DELTA2_BASE = FWD2 - STOP2
DELTA3_BASE = FWD3 - STOP3
DELTA4_BASE = FWD4 - STOP4

DELTA1 = DELTA1_BASE
DELTA2 = DELTA2_BASE
DELTA3 = DELTA3_BASE
DELTA4 = DELTA4_BASE

# =========================
# DIRECCIÓN DE GIRO MOTORES
# =========================
DIR1 = -1
DIR2 = -1
DIR3 = 1
DIR4 = 1

# =========================
# DIRECCIÓN MECÁNICA
# =========================
CENTRO1 = 3900
IZQ1    = 4800
DER1    = 2700

CENTRO2 = 4000
IZQ2    = 2600
DER2    = 5400

# =========================
# ESTADOS
# =========================
estado_mov = "stop"
estado_dir = "centro"

# =========================
# FACTORES
# =========================
factor_vel = 1.0
factor_giro = 1.0

# =========================
# MOVIMIENTO NORMAL
# =========================
def aplicar_movimiento():

    if estado_mov == "forward":

        s1.duty_u16(int(STOP1 + DIR1 * DELTA1 * factor_vel))
        s2.duty_u16(int(STOP2 + DIR2 * DELTA2 * factor_vel))
        s3.duty_u16(int(STOP3 + DIR3 * DELTA3 * factor_vel))
        s4.duty_u16(int(STOP4 + DIR4 * DELTA4 * factor_vel))

    elif estado_mov == "backward":

        s1.duty_u16(int(STOP1 - DIR1 * DELTA1 * factor_vel))
        s2.duty_u16(int(STOP2 - DIR2 * DELTA2 * factor_vel))
        s3.duty_u16(int(STOP3 - DIR3 * DELTA3 * factor_vel))
        s4.duty_u16(int(STOP4 - DIR4 * DELTA4 * factor_vel))

    else:

        s1.duty_u16(STOP1)
        s2.duty_u16(STOP2)
        s3.duty_u16(STOP3)
        s4.duty_u16(STOP4)

# =========================
# DIRECCIÓN MECÁNICA
# =========================
def aplicar_direccion():

    if estado_dir == "izq":

        val1 = int(CENTRO1 + (IZQ1 - CENTRO1) * factor_giro)
        val2 = int(CENTRO2 + (DER2 - CENTRO2) * factor_giro)

        dir1.duty_u16(val1)
        dir2.duty_u16(val2)

    elif estado_dir == "der":

        val1 = int(CENTRO1 + (DER1 - CENTRO1) * factor_giro)
        val2 = int(CENTRO2 + (IZQ2 - CENTRO2) * factor_giro)

        dir1.duty_u16(val1)
        dir2.duty_u16(val2)

    else:

        dir1.duty_u16(CENTRO1)
        dir2.duty_u16(CENTRO2)

# =========================
# GIRO DIFERENCIAL IZQUIERDA
# =========================
def giro_diferencial_izquierda():

    global estado_dir

    estado_dir = "izq"

    # izquierda atrás
    s1.duty_u16(int(STOP1 - DIR1 * DELTA1 * factor_vel))
    s2.duty_u16(int(STOP2 - DIR2 * DELTA2 * factor_vel))

    # derecha adelante
    s3.duty_u16(int(STOP3 + DIR3 * DELTA3 * factor_vel))
    s4.duty_u16(int(STOP4 + DIR4 * DELTA4 * factor_vel))

    aplicar_direccion()

# =========================
# GIRO DIFERENCIAL DERECHA
# =========================
def giro_diferencial_derecha():

    global estado_dir

    estado_dir = "der"

    # izquierda adelante
    s1.duty_u16(int(STOP1 + DIR1 * DELTA1 * factor_vel))
    s2.duty_u16(int(STOP2 + DIR2 * DELTA2 * factor_vel))

    # derecha atrás
    s3.duty_u16(int(STOP3 - DIR3 * DELTA3 * factor_vel))
    s4.duty_u16(int(STOP4 - DIR4 * DELTA4 * factor_vel))

    aplicar_direccion()

# =========================
# RESET VELOCIDAD
# =========================
def reset_velocidad():

    global factor_vel

    factor_vel = 1.0
    print("🔄 Velocidad reseteada")

# =========================
# RESET GIRO
# =========================
def reset_giro():

    global factor_giro

    factor_giro = 1.0
    print("🔄 Giro reseteado")

# =========================
# MENSAJES
# =========================
print("W/S movimiento")
print("J/L dirección mecánica")
print("A/D giro diferencial")
print("K centro")
print("ESPACIO stop")
print("E/C velocidad")
print("T/G intensidad giro")
print("R reset vel | Y reset giro")
print("Q salir")

# =========================
# ENTRADA TECLADO
# =========================
poll = uselect.poll()
poll.register(sys.stdin, uselect.POLLIN)

# Estado inicial
aplicar_movimiento()
aplicar_direccion()

# =========================
# LOOP PRINCIPAL
# =========================
while True:

    if poll.poll(100):

        t = sys.stdin.read(1).lower()

        # =====================
        # MOVIMIENTO
        # =====================

        if t == 'w':

            estado_mov = "forward"
            aplicar_movimiento()

        elif t == 's':

            estado_mov = "backward"
            aplicar_movimiento()

        elif t == ' ':

            estado_mov = "stop"
            aplicar_movimiento()

        # =====================
        # DIRECCIÓN NORMAL
        # =====================

        elif t == 'j':

            estado_dir = "izq"
            aplicar_direccion()

        elif t == 'l':

            estado_dir = "der"
            aplicar_direccion()

        elif t == 'k':

            estado_dir = "centro"
            aplicar_direccion()

        # =====================
        # GIRO DIFERENCIAL
        # =====================

        elif t == 'a':

            giro_diferencial_izquierda()

        elif t == 'd':

            giro_diferencial_derecha()

        # =====================
        # VELOCIDAD
        # =====================

        elif t == 'e':

            factor_vel += 0.1
            print("Vel:", round(factor_vel, 2))

        elif t == 'c':

            factor_vel -= 0.1

            if factor_vel < 0.2:
                factor_vel = 0.2

            print("Vel:", round(factor_vel, 2))

        elif t == 'r':

            reset_velocidad()

        # =====================
        # INTENSIDAD GIRO
        # =====================

        elif t == 't':

            factor_giro += 0.2

            if factor_giro > 1.5:
                factor_giro = 1.5

            print("Giro:", round(factor_giro, 2))

        elif t == 'g':

            factor_giro -= 0.2

            if factor_giro < 0.4:
                factor_giro = 0.4

            print("Giro:", round(factor_giro, 2))

        elif t == 'y':

            reset_giro()

        # =====================
        # SALIR
        # =====================

        elif t == 'q':

            estado_mov = "stop"

            aplicar_movimiento()
            aplicar_direccion()

            break

    time.sleep(0.05)