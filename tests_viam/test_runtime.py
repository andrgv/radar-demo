import asyncio
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import serial
from google.protobuf.struct_pb2 import Struct
from viam.proto.app.robot import ComponentConfig
from radar.synthetic import generate, Target
from radar.acquisition import Source
from viam_module.runtime import RadarRuntime, validate
from viam_module.sensor import UpennMmwave

ATTRS=dict(serial_port='/dev/cu.test',config_path='configs/exploratory-roll90-phase.json',
           reconnect_delay_s=.01,stale_after_s=.1,enable_angles=False)

class FakeSource:
    def __init__(self,cfg,port=None,fail=False,quiet=False):
        self.config=cfg;self.closed=False;self.fail=fail;self.quiet=quiet;self.sequence=0
        self.parser=SimpleNamespace(bad_crc=0,bad_headers=0,gaps=0)
    def read(self):
        time.sleep(.005)
        if self.fail: raise serial.SerialException('device disappeared')
        if self.quiet:return None
        self.sequence+=1
        return generate(self.config,self.sequence,targets=[Target(self.config.ranges[4])],seed=1)
    def close(self):self.closed=True


def wait_for(predicate):
    end=time.monotonic()+3
    while time.monotonic()<end:
        if predicate():return
        time.sleep(.01)
    raise AssertionError('Timed out waiting for worker')

class RuntimeTests(unittest.TestCase):
    def test_reconnect_and_close(self):
        sources=[]
        def factory(cfg,port):
            source=FakeSource(cfg,port,fail=not sources);sources.append(source);return source
        runtime=RadarRuntime(ATTRS,source_factory=factory)
        try:
            wait_for(lambda:runtime.readings()['healthy'])
            self.assertTrue(sources[0].closed)
            self.assertEqual(runtime.readings()['reconnect_count'],1)
            self.assertEqual(runtime.readings()['echo_count'],1)
        finally: runtime.close()
        self.assertTrue(all(s.closed for s in sources))
        self.assertEqual(runtime.readings()['state'],'closed')
        self.assertEqual(runtime.readings()['echoes'],[])

    def test_stale_readings_never_return_old_echoes(self):
        sources=[]
        def factory(cfg,port):
            source=FakeSource(cfg,port);sources.append(source);return source
        runtime=RadarRuntime(ATTRS,source_factory=factory)
        try:
            wait_for(lambda:runtime.readings()['healthy'])
            sources[0].quiet=True
            wait_for(lambda:runtime.readings()['state']=='stale')
            self.assertIsNone(runtime.readings()['distance_m'])
            self.assertEqual(runtime.readings()['echo_count'],0)
        finally:runtime.close()

    def test_background_commands_and_validation(self):
        runtime=RadarRuntime(ATTRS,source_factory=FakeSource)
        try:
            wait_for(lambda:runtime.readings()['healthy'])
            for frames in [True,1,float('nan'),301]:
                with self.assertRaises(ValueError):runtime.command({'command':'capture_background','frames':frames})
            runtime.command({'command':'capture_background','frames':10})
            wait_for(lambda:runtime.readings().get('background_subtracted'))
            runtime.command({'command':'clear_background'})
            wait_for(lambda:runtime.readings().get('echo_count')==1)
        finally:runtime.close()

    def test_no_config_or_wrong_port_fails_before_open(self):
        for attrs in [{},dict(ATTRS,config_path='missing.json'),dict(ATTRS,max_range_m=float('nan'))]:
            with self.assertRaises((ValueError,FileNotFoundError)):validate(attrs)

    def test_raw_export_shares_existing_source_and_disallows_stale_frames(self):
        from viam_module.raw_frame import decode_raw
        sources=[]
        def factory(cfg,port):
            src=FakeSource(cfg,port);sources.append(src);return src
        runtime=RadarRuntime(ATTRS,source_factory=factory)
        try:
            wait_for(lambda:runtime.readings()['healthy'])
            data=runtime.command({'command':'raw_frame'})
            frame,cfg,meta=decode_raw(data,1)
            self.assertEqual(frame.adc.shape,(17,64,3))
            self.assertEqual(len(sources),1)
            self.assertEqual(cfg.calibration_id,runtime.config.calibration_id)
            sources[0].quiet=True
            wait_for(lambda:runtime.readings()['state']=='stale')
            with self.assertRaises(RuntimeError):runtime.command({'command':'raw_frame'})
        finally:runtime.close()
        with self.assertRaises(RuntimeError):runtime.command({'command':'raw_frame'})

    def test_start_failure_closes_port(self):
        port=MagicMock();port.write.side_effect=serial.SerialException('start failed')
        with patch('radar.acquisition.serial.Serial',return_value=port):
            with self.assertRaises(serial.SerialException): Source(validate(ATTRS),port='/dev/cu.test')
        port.close.assert_called_once()

    def test_sensor_sdk_lifecycle(self):
        attributes=Struct();attributes.update(ATTRS)
        config=ComponentConfig(name='radar',attributes=attributes)
        runtime=MagicMock();runtime.readings.return_value={'healthy':True,'echo_count':1}
        with patch('viam_module.sensor.RadarRuntime',return_value=runtime):
            sensor=UpennMmwave.new(config,{})
        self.assertEqual(asyncio.run(sensor.get_readings())['echo_count'],1)
        asyncio.run(sensor.close());runtime.close.assert_called_once()

if __name__=='__main__':unittest.main()
