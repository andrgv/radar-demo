import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from radar.config import Config
from radar.storage import Recorder
from radar.sweep import analyze_sweep, sweep_poses
from radar.synthetic import Target, generate


class SweepTests(unittest.TestCase):
    def build_recording(self, root, missing_target=None):
        config = Config(geometry_mm=[[0, 0], [0, 2.35], [-2.35, 0]])
        config.save(root / "config.json")
        poses = sweep_poses(1.3, 0.3)
        (root / "sweep.json").write_text(json.dumps({"schema": 1, "poses": poses}), encoding="utf-8")
        with Recorder(root / "background", config) as recorder:
            for sequence in range(1, 16):
                recorder.write(generate(config, sequence, targets=[], seed=sequence))
        response = np.array([1, 0.7 * np.exp(0.6j), 1.3 * np.exp(-0.4j)])
        for pose in poses:
            position = np.asarray(pose["xyz_m"])
            distance = float(np.linalg.norm(position))
            target = Target(distance, azimuth_deg=float(np.degrees(np.arctan2(position[0], position[1]))),
                            elevation_deg=float(np.degrees(np.arcsin(position[2] / distance))))
            with Recorder(root / pose["name"], config) as recorder:
                for sequence in range(1, 16):
                    targets = [] if pose["name"] == missing_target else [target]
                    recorder.write(generate(config, sequence, targets=targets,
                        channel_response=response, seed=sequence + 100))
        return config

    def test_known_baselines_recovered_with_heldout_positions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.build_recording(root)
            report = analyze_sweep(root)
            self.assertEqual(report["accepted_heldout_poses"], 2)
            self.assertFalse(report["calibration_saved"])
            np.testing.assert_allclose(report["fitted_baselines_wavelengths_rx2_rx3"],
                config.array_geometry[1:] - config.array_geometry[0], atol=0.01)
            for check in report["heldout_phase_checks"]:
                self.assertLess(max(abs(np.asarray(check["phase_prediction_error_deg"]))), 1)
            self.assertTrue((root / "sweep-report.json").is_file())

    def test_failed_direction_does_not_produce_a_fit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.build_recording(root, missing_target="up")
            report = analyze_sweep(root)
            self.assertIn("insufficient", report["status"])
            self.assertNotIn("fitted_baselines_wavelengths_rx2_rx3", report)

    def test_position_geometry_and_invalid_plan(self):
        poses = sweep_poses(1.3, 0.3)
        right = next(pose for pose in poses if pose["name"] == "right")
        self.assertAlmostEqual(np.linalg.norm(right["xyz_m"]), np.sqrt(1.3**2 + 0.3**2))
        self.assertFalse(poses[-1]["fit"])
        for distance, offset in [(0, 0.3), (1, -0.1), (1, 2), (float("nan"), 0.3)]:
            with self.assertRaises(ValueError):
                sweep_poses(distance, offset)

    def test_handheld_report_does_not_claim_precision_calibration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.build_recording(root)
            manifest = json.loads((root / "sweep.json").read_text(encoding="utf-8"))
            manifest["handheld"] = True
            (root / "sweep.json").write_text(json.dumps(manifest), encoding="utf-8")
            report = analyze_sweep(root)
            self.assertTrue(report["handheld"])
            self.assertIn("qualitative", report["status"])
            self.assertFalse(report["calibration_saved"])
            self.assertIn("Hand/body", report["limitation"])
