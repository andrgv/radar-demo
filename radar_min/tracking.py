"""Conservative single-object range tracking for the range-only GUI.

Tracking is a display and continuity aid. It never turns an invalid candidate,
fit-boundary result, or retained value into a current radar measurement.
"""

from collections import deque
import math


RESET_REASONS = {
    'baseline_invalidated_by_restart',
    'device_counter_changed',
    'frame_config_mismatch',
    'host_sensor_timing_mismatch',
    'restart_or_duplicate',
    'sequence_gap',
    'serial_backlog',
    'serial_timeout',
    'timestamp_gap',
}


class SingleRangeTracker:
    """Track one accepted range return without hiding missed detections."""

    def __init__(self, confirmation_hits=3, max_misses=8, smoothing=0.4,
                 base_gate_m=0.12, max_speed_mps=1.0,
                 motion_window=8, motion_threshold_mps=0.05):
        if confirmation_hits < 1 or max_misses < 1 or motion_window < 4:
            raise ValueError('Invalid tracking counts')
        if not 0 < smoothing <= 1:
            raise ValueError('Tracking smoothing must be in (0, 1]')
        if base_gate_m <= 0 or max_speed_mps < 0 or motion_threshold_mps <= 0:
            raise ValueError('Invalid tracking distances or speeds')
        self.confirmation_hits = int(confirmation_hits)
        self.max_misses = int(max_misses)
        self.smoothing = float(smoothing)
        self.base_gate_m = float(base_gate_m)
        self.max_speed_mps = float(max_speed_mps)
        self.motion_threshold_mps = float(motion_threshold_mps)
        self.motion_history = deque(maxlen=int(motion_window))
        self.next_track_id = 1
        self.last_timestamp_us = None
        self.clock_s = 0.0
        self._clear_active()

    def _clear_active(self):
        self.track_id = None
        self.range_m = None
        self.hits = 0
        self.misses = 0
        self.confirmed = False
        self.last_measurement_s = None
        self.motion_history.clear()

    def reset(self):
        """Discard the active track while keeping IDs monotonic."""
        self._clear_active()
        self.last_timestamp_us = None
        self.clock_s = 0.0

    def _advance_time(self, timestamp_us):
        if timestamp_us is None:
            return None
        timestamp_us = int(timestamp_us) & 0xffffffff
        if self.last_timestamp_us is None:
            self.last_timestamp_us = timestamp_us
            return 0.0
        delta_us = (timestamp_us - self.last_timestamp_us) & 0xffffffff
        self.last_timestamp_us = timestamp_us
        if delta_us == 0 or delta_us >= 0x80000000 or delta_us > 2_000_000:
            return None
        delta_s = delta_us / 1e6
        self.clock_s += delta_s
        return delta_s

    def _start(self, measurement_m):
        self.track_id = self.next_track_id
        self.next_track_id += 1
        self.range_m = float(measurement_m)
        self.hits = 1
        self.misses = 0
        self.confirmed = self.confirmation_hits == 1
        self.last_measurement_s = self.clock_s
        self.motion_history.clear()
        self.motion_history.append((self.clock_s, self.range_m))

    def _motion(self):
        if not self.confirmed or len(self.motion_history) < 4:
            return 'unknown'
        times = [item[0] for item in self.motion_history]
        ranges = [item[1] for item in self.motion_history]
        if times[-1] - times[0] < 0.25:
            return 'unknown'
        mean_t = sum(times) / len(times)
        mean_r = sum(ranges) / len(ranges)
        denominator = sum((value - mean_t) ** 2 for value in times)
        if denominator <= 0:
            return 'unknown'
        slope = sum((t - mean_t) * (r - mean_r)
                    for t, r in zip(times, ranges)) / denominator
        if abs(slope) < self.motion_threshold_mps:
            return 'stationary'
        return 'moving_closer' if slope < 0 else 'moving_away'

    def _result(self, state, measured, raw_range_m=None, lost_track_id=None,
                lost_range_m=None):
        active_id = self.track_id if lost_track_id is None else lost_track_id
        active_range = self.range_m if lost_range_m is None else lost_range_m
        age = None
        if self.last_measurement_s is not None:
            age = max(0.0, self.clock_s - self.last_measurement_s)
        return {
            'state': state,
            'track_id': active_id,
            'measured': bool(measured),
            'raw_range_m': float(raw_range_m) if raw_range_m is not None else None,
            'range_m': float(active_range) if active_range is not None else None,
            'motion': self._motion() if state in {'tracking', 'coasting'} else 'unknown',
            'measurement_age_s': age,
            'hits': self.hits,
            'misses': self.misses,
        }

    def update(self, measurement_m, timestamp_us, reset_reason=None):
        """Update from one frame and return a JSON-safe track status."""
        delta_s = self._advance_time(timestamp_us)
        if reset_reason or (timestamp_us is not None and delta_s is None):
            lost_id, lost_range = self.track_id, self.range_m
            self.reset()
            return {
                'state': 'lost' if lost_id is not None else 'idle',
                'track_id': lost_id,
                'measured': False,
                'raw_range_m': None,
                'range_m': float(lost_range) if lost_range is not None else None,
                'motion': 'unknown',
                'measurement_age_s': None,
                'hits': 0,
                'misses': 0,
                'reset_reason': reset_reason or 'invalid_timestamp',
            }

        valid = measurement_m is not None and math.isfinite(measurement_m) and measurement_m >= 0
        if not valid:
            if self.track_id is None:
                return self._result('idle', False)
            if not self.confirmed:
                lost_id, lost_range = self.track_id, self.range_m
                self._clear_active()
                return self._result('lost', False, lost_track_id=lost_id,
                                    lost_range_m=lost_range)
            self.misses += 1
            if self.misses >= self.max_misses:
                lost_id, lost_range = self.track_id, self.range_m
                self._clear_active()
                return self._result('lost', False, lost_track_id=lost_id,
                                    lost_range_m=lost_range)
            return self._result('coasting', False)

        measurement_m = float(measurement_m)
        if self.track_id is None:
            self._start(measurement_m)
            return self._result('tracking' if self.confirmed else 'tentative', True,
                                measurement_m)

        elapsed = max(0.0, self.clock_s - self.last_measurement_s)
        gate_m = self.base_gate_m + self.max_speed_mps * elapsed
        if abs(measurement_m - self.range_m) > gate_m:
            self._start(measurement_m)
            return self._result('tracking' if self.confirmed else 'tentative', True,
                                measurement_m)

        self.range_m = (self.smoothing * measurement_m
                        + (1 - self.smoothing) * self.range_m)
        self.hits += 1
        self.misses = 0
        self.confirmed = self.confirmed or self.hits >= self.confirmation_hits
        self.last_measurement_s = self.clock_s
        self.motion_history.append((self.clock_s, self.range_m))
        return self._result('tracking' if self.confirmed else 'tentative', True,
                            measurement_m)


def accepted_measurement(reading):
    """Return only a current accepted estimate, never a retained candidate."""
    value = reading.get('experimental_range_m')
    if (not reading.get('target_detected', False)
            or reading.get('fit_boundary', False)
            or value is None
            or not math.isfinite(value)):
        return None
    return float(value)


def enrich_tracking(reading, tracker):
    """Attach one tracking result to a per-frame reading in place."""
    reason = reading.get('reason')
    reset_reason = reason if reason in RESET_REASONS else None
    reading['track'] = tracker.update(
        accepted_measurement(reading),
        reading.get('timestamp_us'),
        reset_reason=reset_reason,
    )
    return reading
