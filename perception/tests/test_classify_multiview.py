"""Tests for multi-view CLIP averaging. _clip_probs is monkeypatched so the real
CLIP model is never loaded."""
import numpy as np

import perception.classify_image as ci

LABELS = {"wood": "a photo of wooden blocks", "metal": "a photo of metal parts"}


def _crop(size: int = 40) -> np.ndarray:
    return np.zeros((size, size, 3), dtype=np.uint8)


def test_multiview_averages_probabilities_and_argmaxes(monkeypatch) -> None:
    """Three crops' probability vectors are averaged; the argmax of the mean is returned."""
    dists = [
        {"wood": 0.9, "metal": 0.1},
        {"wood": 0.4, "metal": 0.6},
        {"wood": 0.5, "metal": 0.5},
    ]
    calls = {"i": 0}

    def fake_clip_probs(crop, labels):
        dist = dists[calls["i"]]
        calls["i"] += 1
        return dist

    monkeypatch.setattr(ci, "_clip_probs", fake_clip_probs)

    label, confidence = ci.classify_crop_multiview([_crop(), _crop(), _crop()], LABELS)
    # mean wood = (0.9+0.4+0.5)/3 = 0.6 ; mean metal = 0.4 -> wood wins at 0.6
    assert label == "wood"
    assert abs(confidence - 0.6) < 1e-9
    assert calls["i"] == 3


def test_max_views_caps_number_of_crops_used(monkeypatch) -> None:
    """Only the first max_views crops are scored, even if more are provided."""
    calls = {"i": 0}

    def fake_clip_probs(crop, labels):
        calls["i"] += 1
        return {"wood": 1.0, "metal": 0.0}

    monkeypatch.setattr(ci, "_clip_probs", fake_clip_probs)
    ci.classify_crop_multiview([_crop() for _ in range(5)], LABELS, max_views=3)
    assert calls["i"] == 3


def test_degenerate_crops_are_skipped(monkeypatch) -> None:
    """Crops smaller than MIN_CROP_DIM_PX in either dimension are ignored."""
    monkeypatch.setattr(ci, "_clip_probs", lambda crop, labels: {"wood": 1.0, "metal": 0.0})
    # one usable, one too small -> only the usable one is scored, still classifies
    label, confidence = ci.classify_crop_multiview([_crop(40), _crop(10)], LABELS)
    assert label == "wood" and confidence == 1.0


def test_all_degenerate_returns_unknown(monkeypatch) -> None:
    """If every crop is degenerate, classification is unknown with zero confidence."""
    monkeypatch.setattr(ci, "_clip_probs", lambda crop, labels: {"wood": 1.0, "metal": 0.0})
    assert ci.classify_crop_multiview([_crop(5), _crop(10)], LABELS) == ("unknown", 0.0)


def test_classify_crop_uses_single_view(monkeypatch) -> None:
    """classify_crop delegates to the multi-view path with a single crop."""
    monkeypatch.setattr(ci, "_clip_probs", lambda crop, labels: {"wood": 0.7, "metal": 0.3})
    label, confidence = ci.classify_crop(_crop(), LABELS)
    assert label == "wood" and abs(confidence - 0.7) < 1e-9
