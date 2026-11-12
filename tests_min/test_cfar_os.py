import unittest
import numpy as np

from radar_min.cfar import CfarConfig,ca_thresholds
from radar_min.cfar_os import OsConfig,os_thresholds,select_os_candidate
from radar_min.rd_live import LiveRangeDoppler
from tests_min.test_range_doppler import C,tone


class OsTests(unittest.TestCase):
    def test_rank_uses_actual_edge_references_and_excludes_dc_and_guards(self):
        settings=CfarConfig(1,4,4,2)
        power=np.ones(33);power[0]=power[-1]=1e12
        power[3:7]=[1,2,100,200]
        power[1]=power[2]=1e9
        noise,threshold,counts=os_thresholds(power,settings)
        self.assertEqual(counts[1],4)
        self.assertEqual(noise[1],2)  # ceil(.5*4) = second smallest, not median average
        self.assertEqual(threshold[1],4)
        self.assertGreater(ca_thresholds(power,settings)[0][1],70)
        self.assertTrue(np.isnan(threshold[[0,-1]]).all())

    def test_scaling_validation_and_no_input_mutation(self):
        p=np.arange(1,34,dtype=float);before=p.copy();s=CfarConfig(1,4,4,2)
        np.testing.assert_allclose(os_thresholds(p*10,s)[0],os_thresholds(p,s)[0]*10,equal_nan=True)
        np.testing.assert_array_equal(p,before)
        for value in (0,1.1,np.nan):
            with self.assertRaises(ValueError):OsConfig(value)
        with self.assertRaises(ValueError):os_thresholds([-1,2,3],s)

    def test_selection_withholds_multiple_groups_and_competing_rd_peaks(self):
        reading=dict(target_detected=True,reason='cfar_peak_uncalibrated',
                     candidates=[{},{}],fine_range=dict(range_m=.8),selected_group_bins=[2,3])
        self.assertEqual(select_os_candidate(reading,[])['reason'],'multiple_os_groups')
        reading['candidates']=[{}]
        peaks=[dict(range_bin=2,cycles_per_saved_block=0),dict(range_bin=3,cycles_per_saved_block=.1)]
        result=select_os_candidate(reading,[dict(local_maxima=peaks)])
        self.assertIsNone(result['experimental_range_m'])
        self.assertEqual(result['reason'],'multiple_current_rd_peaks')
        result=select_os_candidate(reading,[dict(local_maxima=peaks[:1])])
        self.assertEqual(result['experimental_range_m'],.8)
        self.assertFalse(result['primary_eligible'])

    def test_optional_branch_preserves_baseline_and_clears_on_rejection(self):
        default=LiveRangeDoppler(C);experimental=LiveRangeDoppler(C,experimental_os=True)
        for seq in (1,2,3):
            frame=tone([(2.2,0,2000)],seq)
            a=default.update(frame);b=experimental.update(frame)
            self.assertEqual(a['results'],b['results'])
            self.assertEqual(a['association'],b['association'])
            self.assertEqual(a['experimental_range_m'],b['experimental_range_m'])
        self.assertIn('clutter_comparison',b)
        rejected=experimental.reject_frame(tone([(2.2,0,2000)],4),'clock_fit_unstable')
        self.assertNotIn('clutter_comparison',rejected)
        self.assertFalse(rejected['valid'])
        recovered=experimental.update(tone([(2.2,0,2000)],5))
        self.assertIsNone(recovered['clutter_comparison']['selection']['experimental_range_m'])


if __name__=='__main__':unittest.main()
