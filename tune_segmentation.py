from pathlib import Path
import numpy as np
from cellwatch_qc import load_image, segment_nuclei, parse_bbbc_counts
truth=parse_bbbc_counts('data/BBBC001/BBBC001_v1_counts.txt')
paths=sorted(Path('data/BBBC001/images').rglob('*.tif'))
for off in [-.06,-.05,-.04,-.03,-.02,-.01,0,.01,.02]:
 for min_area in [10,15,20,25,30,40,50]:
  errs=[]
  for p in paths:
   im=load_image(p)
   # derive otsu on raw via default, then offset
   base=segment_nuclei(im,min_area=min_area)
   n=len(segment_nuclei(im,threshold=max(.01,min(.95,base.threshold+off)),min_area=min_area).props)
   errs.append(abs(n-truth[p.name])/truth[p.name])
  print(f'off={off:+.2f} area={min_area:2d} mape={np.mean(errs):.4f} counts={[len(segment_nuclei(load_image(p),threshold=max(.01,min(.95,segment_nuclei(load_image(p),min_area=min_area).threshold+off)),min_area=min_area).props) for p in paths]}')
