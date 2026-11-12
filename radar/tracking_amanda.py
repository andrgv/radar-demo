"""Range-only association; retained tracks are estimates, not fresh detections."""
from collections import deque
from dataclasses import dataclass, replace
import math


@dataclass
class RangeTrack:
    track_id: int
    range_m: float
    state: str
    measured: bool
    measurement_age_s: float
    confidence: float
    angle_valid: bool
    xyz: tuple | None
    close_range: bool
    measurement_kind: str = 'strong'


class RangeTracker:
    def __init__(self, config):
        self.config = config
        self.reset()
        self.next_id = 1

    def reset(self):
        self.active = []
        self.last_timestamp = None
        self.elapsed = 0.0

    def update(self, detections, supporting, timestamp_us):
        config = self.config
        dt = 0.0
        if self.last_timestamp is not None:
            delta = (timestamp_us - self.last_timestamp) & 0xffffffff
            if delta >= 0x80000000:  # device restart, rather than timestamp wrap
                self.reset()
            else:
                dt = delta / 1e6
        self.last_timestamp = timestamp_us
        self.elapsed += dt
        now = self.elapsed
        self.active = [entry for entry in self.active
                       if now - entry['last_seen'] <= config.track_hold_s + 1e-9]
        # Prefer strong measurements; a weak candidate can only maintain a
        # confirmed track. Greedy nearest association is intentionally range-only.
        matched = set()
        for candidates, strong in ((detections, True), (supporting, False)):
            pairs = []
            for i, entry in enumerate(self.active):
                if i in matched or (not strong and not entry['confirmed']):
                    continue
                tolerance = (config.track_match_bins * abs(config.ranges[1] - config.ranges[0])
                             + config.track_max_speed_mps * (now - entry['last_seen']))
                for j, candidate in enumerate(candidates):
                    distance = abs(entry['track'].range_m - candidate.range_m)
                    if distance <= tolerance:
                        pairs.append((distance, i, j))
            used = set()
            for _, i, j in sorted(pairs):
                if i in matched or j in used:
                    continue
                self._measure(self.active[i], candidates[j], now, strong)
                matched.add(i)
                used.add(j)
            if strong:
                for j, candidate in enumerate(candidates):
                    if j in used:
                        continue
                    # Static and moving detections at the same range represent
                    # one range observation for this tracker.
                    if any(abs(candidate.range_m - candidates[k].range_m) <
                           abs(config.ranges[1] - config.ranges[0]) * 0.5 for k in used):
                        continue
                    track = RangeTrack(self.next_id, candidate.range_m, 'tentative',
                                       True, 0.0, 0.0, False, None, candidate.close_range)
                    self.next_id += 1
                    entry = dict(track=track, confirmed=False, last_seen=now,
                                 hits=deque(maxlen=config.track_confirm_window))
                    self.active.append(entry)
                    self._measure(entry, candidate, now)
                    matched.add(len(self.active) - 1)
                    used.add(j)
        output = []
        survivors = []
        for i, entry in enumerate(self.active):
            if i not in matched:
                entry['hits'].append(False)
            if sum(entry['hits']) >= config.track_confirm_hits:
                entry['confirmed'] = True
            age = now - entry['last_seen']
            if not entry['confirmed'] and len(entry['hits']) == config.track_confirm_window:
                continue
            state = ('coasting' if i not in matched else 'confirmed') if entry['confirmed'] else 'tentative'
            track = replace(entry['track'], state=state, measured=i in matched,
                            measurement_kind=entry['track'].measurement_kind if i in matched else 'none',
                            measurement_age_s=age,
                            confidence=(1.0 if entry['confirmed'] else
                                        sum(entry['hits']) / config.track_confirm_hits)
                            * max(0.0, 1 - age / config.track_hold_s))
            entry['track'] = track
            survivors.append(entry)
            output.append(track)
        self.active = survivors
        return output

    def _measure(self, entry, detection, now, strong=True):
        track = entry['track']
        distance = track.range_m + self.config.track_smoothing * (detection.range_m - track.range_m)
        valid = bool(detection.angle_valid and all(math.isfinite(v) for v in detection.xyz))
        xyz = (tuple(v * distance / detection.range_m for v in detection.xyz)
               if valid and detection.range_m != 0 else None)
        entry['track'] = replace(track, range_m=distance, angle_valid=xyz is not None,
                                 xyz=xyz, close_range=detection.close_range,
                                 measurement_kind='strong' if strong else 'supporting')
        entry['last_seen'] = now
        entry['hits'].append(True)
