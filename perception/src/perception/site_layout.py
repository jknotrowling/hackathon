"""
site_layout.py -- statisches Baustellen-Layout aus einer Konfig-Datei.

Der Nutzer definiert EINMAL (JSON): Site-Groesse, Einfahrt(en), aktive
Arbeitsbereiche, Lagerzonen, Sperrflaechen (Wege, Kranbahn). Daraus wird ein
Raster gebaut, auf dem die Platzierung optimiert.

Alle Angaben in Metern, Ursprung unten-links. Rechtecke als [x, y, breite, hoehe].

Beispiel-Konfig (site_layout.json):
{
  "size_m": [20.0, 15.0],
  "grid_res_m": 0.1,
  "entrances": [ {"name": "tor_nord", "xy": [10.0, 15.0]} ],
  "work_areas": [ {"name": "rohbau", "rect": [2.0, 8.0, 6.0, 5.0]} ],
  "storage_zones": [ {"name": "lager_ost", "rect": [12.0, 2.0, 7.0, 10.0]},
                      {"name": "lager_sued", "rect": [2.0, 0.5, 8.0, 3.0]} ],
  "forbidden": [ {"name": "fahrweg", "rect": [9.0, 0.0, 2.0, 15.0]} ]
}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np


@dataclass
class SiteLayout:
    size_m: tuple[float, float]
    res: float
    entrances: list[dict]
    work_areas: list[dict]
    storage_zones: list[dict]
    forbidden: list[dict]
    # abgeleitet:
    shape: tuple[int, int] = field(init=False)          # (H, W) Zellen
    storage_mask: np.ndarray = field(init=False)        # True = darf gelagert werden
    dist_to_work: np.ndarray = field(init=False)        # Meter, pro Zelle
    dist_to_entrance: np.ndarray = field(init=False)    # Meter, pro Zelle

    def __post_init__(self):
        W = int(round(self.size_m[0] / self.res))
        H = int(round(self.size_m[1] / self.res))
        self.shape = (H, W)

        def rect_mask(rect):
            x, y, w, h = rect
            m = np.zeros(self.shape, dtype=bool)
            x0, y0 = int(x / self.res), int(y / self.res)
            x1, y1 = int((x + w) / self.res), int((y + h) / self.res)
            m[max(0, y0):min(H, y1), max(0, x0):min(W, x1)] = True
            return m

        storage = np.zeros(self.shape, dtype=bool)
        for z in self.storage_zones:
            storage |= rect_mask(z["rect"])
        for z in self.forbidden:
            storage &= ~rect_mask(z["rect"])
        for z in self.work_areas:                    # nicht IM Arbeitsbereich lagern
            storage &= ~rect_mask(z["rect"])
        self.storage_mask = storage

        # Distanzfelder (euklidisch zur naechsten Ziel-Zelle), in Metern.
        self.dist_to_work = self._dist_field(
            np.any([rect_mask(z["rect"]) for z in self.work_areas], axis=0)
            if self.work_areas else np.zeros(self.shape, bool)
        )
        ent = np.zeros(self.shape, dtype=bool)
        for e in self.entrances:
            gx, gy = int(e["xy"][0] / self.res), int(e["xy"][1] / self.res)
            ent[max(0, min(H - 1, gy)), max(0, min(W - 1, gx))] = True
        self.dist_to_entrance = self._dist_field(ent)

    def _dist_field(self, targets: np.ndarray) -> np.ndarray:
        """Euklidische Distanz jeder Zelle zur naechsten True-Zelle, via cv2."""
        import cv2
        if not targets.any():
            return np.zeros(self.shape, dtype=np.float32)
        # distanceTransform misst Abstand zu 0-Pixeln -> Ziel invertieren
        inv = (~targets).astype(np.uint8)
        d = cv2.distanceTransform(inv, cv2.DIST_L2, 5)
        return d * self.res

    # ------------------------------------------------------------------
    @classmethod
    def load(cls, path: str) -> "SiteLayout":
        with open(path) as f:
            cfg = json.load(f)
        return cls(
            size_m=tuple(cfg["size_m"]),
            res=float(cfg.get("grid_res_m", 0.1)),
            entrances=cfg.get("entrances", []),
            work_areas=cfg.get("work_areas", []),
            storage_zones=cfg.get("storage_zones", []),
            forbidden=cfg.get("forbidden", []),
        )

    def cell_to_m(self, gx, gy):
        return ((gx + 0.5) * self.res, (gy + 0.5) * self.res)
