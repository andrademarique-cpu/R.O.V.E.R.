import socket
import struct
import serial
import time
import RPi.GPIO as GPIO
import sys

# --- CONFIGURACION DE COMUNICACIONES ---
PUERTO = 5005
uart_pico = serial.Serial('/dev/ttyAMA0', baudrate=115200, timeout=0.1)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PUERTO))

# Formato UDP del PC (7 variables: 6 floats, 1 uint16)
formato_udp = struct.Struct('ffffffH')

# --- CONFIGURACION DE PINES (GPIO) ---
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

PIN_IN1 = 14
PIN_IN2 = 15
PIN_SERVO1 = 16
PIN_SERVO2 = 17

# Configurar pines como salidas
GPIO.setup(PIN_IN1, GPIO.OUT)
GPIO.setup(PIN_IN2, GPIO.OUT)
GPIO.setup(PIN_SERVO1, GPIO.OUT) # [CORREGIDO] 
GPIO.setup(PIN_SERVO2, GPIO.OUT) # [CORREGIDO]

t_move = 2 # Tiempo en segundos para el recorrido completo

# Configuracion de los Servos (PWM a 50Hz)
servo1 = GPIO.PWM(PIN_SERVO1, 50)
servo2 = GPIO.PWM(PIN_SERVO2, 50)

servo1.start(0) 
servo2.start(0)

# --- MEMORIA DEL SISTEMA ---
estado_sistema = "abajo" 
angulo_actual_servo = 70

# --- DICCIONARIO DE BOTONES ---
MAPEO_BOTONES = {
    0: "BTN_SOUTH",     # A / Cruz
    1: "BTN_EAST",      # B / Circulo
    2: "BTN_WEST",      # X / Cuadrado
    3: "BTN_NORTH",     # Y / Triangulo
    4: "BTN_TL",        # Bumper Izquierdo (LB)
    5: "BTN_TR",        # Bumper Derecho (RB)
    6: "BTN_SELECT",    # Select / View
    7: "BTN_START",     # Start / Menu
    8: "BTN_THUMBL",    # Clic Joystick Izquierdo (L3)
    9: "BTN_THUMBR",    # Clic Joystick Derecho (R3)
    10: "DPAD_UP",      # D-Pad Arriba (Mapeo personalizado en tu PC)
    11: "DPAD_DOWN",    # D-Pad Abajo
    12: "DPAD_LEFT",    # D-Pad Izquierda
    13: "DPAD_RIGHT"    # D-Pad Derecha
}

# --- FUNCIONES ---
def obtener_botones_activos(btns_mascara):
    botones_presionados = []
    for bit, nombre_boton in MAPEO_BOTONES.items():
        if (btns_mascara & (1 << bit)) != 0:
            botones_presionados.append(nombre_boton)
    return botones_presionados

def detener_dc():
    GPIO.output(PIN_IN1, GPIO.LOW)
    GPIO.output(PIN_IN2, GPIO.LOW)

def calcular_duty(angulo):
    angulo = max(0.0, min(180.0, float(angulo)))
    min_duty = 2.5
    max_duty = 12.5
    return min_duty + ((max_duty - min_duty) * (angulo / 180.0))

def mover_servo(duty):
    """[CORREGIDO] Aplica el pulso a ambos servos simultneamente"""
    servo1.ChangeDutyCycle(duty)
    servo2.ChangeDutyCycle(duty)

def ejecutar_movimiento_dual(angulo_objetivo):
    global angulo_actual_servo
    pasos = int(t_move * 25) 
    pausa_dt = t_move / pasos
    paso_angular = (angulo_objetivo - angulo_actual_servo) / pasos
    
    for i in range(1, pasos + 1):
        theta_k = angulo_actual_servo + (paso_angular * i)
        mover_servo(calcular_duty(theta_k))
        time.sleep(pausa_dt)
        
    angulo_actual_servo = angulo_objetivo
    detener_dc()
    mover_servo(0)
    print("|| Recorrido finalizado, actuadores detenidos.")

def subir():
    global estado_sistema
    if estado_sistema == "arriba":
        print("[!] Bloqueo: Ya se encuentra ARRIBA.")
        return 
    print(f"Subiendo sincronizado ({t_move} s)...")
    GPIO.output(PIN_IN1, GPIO.LOW)
    GPIO.output(PIN_IN2, GPIO.HIGH)
    ejecutar_movimiento_dual(120)
    estado_sistema = "arriba"

def bajar():
    global estado_sistema
    if estado_sistema == "abajo":
        print("[!] Bloqueo: Ya se encuentra ABAJO.")
        return
    print(f"Bajando sincronizado ({t_move} s)...")
    GPIO.output(PIN_IN1, GPIO.HIGH)
    GPIO.output(PIN_IN2, GPIO.LOW)
    ejecutar_movimiento_dual(70)
    estado_sistema = "abajo"

def ejecutar_trayectoria_servo(theta_target, t_exec_s, sample_rate_hz=25):
    global angulo_actual_servo
    theta_target = max(0.0, min(180.0, float(theta_target)))
    steps_count = max(1, int(t_exec_s * sample_rate_hz))
    dt_s = t_exec_s / steps_count
    theta_step = (theta_target - angulo_actual_servo) / steps_count
    
    for k in range(1, steps_count + 1):
        theta_k = angulo_actual_servo + (theta_step * k)
        mover_servo(calcular_duty(theta_k))
        time.sleep(dt_s)
        
    angulo_actual_servo = theta_target
    mover_servo(0)

def lower_bucket(dump_angle_deg, t_total_s):
    global estado_sistema, angulo_actual_servo
    if estado_sistema != "arriba":
        print("[!] Interlock: Operacion denegada. Suba primero el mecanismo.")
        return
    
    print(f"[*] Descargando bucket. Objetivo: {dump_angle_deg}, Tiempo: {t_total_s}s")
    theta_home = angulo_actual_servo 
    t_stroke_s = float(t_total_s) / 2.0
    
    ejecutar_trayectoria_servo(dump_angle_deg, t_stroke_s)
    time.sleep(1) 
    ejecutar_trayectoria_servo(theta_home, t_stroke_s)
    print("[*] Bucket asegurado en reposo.")

def enviar_a_pico(gatl, gatr, x_izq):
    gatl = max(0.0, min(1.0, gatl))
    gatr = max(0.0, min(1.0, gatr))
    x_izq = max(-1.0, min(1.0, x_izq))

    gatl_byte = int(gatl * 250)
    gatr_byte = int(gatr * 250)
    joyx_byte = min(255, int((x_izq + 1) * 125))
    
    checksum = (0x01 + gatl_byte + gatr_byte + joyx_byte) % 256
    trama = bytearray([0xFF, 0xEE, 0x01, gatl_byte, gatr_byte, joyx_byte, checksum])
    uart_pico.write(trama)
    
# --- BUCLE PRINCIPAL ---
try:
    print("Iniciando posiciones...")
    detener_dc()
    mover_servo(calcular_duty(angulo_actual_servo))
    time.sleep(0.5)
    mover_servo(0)

    print("Rover a la escucha (Trama UDP y enviando a Pico por UART)...")
    
    while True:
        # Recibir paquete UDP
        datos, addr = sock.recvfrom(1024)
        ejx, ejy, ejrx, ejry, gatl, gatr, btns = formato_udp.unpack(datos)
        
        botones_actuales = obtener_botones_activos(btns)
        
        # --- Logica de la Excavacion vinculada a botones ---
        # Puedes mapearlos a tu gusto. Aqui un ejemplo:
        if "DPAD_UP" in botones_actuales:
            print("subir")
            subir()
        elif "DPAD_DOWN" in botones_actuales:
            print("Bajar")
            bajar()
        elif "BTN_WEST" in botones_actuales:
            lower_bucket(180, 10)
            
        # --- Logica de traccion ---
        x_izq = 0.0 if abs(ejx) < 0.15 else ejx
        enviar_a_pico(gatl, gatr, x_izq)
        
        print(f"Traccion -> L:{gatl:.2f} R:{gatr:.2f} X:{x_izq:.2f} | Botones: {botones_actuales}")

except KeyboardInterrupt:
    print("\n[!] Programa detenido manualmente (Ctrl+C).")
except Exception as e:
    print(f"\n[!] Error crkitico: {e}")
finally:
    # [CORREGIDO] Bloque de limpieza seguro
    print("[*] Limpiando puertos e interfaces...")
    detener_dc()
    servo1.stop()
    servo2.stop()
    GPIO.cleanup()
    uart_pico.close()
    sock.close()
    sys.exit(0)
