"""Persistent clusters of localized radar returns for a FIXED sensor.

Regions represent repeated reflection locations, not semantic objects, physical
outlines or free space. Evidence scores are engineering support, not probability.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import time

import numpy as np


@dataclass(frozen=True)
class SceneMapSettings:
    merge_radius_m: float = .35
    min_observations: int = 3
    remember_seconds: float = 30.
    tentative_seconds: float = 2.
    max_objects: int = 512

    def __post_init__(self):
        for name in ('merge_radius_m', 'remember_seconds', 'tentative_seconds'):
            value = getattr(self, name)
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f'{name} must be finite and positive')
        for name in ('min_observations', 'max_objects'):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f'{name} must be a positive integer')


def reference_fingerprint(detector):
    """A saved map cannot silently move to different acquisition/calibration."""
    payload = dict(config=asdict(detector.config), reference_xyz=detector.reference_xyz.tolist(),
                   reference_phase=detector.reference_phase, assumed_z=detector.z,
                   synthetic=detector.metadata.get('source') == 'synthetic')
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()


class FixedSceneMap:
    def __init__(self, fingerprint, settings=None, *, assumed_z=0, clock=time.monotonic, wall_clock=time.time):
        self.settings = settings or SceneMapSettings()
        self.fingerprint = fingerprint
        self.z = float(assumed_z)
        if not np.isfinite(self.z):
            raise ValueError('Assumed height must be finite')
        self.clock = clock
        self.wall_clock = wall_clock
        self.objects = {}
        self.next_id = 1
        self.current_ids = set()
        self.last_key = None
        self.last_time = None
        self.last_sensor_state = 'WAITING'
        self.last_reason = 'waiting_for_frames'
        self.saturated = False
        self.generation = 0

    def _time(self, now):
        now = float(self.clock() if now is None else now)
        if not np.isfinite(now):
            raise ValueError('Map time must be finite')
        if self.last_time is not None and now < self.last_time:
            raise ValueError('Map time cannot go backwards')
        self.last_time = now
        return now

    def clear(self):
        self.objects.clear()
        self.current_ids.clear()
        self.last_key = None
        self.saturated = False
        self.generation += 1
        self.last_reason = 'map_cleared'

    def _clusters(self, observations):
        points = []
        for item in observations:
            if item.get('state') != 'LOCALIZED' or not item.get('confirmed'):
                continue
            values = [item.get('x_m'), item.get('y_m')]
            if any(v is None for v in values) or not np.isfinite(values).all() or values[1] <= 0:
                continue
            points.append(np.asarray(values, float))
        # Connected spatial components within each frame. A dozen adjacent
        # returns in ONE frame contribute one vote, not a dozen confirmations.
        remaining = set(range(len(points)))
        clusters = []
        while remaining:
            seed = min(remaining)
            remaining.remove(seed)
            component, frontier = [seed], [seed]
            while frontier:
                i = frontier.pop()
                neighbors = [j for j in sorted(remaining)
                             if np.linalg.norm(points[j]-points[i]) <= self.settings.merge_radius_m]
                for j in neighbors:
                    remaining.remove(j)
                    component.append(j)
                    frontier.append(j)
            xy = np.mean([points[i] for i in component], axis=0)
            clusters.append((xy, len(component)))
        return clusters

    def update(self, result, *, now=None):
        now = self._time(now)
        # Briefly show memory even if the detector loses a track or transport
        # fails. No fault or missing frame supplies positive or negative votes.
        self.objects = {key: obj for key, obj in self.objects.items()
                        if obj['observations'] >= self.settings.min_observations
                        or now-obj['last_seen_s'] <= self.settings.tentative_seconds}
        if result is None:
            if any(now-self.objects[i]['last_seen_s'] > .5 for i in self.current_ids if i in self.objects):
                self.current_ids.clear()
            return self.snapshot(now=now)
        self.last_sensor_state = result['state']
        self.last_reason = result.get('reason', 'current_frame')
        key = (result.get('sequence'), result.get('timestamp_us'))
        if result['state'] == 'UNCERTAIN':
            self.current_ids.clear()
            return self.snapshot(now=now)
        if key == (None, None) or key == self.last_key:
            return self.snapshot(now=now)
        self.last_key = key
        self.current_ids.clear()
        clusters = self._clusters(result.get('obstacles', []))
        pairs = []
        for i, (xy, _) in enumerate(clusters):
            for object_id, obj in self.objects.items():
                distance = float(np.linalg.norm(xy-[obj['x_m'], obj['y_m']]))
                if distance <= self.settings.merge_radius_m:
                    pairs.append((distance, i, object_id))
        matches, used = {}, set()
        for _, i, object_id in sorted(pairs):
            if i not in matches and object_id not in used:
                matches[i] = object_id
                used.add(object_id)
        self.saturated = False
        for i, (xy, count) in enumerate(clusters):
            object_id = matches.get(i)
            if object_id is None:
                if len(self.objects) >= self.settings.max_objects:
                    self.saturated = True
                    continue
                object_id = self.next_id
                self.next_id += 1
                self.objects[object_id] = dict(object_id=object_id, x_m=float(xy[0]), y_m=float(xy[1]),
                    observations=0, raw_return_count=0, m2_x=0., m2_y=0.,
                    first_seen_s=now, last_seen_s=now)
            obj = self.objects[object_id]
            n = obj['observations']+1
            # Running centroid/scatter uses one localized component per frame.
            for axis, value in zip(('x', 'y'), xy):
                delta = float(value)-obj[f'{axis}_m']
                obj[f'{axis}_m'] += delta/n
                obj[f'm2_{axis}'] = max(0., obj[f'm2_{axis}']+delta*(float(value)-obj[f'{axis}_m']))
            obj.update(observations=n, raw_return_count=obj['raw_return_count']+count, last_seen_s=now)
            self.current_ids.add(object_id)
        return self.snapshot(now=now)

    def snapshot(self, *, now=None, stopped=False):
        now = self._time(now)
        if stopped:
            self.current_ids.clear()
            self.last_sensor_state = 'STOPPED'
            self.last_reason = 'saved_map_not_live_observation'
        items = []
        for object_id, obj in sorted(self.objects.items()):
            age = max(0., now-obj['last_seen_s'])
            confirmed = obj['observations'] >= self.settings.min_observations
            current = object_id in self.current_ids and age <= .5 and not stopped
            state = ('TENTATIVE' if not confirmed else 'CURRENT' if current else
                     'REMEMBERED' if age <= self.settings.remember_seconds else 'STALE')
            x, y = obj['x_m'], obj['y_m']
            spread_x = float(np.sqrt(max(0., obj['m2_x'])/max(1, obj['observations']-1)))
            spread_y = float(np.sqrt(max(0., obj['m2_y'])/max(1, obj['observations']-1)))
            items.append(dict(**obj, state=state, confirmed=confirmed, currently_observed=current,
                age_s=age, range_m=float(np.sqrt(x*x+y*y+self.z*self.z)),
                azimuth_deg=float(np.degrees(np.arctan2(x, y))),
                spread_x_m=spread_x, spread_y_m=spread_y,
                # Labelled as support, never interpreted as occupancy probability.
                support_score=float(min(1., obj['observations']/10)*np.exp(-age/self.settings.remember_seconds))))
        return dict(schema=1, kind='fixed-radar-object-region-map', frame_id='fixed_radar',
            units='meters', origin_xy_m=[0., 0.], fingerprint=self.fingerprint,
            fixed_radar_required=True, calibrated=False, assumed_z_m=self.z,
            updated_s=now, saved_unix_s=float(self.wall_clock()),
            generation=self.generation, next_id=self.next_id, settings=asdict(self.settings),
            sensor_state=self.last_sensor_state, reason=self.last_reason,
            capacity_reached=self.saturated, objects=items,
            limitations='Reflection clusters, not semantic object identities, physical outlines or free space. Support is not probability.')

    def restore(self, path, *, now=None):
        """Resume compatible saved positions as memory, never as live evidence."""
        data = json.loads(Path(path).read_text())
        if (not isinstance(data, dict) or data.get('schema') != 1 or data.get('kind') != 'fixed-radar-object-region-map'
                or data.get('fingerprint') != self.fingerprint or data.get('assumed_z_m') != self.z):
            raise ValueError('Saved map does not match this radar configuration/reference/height')
        values = data.get('objects')
        if not isinstance(values, list) or len(values) > self.settings.max_objects:
            raise ValueError('Invalid saved map object count')
        objects = {}
        now = self._time(now)
        try:
            saved_time = float(data['updated_s'])
            saved_wall = float(data['saved_unix_s'])
        except (TypeError, ValueError, KeyError) as error:
            raise ValueError('Invalid saved map timestamp') from error
        if not np.isfinite([saved_time, saved_wall]).all():
            raise ValueError('Invalid saved map timestamp')
        offset = now-saved_time-max(0., self.wall_clock()-saved_wall)
        for item in values:
            names = ('object_id', 'x_m', 'y_m', 'observations', 'raw_return_count',
                     'm2_x', 'm2_y', 'first_seen_s', 'last_seen_s')
            if not isinstance(item, dict) or any(name not in item for name in names):
                raise ValueError('Invalid saved object region')
            obj = {name: item[name] for name in names}
            if any(type(value) not in (int, float) for value in obj.values()):
                raise ValueError('Invalid saved object numeric fields')
            if (any(type(obj[k]) is not int or obj[k] < 1 for k in ('object_id', 'observations', 'raw_return_count'))
                    or not np.isfinite([obj[k] for k in ('x_m', 'y_m', 'm2_x', 'm2_y', 'first_seen_s', 'last_seen_s')]).all()
                    or obj['y_m'] <= 0 or min(obj['m2_x'], obj['m2_y']) < 0
                    or not obj['first_seen_s'] <= obj['last_seen_s'] <= saved_time
                    or obj['object_id'] in objects):
                raise ValueError('Invalid saved object region')
            obj['first_seen_s'] += offset
            obj['last_seen_s'] += offset
            objects[obj['object_id']] = obj
        next_id, generation = data.get('next_id', max(objects, default=0)+1), data.get('generation', 0)
        if (type(next_id) is not int or next_id <= max(objects, default=0)
                or type(generation) is not int or generation < 0):
            raise ValueError('Invalid saved map IDs/generation')
        self.objects = objects
        self.current_ids.clear()
        self.next_id = next_id
        self.generation = generation
        self.last_sensor_state = 'RESTORED'
        self.last_reason = 'loaded_positions_require_new_observations'
        return self.snapshot(now=now)


class MapArchive:
    """Atomically replace map.json; append an auditable observation history."""
    def __init__(self, output):
        self.output = Path(output) if output else None
        self.history = None
        self.ready = False

    def activate(self):
        # Called only after this run's Recorder has exclusively created output.
        self.ready = True

    def write(self, snapshot, event='observation'):
        if self.output is None or not self.ready:
            return
        if self.history is None:
            self.history = (self.output/'map_history.jsonl').open('x')
        encoded = json.dumps(snapshot, allow_nan=False)
        self.history.write(json.dumps(dict(snapshot, event=event), allow_nan=False)+'\n')
        self.history.flush()
        temporary = self.output/'map.json.tmp'
        temporary.write_text(encoded+'\n')
        temporary.replace(self.output/'map.json')

    def close(self):
        if self.history:
            self.history.close()
