"""
demo_placement.py -- Beispiel-Site + Lieferungs-Sequenz + Visualisierung.

Erzeugt site_layout.json (Beispiel einer Baustelle mit Tor, Rohbau-Arbeitsbereich,
zwei Lagerzonen, Fahrweg als Sperrflaeche), platziert eine Serie ankommender
Lieferungen mit unterschiedlichen Nutzungsfrequenzen und rendert das Ergebnis.

    python demo_placement.py
"""

import json

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mp

from site_layout import SiteLayout
from placement import Placer, FixedUsage

SITE_CFG = {
    "size_m": [20.0, 15.0],
    "grid_res_m": 0.1,
    "entrances": [{"name": "tor_nord", "xy": [10.0, 15.0]}],
    "work_areas": [{"name": "rohbau", "rect": [2.0, 8.0, 6.0, 5.0]}],
    "storage_zones": [
        {"name": "lager_ost", "rect": [12.0, 2.0, 7.0, 11.0]},
        {"name": "lager_sued", "rect": [1.0, 0.5, 7.5, 4.0]},
    ],
    "forbidden": [{"name": "fahrweg", "rect": [9.0, 0.0, 2.0, 15.0]}],
}

USAGE = {"BRICK": 0.9, "GRAVEL": 0.7, "I_BEAM": 0.3, "PALLET": 0.15}

DELIVERIES = [
    ("BRICK",  (1.2, 0.8)),
    ("GRAVEL", (2.0, 2.0)),
    ("PALLET", (1.2, 0.8)),
    ("I_BEAM", (3.0, 0.5)),
    ("BRICK",  (1.2, 0.8)),
    ("PALLET", (1.2, 0.8)),
    ("GRAVEL", (1.5, 1.5)),
    ("BRICK",  (1.2, 0.8)),
]


def render(layout: SiteLayout, placer: Placer, out="placement_demo.png"):
    fig, ax = plt.subplots(figsize=(12, 9))
    ax.add_patch(mp.Rectangle((0, 0), *layout.size_m, fc="#f2f2ee", ec="black", lw=1.5))
    for z in layout.storage_zones:
        ax.add_patch(mp.Rectangle(z["rect"][:2], z["rect"][2], z["rect"][3],
                                  fc="#dcebdc", ec="green", lw=1, alpha=0.8))
        ax.annotate(z["name"], (z["rect"][0] + 0.15, z["rect"][1] + z["rect"][3] - 0.45),
                    fontsize=9, color="darkgreen")
    for z in layout.work_areas:
        ax.add_patch(mp.Rectangle(z["rect"][:2], z["rect"][2], z["rect"][3],
                                  fc="#ffe6cc", ec="darkorange", lw=1.5))
        ax.annotate("ARBEITSBEREICH " + z["name"], (z["rect"][0] + 0.15, z["rect"][1] + 0.2),
                    fontsize=9, color="darkorange", fontweight="bold")
    for z in layout.forbidden:
        ax.add_patch(mp.Rectangle(z["rect"][:2], z["rect"][2], z["rect"][3],
                                  fc="#e0e0e0", ec="grey", hatch="//", alpha=0.9))
        ax.annotate(z["name"], (z["rect"][0] + 0.15, z["rect"][1] + 7.0),
                    fontsize=8, color="grey", rotation=90)
    for e in layout.entrances:
        ax.plot(*e["xy"], marker="v", color="red", markersize=16)
        ax.annotate(e["name"], (e["xy"][0] + 0.25, e["xy"][1] - 0.55), color="red", fontsize=9)

    colors = {"BRICK": "#c0392b", "GRAVEL": "#7f8c8d", "I_BEAM": "#2c3e50", "PALLET": "#ب"}
    colors = {"BRICK": "#c0392b", "GRAVEL": "#7f8c8d", "I_BEAM": "#2c3e50", "PALLET": "#b9770e"}
    for i, p in enumerate(placer.placed, 1):
        fw, fh = p["footprint_m"]
        ax.add_patch(mp.Rectangle((p["x"] - fw / 2, p["y"] - fh / 2), fw, fh,
                                  fc=colors.get(p["sku"], "steelblue"), alpha=0.85, ec="black"))
        ax.annotate(f"{i}. {p['sku']}\n(u={p['usage']})", (p["x"], p["y"]),
                    ha="center", va="center", fontsize=7.5, color="white", fontweight="bold")

    ax.set_xlim(-0.5, layout.size_m[0] + 0.5)
    ax.set_ylim(-0.5, layout.size_m[1] + 0.5)
    ax.set_aspect("equal")
    ax.set_title("Lagerplatz-Optimierung: haeufig genutzt -> nah am Arbeitsbereich\n"
                 "(Zahl = Ankunftsreihenfolge, u = Nutzungsfrequenz)")
    ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]")
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"[demo] gerendert -> {out}")


def main():
    with open("site_layout.json", "w") as f:
        json.dump(SITE_CFG, f, indent=2)
    layout = SiteLayout.load("site_layout.json")
    placer = Placer(layout, FixedUsage(USAGE))

    for sku, footprint in DELIVERIES:
        placer.place(sku, footprint)

    placer.export_planned("planned_placements.json")
    render(layout, placer)


if __name__ == "__main__":
    main()
