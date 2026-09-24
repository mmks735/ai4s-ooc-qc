import json
from pathlib import Path
import nbformat as nbf

root = Path(__file__).resolve().parent
nb = nbf.v4.new_notebook()
nb['metadata'] = {
    'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
    'language_info': {'name': 'python', 'version': '3.12'},
}
nb['cells'] = [
    nbf.v4.new_markdown_cell(
        '# CellWatch QC — AI4S reproducibility demo\n\n'
        '**Category:** Tool & Platform — AI + Organ-on-a-Chip (In Vitro Life Systems)  \n'
        '**Public repository:** https://github.com/mmks735/ai4s-ooc-qc\n\n'
        'This notebook runs the actual public CellWatch QC pipeline on BBBC001v1 and renders '
        'the real-data count validation plus a controlled blur stress test. The QC score is an '
        'image-usability triage heuristic, not a biological diagnosis.'
    ),
    nbf.v4.new_code_cell(
        '!pip install -q -r https://raw.githubusercontent.com/mmks735/ai4s-ooc-qc/master/requirements.txt\n'
        '!git clone -q --depth 1 https://github.com/mmks735/ai4s-ooc-qc.git\n'
        '%cd /kaggle/working/ai4s-ooc-qc\n'
        'print("repository cloned")'
    ),
    nbf.v4.new_code_cell(
        'import subprocess\n'
        'subprocess.run(["python", "run_demo.py"], check=True)\n'
        'print("demo complete")'
    ),
    nbf.v4.new_code_cell(
        'import json, pandas as pd\n'
        'from IPython.display import Image, display\n'
        'summary = json.load(open("outputs/summary.json"))\n'
        'print(json.dumps(summary, indent=2))\n'
        'display(pd.read_csv("outputs/metrics.csv"))\n'
        'display(Image(filename="outputs/validation.png"))'
    ),
    nbf.v4.new_markdown_cell(
        '## Interpretation\n\n'
        'The six-image BBBC001 result is a transparent segmentation smoke test (count MAPE 8.71% '
        'in the checked run). The separate synthetic stress test in the repository measures '
        'software response to controlled blur/exposure failures; it is not biological validation. '
        'A production OoC deployment needs a labelled, consented, multi-channel calibration set.'
    ),
]
nb['metadata']['kaggle'] = {
    'id': 'mdmahfujulkarim/cellwatch-qc-ai4s-demo',
    'title': 'CellWatch QC AI4S Demo',
    'code_file': 'cellwatch-qc-ai4s-demo.ipynb',
    'language': 'python',
    'kernel_type': 'notebook',
    'is_private': 'false',
    'enable_gpu': 'false',
    'enable_tpu': 'false',
    'enable_internet': 'true',
}
(root / 'cellwatch-qc-ai4s-demo.ipynb').write_text(nbf.writes(nb), encoding='utf-8')
print(root / 'cellwatch-qc-ai4s-demo.ipynb')
