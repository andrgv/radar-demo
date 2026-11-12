from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import numpy as np

from radar.protocol import encode, wire_size
from radar.storage import replay
from radar_min.__main__ import stream
from radar_min.cfar_2d import CaCfar2D
from radar_min.range_doppler import RangeDoppler
from radar_min.rd_association import CandidateAssociator
from radar_min.rd_live import LiveRangeDoppler, feature_table_rows
from tests_min.test_range_doppler import C, tone


class LiveRDTests(unittest.TestCase):
    def test_live_adapter_matches_replay_algorithms_and_snapshot_is_immutable(self):
        live=LiveRangeDoppler(C)
        rd=RangeDoppler(C);cfar=CaCfar2D((16,33));association=CandidateAssociator(C)
        for seq in range(1,7):
            f=tone([(6,0,2000),(15,-.25,1000)],seq)
            if seq==4:f.flags=0
            reading=live.update(f)
            full,_,info=rd.update(f)
            if info['valid']:
                _,th,accepted,clusters=cfar.detect(full)
                report=association.update(f,full,th,accepted,clusters)
                np.testing.assert_array_equal(live.snapshot.full_power,full)
                np.testing.assert_allclose(live.snapshot.threshold_power,th,equal_nan=True)
                self.assertEqual(live.snapshot.sequence,seq)
                with self.assertRaises(ValueError):live.snapshot.full_power[0,0]=0
            else:
                report=association.update(f,None,None,None,[],valid=False,reason=info['reason'])
                self.assertIsNone(live.snapshot)
            self.assertEqual(reading['association'],report)
            json.dumps(reading,allow_nan=False)

    def test_reject_advances_guards_and_clears_without_recycling_ids(self):
        live=LiveRangeDoppler(C)
        for seq in (1,2,3):reading=live.update(tone([(6,0,2000)],seq))
        ids={t['track_id']for t in reading['association']['tracks']}
        rejected=live.reject_frame(tone([(6,0,2000)],4),'serial_backlog')
        self.assertFalse(rejected['valid']);self.assertIsNone(live.snapshot)
        self.assertEqual(rejected['association']['tracks'],[])
        self.assertTrue(all(t['measurement']is None for t in rejected['association']['ended_tracks']))
        recovered=live.update(tone([(6,0,2000)],5))
        self.assertTrue(recovered['valid'])
        self.assertNotEqual(recovered['reason'],'sequence_gap')
        self.assertTrue(ids.isdisjoint({t['track_id']for t in recovered['association']['tracks']}))
        live.clear();self.assertIsNone(live.snapshot);self.assertEqual(live.associator.tracks,[])

    def test_table_only_shows_fresh_confirmed_current_points(self):
        live=LiveRangeDoppler(C)
        for seq in (1,2,3):reading=live.update(tone([(6,0,2000)],seq))
        rows=feature_table_rows(reading,C)
        measured=[values for state,values in rows if state=='measured']
        self.assertEqual(measured[0][2],f'~{6*C.spacing_m:.2f}')
        self.assertEqual(feature_table_rows(reading,C,False),[])
        track=reading['association']['tracks'][0]
        track['state']='ambiguous';track['current_support_cells']=[[8,6],[8,7]]
        # Even a malformed old point must not leak into ambiguous distance columns.
        row=feature_table_rows(reading,C)[0][1]
        self.assertEqual(row[2:6],['—']*4)
        self.assertEqual(row[6],'6, 7')
        track['state']='measured';track['last_peak_sequence']=2
        self.assertEqual(feature_table_rows(reading,C)[0][1][2],'—')

    def test_wire_size_supports_all_recording_versions(self):
        f=tone([(6,0,2000)])
        self.assertEqual(wire_size(f),len(encode(f)))
        for capacity in (64,128,320):
            edged=replace(f,edge_times_us=tuple(range(17)),edge_count=17,edge_capacity=capacity)
            self.assertEqual(wire_size(edged),len(encode(edged)))
        self.assertEqual(wire_size(edged),7868)

    def test_stream_quality_gates_clear_rd_results_and_preserve_raw(self):
        for kind in ('backlog','clock','flags'):
            live=LiveRangeDoppler(C);stop=threading.Event();updates=[]
            frames=[tone([(6,0,2000)],i)for i in range(1,5)]
            if kind=='flags':frames[-1].flags=0
            packets=[encode(replace(f,edge_times_us=tuple(range(272)),edge_count=272,edge_capacity=320))for f in frames]
            class Serial:
                def __init__(self):self.index=0;self.closed=False
                @property
                def in_waiting(self):return 2*len(packets[-1])+1 if kind=='backlog'and self.index==4 else 0
                def reset_input_buffer(self):pass
                def write(self,b):pass
                def read(self,n):result=packets[self.index];self.index+=1;return result
                def close(self):self.closed=True
            class Clock:
                def __init__(self):self.calls=0
                def metadata(self):return {}
                def update(self,*a,**kw):
                    self.calls+=1
                    return dict(reason='clock_fit_unstable'if kind=='clock'and self.calls==4 else None,
                                residual_s=0,raw_residual_s=0,state='collecting')
            serial=Serial()
            def observe(f,r):
                updates.append((r,live.snapshot))
                if f.sequence==4:stop.set()
            with tempfile.TemporaryDirectory()as folder,patch('radar_min.__main__.ClockSync',Clock):
                output=Path(folder)/'capture'
                result=stream('fake',C,output,10,detector=live,serial_factory=lambda *a,**kw:serial,
                    observer=observe,stop_event=stop,quiet=True)
                self.assertEqual(result['frames'],4)
                self.assertEqual(result['rejected_frames'],1)
                self.assertEqual(len(list(replay(output))),4)
                saved=[json.loads(x)for x in(output/'readings.jsonl').read_text().splitlines()]
                self.assertTrue(saved[2]['measured_features']>0)
                self.assertEqual(saved[2]['receiver_diagnostics']['frame_sequence'],3)
                self.assertFalse(saved[3]['valid'])
                self.assertNotIn('receiver_diagnostics',saved[3])
                self.assertEqual(saved[3]['association']['tracks'],[])
                self.assertEqual(json.loads((output/'metadata.json').read_text())['detector']['cfar']['factor'],4)
            self.assertIsNone(updates[-1][1]);self.assertTrue(serial.closed)

    def test_timeout_clears_processor_and_notifies_observer(self):
        live=LiveRangeDoppler(C);updates=[]
        packets=[encode(tone([(6,0,2000)],i))for i in (1,2,3)]+[b'']
        class Serial:
            in_waiting=0
            def __init__(self):self.index=0
            def reset_input_buffer(self):pass
            def write(self,b):pass
            def read(self,n):result=packets[self.index];self.index+=1;return result
            def close(self):pass
        ticks=iter([0,0,.1,.2,.3,.4,.5,.6,1.7])
        with tempfile.TemporaryDirectory()as folder,patch('radar_min.__main__.time.monotonic',side_effect=lambda:next(ticks)):
            with self.assertRaises(TimeoutError):
                stream('fake',C,Path(folder)/'capture',10,detector=live,serial_factory=lambda *a,**kw:Serial(),
                       observer=lambda f,r:updates.append((f,r,live.snapshot)),quiet=True)
        self.assertTrue(updates[2][1]['measured_features']>0)
        self.assertIsNone(updates[-1][0]);self.assertIsNone(updates[-1][2])
        self.assertEqual(live.associator.tracks,[])


if __name__=='__main__':unittest.main()
