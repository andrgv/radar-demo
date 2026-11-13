import unittest
import numpy as np
from viam_module.mapping import RadarMap, transform


def frame(name='a', x=1, width=20, config='same'):
    return dict(frame_id=name, captured_at_unix=100., config_sha256=config,
                points=[dict(x_m=x,y_m=0,z_m=0,angular_width_deg=[width,width])])


def command(name='a', pose=None):
    return dict(frame_id=name,map_id='room',pose_timestamp_unix=100.,
                map_from_radar_optical=np.eye(4).tolist() if pose is None else pose.tolist())


class MappingTests(unittest.TestCase):
    def test_motion_compensation_duplicate_frames_and_correction(self):
        m=RadarMap();m.capture(frame());m.add(command())
        pose=np.eye(4);pose[0,3]=.5
        m.capture(frame('b',x=.5));m.add(command('b',pose));m.add(command('b',pose))
        self.assertEqual(m.points({})['point_count'],1)
        self.assertEqual(len(m.frames),2)
        pose[0,3]=1.5
        m.update_poses({'map_id':'room','poses':{'b':pose.tolist()}})
        self.assertEqual(sorted(p['x_m'] for p in m.points({})['points']),[1,2])

    def test_rotation_and_translation(self):
        m=RadarMap();m.capture(frame())
        pose=np.array([[0,-1,0,2],[1,0,0,3],[0,0,1,4],[0,0,0,1]])
        m.add(command(pose=pose))
        p=m.points({})['points'][0]
        self.assertEqual([p[k] for k in ['x_m','y_m','z_m']],[2,4,4])

    def test_reject_time_map_and_config_mismatch(self):
        m=RadarMap();m.capture(frame())
        bad=command();bad['pose_timestamp_unix']=101
        with self.assertRaises(ValueError):m.add(bad)
        self.assertEqual(len(m.frames),0)
        m.add(command());bad=command();bad['map_id']='new'
        with self.assertRaises(ValueError):m.add(bad)
        m.capture(frame('b',config='changed'))
        with self.assertRaises(ValueError):m.add(command('b'))

    def test_uncertain_echo_not_promoted_to_wall(self):
        m=RadarMap();m.capture(frame(width=120));m.add(command())
        self.assertEqual(m.points({})['point_count'],0)
        self.assertEqual(m.points({})['rejected_uncertain_points'],1)
        self.assertEqual(m.points({'max_angular_width_deg':120})['point_count'],1)

    def test_empty_reset_bounds_invalid_pose(self):
        m=RadarMap();empty=frame();empty['points']=[]
        m.capture(empty);m.add(command())
        self.assertEqual(m.points({})['points'],[])
        for i in range(510):
            name=str(i);m.capture(frame(name));m.add(command(name))
        self.assertEqual(len(m.frames),500);self.assertEqual(len(m.pending),32)
        m.reset();self.assertEqual(m.points({})['point_count'],0)
        for value in [np.zeros((4,4)),np.diag([2,1,1,1]),np.full((4,4),np.nan)]:
            with self.assertRaises(ValueError):transform(value)

    def test_loop_closure_validation_atomic(self):
        m=RadarMap();m.capture(frame());m.add(command())
        pose=np.eye(4);pose[0,3]=10
        with self.assertRaises(ValueError):
            m.update_poses({'map_id':'room','poses':{'a':pose.tolist(),'missing':pose.tolist()}})
        self.assertEqual(m.points({})['points'][0]['x_m'],1)
