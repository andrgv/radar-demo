"""Numerical unit tests: synthetic phases, never evidence of calibrated hardware."""
import unittest
import numpy as np

from radar.angular_calibration import AngularCalibrationError, fit_angular_report
from radar.config import Config


class AngularCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.config = Config(geometry_mm=[[0, 0], [0, 2.35], [-2.35, 0]])
        self.config.validate()
        self.nominal = self.config.array_geometry[1:] - self.config.array_geometry[0]
        distance, offset = 2., .4
        def entry(name, right, up, fit):
            r = np.array([right, distance, up], float)
            u = r[[0, 2]]/np.linalg.norm(r)
            az = np.degrees(np.arctan2(r[0], r[1]))
            el = np.degrees(np.arcsin(r[2]/np.linalg.norm(r)))
            return {'name':name, 'direction_right_up':u.tolist(),
                    'expected_azimuth_deg':float(az),'expected_elevation_deg':float(el),
                    'accepted':True, 'fit':fit,
                    'min_coherence':0.99,'local_contrast_db':21.}
        self.rows = [
            entry('center',0,0,True), entry('left',-offset,0,True),
            entry('right',offset,0,True), entry('up',0,offset,True),
            entry('check_right',offset/2,0,False),
            entry('check_left',-offset/2,0,False),
            entry('check_up',0,offset/2,False),
            entry('check_down',0,-offset/2,False),
            entry('center_repeat',0,0,False)]
        self.phase_offset = np.radians([52., -91.])

    def report(self, baselines=None, perturb=None):
        b = self.nominal if baselines is None else baselines
        rows = []
        for row in self.rows:
            phase = self.phase_offset + 2*np.pi*b @ row['direction_right_up']
            if perturb and row['name'] in perturb:
                phase += np.radians(perturb[row['name']])
            rows.append({**row, 'relative_phase_deg':np.degrees(np.angle(np.exp(1j*phase))).tolist()})
        return {'synthetic':False,'handheld':False,'poses':rows}

    def test_nominal_physical_phase_calibration_heldout_all_directions(self):
        calibrated, stats = fit_angular_report(self.report(), self.config)
        self.assertEqual(stats['status'], 'heldout_passed')
        self.assertLess(stats['heldout_max_error_deg'], 1e-5)
        self.assertEqual(stats['mode'], 'physical')
        self.assertFalse(calibrated.verified)
        np.testing.assert_allclose(np.angle(calibrated.gains[1:]), -self.phase_offset, atol=1e-6)
        np.testing.assert_allclose(calibrated.array_geometry, self.config.array_geometry)

    def test_bad_vertical_holdout_rejected(self):
        with self.assertRaisesRegex(AngularCalibrationError, 'Held-out angular validation failed'):
            fit_angular_report(self.report(perturb={'check_down':[28., -20.]}), self.config)

    def test_missing_vertical_holdout_not_certified(self):
        report = self.report()
        report['poses'] = [r for r in report['poses'] if r['name'] != 'check_up']
        with self.assertRaisesRegex(AngularCalibrationError, 'Missing sweep poses'):
            fit_angular_report(report, self.config)

    def test_nominal_geometry_mismatch_rejected_before_calibration(self):
        wrong = np.array([[.46, 0], [0, -.46]])
        with self.assertRaisesRegex(AngularCalibrationError, 'phase slopes do not match nominal'):
            fit_angular_report(self.report(baselines=wrong), self.config)

    def test_empirical_geometry_requires_explicit_mode_and_heldouts(self):
        b = self.nominal + np.array([[.07, .04], [.01, -.05]])
        calibrated, stats = fit_angular_report(self.report(baselines=b), self.config, mode='empirical')
        self.assertEqual(stats['status'], 'heldout_passed')
        self.assertFalse(calibrated.verified)
        self.assertIsNone(calibrated.geometry_mm)
        self.assertIn('Empirical', calibrated.geometry_label)
        np.testing.assert_allclose(calibrated.array_geometry[1:], b, atol=1e-8)

    def test_handheld_and_synthetic_rejected(self):
        for key in ['synthetic','handheld']:
            report = self.report()
            report[key] = True
            with self.assertRaises(AngularCalibrationError):
                fit_angular_report(report, self.config)

    def test_center_repeat_drift_rejected(self):
        with self.assertRaisesRegex(AngularCalibrationError, 'return-to-center'):
            fit_angular_report(self.report(perturb={'center_repeat':[26.,0.]}), self.config)


if __name__ == '__main__':
    unittest.main()
