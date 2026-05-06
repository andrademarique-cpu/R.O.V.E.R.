from machine import UART, Pin, PWM
import time, sys, uselect

#conectar grounds en comun raspberry 4 con pico W
#conectar 
#raspberry 4 gpio 14 - pico w gpio 1
#raspberry 4 gpio 15 - pico w gpio 0

#INICIA CODIGO MOVILIDAD

# Servos
s1 = PWM(Pin(26))   
s2 = PWM(Pin(22))
s3 = PWM(Pin(19))
s4 = PWM(Pin(18))

# Dirección
dir1 = PWM(Pin(20))
dir2 = PWM(Pin(21))

for s in (s1, s2, s3, s4, dir1, dir2):
    s.freq(50)

# Stop
STOP1 = 5000
STOP2 = 4950
STOP3 = 4950
STOP4 = 5000

# FWD base
FWD1 = 5660
FWD2 = 5900
FWD3 = 5800
FWD4 = 5850

# DELTAS BASE
DELTA1_BASE = FWD1 - STOP1
DELTA2_BASE = FWD2 - STOP2
DELTA3_BASE = FWD3 - STOP3
DELTA4_BASE = FWD4 - STOP4

DELTA1 = DELTA1_BASE
DELTA2 = DELTA2_BASE
DELTA3 = DELTA3_BASE
DELTA4 = DELTA4_BASE

# Dirección giro ruedas
DIR1 = -1
DIR2 = -1
DIR3 = 1 
DIR4 = 1 

# Dirección mecánica
CENTRO1 = 4700
IZQ1    = 6400
DER1    = 2800

CENTRO2 = 5100
IZQ2    = 3200
DER2    = 7200

# Estados
estado_mov = "stop"
estado_dir = "centro"

# Factores
factor_vel = 1.0
factor_giro = 1.0  

# FUNCIONES
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

    elif estado_mov == "stop":
        s1.duty_u16(STOP1)
        s2.duty_u16(STOP2)
        s3.duty_u16(STOP3)
        s4.duty_u16(STOP4)

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

# Reset
def reset_velocidad():
    global factor_vel
    factor_vel = 1.0
    print("🔄 Velocidad reseteada")

def reset_giro():
    global factor_giro
    factor_giro = 1.0
    print("🔄 Giro reseteado")

#FINALIZA CODIGO MOVILIDAD

# CORRECCIÓN: Usar pines 0 y 1 para UART según tus conexiones físicas
uart = UART(0, baudrate=115200, tx=Pin(16), rx=Pin(17))
led_onboard = Pin(25, Pin.OUT)

# Variables de la Máquina de Estados (7 bytes)
estado_sinc = 0
comando_rx = 0
vel_izq_rx = 0 # Gatillo Izquierdo (Reversa)
vel_der_rx = 0 # Gatillo Derecho (Avanzar)
joyx_rx = 0    # Joystick X (Dirección)

ultimo_mensaje_ms = time.ticks_ms()
TIMEOUT_SEGURIDAD_MS = 500

def detener_motores():
    global estado_mov, estado_dir, factor_vel, factor_giro
    led_onboard.value(0)
    estado_mov = "stop"
    estado_dir = "centro"
    factor_vel = 0.0
    factor_giro = 0.0
    aplicar_movimiento()
    aplicar_direccion()

while True:
    if uart.any():
        buffer = uart.read() 
        for byte_recibido in buffer: 
            if estado_sinc == 0:
                if byte_recibido == 0xFF: estado_sinc = 1
            elif estado_sinc == 1:
                if byte_recibido == 0xEE: estado_sinc = 2
                else: estado_sinc = 0
            elif estado_sinc == 2:
                comando_rx = byte_recibido
                estado_sinc = 3
            elif estado_sinc == 3:
                vel_izq_rx = byte_recibido 
                estado_sinc = 4
            elif estado_sinc == 4:
                vel_der_rx = byte_recibido 
                estado_sinc = 5
            elif estado_sinc == 5:
                joyx_rx = byte_recibido    
                estado_sinc = 6
            elif estado_sinc == 6: # RECEPCIÓN DEL CHECKSUM
                checksum_rx = byte_recibido 
                checksum_calc = (comando_rx + vel_izq_rx + vel_der_rx + joyx_rx) % 256
                
                if checksum_rx == checksum_calc:
                    ultimo_mensaje_ms = time.ticks_ms()
                    led_onboard.toggle()
                    
                    # --- MAPEO DE MOVIMIENTO (Gatillos) ---
                    # Asumimos que vel_der_rx (Gatillo R) es avanzar y vel_izq_rx (Gatillo L) es retroceder.
                    # Rango: 0 a 255. Ponemos una zona muerta de 10.
                    if vel_der_rx > 10 and vel_izq_rx <= 10:
                        estado_mov = "forward"
                        factor_vel = vel_der_rx / 255.0
                    elif vel_izq_rx > 10 and vel_der_rx <= 10:
                        estado_mov = "backward"
                        factor_vel = vel_izq_rx / 255.0
                    else:
                        estado_mov = "stop"
                        factor_vel = 0.0
                        
                    # --- MAPEO DE DIRECCIÓN (Joystick) ---
                    # Rango: 0 a 255. El centro es ~127.
                    # Zona muerta entre 110 y 145 para que no vibre si el joystick no está perfecto
                    if joyx_rx > 145: 
                        estado_dir = "der"
                        factor_giro = (joyx_rx - 127) / 128.0 # Normaliza de 0.0 a 1.0
                    elif joyx_rx < 110:
                        estado_dir = "izq"
                        factor_giro = (127 - joyx_rx) / 128.0 # Normaliza de 0.0 a 1.0
                    else:
                        estado_dir = "centro"
                        factor_giro = 0.0
                    
                    # Limitamos factores por seguridad (no mayores a 1.0)
                    factor_vel = min(1.0, factor_vel)
                    factor_giro = min(1.0, factor_giro) - 0.5

                    # Aplicar cambios a los PWM
                    aplicar_movimiento()
                    aplicar_direccion()
                    
                    print(f"Mov: {estado_mov} (Vel: {factor_vel:.2f}) | Dir: {estado_dir} (Giro: {factor_giro:.2f})")
                
                estado_sinc = 0

    if time.ticks_diff(time.ticks_ms(), ultimo_mensaje_ms) > TIMEOUT_SEGURIDAD_MS:
        print("Security-timeout")
        detener_motores()