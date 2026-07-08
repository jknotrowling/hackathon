"""
placement.py -- Lagerplatz-Optimierung: wohin mit einer ankommenden Lieferung?

Kernidee (Prozessoptimierung): haeufig gebrauchte SKUs nah am Arbeitsbereich,
selten gebrauchte weiter weg. Zusatzterm: Naehe zur Einfahrt (kurzer Abladeweg).

    layout = SiteLayout.load("site_layout.json")
    usage  = FixedUsage({"BRICK": 0.9, "GRAVEL": 0.7, "I_BEAM": 0.3, "PALLET": 0.2})
    planner = Placer(layout, usage)
    planner.load_occupancy_from_unity("captures/unity_scene.json")   # optional
    spot = planner.place("BRICK", footprint_m=(1.2, 0.8))
    # -> {"sku","x","y","yaw_deg","zone","score"} und belegt die Flaeche intern

Kostenmodell pro freier Lager-Zelle:
    cost = usage(sku) * dist_to_work  +  w_ent * dist_to_entrance
Beide Terme sind ENDLICHE Distanzen -- bewusst KEIN unbeschraenkter Bonus-Term
(die Lektion aus dem Waypoint-Bug: unbeschraenkte Belohnungen ziehen in die Ecke).
Hohe usage => dist_to_work dominiert => Platz nah an der Arbeit. Niedrige usage
=> der Entfernungs-Term ist billig => weiter entfernte Plaetze werden akzeptiert,
die teuren nahen bleiben fuer die Viel-Nutzer frei.

Usage-Modell ist eine Schnittstelle: FixedUsage jetzt, LearnedUsage spaeter
(gleiche .frequency(sku)-Signatur, z.B. gespeist aus Verbrauchs-Events).
"""

from __future__ import annotations

import json
import math

import cv2
import numpy as np

from site_layout import SiteLayout


# ----------------------------------------------------------------------------
class FixedUsage:
    """Feste Nutzungsfrequenz je SKU in [0..1]. default fuer unbekannte SKUs."""

    def __init__(self, freq: dict[str, float], default: float = 0.5):
        self.freq = dict(freq)
        self.default = default

    def frequency(self, sku: str) -> float:
        return float(self.freq.get(sku, self.default))


class LearnedUsage:
    """Platzhalter fuer spaeter: gleitende Nutzungsfrequenz aus Verbrauchs-Events.
    Gleiche Schnittstelle wie FixedUsage -> im Placer austauschbar."""

    def __init__(self, halflife_events: int = 50, default: float = 0.5):
        self.counts: dict[str, float] = {}
        self.total = 0.0
        self.halflife = halflife_events
        self.default = default

    def record_consumption(self, sku: str, qty: float = 1.0):
        decay = 0.5 ** (1.0 / self.halflife)
        for k in self.counts:
            self.counts[k] *= decay
        self.total = self.total * decay + qty
        self.counts[sku] = self.counts.get(sku, 0.0) + qty

    def frequency(self, sku: str) -> float:
        if self.total <= 0:
            return self.default
        return min(1.0, self.counts.get(sku, 0.0) / self.total * 3.0)


# ----------------------------------------------------------------------------
class Placer:
    def __init__(self, layout: SiteLayout, usage, w_entrance: float = 0.25,
                 clearance_m: float = 0.3):
        self.layout = layout
        self.usage = usage
        self.w_entrance = w_entrance
        self.clearance_m = clearance_m
        self.occupied = np.zeros(layout.shape, dtype=bool)
        self.placed: list[dict] = []

    # -- Belegung -------------------------------------------------------------
    def occupy_rect(self, x_m, y_m, w_m, h_m):
        r = self.layout.res
        x0, y0 = int(x_m / r), int(y_m / r)
        x1, y1 = int(math.ceil((x_m + w_m) / r)), int(math.ceil((y_m + h_m) / r))
        H, W = self.layout.shape
        self.occupied[max(0, y0):min(H, y1), max(0, x0):min(W, x1)] = True

    def load_occupancy_from_unity(self, manifest_path: str,
                                  offset_xy: tuple[float, float] = (0.0, 0.0)):
        """Belegung aus dem unity_scene.json des Kollegen (Blobs mit Position +
        AABB). offset_xy verschiebt Tisch-Koordinaten in Site-Koordinaten."""
        with open(manifest_path) as f:
            scene = json.load(f)
        ox, oy = offset_xy
        for blob in scene.get("blobs", []):
            cx, cy = blob["position_xyz"][0] + ox, blob["position_xyz"][1] + oy
            ex, ey = blob["aabb_extent_xyz"][0], blob["aabb_extent_xyz"][1]
            self.occupy_rect(cx - ex / 2, cy - ey / 2, ex, ey)
        print(f"[placement] Belegung aus {manifest_path}: {len(scene.get('blobs', []))} Blobs")

    # -- Platzierung ----------------------------------------------------------
    def place(self, sku: str, footprint_m: tuple[float, float]) -> dict | None:
        """Findet den besten freien Lagerplatz fuer EINE Lieferung und belegt ihn.
        footprint_m = (breite, tiefe) der Lieferung in Metern. Probiert beide
        Orientierungen (0/90 Grad). None wenn nirgends Platz ist."""
        lay = self.layout
        freq = self.usage.frequency(sku)

        # Kostenkarte: endliche Terme, keine unbeschraenkten Boni.
        cost = freq * lay.dist_to_work + self.w_entrance * lay.dist_to_entrance

        best = None
        for yaw, (fw, fh) in ((0.0, footprint_m), (90.0, footprint_m[::-1])):
            ok = self._fit_mask(fw, fh)
            c = np.where(ok, cost, np.inf)
            if not np.isfinite(c).any():
                continue
            idx = np.unravel_index(np.argmin(c), c.shape)
            score = float(c[idx])
            if best is None or score < best[0]:
                best = (score, idx, yaw, fw, fh)

        if best is None:
            print(f"[placement] {sku}: KEIN freier Platz fuer {footprint_m}")
            return None

        score, (gy, gx), yaw, fw, fh = best
        # (gy,gx) ist die Zelle der linken-unteren Ecke des Footprints
        x_m, y_m = gx * lay.res, gy * lay.res
        self.occupy_rect(x_m, y_m, fw, fh)
        zone = self._zone_name(gx, gy)
        result = {
            "sku": sku,
            "x": round(x_m + fw / 2, 3), "y": round(y_m + fh / 2, 3),  # Mittelpunkt
            "yaw_deg": yaw,
            "footprint_m": [fw, fh],
            "zone": zone,
            "score": round(score, 3),
            "usage": round(freq, 2),
        }
        self.placed.append(result)
        print(f"[placement] {sku} (usage={freq:.2f}) -> ({result['x']}, {result['y']})"
              f" in '{zone}', score={score:.2f}")
        return result

    def _fit_mask(self, fw_m: float, fh_m: float) -> np.ndarray:
        """True dort, wo ein fw x fh Footprint (linke-untere Ecke in der Zelle)
        KOMPLETT in Lagerflaeche liegt und weder Belegung noch Clearance verletzt."""
        lay = self.layout
        r = lay.res
        kw = max(1, int(math.ceil(fw_m / r)))
        kh = max(1, int(math.ceil(fh_m / r)))
        # Belegung + Sicherheitsabstand aufblasen
        cl = max(1, int(self.clearance_m / r))
        kern = cv2.getStructuringElement(cv2.MORPH_RECT, (2 * cl + 1, 2 * cl + 1))
        blocked = cv2.dilate(self.occupied.astype(np.uint8), kern).astype(bool)
        free = lay.storage_mask & ~blocked
        # Erosion mit Footprint-Kernel: Zelle bleibt True nur wenn das GANZE
        # Rechteck ab dieser Ecke frei ist. (erode prueft das Fenster zentriert,
        # daher Anker auf die Ecke legen.)
        kern_fp = np.ones((kh, kw), np.uint8)
        fits = cv2.erode(free.astype(np.uint8), kern_fp, anchor=(0, 0)) > 0
        return fits

    def _zone_name(self, gx: int, gy: int) -> str:
        x, y = self.layout.cell_to_m(gx, gy)
        for z in self.layout.storage_zones:
            zx, zy, zw, zh = z["rect"]
            if zx <= x <= zx + zw and zy <= y <= zy + zh:
                return z["name"]
        return "?"

    # -- Export ---------------------------------------------------------------
    def export_planned(self, out_path: str = "planned_placements.json"):
        with open(out_path, "w") as f:
            json.dump({"planned": self.placed}, f, indent=2)
        print(f"[placement] {len(self.placed)} geplante Platzierungen -> {out_path}")
