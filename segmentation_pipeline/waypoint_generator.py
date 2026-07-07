import cv2
import numpy as np
import math


def generate_final_inspection_waypoints(mapper, base_desired_dist=0.3):
    """
    Berechnet optimierte 6DOF-Wegpunkte für den VLM-Scan.
    - Nutzt 'distanceTransform' für die Sicherheit.
    - Nutzt eine 'cost_map' für den perfekten Kompromiss zwischen Nähe und Sicherheit.
    - Skaliert den Abstand automatisch anhand der Objektgröße.
    """
    # 1. Karten-Grundlagen
    binary_map = (mapper.confidence_map > 0).astype(np.uint8)
    # Sicherheitszone: Alles im Umkreis von 5cm von Objekten ist 'gefährlich'
    clearance_pixels = int(0.05 / mapper.grid_res)
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (clearance_pixels * 2, clearance_pixels * 2)
    )
    danger_map = cv2.dilate(binary_map, kernel, iterations=1)

    # Distanz-Karte (wie weit ist ein freier Pixel vom nächsten Objekt weg?)
    dist_map = cv2.distanceTransform((1 - danger_map).astype(np.uint8), cv2.DIST_L2, 5)

    contours, _ = cv2.findContours(
        binary_map, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    waypoints = []

    # 2. Grid-Koordinaten-Karten für die Kostenfunktion
    h, w = mapper.grid_shape
    y_grid, x_grid = np.ogrid[:h, :w]

    for i, contour in enumerate(contours):
        if cv2.contourArea(contour) < 20:
            continue  # Rauschen ignorieren

        # Objektzentrum und Größe bestimmen
        M = cv2.moments(contour)
        target_x = (M["m10"] / M["m00"]) * mapper.grid_res
        target_y = (M["m01"] / M["m00"]) * mapper.grid_res

        # Dynamischer Abstand: Je größer das Objekt, desto weiter weg die Kamera
        obj_radius = np.sqrt(cv2.contourArea(contour) * (mapper.grid_res ** 2) / np.pi)
        optimal_dist = obj_radius * 3.0 + base_desired_dist

        # 3. Kostenfunktion auf dem gesamten Grid berechnen
        # Nähe zum Zielzentrum (x_grid * res ist die physikalische X-Koordinate)
        prox_map = np.sqrt(
            (x_grid * mapper.grid_res - target_x) ** 2
            + (y_grid * mapper.grid_res - target_y) ** 2
        )

        # Kosten = Abweichung vom Zielabstand (quadriert) - Sicherheitsabstand (skaliert)
        # Wir wollen niedrige Kosten -> nahe am Ziel, weit weg von Hindernissen
        cost_map = ((prox_map - optimal_dist) ** 2) - (dist_map * 0.2)

        # Wir verbieten Punkte auf dem Objekt selbst oder in der 'Danger Zone'
        cost_map[danger_map == 1] = 9999

        # 4. Besten Punkt extrahieren
        min_idx = np.unravel_index(np.argmin(cost_map), cost_map.shape)
        best_grid_x, best_grid_y = min_idx[1], min_idx[0]

        # 5. Wegpunkt berechnen
        arm_x = best_grid_x * mapper.grid_res
        arm_y = best_grid_y * mapper.grid_res

        # Objekt-Höhe (für Z)
        obj_mask = np.zeros_like(binary_map)
        cv2.drawContours(obj_mask, [contour], -1, 1, thickness=cv2.FILLED)
        target_z = np.max(mapper.elevation_map[obj_mask == 1])

        # Pitch fest auf 45°
        pitch_rad = math.radians(45)
        arm_z = target_z + (optimal_dist * math.sin(pitch_rad))

        waypoints.append(
            {
                "target_id": f"objekt_{i}",
                "arm_x": round(arm_x, 3),
                "arm_y": round(arm_y, 3),
                "arm_z": round(arm_z, 3),
                "cam_pitch": 45,
                # Kamera zeigt immer zum Zentrum des Objekts
                "cam_yaw": math.degrees(math.atan2(target_y - arm_y, target_x - arm_x)),
            }
        )

    return waypoints
