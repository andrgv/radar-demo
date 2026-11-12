"""Record timing bounds from existing captures without treating them as chirp measurements."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from radar.storage import replay


ROOT = Path(__file__).resolve().parents[1]
SOURCES = [ROOT/'recordings/gui-20261110-162410-575208'/f'live-{i:03}' for i in (1, 2)]
SCOPE = ROOT/'build/scope-timing/APP_CYSBSYSKIT-DEV-01/Release/glass-radar-3rx.hex'
C = 299792458


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(sources=SOURCES, scope=SCOPE):
    captures = []
    for path in sources:
        frames = list(replay(path))
        elapsed = np.array([f.capture_elapsed_us for f in frames if f.capture_elapsed_us is not None])
        if len(elapsed) != len(frames) or len(frames) < 1:
            raise ValueError(f'Missing elapsed field in {path}')
        if any(f.adc.shape != (17, 64, 3) for f in frames):
            raise ValueError(f'Unexpected frame shape in {path}')
        captures.append(dict(recording=str(path.relative_to(ROOT)), raw_sha256=sha(path/'frames.grd'),
                             frames=len(frames), acquired_chirps=17, retained_chirps=16,
                             acquisition_path_elapsed_us=dict(min=int(elapsed.min()),
                                p05=float(np.percentile(elapsed, 5)), median=float(np.median(elapsed)),
                                p95=float(np.percentile(elapsed, 95)), max=int(elapsed.max()))))
    longest_us=max(x['acquisition_path_elapsed_us']['max'] for x in captures)
    # Any 16 consecutive uniformly spaced retained chirps have 15 start intervals.
    # This conservative bound counts the entire trigger/readout/stop duration.
    t_upper=longest_us/15*1e-6
    illustrative_carrier=60e9
    wavelength=C/illustrative_carrier
    return dict(schema=1, captures=captures,
        scope_image=dict(path=str(scope.relative_to(ROOT)), exists=scope.is_file(),
                         sha256=sha(scope) if scope.is_file() else None,
                         profile_id='0x33515301', flashed=False, measured=False),
        source_sha256=sha(Path(__file__)),
        condition='All 16 retained blocks are sequential coherent chirps, uniformly spaced, fully contained between the MCU trigger and completion timestamps.',
        inference='If the condition holds, 15 chirp-start intervals fit within the maximum acquisition-path elapsed time. This is an upper bound, not a measured interval.',
        chirp_interval_upper_bound_us_if_uniform=longest_us/15,
        assumed_carrier_hz_for_illustration=illustrative_carrier,
        actual_carrier_verified=False,
        native_doppler_bin_cycles_per_chirp=1/16,
        velocity_bin_spacing_lower_bound_mps_if_uniform_and_60ghz=wavelength/(2*16*t_upper),
        illustrative_spacing_mps_for_T_us={str(t):wavelength/(2*16*t*1e-6) for t in (25, 50, 100, 200)},
        unresolved='Actual chirp spacing, uniformity, raw-block/edge correspondence, carrier and physical Doppler sign. The scope marker and matching raw capture must be measured.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'evidence/rd-timing-feasibility-20261110/feasibility.json')
    args=parser.parse_args()
    report=assess()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2))
    print(json.dumps({key:report[key] for key in ('chirp_interval_upper_bound_us_if_uniform',
        'velocity_bin_spacing_lower_bound_mps_if_uniform_and_60ghz','scope_image')},indent=2))


if __name__=='__main__':
    main()
