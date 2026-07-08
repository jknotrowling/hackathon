"""CLIP-based image classification of blob crops (material and coarse unit-type).

A single scoring primitive -- _clip_probs -- runs CLIP over a crop against a set of
text-prompt labels and returns a softmax distribution. Both the single-view
(classify_crop) and multi-view (classify_crop_multiview) entry points are thin
wrappers over it, so there is exactly one place that talks to the model.

The heavy CLIP/torch imports are deferred into load_clip so this module (and the
CLI that imports it) load fine without the model installed; tests monkeypatch
_clip_probs and never touch the real model.
"""
import cv2
import numpy as np

MAX_VIEWS_PER_BLOB = 3      # top-N ranked views to average over in multi-view classification
MIN_CROP_DIM_PX = 20        # crops smaller than this in either dimension are too small to classify

CLIP_MODEL_NAME = "ViT-B-32"
CLIP_PRETRAINED = "laion2b_s34b_b79k"

BLOB_MATERIAL_LABELS = {
    "metal": "a photo of metal parts",
    "dirt": "a photo of dirt or earthworks",
    "gravel": "a photo of gravel or crushed stone",
    "sand": "a photo of a loose pile of sand",
}

UNIT_TYPE_LABELS = {
    "discrete": "a photo of stacked rigid objects",
    "bulk": "a photo of a loose pile of bulk material",
}

# Which discrete unit a blob is made of -- CLIP picks the shape visually, then
# arithmetic.count_units divides the volume by that shape's unit volume. This replaces
# letting the arithmetic guess the shape (which biased every blob toward "1 large unit").
SHAPE_LABELS = {
    "pallet": "a photo of a flat rectangular metal shipping pallet",
    "i_beam": "a photo of a long metal I-beam girder",
    "brick": "a photo of small rectangular bricks, can have holes",
}

_CLIP = None    # lazily-loaded (model, preprocess, tokenizer)


def load_clip():
    """Load and cache the CLIP model, preprocessing transform, and tokenizer (torch imported here)."""
    global _CLIP
    if _CLIP is None:
        import open_clip
        import torch

        model, _, preprocess = open_clip.create_model_and_transforms(
            CLIP_MODEL_NAME, pretrained=CLIP_PRETRAINED
        )
        model.eval()
        tokenizer = open_clip.get_tokenizer(CLIP_MODEL_NAME)
        _CLIP = (model, preprocess, tokenizer)
        # keep torch reference alive on the module for _clip_probs
        globals()["_torch"] = torch
    return _CLIP


def _clip_probs(crop_bgr: np.ndarray, labels: dict[str, str]) -> dict[str, float]:
    """Return CLIP's softmax probability over the label prompts for a single BGR crop."""
    from PIL import Image

    model, preprocess, tokenizer = load_clip()
    torch = globals()["_torch"]

    keys = list(labels)
    prompts = [labels[k] for k in keys]

    rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    image = preprocess(Image.fromarray(rgb)).unsqueeze(0)
    text = tokenizer(prompts)

    with torch.no_grad():
        image_features = model.encode_image(image)
        text_features = model.encode_text(text)
        image_features /= image_features.norm(dim=-1, keepdim=True)
        text_features /= text_features.norm(dim=-1, keepdim=True)
        probs = (100.0 * image_features @ text_features.T).softmax(dim=-1).squeeze(0)

    return {key: float(probs[i]) for i, key in enumerate(keys)}


def _is_classifiable(crop: np.ndarray) -> bool:
    """A crop is usable only if both dimensions are at least MIN_CROP_DIM_PX."""
    return crop is not None and crop.ndim == 3 and crop.shape[0] >= MIN_CROP_DIM_PX and crop.shape[1] >= MIN_CROP_DIM_PX


def classify_crop_multiview(
    ranked_crops: list[np.ndarray], labels: dict[str, str], max_views: int = MAX_VIEWS_PER_BLOB
) -> tuple[str, float]:
    """Average CLIP probabilities across up to max_views crops (best-first) and return (label, confidence).

    Callers pass ready-made crops in ranked order; this does no projection/cropping.
    Degenerate crops (< MIN_CROP_DIM_PX either dimension) are skipped; if none are
    usable, returns ("unknown", 0.0).
    """
    usable = [crop for crop in ranked_crops[:max_views] if _is_classifiable(crop)]
    if not usable:
        return ("unknown", 0.0)

    accumulated: dict[str, float] = {}
    for crop in usable:
        for key, prob in _clip_probs(crop, labels).items():
            accumulated[key] = accumulated.get(key, 0.0) + prob

    averaged = {key: total / len(usable) for key, total in accumulated.items()}
    best_key = max(averaged, key=averaged.get)
    return (best_key, averaged[best_key])


def classify_crop(crop: np.ndarray, labels: dict[str, str]) -> tuple[str, float]:
    """Single-view classification: the tallest/best crop only (shares the multi-view scoring code)."""
    return classify_crop_multiview([crop], labels, max_views=1)
