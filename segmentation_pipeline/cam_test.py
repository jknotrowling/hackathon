import pyrealsense2 as rs
import numpy as np
import cv2
import os
import time

# Ordner für die Bilder erstellen
os.makedirs("sam_test_daten", exist_ok=True)

# Pipeline konfigurieren
pipeline = rs.pipeline()
config = rs.config()
config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

print("Starte Kamera... Bitte warten.")
pipeline.start(config)

# Kurz warten, damit die Kamera-Sensoren sich an das Licht anpassen (Auto-Exposure)
time.sleep(2)

print("Kamera bereit! Starte automatische Aufnahme...")

try:
    for i in range(5):  # Nimmt 5 Bilder auf
        frames = pipeline.wait_for_frames()
        depth_frame = frames.get_depth_frame()
        color_frame = frames.get_color_frame()

        if not depth_frame or not color_frame:
            print("Fehler beim Abrufen der Frames.")
            continue

        # Konvertieren und speichern
        depth_image = np.asanyarray(depth_frame.get_data())
        color_image = np.asanyarray(color_frame.get_data())

        color_filename = f"sam_test_daten/rgb_{i}.png"
        depth_filename = f"sam_test_daten/depth_{i}.png"

        cv2.imwrite(color_filename, color_image)
        cv2.imwrite(depth_filename, depth_image)

        print(f"[{i+1}/5] Gespeichert: {color_filename}")

        # 2 Sekunden warten bis zum nächsten Bild
        time.sleep(2)

finally:
    pipeline.stop()
    print("Aufnahme beendet. Kamera freigegeben.")
