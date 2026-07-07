import pandas as pd
import numpy as np
import cv2
import torch
import math
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sam2.build_sam import build_sam2
from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator


class RGBDSiteMapper:
    def __init__(self, sam2_checkpoint, sam2_config, site_size_m=2.0, grid_res_m=0.002):
        """
        Initialisiert die präzise 3D-Kartierung für den Roboterarm-Aufbau.

        site_size_m: Kantenlänge des Miniaturmodells (z.B. 2.0 Meter)
        grid_res_m: Auflösung pro Pixel auf der Karte (z.B. 0.002 Meter = 2mm)
        """
        self.grid_res = grid_res_m
        self.grid_shape = (int(site_size_m / grid_res_m), int(site_size_m / grid_res_m))

        # 1. Konfidenz-Karte (Wie oft wurde ein Pixel als Objekt erkannt)
        self.confidence_map = np.zeros(self.grid_shape, dtype=np.float32)
        # 2. Digitales Höhenmodell (DEM) der Objekte auf dem Tisch
        self.elevation_map = np.zeros(self.grid_shape, dtype=np.float32)

        # SAM2 Setup
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[*] Initialisiere SAM2 auf {self.device.type.upper()}...")

        if torch.cuda.is_available():
            torch.autocast("cuda", dtype=torch.bfloat16).__enter__()
            if torch.cuda.get_device_properties(0).major >= 8:
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True

        self.sam2_model = build_sam2(sam2_config, sam2_checkpoint, device=self.device)
        self.mask_generator = SAM2AutomaticMaskGenerator(self.sam2_model)
        print("[*] Robot-Arm RGB-D Mapping Pipeline bereit.")

    def _accumulate_object_3d(
        self,
        binary_mask,
        point_cloud_grid,
        arm_x,
        arm_y,
        arm_z,
        roll_deg,
        pitch_deg,
        yaw_deg,  # NEU: Volle 6DOF Orientierung
    ):
        """
        Transformiert die RealSense-Punktwolke über volle 6DOF-Kinematik
        in globale Koordinaten und updatet die Karten.
        """
        # 1. Maske auf das geordnete 3D-Grid anwenden
        v_coords, u_coords = np.where(binary_mask)
        if len(u_coords) == 0:
            return

        # Extrahiere die lokalen Kamerapunkte (X, Y, Z in Metern) für die Maske
        local_points = point_cloud_grid[v_coords, u_coords]

        # Filter: Ignoriere Fehlmessungen der Kamera (z < 0.05m oder unendlich)
        z_cam = local_points[:, 2]
        valid = (z_cam > 0.05) & (z_cam < 3.0) & (~np.isnan(local_points[:, 0]))
        if not np.any(valid):
            return

        # Nur gültige 3D-Punkte behalten. Shape ist jetzt (N, 3)
        valid_points = local_points[valid]

        # 2. 6DOF Transformation (Rotation)
        # Wir bauen eine Rotationsmatrix aus deinen Winkeln.
        # ACHTUNG: Die Reihenfolge ('xyz', 'zyx' etc.) hängt vom genauen
        # Koordinatensystem deines Roboterarms ab! 'xyz' ist oft Standard.
        rot_matrix = R.from_euler("xyz", [roll_deg, pitch_deg, yaw_deg], degrees=True)

        # Alle Punkte auf einen Schlag rotieren (schnelle C-Implementierung unter der Haube)
        rotated_points = rot_matrix.apply(valid_points)

        # 3. Translation (Arm-Position addieren)
        # Wenn dein Kamera-Zentrum exakt auf dem Tool Center Point (TCP) liegt:
        global_x = arm_x + rotated_points[:, 0]
        global_y = arm_y + rotated_points[:, 1]

        # WICHTIGER HINWEIS ZUR Z-ACHSE:
        # Dein alter Code machte (arm_z - z_cam). Das bedeutet, die Z-Achse deiner Kamera
        # zeigte genau in die entgegengesetzte Richtung der globalen Z-Achse (Kamera Z schaut
        # auf den Tisch, Globale Z geht vom Tisch nach oben).
        # Wenn deine neuen 6DOF-Winkel dieses umgedrehte Koordinatensystem schon
        # berücksichtigen, machst du hier einfach ein '+'. Teste das am besten zuerst:
        global_z = arm_z + rotated_points[:, 2]

        # 4. Umrechnung in Grid-Indizes
        grid_x = (global_x / self.grid_res).astype(int)
        grid_y = (global_y / self.grid_res).astype(int)

        # 5. Filter gegen Out-of-Bounds (Punkte außerhalb deiner definierten Tischgröße)
        bounds_mask = (
            (grid_x >= 0)
            & (grid_x < self.grid_shape[1])
            & (grid_y >= 0)
            & (grid_y < self.grid_shape[0])
        )

        gx = grid_x[bounds_mask]
        gy = grid_y[bounds_mask]
        gz = global_z[bounds_mask]

        if len(gx) == 0:
            return

        # 6. Karten-Akkumulation
        np.add.at(self.confidence_map, (gy, gx), 1.0)
        np.maximum.at(self.elevation_map, (gy, gx), gz)

    def process_frame(
        self,
        color_image,
        point_cloud_grid,
        arm_x,
        arm_y,
        arm_z,
        roll_deg,
        pitch_deg,
        yaw_deg,  # NEU angepasst
    ):
        masks = self.mask_generator.generate(color_image)

        for mask_data in masks:
            if mask_data["area"] < 400:
                continue

            self._accumulate_object_3d(
                binary_mask=mask_data["segmentation"],
                point_cloud_grid=point_cloud_grid,
                arm_x=arm_x,
                arm_y=arm_y,
                arm_z=arm_z,
                roll_deg=roll_deg,
                pitch_deg=pitch_deg,
                yaw_deg=yaw_deg,
            )

    def save_maps(self, prefix="miniature_site"):
        """Speichert das 2.5D Höhenmodell und die Konfidenzkarte als PNG."""
        # 1. Konfidenz-Karte
        plt.figure(figsize=(10, 10))
        plt.imshow(self.confidence_map, origin="lower", cmap="inferno")
        plt.colorbar(label="Erkennungs-Häufigkeit")
        plt.title("Objekt-Konfidenzkarte (2D)")
        plt.savefig(f"{prefix}_confidence.png", dpi=300, bbox_inches="tight")
        plt.close()

        # 2. Digitales Höhenmodell (DEM)
        plt.figure(figsize=(10, 10))
        # Maskiere Bereiche ohne Objekte, damit der leere Tisch die Farbskala nicht dominiert
        masked_elevation = np.ma.masked_where(
            self.confidence_map < 1, self.elevation_map
        )
        plt.imshow(masked_elevation, origin="lower", cmap="viridis")
        plt.colorbar(label="Reale Höhe über dem Tisch (Meter)")
        plt.title("2.5D Digitales Höhenmodell (DEM)")
        plt.savefig(f"{prefix}_elevation.png", dpi=300, bbox_inches="tight")
        plt.close()
        print(f"[*] Karten erfolgreich gespeichert: {prefix}_*.png")
