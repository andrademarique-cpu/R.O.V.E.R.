from machine import Pin, PWM
import time, sys, uselect

# 1. Configurar los pines GPIO como Salidas (OUT)
pin_in1 = Pin(0, Pin.OUT)
pin_in2 = Pin(1, Pin.OUT)
t_move = 2 # Tiempo en segundos para el recorrido completo

# Servos Movilidad
s1 = PWM(Pin(17))  # izquierda
s2 = PWM(Pin(16))  # izquierda
s3 = PWM(Pin(18))  # derecha
s4 = PWM(Pin(21))  # derecha

# Servos direccion
dir1 = PWM(Pin(19))
dir2 = PWM(Pin(20))

for s in (s1, s2, s3, s4, dir1, dir2):
    s.freq(50)

# Stop continuos
STOP1 = 4950
STOP2 = 5000
STOP3 = 4950
STOP4 = 5000

# FWD (calibrados)
FWD1 = 5660
FWD2 = 5900
FWD3 = 5800
FWD4 = 5800

# DELTAS 
DELTA1 = FWD1 - STOP1
DELTA2 = FWD2 - STOP2
DELTA3 = FWD3 - STOP3
DELTA4 = FWD4 - STOP4

# Dirección de giro 
DIR1 = 1
DIR2 = 1
DIR3 = -1
DIR4 = -1

# DIRECCIÓN MECÁNICA
CENTRO1 = 4000
IZQ1    = 6000
DER1    = 2400

CENTRO2 = 4900
IZQ2    = 3000
DER2    = 6800

# ESTADOS 
estado_mov = "stop"
estado_dir = "centro"

# FUNCIONES 
def aplicar_movimiento():
    if estado_mov == "forward":
        s1.duty_u16(STOP1 + DIR1 * DELTA1)
        s2.duty_u16(STOP2 + DIR2 * DELTA2)
        s3.duty_u16(STOP3 + DIR3 * DELTA3)
        s4.duty_u16(STOP4 + DIR4 * DELTA4)

    elif estado_mov == "backward":
        s1.duty_u16(STOP1 - DIR1 * DELTA1)
        s2.duty_u16(STOP2 - DIR2 * DELTA2)
        s3.duty_u16(STOP3 - DIR3 * DELTA3)
        s4.duty_u16(STOP4 - DIR4 * DELTA4)

    else:
        s1.duty_u16(STOP1)
        s2.duty_u16(STOP2)
        s3.duty_u16(STOP3)
        s4.duty_u16(STOP4)

def aplicar_direccion():
    if estado_dir == "izq":
        dir1.duty_u16(IZQ1)
        dir2.duty_u16(DER2)  # invertido

    elif estado_dir == "der":
        dir1.duty_u16(DER1)
        dir2.duty_u16(IZQ2)  # invertido

    else:
        dir1.duty_u16(CENTRO1)
        dir2.duty_u16(CENTRO2)

# Servo motor Excavacion
pin_señal = Pin(16)
servo = PWM(pin_señal)
servo.freq(50)

# 2. Variables de estado lógico (Memoria del sistema)
estado_sistema = "abajo" 
angulo_actual_servo = 70 

# 3. Funciones de control y trayectoria
def detener_dc():
    pin_in1.value(0) 
    pin_in2.value(0) 

def calcular_duty(angulo):
    """Calcula la señal PWM en silencio para no saturar la consola durante el bucle."""
    angulo = max(0.0, min(180.0, float(angulo)))
    min_duty = 1638
    max_duty = 8192
    return int(min_duty + ((max_duty - min_duty) * (angulo / 180.0)))

def ejecutar_movimiento_dual(angulo_objetivo):
    """
    Interpola el servo lentamente durante 't_move' segundos 
    mientras el motor DC (que ya fue encendido) sigue girando.
    """
    global angulo_actual_servo
    
    # 25 iteraciones por segundo de movimiento
    pasos = int(t_move * 25) 
    pausa_dt = t_move / pasos
    paso_angular = (angulo_objetivo - angulo_actual_servo) / pasos
    
    # Bucle que sincroniza ambos tiempos
    for i in range(1, pasos + 1):
        theta_k = angulo_actual_servo + (paso_angular * i)
        servo.duty_u16(calcular_duty(theta_k))
        time.sleep(pausa_dt)
        
    # Al finalizar el tiempo, actualizamos variables y cortamos el DC
    angulo_actual_servo = angulo_objetivo
    detener_dc()
    print("|| Recorrido finalizado, actuadores detenidos.")

def subir():
    global estado_sistema
    # Validamos el estado antes de actuar
    if estado_sistema == "arriba":
        print("[!] Bloqueo de seguridad: El mecanismo ya se encuentra ARRIBA.")
        return # El "return" cancela la función y evita que los motores se enciendan
        
    print(f"Subiendo de forma sincronizada ({t_move} s)...")
    
    # 1. Encender el motor DC en dirección de subida
    pin_in1.value(0) 
    pin_in2.value(1) 
    
    # 2. Mover el servo a 180° ocupando el mismo lapso de tiempo
    ejecutar_movimiento_dual(120)
    
    # 3. Memorizar la nueva posición
    estado_sistema = "arriba"
    print("[*] Estado actualizado: ARRIBA")

def bajar():
    global estado_sistema
    # Validamos el estado
    if estado_sistema == "abajo":
        print("[!] Bloqueo de seguridad: El mecanismo ya se encuentra ABAJO.")
        return
        
    print(f"Bajando de forma sincronizada ({t_move} s)...")
    
    # 1. Encender el motor DC en dirección de bajada
    pin_in1.value(1) 
    pin_in2.value(0) 
    
    # 2. Mover el servo a 0° ocupando el mismo lapso de tiempo
    ejecutar_movimiento_dual(70)
    
    # 3. Memorizar la nueva posición
    estado_sistema = "abajo"
    print("[*] Estado actualizado: ABAJO")

def ejecutar_trayectoria_servo(theta_target, t_exec_s, sample_rate_hz=25):
    """
    Ejecuta un perfil de posición lineal exclusivo para el servomotor.
    """
    global angulo_actual_servo
    
    theta_target = max(0.0, min(180.0, float(theta_target)))
    steps_count = max(1, int(t_exec_s * sample_rate_hz))
    dt_s = t_exec_s / steps_count
    theta_step = (theta_target - angulo_actual_servo) / steps_count
    
    for k in range(1, steps_count + 1):
        theta_k = angulo_actual_servo + (theta_step * k)
        servo.duty_u16(calcular_duty(theta_k))
        time.sleep(dt_s)
        
    angulo_actual_servo = theta_target

def lower_bucket(dump_angle_deg, t_total_s):
    """
    t_total_s: Tiempo total para completar la secuencia (descarga + retorno)
    """
    global estado_sistema, angulo_actual_servo
    
    # 1. Interlock de Seguridad
    if estado_sistema != "arriba":
        print("[!] Interlock Activo: El mecanismo no está en posición (ARRIBA). Operación de descarga denegada.")
        return
        
    print(f"[*] Iniciando secuencia del bucket. Objetivo: {dump_angle_deg}°, Tiempo Total: {t_total_s}s")
    
    # 2. Registrar el estado inicial para garantizar el retorno exacto
    theta_home = angulo_actual_servo 
    t_stroke_s = float(t_total_s) / 2.0
    
    # 3. Fase de Extensión (Descarga de carga útil)
    ejecutar_trayectoria_servo(dump_angle_deg, t_stroke_s)
    
    time.sleep(1) # Pausa breve para simular el tiempo de descarga
    
    # 4. Fase de Retracción (Retorno a home)
    ejecutar_trayectoria_servo(theta_home, t_stroke_s)
    
    print("[*] Secuencia completada. Bucket asegurado en posición de reposo.")

# --- Secuencia de Inicialización ---
detener_dc()
servo.duty_u16(calcular_duty(angulo_actual_servo)) 

print("\n--- Sistema Ciberfísico Listo ---")
print("Controles de la consola:")
print(" Escribe 'w' y presiona Enter para Subir")
print(" Escribe 's' y presiona Enter para Bajar")
print(" Escribe 'd' y presiona Enter para Descargar Bucket")

# 4. Bucle principal
while True:
    comando = input("\nIngresa un comando (i(subir)/k(bajar)/l(soltar arena)/set(poner angulo deseado para debug)): ").strip().lower()
    
    if comando == 'i':
        subir()
    elif comando == 'k':
        bajar()
    elif comando == 'l':
        try:
            lower_bucket(float(180), float(10))
        except ValueError:
            print("Error de casteo: El ángulo y el tiempo deben ser valores numéricos.")
    elif comando == "set":
        input_angulo = input("Ingresa el ángulo objetivo para el servo (0-180): ")
        ejecutar_trayectoria_servo(float(input_angulo), float(5))
        
    else:
        print("Comando no reconocido.")