#!/usr/bin/env python3
"""Non-flashing GRD3 compatibility probe for the radar-demo repository.

Run from repo root: .venv/bin/python /path/to/check_radar_firmware.py --port /dev/ttyACM0
Sends only normal stream-start/stream-stop commands; never programs the device.
"""
import argparse
import sys
import time

import serial
from radar.protocol import Parser

KNOWN_PROFILES = {
    0x33514801: "qualification-hpf100 (100 kHz)",
    0x33514802: "qualification-hpf350 (350 kHz)",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--port', required=True, help='Serial port, e.g. /dev/ttyACM0')
    ap.add_argument('--seconds', type=float, default=8)
    args = ap.parse_args()
    if not 1 <= args.seconds <= 30:
        ap.error('--seconds must be between 1 and 30')
    parser = Parser()
    frames = []
    try:
        with serial.Serial(args.port, 2_000_000, timeout=0.15, write_timeout=1) as device:
            device.reset_input_buffer()
            device.write(b'B')  # start standard streaming; no flash
            try:
                deadline = time.monotonic() + args.seconds
                while time.monotonic() < deadline and len(frames) < 10:
                    data = device.read(max(1, min(device.in_waiting, 65536)))
                    if data:
                        frames.extend(parser.feed(data))
            finally:
                device.write(b'c')  # stop standard streaming
                device.flush()
    except serial.SerialException as exc:
        print(f'Serial port error: {exc}', file=sys.stderr)
        return 2

    print(f'Valid GRD3 packets: {len(frames)}')
    print(f'Parser errors: bad_crc={parser.bad_crc}, bad_headers={parser.bad_headers}, '
          f'sequence_gaps={parser.gaps}, discarded_bytes={parser.discarded_bytes}')
    if not frames:
        print('NO VALID GRD3 PACKETS. Check port, power, permissions, baud and '
              'whether the loaner changed firmware; this does not prove flashing is needed.')
        return 1
    profiles = {frame.profile_id for frame in frames}
    shapes = {frame.adc.shape for frame in frames}
    print('Profile IDs:', ', '.join(f'0x{p:08X} ({KNOWN_PROFILES.get(p,"unknown")})' for p in sorted(profiles)))
    print('ADC shapes:', ', '.join(str(x) for x in sorted(shapes)))
    print('Capture elapsed present:', all(f.capture_elapsed_us is not None for f in frames))
    print('First/last counters:',
          f'dropped={frames[0].dropped}/{frames[-1].dropped},'
          f' errors={frames[0].errors}/{frames[-1].errors}')
    if len(profiles) == 1 and profiles.issubset(KNOWN_PROFILES) and shapes == {(17, 64, 3)} \
            and all(f.flags & 1 for f in frames) and parser.bad_crc == 0 \
            and parser.bad_headers == 0 and parser.gaps == 0 \
            and frames[0].dropped == frames[-1].dropped and frames[0].errors == frames[-1].errors:
        profile = next(iter(profiles))
        config = 'configs/qualification-hpf100.json' if profile == 0x33514801 else 'configs/qualification-hpf350.json'
        print('PASS: basic firmware/data compatibility. No reflash indicated.')
        print('Use sweep --config', config)
        return 0
    print('NOT ACCEPTED for calibration: profile or packet health needs investigation before sweep.')
    return 1

if __name__ == '__main__':
    raise SystemExit(main())
    