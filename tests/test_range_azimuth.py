from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from radar.config import Config
from radar.angle_lab import raw_model_phase
from radar.protocol import Frame
from radar import range_azimuth as ra

class RangeAzimuthTests(unittest.TestCase):
    def setUp(self):
        self.cfg=Config(sample_rate_hz=5e6, slope_hz_s=33691406250000,
                        geometry_mm=[[0,0],[0,2.35],[-2.35,0]], mount_roll_deg=90)
        self.xyz=[0,2,-.1125]
        self.phase=raw_model_phase(self.cfg,self.xyz)[0]
    def estimator(self):
        return ra.RangeAzimuth(self.cfg,self.phase,self.xyz,min_range=1.5,max_range=2.5)
    def test_simultaneous_range_and_azimuth(self):
        for angle in [-12,-4,0,4,12]:
            cfg=self.cfg;r=cfg.ranges[6];h=np.sqrt(r*r-self.xyz[2]**2)
            xyz=np.array([h*np.sin(np.deg2rad(angle)),h*np.cos(np.deg2rad(angle)),self.xyz[2]])
            signature=np.linalg.solve(cfg.angle_matrix,np.exp(2j*np.pi*cfg.array_geometry@xyz[[0,2]]/r))*cfg.gains
            s=np.ones((16,33,3),complex)*1e-4
            s[:,5:8]=np.array([.25,1,.25])[None,:,None]*signature
            frame=Frame(1,0,cfg.profile_id,np.zeros((17,64,3)))
            with patch.object(ra,'range_fft',return_value=s):
                result,_=self.estimator().update(frame)
            self.assertEqual(result['state'],'CANDIDATE')
            self.assertAlmostEqual(result['range_m'],r,places=6)
            self.assertAlmostEqual(result['azimuth_deg'],angle,delta=.06)
            self.assertAlmostEqual(result['x_m'],xyz[0],delta=.003)
    def test_empty_does_not_produce_azimuth(self):
        f=Frame(1,0,self.cfg.profile_id,np.zeros((17,64,3)))
        result,_=self.estimator().update(f)
        self.assertEqual(result['state'],'NO_TARGET')
        self.assertIsNone(result['azimuth_deg'])
    def test_incoherent_peak_is_rejected(self):
        s=np.ones((16,33,3),complex)*.001;s[:,6]=1
        s[:,6,1]=np.exp(2j*np.pi*np.arange(16)/16)
        f=Frame(1,0,self.cfg.profile_id,np.zeros((17,64,3)))
        with patch.object(ra,'range_fft',return_value=s):r,_=self.estimator().update(f)
        self.assertEqual(r['state'],'WEAK');self.assertIsNone(r['azimuth_deg'])
    @unittest.skipUnless(Path('recordings/box-angle-01/center/frames.grd').is_file(), 'local recordings required')
    def test_rejects_bad_reference(self):
        self.cfg=Config.load('configs/exploratory-roll90-phase.json')
        with self.assertRaisesRegex(ValueError,'quality'):
            ra.load_reference('recordings/box-angle-01/center',self.xyz,self.cfg)
    @unittest.skipUnless(Path('recordings/box-angle-01/center_repeat/frames.grd').is_file(), 'local recordings required')
    def test_recorded_checks(self):
        self.cfg=Config.load('configs/exploratory-roll90-phase.json')
        phase=ra.load_reference('recordings/box-angle-01/center_repeat',self.xyz,self.cfg)
        for name,truth in [('check_left',-4.289),('check_right',4.289)]:
            root=Path('recordings/box-angle-01')/name
            est=ra.RangeAzimuth(self.cfg,phase,self.xyz,min_range=1.5,max_range=2.5,window=50)
            bg=ra.load_background(root,self.cfg)
            for f in ra.replay(root):r,_=est.update(f,bg)
            self.assertEqual(r['state'],'CANDIDATE')
            self.assertAlmostEqual(r['azimuth_deg'],truth,delta=.25)
            self.assertLess(abs(r['range_m']-2),.16)

    def test_discontinuity_resets_average(self):
        est=self.estimator()
        for seq in [1,2,5]:
            r,_=est.update(Frame(seq,0,self.cfg.profile_id,np.zeros((17,64,3))))
        self.assertEqual(r['averaged_frames'],1)
    def test_profile_mismatch(self):
        with self.assertRaisesRegex(ValueError,'incompatible'):
            self.estimator().update(Frame(1,0,0,np.zeros((17,64,3))))

if __name__=='__main__':unittest.main()
