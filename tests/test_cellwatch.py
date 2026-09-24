import unittest

import numpy as np

from cellwatch_qc import image_features, quality_score, segment_nuclei


class CellWatchTests(unittest.TestCase):
    def test_synthetic_field_has_detectable_objects(self):
        image = np.full((64, 64), 0.08, dtype=np.float32)
        yy, xx = np.mgrid[:64, :64]
        for cy, cx in ((18, 20), (40, 43), (25, 48)):
            image += np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / 8).astype(np.float32) * 0.8
        result = segment_nuclei(image, min_area=8)
        self.assertGreaterEqual(len(result.props), 2)
        features = image_features(image, result)
        self.assertGreater(features["focus_laplacian"], 0)
        self.assertGreaterEqual(quality_score(features), 0)
        self.assertLessEqual(quality_score(features), 1)

    def test_empty_image_is_not_hidden_as_high_quality(self):
        image = np.full((64, 64), 0.2, dtype=np.float32)
        result = segment_nuclei(image)
        features = image_features(image, result)
        self.assertEqual(features["object_count"], 0)
        self.assertLess(quality_score(features), 0.55)


if __name__ == "__main__":
    unittest.main()
