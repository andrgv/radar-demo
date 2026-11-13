import asyncio
import unittest
from unittest.mock import MagicMock

from viam_module.sensor import UpennMmwave


class SensorReadingsTests(unittest.TestCase):
    def setUp(self):
        self.sensor = UpennMmwave('radar')
        self.sensor.runtime = MagicMock()

    def readings(self, values, **kwargs):
        self.sensor.runtime.readings.return_value = values
        return asyncio.run(self.sensor.get_readings(**kwargs))

    def test_default_only_primary_measurements_and_count(self):
        result = self.readings(dict(healthy=True, distance_m=1.234567,
            azimuth_deg=-4.321, echo_count=2, echoes=[{'distance_m':1.234567}],
            radial_velocity_mps=None, angle_calibrated=False,
            features={'saturation_fraction':0}, sequence=42))
        self.assertEqual(result, dict(distance_m=1.234567, azimuth_deg=-4.321, echo_count=2))

    def test_unavailable_angle_is_omitted_but_zero_is_retained(self):
        result = self.readings(dict(healthy=True, distance_m=1, azimuth_deg=None, echo_count=1))
        self.assertNotIn('azimuth_deg',result)
        result = self.readings(dict(healthy=True, distance_m=1, azimuth_deg=0, echo_count=1))
        self.assertEqual(result['azimuth_deg'],0)

    def test_no_echo_does_not_show_null_measurements(self):
        self.assertEqual(self.readings(dict(healthy=True, distance_m=None,
            azimuth_deg=None, echo_count=0)), {'echo_count':0})

    def test_connection_failure_is_visible_not_an_empty_scene(self):
        result = self.readings(dict(healthy=False,state='reconnecting',
            error='device missing',distance_m=None,azimuth_deg=None,echo_count=0))
        self.assertEqual(result,{'status':'reconnecting','error':'device missing'})

    def test_detailed_opt_in_and_status_preserve_full_telemetry(self):
        full=dict(healthy=True,distance_m=1,azimuth_deg=None,echo_count=1,echoes=[{'distance_m':1}])
        self.assertEqual(self.readings(full,extra={'detailed':True}),full)
        self.assertEqual(asyncio.run(self.sensor.get_status()),full)
        self.sensor.runtime.command.return_value=full
        self.assertEqual(asyncio.run(self.sensor.do_command({'command':'status'})),full)
        self.sensor.runtime.command.assert_called_once_with({'command':'status'})

if __name__=='__main__':unittest.main()
