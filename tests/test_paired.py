import tempfile
from pathlib import Path
import unittest
import numpy as np
from radar.config import Config
from radar.paired import load_session, compare, investigate_bin, audit_wire
from radar.storage import Recorder
from radar.synthetic import Target, generate
from radar.acquisition import Source
from radar.protocol import Parser, encode


class PairedTests(unittest.TestCase):
    def test_wire_audit_locates_deleted_bytes_without_counting_shutdown_tail(self):
        config=Config()
        first=encode(generate(config,1,seed=1))
        second=encode(generate(config,2,seed=2))
        third=encode(generate(config,3,seed=3))
        fourth=encode(generate(config,4,seed=4))
        wire=first+second[:100]+second[127:]+third+fourth[:200]
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'serial-wire.bin').write_bytes(wire)
            result=audit_wire(directory)
            self.assertEqual(result['accepted_frames'],2)
            self.assertEqual(result['crc_failures'],1)
            self.assertEqual(result['missing_sequences'],1)
            self.assertEqual(result['tail_bytes'],200)
            self.assertEqual(result['rejected_packet_boundaries'][0]['boundary_shortfall_bytes'],27)
            self.assertEqual(result['rejected_packet_boundaries'][0]['sequence'],2)

    def test_pair_isolates_range_change_and_identical_pair_has_no_excess(self):
        config=Config()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,amplitude in [('control',300),('target',900)]:
                with Recorder(root/name,config) as recorder:
                    for i in range(20):
                        recorder.write(generate(config,i+1,targets=[Target(config.ranges[4],amplitude=amplitude)],noise=3,seed=i))
            control=load_session(root/'control',config)
            target=load_session(root/'target',config)
            result=compare(control,target,config,bootstrap=30)
            self.assertAlmostEqual(result['target_control_gain_db'],20*np.log10(3),delta=0.1)
            self.assertGreater(result['gain_block_bootstrap_95_db'][0],9)
            self.assertEqual(result['target_fraction_above_control_reference_q99'],1)
            same=compare(control,control,config,bootstrap=10)
            self.assertEqual(same['target_control_gain_db'],0)
            self.assertIsNone(same['differential_peak_az_el_deg'])
            self.assertIn('rectangular_window_local_peak',investigate_bin(control))

    def test_original_corrupt_wire_is_preserved_but_replay_is_clean(self):
        config=Config()
        packets=[encode(generate(config,i,seed=i)) for i in [1,2,3]]
        broken=bytearray(packets[1]);broken[100]^=1
        wire=packets[0]+bytes(broken)+packets[2]
        class SerialStub:
            in_waiting=len(wire)
            def read(self,n):return wire
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'session'
            source=Source(config);source.serial=SerialStub()
            with Recorder(path,config) as recorder:
                source.transport_recorder=recorder
                for _ in range(2):recorder.write(source.read())
            self.assertEqual((path/'serial-wire.bin').read_bytes(),wire)
            parser=Parser();frames=parser.feed(wire)
            self.assertEqual([f.sequence for f in frames],[1,3])
            self.assertEqual(parser.bad_crc,1)
            self.assertEqual(parser.gaps,1)
            self.assertGreaterEqual(parser.discarded_bytes,len(packets[1]))
