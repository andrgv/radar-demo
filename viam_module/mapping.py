"""Experimental external-pose radar mapping; no radar-only localization."""
from collections import OrderedDict
import copy
import math

import numpy as np


def transform(value):
    matrix = np.asarray(value, dtype=float)
    if (matrix.shape != (4, 4) or not np.isfinite(matrix).all()
            or not np.allclose(matrix[3], [0, 0, 0, 1], atol=1e-6)
            or not np.allclose(matrix[:3, :3].T @ matrix[:3, :3], np.eye(3), atol=1e-5)
            or not np.isclose(np.linalg.det(matrix[:3, :3]), 1, atol=1e-5)):
        raise ValueError('Pose must be a finite rigid 4x4 transform; translation is meters')
    return matrix


class RadarMap:
    """Bounded keyframes allow external loop-closure corrections without ghosting."""
    def __init__(self):
        self.pending = OrderedDict()
        self.frames = OrderedDict()
        self.map_id = None

    def capture(self, snapshot):
        frame = copy.deepcopy(snapshot)
        self.pending[frame['frame_id']] = frame
        self.pending.move_to_end(frame['frame_id'])
        while len(self.pending) > 32:
            self.pending.popitem(last=False)
        return frame

    def reset(self):
        self.pending.clear()
        self.frames.clear()
        self.map_id = None
        return {'keyframe_count': 0}

    def add(self, command):
        frame_id = command.get('frame_id')
        frame = self.pending.get(frame_id)
        if frame is None:
            raise ValueError('Unknown frame_id; call mapping_frame first (last 32 are retained)')
        map_id = command.get('map_id')
        if not isinstance(map_id, str) or not map_id.strip():
            raise ValueError('map_id must identify the external SLAM/odometry coordinate frame')
        if self.map_id is not None and self.map_id != map_id:
            raise ValueError('Map frame changed; map_reset before starting a new map')
        stamp = float(command['pose_timestamp_unix'])
        if not math.isfinite(stamp) or abs(stamp - frame['captured_at_unix']) > .1:
            raise ValueError('Pose must match frame capture time within 0.1 seconds')
        # Explicit input: caller composes map<-base and base<-radar_optical.
        pose = transform(command['map_from_radar_optical'])
        if self.frames:
            first = next(iter(self.frames.values()))[0]
            if first['config_sha256'] != frame['config_sha256']:
                raise ValueError('Radar config changed; map_reset required')
        self.frames[frame_id] = (frame, pose)
        self.map_id = map_id
        while len(self.frames) > 500:
            self.frames.popitem(last=False)
        return {'map_id': self.map_id, 'keyframe_count': len(self.frames),
                'frame_id': frame_id, 'pose_time_offset_s': stamp-frame['captured_at_unix']}

    def update_poses(self, command):
        if command.get('map_id') != self.map_id or self.map_id is None:
            raise ValueError('map_id must match the existing map')
        changes = command.get('poses', {})
        if not isinstance(changes, dict) or not changes:
            raise ValueError('poses must map retained frame IDs to corrected transforms')
        validated = {}
        for frame_id, value in changes.items():
            if frame_id not in self.frames:
                raise ValueError('Cannot correct an unknown/evicted keyframe')
            validated[frame_id] = transform(value)
        for frame_id, pose in validated.items():
            self.frames[frame_id] = (self.frames[frame_id][0], pose)
        return {'updated_keyframes': len(validated), 'map_id': self.map_id}

    def points(self, command):
        width = float(command.get('max_angular_width_deg', 30))
        voxel = float(command.get('voxel_size_m', .2))
        if not math.isfinite(width) or not 1 <= width <= 120:
            raise ValueError('max_angular_width_deg must be in [1,120]')
        if not math.isfinite(voxel) or not .05 <= voxel <= 2:
            raise ValueError('voxel_size_m must be in [0.05,2]')
        cells = {}
        rejected = 0
        for frame_id, (frame, pose) in self.frames.items():
            for point in frame['points']:
                angles = np.asarray(point['angular_width_deg'], dtype=float)
                xyz = np.array([point['x_m'], point['y_m'], point['z_m']], dtype=float)
                if (angles.shape != (2,) or not np.isfinite(angles).all()
                        or (angles < 0).any() or angles.max() > width
                        or not np.isfinite(xyz).all()):
                    rejected += 1
                    continue
                xyz = pose[:3, :3] @ xyz + pose[:3, 3]
                key = tuple(np.floor(xyz/voxel).astype(np.int64))
                # Retain an actual measured endpoint, never a fabricated surface.
                cells[key] = dict(x_m=float(xyz[0]), y_m=float(xyz[1]), z_m=float(xyz[2]),
                                  source_frame_id=frame_id)
        return dict(map_id=self.map_id, coordinate_frame='external_map', units='meters',
                    mode='external_pose_radar_endpoints', keyframe_count=len(self.frames),
                    point_count=len(cells), points=list(cells.values()),
                    rejected_uncertain_points=rejected, voxel_size_m=voxel,
                    max_angular_width_deg=width, localization_estimated=False,
                    calibrated=False, free_space_inferred=False,
                    dynamic_objects_removed=False, max_keyframes=500)
