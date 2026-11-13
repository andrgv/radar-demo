"""Conservative, explicitly seeded single-return tracking, not object identity."""
from collections import deque
from dataclasses import asdict, dataclass
import threading

import numpy as np


@dataclass(frozen=True)
class TargetSettings:
    start_range_m: float
    start_bearing_deg: float = 0.
    acquisition_gate_m: float = .3
    range_gate_m: float = .25
    max_step_m: float = .35
    bearing_gate_deg: float = 8.
    confirmation_frames: int = 3
    max_misses: int = 15

    def __post_init__(self):
        values = [self.start_range_m, self.start_bearing_deg, self.acquisition_gate_m,
                  self.range_gate_m, self.max_step_m, self.bearing_gate_deg]
        if (not np.isfinite(values).all() or self.start_range_m <= 0
                or abs(self.start_bearing_deg) > 60
                or min(self.acquisition_gate_m, self.range_gate_m, self.max_step_m, self.bearing_gate_deg) <= 0):
            raise ValueError('Invalid selected-target starting position or association bounds')
        if any(type(v) is not int or v < 1 for v in (self.confirmation_frames, self.max_misses)):
            raise ValueError('Target confirmation and miss counts must be positive integers')


class SelectedTargetTracker:
    def __init__(self, settings, *, assumed_z=0, frame_interval_s=.1):
        self.settings = settings
        self.z = float(assumed_z)
        self.interval = float(frame_interval_s)
        if (not np.isfinite([self.z, self.interval]).all() or self.interval <= 0
                or abs(self.z) >= settings.start_range_m):
            raise ValueError('Invalid selected-target height or frame interval')
        self.reset_requested = threading.Event()
        self.target_id = 0
        self.elapsed = 0.
        self.previous_timestamp = None
        self.last_key = None
        self._reset()

    def _reset(self):
        self.target_id += 1
        self.state = 'SEARCHING'
        self.reason = 'waiting_near_selected_start_position'
        self.hits = 0
        self.misses = 0
        self.locked = False
        self.last = None
        self.velocity = 0.
        self.history = deque(maxlen=100)

    def request_relock(self):
        """The UI requests; only the acquisition worker mutates association."""
        self.reset_requested.set()

    def snapshot(self):
        return self._report()

    def _report(self, current=None, accepted=0, rejected=0):
        return dict(kind='selected-target-track-v1', target_id=self.target_id,
            state=self.state, reason=self.reason, settings=asdict(self.settings),
            confirmation_hits=self.hits, misses=self.misses,
            measurement=current, last_measurement=self.last if self.locked else None,
            last_seen_age_s=max(0., self.elapsed-self.last['seen_elapsed_s']) if self.last else None,
            accepted_candidates=accepted, rejected_candidates=rejected,
            history=list(self.history), calibrated=False,
            limitation='Association aid, not verified physical identity or calibrated range accuracy. No automatic reacquisition after loss.')

    def _miss(self, reason, *, force_loss=False):
        self.misses += 1
        self.reason = reason
        if self.locked:
            self.state = 'LOST' if force_loss or self.misses >= self.settings.max_misses else 'MISSING'
        else:
            self.state = 'SEARCHING'
            self.hits = 0
            self.last = None
        return self._report()

    def update(self, result):
        if self.reset_requested.is_set():
            self.reset_requested.clear()
            self._reset()
        key = (result.get('sequence'), result.get('timestamp_us'))
        if key == self.last_key:
            if result['state'] == 'UNCERTAIN':
                return self._miss('sensor_rejected_duplicate_frame', force_loss=True)
            return self._report()
        self.last_key = key
        timestamp = result.get('timestamp_us')
        if timestamp is not None:
            if self.previous_timestamp is not None:
                delta = (timestamp-self.previous_timestamp) & 0xffffffff
                self.elapsed += delta/1e6 if 0 < delta < 0x80000000 else self.interval
            self.previous_timestamp = timestamp
        if self.state == 'LOST':
            self.reason = 'target_lost_explicit_relock_required'
            return self._report()
        if result['state'] == 'UNCERTAIN':
            return self._miss('sensor_rejected_frame: '+result.get('reason', 'unknown'), force_loss=True)

        candidates = []
        for item in result.get('observations', []):
            distance, bearing = item.get('range_m'), item.get('azimuth_deg')
            coherence = item.get('coherence_rx2')
            if (distance is None or bearing is None or coherence is None
                    or not np.isfinite([distance, bearing, coherence]).all()
                    or distance <= abs(self.z) or coherence < .9):
                continue
            candidates.append(item)
        s = self.settings
        if self.last is None:
            center_r, center_a, gate = s.start_range_m, s.start_bearing_deg, s.acquisition_gate_m
        else:
            dt = min(.3, max(0., self.elapsed-self.last['seen_elapsed_s']))
            center_r = self.last['range_m']+self.velocity*dt
            center_a, gate = self.last['azimuth_deg'], s.range_gate_m
        ranked = []
        for item in candidates:
            dr, da = abs(item['range_m']-center_r), abs(item['azimuth_deg']-center_a)
            if (dr <= gate and da <= s.bearing_gate_deg
                    and (self.last is None or abs(item['range_m']-self.last['range_m']) <= s.max_step_m)):
                ranked.append((dr/gate+da/s.bearing_gate_deg, item))
        ranked.sort(key=lambda pair: pair[0])
        if not ranked:
            report = self._miss('no_return_within_selected_target_gate')
            report['rejected_candidates'] = len(candidates)
            return report
        if len(ranked) > 1 and ranked[1][0]-ranked[0][0] < .2:
            report = self._miss('ambiguous_returns_within_selected_target_gate')
            report.update(accepted_candidates=len(ranked), rejected_candidates=len(candidates)-len(ranked))
            return report
        chosen = ranked[0][1]
        distance, bearing = float(chosen['range_m']), float(chosen['azimuth_deg'])
        horizontal = float(np.sqrt(distance**2-self.z**2))
        measurement = dict(range_m=distance, azimuth_deg=bearing,
            x_m=float(horizontal*np.sin(np.radians(bearing))),
            y_m=float(horizontal*np.cos(np.radians(bearing))),
            coherence_rx2=float(chosen['coherence_rx2']), source_track_id=chosen.get('track_id'),
            range_bin=chosen.get('range_bin'), seen_elapsed_s=self.elapsed,
            signal_to_reference_db=chosen.get('signal_to_reference_db'))
        if self.last is not None:
            dt = self.elapsed-self.last['seen_elapsed_s']
            if dt > 0:
                rate = (distance-self.last['range_m'])/dt
                self.velocity = float(np.clip(.5*self.velocity+.5*rate, -.75, .75))
        self.last = measurement
        self.hits += 1
        self.misses = 0
        self.locked = self.locked or self.hits >= s.confirmation_frames
        self.state = 'TRACKING' if self.locked else 'ACQUIRING'
        self.reason = 'associated_current_measurement' if self.locked else 'confirming_selected_return'
        if self.locked:
            self.history.append(measurement)
        return self._report(current=measurement if self.locked else None,
                            accepted=len(ranked), rejected=len(candidates)-len(ranked))

    def stop(self):
        self.state = 'STOPPED'
        self.reason = 'no_current_measurement_after_stop'
        return self._report()
