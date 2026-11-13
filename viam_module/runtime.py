"""Single-owner acquisition worker with reconnect and stale-data protection."""
import copy
import hashlib
import math
import queue
import threading
import time
import sys
import uuid
from pathlib import Path

import serial
import numpy as np
from radar.range_azimuth import load_reference
from radar.acquisition import Source
from .processing import EchoProcessor, config_path, radar_config
from .raw_frame import encode_raw


def validate(attributes):
    port = attributes.get('serial_port')
    if not isinstance(port, str) or not Path(port).is_absolute():
        raise ValueError('serial_port must be an absolute device path')
    cfg = radar_config(attributes)
    for key, default, allow_zero in [('min_range_m', .5, True), ('max_range_m', 3, False),
                                     ('stale_after_s', 1, False), ('reconnect_delay_s', 1, False)]:
        value = attributes.get(key, default)
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0 or (not allow_zero and value == 0)):
            raise ValueError(f'{key} must be finite and {"nonnegative" if allow_zero else "positive"}')
    if attributes.get('min_range_m', .5) >= attributes.get('max_range_m', 3):
        raise ValueError('min_range_m must be less than max_range_m')
    if type(attributes.get('enable_angles', True)) is not bool:
        raise ValueError('enable_angles must be boolean')
    if 'angle_reference_path' in attributes:
        path = attributes['angle_reference_path']
        xyz = np.asarray(attributes.get('reference_xyz_m'), dtype=float)
        if not isinstance(path, str) or not Path(path).is_absolute():
            raise ValueError('angle_reference_path must be an absolute recording directory on the host')
        if xyz.shape != (3,) or not np.isfinite(xyz).all() or xyz[1] <= 0:
            raise ValueError('reference_xyz_m requires finite [right, forward, up], forward > 0')
        z = attributes.get('target_z_m', float(xyz[2]))
        if isinstance(z, bool) or not isinstance(z, (int, float)) or not math.isfinite(z):
            raise ValueError('target_z_m must be finite')
    return cfg


class RadarRuntime:
    def __init__(self, attributes, source_factory=Source, clock=time.monotonic):
        self.config = validate(attributes)
        self.attributes = dict(attributes)
        self.reference = None
        if 'angle_reference_path' in attributes:
            xyz = attributes['reference_xyz_m']
            phase = load_reference(attributes['angle_reference_path'], xyz, self.config)
            self.reference = (phase, xyz, attributes.get('target_z_m', xyz[2]))
        self.source_factory, self.clock = source_factory, clock
        self.stale_after = attributes.get('stale_after_s', 1)
        self.reconnect_delay = attributes.get('reconnect_delay_s', 1)
        revision_path = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])) / 'viam_module/source_revision.txt'
        self.source_revision = revision_path.read_text().strip() if revision_path.is_file() else 'working-tree'
        self.config_hash = hashlib.sha256(config_path(attributes).read_bytes()).hexdigest()
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.commands = queue.Queue(maxsize=8)
        self.snapshot = None
        self.raw_frame = None
        self.captured_at_unix = None
        self.frame_counter = 0
        self.session_id = uuid.uuid4().hex
        self.received_at = None
        self.state, self.error = 'starting', None
        self.reconnects = 0
        self.thread = threading.Thread(target=self._run, name='upenn-mmwave-reader', daemon=True)
        self.thread.start()

    def _state(self, state, error=None, clear=False):
        with self.lock:
            self.state, self.error = state, error
            if clear:
                self.snapshot = None
                self.raw_frame = None
                self.captured_at_unix = None
                self.received_at = None

    def readings(self):
        with self.lock:
            age = None if self.received_at is None else self.clock()-self.received_at
            healthy = self.state == 'streaming' and age is not None and age <= self.stale_after
            result = copy.deepcopy(self.snapshot) if healthy else dict(
                detected=False, echo_count=0, echoes=[], distance_m=None,
                azimuth_deg=None, elevation_deg=None, doppler_cycles_per_chirp=None,
                doppler_hz=None, radial_velocity_mps=None, doppler_resolved=False,
            )
            state = 'stale' if self.state == 'streaming' and not healthy else self.state
            result.update(healthy=healthy, state=state, error=self.error,
                          frame_age_s=age, reconnect_count=self.reconnects,
                          config_path=self.attributes['config_path'], config_sha256=self.config_hash,
                          model='carlyworkspace:upenn-mmwave:infineon-mmwave',
                          adapter_version='1.1.0', source_commit=self.source_revision)
            return result

    def command(self, command):
        name = command.get('command')
        if name == 'raw_frame':
            return self.latest_raw_frame()
        if name == 'status':
            return self.readings()
        if name not in ('capture_background', 'clear_background'):
            raise ValueError('Supported commands: status, raw_frame, capture_background, clear_background')
        frames = command.get('frames', 30)
        if (isinstance(frames, bool) or not isinstance(frames, (int, float))
                or not math.isfinite(frames) or frames != int(frames) or not 10 <= frames <= 300):
            raise ValueError('frames must be an integer from 10 through 300')
        with self.lock:
            if self.state != 'streaming':
                raise RuntimeError('Background commands require a streaming sensor')
            try:
                self.commands.put_nowait((name, int(frames)))
            except queue.Full:
                raise RuntimeError('Background command queue is full') from None
        return {'accepted': True, 'command': name}

    def latest_raw_frame(self):
        # Export the original validated ADC, not the echo list or a reconstructed
        # image. Never block acquisition on reconstruction or serial access.
        with self.lock:
            age = None if self.received_at is None else self.clock()-self.received_at
            if (self.state != 'streaming' or self.raw_frame is None
                    or age is None or age > self.stale_after or self.stop.is_set()):
                raise RuntimeError(f'Raw radar frame unavailable ({self.state}): {self.error or "waiting for fresh data"}')
            return encode_raw(self.raw_frame, self.config,
                frame_id=f'{self.session_id}:{self.frame_counter}',
                captured_at_unix=self.captured_at_unix,
                age=age, stale_after=self.stale_after)

    def close(self):
        self.stop.set()
        self.thread.join(5)
        if self.thread.is_alive():
            raise RuntimeError('Reader did not stop within five seconds; do not open a second reader')

    def _run(self):
        while not self.stop.is_set():
            source = None
            try:
                # No background survives a reconnect: the board/mount may have moved.
                processor = EchoProcessor(self.config,
                    self.attributes.get('min_range_m', .5),
                    self.attributes.get('max_range_m', 3),
                    self.attributes.get('enable_angles', True))
                processor.reference = self.reference
                source = self.source_factory(self.config, port=self.attributes['serial_port'])
                last_frame = self.clock()
                previous_identity = None
                while not self.stop.is_set():
                    try:
                        name, frames = self.commands.get_nowait()
                        if name == 'capture_background':
                            processor.capture_background(frames)
                        else:
                            processor.clear_background()
                    except queue.Empty:
                        pass
                    frame = source.read()
                    if frame is None or (frame.sequence, frame.timestamp_us) == previous_identity:
                        if self.clock()-last_frame > max(2, self.stale_after):
                            raise TimeoutError('No fresh radar frames; reconnecting serial device')
                        continue
                    received = self.clock()
                    captured_at_unix = time.time()
                    previous_identity = (frame.sequence, frame.timestamp_us)
                    snapshot = processor.process(frame)
                    snapshot.update(crc_errors=source.parser.bad_crc,
                                    bad_headers=source.parser.bad_headers,
                                    sequence_gaps=source.parser.gaps)
                    with self.lock:
                        self.snapshot = snapshot
                        self.raw_frame = frame
                        self.captured_at_unix = captured_at_unix
                        self.frame_counter += 1
                        self.received_at = last_frame = received
                        self.state, self.error = 'streaming', None
            except (serial.SerialException, OSError, TimeoutError) as error:
                self._state('reconnecting', str(error), clear=True)
                with self.lock:
                    self.reconnects += 1
            except Exception as error:
                # Config/protocol/processing errors are not cured by endless retries.
                self._state('error', f'{type(error).__name__}: {error}', clear=True)
                break
            finally:
                if source is not None:
                    try:
                        source.close()
                    except (serial.SerialException, OSError):
                        pass
                while True:
                    try:
                        self.commands.get_nowait()
                    except queue.Empty:
                        break
            if not self.stop.is_set():
                self.stop.wait(self.reconnect_delay)
        if self.stop.is_set():
            self._state('closed', clear=True)
