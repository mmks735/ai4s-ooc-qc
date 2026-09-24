"""Run the CellWatch QC demo on BBBC001 and create report-ready artefacts."""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import urllib.request
import zipfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import ndimage as ndi
from skimage.color import gray2rgb
from skimage.draw import disk
from skimage.util import img_as_float

from cellwatch_qc import analyze_image, iter_images, load_image, parse_bbbc_counts, segment_nuclei

BBBC_URL = "https://data.broadinstitute.org/bbbc/BBBC001/BBBC001_v1_images_tif.zip"
COUNT_URL = "https://data.broadinstitute.org/bbbc/BBBC001/BBBC001_v1_counts.txt"


def ensure_data(data_dir: Path) -> tuple[Path, Path]:
    root = data_dir / "BBBC001"
    root.mkdir(parents=True, exist_ok=True)
    archive = root / "BBBC001_v1_images_tif.zip"
    counts = root / "BBBC001_v1_counts.txt"
    images_dir = root / "images"
    if not archive.exists():
        print(f"Downloading {BBBC_URL}")
        urllib.request.urlretrieve(BBBC_URL, archive)
    if not counts.exists():
        print(f"Downloading {COUNT_URL}")
        urllib.request.urlretrieve(COUNT_URL, counts)
    if not images_dir.exists() or not any(images_dir.rglob("*.tif")):
        print("Extracting BBBC001 images")
        with zipfile.ZipFile(archive) as handle:
            handle.extractall(images_dir)
    return images_dir, counts


def overlay_image(gray: np.ndarray, result, title: str) -> np.ndarray:
    rgb = gray2rgb(img_as_float(gray))
    for prop in result.props:
        y, x = prop["centroid"]
        radius = max(2, int(math.sqrt(prop["area"] / math.pi)))
        rr, cc = disk((y, x), radius, shape=rgb.shape[:2])
        valid = (rr >= 0) & (rr < rgb.shape[0]) & (cc >= 0) & (cc < rgb.shape[1])
        rgb[rr[valid], cc[valid]] = (1.0, 0.25, 0.1)
    return np.clip(rgb, 0, 1)


def make_frame(gray: np.ndarray, result, score: float, name: str, subtitle: str) -> np.ndarray:
    overlay = overlay_image(gray, result, name)
    fig, axes = plt.subplots(1, 2, figsize=(10, 5), dpi=100)
    axes[0].imshow(gray, cmap="gray", vmin=0, vmax=1)
    axes[0].set_title("Input microscopy field")
    axes[0].axis("off")
    axes[1].imshow(overlay)
    axes[1].set_title(f"Detected objects: {len(result.props)} | QC score: {score:.3f}")
    axes[1].axis("off")
    fig.suptitle(f"CellWatch QC — {name}\n{subtitle}", fontsize=13)
    fig.tight_layout()
    fig.canvas.draw()
    frame = np.asarray(fig.canvas.buffer_rgba())[..., :3] / 255.0
    plt.close(fig)
    return frame


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data", type=Path)
    parser.add_argument("--output-dir", default="outputs", type=Path)
    parser.add_argument("--no-video", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    images_dir, counts_path = ensure_data(args.data_dir)
    paths = iter_images(images_dir)
    if not paths:
        raise SystemExit(f"no images found below {images_dir}")
    truth = parse_bbbc_counts(counts_path)
    rows = []
    frames = []
    for path in paths:
        gray = load_image(path)
        result, features, score = analyze_image(path)
        expected = truth.get(path.name)
        row = {
            "image": path.name,
            "ground_truth_count": expected,
            "detected_count": features["object_count"],
            "absolute_error": abs(features["object_count"] - expected) if expected is not None else None,
            "quality_score": score,
            **{key: value for key, value in features.items() if key != "object_count"},
        }
        rows.append(row)
        annotated = overlay_image(gray, result, path.name)
        plt.imsave(args.output_dir / f"annotated_{path.stem}.png", annotated)
        subtitle = "Real BBBC001 Hoechst field; circles are automated detections"
        frames.append(make_frame(gray, result, score, path.name, subtitle))
        # Add a controlled out-of-focus perturbation to demonstrate triage.
        blurred = ndi.gaussian_filter(gray, sigma=3.0)
        blurred_result, blurred_features, blurred_score = analyze_image_from_array(blurred)
        frames.append(
            make_frame(
                blurred,
                blurred_result,
                blurred_score,
                path.name,
                f"Controlled blur stress test | score change {score - blurred_score:+.3f}",
            )
        )
        print(
            f"{path.name}: detected={features['object_count']:.0f} "
            f"truth={expected} QC={score:.3f} threshold={features['otsu_threshold']:.3f}"
        )

    fieldnames = list(rows[0].keys())
    with (args.output_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    valid = [row for row in rows if row["ground_truth_count"] is not None]
    mae = float(np.mean([row["absolute_error"] for row in valid])) if valid else None
    mape = float(np.mean([row["absolute_error"] / row["ground_truth_count"] for row in valid if row["ground_truth_count"]])) if valid else None
    summary = {
        "dataset": "BBBC001v1",
        "images": len(rows),
        "count_mae": mae,
        "count_mape": mape,
        "mean_quality_score": float(np.mean([row["quality_score"] for row in rows])),
        "note": "Counts are a transparent segmentation baseline, not a biological diagnosis.",
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Compact report plots.
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), dpi=120)
    names = [row["image"].replace("AS_09125_050118150001_", "") for row in rows]
    axes[0].bar(names, [row["detected_count"] for row in rows], label="detected", color="#2a9d8f")
    axes[0].scatter(names, [row["ground_truth_count"] for row in rows], label="manual mean", color="#e76f51", zorder=3)
    axes[0].set_ylabel("nuclei / objects")
    axes[0].set_title("BBBC001 count validation")
    axes[0].tick_params(axis="x", rotation=35)
    axes[0].legend(frameon=False)
    axes[1].bar(names, [row["quality_score"] for row in rows], color="#457b9d")
    axes[1].set_ylim(0, 1)
    axes[1].set_ylabel("QC score")
    axes[1].set_title("Image triage score")
    axes[1].tick_params(axis="x", rotation=35)
    fig.tight_layout()
    fig.savefig(args.output_dir / "validation.png", dpi=150)
    plt.close(fig)

    if not args.no_video:
        import imageio.v2 as imageio
        video_path = args.output_dir / "cellwatch_demo.mp4"
        with imageio.get_writer(video_path, fps=1.5, codec="libx264", quality=7) as writer:
            for frame in frames:
                writer.append_data((np.clip(frame, 0, 1) * 255).astype(np.uint8))
        print(f"wrote {video_path}")

    print(json.dumps(summary, indent=2))
    return 0


def analyze_image_from_array(image: np.ndarray):
    result = segment_nuclei(image)
    from cellwatch_qc import image_features, quality_score
    features = image_features(image, result)
    return result, features, quality_score(features)


if __name__ == "__main__":
    raise SystemExit(main())
