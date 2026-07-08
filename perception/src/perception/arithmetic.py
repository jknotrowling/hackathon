"""Arithmetic count estimation for discrete-unit blobs.

Given a blob's measured (top-down DEM) volume and the unit shape it is made of, the
count is volume / unit_volume rounded to a whole number. The unit volume used is the
shape's bounding envelope (UNIT_DIMS_M), because the DEM measures the space from the
tabletop up to the top surface -- it never sees internal/side holes, so a brick counts
as its 4x2x2 envelope regardless of its two side holes.

PACKING_FILL_FACTOR corrects a systematic overestimate: the 2.5D DEM fills the void
space in a loose pile (and under jagged peaks) as if solid, inflating the volume by
~30-50% for randomly stacked blocks. The factor scales the measured volume down to the
effective solid volume before dividing. It is arrangement-dependent -- calibrate it
against a known count -- so it is a single tunable knob, not a physical constant.

count_units is the primary path: the caller passes the shape identified visually (CLIP),
so arithmetic only does the division. estimate_shape_and_count is a classifier-free
fallback that also guesses the shape, biased toward "1 of the largest unit".
"""

# (major_m, minor_m, height_m) bounding envelope of each unit; major = long axis.
UNIT_DIMS_M = {
    "pallet": (0.12, 0.06, 0.015),   # 6x12x1.5 cm
    "i_beam": (0.15, 0.02, 0.02),    # 15x2x2 cm
    "brick": (0.04, 0.02, 0.02),     # 4x2x2 cm envelope (2 side holes don't change the DEM volume)
}
UNIT_VOLUMES_CM3 = {name: a * b * c * 1_000_000 for name, (a, b, c) in UNIT_DIMS_M.items()}

PACKING_FILL_FACTOR = 0.7    # fraction of a pile's DEM volume that is actually solid unit (empirical; calibrate)


def count_units(volume_m3: float, shape: str, fill_factor: float = PACKING_FILL_FACTOR) -> tuple[int, float]:
    """Estimate how many units of a KNOWN shape make up a measured DEM volume.

    The measured volume is scaled by fill_factor to remove pile void space, then divided
    by the unit envelope. Returns (count, fit_error) where fit_error is how far the raw
    quotient is from a whole number. A discrete blob has >= 1 unit, so count is clamped to
    >= 1. Unknown shape or non-positive volume yields (0, 1.0).
    """
    if volume_m3 <= 0 or shape not in UNIT_VOLUMES_CM3:
        return (0, 1.0)
    effective_cm3 = volume_m3 * 1_000_000 * fill_factor
    raw_count = effective_cm3 / UNIT_VOLUMES_CM3[shape]
    return (max(1, round(raw_count)), abs(raw_count - round(raw_count)))


def estimate_shape_and_count(volume_m3: float, fill_factor: float = PACKING_FILL_FACTOR) -> tuple[str, int, float]:
    """Classifier-free fallback: guess both the shape and count from volume alone.

    Picks the unit shape whose (fill-corrected) volume divides closest to a whole number.
    Biased toward "1 of the largest unit" for mid-range volumes -- prefer count_units with
    a visually-identified shape. volume_m3 <= 0 yields ("unknown", 0, 1.0).
    """
    if volume_m3 <= 0:
        return ("unknown", 0, 1.0)

    effective_cm3 = volume_m3 * 1_000_000 * fill_factor
    best_name = "unknown"
    best_count = 0
    best_error = float("inf")
    for name, unit_volume_cm3 in UNIT_VOLUMES_CM3.items():
        raw_count = effective_cm3 / unit_volume_cm3
        error = abs(raw_count - round(raw_count))
        if error < best_error:
            best_name, best_count, best_error = name, round(raw_count), error

    return (best_name, best_count, best_error)
