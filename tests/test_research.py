import json
from pathlib import Path
import tempfile
import unittest
from radar.config import Config
from radar.research import FEATURES, evaluate, session_rows


class ResearchTests(unittest.TestCase):
    def populate(self, root, verified=True, shared_specimen=False):
        for index in range(8):
            session = root / f"session{index}"
            session.mkdir()
            glass = index % 2 == 1
            metadata = {"label": "glass" if glass else "non_glass",
                "scene_id": "test-scene" if index >= 4 else "train-scene",
                "specimen_id": "shared" if shared_specimen else f"specimen{index}"}
            (session / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            Config(verified=verified).save(session / "config.json")
            frames = []
            for frame_index in range(20):
                values = {name: float(2 * glass + 0.01 * index) for name in FEATURES}
                frames.append(json.dumps({**values, "temporal_frames": frame_index + 1, "saturation_fraction": 0}))
            (session / "features.jsonl").write_text("\n".join(frames), encoding="utf-8")

    def test_grouped_baseline_and_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "data"
            root.mkdir()
            self.populate(root)
            report = evaluate(root, Path(temporary) / "report", {"test-scene"})
            self.assertEqual(report["train_sessions"], 4)
            self.assertEqual(report["test_sessions"], 4)
            self.assertAlmostEqual(report["test_auc"], 1)
            self.assertEqual(report["confusion"], {"tp": 2, "fp": 0, "tn": 2, "fn": 0})
            self.assertTrue((Path(temporary) / "report" / "sessions.csv").is_file())

    def test_unverified_data_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.populate(root, verified=False)
            with self.assertRaisesRegex(ValueError, "Unverified"):
                session_rows(root)

    def test_specimen_leakage_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.populate(root, shared_specimen=True)
            with self.assertRaisesRegex(ValueError, "Specimen overlap"):
                evaluate(root, root / "report", {"test-scene"})


if __name__ == "__main__":
    unittest.main()
