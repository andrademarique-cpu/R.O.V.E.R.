import serial
import time

# Usamos el puerto de hardware real que configuramos antes
puerto_serial = serial.Serial('/dev/ttyAMA0', baudrate=115200, timeout=0.1)

def enviar_trama_control(vel_izq, vel_der):
    """
    Empaqueta los datos y los enviar por UART.
    Para evitar chocar con nuestras cabeceras (0xFF y 0xEE), 
    limitamos el rango til de los motores de 0 a 250.
    """
    # 1. Limitar valores (Seguridad de datos)
    vel_izq = max(0, min(250, int(vel_izq)))
    vel_der = max(0, min(250, int(vel_der)))
    
    comando = 0x01 # 0x01 significa "Comando de Movimiento"
    
    # 2. Calcular Checksum (Suma de datos modulada a 8 bits)
    # Se suman solo los datos tiles, no las cabeceras.
    checksum = (comando + vel_izq + vel_der) % 256
    
    # 3. Construir la trama binaria
    trama = bytearray([
        0xFF,      # Cabecera 1 (Inicio de mensaje)
        0xEE,      # Cabecera 2 (Confirmacin de sincronizacion)
        comando,   # Tipo de mensaje
        vel_izq,   # Dato 1: Motor Izquierdo
        vel_der,   # Dato 2: Motor Derecho
        checksum   # Byte de verificacion matemtica
    ])
    
    # 4. Enviar los bytes fsicos
    puerto_serial.write(trama)

try:
    print("Iniciando transmisin al Rover...")
    while True:
        # Aqu conectaras la salida de tu algoritmo de control/joystick.
        # Por ahora, enviamos un comando fijo de prueba (ej. avanzar).
        enviar_trama_control(150, 150)
        
        # Heartbeat: Enviamos la trama 10 veces por segundo (10Hz)
        time.sleep(0.1) 
        
except KeyboardInterrupt:
    # Si presionas Ctrl+C en la Pi 4, enva un comando de parada antes de salir
    print("\nDeteniendo sistema...")
    enviar_trama_control(0, 0)
    puerto_serial.close()
