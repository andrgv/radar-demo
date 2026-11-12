"""Offline tests for tools/pitch_sweep.py; no radar hardware required."""
import unittest
from types import SimpleNamespace
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import sys
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import pitch_sweep as s
from radar.config import Config


class PitchGeometryTests(unittest.TestCase):
    def setUp(self):
        self.config=Config(geometry_mm=[[0,0],[0,2.35],[-2.35,0]],
                           carrier_hz=60e9, sample_rate_hz=5e6,
                           slope_hz_s=33691406250000,
                           mount_roll_deg=90,
                           chirps=17,samples=64)
        self.config.validate()
        self.plan=s.new_plan('unused.json',2.0,0.7,0.7,0.0,90)
        s.validate_plan(self.plan,self.config)

    def test_bottom_edge_pivot_rotates_antenna(self):
        base=s.new_plan('unused.json',2.0,.34,.3925,0,90)
        fixed=s.apply_fixed_pivot(base,0.0,0.08,.1725)
        self.assertEqual(base['target_xyz_m'][2],.3925)  # original not changed
        self.assertAlmostEqual(fixed['target_xyz_m'][2],.1725)
        self.assertTrue(np.allclose(next(p for p in fixed['poses'] if p['name']=='pitch_plus0')['antenna_xyz_m'],[0,0,.34]))
        up=next(p for p in fixed['poses'] if p['name']=='pitch_plus15')
        down=next(p for p in fixed['poses'] if p['name']=='pitch_minus15')
        self.assertAlmostEqual(up['antenna_xyz_m'][1],-.08*np.sin(np.deg2rad(15)),places=8)
        self.assertAlmostEqual(up['antenna_xyz_m'][2],.34+.08*(np.cos(np.deg2rad(15))-1),places=8)
        self.assertAlmostEqual(down['antenna_xyz_m'][1],-up['antenna_xyz_m'][1],places=8)
        self.assertAlmostEqual(down['antenna_xyz_m'][2],up['antenna_xyz_m'][2],places=8)
        s.validate_plan(fixed,self.config)
        self.assertEqual(len(fixed['poses']),6)

    def test_pivot_forward_offset_and_repeat(self):
        base=s.new_plan('unused.json',2.0,.34,.3925,0,90)
        corrected=s.apply_fixed_pivot(base,.015,.08,.1725,antenna_zero_height_m=.35)
        plus10=next(p for p in corrected['poses'] if p['name']=='pitch_plus10')
        a=np.deg2rad(10)
        self.assertAlmostEqual(plus10['antenna_xyz_m'][1],.015*(np.cos(a)-1)-.08*np.sin(a))
        self.assertAlmostEqual(plus10['antenna_xyz_m'][2],.35+.015*np.sin(a)+.08*(np.cos(a)-1))
        zero=next(p for p in corrected['poses'] if p['name']=='pitch_plus0')
        repeat=next(p for p in corrected['poses'] if p['name']=='zero_repeat')
        self.assertEqual(zero['antenna_xyz_m'],repeat['antenna_xyz_m'])

    def test_invalid_pivot_geometry_rejected(self):
        for v in [0., -0.1, float('nan')]:
            with self.assertRaises(ValueError):
                s.apply_fixed_pivot(self.plan,0.,v,.1725)
        with self.assertRaises(ValueError):
            s.apply_fixed_pivot(self.plan,0.,.08,-.2)

    def test_box_midpoint_above_table_or_floor(self):
        self.assertAlmostEqual(s.bottle_midpoint_height(0),.1725)
        self.assertAlmostEqual(s.bottle_midpoint_height(.34),.5125)
        with self.assertRaises(ValueError): s.bottle_midpoint_height(-.01)

    def test_pitch_axis_sign(self):
        target=[0,2,.7];antenna=[0,0,.7]
        a,dist,e=s.planned_direction(target,antenna,15)
        self.assertAlmostEqual(dist,2)
        self.assertAlmostEqual(e,-15,places=5)
        b,_,e2=s.planned_direction(target,antenna,-15)
        self.assertAlmostEqual(e2,15,places=5)
        self.assertAlmostEqual(a[0],0)
        self.assertAlmostEqual(b[0],0)

    def test_translated_antenna_changes_direction(self):
        a,_,_=s.planned_direction([0,2,.7],[0,0,.7],0)
        b,_,_=s.planned_direction([0,2,.7],[0,0,.8],0)
        self.assertAlmostEqual(a[1],0)
        self.assertLess(b[1],0)

    def test_roll_rotates_rx_baselines(self):
        geo=self.config.array_geometry
        self.assertAlmostEqual(geo[1,1]-geo[0,1],0,places=6)
        self.assertAlmostEqual(geo[2,0]-geo[0,0],0,places=6)
        self.assertLess(geo[2,1],0)

    def test_roles(self):
        self.assertEqual(sum(p['role']=='train' for p in self.plan['poses']),3)
        self.assertEqual(sum(p['role']=='holdout' for p in self.plan['poses']),3)
        self.assertEqual(self.plan['poses'][-1]['name'],'zero_repeat')

    def test_invalid_pose_rejected(self):
        p=json.loads(json.dumps(self.plan));p['poses'][0]['antenna_xyz_m']=[0,2,.7]
        with self.assertRaises(ValueError):s.validate_plan(p,self.config)

    def test_model_phase_training_and_holdouts(self):
        offsets=np.radians([23,-37])
        rows=[]
        for p in self.plan['poses']:
            direction,_,_=s.planned_direction(self.plan['target_xyz_m'],p['antenna_xyz_m'],p['pitch_deg'])
            phase=s.wrap_rad(s.predicted_relative_phase(self.config,direction)+offsets)
            rows.append(dict(name=p['name'], role=p['role'],pitch_deg=p['pitch_deg'],
                             accepted=True,phase_deg=np.degrees(phase).tolist()))
        output=s.evaluate_model(rows,self.plan,self.config,'mixed',0,1.5)
        self.assertIsNone(output['reason'])
        self.assertEqual(output['heldout_accepted'],3)
        self.assertTrue(np.allclose(output['offsets_deg'],[23,-37],atol=.002))
        self.assertLess(max(output['heldout_phase_mae_deg']),.001)
        for p in output['poses']:
            if p['role']=='holdout':
                self.assertAlmostEqual(p['estimated_z_m'],.7,delta=.005)
                self.assertFalse(p['ambiguous'])

    def test_holdout_corruption_not_used_in_calibration(self):
        offsets=np.radians([23,-37])
        rows=[]
        for p in self.plan['poses']:
            direction,_,_=s.planned_direction(self.plan['target_xyz_m'],p['antenna_xyz_m'],p['pitch_deg'])
            phase=s.wrap_rad(s.predicted_relative_phase(self.config,direction)+offsets)
            if p['name']=='pitch_minus10':phase[1]=s.wrap_rad(phase[1]+np.radians(28))
            rows.append(dict(name=p['name'],role=p['role'],pitch_deg=p['pitch_deg'],
                             accepted=True,phase_deg=np.degrees(phase).tolist()))
        output=s.evaluate_model(rows,self.plan,self.config,'mixed',0,1.5)
        self.assertTrue(np.allclose(output['offsets_deg'],[23,-37],atol=.002))
        test=next(p for p in output['poses'] if p['name']=='pitch_minus10')
        self.assertGreater(abs(test['phase_residual_deg'][1]),27)

    def test_no_fit_weak_training(self):
        rows=[]
        for p in self.plan['poses']:
            rows.append(dict(name=p['name'],role=p['role'],pitch_deg=p['pitch_deg'],
                             accepted=p['role']=='holdout',phase_deg=[0,0]))
        result=s.evaluate_model(rows,self.plan,self.config,'mixed',0,1.5)
        self.assertIn('Only 0 accepted',result['reason'])
        self.assertIsNone(result['offsets_deg'])

    def test_mixed_raw_equivalence(self):
        d=np.array([.05,-.15])
        mixed=s.signature(self.config,d,'mixed')
        raw=s.signature(self.config,d,'raw')
        self.assertTrue(np.allclose(self.config.angle_matrix@raw,mixed))



class SyntheticCapturePipelineTest(unittest.TestCase):
    def test_paired_background_synthetic_phase_and_height(self):
        # Exercises recording replay -> per-pitch background subtraction -> fixed-bin
        # phase fitting -> strictly held-out height inversion. Synthetic direct path.
        from radar.storage import Recorder
        from radar.protocol import Frame
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'pitch-data';root.mkdir()
            cfg=Config(geometry_mm=[[0,0],[0,2.35],[-2.35,0]],
                       carrier_hz=60e9,sample_rate_hz=5e6,
                       slope_hz_s=33691406250000,
                       mount_roll_deg=90,samples=64,chirps=17,snr_db=12,
                       angle_matrix_real=[[.5,0,0],[.05,-.44,0],[-.06,0,-.16]],
                       angle_matrix_imag=[[0,0,0],[.1,.16,0],[.02,0,-.46]])
            cfg.save(root/'config.json')
            plan=s.new_plan('unused.json',2.0,.7,.7,0,90)
            s.validate_plan(plan,cfg)
            (root/'pitch_plan.json').write_text(json.dumps(plan))
            k=6;theta=2*np.pi*k*np.arange(cfg.samples)/cfg.samples
            offset=np.exp(1j*np.radians([0,21,-18]))
            bg_amp=np.array([140*np.exp(1j*.2),100*np.exp(1j*1.0),110*np.exp(-1j*1.2)])
            noise_gen=np.random.default_rng(1123)
            for p in plan['poses']:
                d,_,_=s.planned_direction(plan['target_xyz_m'],p['antenna_xyz_m'],p['pitch_deg'])
                steering=s.signature(cfg,d,'mixed')*offset
                raw_sig=np.linalg.solve(cfg.angle_matrix,steering)
                for stage in ['background','target']:
                    with Recorder(root/f'{stage}_{p["name"]}',cfg) as rec:
                        for n in range(30):
                            target=(1200*raw_sig) if stage=='target' else np.zeros(3,complex)
                            base=np.real((bg_amp+target)[None,:]*np.exp(1j*theta[:,None]))
                            base+=noise_gen.normal(0,2,base.shape)
                            adc=np.clip(np.rint(32768+base),1,65534).astype('uint16')
                            adc=np.broadcast_to(adc,(cfg.chirps,cfg.samples,3)).copy()
                            rec.write(Frame(sequence=n+1,timestamp_us=n*100000,profile_id=cfg.profile_id,adc=adc))
            rows=[s.pose_measurement(root,p,cfg,'mixed') for p in plan['poses']]
            self.assertTrue(all(r['accepted'] for r in rows),[(r['name'],r.get('reason'),r.get('contrast_db')) for r in rows])
            result=s.evaluate_model(rows,plan,cfg,'mixed',.2,1.2)
            s.do_analyze(SimpleNamespace(recording=str(root),output=str(Path(td)/'reports'),
                                         domain='mixed',z_min=.2,z_max=1.2, export_pilot=str(Path(td)/'pilot.json')))
            self.assertTrue((Path(td)/'pilot.json').exists())
            self.assertFalse(Config.load(Path(td)/'pilot.json').verified)
            self.assertTrue((Path(td)/'reports'/'summary.json').exists())
            self.assertTrue((Path(td)/'reports'/'phase_vs_pitch.png').exists())
            self.assertTrue((Path(td)/'reports'/'height_inversion.png').exists())
            self.assertIsNone(result['reason'])
            self.assertLess(max(result['heldout_phase_mae_deg']),.7)
            for row in result['poses']:
                if row['role']=='holdout':
                    self.assertAlmostEqual(row['estimated_z_m'],.7,delta=.025)
                    self.assertFalse(row['ambiguous'])


class SerialCaptureTests(unittest.TestCase):
    def test_clean_stream_start_sequence_and_warmup(self):
        from radar.config import Config
        cfg=Config()
        class FakeSerial:
            def __init__(self,*args,**kwargs):
                self.writes=[];self.resets=0
            def write(self,data):self.writes.append(data)
            def flush(self):pass
            def reset_input_buffer(self):self.resets+=1
            def close(self):pass
        class FakeParser:
            bad_crc=0;bad_headers=0;gaps=0;restarts=0;discarded_bytes=0
        class FakeSource:
            def __init__(self,config):
                self.config=config;self.serial=None;self.pending=[]
                self.parser=FakeParser();self.reads=0;self.transport_recorder=None
            def read(self):
                self.reads+=1
                return SimpleNamespace(profile_id=self.config.profile_id,
                    adc=np.zeros((self.config.chirps,self.config.samples,3)))
            def close(self):self.serial.write(b'c')
        ticks=iter(np.arange(0,10,.2))
        with patch.object(s,'Source',FakeSource), patch.object(s.serial,'Serial',FakeSerial), \
             patch.object(s.time,'sleep',lambda _:None), \
             patch.object(s.time,'monotonic',lambda : float(next(ticks))):
            source, startup=s.start_synchronized_source(cfg,'FAKE',warmup_seconds=.6)
        self.assertEqual(source.serial.writes,[b'c',b'B'])
        self.assertEqual(source.serial.resets,1)
        self.assertGreaterEqual(startup['valid_frames'],2)
        self.assertEqual(startup['bad_crc'],0)
        self.assertEqual(source.pending,[])

    def test_failed_capture_archived_then_clean_retry(self):
        calls=[]
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'target_pitch_minus15'
            def fake_capture_once(p,*args):
                calls.append(1)
                Path(p).mkdir()
                (Path(p)/'frames.grd').write_bytes(b'audit' if len(calls)==1 else b'good')
                if len(calls)==1:
                    raise s.TransportIntegrityError('CRC error during capture')
            with patch.object(s,'_capture_once',fake_capture_once), \
                 patch.object(s.time,'sleep',lambda _:None):
                s.capture(path,None,'FAKE',6,{},retries=2)
            self.assertEqual(len(calls),2)
            self.assertEqual((path/'frames.grd').read_bytes(),b'good')
            self.assertEqual((Path(td)/'target_pitch_minus15__FAILED_attempt1'/'frames.grd').read_bytes(),b'audit')

    def test_no_bad_capture_ever_accepted_after_retry_limit(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'capture'
            def always_fail(p,*args):
                Path(p).mkdir()
                raise s.TransportIntegrityError('loss')
            with patch.object(s,'_capture_once',always_fail), \
                 patch.object(s.time,'sleep',lambda _:None):
                with self.assertRaises(RuntimeError):
                    s.capture(path,None,'FAKE',6,{},retries=1)
            self.assertFalse(path.exists())
            self.assertTrue((Path(td)/'capture__FAILED_attempt1').exists())
            self.assertTrue((Path(td)/'capture__FAILED_attempt2').exists())

class BufferedCaptureAndResumeTests(unittest.TestCase):
    def test_capture_reads_completely_before_disk_writes(self):
        from radar.protocol import Frame
        class FakeParser:
            bad_crc=0;bad_headers=0;gaps=0;restarts=0;discarded_bytes=0
            def __init__(self):self.seq=0
            def feed(self,data):
                self.seq+=1
                return [Frame(sequence=self.seq,timestamp_us=self.seq*100000,
                    profile_id=cfg.profile_id,
                    adc=np.ones((cfg.chirps,cfg.samples,3),dtype='uint16'))]
        class FakeSerial:
            in_waiting=2048
            closed=False
            def read(self,n):
                self.serial_reads += 1
                if self.closed:raise AssertionError('read from closed serial')
                return b'hello'
            serial_reads=0
        class FakeSource:
            def __init__(self):self.serial=FakeSerial();self.parser=FakeParser()
            def close(self):self.serial.closed=True
        fake_source=FakeSource()
        class FakeRecorder:
            def __init__(self,path,config,metadata):
                self.path=Path(path);self.path.mkdir();self.count=0
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def write_transport(self,data,parser):
                self.assert_closed()
                self.wire=data
            def write(self,frame):
                self.assert_closed()
                self.count+=1
            def assert_closed(self):
                if not fake_source.serial.closed:
                    raise AssertionError('Disk writes happened while serial was streaming')
        cfg=Config()
        with tempfile.TemporaryDirectory() as td:
            ticks=iter(np.arange(0,20,.1))
            with patch.object(s,'start_synchronized_source',return_value=(fake_source,{'valid_frames':10})), \
                 patch.object(s,'Recorder',FakeRecorder), \
                 patch.object(s.time,'monotonic',lambda:float(next(ticks))):
                s._capture_once(Path(td)/'capture',cfg,'FAKE',6,{})
            stats=json.loads((Path(td)/'capture'/'transport_summary.json').read_text())
            self.assertGreaterEqual(stats['valid_frames'],50)
            self.assertEqual(stats['capture_strategy'],'in_memory_buffered')
            self.assertEqual(stats['bad_crc'],0)
            self.assertTrue(fake_source.serial.closed)
            self.assertEqual(fake_source.serial.serial_reads,stats['valid_frames'])

    def test_resumed_run_skips_previously_completed_backgrounds(self):
        with tempfile.TemporaryDirectory() as td:
            parent=Path(td)
            cfgpath=parent/'config.json'
            cfg=Config()
            cfg.save(cfgpath)
            plan=s.new_plan(str(cfgpath),2,.337,.2295,0,90)
            effective=replace(cfg,mount_roll_deg=90,verified=False,
                              calibration_id='pitch-experiment-UNVERIFIED').validate()
            s.validate_plan(plan,effective)
            planpath=parent/'plan.json';planpath.write_text(json.dumps(plan))
            root=parent/'recordings';root.mkdir()
            (root/'pitch_plan.json').write_text(json.dumps(plan))
            effective.save(root/'config.json')
            for name in ['pitch_minus15','pitch_minus10','pitch_plus0']:
                (root/f'background_{name}').mkdir()
            calls=[]
            def fake_capture(path,*args,**kwargs):
                path=Path(path);calls.append(path.name);path.mkdir()
            with patch.object(s,'verify_existing_capture',return_value=61), \
                 patch.object(s,'capture',side_effect=fake_capture), \
                 patch('builtins.input',return_value=''), \
                 patch.object(s.time,'sleep',lambda _:None):
                s.do_record(SimpleNamespace(plan=str(planpath),output=str(root),
                                            port='FAKE',seconds=6,retries=2,resume=True))
            self.assertEqual(len(calls),9)
            self.assertNotIn('background_pitch_minus15',calls)
            self.assertNotIn('background_pitch_minus10',calls)
            self.assertNotIn('background_pitch_plus0',calls)
            self.assertIn('background_pitch_plus10',calls)
            self.assertIn('target_zero_repeat',calls)

    def test_existing_failure_archives_get_unique_names(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'background_pitch_plus10'
            (Path(td)/'background_pitch_plus10__FAILED_attempt1').mkdir()
            def fake_capture_once(p,*args):
                Path(p).mkdir()
                raise s.TransportIntegrityError('corrupt wire')
            with patch.object(s,'_capture_once',fake_capture_once), \
                 patch.object(s.time,'sleep',lambda _:None):
                with self.assertRaises(RuntimeError):
                    s.capture(path,None,'FAKE',6,{},retries=0)
            self.assertTrue((Path(td)/'background_pitch_plus10__FAILED_attempt2').exists())


if __name__=='__main__': unittest.main()
