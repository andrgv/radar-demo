"""Offline software tests only; do not imply hardware angular calibration."""
from dataclasses import dataclass, replace
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np
from tools.box_sweep_followup import (
    _cross_phase, circular_spread_deg, compare_phases, diagnose, recapture, wrap_deg,
)


def fake_radar_modules():
    radar = types.ModuleType('radar')
    radar.__path__ = []
    config_mod = types.ModuleType('radar.config')
    processing = types.ModuleType('radar.processing')
    storage = types.ModuleType('radar.storage')
    background = types.ModuleType('radar.background')
    box_sweep = types.ModuleType('radar.box_sweep')

    @dataclass
    class Config:
        profile_id: int = 860964866
        samples: int = 16
        chirps: int = 8
        gains_real: object = None
        gains_imag: object = None

        @classmethod
        def load(cls, path):
            return cls(**json.loads(Path(path).read_text()))

        @property
        def ranges(self):
            return np.arange(self.samples // 2 + 1) * 0.7

        @property
        def array_geometry(self):
            return np.array([[0., 0.], [0., .47], [-.47, 0.]])

    def range_fft(adc, config):
        return np.fft.rfft(adc, axis=1)

    def replay(directory):
        name = Path(directory).name
        seed = sum(map(ord, name))
        rng = np.random.default_rng(seed)
        for i in range(20):
            # Same spectrum at each frame to give stable phase signatures.
            a = np.arange(16)[None, :, None]
            gains = np.array([1., np.exp(.4j), np.exp(-.2j)])[None, None, :]
            reference = (1 + 0.4 * (not name.startswith('background_')))
            sample = reference * np.sin(2 * np.pi * 3 * a / 16 +
                                        np.array([0., .4, -.2])[None, None, :])
            adc = np.tile(sample, (8, 1, 1)) + .03 * rng.normal(size=(8, 16, 3))
            yield types.SimpleNamespace(adc=adc, profile_id=860964866, flags=1)

    def noise_threshold(power, factor):
        return np.full_like(power, max(float(np.median(power[1:])), 1e-10) * factor)

    class SpectralBackground:
        @staticmethod
        def from_path(directory, config):
            return object()

    def _capture(path, *_args, **_kwargs):
        Path(path).mkdir()
        (Path(path) / 'frames.grd').write_bytes(b'new')

    def analyze(root):
        report = {'accepted_count': 10, 'total_poses': 10}
        return report

    config_mod.Config = Config
    processing.range_fft = range_fft
    processing.noise_threshold = noise_threshold
    storage.replay = replay
    background.SpectralBackground = SpectralBackground
    box_sweep._capture = _capture
    box_sweep.analyze = analyze
    return {m.__name__: m for m in (radar, config_mod, processing, storage, background, box_sweep)}


class BoxSweepFollowupTests(unittest.TestCase):
    def test_wrapping(self):
        np.testing.assert_allclose(wrap_deg([190., -190., 360., 10.]), [-170., 170., 0., 10.])

    def test_nominal_geometry_predictions(self):
        rows = {
            'check_left': {'direction_right_up': [-.075, -.056], 'relative_phase_deg': [-177.14, 126.16], 'support': 'two_flat'},
            'check_right': {'direction_right_up': [.075, -.056], 'relative_phase_deg': [156.19, 111.65], 'support': 'two_flat'},
        }
        pairs = compare_phases(rows, [[0, .47], [-.47, 0]])
        self.assertEqual(len(pairs), 1)
        self.assertTrue(pairs[0]['same_support'])
        np.testing.assert_allclose(pairs[0]['predicted_deg_rx2_rx3'], [0, -25.38], atol=.02)
        np.testing.assert_allclose(pairs[0]['observed_deg_rx2_rx3'], [-26.67, -14.51], atol=.02)

    def test_circular_temporal_spread(self):
        spread = circular_spread_deg(np.array([[179, 30], [-179, 30], [180, 30]]))
        self.assertLess(spread[0], 1.0)
        self.assertLess(spread[1], 1e-4)

    def test_cross_phase(self):
        spectrum = np.zeros((20, 8, 9, 3), dtype=complex)
        spectrum[:, :, 3, :] = np.array([1., np.exp(1j*.5), np.exp(-1j*.2)])
        measurement = _cross_phase(spectrum, 3)
        np.testing.assert_allclose(measurement['relative_phase_deg'], np.degrees([.5, -.2]), atol=1e-9)
        self.assertAlmostEqual(measurement['min_coherence'], 1.0)

    def test_analyze_does_not_modify_original_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'config.json').write_text(json.dumps({'profile_id':860964866, 'samples':16, 'chirps':8}))
            manifest = {'kind': 'measured-height-paired-background',
                        'poses': [{'name':'center', 'fit':True, 'support':'two_flat', 'xyz_m':[0,2,-.1125]}]}
            (root/'sweep.json').write_text(json.dumps(manifest))
            old = {'poses':[{'name':'center','accepted':False}]}
            (root/'sweep-report.json').write_text(json.dumps(old))
            with patch.dict(sys.modules, fake_radar_modules()):
                result = diagnose(root, make_plots=False)
            self.assertEqual(result['poses'][0]['frames_target'],20)
            self.assertEqual(json.loads((root/'sweep-report.json').read_text()),old)
            self.assertTrue((root/'box-sweep-diagnostics.json').exists())

    def test_recapture_only_failed_into_new_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'original'
            source.mkdir()
            output = Path(directory)/'retry'
            poses = [{'name':'center','fit':True,'support':'two_flat',
                      'support_description':'two flat','xyz_m':[0,2,-.1125]},
                     {'name':'up','fit':True,'support':'one_upright',
                      'support_description':'one upright','xyz_m':[0,2,.0525]}]
            (source/'sweep.json').write_text(json.dumps({'kind':'measured-height-paired-background','poses':poses}))
            (source/'sweep-report.json').write_text(json.dumps({'poses':[{'name':'center','accepted':False},
                                                                            {'name':'up','accepted':True}]}))
            (source/'config.json').write_text(json.dumps({'profile_id':860964866, 'samples':16, 'chirps':8}))
            for name in ('center','up','background_center','background_up'):
                (source/name).mkdir()
                (source/name/'frames.grd').write_bytes(b'original')
            with patch.dict(sys.modules, fake_radar_modules()), patch('builtins.input', return_value=''):
                report = recapture(source,output,'/dev/test',seconds=2)
            self.assertEqual(report['accepted_count'],10)
            self.assertEqual((source/'center'/'frames.grd').read_bytes(), b'original')
            self.assertEqual((output/'center'/'frames.grd').read_bytes(), b'new')
            self.assertEqual((output/'up'/'frames.grd').read_bytes(), b'original')
            self.assertEqual((output/'background_center'/'frames.grd').read_bytes(), b'new')
            self.assertEqual((output/'background_up'/'frames.grd').read_bytes(), b'original')
            with patch.dict(sys.modules, fake_radar_modules()):
                with self.assertRaisesRegex(ValueError,'already exists'):
                    recapture(source,output,'/dev/test')


if __name__=='__main__':
    unittest.main()
