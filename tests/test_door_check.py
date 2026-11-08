import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import time
import threading

import numpy as np

from radar.config import Config
from radar.door_check import analyze_door_check, record_door_check
from radar.protocol import Frame, Parser
from radar.storage import Recorder


class DoorCheckTests(unittest.TestCase):
    def make_study(self, root, decreases=False, heldout_changed=True, no_change=False):
        config = Config()
        config.save(root / 'config.json')
        (root / 'door-check.json').write_text(json.dumps(dict(
            complete=True, repeats=3, measured_glass_distance_m=1.2)))
        for i in range(1, 4):
            for state in ('open', 'closed'):
                changed = state == 'closed' and (i < 3 or heldout_changed) and not no_change
                amplitude = (200 if decreases else 2400) if changed else 800
                name = root / f'{state}-{i:02d}'
                with Recorder(name, config) as recording:
                    for n in range(24):
                        # Isolated bin 7 changes; stronger unrelated clutter stays at 16.
                        x = np.arange(config.samples)
                        signal = 20000 + amplitude * np.cos(2*np.pi*7*x/config.samples)
                        signal += 4000 * np.cos(2*np.pi*16*x/config.samples)
                        adc = np.broadcast_to(signal[None, :, None], (config.chirps, config.samples, 3)).astype('uint16')
                        recording.write(Frame(n+1, n*100000, config.profile_id, adc))
                (name / 'arrivals.jsonl').write_text(''.join(json.dumps(dict(
                    host_unix_ns=1000000000+n*100000000, sequence=n+1))+'\n' for n in range(24)))
        return config

    def test_increase_and_decrease_detected_away_from_strongest_peak(self):
        for decreases in (False, True):
            with self.subTest(decreases=decreases), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.make_study(root, decreases=decreases)
                report = analyze_door_check(root)
                self.assertIn(report['selected_bin'], (6, 7, 8))  # Hann spreads adjacent bins
                self.assertTrue(report['heldout']['closed_detected'])
                self.assertFalse(report['heldout']['open_false_detection'])
                self.assertTrue((root / 'door-profiles.png').exists())
                self.assertTrue((root / 'door-profiles.csv').exists())

    def test_heldout_cannot_change_training_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_study(root, heldout_changed=False)
            report = analyze_door_check(root)
            self.assertIn(report['selected_bin'], (6, 7, 8))
            self.assertFalse(report['heldout']['closed_detected'])

    def test_unchanged_scene_has_no_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_study(root, no_change=True)
            report = analyze_door_check(root)
            self.assertIsNone(report['selected_bin'])
            self.assertIsNone(report['heldout'])

    def test_bad_raw_timing_and_config_rejected(self):
        for failure in ('truncated', 'timing', 'config', 'incomplete', 'short_window'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                config = self.make_study(root)
                path = root / 'open-01'
                if failure == 'truncated':
                    with (path / 'frames.grd').open('ab') as handle:
                        handle.write(b'GRD3')
                elif failure == 'timing':
                    (path / 'arrivals.jsonl').write_text('\n'.join(json.dumps(dict(host_unix_ns=1)) for _ in range(24)))
                elif failure == 'config':
                    config.slope_hz_s *= 2
                    config.save(path / 'config.json')
                elif failure == 'short_window':
                    manifest = json.loads((root / 'door-check.json').read_text())
                    manifest['seconds_per_state'] = 30
                    (root / 'door-check.json').write_text(json.dumps(manifest))
                else:
                    (root / 'door-check.json').write_text('{"complete": false}')
                with self.assertRaises(ValueError):
                    analyze_door_check(root)

    def test_invalid_capture_arguments_do_not_create_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'study'
            with self.assertRaises(ValueError):
                record_door_check(root, Config(), 'FAKE', float('nan'))
            self.assertFalse(root.exists())

    def test_guided_capture_keeps_one_connection_and_labels_all_states(self):
        config = Config()
        instances = []

        class FakeSource:
            def __init__(self, config, port):
                self.parser = Parser()
                self.transport_recorder = None
                self.sequence = 0
                self.closed = False
                self.epoch = time.monotonic()
                instances.append(self)

            def read(self):
                threading.Event().wait(.03)
                self.sequence += 1
                return Frame(self.sequence, int((time.monotonic()-self.epoch)*1e6),
                             config.profile_id, np.full((config.chirps, config.samples, 3), 20000, dtype='uint16'))

            def close(self):
                self.closed = True

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'capture'
            with patch('radar.door_check.Source', FakeSource), patch('builtins.input', return_value=''), \
                 patch('radar.door_check.time.sleep'):
                report = record_door_check(root, config, 'FAKE', 1.2, seconds=3)
            self.assertEqual(len(instances), 1)
            self.assertTrue(instances[0].closed)
            self.assertIsNone(report['selected_bin'])
            manifest = json.loads((root / 'door-check.json').read_text())
            self.assertTrue(manifest['complete'])
            self.assertEqual(len(manifest['completed_sessions']), 6)
            for name in manifest['completed_sessions']:
                metadata = json.loads((root / name / 'metadata.json').read_text())
                self.assertEqual(metadata['door_state'], name.split('-')[0])
                self.assertEqual(metadata['label'], 'unknown')

    def test_interruption_preserves_incomplete_manifest_and_closes_source(self):
        class FakeSource:
            parser = Parser()
            closed = False

            def __init__(self, config, port):
                pass

            def read(self):
                threading.Event().wait(.01)
                config = Config()
                return Frame(1, 100000, config.profile_id,
                             np.full((config.chirps, config.samples, 3), 20000, dtype='uint16'))

            def close(self):
                FakeSource.closed = True

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'capture'
            with patch('radar.door_check.Source', FakeSource), patch('builtins.input', side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    record_door_check(root, config=Config(), port='FAKE', distance=1.2)
            self.assertTrue(FakeSource.closed)
            self.assertFalse(json.loads((root / 'door-check.json').read_text())['complete'])

    def test_profile_mismatch_fails_before_first_prompt(self):
        class FakeSource:
            parser = Parser()
            closed = False

            def __init__(self, config, port):
                pass

            def read(self):
                return Frame(1, 100000, 0x33514802, np.full((17, 64, 3), 20000, dtype='uint16'))

            def close(self):
                FakeSource.closed = True

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'capture'
            with patch('radar.door_check.Source', FakeSource), patch('builtins.input') as prompt:
                with self.assertRaisesRegex(ValueError, 'qualification-hpf350.json'):
                    record_door_check(root, Config(), 'FAKE', 1.2)
                prompt.assert_not_called()
            self.assertTrue(FakeSource.closed)
            self.assertFalse((root / 'open-01').exists())


if __name__ == '__main__':
    unittest.main()
