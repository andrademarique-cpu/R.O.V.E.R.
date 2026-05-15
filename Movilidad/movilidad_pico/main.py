from machine import UART, Pin, PWM
import time, sys

# ==========================================
# CONFIGURACIÓN DE PINES Y CALIBRACIÓN (BASE FUNCIONAL)
# ==========================================

# Servos Tracción
s1 = PWM(Pin(26))   # Izquierda
s2 = PWM(Pin(22))   # Izquierda
s3 = PWM(Pin(19))   # Derecha
s4 = PWM(Pin(18))   # Derecha

# Dirección Mecánica
dir1 = PWM(Pin(20))
dir2 = PWM(Pin(21))

for s in (s1, s2, s3, s4, dir1, dir2):
    s.freq(50)

# Valores de STOP (Calibrados)
STOP1, STOP2, STOP3, STOP4 = 5000, 4950, 4950, 5000

# Valores FWD y Deltas
FWD1, FWD2, FWD3, FWD4 = 5660, 5900, 5800, 5850
DELTA1, DELTA2, DELTA3, DELTA4 = FWD1-STOP1, FWD2-STOP2, FWD3-STOP3, FWD4-STOP4

# Dirección de giro motores
DIR1, DIR2, DIR3, DIR4 = -1, -1, 1, 1 

# Dirección mecánica (Calibración "Funcional")
#oiriginal:
# CENTRO1, IZQ1, DER1 = 5700, 6000, 3000
# CENTRO2, IZQ2, DER2 = 5100, 3200, 7200

CENTRO1, IZQ1, DER1 = 4000, 6000, 3000
CENTRO2, IZQ2, DER2 = 3800, 3200, 7200

# ==========================================
# VARIABLES DE ESTADO Y UART
# ==========================================
estado_mov = "stop"
estado_dir = "centro"
factor_vel = 0.0
factor_giro = 0.0  

uart = UART(0, baudrate=115200, tx=Pin(16), rx=Pin(17))
led_onboard = Pin(25, Pin.OUT)

# Variables de la Máquina de Estados
estado_sinc = 0
comando_rx = 0x01
vel_izq_rx, vel_der_rx, joyx_rx = 0, 0, 0
ultimo_mensaje_ms = time.ticks_ms()
TIMEOUT_SEGURIDAD_MS = 500

# ==========================================
# FUNCIONES INTEGRADAS
# ==========================================

def aplicar_movimiento():
    """Movimiento estándar (Adelante/Atrás)"""
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
    else: # Stop
        s1.duty_u16(STOP1); s2.duty_u16(STOP2)
        s3.duty_u16(STOP3); s4.duty_u16(STOP4)

def aplicar_direccion_mecanica():
    """Giro de las ruedas delanteras"""
    if estado_dir == "izq":
        val1 = int(CENTRO1 + (IZQ1 - CENTRO1) * factor_giro)
        val2 = int(CENTRO2 + (DER2 - CENTRO2) * factor_giro)
        dir1.duty_u16(val1); dir2.duty_u16(val2)
    elif estado_dir == "der":
        val1 = int(CENTRO1 + (DER1 - CENTRO1) * factor_giro)
        val2 = int(CENTRO2 + (IZQ2 - CENTRO2) * factor_giro)
        dir1.duty_u16(val1); dir2.duty_u16(val2)
    else:
        dir1.duty_u16(CENTRO1); dir2.duty_u16(CENTRO2)

def giro_diferencial(sentido, intensidad):
    """NUEVA FUNCIÓN: Gira sobre su propio eje usando tracción opuesta"""
    # Ponemos la dirección en modo giro máximo para ayudar mecánicamente
    if sentido == "izq":
        # Lados izquierdos atrás, derechos adelante
        s1.duty_u16(int(STOP1 - DIR1 * DELTA1 * intensidad))
        s2.duty_u16(int(STOP2 - DIR2 * DELTA2 * intensidad))
        s3.duty_u16(int(STOP3 + DIR3 * DELTA3 * intensidad))
        s4.duty_u16(int(STOP4 + DIR4 * DELTA4 * intensidad))
        # Opcional: mover servos de dirección para cerrar el radio
        dir1.duty_u16(IZQ1); dir2.duty_u16(DER2)
    else: # der
        # Lados izquierdos adelante, derechos atrás
        s1.duty_u16(int(STOP1 + DIR1 * DELTA1 * intensidad))
        s2.duty_u16(int(STOP2 + DIR2 * DELTA2 * intensidad))
        s3.duty_u16(int(STOP3 - DIR3 * DELTA3 * intensidad))
        s4.duty_u16(int(STOP4 - DIR4 * DELTA4 * intensidad))
        dir1.duty_u16(DER1); dir2.duty_u16(IZQ2)

def detener_motores():
    global estado_mov, factor_vel
    estado_mov = "stop"
    factor_vel = 0.0
    aplicar_movimiento()
    dir1.duty_u16(CENTRO1)
    dir2.duty_u16(CENTRO2)
    led_onboard.value(0)

# ==========================================
# BUCLE PRINCIPAL (MÁQUINA DE ESTADOS)
# ==========================================

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
            elif estado_sinc == 6:
                checksum_rx = byte_recibido 
                checksum_calc = (comando_rx + vel_izq_rx + vel_der_rx + joyx_rx) % 256
                
                if checksum_rx == checksum_calc:
                    ultimo_mensaje_ms = time.ticks_ms()
                    led_onboard.toggle()
                    
                    # ========================================================
                    # EVALUACIÓN DE COMANDOS PRIORITARIOS (BOTONES DE GIRO)
                    # ========================================================
                    print("Cmd: 0x{:02X} | V_Izq: {} | V_Der: {} | JoyX: {}".format(comando_rx, vel_izq_rx, vel_der_rx, joyx_rx))
                    if comando_rx == 0x02:
                        # BTN_TL: Giro diferencial inmediato sobre su eje a la izquierda
                        # (Ajusta el 1.0 si notas que gira demasiado rápido)
                        giro_diferencial("izq", 1.0)
                        
                    elif comando_rx == 0x03:
                        # BTN_TR: Giro diferencial inmediato sobre su eje a la derecha
                        giro_diferencial("der", 1.0)
                        
                    else:
                        # COMANDO NORMAL (0x01): LÓGICA TRADICIONAL POR MANDOS ANALÓGICOS
                        
                        # 1. MAPEO DE VELOCIDAD (Gatillos)
                        if vel_der_rx > 15:
                            estado_mov = "forward"
                            factor_vel = vel_der_rx / 255.0
                        elif vel_izq_rx > 15:
                            estado_mov = "backward"
                            factor_vel = vel_izq_rx / 255.0
                        else:
                            estado_mov = "stop"
                            factor_vel = 0.0
                            
                        # 2. MAPEO DE DIRECCIÓN (Joystick X)
                        if joyx_rx > 145: 
                            estado_dir = "der"
                            factor_giro = (joyx_rx - 127) / 128.0
                        elif joyx_rx < 110:
                            estado_dir = "izq"
                            factor_giro = (127 - joyx_rx) / 128.0
                        else:
                            estado_dir = "centro"
                            factor_giro = 0.0
                        
                        # 3. LÓGICA DE CONTROL COMBINADA
                        if estado_mov == "stop" and estado_dir != "centro":
                            giro_diferencial(estado_dir, factor_giro)
                        else:
                            aplicar_movimiento()
                            aplicar_direccion_mecanica()
                
                estado_sinc = 0

    # Seguridad: si se pierde la conexión, parar
    if time.ticks_diff(time.ticks_ms(), ultimo_mensaje_ms) > TIMEOUT_SEGURIDAD_MS:
        detener_motores()
        print("Security-Timeout")