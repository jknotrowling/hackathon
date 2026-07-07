"""
warehouse.py -- Lager-/Bestands-Logik fuer den Baustellen-Segmentation-Stack.

Reine Mengen-Sicht, komplett in Python-Dicts. Keine DB, keine Dependencies.
Haelt den SOLL-Bestand pro Objekt und gleicht ihn gegen die IST-Zaehlung des
VLM ab.

    from warehouse import Warehouse

    wh = Warehouse()                       # kommt vorbefuellt
    wh.expected_counts()                   # {'BEAM-STL-200': 6, ...}  <- Soll
    for row in wh.reconcile({"BEAM-STL-200": 4}):   # <- Ist aus dem VLM
        print(row["sku"], row["status"], row["diff"])
"""

from __future__ import annotations
from typing import Dict, List, Optional


# -----------------------------------------------------------------------------
# Beispiel-Bestand einer (Miniatur-)Baustelle. Einfach hier anpassen.
# objects[sku] = Stammdaten,  expected[sku] = Soll-Menge
# -----------------------------------------------------------------------------
DEFAULT_OBJECTS: Dict[str, dict] = {
    "BEAM-STL-200": {
        "name": "Stahltraeger IPE 200",
        "category": "Bauelement",
        "height_m": 0.20,
        "color_hex": "#8a8d8f",
        "unit": "Stueck",
    },
    "PAL-BRICK-01": {
        "name": "Ziegel-Palette",
        "category": "Baumaterial",
        "height_m": 1.05,
        "color_hex": "#a8432a",
        "unit": "Palette",
    },
    "CONT-20": {
        "name": "Baustellencontainer 20ft",
        "category": "Container",
        "height_m": 2.59,
        "color_hex": "#2f6fb0",
        "unit": "Container",
    },
    "PIPE-DN100": {
        "name": "Rohrbuendel DN100",
        "category": "Baumaterial",
        "height_m": 0.40,
        "color_hex": "#d9a441",
        "unit": "Bund",
    },
    "WIN-120x140": {
        "name": "Fensterelement 120x140",
        "category": "Bauelement",
        "height_m": 1.40,
        "color_hex": "#e8e8e8",
        "unit": "Stueck",
    },
    "INS-PANEL": {
        "name": "Daemmplatten-Paket",
        "category": "Baumaterial",
        "height_m": 0.60,
        "color_hex": "#f2e6b3",
        "unit": "Palette",
    },
    "MIX-CEM-25": {
        "name": "Zementsack 25kg",
        "category": "Baumaterial",
        "height_m": 0.70,
        "color_hex": "#6b6b6b",
        "unit": "Stueck",
    },
}

DEFAULT_EXPECTED: Dict[str, int] = {
    "BEAM-STL-200": 6,
    "PAL-BRICK-01": 4,
    "CONT-20": 1,
    "PIPE-DN100": 3,
    "WIN-120x140": 8,
    "INS-PANEL": 5,
    "MIX-CEM-25": 20,
}


class Warehouse:
    """Haelt Objekt-Stammdaten + Soll-Bestand und macht den Soll-Ist-Abgleich."""

    def __init__(
        self,
        objects: Optional[Dict[str, dict]] = None,
        expected: Optional[Dict[str, int]] = None,
    ):
        # copy(), damit die Defaults nicht versehentlich global mutiert werden
        self.objects: Dict[str, dict] = dict(objects or DEFAULT_OBJECTS)
        self.expected: Dict[str, int] = dict(expected or DEFAULT_EXPECTED)

    # -- Pflege -------------------------------------------------------------
    def add_object(self, sku: str, name: str, category: str, **fields) -> None:
        """Legt einen Objekt-Typ an / aktualisiert ihn."""
        self.objects[sku] = {"name": name, "category": category, **fields}

    def set_expected(self, sku: str, quantity: int) -> None:
        """Setzt die Soll-Menge fuer ein Objekt."""
        self.expected[sku] = quantity

    # -- Abfragen -----------------------------------------------------------
    def get(self, sku: str) -> Optional[dict]:
        """Stammdaten eines Objekts (oder None)."""
        return self.objects.get(sku)

    def expected_counts(self) -> Dict[str, int]:
        """{sku: Soll-Menge} -- das, wogegen das VLM abgeglichen wird."""
        return dict(self.expected)

    def name_of(self, sku: str) -> str:
        obj = self.objects.get(sku)
        return obj["name"] if obj else "(unbekannt)"

    # -- Herzstueck: Soll-Ist-Abgleich -------------------------------------
    def reconcile(self, counted: Dict[str, int]) -> List[dict]:
        """
        Gleicht die IST-Zaehlung des VLM gegen den SOLL-Bestand ab.

        counted: {sku: gezaehlte_menge} -- direkt aus dem VLM-Schritt.

        Rueckgabe: eine Zeile (dict) pro Objekt mit
            sku, name, expected, counted, diff, status
        status:
            ok          -> counted == expected
            fehlmenge   -> counted <  expected
            ueberschuss -> counted >  expected
            unerwartet  -> gezaehlt, aber kein Soll-Bestand hinterlegt
        """
        report: List[dict] = []
        for sku in sorted(set(self.expected) | set(counted)):
            exp = int(self.expected.get(sku, 0))
            cnt = int(counted.get(sku, 0))

            if sku not in self.expected:
                status = "unerwartet"
            elif cnt == exp:
                status = "ok"
            elif cnt < exp:
                status = "fehlmenge"
            else:
                status = "ueberschuss"

            report.append(
                {
                    "sku": sku,
                    "name": self.name_of(sku),
                    "expected": exp,
                    "counted": cnt,
                    "diff": cnt - exp,  # negativ = Fehlmenge, positiv = Ueberschuss
                    "status": status,
                }
            )
        return report


# Kleiner Selbsttest / Demo
if __name__ == "__main__":
    wh = Warehouse()

    # so koennte die VLM-Ausgabe aussehen: {sku: gezaehlte_menge}
    vlm_counts = {
        "BEAM-STL-200": 4,  # Soll 6 -> Fehlmenge
        "PAL-BRICK-01": 4,  # Soll 4 -> ok
        "PIPE-DN100": 5,  # Soll 3 -> Ueberschuss
        "SCAFFOLD-X": 2,  # kein Soll -> unerwartet
    }

    print(f"{'SKU':<15}{'Name':<26}{'Soll':>5}{'Ist':>5}{'Diff':>6}  Status")
    print("-" * 72)
    for row in wh.reconcile(vlm_counts):
        print(
            f"{row['sku']:<15}{row['name']:<26}{row['expected']:>5}"
            f"{row['counted']:>5}{row['diff']:>+6}  {row['status']}"
        )
