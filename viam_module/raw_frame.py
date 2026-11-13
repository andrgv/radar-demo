"""Versioned, bounded raw-frame exchange over Sensor.DoCommand.

The camera is a Viam dependency client, not an in-process pointer to the sensor.
JSON text preserves integer config fields through protobuf Struct conversion.
"""
import base64
import hashlib
import json
import math
from dataclasses import asdict

import numpy as np
from radar.config import Config
from radar.protocol import Frame

MAX_ADC_BYTES = 1024 * 1024


def encode_raw(frame, config, *, frame_id, captured_at_unix, age, stale_after):
    config_json = json.dumps(asdict(config), sort_keys=True, allow_nan=False)
    return dict(
        schema='upenn-mmwave/raw-frame/v1', frame_id=frame_id,
        adc_base64=base64.b64encode(np.asarray(frame.adc, dtype='<u2').tobytes()).decode('ascii'),
        radar_config_json=config_json,
        radar_config_sha256=hashlib.sha256(config_json.encode()).hexdigest(),
        sequence=int(frame.sequence), timestamp_us=int(frame.timestamp_us),
        profile_id=int(frame.profile_id), flags=int(frame.flags),
        dropped=int(frame.dropped), errors=int(frame.errors),
        captured_at_unix=captured_at_unix, frame_age_s=age,
        stale_after_s=stale_after,
    )


def _number(value, name, *, minimum=0, maximum=math.inf, integer=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not minimum <= value <= maximum
            or (integer and value != int(value))):
        raise ValueError(f'Invalid raw-frame {name}')
    return int(value) if integer else float(value)


def decode_raw(packet, maximum_age):
    if packet.get('schema') != 'upenn-mmwave/raw-frame/v1':
        raise ValueError('Dependency is not an updated upenn-mmwave raw-frame sensor')
    frame_id = packet.get('frame_id')
    if not isinstance(frame_id, str) or not 1 <= len(frame_id) <= 200:
        raise ValueError('Invalid raw-frame identity')
    age = _number(packet.get('frame_age_s'), 'age')
    source_limit = _number(packet.get('stale_after_s'), 'stale threshold', minimum=1e-9)
    if age > min(source_limit, maximum_age):
        raise RuntimeError('Radar frame is stale; refusing to return an old cloud')
    captured = _number(packet.get('captured_at_unix'), 'capture timestamp', minimum=1)
    encoded = packet.get('adc_base64')
    cfg_json = packet.get('radar_config_json')
    if not isinstance(encoded, str) or len(encoded) > ((MAX_ADC_BYTES+2)//3)*4:
        raise ValueError('Raw frame exceeds bounded ADC payload')
    if not isinstance(cfg_json, str) or len(cfg_json) > 16384:
        raise ValueError('Invalid raw-frame configuration')
    digest = hashlib.sha256(cfg_json.encode()).hexdigest()
    if digest != packet.get('radar_config_sha256'):
        raise ValueError('Raw-frame configuration hash mismatch')
    cfg = Config(**json.loads(cfg_json)).validate()
    for key, lo, hi in [('samples',16,2048),('chirps',8,1024),('discard_chirps',0,1023)]:
        _number(getattr(cfg,key),key,minimum=lo,maximum=hi,integer=True)
    data = base64.b64decode(encoded, validate=True)
    expected = cfg.chirps*cfg.samples*3*2
    if len(data) != expected or expected > MAX_ADC_BYTES:
        raise ValueError('Raw-frame byte count does not match acquisition dimensions')
    values = {key: _number(packet.get(key),key,maximum=0xffffffff,integer=True)
              for key in ['sequence','timestamp_us','profile_id','flags','dropped','errors']}
    if values['profile_id'] != cfg.profile_id or not values['flags'] & 1 or values['flags'] & 8:
        raise ValueError('Point cloud requires matching non-averaged raw radar frames')
    if values['errors']:
        raise ValueError('Radar reports acquisition errors')
    adc = np.frombuffer(data, dtype='<u2').reshape(cfg.chirps,cfg.samples,3)
    return Frame(adc=adc, **values), cfg, dict(
        frame_id=frame_id, config_sha256=digest, captured_at_unix=captured,
        source_age_s=age, maximum_age_s=min(source_limit, maximum_age),
    )
