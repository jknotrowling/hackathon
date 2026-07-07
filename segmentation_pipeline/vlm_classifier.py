"""
vlm_classifier.py -- VLM-Stufe der Pipeline: Bild-Crop -> sku.

Bekommt pro Waypoint einen Crop (klares Objekt in der Mitte) und ordnet ihn
EINEM Eintrag aus dem Warehouse-Katalog zu. NUR Klassifikation -- die Stueckzahl
kommt spaeter aus der Belegungs-/Hoehen-Karte, nicht aus dem VLM.

Design:
  * OpenAI wird NUR hier importiert (lazy). Der Rest des Stacks kennt kein OpenAI.
    -> spaeter auf ein lokales Modell wechseln = nur diese Datei tauschen.
  * Erzwungenes JSON (json_schema, sku als Enum) -> keine erfundenen SKUs, kein Parsing-Elend.
  * Trocken-Modus (dry_run=True) -> gibt Dummy-JSON zurueck, 0 API-Kosten,
    ideal zum Justieren der Downstream-Logik.

Nutzung:
    from vlm_classifier import VLMClassifier

    clf = VLMClassifier(model="gpt-4o-mini", dry_run=False)
    result = clf.classify(crop_rgb, warehouse.objects)
    # -> {"sku": "PAL-BRICK-01", "confidence": 0.93, "reasoning": "...", "dry_run": False}
"""

from __future__ import annotations

import os
import io
import json
import base64
from typing import Dict, Optional, Union

import numpy as np
from PIL import Image


ImageInput = Union[np.ndarray, "Image.Image", str]

# Fallback-Label, wenn kein Katalog-Eintrag passt
UNKNOWN = "UNKNOWN"


class VLMClassifier:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        dry_run: bool = False,
        api_key: Optional[str] = None,
        max_edge: int = 768,
        detail: str = "low",
    ):
        """
        model    : OpenAI-Vision-Modell (gpt-4o-mini / gpt-4.1-mini sind guenstig).
        dry_run  : True -> kein API-Call, Dummy-Antwort. Zum Testen ohne Kosten.
        api_key  : sonst aus Umgebungsvariable OPENAI_API_KEY.
        max_edge : Crops werden vor dem Senden auf diese lange Kante skaliert
                   (kleiner = billiger; fuer ein zentriertes Objekt reicht das locker).
        detail   : "low" spart Tokens massiv (fixer Low-Res-Pfad). "high"/"auto" moeglich.
        """
        self.model = model
        self.dry_run = dry_run
        self.max_edge = max_edge
        self.detail = detail
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._client = None  # lazy, damit dry_run ganz ohne openai laeuft

    # -------------------------------------------------------------------------
    # Oeffentliche API
    # -------------------------------------------------------------------------
    def classify(self, image: ImageInput, sku_catalog: Dict[str, dict]) -> dict:
        """
        Klassifiziert EIN Objekt in 'image' gegen die SKUs aus 'sku_catalog'.

        sku_catalog: {sku: {name, category, color_hex, ...}}  (z.B. warehouse.objects)

        Rueckgabe: {"sku", "confidence", "reasoning", "dry_run"}.
        Bei Fehler/keinem Treffer: sku=UNKNOWN, confidence=0.0.
        """
        skus = list(sku_catalog.keys())
        if not skus:
            raise ValueError("Leerer SKU-Katalog.")

        if self.dry_run:
            return {
                "sku": skus[0],
                "confidence": 1.0,
                "reasoning": "dry-run (kein API-Call)",
                "dry_run": True,
            }

        try:
            img_b64 = self._encode_image(image)
            system_prompt, user_text = self._build_prompt(sku_catalog)
            schema = self._response_schema(skus)
            data = self._call_api(system_prompt, user_text, img_b64, schema)
            data.setdefault("reasoning", "")
            data["dry_run"] = False
            return data
        except Exception as exc:  # ein fehlgeschlagener Call darf den Scan nicht killen
            return {
                "sku": UNKNOWN,
                "confidence": 0.0,
                "reasoning": f"Fehler: {exc}",
                "dry_run": False,
            }

    # -------------------------------------------------------------------------
    # Bild -> base64-JPEG (skaliert)
    # -------------------------------------------------------------------------
    def _encode_image(self, image: ImageInput) -> str:
        if isinstance(image, str):
            img = Image.open(image)
        elif isinstance(image, np.ndarray):
            arr = image
            if arr.dtype != np.uint8:  # z.B. float 0..1 -> 0..255
                arr = np.clip(arr * 255 if arr.max() <= 1.0 else arr, 0, 255).astype(
                    np.uint8
                )
            img = Image.fromarray(arr)
        elif isinstance(image, Image.Image):
            img = image
        else:
            raise TypeError(f"Nicht unterstuetzter Bildtyp: {type(image)}")

        img = img.convert("RGB")

        # Auf max_edge herunterskalieren (Seitenverhaeltnis halten)
        w, h = img.size
        scale = self.max_edge / max(w, h)
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    # -------------------------------------------------------------------------
    # Prompt-Bau: geschlossene Auswahl mit Beschreibung
    # -------------------------------------------------------------------------
    def _build_prompt(self, sku_catalog: Dict[str, dict]) -> tuple[str, str]:
        lines = []
        for sku, meta in sku_catalog.items():
            name = meta.get("name", sku)
            cat = meta.get("category", "")
            color = meta.get("color_hex", "")
            desc = meta.get("description", "")
            extra = " | ".join(x for x in (cat, desc, color) if x)
            lines.append(f"- {sku}: {name}" + (f" ({extra})" if extra else ""))
        catalog_block = "\n".join(lines)

        system_prompt = (
            "Du bist ein Klassifikator fuer Baustellen-Logistik. Im Bild ist genau EIN "
            "Objekt zentral zu sehen. Ordne es exakt einem SKU aus der vorgegebenen Liste "
            "zu. Passt keiner, antworte mit 'UNKNOWN'. "
            "ZAEHLE NICHT und schaetze keine Mengen oder Masse -- nur die Objektart. "
            "Halte 'reasoning' auf einen kurzen Satz."
        )
        user_text = (
            "Moegliche Objekte:\n"
            f"{catalog_block}\n\n"
            "Welches Objekt ist im Bild zentral zu sehen?"
        )
        return system_prompt, user_text

    # -------------------------------------------------------------------------
    # JSON-Schema (Enum erzwingt gueltige SKUs)
    # -------------------------------------------------------------------------
    def _response_schema(self, skus: list[str]) -> dict:
        return {
            "name": "object_classification",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "enum": skus + [UNKNOWN]},
                    "confidence": {"type": "number"},
                    "reasoning": {"type": "string"},
                },
                "required": ["sku", "confidence", "reasoning"],
                "additionalProperties": False,
            },
        }

    # -------------------------------------------------------------------------
    # Der eigentliche API-Call (einzige Stelle mit OpenAI)
    # -------------------------------------------------------------------------
    def _call_api(
        self, system_prompt: str, user_text: str, img_b64: str, schema: dict
    ) -> dict:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    "Kein OPENAI_API_KEY gefunden (Umgebungsvariable setzen oder "
                    "api_key uebergeben) -- oder dry_run=True nutzen."
                )
            from openai import OpenAI  # lazy import

            self._client = OpenAI(api_key=self._api_key)

        resp = self._client.chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=300,
            response_format={"type": "json_schema", "json_schema": schema},
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_b64}",
                                "detail": self.detail,
                            },
                        },
                    ],
                },
            ],
        )
        return json.loads(resp.choices[0].message.content)


# -----------------------------------------------------------------------------
# Kleine Demo: Trocken-Modus + Bildaufbereitung ohne echten Call
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Beispiel-Katalog im Format von warehouse.objects
    catalog = {
        "BEAM-STL-200": {
            "name": "Stahltraeger IPE 200",
            "category": "Bauelement",
            "color_hex": "#8a8d8f",
        },
        "PAL-BRICK-01": {
            "name": "Ziegel-Palette",
            "category": "Baumaterial",
            "color_hex": "#a8432a",
        },
        "CONT-20": {
            "name": "Baustellencontainer 20ft",
            "category": "Container",
            "color_hex": "#2f6fb0",
        },
    }

    # ein synthetischer RGB-Crop (rot) -- steht stellvertretend fuer einen Waypoint-Crop
    dummy_crop = np.full((900, 1200, 3), (168, 67, 42), dtype=np.uint8)

    clf = VLMClassifier(dry_run=True)
    result = clf.classify(dummy_crop, catalog)
    print("Trocken-Modus Ergebnis:", result)

    # Prompt- und Schema-Aufbau gegenchecken (kein API-Call)
    sysp, usr = clf._build_prompt(catalog)
    print("\n--- System-Prompt ---\n" + sysp)
    print("\n--- User-Text ---\n" + usr)
    print("\n--- SKU-Enum ---")
    print(clf._response_schema(list(catalog))["schema"]["properties"]["sku"]["enum"])
