"""Evidence fusion must preserve baseline behavior and separate competing returns."""
from dataclasses import replace
import unittest

from radar_min.cfar import CfarConfig, CfarDetector
from radar_min.rd_live import LiveRangeDoppler
from tests_min.test_range_doppler import C, tone


class JointResultsTests(unittest.TestCase):
    def test_primary_preserves_independent_baseline_and_resets_on_rejection(self):
        joint = LiveRangeDoppler(C)
        baseline = CfarDetector(C, CfarConfig(1,4,4,2))
        for sequence in range(1,6):
            frame = tone([(2.2,0,2000)],sequence)
            actual, expected = joint.update(frame), baseline.update(frame)
            self.assertEqual(actual['one_d'], {**expected, 'processing_ms': actual['one_d']['processing_ms']})
            primary = actual['results']['primary']
            self.assertEqual(primary['experimental_range_m'] if primary else None, expected['experimental_range_m'])
        rejected = joint.reject_frame(tone([(2.2,0,2000)],6),'serial_backlog')
        self.assertFalse(rejected['valid'])
        self.assertNotIn('results',rejected)
        recovered = joint.update(tone([(2.2,0,2000)],7))
        self.assertIsNone(recovered['results']['primary'])
        self.assertTrue(all(r.get('rd_range_m') is None for r in recovered['results']['candidates']))

    def test_doppler_conditioned_range_does_not_copy_the_stronger_wall(self):
        joint = LiveRangeDoppler(C)
        for sequence in (1,2,3):
            result = joint.update(tone([(2.15,0,3000),(1.7,-.25,1200)],sequence))
        rows = result['results']['candidates']
        moving = next(r for r in rows if r.get('cycles_per_saved_block') == -.25)
        wall = next(r for r in rows if r.get('cycles_per_saved_block') == 0)
        self.assertAlmostEqual(moving['rd_range_m'],1.7*C.spacing_m,delta=.025)
        self.assertAlmostEqual(wall['rd_range_m'],2.15*C.spacing_m,delta=.01)
        self.assertGreater(wall['rd_range_m']-moving['rd_range_m'],.15)
        group = next(r for r in rows if r['sources']==['1D'])
        self.assertEqual(group['association'],'multiple_range_matches')
        self.assertEqual(moving['sources'],['RD'])
        self.assertFalse(moving['primary_eligible'])

    def test_unique_duplicate_merges_and_all_1d_groups_confirm(self):
        config = replace(C,max_bin=20)
        joint = LiveRangeDoppler(config)
        for sequence in (1,2,3):
            result = joint.update(tone([(3,0,2000),(15,-.25,1700)],sequence))
        rows = [r for r in result['results']['candidates'] if '1D' in r['sources']]
        self.assertEqual(len(rows),2)
        self.assertTrue(all(r['sources']==['1D','RD'] for r in rows))
        self.assertTrue(all(r['one_d_confirmed'] for r in rows))
        self.assertTrue(all(r['one_d_range_m'] is not None for r in rows))
        self.assertEqual(sum(r['primary_eligible'] for r in rows),1)

    def test_rd_only_measurement_never_promotes_to_primary(self):
        joint = LiveRangeDoppler(C)
        for sequence in (1,2,3):
            result = joint.update(tone([(12,0,2000)],sequence))
        rd = next(r for r in result['results']['candidates'] if r.get('rd_confirmed'))
        self.assertIsNotNone(rd['rd_range_m'])
        self.assertFalse(rd['primary_eligible'])
        self.assertIsNone(result['results']['primary'])

    def test_nearby_doppler_competitors_withhold_refinement(self):
        joint = LiveRangeDoppler(C)
        frame = tone([(2,0,1000)])
        baseline = joint.one_d.update(frame)
        peaks = [dict(doppler_bin=d, range_bin=2, cycles_per_saved_block=(d-8)/16) for d in (8,10)]
        tracks = [dict(track_id=i,state='measured',measurement_valid=True,last_peak_sequence=1,
                       current_peak=p,current_support_cells=[]) for i,p in enumerate(peaks,1)]
        result = joint.bank.update(frame,baseline,dict(tracks=tracks),[dict(local_maxima=peaks)])
        for r in result['candidates']:
            if 'RD' in r['sources']:
                self.assertIsNone(r['rd_range_m'])
                self.assertEqual(r['rd_fine_range']['reason'],'competing_rd_peak_in_refinement_support')


if __name__ == '__main__':
    unittest.main()
