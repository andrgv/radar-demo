import unittest
from unittest.mock import patch
import numpy as np
from radar_min.cfar import CfarConfig,CfarDetector
from radar_min.cfar_range import refine_group
from radar_min.gui import display_values,range_displayable
from tests_min.test_cfar import C,frame


class GroupRangeTests(unittest.TestCase):
    def test_peak_maximum_can_alternate_inside_one_group(self):
        d=CfarDetector(C,CfarConfig(guard_cells=1,training_cells=4,min_training_cells=4,factor=2))
        results=[]
        for i,values in enumerate(([100,90],[90,100],[100,90],[90,100]),1):
            p=np.ones(33);p[1:3]=values
            with patch('radar_min.cfar.power',return_value=p),patch('radar_min.cfar.refine_group',return_value=dict(range_m=.5)):
                results.append(d.update(frame(i)))
        self.assertEqual([r['target_detected'] for r in results],[False,False,True,True])
        self.assertEqual(results[-1]['confirmation_hits'],4)
        self.assertEqual(results[-1]['experimental_range_m'],.5)
        p=np.ones(33);p[4]=100
        with patch('radar_min.cfar.power',return_value=p):r=d.update(frame(5))
        self.assertFalse(r['target_detected']);self.assertIsNone(r['experimental_range_m'])

    def test_group_overlap_cannot_carry_large_jump(self):
        d=CfarDetector(C,CfarConfig(guard_cells=1,training_cells=4,min_training_cells=4,factor=1.5))
        with patch('radar_min.cfar.refine_group',return_value=dict(range_m=.5)):
            for i in range(1,4):
                p=np.ones(33);p[1:5]=[110,90,90,100]
                with patch('radar_min.cfar.power',return_value=p):d.update(frame(i))
            p[1:5]=[100,90,90,110]
            with patch('radar_min.cfar.power',return_value=p):r=d.update(frame(4))
        self.assertFalse(r['target_detected']);self.assertEqual(r['confirmation_hits'],1)

    def test_unreferenced_fractional_tone_has_subbin_estimate(self):
        f=frame(1,k=2.4,amplitude=1000)
        r=refine_group(f,C,[2,3])
        self.assertIsNotNone(r['range_m'])
        self.assertAlmostEqual(r['range_m'],2.4*C.spacing_m,delta=.008)
        self.assertFalse(r['boundary'])

    def test_peak_outside_support_cannot_be_forced_to_boundary(self):
        r=refine_group(frame(1,k=4,amplitude=1000),C,[1])
        self.assertIsNone(r['range_m']);self.assertTrue(r['boundary'])

    def test_comparable_competing_fine_peaks_are_unresolved(self):
        bins=np.arange(2049)*C.samples/4096
        p=np.exp(-((bins-1)/.05)**2)+.8*np.exp(-((bins-2)/.05)**2)
        with patch('radar_min.cfar_range.range_spectrum',return_value=np.sqrt(p)[None,:,None]):
            result=refine_group(frame(1),C,[1,2])
        self.assertIsNone(result['range_m'])
        self.assertEqual(result['reason'],'multiple_fine_peaks')

    def test_empty_zero_signal_does_not_create_a_fine_range(self):
        f=frame(1,amplitude=0);f.adc[:]=32768
        self.assertIsNone(refine_group(f,C,[1,2])['range_m'])

    def test_miss_and_fault_clear_group_and_fine_readout(self):
        d=CfarDetector(C)
        for i in range(1,4):r=d.update(frame(i))
        self.assertIsNotNone(r['experimental_range_m'])
        r=d.update(frame(5))
        self.assertIsNone(r['experimental_range_m']);self.assertFalse(r['target_detected'])
        self.assertFalse(d.group)
        self.assertFalse(d.update(frame(6))['target_detected'])
        d.update(frame(7));r=d.update(frame(8,amplitude=0))
        self.assertIsNone(r['experimental_range_m']);self.assertFalse(d.group)

    def test_presence_without_resolved_distance_stays_blank(self):
        r=dict(algorithm='range-ca-cfar-v2',target_detected=True,experimental_range_m=None,
               provisional_range_m=.695,fine_range=dict(reason='fine_peak_at_group_boundary'))
        self.assertFalse(range_displayable(r));self.assertEqual(display_values(r,True)[0],'—')
        self.assertIn('unresolved',display_values(r,True)[1])
        r['experimental_range_m']=.503
        self.assertEqual(display_values(r,True)[0],'50.3 cm')
        self.assertEqual(display_values(r,False)[0],'—')


if __name__=='__main__':unittest.main()
