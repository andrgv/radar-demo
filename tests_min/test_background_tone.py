"""Positive control for offline nuisance solver, not hardware qualification."""
from types import SimpleNamespace
import unittest
import numpy as np
from radar_min.core import Config
from tools.evaluate_tone_background import JointBackground
from tools.fit_range_signal import traces

class BackgroundToneTests(unittest.TestCase):
    def test_distinct_target_with_phase_and_amplitude_changing_background(self):
        c=Config();t=np.arange(c.samples)/c.sample_rate_hz
        def wave(d,p):return np.cos(2*np.pi*(2*c.slope_hz_s*d/299792458)*t+p)
        def frame(x):return SimpleNamespace(adc=np.tile(x[None,:,None],(c.chirps,1,3)))
        empty=[frame(20000+70*wave(.9,0)) for _ in range(30)]
        model=JointBackground(c,empty,1);ref=traces(empty[0],c)
        for distance in [.3,.4,.5]:
            for phase in np.arange(12)*2*np.pi/12:
                f=frame(20000+(70+20*np.sin(phase))*wave(.9,phase)+20*wave(distance,.7))
                self.assertLess(abs(model.fit(traces(f,c)-ref)-distance),.0051)
