"""
site_config.py -- statische Zonen-Karte der Baustelle (fuer den Placement-Planner).

Definiert per Eckpunkten, welche Flaeche was ist: Baugebiet, Umlaufweg, Lager,
Ausgangs-Korridor und Eingang. Ergebnis ist ein integer-codiertes Grid, das
deckungsgleich zum RGBDSiteMapper liegt (gleicher Ursprung unten-links,
gleiche Aufloesung), damit der Planner Belegung + Zonen einfach ueberlagern kann.

Layout (Ursprung unten-links, x -> rechts, y -> hoch), alle Masse in cm:

    y
    ^   +----------------------------------+
    |   |  LAGER |###### WEG (Umlauf) ######|
    |   |        |##+------------------+##  |
    |   |        |##|                  |##  |
    |   |        |##|    BAUGEBIET      |##  |
    |   |        |##|     40 x 60       |##  |
    |   |        |##|                  |##  |
    |   |        |##+------------------+##  |
    |   |        |###### WEG ###############|
    |   +-----------------+  +--------------+
    |                     |WEG| (Korridor)
    |                     |EIN|  <- einziger Ein-/Ausgang
    +---------------------+---+-----------------> x

Alle Kantenmasse stehen unten als Konstanten -- eine Zahl aendern, alles
reflowt automatisch.
"""

from __future__ import annotations
import numpy as np


# -----------------------------------------------------------------------------
# Legende: integer-Code pro Zelltyp
# -----------------------------------------------------------------------------
FREI = 0  # ausserhalb / ungenutzt
WEG = 1  # Fahr-/Laufweg  -> hart gesperrt fuer Ablage
EINGANG = 2  # einziger Ein-/Ausgang -> Startpunkt fuer Erreichbarkeit
LAGER = 3  # Materiallager  -> hier darf abgelegt werden
BAUGEBIET = 4  # aktive Bauzone -> "nah dran" = gut erreichbar
SPERR = 5  # manuell gesperrt (Reserve, per Default leer)

ZONE_NAMES = {
    FREI: "frei",
    WEG: "weg",
    EINGANG: "eingang",
    LAGER: "lager",
    BAUGEBIET: "baugebiet",
    SPERR: "sperr",
}

# -----------------------------------------------------------------------------
# Layout-Masse in cm  (hier anpassen)
# -----------------------------------------------------------------------------
BAU_W = 40  # Baugebiet Breite (x)
BAU_H = 60  # Baugebiet Hoehe  (y)
PATH_W = 5  # Breite des Umlaufwegs rundum
LAGER_W = 15  # Breite des Materiallagers links
EXIT_W = 10  # Breite des Ausgangs-Korridors
EXIT_H = 15  # Laenge des Korridors nach unten (bis zur Aussenkante)
MOUTH_H = 3  # Hoehe des als EINGANG markierten Korridor-Munds


def _zones_cm():
    """
    Liefert die Zonen als (code, x0, y0, x1, y1) in cm -- in FUELL-REIHENFOLGE.
    Spaeter gefuellte Zonen ueberschreiben fruehere (so entsteht z.B. der
    5cm-Ring: erst die ganze Weg-Box, dann das Baugebiet in die Mitte).
    """
    # Ring-Aussenbox (Weg + Baugebiet), Lager sitzt links daneben
    ring_x0, ring_y0 = LAGER_W, EXIT_H
    ring_x1 = ring_x0 + PATH_W + BAU_W + PATH_W
    ring_y1 = ring_y0 + PATH_W + BAU_H + PATH_W

    # Baugebiet zentral im Ring
    bau_x0, bau_y0 = ring_x0 + PATH_W, ring_y0 + PATH_W
    bau_x1, bau_y1 = bau_x0 + BAU_W, bau_y0 + BAU_H

    # Ausgangs-Korridor mittig unter dem Baugebiet, nach unten raus
    cx = (bau_x0 + bau_x1) / 2
    ex0, ex1 = cx - EXIT_W / 2, cx + EXIT_W / 2

    return [
        (LAGER, 0, ring_y0, LAGER_W, ring_y1),  # Materiallager links
        (WEG, ring_x0, ring_y0, ring_x1, ring_y1),  # ganze Weg-Box ...
        (WEG, ex0, 0, ex1, ring_y0),  # ... + Korridor
        (BAUGEBIET, bau_x0, bau_y0, bau_x1, bau_y1),  # carvt den Ring frei
        (EINGANG, ex0, 0, ex1, MOUTH_H),  # Mund = Ein-/Ausgang
    ]


def canvas_size_cm():
    """Bounding-Box der gesamten Szene in cm -> (breite, hoehe)."""
    zones = _zones_cm()
    w = max(x1 for _, _, _, x1, _ in zones)
    h = max(y1 for _, _, _, _, y1 in zones)
    return w, h


def build_zone_map(
    mapper=None, grid_res_m: float = 0.002, site_size_m: float = 1.0
) -> np.ndarray:
    """
    Rastert die Zonen aufs Grid und gibt ein uint8-Array (Codes) zurueck.

    mapper       : optional ein RGBDSiteMapper -> uebernimmt grid_res & grid_shape,
                   damit die Zonenkarte exakt zur confidence_map/elevation_map passt.
    grid_res_m   : Meter pro Zelle (nur wenn kein mapper).
    site_size_m  : Kantenlaenge des (quadratischen) Grids (nur wenn kein mapper).
    """
    if mapper is not None:
        res = mapper.grid_res
        shape = mapper.grid_shape
    else:
        res = grid_res_m
        n = int(site_size_m / grid_res_m)
        shape = (n, n)

    grid = np.full(shape, FREI, dtype=np.uint8)

    for code, x0, y0, x1, y1 in _zones_cm():
        gx0, gx1 = int((x0 / 100) / res), int((x1 / 100) / res)
        gy0, gy1 = int((y0 / 100) / res), int((y1 / 100) / res)
        # Zeile = y (Ursprung unten, passt zu origin="lower" im Mapper)
        grid[gy0:gy1, gx0:gx1] = code

    return grid


def blocked_mask(grid: np.ndarray) -> np.ndarray:
    """
    Hart gesperrte Zellen fuer die Ablage: Wege, Eingang, Sperrzonen.
    Genau die Maske, die der Planner spaeter auf 'unendliche Kosten' setzt.
    """
    return np.isin(grid, [WEG, EINGANG, SPERR])


def save_preview(
    grid: np.ndarray, path: str = "zone_map.png", grid_res_m: float = 0.002
) -> None:
    """Rendert die Zonenkarte als PNG mit cm-Achsen und Legende."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, BoundaryNorm
    import matplotlib.patches as mpatches

    colors = {
        FREI: "#f5f5f5",
        WEG: "#b8b8b8",
        EINGANG: "#39a845",
        LAGER: "#e08a2b",
        BAUGEBIET: "#2f6fb0",
        SPERR: "#c0392b",
    }
    cmap = ListedColormap([colors[c] for c in sorted(colors)])
    norm = BoundaryNorm(np.arange(-0.5, 6.5, 1), cmap.N)

    w_cm = grid.shape[1] * grid_res_m * 100
    h_cm = grid.shape[0] * grid_res_m * 100
    scene_w, scene_h = canvas_size_cm()

    fig, ax = plt.subplots(figsize=(7, 8))
    ax.imshow(
        grid,
        origin="lower",
        cmap=cmap,
        norm=norm,
        extent=[0, w_cm, 0, h_cm],
        interpolation="nearest",
    )
    ax.set_xlim(0, scene_w + 5)
    ax.set_ylim(0, scene_h + 5)
    ax.set_xlabel("x [cm]")
    ax.set_ylabel("y [cm]")
    ax.set_title("Zonen-Karte Baustelle (Soll-Layout)")
    ax.grid(True, color="white", linewidth=0.3, alpha=0.5)

    handles = [
        mpatches.Patch(color=colors[c], label=ZONE_NAMES[c]) for c in sorted(colors)
    ]
    ax.legend(handles=handles, loc="upper right", framealpha=0.9)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    grid = build_zone_map(grid_res_m=0.002, site_size_m=1.0)
    w, h = canvas_size_cm()
    print(f"Szene: {w:.0f} x {h:.0f} cm  |  Grid: {grid.shape}  @ 2mm")
    # Flaechen-Check pro Zone
    for code in sorted(ZONE_NAMES):
        cells = int((grid == code).sum())
        area = cells * (0.002 * 100) ** 2  # cm^2
        if cells:
            print(f"  {ZONE_NAMES[code]:<10} {area:8.0f} cm^2")
    save_preview(grid, "zone_map.png")
    print("Vorschau -> zone_map.png")
