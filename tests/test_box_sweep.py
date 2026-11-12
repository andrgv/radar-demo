"""Synthetic SOFTWARE tests; not evidence of measured hardware accuracy."""
import unittest
from dataclasses import dataclass
import numpy as np

from radar.box_sweep import make_poses, fit, CalibrationRejected


@dataclass
class FakeConfig:
    verified: bool = False
    calibration_id: str = 'uncalibrated'
    gains_real: list = None
    gains_imag: list = None
    angle_matrix_real: object = None
    angle_matrix_imag: object = None
    geometry_mm: object = None
    geometry_wavelengths: object = None
    geometry_label: str = 'nominal'
    mount_roll_deg: float = 0.

    @property
    def array_geometry(self):
        return np.array([[0., 0.], [.0, .47], [-.47, 0.]])

    def validate(self):
        return self


class BoxSweepTests(unittest.TestCase):
    def setUp(self):
        self.poses = make_poses()
        self.cfg = FakeConfig()
        self.baselines = self.cfg.array_geometry[1:]
        self.intercept = np.radians(np.array([35., -75.]))

    def report(self, overrides=None, b=None):
        baselines = self.baselines if b is None else b
        rows = []
        for p in self.poses:
            xyz = p['xyz_m']
            xyz = np.array(xyz)
            u = xyz[[0,2]] / np.linalg.norm(xyz)
            phase = self.intercept + 2 * np.pi * (baselines @ u)
            if overrides and p['name'] in overrides:
                phase += np.radians(np.asarray(overrides[p['name']]))
            rows.append({**p, 'accepted': True,
                'direction_right_up': u.tolist(),
                'relative_phase_deg': np.degrees(np.angle(np.exp(1j*phase))).tolist(),
                'expected_azimuth_deg': np.degrees(np.arctan2(xyz[0],xyz[1])),
                'expected_elevation_deg': np.degrees(np.arcsin(xyz[2]/np.linalg.norm(xyz)))})
        return {'synthetic':False, 'handheld':False, 'poses': rows}

    def test_real_heights(self):
        heights = {p['name']:p['xyz_m'][2] for p in self.poses}
        self.assertEqual(len(heights),10)
        self.assertAlmostEqual(heights['center'],-.1125)
        self.assertAlmostEqual(heights['up'], .1075)
        self.assertAlmostEqual(heights['down'],-.2225)
        self.assertAlmostEqual(heights['check_up'],.0525)
        self.assertAlmostEqual(heights['check_down'],-.1675)

    def test_nominal_calibration(self):
        calibrated, stats = fit(self.report(), self.cfg)
        self.assertEqual(stats['status'],'heldout_passed')
        self.assertLess(stats['heldout_max_error_deg'],1e-4)
        self.assertLess(stats['center_repeat_error_deg'],1e-4)
        np.testing.assert_allclose(np.angle(np.asarray(calibrated.gains_real[1:]) +
           1j * np.asarray(calibrated.gains_imag[1:])), -self.intercept, atol=1e-8)
        self.assertFalse(calibrated.verified)

    def test_vertical_holdout_rejected(self):
        with self.assertRaisesRegex(CalibrationRejected, 'Holdout failed'):
            fit(self.report(overrides={'check_up':[30,0]}), self.cfg)

    def test_reference_repeat_rejected(self):
        with self.assertRaisesRegex(CalibrationRejected, 'Holdout failed'):
            fit(self.report(overrides={'center_repeat':[25,0]}), self.cfg)

    def test_wrong_receiver_geometry_rejected(self):
        with self.assertRaisesRegex(CalibrationRejected, 'baselines differ'):
            fit(self.report(b=np.array([[0.40, 0.0],[0.0,-0.45]])), self.cfg)

    def test_missing_pose_rejected(self):
        r=self.report();r['poses']=[p for p in r['poses'] if p['name'] != 'check_down']
        with self.assertRaisesRegex(CalibrationRejected,'Missing poses'):
            fit(r,self.cfg)

    def test_bad_quality_gate_rejected(self):
        r=self.report();r['poses'][0]['accepted']=False
        with self.assertRaisesRegex(CalibrationRejected,'Failed target-quality'):
            fit(r,self.cfg)


if __name__ == '__main__':
    unittest.main()
