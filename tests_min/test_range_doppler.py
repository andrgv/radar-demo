import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from radar.protocol import Frame
from radar.storage import Recorder
from radar_min.core import Config
from radar_min.range_doppler import RangeDoppler
from radar_min.__main__ import main


C = Config()


def tone(returns, seq=1):
    chirp = np.arange(C.chirps)[:, None, None]
    sample = np.arange(C.samples)[None, :, None]
    rx_phase = np.array([0, 0.4, -0.7])[None, None, :]
    adc = np.full((C.chirps, C.samples, 3), 32768.0)
    for k, frequency, amplitude in returns:
        adc += amplitude*np.cos(2*np.pi*(k*sample/C.samples+frequency*chirp)+rx_phase)
    return Frame(seq, seq*100000, C.profile_id, adc)


class RangeDopplerTests(unittest.TestCase):
    def test_signed_tones_phase_and_normalization(self):
        for f in (0, 3/16, -3/16, 1/16):
            processor = RangeDoppler(C)
            full, moving, info = processor.update(tone([(6, f, 1000)]))
            self.assertTrue(info['valid'])
            self.assertEqual(full.shape, (16, 33))
            self.assertEqual(info['peak_range_bin'], 6)
            self.assertAlmostEqual(info['peak_cycles_per_saved_block'], f)
            self.assertAlmostEqual(full[:, 6].max()/1e6, 1, places=3)
            np.testing.assert_allclose(info['phase_probe']['phase_step_rad'],
                                       2*np.pi*f, atol=0.001)
            if f == 0:
                self.assertLess(moving.max(), full.max()*1e-20)
            else:
                self.assertGreater(moving.max(), full.max()*0.9)

    def test_stationary_and_moving_returns_survive_in_full_map(self):
        processor = RangeDoppler(C)
        full, moving, _ = processor.update(tone([(5, 0, 2000), (12, -4/16, 800)]))
        self.assertGreater(full[8, 5], 3.9e6)
        self.assertGreater(full[4, 12], 0.63e6)
        self.assertLess(moving[8, 5], full[8, 5]*1e-6)
        self.assertGreater(moving[4, 12], 0.63e6)

    def test_near_zero_is_not_notched(self):
        full, moving, _ = RangeDoppler(C).update(tone([(6, 0.02, 1000)]))
        self.assertGreater(moving[8, 6], 0)
        self.assertGreater(full[8, 6], moving[8, 6])

    def test_gaps_invalid_flags_adc_and_recovery(self):
        processor = RangeDoppler(C)
        self.assertTrue(processor.update(tone([(6, 0, 1000)]))[2]['valid'])
        full, _, info = processor.update(tone([(6, 0, 1000)], seq=3))
        self.assertIsNone(full)
        self.assertEqual(info['reason'], 'sequence_gap')
        self.assertTrue(processor.update(tone([(6, 0, 1000)], seq=4))[2]['valid'])
        for mutation, reason in ((lambda f: setattr(f, 'flags', 0), 'invalid_frame_flags'),
                                 (lambda f: f.adc.fill(0), 'adc_container_rail'),
                                 (lambda f: f.adc.fill(np.nan), 'invalid_adc'),
                                 (lambda f: setattr(f, 'profile_id', 0), 'frame_config_mismatch')):
            frame = tone([(6, 0, 1000)])
            mutation(frame)
            a, b, info = RangeDoppler(C).update(frame)
            self.assertIsNone(a)
            self.assertIsNone(b)
            self.assertEqual(info['reason'], reason)

    def test_replay_exports_and_rejects_damaged_recording(self):
        import matplotlib
        matplotlib.use('Agg')
        with tempfile.TemporaryDirectory() as tmp:
            recording = Path(tmp)/'capture'
            output = Path(tmp)/'rd'
            with Recorder(recording, C) as recorder:
                for seq in range(1, 4):
                    recorder.write(tone([(6, -3/16, 1000)], seq))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['range-doppler', str(recording), '--output', str(output)]), 0)
            meta = json.loads((output/'metadata.json').read_text())
            self.assertEqual(meta['valid_frames'], 3)
            self.assertFalse(meta['timing_verified'])
            self.assertTrue((output/'preview.png').is_file())
            with np.load(output/'maps.npz') as maps:
                self.assertEqual(maps['full_power'].shape, (3, 16, 33))
                self.assertTrue(maps['valid'].all())
            raw = recording/'frames.grd'
            data = bytearray(raw.read_bytes())
            data[100] ^= 1
            raw.write_bytes(data)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['range-doppler', str(recording), '--output', str(Path(tmp)/'bad')]), 2)


if __name__ == '__main__':
    unittest.main()
