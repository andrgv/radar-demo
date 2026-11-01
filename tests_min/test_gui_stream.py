import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import numpy as np
from radar.protocol import Frame,encode
from radar_min.core import Config
from radar_min.__main__ import stream,read_recording
from radar_min.gui import display_values,range_displayable


class GuiStreamTests(unittest.TestCase):
    def test_search_boundary_preserves_presence_but_not_distance(self):
        for distance in [.15,1.5]:
            r=dict(target_detected=True,experimental_range_m=distance,fit_boundary=True)
            self.assertFalse(range_displayable(r))
            self.assertEqual(display_values(r,True)[0],'—')
            self.assertIn('distance unresolved',display_values(r,True)[1])
            self.assertTrue(r['target_detected'])
            self.assertEqual(r['experimental_range_m'],distance)

    def test_rejected_and_stale_estimate_never_main_readout(self):
        r=dict(target_detected=True,experimental_range_m=.4,excess_db=7,reason='spectral_change_uncalibrated')
        self.assertEqual(display_values(r,True)[0],'40.0 cm')
        self.assertEqual(display_values(r,False)[0],'—')
        r['target_detected']=False
        self.assertEqual(display_values(r,True)[0],'—')
        self.assertIn('candidate only',display_values(r,True)[1])

    def test_stop_saves_raw_and_observer_fields_then_closes(self):
        c=Config();f=Frame(1,100000,c.profile_id,np.full((17,64,3),12000,dtype=np.uint16));packet=encode(f)
        class Serial:
            in_waiting=0
            def __init__(self):self.commands=[];self.closed=False
            def reset_input_buffer(self):pass
            def write(self,b):self.commands.append(b)
            def read(self,n):return packet
            def close(self):self.closed=True
        ser=Serial();stop=threading.Event()
        def observe(frame,reading):reading['experimental_range_m']=.4;stop.set()
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'recording'
            stream('fake',c,out,10,serial_factory=lambda *a,**kw:ser,observer=observe,stop_event=stop,quiet=True)
            self.assertEqual((out/'serial-wire.bin').read_bytes(),packet)
            self.assertEqual(len(read_recording(out)[1]),1)
            self.assertEqual(json.loads((out/'readings.jsonl').read_text())['experimental_range_m'],.4)
        self.assertTrue(ser.closed);self.assertEqual(ser.commands,[b'B',b'c'])

    def test_timeout_observer_receives_clear(self):
        class Serial:
            in_waiting=0
            def reset_input_buffer(self):pass
            def write(self,b):pass
            def read(self,n):return b''
            def close(self):pass
        updates=[];ticks=iter([0,0,.2,.3,1.2])
        with tempfile.TemporaryDirectory() as t,patch('radar_min.__main__.time.monotonic',side_effect=lambda:next(ticks)):
            with self.assertRaises(TimeoutError):stream('fake',Config(),Path(t)/'r',5,serial_factory=lambda *a,**kw:Serial(),observer=lambda f,r:updates.append((f,r)),quiet=True)
        self.assertIsNone(updates[-1][0]);self.assertFalse(updates[-1][1]['target_detected'])
        self.assertEqual(updates[-1][1]['received_bytes'],0)
        self.assertIn('No serial bytes',updates[-1][1]['detail'])

    def test_timeout_distinguishes_corrupt_input_from_stalled_stream(self):
        c=Config();packet=encode(Frame(1,100000,c.profile_id,np.full((17,64,3),12000,dtype=np.uint16)))
        for payload,expected_frames,detail in [(b'garbage',0,'no complete radar frame'),(packet,1,'Stream stalled after 1 frames')]:
            class Serial:
                in_waiting=0
                def __init__(self):self.parts=iter([payload,b'']);self.closed=False
                def reset_input_buffer(self):pass
                def write(self,b):pass
                def read(self,n):return next(self.parts)
                def close(self):self.closed=True
            ser=Serial();updates=[];ticks=iter([0,0,.2,.3,1.3])
            with tempfile.TemporaryDirectory() as t,patch('radar_min.__main__.time.monotonic',side_effect=lambda:next(ticks)):
                out=Path(t)/'r'
                with self.assertRaisesRegex(TimeoutError,detail):
                    stream('fake',c,out,5,serial_factory=lambda *a,**kw:ser,observer=lambda f,r:updates.append((f,r)),quiet=True)
                summary=json.loads((out/'capture-summary.json').read_text())
                self.assertEqual(summary['received_bytes'],len(payload))
                self.assertEqual(summary['frames'],expected_frames)
                self.assertEqual((out/'serial-wire.bin').read_bytes(),payload)
            self.assertTrue(ser.closed)
            self.assertFalse(updates[-1][1]['target_detected'])


if __name__=='__main__':unittest.main()
