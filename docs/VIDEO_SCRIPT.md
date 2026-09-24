# CellWatch QC — demo video script (under 5 minutes)

**Target length:** 60–90 seconds  
**Format:** screen recording of the actual local run, with voice-over or captions

1. **0:00–0:10 — Problem**  
   “OoC workflows can quietly accept blurred or unusable fields. CellWatch QC provides an auditable first-pass quality gate before downstream image analysis.”

2. **0:10–0:25 — Input**  
   Show the BBBC001 public image source and one real Hoechst field. State that raw images are downloaded, not uploaded or redistributed by the app.

3. **0:25–0:45 — Run**  
   Show the terminal command:
   ```bash
   python run_demo.py
   ```
   Show the six detected counts, the overlay, and the generated `metrics.csv` / `summary.json`.

4. **0:45–1:05 — Stress test**  
   Show a real field beside the controlled blurred version. Explain that the focus, contrast, object and exposure features change visibly and produce a lower QC score.

5. **1:05–1:20 — Validation**  
   Show the validation plot: count MAE 32.4 objects/image and MAPE 8.71% on six BBBC001 fields. State clearly that this is a transparent baseline and not a biological or clinical claim.

6. **1:20–1:30 — Impact and limitation**  
   “The output is a review queue and an audit trail, not a diagnosis. A future OoC-specific validation set and grouped evaluation are required before operational deployment.”

7. **Final frame**  
   Show the public repository, reproduction command, MIT code license, and separate CC BY-NC-SA 3.0 terms for BBBC001 data.
