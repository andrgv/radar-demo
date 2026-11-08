"""Track receiver-specific peaks through saved door transitions without labels.

Labels and pane distances are used only after full-stream peak tracking.
Tracks can belong to operator, frame, background or multipath, not just glass.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from radar.config import Config


def track_peaks(power, times):
    """RX-specific local maxima, quadratic log interpolation, fixed association.

    No pane range, door state, scene reference, or manually chosen RX input.
    Peak positions are provisional frequency coordinates, not object distances.
    """
    tracks=[]
    for rx in range(power.shape[2]):
        active=[]
        for index, t in enumerate(times):
            db=10*np.log10(np.maximum(power[index,:,rx],1e-12))
            peaks=[]
            for b in range(1,len(db)-1):
                if db[b]>=db[b-1] and db[b]>db[b+1]:
                    curvature=db[b-1]-2*db[b]+db[b+1]
                    offset=float(np.clip(.5*(db[b-1]-db[b+1])/curvature,-.5,.5)) if curvature<0 else 0.
                    peaks.append((b+offset,float(db[b])))
            # Greedy closest-frequency association; ambiguous merges remain a limitation.
            pairs=sorted((abs(track['points'][-1][1]-peak[0]), j, k)
                         for j,track in enumerate(active) for k,peak in enumerate(peaks)
                         if 0<t-track['points'][-1][0]<=.3)
            used_tracks=set();used_peaks=set()
            for difference,j,k in pairs:
                if difference>.75:break
                if j in used_tracks or k in used_peaks:continue
                used_tracks.add(j);used_peaks.add(k)
                active[j]['points'].append([float(t),*peaks[k]])
            expired=[track for track in active if t-track['points'][-1][0]>.3]
            tracks.extend(expired)
            active=[track for track in active if t-track['points'][-1][0]<=.3]
            for k,peak in enumerate(peaks):
                if k not in used_peaks:active.append(dict(rx=rx+1,points=[[float(t),*peak]]))
        tracks.extend(active)
    return [track for track in tracks if len(track['points'])>=5]


def audit(recordings,cache,output):
    recordings,cache,output=Path(recordings),Path(cache),Path(output)
    output.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((cache/'summary.json').read_text())['sessions']
    report={}
    for name,session in manifest.items():
        data=np.load(cache/f'{name}-stream.npz')
        times=(data['host_unix_ns']-data['host_unix_ns'][0])/1e9
        tracks=track_peaks(data['mean_power'],times)
        config=Config.load(recordings/name/'config.json')
        distance=json.loads((recordings/name/'door-check.json').read_text())['measured_glass_distance_m']
        spacing=299792458*config.sample_rate_hz/(2*config.slope_hz_s*config.samples)
        expected=distance/spacing
        intervals=[]
        for interval in session['intervals']:
            start=interval['start_s'];end=min(start+5,interval['end_s'])
            matches=[]
            for identifier,track in enumerate(tracks):
                points=np.array(track['points'])
                following=points[(points[:,0]>=start)&(points[:,0]<=end)]
                if len(following)<20:continue
                frequency=float(np.median(following[:,1]))
                if abs(frequency-expected)>1:continue
                preceding=points[(points[:,0]>=start-15)&(points[:,0]<start)]
                matches.append(dict(track=identifier,rx=track['rx'],median_capture_bin=frequency,
                    capture_peak_to_peak_bins=float(np.ptp(following[:,1])),
                    preceding_points=len(preceding),
                    preceding_bin_span=preceding[:,1].tolist() if len(preceding) else [],
                    track_start_s=track['points'][0][0],track_end_s=track['points'][-1][0]))
            intervals.append(dict(name=interval['name'],start_s=start,near_pane_tracks=matches))
        report[name]=dict(expected_fractional_bin=expected,intervals=intervals,tracks=tracks)
        print(name,[(v['name'],[(t['rx'],round(t['median_capture_bin'],2),round(t['track_start_s'],1))
                    for t in v['near_pane_tracks']]) for v in intervals],flush=True)
    (output/'tracks.json').write_text(json.dumps(dict(method=__doc__,sessions=report),indent=2,allow_nan=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('recordings');p.add_argument('cache');p.add_argument('output')
    a=p.parse_args();audit(a.recordings,a.cache,a.output)
