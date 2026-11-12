"""Analyze measured CHIRP_ACTIVE rising-edge times; never infer them from frames."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np


def analyze(path):
    with Path(path).open(newline='') as stream:
        rows=list(csv.DictReader(stream))
    if not rows or 'time_us' not in rows[0]:
        raise ValueError('CSV needs time_us header and at least two edges per burst')
    bursts={}
    for row in rows:
        key=row.get('burst_id') or 'burst-1'
        bursts.setdefault(key,[]).append(float(row['time_us']))
    output=[]
    for key,values in bursts.items():
        stamps=np.array(values,dtype=float)
        if len(stamps)<2 or not np.isfinite(stamps).all():
            raise ValueError(f'{key}: need at least two finite edges')
        intervals=np.diff(stamps)
        if np.any(intervals<=0):
            raise ValueError(f'{key}: edges must be strictly increasing in each burst')
        median=float(np.median(intervals))
        output.append(dict(burst_id=key, rising_edges=len(stamps), intervals_us=intervals.tolist(),
            median_interval_us=median, min_interval_us=float(intervals.min()),
            max_interval_us=float(intervals.max()),
            max_relative_deviation_from_median=float(np.max(np.abs(intervals-median))/median),
            first_interval_us=float(intervals[0]),
            total_first_to_last_us=float(stamps[-1]-stamps[0])))
    return dict(schema=1, input=str(Path(path).resolve()), bursts=output,
                interpretation='Sensor CHIRP_ACTIVE edge schedule only. Verify which edges correspond to saved chirps, same ramp/sample timing, carrier and phase before physical Doppler claims. Do not join bursts.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    report=analyze(args.csv)
    result=json.dumps(report,indent=2)
    if args.output:
        args.output.write_text(result+'\n')
    print(result)


if __name__=='__main__':
    main()
