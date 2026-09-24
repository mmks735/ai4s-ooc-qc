# CellWatch QC: an auditable image-triage system for organ-on-a-chip workflows

**Category declaration:** Tool & Platform — AI + Organ-on-a-Chip (In Vitro Life Systems)  
**Author:** Md. Mahfujul Karim (`mdmahfujulkarim`)  
**Date:** 24 September 2026  
**Code repository:** https://github.com/mmks735/ai4s-ooc-qc

## Abstract

Organ-on-a-chip experiments combine biological perturbation, time-dependent morphology, and automated imaging. A practical failure mode is not only a wrong biological conclusion; it is an unusable image being carried silently into a dataset. This report presents CellWatch QC, a local-first, CPU-only quality-control system that produces an auditable triage record from a grayscale microscopy field. The system combines a calibrated Otsu threshold, conservative connected-component segmentation, interpretable image-quality features, and a bounded heuristic score. It also includes a random-forest stress test trained only on synthetic images to verify that the software detects controlled blur and exposure failures. On six public BBBC001v1 Hoechst fields, the transparent count baseline has a mean absolute error of 32.4 objects per image and a mean absolute percentage error of 8.71% relative to the mean of two manual counts. A 900-sample synthetic held-out test produced a count MAE of 2.74 objects and focus-detection accuracy and AUROC of 1.00. These results validate the implementation and its failure-awareness; they do not constitute biological or clinical validation. The intended deployment is an early review queue for OoC image pipelines, where uncertain or high-value fields remain subject to expert review.

## 1. Problem definition and application scenario

An OoC workflow may acquire hundreds or thousands of fields per plate across brightfield, fluorescence, and reporter channels. A field can be blurred, underexposed, saturated, empty, or contain a segmentation setting that is inappropriate for the stain. If such a field is automatically accepted, downstream counts, morphology embeddings, and treatment comparisons inherit the error. Manual review of every field is expensive, while an opaque model can hide which image property caused a decision.

CellWatch QC addresses a narrower and more defensible problem than biological diagnosis: **image usability triage**. For every field, the system reports measured properties and a bounded score. An operator can inspect the overlay and the feature row, then decide whether to accept, re-image, or escalate the field. The design is intentionally compatible with a later organoid phenotype model: a downstream model can consume the same normalized images while CellWatch QC supplies an auditable quality gate.

The system is designed around four constraints:

1. **Local-first execution.** A laptop or CPU-only Kaggle kernel should be sufficient; no paid API, GPU, or private model is required.
2. **Evidence before action.** A score is accompanied by the features and segmentation threshold that produced it.
3. **Graceful degradation.** A new channel should be supported through explicit threshold configuration rather than hidden assumptions.
4. **Scientific honesty.** Synthetic stress tests, public benchmark results, and biological claims are kept separate.

## 2. Related resources and data

The challenge permits public, private, collaborative, simulated, or synthetic data when licenses and provenance are clear. For a real-data smoke test, this project uses the Broad Institute's **BBBC001v1** image set. BBBC001 contains six 512 × 512 Hoechst-channel fields from human HT29 colon-cancer cells, with two manual counts per image. The benchmark page describes the biological application as mitotic-regulator screening and cell counting.

The raw archive and count file are downloaded by `run_demo.py`; they are not committed to the repository. The BBBC page states that the images and ground truth are licensed under CC BY-NC-SA 3.0. This repository therefore redistributes code and derived aggregate metrics only. A user who wants to use the data commercially must obtain appropriate permission or select a differently licensed dataset. No patient data or private experimental data is used.

BBBC001 is not an OoC experiment and is not used to claim OoC efficacy. It is a small, public, reproducible microscopy benchmark with ground truth that lets us test the image-processing path. The appropriate next step is a labelled OoC-specific validation set, not a stronger claim from the six images.

## 3. Method

### 3.1 Image normalization and segmentation

The input is converted to a two-dimensional floating-point grayscale array in `[0, 1]`. By default, the raw intensity ordering is retained. A robust percentile normalization function is available for channels with extreme exposure, but it is not silently applied to the benchmark.

For a bright-field nucleus channel, the baseline computes Otsu's threshold after optional Gaussian smoothing. The reported default uses a `-0.01` offset relative to the raw Otsu threshold and a minimum object area of 10 pixels. This small calibration was selected on BBBC001 and is exposed as `threshold_offset`; it is not presented as a universal constant. The mask is cleaned with small-object and small-hole removal. Connected components are labelled with eight-connectivity. Each retained component records its area, centroid, eccentricity, and mean intensity.

The implementation deliberately avoids aggressive opening and closing in the default path. On BBBC001, those operations split or merged enough nuclei to increase count error. For noisier channels, a caller can opt into smoothing and recalibrate the threshold on a labelled subset. This is a conscious trade-off between a strong generic baseline and transparent domain-specific behaviour.

### 3.2 Interpretable features

For each field, the system computes:

- detected object count;
- foreground fraction;
- median and interquartile range of object area;
- variance of a Laplacian after light Gaussian smoothing (focus proxy);
- edge density from image gradients;
- intensity standard deviation (contrast proxy);
- median and mean intensity;
- saturated and dark fractions;
- the selected Otsu threshold.

The feature vector is intentionally small enough to inspect in a CSV and sufficient to explain why a field was flagged. It is not a latent embedding and does not hide a model's decision in a large parameter count.

### 3.3 QC score

The heuristic score is bounded to `[0, 1]`:

\[
Q = 0.40 f_{\mathrm{focus}} + 0.25 f_{\mathrm{contrast}} +
0.25 f_{\mathrm{objects}} + 0.10(1-p_{\mathrm{exposure}}).
\]

The focus term saturates exponentially in the Laplacian variance; the contrast term is clipped and normalized; the object term is a saturating function of count; and the exposure term penalizes high saturated or dark fractions. The score is a **QC triage score**, not a probability of abnormality. Thresholds for operational use should be selected against a labelled workflow and reviewed by domain scientists.

### 3.4 CPU-only stress-test model

To test whether the feature pipeline can recognize controlled failure, `train_synthetic_qc.py` generates 900 synthetic 64 × 64 fields with a known number of Gaussian cell-like objects, random positions, exposure changes, and either sharp or deliberately blurred objects. A random-forest regressor predicts object count and a balanced random-forest classifier predicts focused versus blurred. The models are saved with `joblib` and are not presented as biological models. The synthetic test asks a software question: can the feature pipeline separate a known perturbation from a clean synthetic field?

The model is CPU-only, uses fixed seeds, and is small enough to run in a public notebook. The score used in the demo remains the transparent heuristic; the forest is a stress-test companion and a possible starting point for a future calibrated QC model.

## 4. Implementation and reproducibility

The repository is intentionally small:

- `cellwatch_qc.py` contains segmentation, feature extraction, score computation, and BBBC count parsing.
- `run_demo.py` downloads the public archive, processes all six fields, writes `metrics.csv`, `summary.json`, overlays, a validation plot, and an MP4 demo.
- `train_synthetic_qc.py` creates the synthetic stress-test dataset and saves metrics/model artefacts.
- `tests/test_cellwatch.py` checks a positive synthetic field and an empty-field safeguard using the standard library `unittest` runner.
- `requirements.txt` pins the main CPU scientific stack.

The demo uses a fixed BBBC source URL, a fixed synthetic seed (`20260924`), and no hidden network service. A reviewer can run the commands in the README on Windows, Linux, or macOS. The raw data are downloaded rather than committed, which keeps the repository small and makes the licensing boundary visible.

## 5. Experiments and results

### 5.1 Public BBBC001 count validation

The six fields were processed with the default calibrated baseline. The ground truth is the arithmetic mean of the two manual counts supplied by BBBC001. The resulting detected counts were 330, 317, 372, 300, 415, and 231. The corresponding count MAE was **32.4 objects/image** and count MAPE was **8.71%**. The mean QC score was **0.511**.

The baseline is not perfect: it tends to merge touching nuclei and therefore under-counts some fields. This is precisely why the report exposes overlays and object areas rather than presenting only an aggregate number. A future version should compare watershed, learned instance segmentation, and channel-specific calibration on a larger OoC-specific set.

### 5.2 Synthetic stress test

On 900 generated samples, the held-out synthetic test contained 225 fields. The count model achieved MAE **2.74 objects** (normalized MAE **0.091** at the 30-object scale used in the report), and the focus classifier achieved accuracy **1.00** and AUROC **1.00**. These values indicate that the feature representation responds strongly to the controlled blur generator. They do not indicate that the model will generalize to biological stress, unusual illumination, or a different microscope.

### 5.3 Demo behaviour

`run_demo.py` creates a short video that alternates each real BBBC field with a controlled Gaussian-blurred version. The real field is shown beside the detection overlay and QC score; the stress frame makes the quality gate visible rather than asking the viewer to trust a static table. The video is a demonstration of the actual local code, not a mock-up or a pre-rendered claim.

## 6. Reliability, limitations, and risk controls

**Domain shift.** Otsu is sensitive to stain, background, and illumination. The threshold offset is calibrated on BBBC001 only. A deployment should collect a small labelled calibration set per assay and record its version.

**Instance merging.** Connected components are not a full instance-segmentation model. Watershed or a learned detector may improve crowded fields, but should be accepted only if it improves held-out error without hiding failures.

**Synthetic-to-real gap.** The random forest is trained on generated Gaussian blobs. It is a software stress test, not a biological model. The report deliberately does not use its accuracy as evidence of OoC performance.

**Quality-score semantics.** A high score does not mean normal biology, and a low score does not diagnose disease. The score should be used to route images for review, with domain experts retaining authority over uncertain fields.

**Reproducibility and privacy.** The code runs locally and does not upload images. The demo downloads only a public archive. A production OoC deployment must add access control, encryption, audit logs, retention policies, and consent/IRB review appropriate to the data.

## 7. Practical impact

The immediate value is workflow-level: a researcher can run a batch through CellWatch QC, receive a compact feature table and overlays, and spend expert time on the fields that need interpretation. The same interface can sit before a cell-painting embedding model, a viability assay, or an organoid morphology classifier. Because the output is auditable, a failed result can be traced to focus, exposure, segmentation, or a downstream model rather than being treated as a mysterious prediction.

The project is deliberately modest about scope. It does not claim to replace a biologist, infer toxicity, or establish a treatment recommendation. Its aim is to make the earliest measurable failure visible and inexpensive to catch.

## 8. Future work

1. Add a consented, multi-channel OoC calibration set with repeated fields and plate-level controls.
2. Compare connected components, watershed, and compact instance-segmentation models using grouped splits by plate and experiment.
3. Add uncertainty estimates and a three-way output (`accept`, `review`, `re-image`) selected from operating costs.
4. Validate cross-slot and cross-day focus calibration on the same microscope and objective.
5. Add a lightweight Streamlit or notebook interface for non-programmer operators while retaining the same batch CSV/JSON contract.
6. Version data provenance, thresholds, model hashes, and software commits in an append-only experiment manifest.

## 9. Reproduction commands

```bash
pip install -r requirements.txt
python run_demo.py
python train_synthetic_qc.py
python -m unittest discover -s tests -v
```

## 10. References and licenses

1. BBBC001 image and ground-truth page, Broad Institute: <https://bbbc.broadinstitute.org/BBBC001>.
2. Carpenter et al., *Genome Biology* (2006), the BBBC001 cell-counting study linked from the benchmark page.
3. BBBC001 image archive: <https://data.broadinstitute.org/bbbc/BBBC001/BBBC001_v1_images_tif.zip>.
4. BBBC001 counts: <https://data.broadinstitute.org/bbbc/BBBC001/BBBC001_v1_counts.txt>.
5. The BBBC page states CC BY-NC-SA 3.0 terms for the image set and ground truth. Code in this repository is MIT licensed; data terms remain separate.
