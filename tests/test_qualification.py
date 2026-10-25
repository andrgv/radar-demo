from dataclasses import replace
from pathlib import Path
import unittest
import numpy as np
from radar.config import Config
from radar.processing import Processor,range_fft
from radar.synthetic import generate,Target
from radar.protocol import Parser,encode


class QualificationTests(unittest.TestCase):
    def test_scope_mux_preserves_spi_and_io_voltage_fields(self):
        import re
        from radar.recording_audit import read_register_profile
        root=Path(__file__).resolve().parents[1]
        registers,_=read_register_profile(root/'firmware/vendor/presence_detection_tracking.h')
        hal=(root.parent/'mtb_shared/sensor-xensiv-bgt60cutrxx/release-v1.1.0/register_hal/xensiv_bgt60cutrxxb_register_hal.h').read_text()
        def value(name):
            match=re.search(r'(?:#define\s+|\b)BGT60CUTR13B_'+name+r'\s+(?:=\s*)?(0x[0-9a-fA-F]+|\d+)',hal)
            return int(match.group(1),0)
        io=registers[0x100]
        expected=(io&~value('IO_CTRL_DMUX0_SEL_msk'))|value('IO_CTRL_DMUX0_SEL_CHIRP_ACTIVE')
        self.assertEqual(expected,0x8000000f)
        self.assertEqual(expected&0x80000000,io&0x80000000)
        dio=registers[0x120]
        expected=(dio&~(value('IO_DIO4_MAP_msk')|value('IO_DIO4_PULSE_LEN_msk')))|(
            value('IO_DIO4_MAP_DMUX0')<<value('IO_DIO4_MAP_pos'))|value('IO_DIO4_EN_msk')|value('IO_DIO4_STREN_msk')
        self.assertEqual(expected,0x60c)

    def test_unverified_timing_does_not_leak_placeholder_velocity(self):
        base=Config()
        frame=generate(base,targets=[Target(base.ranges[10],velocity_mps=0.4)],seed=1)
        results=[Processor(replace(base,chirp_interval_s=interval)).process(frame) for interval in [0.001,0.01]]
        np.testing.assert_equal(results[0].velocities,results[1].velocities)
        for result in results:
            self.assertTrue(result.detections)
            self.assertTrue(all(d.velocity_mps is None for d in result.detections))
            self.assertIn('unverified',result.doppler_unit)
        # The same ADC data retain the SAME ranges and inter-channel phase.
        np.testing.assert_array_equal(results[0].ranges,results[1].ranges)
        np.testing.assert_array_equal(results[0].profile_db,results[1].profile_db)
        np.testing.assert_array_equal(range_fft(frame.adc,base),range_fft(frame.adc,replace(base,chirp_interval_s=0.01)))

    def test_only_verified_timing_and_carrier_enable_mps(self):
        config=Config(chirp_timing_verified=True)
        self.assertFalse(config.velocity_scale_verified)
        config=replace(config,carrier_frequency_verified=True)
        result=Processor(config).process(generate(config,seed=2))
        self.assertEqual(result.doppler_unit,'m/s')
        self.assertTrue(all(d.velocity_mps is not None for d in result.detections))
        with self.assertRaises(ValueError):
            replace(config,chirp_timing_verified='false').validate()

    def test_optional_elapsed_header_is_backward_compatible(self):
        frame=generate(Config(),seed=1)
        old=Parser().feed(encode(frame))[0]
        self.assertIsNone(old.capture_elapsed_us)
        new=Parser().feed(encode(replace(frame,capture_elapsed_us=1234)))[0]
        self.assertEqual(new.capture_elapsed_us,1234)
        self.assertEqual(new.flags&2,2)
        np.testing.assert_array_equal(old.adc,new.adc)

    def test_qualification_register_difference_is_only_hpf1(self):
        import json,hashlib
        from tools.prepare_qualification import prepare
        root=Path(__file__).resolve().parents[1]
        before=hashlib.sha256((root/'firmware/main.c').read_bytes()).hexdigest()
        result=prepare()
        self.assertEqual(before,result['baseline_sha256'])
        self.assertEqual(before,hashlib.sha256((root/'firmware/main.c').read_bytes()).hexdigest())
        self.assertEqual(len(result['register_differences']),3)
        for change in result['register_differences']:
            self.assertEqual(int(change['hpf350'],16)^int(change['hpf100'],16),0x100)
