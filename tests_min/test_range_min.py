import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from radar.protocol import Frame,Parser,encode
from radar_min.core import Config,Baseline,Detector,power
from radar_min.__main__ import main,stream,read_recording

C=Config()
def frame(seq,k=2,amplitude=0):
    x=32768+amplitude*np.cos(2*np.pi*k*np.arange(C.samples)/C.samples)+np.random.default_rng(seq).normal(0,2,C.samples)
    adc=np.broadcast_to(x[None,:,None],(C.chirps,C.samples,3)).copy().astype('uint16')
    return Frame(seq,(seq*100000)&0xffffffff,C.profile_id,adc)

def baseline():
    return Baseline.fit([frame(i) for i in range(1,31)],C)

class RangeTests(unittest.TestCase):
    def test_fft_known_frequency_amplitude_and_dc(self):
        p=power(frame(1,k=3,amplitude=1000),C)
        self.assertEqual(int(np.argmax(p)),3)
        self.assertAlmostEqual(float(p[3]),1e6,delta=2000)
        flat=frame(1,amplitude=0);flat.adc[:]=32768
        np.testing.assert_equal(power(flat,C),0)
        self.assertAlmostEqual(C.spacing_m,0.34758545855)

    def test_malformed_config_adc_profile(self):
        for kwargs in ({'sample_rate_hz':float('nan')},{'discard_chirps':17},{'min_bin':0},{'max_bin':32}):
            with self.assertRaises(ValueError):Config(**kwargs)
        f=frame(1);f.profile_id=0
        with self.assertRaises(ValueError):power(f,C)
        f=frame(1);f.adc[0:,:,:]=0
        with self.assertRaises(ValueError):power(f,C)

    def test_persistence_and_immediate_disappearance(self):
        d=Detector(baseline())
        self.assertFalse(d.update(frame(31,amplitude=1000))['target_detected'])
        self.assertFalse(d.update(frame(32,amplitude=1000))['target_detected'])
        hit=d.update(frame(33,amplitude=1000))
        self.assertTrue(hit['target_detected']);self.assertEqual(hit['range_bin'],2)
        self.assertIsNone(hit['range_m']);self.assertFalse(hit['calibrated'])
        miss=d.update(frame(34))
        self.assertFalse(miss['target_detected']);self.assertIsNone(miss['range_bin'])
        self.assertFalse(d.update(frame(35,amplitude=1000))['target_detected'])

    def test_new_bin_does_not_keep_previous_detection(self):
        d=Detector(baseline())
        for i in range(31,34):d.update(frame(i,amplitude=1000))
        moved=d.update(frame(34,k=4,amplitude=1000))
        self.assertFalse(moved['target_detected']);self.assertIsNone(moved['range_bin'])

    def test_gap_duplicate_and_restart(self):
        d=Detector(baseline())
        for i in range(31,34):d.update(frame(i,amplitude=1000))
        self.assertEqual(d.update(frame(35,amplitude=1000))['reason'],'sequence_gap')
        self.assertFalse(d.update(frame(36,amplitude=1000))['target_detected'])
        self.assertEqual(d.update(frame(36))['reason'],'baseline_invalidated_by_restart')
        self.assertEqual(d.update(frame(37))['reason'],'baseline_invalidated_by_restart')

    def test_timestamp_and_device_error(self):
        d=Detector(baseline());d.update(frame(1))
        f=frame(2);f.timestamp_us+=500000
        self.assertEqual(d.update(f)['reason'],'timestamp_gap')
        d=Detector(baseline());d.update(frame(1));f=frame(2);f.errors=1
        self.assertEqual(d.update(f)['reason'],'device_counter_changed')

    def test_wire_chunks_crc_resync_wrap(self):
        a=frame(1);a.sequence=0xffffffff
        b=frame(2);b.sequence=0
        packet=bytearray(encode(a));packet[70]^=1
        wire=b'junk'+packet+encode(a)+encode(b);p=Parser();decoded=[]
        for start in range(0,len(wire),37):decoded.extend(p.feed(wire[start:start+37]))
        self.assertEqual([f.sequence for f in decoded],[0xffffffff,0]);self.assertEqual(p.bad_crc,1)
        self.assertEqual(p.gaps,0);np.testing.assert_equal(decoded[0].adc,a.adc)

    def test_baseline_roundtrip_and_holdout_overlap_blocked(self):
        from radar.storage import Recorder
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);rec=root/'empty'
            with Recorder(rec,C) as r:
                for i in range(1,62):r.write(frame(i))
            with patch('sys.stdout',new_callable=io.StringIO):
                self.assertEqual(main(['baseline',str(rec),str(root/'b.json')]),0)
            b=Baseline.load(root/'b.json');self.assertEqual(b.config.fingerprint,C.fingerprint)
            with patch('sys.stderr',new_callable=io.StringIO):
                self.assertEqual(main(['replay',str(rec),'--baseline',str(root/'b.json')]),2)
            self.assertEqual(len(read_recording(rec)[1]),61)

    def test_baseline_does_not_fit_holdout(self):
        b=baseline();before=b.threshold_db.copy();d=Detector(b)
        for i in range(31,40):d.update(frame(i,amplitude=10000))
        np.testing.assert_equal(before,b.threshold_db)

    def test_serial_capture_preserves_corruption_and_replays(self):
        bad=bytearray(encode(frame(1)));bad[55]^=1
        chunks=[bytes(bad),encode(frame(1)),encode(frame(2))]
        class Serial:
            in_waiting=0
            def __init__(self,*a,**kw):self.commands=[];self.closed=False
            def reset_input_buffer(self):pass
            def write(self,b):self.commands.append(b)
            def read(self,n):return chunks.pop(0) if chunks else b''
            def close(self):self.closed=True
        serial=Serial()
        ticks=iter(np.arange(0,5,.05))
        with tempfile.TemporaryDirectory() as t, patch('radar_min.__main__.time.monotonic',side_effect=lambda:float(next(ticks))), patch('radar_min.__main__.emit'):
            out=Path(t)/'capture'
            stream('fake',C,out,.4,serial_factory=lambda *a,**kw:serial)
            self.assertEqual(serial.commands,[b'B',b'c']);self.assertTrue(serial.closed)
            self.assertEqual((out/'serial-wire.bin').read_bytes(),bytes(bad)+encode(frame(1))+encode(frame(2)))
            self.assertEqual(len(read_recording(out)[1]),2)
            self.assertEqual(json.loads((out/'capture-summary.json').read_text())['serial']['bad_crc'],1)

    def test_serial_timeout_clears_and_closes(self):
        class Serial:
            in_waiting=0
            def reset_input_buffer(self):pass
            def write(self,b):pass
            def read(self,n):return b''
            def close(self):self.closed=True
        ser=Serial();d=Detector(baseline());d.hits=3
        ticks=iter([0,0,.2,.3,1.2])
        with tempfile.TemporaryDirectory() as t, patch('radar_min.__main__.time.monotonic',side_effect=lambda:next(ticks)),patch('radar_min.__main__.emit'):
            with self.assertRaises(TimeoutError):stream('fake',C,Path(t)/'capture',5,d,serial_factory=lambda *a,**kw:ser)
            self.assertEqual(d.hits,0);self.assertTrue(ser.closed)

if __name__=='__main__':unittest.main()
