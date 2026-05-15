import depthai as dai
import cv2
import numpy as np
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

pipeline = dai.Pipeline()
cam = pipeline.create(dai.node.ColorCamera)
monoLeft = pipeline.create(dai.node.MonoCamera)
monoRight = pipeline.create(dai.node.MonoCamera)
stereo = pipeline.create(dai.node.StereoDepth)
xoutRgb = pipeline.create(dai.node.XLinkOut)
xoutDepth = pipeline.create(dai.node.XLinkOut)
xoutRgb.setStreamName("rgb")
xoutDepth.setStreamName("depth")

cam.setBoardSocket(dai.CameraBoardSocket.CAM_A)
cam.setPreviewSize(640, 400)
cam.setInterleaved(False)
cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)

monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
monoLeft.setBoardSocket(dai.CameraBoardSocket.CAM_B)
monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
monoRight.setBoardSocket(dai.CameraBoardSocket.CAM_C)

stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
stereo.setLeftRightCheck(True)
stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
stereo.setOutputSize(640, 400)


monoLeft.out.link(stereo.left)
monoRight.out.link(stereo.right)
cam.preview.link(xoutRgb.input)
stereo.depth.link(xoutDepth.input)

LIMITE_EXCAVAR    = 200
LIMITE_PRECAUCION = 600

latest_frame = None
frame_lock = threading.Lock()

def get_color(dist_mm):
    if 0 < dist_mm < LIMITE_EXCAVAR:
        return (0, 0, 255), "EXCAVAR"
    elif dist_mm < LIMITE_PRECAUCION:
        return (0, 255, 255), "PRECAUCION"
    else:
        return (0, 255, 0), "DESPEJADO"

def draw_hud(frame, dist_mm, elapsed):
    h, w = frame.shape[:2]
    cx = w // 2
    color, status = get_color(dist_mm)

    cv2.line(frame, (cx - 280, h),        (cx - 60, h//2 + 30),  color, 2)
    cv2.line(frame, (cx + 280, h),        (cx + 60, h//2 + 30),  color, 2)
    cv2.line(frame, (cx - 80,  h//2+30),  (cx + 80,  h//2+30),  (0, 255, 0),   1)
    cv2.line(frame, (cx - 160, h//2+100), (cx + 160, h//2+100), (0, 255, 255), 2)
    cv2.line(frame, (cx - 240, h-60),     (cx + 240, h-60),     (0, 0, 255),   2)
    
    cv2.putText(frame, "LEJOS", (cx+85,  h//2+28),  1, 0.8, (0,255,0),   1)
    cv2.putText(frame, "MEDIO", (cx+165, h//2+98),  1, 0.8, (0,255,255), 1)
    cv2.putText(frame, "CERCA", (cx+245, h-62),     1, 0.8, (0,0,255),   1)

    cv2.drawMarker(frame, (cx, h//2), color, cv2.MARKER_CROSS, 20, 2)

    cv2.rectangle(frame, (0, 0), (260, 75), (0, 0, 0), -1)
    dist_txt = f"{dist_mm} mm" if dist_mm > 0 else "SIN DATO"
    cv2.putText(frame, f"DIST: {dist_txt}", (10, 28), 1, 1.6, color, 2)
    cv2.putText(frame, status,              (10, 58), 1, 1.1, (255,255,255), 1)

    t = time.strftime("%M:%S", time.gmtime(elapsed))
    cv2.putText(frame, f"T {t}", (w-90, 28), 1, 1.2, (255,255,255), 1)

    return frame
class StreamHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silencia logs del servidor

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <head>
                    <title>ROVER HUD</title>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <style>
                        body { background:#000; margin:0; display:flex;
                               justify-content:center; align-items:center;
                               height:100vh; }
                        img  { width:100%; max-width:640px; }
                    </style>
                </head>
                <body>
                    <img src="/stream">
                </body>
                </html>
            """)
        elif self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while True:
                    with frame_lock:
                        if latest_frame is None:
                            continue
                        _, jpg = cv2.imencode(".jpg", latest_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n\r\n")
                    self.wfile.write(jpg.tobytes())
                    self.wfile.write(b"\r\n")
                    time.sleep(0.033)
            except:
                pass
def start_server():
    server = HTTPServer(("0.0.0.0", 8080), StreamHandler)
    server.serve_forever()

threading.Thread(target=start_server, daemon=True).start()

with dai.Device(pipeline) as device:
    qRgb   = device.getOutputQueue("rgb",   maxSize=4, blocking=False)
    qDepth = device.getOutputQueue("depth", maxSize=4, blocking=False)
    print("HUD activo - Q para salir")
    print("Stream disponible en http://<IP_RASPI>:8080")
    t0 = time.time()

    while True:
        frame      = qRgb.get().getCvFrame()
        depthFrame = qDepth.get().getFrame()

        h, w = frame.shape[:2]
        cx, cy = w//2, h//2

        roi = depthFrame[cy-5:cy+5, cx-5:cx+5]
        roi_valid = roi[roi > 0]
        dist_mm = int(np.median(roi_valid)) if roi_valid.size > 0 else 0

        frame = draw_hud(frame, dist_mm, time.time() - t0)

        with frame_lock:
            latest_frame = frame.copy()

        cv2.imshow("ROVER HUD - GRUPO 6", frame)
        if cv2.waitKey(1) == ord('q'):
            break

cv2.destroyAllWindows()
