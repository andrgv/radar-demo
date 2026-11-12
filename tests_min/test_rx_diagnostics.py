import json
import unittest
import numpy as np

from radar_min.core import range_spectrum
from radar_min.rx_diagnostics import receiver_group_diagnostics,current_receiver_diagnostic
from radar_min.rd_live import LiveRangeDoppler
from tests_min.test_range_doppler import C,tone


class ReceiverDiagnosticsTests(unittest.TestCase):
    def diagnose(self,frame,bins,pooled):
        p=np.mean(abs(range_spectrum(frame,C,nfft=4096))**2,axis=0)
        return receiver_group_diagnostics(frame,C,bins,p,4096,pooled)

    def test_clean_tone_agrees_and_weak_rx_does_not_force_a_peak(self):
        f=tone([(2.2,0,2000)])
        d=self.diagnose(f,[1,2,3],2.2*C.spacing_m)
        self.assertEqual(d['resolved_rx'],3)
        self.assertLess(d['spread_m'],.01)
        self.assertLess(d['single_tone_residual_fraction'],1e-12)
        self.assertEqual(d['flags'],[])
        f.adc[:,:,2]=32768
        d=self.diagnose(f,[1,2,3],2.2*C.spacing_m)
        self.assertEqual(d['resolved_rx'],2)
        self.assertIsNone(d['receivers'][2]['range_m'])
        self.assertIn('rx_peak_unresolved',d['flags'])
        json.dumps(d,allow_nan=False)

    def test_receiver_disagreement_and_background_mismatch_are_separate(self):
        f=tone([]);n=np.arange(C.samples)[None,:,None]
        f.adc=32768+np.broadcast_to(2000*np.cos(2*np.pi*n*np.array([1.7,2.2,2.6])/C.samples),f.adc.shape)
        d=self.diagnose(f,[1,2,3],2.2*C.spacing_m)
        self.assertIn('rx_peak_disagreement',d['flags'])
        self.assertGreater(d['spread_m'],.2)
        d=self.diagnose(tone([(2.2,0,1000),(7,0,4000)]),[1,2,3],2.2*C.spacing_m)
        self.assertIn('single_tone_mismatch_at_fft_range',d['flags'])
        self.assertGreater(d['single_tone_residual_fraction'],.9)

    def test_unresolved_pooled_range_has_no_forced_model_fit(self):
        d=self.diagnose(tone([(4,0,2000)]),[1],None)
        self.assertEqual(d['resolved_rx'],0)
        self.assertIsNone(d['spread_m'])
        self.assertIsNone(d['single_tone_residual_fraction'])
        self.assertTrue(all(r['boundary']for r in d['receivers']))

    def test_confirmation_selection_rejection_and_recovery_never_hold_diagnostics(self):
        live=LiveRangeDoppler(C)
        first=live.update(tone([(2.2,0,2000)],1))
        self.assertIsNone(current_receiver_diagnostic(first))
        for seq in (2,3):reading=live.update(tone([(2.2,0,2000)],seq))
        d=current_receiver_diagnostic(reading)
        self.assertEqual(d['frame_sequence'],3)
        cid=reading['results']['primary']['candidate_id']
        self.assertEqual(current_receiver_diagnostic(reading,cid),d)
        self.assertIsNone(current_receiver_diagnostic(reading,'missing'))
        reading['receiver_diagnostics']['frame_sequence']=0
        self.assertIsNone(current_receiver_diagnostic(reading))
        rejected=live.reject_frame(tone([(2.2,0,2000)],4),'serial_backlog')
        self.assertIsNone(current_receiver_diagnostic(rejected))
        self.assertIsNone(live.bank.receiver_diagnostics)
        recovered=live.update(tone([(2.2,0,2000)],5))
        self.assertIsNone(current_receiver_diagnostic(recovered))
        live.clear();self.assertIsNone(live.bank.receiver_diagnostics)
