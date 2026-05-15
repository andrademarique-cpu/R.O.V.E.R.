import socket
import struct
import time
import threading
from inputs import get_gamepad

# --- CONFIGURACIÓN ---
IP_RASPBERRY = "10.22.214.10"
PUERTO = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

estado = {
    "ejes": [0.0, 0.0, 0.0, 0.0],
    "gatillos": [0.0, 0.0],
    "botones": 0
}

# --- AJUSTA ESTOS NOMBRES si tu control genérico usa códigos distintos ---
# Corre el script una vez y presiona LB/RB para ver qué código aparece en consola
BTN_LB = "BTN_TL"   # Cambia si ves otro código al presionar LB
BTN_RB = "BTN_TR"   # Cambia si ves otro código al presionar RB

BTN_MAP = {
    "BTN_SOUTH": 0, "BTN_EAST": 1, "BTN_WEST": 2, "BTN_NORTH": 3,
    BTN_LB: 4, BTN_RB: 5, "BTN_SELECT": 6, "BTN_START": 7,
    "BTN_THUMBL": 8, "BTN_THUMBR": 9
}

def frenado_emergencia():
    estado["ejes"] = [0.0, 0.0, 0.0, 0.0]
    estado["gatillos"] = [0.0, 0.0]
    estado["botones"] = 0

def leer_control():
    while True:
        try:
            eventos = get_gamepad()
            for e in eventos:
                print(f"[DEBUG] tipo='{e.ev_type}' code='{e.code}' state={e.state}")
                # --- DEBUG: imprime cualquier evento desconocido ---
                # Útil para controles genéricos con nombres distintos
                if e.ev_type == "Key" and e.code not in BTN_MAP:
                    print(f"[DEBUG] Botón desconocido: code='{e.code}' state={e.state}")
                if e.ev_type == "Absolute" and e.code not in (
                    "ABS_X","ABS_Y","ABS_RX","ABS_RY","ABS_Z","ABS_RZ",
                    "ABS_HAT0X","ABS_HAT0Y"
                ):
                    print(f"[DEBUG] Eje desconocido: code='{e.code}' state={e.state}")

                # Ejes - rango 0-255 centrado en 127 para controles genéricos
                # Si tu control reporta -32768 a 32767 cambia / 255 por / 32767
                if e.code == "ABS_X":   estado["ejes"][0] = (e.state - 127) / 128.0
                elif e.code == "ABS_Y": estado["ejes"][1] = -((e.state - 127) / 128.0)
                elif e.code == "ABS_RX": estado["ejes"][2] = (e.state - 127) / 128.0
                elif e.code == "ABS_RY": estado["ejes"][3] = -((e.state - 127) / 128.0)

                # Gatillos
                elif e.code == "ABS_Z":  estado["gatillos"][0] = e.state / 255.0
                elif e.code == "ABS_RZ": estado["gatillos"][1] = e.state / 255.0

                # D-Pad
                elif e.code == "ABS_HAT0Y":
                    if e.state == -1: estado["botones"] |= (1 << 10)
                    else:             estado["botones"] &= ~(1 << 10)
                    if e.state == 1:  estado["botones"] |= (1 << 11)
                    else:             estado["botones"] &= ~(1 << 11)
                elif e.code == "ABS_HAT0X":
                    if e.state == -1: estado["botones"] |= (1 << 12)
                    else:             estado["botones"] &= ~(1 << 12)
                    if e.state == 1:  estado["botones"] |= (1 << 13)
                    else:             estado["botones"] &= ~(1 << 13)

                # Botones estándar
                elif e.code in BTN_MAP:
                    bit = BTN_MAP[e.code]
                    if e.state: estado["botones"] |= (1 << bit)
                    else:       estado["botones"] &= ~(1 << bit)

        except Exception as ex:
            print(f"\n[!] ALERTA: Control desconectado ({ex}). Aplicando freno de emergencia.")
            frenado_emergencia()
            time.sleep(1)
            print("Buscando control...")

threading.Thread(target=leer_control, daemon=True).start()

formato_udp = struct.Struct('ffffffH')

print("Estación Base iniciada. Transmitiendo a la Raspberry...")
print(f"[INFO] LB mapeado a '{BTN_LB}' | RB mapeado a '{BTN_RB}'")
print("[INFO] Si LB/RB no funcionan, revisa los mensajes [DEBUG] al presionarlos\n")

try:
    while True:
        paquete_binario = formato_udp.pack(
            estado["ejes"][0], estado["ejes"][1],
            estado["ejes"][2], estado["ejes"][3],
            estado["gatillos"][0], estado["gatillos"][1],
            estado["botones"]
        )
        sock.sendto(paquete_binario, (IP_RASPBERRY, PUERTO))
        time.sleep(0.02)

except KeyboardInterrupt:
    print("\nTransmisión detenida.")
finally:
    paquete_freno = formato_udp.pack(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)
    sock.sendto(paquete_freno, (IP_RASPBERRY, PUERTO))
    sock.close()