import unittest

import numpy as np

from tools.audit_pointcloud_recordings import summarize_cells


class EmpiricalCloudSummaryTests(unittest.TestCase):
    def test_no_points_is_reported_as_missing(self):
        self.assertIsNone(summarize_cells({}, 10))

    def test_stable_wrong_point_reports_stability_and_missing_frames_without_accuracy_claim(self):
        cells = {(8, 0.): [[1., 2., 3., 70., 70.]] * 6,
                 (10, .25): [[2., 3., 4., 80., 80.]] * 2}
        result = summarize_cells(cells, 10)
        self.assertEqual(result['native_range_bin'], 8)
        self.assertEqual(result['fraction_frames_present'], .6)
        np.testing.assert_allclose(result['xyz_std_m'], [0, 0, 0])
        self.assertIn('stable wrong direction', result['interpretation'])
        self.assertNotIn('accuracy_m', result)

    def test_spread_preserves_each_coordinate_and_does_not_smooth_outliers(self):
        points = [[float(i), float(2*i), float(3*i), 70., 75.] for i in range(10)]
        result = summarize_cells({(4, 0.):points}, 10)
        np.testing.assert_allclose(result['xyz_p05_median_p95_m'][1], [4.5, 9., 13.5])
        self.assertEqual(result['frames_present'], 10)
        self.assertGreater(result['xyz_std_m'][0], 2)


if __name__ == '__main__':
    unittest.main()
