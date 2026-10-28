import json
import itertools
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from radar.config import Config
from radar.range_check import analyze_range_check, record_range_check
from radar.storage import Recorder
from radar.synthetic import Target, generate


class RangeCheckTests(unittest.TestCase):
    def make_study(self, root, near_bin, far_bin):
        config = Config()
        config.save(root / "config.json")
        (root / "range-check.json").write_text(json.dumps({"schema": 1,
            "measured_distances_m": {"near": 0.8, "far": 1.6}}), encoding="utf-8")
        clutter = Target(float(config.ranges[5]), amplitude=1700)
        for name, target_bin, start in (("empty", None, 0), ("near", near_bin, 100),
                                        ("far", far_bin, 200)):
            targets = [clutter]
            if target_bin is not None:
                targets.append(Target(float(config.ranges[target_bin]), amplitude=1800))
            with Recorder(root / name, config) as recorder:
                for index in range(30):
                    recorder.write(generate(config, sequence=index + 1, targets=targets,
                                            seed=start + index))

    def test_outward_shift_is_reported_without_claiming_calibration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_study(root, 10, 18)
            report = analyze_range_check(root)
            self.assertEqual(report["near"]["strongest_changed_bin"], 10)
            self.assertEqual(report["far"]["strongest_changed_bin"], 18)
            self.assertTrue(report["strongest_changed_bin_moves_outward"])
            self.assertIn("unverified", report["interpretation"])
            self.assertTrue((root / "range-check-report.json").exists())

    def test_inverted_shift_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_study(root, 18, 10)
            report = analyze_range_check(root)
            self.assertFalse(report["strongest_changed_bin_moves_outward"])
            self.assertIn("do not report", report["interpretation"])

    def test_backlogged_capture_is_not_reported_as_valid_movement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_study(root, 10, 18)
            manifest = json.loads((root / "range-check.json").read_text())
            manifest["seconds_per_position"] = 1
            (root / "range-check.json").write_text(json.dumps(manifest), encoding="utf-8")
            report = analyze_range_check(root)
            self.assertFalse(report["capture_timing_valid"])
            self.assertIsNone(report["short_range_live_selector"]["dominant_bin_moves_outward"])
            self.assertIn("INVALID CAPTURE", report["interpretation"])

    def test_guided_capture_saves_three_raw_sessions(self):
        config = Config()
        ticks = itertools.count()
        active = {"target_bin": None, "open_count": 0}

        class FakeSource:
            def __init__(self, received_config, port):
                active["open_count"] += 1
                self.sequence = 0
                self.serial = None
                self.transport_recorder = None

            def read(self):
                threading.Event().wait(0.001)
                self.sequence += 1
                target_bin = active["target_bin"]
                targets = [] if target_bin is None else [
                    Target(float(config.ranges[target_bin]), amplitude=1800)]
                return generate(config, sequence=self.sequence, targets=targets, seed=self.sequence)

            def close(self):
                pass

        def answer(prompt):
            if "NEAR distance" in prompt:
                return "0.8"
            if "FAR distance" in prompt:
                return "1.6"
            if "Remove the box" in prompt:
                active["target_bin"] = None
            elif "NEAR position" in prompt:
                active["target_bin"] = 10
            elif "FAR position" in prompt:
                active["target_bin"] = 18
            return ""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "guided"
            with patch("radar.range_check.Source", FakeSource), \
                 patch("radar.range_check.time.sleep"), \
                 patch("radar.range_check.time.monotonic", side_effect=lambda: next(ticks) * 0.05), \
                 patch("builtins.input", side_effect=answer):
                report = record_range_check(root, config, "FAKE", seconds=3)
            self.assertTrue(report["strongest_changed_bin_moves_outward"])
            self.assertTrue(report["capture_timing_valid"])
            self.assertEqual(report["measured_distances_m"], {"near": 0.8, "far": 1.6})
            self.assertEqual(active["open_count"], 1)
            self.assertTrue(json.loads((root / "range-check.json").read_text())["one_continuous_sensor_session"])
            for name in ("empty", "near", "far"):
                self.assertTrue((root / name / "frames.grd").exists())


if __name__ == "__main__":
    unittest.main()
