"""Bounded startup clock-rate estimate, frozen before long-run freshness checks.

This measures relative host/device progress. It cannot establish absolute age or
separate a constant rate error from every gradual latency ramp during startup.
"""
from dataclasses import dataclass, asdict
import numpy as np


@dataclass(frozen=True)
class ClockPolicy:
    fit_span_s: float = 20.0
    max_fit_span_s: float = 30.0
    min_samples: int = 100
    max_rate_error: float = .02
    max_fit_residual_s: float = .1
    p95_fit_residual_s: float = .05
    max_progress_error_s: float = .5


class ClockSync:
    def __init__(self):
        self.policy = ClockPolicy()
        self.start_host = None
        self.last_host = None
        self.previous_ts = None
        self.device_elapsed = 0.
        self.rate = 1.
        self.offset = 0.
        self.samples = []
        self.state = 'collecting'
        self.failure = None

    def metadata(self):
        return dict(algorithm='bounded-startup-clock-v1', policy=asdict(self.policy),
                    limitation='Relative progress only; no absolute age handshake; startup latency ramps can resemble clock skew')

    def update(self, timestamp_us, host_now, eligible=True, restart=False):
        if restart:
            self.failure = self.failure or 'clock_restart_or_duplicate'
        if self.start_host is None:
            self.start_host = self.last_host = host_now
            self.previous_ts = timestamp_us
        else:
            delta = (timestamp_us-self.previous_ts) & 0xffffffff
            self.previous_ts = timestamp_us
            if delta == 0 or delta >= 0x80000000:
                self.failure = self.failure or 'clock_restart_or_duplicate'
            else:
                self.device_elapsed += delta/1e6
            if host_now < self.last_host:
                self.failure = self.failure or 'host_clock_went_backwards'
            self.last_host = host_now
        elapsed = host_now-self.start_host
        raw_error = elapsed-self.device_elapsed
        # Check against the existing mapping BEFORE admitting new fit samples.
        residual = elapsed-(self.offset+self.rate*self.device_elapsed)
        if abs(residual) > self.policy.max_progress_error_s:
            self.failure = self.failure or 'host_sensor_timing_mismatch'
        if not self.failure and self.state == 'collecting' and eligible:
            self.samples.append((self.device_elapsed, elapsed))
            if self.device_elapsed >= self.policy.fit_span_s and len(self.samples) >= self.policy.min_samples:
                x,y = np.array(self.samples).T
                centered = x-x.mean()
                rate = float(np.dot(centered, y-y.mean())/np.dot(centered, centered))
                offset = float(np.median(y-rate*x))
                errors = abs(y-(offset+rate*x))
                if abs(rate-1) > self.policy.max_rate_error:
                    self.failure = 'clock_rate_out_of_bounds'
                elif (float(np.max(errors)) > self.policy.max_fit_residual_s or
                      float(np.percentile(errors,95)) > self.policy.p95_fit_residual_s):
                    self.failure = 'clock_fit_unstable'
                else:
                    self.rate, self.offset = rate, offset
                    self.state = 'frozen'
                    residual = elapsed-(self.offset+self.rate*self.device_elapsed)
        if not self.failure and self.state == 'collecting' and self.device_elapsed > self.policy.max_fit_span_s:
            self.failure = 'clock_fit_unavailable'
        if self.failure:
            self.state = 'invalid'
        return dict(reason=self.failure, state=self.state,
                    host_seconds_per_device_second=self.rate, offset_s=self.offset,
                    residual_s=residual, raw_residual_s=raw_error,
                    device_elapsed_s=self.device_elapsed, host_elapsed_s=elapsed,
                    fit_samples=len(self.samples))
