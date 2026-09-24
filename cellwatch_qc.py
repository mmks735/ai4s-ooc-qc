"""CellWatch QC: reproducible microscopy quality-control primitives.

The module deliberately separates measured image evidence from biological
claims.  It provides deterministic segmentation and interpretable image-quality
features that can be used as an early triage step in organ-on-a-chip workflows.
It does not diagnose disease or infer treatment response.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage import filters, measure, morphology, segmentation
from skimage.feature import canny
from skimage.util import img_as_float


@dataclass(frozen=True)
class SegmentationResult:
    image: np.ndarray
    mask: np.ndarray
    labels: np.ndarray
    threshold: float
    props: tuple[dict, ...]


def load_image(path: str | Path) -> np.ndarray:
    """Load an image as a two-dimensional floating array in [0, 1]."""
    with Image.open(path) as handle:
        array = np.asarray(handle.convert("L"), dtype=np.float32) / 255.0
    if array.ndim != 2:
        raise ValueError(f"expected a grayscale image, got shape {array.shape}")
    return array


def _percentile_normalize(image: np.ndarray) -> np.ndarray:
    """Robustly scale an image without changing the ordering of intensities."""
    low, high = np.percentile(image, [1.0, 99.5])
    if high <= low:
        return np.clip(image, 0.0, 1.0)
    return np.clip((image - low) / (high - low), 0.0, 1.0)


def segment_nuclei(
    image: np.ndarray,
    *,
    threshold: float | None = None,
    min_area: int = 10,
    max_area: int = 4000,
    normalize: bool = False,
    smooth_sigma: float = 0.0,
    threshold_offset: float = -0.01,
) -> SegmentationResult:
    """Segment bright nuclear objects with a deterministic baseline.

    The default is a lightly calibrated Otsu threshold (offset ``-0.01``)
    for the BBBC001 Hoechst channel used by the demo.  For a new assay,
    expose ``threshold`` or recalibrate the offset on a small labelled subset
    rather than assuming that Otsu transfers unchanged across channels.
    """
    raw = np.asarray(image, dtype=np.float32)
    if raw.ndim != 2:
        raise ValueError("segment_nuclei expects a 2-D grayscale image")
    work = _percentile_normalize(raw) if normalize else np.clip(raw, 0.0, 1.0)
    smooth = ndi.gaussian_filter(work, sigma=smooth_sigma) if smooth_sigma > 0 else work
    base_threshold = float(filters.threshold_otsu(smooth) if threshold is None else threshold)
    selected_threshold = float(np.clip(base_threshold + threshold_offset, 0.01, 0.99)) if threshold is None else float(threshold)
    mask = smooth > selected_threshold
    # Keep the baseline conservative: BBBC001 nuclei are already separated and
    # aggressive opening/closing can split or merge valid objects.  Callers can
    # opt into smoothing for noisier channels via ``smooth_sigma``.
    mask = morphology.remove_small_objects(mask, max_size=max(0, min_area - 1))
    mask = morphology.remove_small_holes(mask, max_size=max(0, min_area - 1))
    labels = measure.label(mask, connectivity=2)
    props = []
    for prop in measure.regionprops(labels, intensity_image=work):
        area = int(prop.area)
        if area < min_area or area > max_area:
            continue
        mean_intensity = float(
            prop.intensity_mean if hasattr(prop, "intensity_mean") else prop.mean_intensity
        )
        props.append(
            {
                "label": int(prop.label),
                "area": area,
                "centroid": (float(prop.centroid[1]), float(prop.centroid[0])),
                "eccentricity": float(prop.eccentricity),
                "mean_intensity": mean_intensity,
            }
        )
    # Relabel only retained objects so feature counts match the reported list.
    if len(props) != int(labels.max()):
        keep = {row["label"] for row in props}
        remap = np.zeros_like(labels)
        next_label = 1
        for old_label in sorted(keep):
            remap[labels == old_label] = next_label
            props[next_label - 1]["label"] = next_label
            next_label += 1
        labels = remap
        mask = labels > 0
    return SegmentationResult(work, mask, labels, selected_threshold, tuple(props))


def image_features(image: np.ndarray, result: SegmentationResult | None = None) -> dict[str, float]:
    """Return interpretable focus, contrast, object and exposure features."""
    arr = np.asarray(image, dtype=np.float32)
    if arr.ndim != 2:
        raise ValueError("image_features expects a 2-D grayscale image")
    seg = result or segment_nuclei(arr)
    laplacian = ndi.laplace(ndi.gaussian_filter(arr, sigma=1.0))
    grad = np.hypot(*np.gradient(ndi.gaussian_filter(arr, sigma=1.0)))
    areas = np.asarray([row["area"] for row in seg.props], dtype=np.float32)
    count = float(len(areas))
    area_median = float(np.median(areas)) if count else 0.0
    area_iqr = float(np.percentile(areas, 75) - np.percentile(areas, 25)) if count else 0.0
    return {
        "object_count": count,
        "foreground_fraction": float(seg.mask.mean()),
        "area_median": area_median,
        "area_iqr": area_iqr,
        "focus_laplacian": float(np.var(laplacian)),
        "edge_density": float(np.mean(grad > 0.08)),
        "contrast_std": float(np.std(arr)),
        "background_mean": float(np.mean(arr)),
        "intensity_median": float(np.median(arr)),
        "saturated_fraction": float(np.mean(arr >= 0.98)),
        "dark_fraction": float(np.mean(arr <= 0.02)),
        "otsu_threshold": float(seg.threshold),
    }


def quality_score(features: dict[str, float]) -> float:
    """Map measured features to an interpretable [0, 1] triage score.

    The score is intentionally a quality-control score, not a biological
    probability.  It rewards focus, contrast and a non-empty field while
    penalising saturation and empty frames.
    """
    focus = 1.0 - np.exp(-max(0.0, features["focus_laplacian"]) / 0.0015)
    contrast = float(np.clip(features["contrast_std"] / 0.22, 0.0, 1.0))
    objects = 1.0 - np.exp(-features["object_count"] / 45.0)
    exposure_penalty = min(1.0, features["saturated_fraction"] * 8.0 + features["dark_fraction"] * 4.0)
    score = 0.40 * focus + 0.25 * contrast + 0.25 * objects + 0.10 * (1.0 - exposure_penalty)
    return float(np.clip(score, 0.0, 1.0))


def analyze_image(path: str | Path, *, normalize: bool = False) -> tuple[SegmentationResult, dict[str, float], float]:
    image = load_image(path)
    segmentation_result = segment_nuclei(image, normalize=normalize)
    features = image_features(image, segmentation_result)
    return segmentation_result, features, quality_score(features)


def parse_bbbc_counts(path: str | Path) -> dict[str, float]:
    """Parse the BBBC001 tab-delimited manual count file."""
    rows: dict[str, float] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        if len(header) < 3:
            raise ValueError("unexpected BBBC count format")
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) >= 3:
                rows[fields[0]] = float(fields[1]) if fields[1] == fields[2] else (float(fields[1]) + float(fields[2])) / 2.0
    return rows


def iter_images(folder: str | Path, patterns: Iterable[str] = ("*.tif", "*.tiff", "*.png", "*.jpg")) -> list[Path]:
    root = Path(folder)
    found: list[Path] = []
    for pattern in patterns:
        found.extend(root.rglob(pattern))
    return sorted({path for path in found if path.is_file()})
