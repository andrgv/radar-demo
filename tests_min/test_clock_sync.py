import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import numpy as np

from radar.protocol import Frame,encode
from radar_min.clock_sync import ClockSync
from radar_min.core import Config
from radar_min.cfar import CfarDetector
from radar_min.__main__ import stream


class ClockTests(unittest.TestCase):
    def train(self,rate=.993):
        sync=ClockSync()
        for i in range(251):r=sync.update(i*100000,i*.1*rate)
        self.assertEqual(r['state'],'frozen')
        return sync

    def test_both_clock_rate_directions_remain_valid_for_an_hour(self):
        for rate in [.993,1.007]:
            sync=self.train(rate)
            for i in range(251,36001):r=sync.update((i*100000)&0xffffffff,i*.1*rate)
            self.assertIsNone(r['reason'])
            self.assertAlmostEqual(r['host_seconds_per_device_second'],rate,places=8)
            self.assertLess(abs(r['residual_s']),1e-6)
            self.assertGreater(abs(r['raw_residual_s']),20)
            self.assertLessEqual(r['fit_samples'],202)

    def test_rate_freezes_and_step_delay_cannot_be_learned_away(self):
        sync=self.train();rate=sync.rate
        r=sync.update(25100000,25.1*.993+.6)
        self.assertEqual(r['reason'],'host_sensor_timing_mismatch')
        for i in range(252,501):r=sync.update(i*100000,i*.1*.993+.6)
        self.assertEqual(sync.rate,rate)
        self.assertEqual(r['state'],'invalid')
        self.assertIsNotNone(sync.update(50100000,50.1*.993)['reason'])

    def test_growing_delay_after_freeze_still_rejects(self):
        sync=self.train()
        for i in range(251,1001):
            r=sync.update(i*100000,i*.1*.993+max(0,i*.1-25)*.01)
        self.assertEqual(r['reason'],'host_sensor_timing_mismatch')

    def test_out_of_bounds_and_jittery_startup_rejected(self):
        sync=ClockSync()
        for i in range(211):r=sync.update(i*100000,i*.1*1.022)
        self.assertEqual(r['reason'],'clock_rate_out_of_bounds')
        sync=ClockSync()
        for i in range(211):r=sync.update(i*100000,i*.1+.06*(i%2))
        self.assertEqual(r['reason'],'clock_fit_unstable')
        fit=r['fit_diagnostics']
        self.assertGreater(fit['p95_residual_s'],fit['p95_limit_s'])
        self.assertEqual(fit['p95_limit_s'],.05)
        self.assertEqual(fit['max_limit_s'],.1)

    def test_wrap_supported_but_restart_duplicate_and_host_reversal_fail(self):
        sync=ClockSync();base=0xffffffff-500000
        for i in range(251):r=sync.update((base+i*100000)&0xffffffff,i*.1*.993)
        self.assertEqual(r['state'],'frozen')
        self.assertIsNone(r['reason'])
        self.assertEqual(sync.update((base+250*100000)&0xffffffff,25.1)['reason'],'clock_restart_or_duplicate')
        sync=self.train()
        self.assertEqual(sync.update(1000,25.1)['reason'],'clock_restart_or_duplicate')
        sync=self.train()
        self.assertEqual(sync.update(25100000,25.1*.993,restart=True)['reason'],'clock_restart_or_duplicate')
        sync=self.train()
        self.assertEqual(sync.update(25100000,0)['reason'],'host_clock_went_backwards')

    def test_queued_or_invalid_frames_do_not_train_clock(self):
        sync=ClockSync()
        for i in range(311):r=sync.update(i*100000,i*.1,eligible=False)
        self.assertEqual(r['reason'],'clock_fit_unavailable')
        self.assertEqual(r['fit_samples'],0)

    def test_stream_queued_burst_is_preserved_but_never_used_for_clock_fit(self):
        c=Config();adc=np.full((c.chirps,c.samples,3),32768,dtype='uint16')
        packet=b''.join(encode(Frame(i,i*100000,c.profile_id,adc)) for i in range(1,4))
        class Serial:
            in_waiting=0
            def reset_input_buffer(self):pass
            def write(self,value):pass
            def close(self):pass
            def read(self,n):return packet
        stop=threading.Event();updates=[]
        def observe(frame,reading):
            updates.append(dict(reading))
            if frame.sequence==3:stop.set()
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'capture'
            summary=stream('fake',c,out,5,CfarDetector(c),serial_factory=lambda *a,**kw:Serial(),
                observer=observe,stop_event=stop,quiet=True)
            self.assertEqual((out/'serial-wire.bin').read_bytes(),packet)
        self.assertEqual(summary['rejected_frames'],3)
        self.assertTrue(all(r['reason']=='serial_backlog' and not r['target_detected'] for r in updates))
        self.assertTrue(all(r['clock_sync']['fit_samples']==0 for r in updates))

    def test_stream_long_skew_and_delayed_delivery_keep_raw_and_clear_readout(self):
        c=Config()
        wave=32768+1000*np.cos(2*np.pi*2*np.arange(c.samples)/c.samples)
        adc=np.broadcast_to(wave[None,:,None],(c.chirps,c.samples,3)).astype('uint16').copy()
        for inject_delay in [False,True]:
            class Serial:
                in_waiting=0
                def __init__(self):self.index=0;self.now=0.;self.closed=False;self.commands=[]
                def reset_input_buffer(self):pass
                def write(self,value):self.commands.append(value)
                def close(self):self.closed=True
                def read(self,n):
                    self.index+=1
                    self.now=self.index*.1*.993+(.6 if inject_delay and self.index>=1000 else 0)
                    return encode(Frame(self.index,self.index*100000,c.profile_id,adc))
            ser=Serial();stop=threading.Event();last=[]
            def observe(frame,reading):
                if ser.index==1500:last.append(dict(reading));stop.set()
            with tempfile.TemporaryDirectory() as tmp,patch('radar_min.__main__.time.monotonic',side_effect=lambda:ser.now):
                out=Path(tmp)/'capture'
                summary=stream('fake',c,out,200,CfarDetector(c),serial_factory=lambda *a,**kw:ser,
                    observer=observe,stop_event=stop,quiet=True)
                metadata=json.loads((out/'metadata.json').read_text())
                self.assertEqual(metadata['clock_sync']['algorithm'],'bounded-startup-clock-v1')
                self.assertEqual(summary['frames'],1500)
                self.assertEqual((out/'serial-wire.bin').stat().st_size,1500*len(encode(Frame(1,100000,c.profile_id,adc))))
            if inject_delay:
                self.assertFalse(last[0]['target_detected']);self.assertIsNone(last[0]['experimental_range_m'])
                self.assertEqual(last[0]['reason'],'host_sensor_timing_mismatch')
                self.assertGreater(summary['rejected_frames'],0)
            else:
                self.assertTrue(last[0]['target_detected']);self.assertIsNotNone(last[0]['experimental_range_m'])
                self.assertEqual(summary['rejected_frames'],0)
                self.assertGreater(last[0]['raw_relative_timing_error_s'],1)
                self.assertLess(last[0]['relative_timing_error_s'],.001)
            self.assertTrue(ser.closed);self.assertEqual(ser.commands,[b'B',b'c'])


if __name__=='__main__':unittest.main()
