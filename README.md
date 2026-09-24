# CellWatch QC

**Category: Tool & Platform — AI + Organ-on-a-Chip (In Vitro Life Systems)**  
**Public code:** https://github.com/mmks735/ai4s-ooc-qc

CellWatch QC is a small, CPU-only microscopy quality-control system for organ-on-a-chip (OoC) workflows. It turns a grayscale field into an auditable record of focus, contrast, exposure, object count, and an interpretable triage score. The goal is to catch unusable or out-of-focus fields before they enter a downstream organoid / cell-painting analysis; it is not a diagnostic or treatment-response model.

## Why this matters

OoC experiments produce many fields across plates, channels, and time points. A failed field can silently become a training label, a false morphology measurement, or a misleading downstream conclusion. A lightweight, local-first QC step gives an operator a fast reason to re-image or review a field while preserving the original pixels and the exact features used for the decision.

## What the system does

1. Loads a grayscale microscopy image without changing its source data.
2. Computes a calibrated Otsu threshold (the `-0.01` offset is calibrated on the public BBBC001 Hoechst benchmark, not claimed to be universal).
3. Removes tiny objects and small holes, then reports connected-component measurements.
4. Computes interpretable features: focus (Laplacian variance), edge density, contrast, foreground fraction, object-area statistics, intensity and exposure fractions.
5. Produces a bounded `[0, 1]` QC score and annotated overlays.
6. Runs a CPU-only random-forest stress test trained on synthetic images to verify that the feature pipeline detects known blur and exposure failures. Synthetic performance is reported as pipeline validation, never as biological evidence.

## Reproducible results

The checked demo run uses six images from **BBBC001v1** (human HT29 colon-cancer cells, Hoechst channel):

| Metric | Result |
|---|---:|
| Images | 6 |
| Count MAE vs mean of two manual counts | 32.4 objects/image |
| Count MAPE | 8.71% |
| Mean QC score | 0.511 |

The baseline is intentionally transparent and under-counts some touching nuclei; it is a reproducible starting point, not a claim of state-of-the-art segmentation. A separate 900-sample synthetic stress test produced a count MAE of 2.74 objects and a focus-detection accuracy/AUC of 1.00 on its held-out synthetic test split. Those synthetic numbers test the software path; they do not establish biological validity.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# Download BBBC001, create overlays, metrics, validation plot and demo video
python run_demo.py

# Optional: train the CPU-only synthetic QC stress-test model
python train_synthetic_qc.py

# Run the dependency-light unit tests
python -m unittest discover -s tests -v
```

The raw BBBC001 images are downloaded at runtime and are intentionally not committed. The generated artefacts are written to `outputs/`:

- `metrics.csv` — per-image features, count error and QC score
- `summary.json` — aggregate validation metrics
- `validation.png` — count and QC summary plot
- `annotated_*.png` — detection overlays
- `cellwatch_demo.mp4` — short actual-system demo (under five minutes)

## Data, licensing and compliance

The demo downloads the BBBC001v1 TIFF archive and count file from the Broad Institute. The BBBC page identifies the image set as licensed under **Creative Commons Attribution-NonCommercial-ShareAlike 3.0 (CC BY-NC-SA 3.0)** and asks users to cite the BBBC collection and the Carpenter et al. study. See:

- <https://bbbc.broadinstitute.org/BBBC001>
- <https://data.broadinstitute.org/bbbc/BBBC001/BBBC001_v1_images_tif.zip>
- <https://data.broadinstitute.org/bbbc/BBBC001/BBBC001_v1_counts.txt>

No patient data, private OoC experiment, credentials, or paid service is required. The repository contains code and generated metrics, not a redistribution of the raw image archive. Users must independently verify that a dataset's terms permit their intended commercial or clinical use; this project is not a medical device.

## Interpretation and limitations

- The count is an image-processing baseline for bright, compact nuclei. It can merge touching objects, miss dim objects, and fail on different stains or illumination.
- The QC score is a triage heuristic. It is not a probability of biological abnormality and must not be used to make clinical decisions.
- The synthetic stress-test model measures software robustness under controlled perturbations, not generalization to OoC biology.
- The next scientific validation should use a labelled, consented OoC image set with channel-specific thresholds, repeated fields, plate-level leakage checks, and analyst-reviewed annotations.

## Practical impact

CellWatch QC can run on a laptop or a Kaggle CPU kernel, emits a compact CSV/JSON audit trail, and makes the reason for a review visible through the feature values and overlay. In a plate workflow it can be used as a first-pass filter, preserving expert review for uncertain or high-value fields rather than replacing it.

## License

Code is released under the MIT License in `LICENSE`. The BBBC001 data retain their own license and are not relicensed by this repository.
