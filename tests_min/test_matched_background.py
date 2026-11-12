"""Numerical controls for the offline matched-background comparison."""
from types import SimpleNamespace
import unittest
import numpy as np
from radar_min.core import Config, range_spectrum
from tools.investigate_matched_background import background_products, spectrum


class MatchedBackgroundTests(unittest.TestCase):
    def test_fft_matches_acquisition_processing(self):
        c = Config()
        adc = np.random.default_rng(3).integers(18000, 22000, (c.chirps, c.samples, 3))
        frame = SimpleNamespace(adc=adc, profile_id=c.profile_id)
        np.testing.assert_allclose(spectrum(adc[c.discard_chirps:].astype(float), 2048),
                                   range_spectrum(frame, c, nfft=2048))

    def test_fixed_template_recovers_added_tone_and_phase_flip_is_not_target(self):
        n = np.arange(64)
        background = np.tile((80*np.cos(2*np.pi*6*n/64))[:, None], (1,3))
        target = np.tile((12*np.cos(2*np.pi*2*n/64+.3))[:, None], (1,3))
        empty = np.tile(background[None], (16,1,1))
        reference = np.mean(abs(spectrum(empty, 64))**2, axis=0)
        unchanged = background_products(empty, background, reference, 64)
        np.testing.assert_allclose(unchanged['coherent_residual'], 0, atol=1e-20)
        np.testing.assert_allclose(unchanged['power_excess'], 0, atol=1e-20)
        result = background_products(empty+target[None], background, reference, 64)
        self.assertEqual(np.argmax(result['coherent_residual'].mean(axis=1)), 2)
        # A background phase reversal has equal power but a large waveform residual.
        flipped = background_products(-empty, background, reference, 64)
        np.testing.assert_allclose(flipped['power_excess'], 0, atol=1e-20)
        np.testing.assert_allclose(flipped['coherent_residual'], 4*reference, atol=1e-10)


if __name__ == '__main__':
    unittest.main()
