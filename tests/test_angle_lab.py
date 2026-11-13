"""Offline tests: pure geometry + phase identification, no radar required."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np

from radar.angle_lab import (wrap, raw_model_phase, infer_azimuth_rx2,
    circular_spread_rad, _elevation_diagnostic, _stats_at_bin, infer_elevation_rx3)


class FakeConfig:
    def __init__(self):
        self.array_geometry = np.array([[0,0],[-.4703,0],[0,-.4703]])
        self.angle_matrix = np.array([[.5,0,0],[.052+.106j,-.439+.160j,0],
                                      [-.062+.018j,0,-.158-.460j]])
        self.gains = np.array([1,np.exp(.25j),np.exp(-.22j)])
        self.ranges = np.arange(33)*.348


class LabTests(unittest.TestCase):
    def setUp(self):
        self.cfg=FakeConfig()
        self.anchor=[0,2,-.1125]
        self.p0 = raw_model_phase(self.cfg,self.anchor)

    def test_rotation_and_raw_matrix_included(self):
        phase=raw_model_phase(self.cfg,[.15,2,-.1125])
        self.assertEqual(phase.shape,(2,))
        self.assertNotAlmostEqual(phase[1],phase[0])
        expected=np.linalg.solve(self.cfg.angle_matrix,
                 np.exp(2j*np.pi*self.cfg.array_geometry@np.array([.15,-.1125])/np.linalg.norm([.15,2,-.1125])))
        expected=expected*self.cfg.gains
        np.testing.assert_allclose(phase,np.angle(expected[1:]*expected[0].conj()))

    def test_horizontal_inverse_multiple_positions(self):
        for truth in [-12,-8,-4.29,0,4.29,8,12]:
            x=2*np.tan(np.radians(truth))
            observed=raw_model_phase(self.cfg,[x,2,-.1125])[0]
            az,res=infer_azimuth_rx2(observed,self.p0[0],self.anchor,self.cfg)
            self.assertAlmostEqual(az,truth,delta=.06)
            self.assertLess(res,.1)

    def test_constant_phase_offset_cancels(self):
        x=.15
        observed=raw_model_phase(self.cfg,[x,2,-.1125])[0]
        phase_bias=.5
        az,_=infer_azimuth_rx2(observed+phase_bias,self.p0[0]+phase_bias,self.anchor,self.cfg)
        self.assertAlmostEqual(az,np.degrees(np.arctan2(x,2)),delta=.08)

    def test_unmodeled_height_does_not_bless_z(self):
        # Horizontal inversion explicitly requires support height and is NOT
        # a claim that the radar has recovered the elevation.
        observed=raw_model_phase(self.cfg,[.15,2,-.1125])[0]
        az,_=infer_azimuth_rx2(observed,self.p0[0],self.anchor,self.cfg,z_m=-.1125)
        self.assertAlmostEqual(az,4.29,delta=.08)

    def test_rx3_elevation_inversion_on_clean_point_target(self):
        for truth in [-6.3,-3.2,0.,1.5,3.1,6.]:
            target=[0,2,2*np.tan(np.deg2rad(truth))]
            measured=raw_model_phase(self.cfg,target)[1]
            result=infer_elevation_rx3(measured,self.p0[1],self.anchor,self.cfg)
            self.assertAlmostEqual(result['elevation_deg'],truth,delta=.06)
            self.assertFalse(result['search_boundary_hit'])

    def test_wrap(self):
        np.testing.assert_allclose(np.exp(1j*wrap([np.pi*3,-np.pi*3])),[-1,-1],atol=1e-12)

    def test_spread_and_coherence(self):
        S=np.ones((12,16,12,3),dtype=complex)
        S[:,:,:,1]=np.exp(.15j);S[:,:,:,2]=np.exp(-.3j)
        st=_stats_at_bin(S,6)
        np.testing.assert_allclose(st['coherence'],[1,1],atol=1e-12)
        np.testing.assert_allclose(st['phase_rad'],[.15,-.3],atol=1e-12)
        np.testing.assert_allclose(st['phase_spread_deg'],[0,0],atol=2e-6)

    def test_elevation_support_confounded(self):
        names=[('center_repeat',-.1125,'two_flat'),('up',.1075,'upright_plus_flat'),
               ('check_up',.0525,'one_upright'),('down',-.2225,'none'),('check_down',-.1675,'one_flat')]
        rows={n:dict(xyz_m=[0,2,z],support=s,direction_right_up=[0,z/np.hypot(2,z)],accepted=True)
              for n,z,s in names}
        stats={n:{k:dict(phase_rad=raw_model_phase(self.cfg,rows[n]['xyz_m']),
                           coherence=np.ones(2),phase_spread_deg=np.zeros(2)) for k in (5,6,7)} for n in rows}
        report=_elevation_diagnostic(rows,stats,self.cfg,[5,6,7])
        self.assertFalse(report['structurally_identifiable'])
        self.assertFalse(report['same_support_different_height_pairs'])
        for row in report['two_raised_pose_extrapolation']:
            self.assertLess(abs(row['heldout_center_phase_error_deg']),0.5)

    def test_elevation_changed_scene_has_large_bias(self):
        names=[('center_repeat',-.1125,'two_flat',113.82),
               ('up',.1075,'upright_plus_flat',118.74),
               ('check_up',.0525,'one_upright',125.66)]
        rows={n:dict(xyz_m=[0,2,z],support=s,direction_right_up=[0,z/np.hypot(2,z)],accepted=True)
              for n,z,s,_ in names}
        stats={n:{6:dict(phase_rad=np.radians([155,phase]),coherence=np.ones(2),
                         phase_spread_deg=np.zeros(2))} for n,z,s,phase in names}
        r=_elevation_diagnostic(rows,stats,self.cfg,[6])
        test=next(p for p in r['two_raised_pose_extrapolation'] if p['rx']==3)
        self.assertGreater(abs(test['heldout_center_phase_error_deg']),20)

if __name__=='__main__':unittest.main()

class IntegrationTests(unittest.TestCase):
    def test_end_to_end_synthetic_sweep(self):
        import json, sys, types
        from unittest import mock
        from radar import angle_lab as lab
        c = FakeConfig()
        # Simulate the actual config interface. All scene-specific text is mocked;
        # no claims about the real saved radar frames.
        c.profile_id = 0x33514802
        c.samples=64;c.chirps=17;c.sample_rate_hz=5e6
        c.slope_hz_s=33691406250000.;c.carrier_hz=60e9;c.discard_chirps=1
        c.verified=False
        rows=[]
        arr=[('center',0,-.1125,'two_flat',False),
             ('left',-.30,-.1125,'two_flat',False),
             ('right',+.30,-.1125,'two_flat',False),
             ('check_left',-.15,-.1125,'two_flat',True),
             ('check_right',+.15,-.1125,'two_flat',True),
             ('center_repeat',0,-.1125,'two_flat',True),
             ('up',0,+.1075,'upright_plus_flat',True),
             ('down',0,-.2225,'none',False),
             ('check_up',0,+.0525,'one_upright',True),
             ('check_down',0,-.1675,'one_flat',False)]
        for n,x,z,s,acc in arr:
            rows.append(dict(name=n, xyz_m=[x,2,z], support=s,accepted=acc,
                             direction_right_up=[x/np.linalg.norm([x,2,z]),z/np.linalg.norm([x,2,z])],
                             range_bin=6))
        fake_specs={}
        rng=np.random.default_rng(4)
        for row in rows:
            xyz=row['xyz_m']
            direction=np.array([xyz[0],xyz[2]])/np.linalg.norm(xyz)
            signature=np.linalg.solve(c.angle_matrix,np.exp(2j*np.pi*(c.array_geometry@direction)))*c.gains
            spec=(rng.normal(size=(18,16,33,3))+1j*rng.normal(size=(18,16,33,3)))*0.01
            spec[:,:,6,:]+=signature[None,None,:]
            fake_specs[row['name']]=spec
        class FakeConfigModule:
            Config=types.SimpleNamespace(load=lambda path: c)
        proc=types.ModuleType('radar.processing')
        proc.noise_threshold=lambda power,factor: np.full_like(power,.0002)
        proc.interpolated_range=lambda power,k,cfg: 2.0
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'recordings';root.mkdir()
            (root/'sweep.json').write_text(json.dumps(dict(kind='measured-height-paired-background',
                     poses=rows)))
            (root/'sweep-report.json').write_text(json.dumps(dict(poses=rows)))
            out=Path(td)/'results'
            with mock.patch.dict(sys.modules,{'radar.config':FakeConfigModule, 'radar.processing':proc}):
                with mock.patch.object(lab,'_frame_spectra',side_effect=lambda f,cfg:fake_specs[Path(f).name]):
                    summary=lab.analyze(root,'configs/experimental.json',out)
            self.assertEqual(summary['accepted_horizontal_holdouts'],2)
            held=[r for r in summary['horizontal'] if r['validation_holdout']]
            for row in held:
                self.assertLess(abs(row['azimuth_error_deg']),.1)
            self.assertFalse(summary['elevation']['structurally_identifiable'])
            self.assertTrue((out/'range_azimuth.json').is_file())
            self.assertTrue((out/'range_azimuth.png').is_file())
            self.assertTrue((out/'elevation_audit.png').is_file())
            self.assertTrue((out/'elevation_candidate.png').is_file())
