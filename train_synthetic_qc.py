"""Train and evaluate a small, CPU-only QC model on synthetic stress tests.

Synthetic data is used only to test whether the feature pipeline detects known
blur/exposure failures.  It is not presented as biological training data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from scipy import ndimage as ndi
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, mean_absolute_error, roc_auc_score
from sklearn.model_selection import train_test_split

from cellwatch_qc import image_features, quality_score, segment_nuclei


def make_image(rng: np.random.Generator, count: int, focused: bool, exposure: float) -> tuple[np.ndarray, int, int]:
    size = 64
    image = rng.normal(0.08, 0.025, (size, size)).astype(np.float32)
    yy, xx = np.mgrid[:size, :size]
    for _ in range(count):
        cy = int(rng.integers(7, size - 7))
        cx = int(rng.integers(7, size - 7))
        radius = float(rng.uniform(2.0, 4.5))
        sigma = float(rng.uniform(1.0, 1.8))
        blob = np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * sigma**2))
        image += blob.astype(np.float32) * float(rng.uniform(0.35, 0.75))
    if not focused:
        image = ndi.gaussian_filter(image, sigma=float(rng.uniform(2.0, 4.0)))
    image *= float(rng.uniform(0.75, 1.25)) * exposure
    image += rng.normal(0, float(rng.uniform(0.005, 0.035)), image.shape).astype(np.float32)
    return np.clip(image, 0, 1).astype(np.float32), count, int(focused)


def vectorize(images: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows = []
    counts = []
    focus = []
    for image, count, is_focused in images:
        segmentation = segment_nuclei(image, min_area=8, threshold_offset=-0.01)
        rows.append([image_features(image, segmentation)[key] for key in (
            "object_count", "foreground_fraction", "area_median", "area_iqr",
            "focus_laplacian", "edge_density", "contrast_std", "background_mean",
            "intensity_median", "saturated_fraction", "dark_fraction", "otsu_threshold",
        )])
        counts.append(count)
        focus.append(is_focused)
    return np.asarray(rows, dtype=np.float32), np.asarray(counts), np.asarray(focus)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="outputs", type=Path)
    parser.add_argument("--model-dir", default="models", type=Path)
    parser.add_argument("--samples", type=int, default=900)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.model_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260924)
    records = []
    for _ in range(args.samples):
        count = int(rng.integers(4, 36))
        focused = bool(rng.integers(0, 2))
        exposure = float(rng.uniform(0.65, 1.15))
        records.append(make_image(rng, count, focused, exposure))
    X, y_count, y_focus = vectorize(records)
    X_train, X_test, yc_train, yc_test, yf_train, yf_test = train_test_split(
        X, y_count, y_focus, test_size=0.25, random_state=42, stratify=y_focus
    )
    count_model = RandomForestRegressor(n_estimators=180, min_samples_leaf=3, random_state=42, n_jobs=-1)
    focus_model = RandomForestClassifier(n_estimators=180, min_samples_leaf=3, random_state=42, n_jobs=-1, class_weight="balanced")
    count_model.fit(X_train, yc_train)
    focus_model.fit(X_train, yf_train)
    pred_count = count_model.predict(X_test)
    pred_focus = focus_model.predict_proba(X_test)[:, 1]
    metrics = {
        "samples": args.samples,
        "test_samples": int(len(X_test)),
        "count_mae_units": float(mean_absolute_error(yc_test, pred_count)),
        "count_mae_normalized": float(mean_absolute_error(yc_test, pred_count) / 30.0),
        "focus_accuracy": float(accuracy_score(yf_test, pred_focus >= 0.5)),
        "focus_auc": float(roc_auc_score(yf_test, pred_focus)),
        "feature_names": [
            "object_count", "foreground_fraction", "area_median", "area_iqr",
            "focus_laplacian", "edge_density", "contrast_std", "background_mean",
            "intensity_median", "saturated_fraction", "dark_fraction", "otsu_threshold",
        ],
        "disclaimer": "Synthetic stress-test metrics are not biological validation.",
    }
    joblib.dump({"count_model": count_model, "focus_model": focus_model, "metrics": metrics}, args.model_dir / "synthetic_qc.joblib")
    (args.output_dir / "synthetic_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
