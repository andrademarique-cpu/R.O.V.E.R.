import socket
import struct
import time
import threading
from inputs import get_gamepad

# --- CONFIGURACIÓN ---
IP_RASPBERRY = "10.198.28.10"
PUERTO = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

estado = {
    "ejes": [0.0, 0.0, 0.0, 0.0], # X, Y, RX, RY
    "gatillos": [0.0, 0.0],       # L, R
    "botones": 0                  # Máscara de bits para 16 botones
}

# Se agregaron los botones L3 y R3 (clic en los joysticks)
# NOTA: BTN_TL es LB (Left Bumper) y BTN_TR es RB (Right Bumper)
BTN_MAP = {
    "BTN_SOUTH": 0, "BTN_EAST": 1, "BTN_WEST": 2, "BTN_NORTH": 3,
    "BTN_TL": 4, "BTN_TR": 5, "BTN_SELECT": 6, "BTN_START": 7,
    "BTN_THUMBL": 8, "BTN_THUMBR": 9
}

def frenado_emergencia():
    """Pone todos los valores a 0 para detener el Rover instantáneamente"""
    estado["ejes"] = [0.0, 0.0, 0.0, 0.0]
    estado["gatillos"] = [0.0, 0.0]
    estado["botones"] = 0

def leer_control():
    # Bucle infinito externo: Mantiene vivo el hilo aunque el control desaparezca
    while True:
        try:
            # get_gamepad() bloquea hasta que hay un evento. 
            # Si se desconecta, lanza una excepción (UnpluggedError)
            eventos = get_gamepad()
            for e in eventos:
                # Ejes principales
                if e.code == "ABS_X": estado["ejes"][0] = e.state / 255
                elif e.code == "ABS_Y": estado["ejes"][1] = -e.state / 255
                elif e.code == "ABS_RX": estado["ejes"][2] = e.state / 255
                elif e.code == "ABS_RY": estado["ejes"][3] = -e.state / 255
                
                # Gatillos
                elif e.code == "ABS_Z": estado["gatillos"][0] = e.state / 255
                elif e.code == "ABS_RZ": estado["gatillos"][1] = e.state / 255
                
                # Flechas (D-Pad) - Se mapean a los bits 10, 11, 12 y 13
                elif e.code == "ABS_HAT0Y":
                    if e.state == -1: estado["botones"] |= (1 << 10)   # Arriba
                    else: estado["botones"] &= ~(1 << 10)
                    if e.state == 1: estado["botones"] |= (1 << 11)    # Abajo
                    else: estado["botones"] &= ~(1 << 11)
                    
                elif e.code == "ABS_HAT0X":
                    if e.state == -1: estado["botones"] |= (1 << 12)   # Izquierda
                    else: estado["botones"] &= ~(1 << 12)
                    if e.state == 1: estado["botones"] |= (1 << 13)    # Derecha
                    else: estado["botones"] &= ~(1 << 13)

                # Botones estándar
                elif e.code in BTN_MAP:
                    bit = BTN_MAP[e.code]
                    if e.state: estado["botones"] |= (1 << bit)
                    else: estado["botones"] &= ~(1 << bit)
                    
        except Exception as ex:
            # --- PROTOCOLO DE DESCONEXIÓN ---
            print("\n[!] ALERTA: Control desconectado. Aplicando freno de emergencia.")
            frenado_emergencia() # 1. Detener el rover
            
            # 2. Esperar un segundo antes de intentar buscar el control de nuevo
            time.sleep(1) 
            print("Buscando control...")

# Iniciar hilo de lectura
threading.Thread(target=leer_control, daemon=True).start()

formato_udp = struct.Struct('ffffffH')

print("Estación Base iniciada. Transmitiendo datos binarios a la Raspberry...")
try:
    while True:
        # Empaquetamos el estado actual. Si se desconectó, frenado_emergencia() 
        # ya habrá puesto todo esto en 0, enviando una trama de detención segura.
        paquete_binario = formato_udp.pack(
            estado["ejes"][0], estado["ejes"][1], 
            estado["ejes"][2], estado["ejes"][3],
            estado["gatillos"][0], estado["gatillos"][1],
            estado["botones"]
        )
        print(estado["ejes"][0], estado["ejes"][1], 
            estado["ejes"][2], estado["ejes"][3],
            estado["gatillos"][0], estado["gatillos"][1],
            estado["botones"]) # Debug para ver los bits de los botones
        sock.sendto(paquete_binario, (IP_RASPBERRY, PUERTO))
        time.sleep(0.02) # Transmitiendo a 50Hz
        
except KeyboardInterrupt:
    print("\nTransmisión detenida por el usuario.")
finally:
    # Freno final al cerrar el programa
    paquete_freno = formato_udp.pack(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)
    sock.sendto(paquete_freno, (IP_RASPBERRY, PUERTO))
    sock.close()