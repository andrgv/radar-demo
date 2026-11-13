"""Synthetic tests for tools/two_path_geometry_audit.py; no hardware claims."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np

here=Path(__file__).resolve().parent
candidates=[here/'two_path_geometry_audit.py', here/'../tools/two_path_geometry_audit.py']
path=next((p for p in candidates if p.exists()),None)
if path is None:
    raise RuntimeError('Place test alongside script or under tests/ with script under tools/')
import sys
spec=importlib.util.spec_from_file_location('two_path_geometry_audit',path)
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)

class Cfg:
    samples=64
    sample_rate_hz=5_000_000
    slope_hz_s=33691406250000.
    carrier_hz=60e9
    array_geometry=np.array([[0,0],[-.470,0],[0,-.470]])
    angle_matrix=np.eye(3,dtype=complex)

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.cfg=Cfg()
        self.bins=(4,5,6,7,8)
        self.theta=np.array([.3,-.2])
        self.gamma=.45+.13j

    def obs(self,name,x,y,z):
        v=m.template(self.cfg,x,y,z,.34,self.bins,self.theta,self.gamma)
        v=v/np.linalg.norm(v)
        return m.Observation(name,x,y,z,True,np.outer(v,v.conj()),1.,300)

    def test_kernel_beats_at_expected_bin(self):
        k=m.fft_kernel(4.,self.cfg,range(2,12))
        self.assertEqual(int(np.argmax(abs(k)))+2,6)

    def test_covariance_invariant_common_chirp_phase(self):
        rng=np.random.default_rng(42)
        v=m.template(self.cfg,0,2.,-.1,.34,self.bins,self.theta,self.gamma)
        v=v/np.linalg.norm(v)
        signals=np.stack([(v * np.exp(1j*float(rng.uniform(-np.pi,np.pi)))).reshape(5,3)
                          for _ in range(100)])
        cov,lam,count=m.normalized_covariance(signals[None])
        self.assertEqual(count,100)
        self.assertAlmostEqual(lam,1.,places=9)
        self.assertAlmostEqual(m.alignment(cov,v),1.,places=9)

    def test_single_path_is_nested(self):
        a,b=m.paths(self.cfg,.15,2,-.1125,.34,self.bins)
        t=m.template(self.cfg,.15,2,-.1125,.34,self.bins,np.zeros(2),0j)
        np.testing.assert_allclose(t,a.reshape(-1))
        self.assertGreater(np.linalg.norm(b),0)

    def test_fitting_two_path_data(self):
        poses=[self.obs(name,x,2,z) for name,x,z in
               [('center',0,-.1125),('left',-.3,-.1125),('right',.3,-.1125),
                ('up',0,.1075),('down',0,-.2225)]]
        _,_,loss_direct,_=m.fit(poses,self.cfg,.34,self.bins,bounce=False,domain='vendor-raw')
        _,_,loss_floor,_=m.fit(poses,self.cfg,.34,self.bins,bounce=True,domain='vendor-raw')
        self.assertLess(loss_floor,.01)
        self.assertGreater(loss_direct,loss_floor+.015)

    def test_inversion_does_not_use_true_z(self):
        observation=self.obs('heldout',0,2,.0525)
        a,_,_=m.invert(observation,self.cfg,.34,self.bins,self.theta,self.gamma,domain='vendor-raw')
        observation.z_truth=-.2
        b,_,_=m.invert(observation,self.cfg,.34,self.bins,self.theta,self.gamma,domain='vendor-raw')
        self.assertEqual(a['z_est_m'],b['z_est_m'])

    def test_wrong_height_can_fit_well_without_being_identified(self):
        observation=self.obs('heldout',0,2,.0525)
        result,_,_=m.invert(observation,self.cfg,.34,self.bins,self.theta,self.gamma,domain='vendor-raw')
        self.assertGreater(result['score'],.99)
        self.assertLess(result['score_gap_nonlocal'],.02)

if __name__=='__main__':
    unittest.main()
