import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from radar.config import Config
from radar.protocol import Frame
from radar.storage import Recorder
from tools.audit_glass_signature import (cross_setup_statistics, extract_recording,
    paired_statistics, range_regions, window_metrics)
from tools.audit_coherence_origin import coherence_components


class SignatureMeasurementsTests(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.regions = range_regions(self.config, self.config.ranges[5])
        rng = np.random.default_rng(42)
        self.spectrum = (rng.normal(size=(10, 16, 33, 3))
                         + 1j * rng.normal(size=(10, 16, 33, 3)))
        # A coherent, stationary scattering center, with distinct RX phase.
        self.spectrum[:, :, 5, :] += 100 * np.exp(1j * np.array([0., .4, -.7]))

    def test_known_stationary_scatterer_has_high_coherence_and_gain_invariant_ratios(self):
        original, _ = window_metrics(self.spectrum, self.regions)
        scaled, _ = window_metrics(2 * self.spectrum, self.regions)
        self.assertGreater(original['chirp_stationary_fraction_combined'], .99)
        self.assertGreater(original['cross_rx_coherence_23'], .99)
        for key in original:
            if key.startswith('pane_power_db_'):
                self.assertAlmostEqual(scaled[key] - original[key], 20 * np.log10(2), places=9)
            else:
                self.assertAlmostEqual(scaled[key], original[key], places=9)

    def test_global_chirp_phase_motion_preserves_cross_rx_but_changes_stationary_fraction(self):
        original, _ = window_metrics(self.spectrum, self.regions)
        moving = self.spectrum * np.exp(2j * np.pi * np.arange(16) / 16)[None, :, None, None]
        changed, _ = window_metrics(moving, self.regions)
        self.assertLess(changed['chirp_stationary_fraction_combined'], .001)
        self.assertAlmostEqual(changed['cross_rx_coherence_12'], original['cross_rx_coherence_12'])
        self.assertAlmostEqual(changed['pane_power_db_combined'], original['pane_power_db_combined'])

    def test_receiver_only_return_is_preserved_and_tail_energy_is_separate(self):
        signal = self.spectrum.copy()
        signal[:, :, 5, 1:] = 0
        original, _ = window_metrics(signal, self.regions)
        self.assertGreater(original['pane_power_db_rx1'], original['pane_power_db_rx2'] + 30)
        signal[:, :, 20, :] += 1000
        tail, _ = window_metrics(signal, self.regions)
        self.assertAlmostEqual(tail['pane_power_db_rx1'], original['pane_power_db_rx1'])
        self.assertGreater(tail['later_over_pane_db_rx1'], original['later_over_pane_db_rx1'] + 20)

    def test_survey_roi_excludes_dc_and_nyquist_and_refuses_out_of_range(self):
        self.assertEqual(self.regions['roi'], [4, 5, 6])
        self.assertNotIn(0, self.regions['references'])
        self.assertNotIn(32, self.regions['references'])
        for distance in (0, float('nan'), self.config.ranges[-1] * 2):
            with self.assertRaises(ValueError):
                range_regions(self.config, distance)


class SignatureComparisonTests(unittest.TestCase):
    def test_consistent_changes_that_are_smaller_than_repeat_drift_do_not_pass(self):
        stats = paired_statistics([0, 10, 20], [1, 11, 21])
        self.assertEqual(stats['same_sign_direction'], 1)
        self.assertFalse(stats['strict_repeatability'])
        self.assertEqual(stats['recording_range_separation_direction'], 0)

    def test_reversed_effect_between_setups_is_not_a_common_signature(self):
        stats = cross_setup_statistics({
            'a': paired_statistics([0, 1, 2], [10, 11, 12]),
            'b': paired_statistics([10, 11, 12], [0, 1, 2]),
        })
        self.assertTrue(stats['strict_repeatability_every_setup'])
        self.assertEqual(stats['same_direction_all_pairs'], 0)
        self.assertFalse(stats['common_direction_and_strict_repeatability'])

    def test_common_effect_does_not_imply_common_absolute_threshold(self):
        stats = cross_setup_statistics({
            'a': paired_statistics([0, 1, 2], [10, 11, 12]),
            'b': paired_statistics([100, 101, 102], [110, 111, 112]),
        })
        self.assertTrue(stats['common_direction_and_strict_repeatability'])
        self.assertEqual(stats['common_threshold_separation_direction'], 0)
        self.assertEqual(stats['by_setup']['a']['recording_rank_auc_higher_is_closed'], 1)

    def test_ties_have_half_rank_credit_and_no_separation(self):
        stats = paired_statistics([1, 1, 1], [1, 1, 1])
        self.assertEqual(stats['recording_rank_auc_higher_is_closed'], .5)
        self.assertFalse(stats['strict_repeatability'])


class CoherenceOriginTests(unittest.TestCase):
    def test_stationary_generic_tone_explains_near_unity_coherence_without_material_labels(self):
        rng = np.random.default_rng(63)
        noise = rng.normal(size=(10, 16, 33, 3)) + 1j * rng.normal(size=(10, 16, 33, 3))
        low = coherence_components(noise + 3, [4, 5])['rx12']
        high = coherence_components(noise + 100, [4, 5])['rx12']
        self.assertGreater(high['observed'], low['observed'])
        self.assertGreater(high['observed'], .999)
        self.assertLess(abs(high['observed_minus_stationary_mean']), .0001)

    def test_zero_mean_shared_dynamics_are_coherent_but_not_explained_by_stationary_mean(self):
        x = np.broadcast_to(np.exp(2j * np.pi * np.arange(16) / 16)[None, :, None, None],
                            (10, 16, 33, 3))
        result = coherence_components(x, [4, 5])['rx12']
        self.assertAlmostEqual(result['observed'], 1)
        self.assertLess(result['stationary_mean'], 1e-20)
        self.assertAlmostEqual(result['residual_cross_magnitude'], 1)

    def test_observed_coherence_matches_primary_audit(self):
        rng = np.random.default_rng(44)
        x = rng.normal(size=(10, 16, 33, 3)) + 1j * rng.normal(size=(10, 16, 33, 3))
        regions = range_regions(Config(), Config().ranges[5])
        original, _ = window_metrics(x, regions)
        decomposed = coherence_components(x, regions['roi'])
        for pair in ('12', '13', '23'):
            self.assertAlmostEqual(original[f'cross_rx_coherence_{pair}'], decomposed[f'rx{pair}']['observed'])


class SignatureRawValidationTests(unittest.TestCase):
    def write_capture(self, path):
        config = Config()
        rng = np.random.default_rng(16)
        axis = np.arange(config.samples)[None, :, None]
        with Recorder(path, config) as recorder:
            for i in range(43):
                signal = (32768 + 1000 * np.cos(2 * np.pi * 5 * axis / config.samples)
                          + rng.normal(size=(config.chirps, config.samples, 3)))
                recorder.write(Frame(i, i * 100000, config.profile_id, signal.astype('<u2')))
        (path / 'arrivals.jsonl').write_text(''.join(json.dumps(dict(
            sequence=i, host_unix_ns=i * 100000000)) + '\n' for i in range(43)))
        return config

    def test_raw_to_summary_preserves_tail_and_rejects_corrupt_stale_or_wrong_arrivals(self):
        for failure in (None, 'crc', 'stale', 'sequence'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'capture'
                config = self.write_capture(path)
                if failure == 'crc':
                    raw = bytearray((path / 'frames.grd').read_bytes())
                    raw[100] ^= 1
                    (path / 'frames.grd').write_bytes(raw)
                elif failure in ('stale', 'sequence'):
                    rows = [json.loads(line) for line in (path / 'arrivals.jsonl').read_text().splitlines()]
                    for row in rows:
                        if failure == 'stale':
                            row['host_unix_ns'] = 0
                        else:
                            row['sequence'] += 1
                    (path / 'arrivals.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
                regions = range_regions(config, config.ranges[5])
                if failure:
                    with self.assertRaises(ValueError):
                        extract_recording(path, config, regions, 4.2)
                else:
                    summary, windows, hashes = extract_recording(path, config, regions, 4.2)
                    self.assertEqual(summary['windows'], 3)
                    self.assertEqual(summary['discarded_tail_frames'], 3)
                    self.assertEqual(windows[0]['first_sequence'], 10)
                    self.assertEqual(windows[-1]['last_sequence'], 39)
                    self.assertEqual(len(hashes), 43)


if __name__ == '__main__':
    unittest.main()
