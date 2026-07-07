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
        self, binary_mask, point_cloud_grid, arm_x, arm_y, arm_z, yaw_deg
    ):
        """
        Nimmt das geordnete 3D-Grid der RealSense, transformiert die maskierten Punkte
        über die Kinematik des Roboterarms in globale Koordinaten und updatet die Karten.
        """
        # 1. Maske auf das geordnete 3D-Grid anwenden
        v_coords, u_coords = np.where(binary_mask)
        if len(u_coords) == 0:
            return

        # Extrahiere die lokalen Kamerapunkte (X, Y, Z in Metern) für die Maske
        local_points = point_cloud_grid[v_coords, u_coords]

        x_cam = local_points[:, 0]
        y_cam = local_points[:, 1]
        z_cam = local_points[:, 2]

        # Filter: Ignoriere Fehlmessungen der Kamera (0.0 oder unendlich)
        valid = (z_cam > 0.05) & (z_cam < 3.0) & (~np.isnan(x_cam))
        if not np.any(valid):
            return

        x_cam, y_cam, z_cam = x_cam[valid], y_cam[valid], z_cam[valid]

        # 2. Globale Höhe (Z) berechnen
        # Da die Kamera nach unten blickt, ist die Höhe des Objekts auf dem Tisch:
        # Arm-Höhe minus Abstand von der Linse zum Objekt
        global_z = arm_z - z_cam

        # 3. Globale X/Y Koordinaten berechnen (Rotation durch Arm-Yaw + Translation)
        yaw_rad = math.radians(yaw_deg)
        cos_y, sin_y = math.cos(yaw_rad), math.sin(yaw_rad)

        rot_x = x_cam * cos_y - y_cam * sin_y
        rot_y = x_cam * sin_y + y_cam * cos_y

        global_x = arm_x + rot_x
        global_y = arm_y + rot_y

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

        gx, gy, gz = grid_x[bounds_mask], grid_y[bounds_mask], global_z[bounds_mask]
        if len(gx) == 0:
            return

        # 6. Karten-Akkumulation
        # Konfidenz hochzählen
        np.add.at(self.confidence_map, (gy, gx), 1.0)

        # Maximale Höhe speichern (damit Rauschen oder Überlappungen die reale Höhe nicht verfälschen)
        np.maximum.at(self.elevation_map, (gy, gx), gz)

    def process_frame(
        self, color_image, point_cloud_grid, arm_x, arm_y, arm_z, yaw_deg
    ):
        """
        Verarbeitet ein einzelnes Live-Frame aus deinem Roboter-Skript.

        color_image: NumPy Array (RGB, Standard-Bild)
        point_cloud_grid: NumPy Array Shape (H, W, 3) mit geordneten X,Y,Z-Werten in Metern
        """
        # Segmente finden
        masks = self.mask_generator.generate(color_image)

        for mask_data in masks:
            # Kleine Rausch-Masken (kleiner als 400 Pixel) direkt aussortieren
            if mask_data["area"] < 400:
                continue

            self._accumulate_object_3d(
                binary_mask=mask_data["segmentation"],
                point_cloud_grid=point_cloud_grid,
                arm_x=arm_x,
                arm_y=arm_y,
                arm_z=arm_z,
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
