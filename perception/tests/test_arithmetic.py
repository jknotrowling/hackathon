"""Tests for arithmetic count estimation. No hardware or model needed."""
from perception.arithmetic import count_units, estimate_shape_and_count


def test_count_units_divides_by_the_given_shape() -> None:
    """With a known shape and no fill correction, count is volume/unit rounded."""
    # 4 bricks (~64 cm^3). The classifier-free path mis-picks i_beam (64/60~=1);
    # count_units told the shape is 'brick' returns 4.
    count, error = count_units(4 * 16e-6, "brick", fill_factor=1.0)
    assert count == 4 and error < 1e-6

    assert count_units(60e-6, "i_beam", fill_factor=1.0)[0] == 1        # one I-beam
    assert count_units(3 * 108e-6, "pallet", fill_factor=1.0)[0] == 3   # three pallets


def test_packing_fill_factor_corrects_pile_overestimate() -> None:
    """A DEM volume inflated by pile voids divides down to the true count with the fill factor."""
    # 4 real bricks, but the DEM over-measured by ~43% (voids) -> ~89.6 cm^3.
    inflated = 4 * 16e-6 / 0.7
    assert count_units(inflated, "brick", fill_factor=0.7)[0] == 4


def test_count_units_is_at_least_one_for_a_discrete_blob() -> None:
    """A discrete blob smaller than a whole unit still counts as at least 1."""
    assert count_units(5e-6, "brick")[0] == 1


def test_count_units_rejects_unknown_shape_or_bad_volume() -> None:
    """Unknown shape or non-positive volume returns (0, 1.0) instead of crashing."""
    assert count_units(50e-6, "gravel") == (0, 1.0)
    assert count_units(0.0, "brick") == (0, 1.0)
    assert count_units(-1.0, "brick") == (0, 1.0)


def test_estimate_shape_and_count_fallback_recovers_exact_multiples() -> None:
    """The classifier-free fallback still recovers a clean whole-unit multiple (no fill correction)."""
    shape, count, error = estimate_shape_and_count(5 * 16e-6, fill_factor=1.0)     # 5 bricks
    assert shape == "brick" and count == 5 and error < 1e-6

    shape, count, error = estimate_shape_and_count(2 * 108e-6, fill_factor=1.0)    # 2 pallets
    assert shape == "pallet" and count == 2 and error < 1e-6


def test_estimate_shape_and_count_nonpositive_is_unknown() -> None:
    """Zero or negative volume is reported as unknown rather than crashing."""
    assert estimate_shape_and_count(0.0) == ("unknown", 0, 1.0)
    assert estimate_shape_and_count(-1.0) == ("unknown", 0, 1.0)
