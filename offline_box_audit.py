#!/usr/bin/env python3
"""Read-only exploratory audit of an existing 3-RX box-angle sweep.

Usage (from radar-demo repo root):
    .venv/bin/python offline_box_audit.py recordings/box-angle-01

Requires box-sweep-diagnostics.json produced by tools/box_sweep_followup.py.
Reads saved JSON only. Never opens a serial port, writes to the sweep, or
produces a calibration configuration.
"""
import argparse
import json
import math
from pathlib import Path

HORIZONTAL = ("check_left", "center_repeat", "check_right")


def wrap(angle):
    return (float(angle) + 180.0) % 360.0 - 180.0


def vector(x, y, z):
    return math.sqrt(x*x + y*y + z*z)


def get_direction_x(row):
    return float(row["direction_right_up"][0])


def fit_two(a, b, field):
    xa, xb = get_direction_x(a), get_direction_x(b)
    if abs(xb - xa) < 1e-8:
        raise ValueError("Positions have negligible horizontal separation")
    pa = [float(v) for v in a[field]]
    pb = [float(v) for v in b[field]]
    slope = [wrap(q - p) / (xb - xa) for p, q in zip(pa, pb)]
    return (xa, pa, slope)


def predict(model, x):
    anchor_x, anchor_phases, slopes = model
    return [wrap(p + b*(x-anchor_x)) for p,b in zip(anchor_phases, slopes)]


def residual(predicted, observed):
    return [wrap(o-p) for o,p in zip(observed, predicted)]


def estimate_horizontal(predicted, observed, slope):
    # Linear least-squares estimate in direction-cosine units (small angles).
    errors = residual(predicted, observed)
    den = sum(b*b for b in slope)
    return sum(e*b for e,b in zip(errors,slope))/den if den > 1e-12 else None


def audit(rows, field):
    missing = set(HORIZONTAL) - set(rows)
    if missing:
        raise ValueError(f"Missing pose(s): {', '.join(sorted(missing))}")
    for name in HORIZONTAL:
        if not rows[name].get("accepted_previous", False):
            raise ValueError(f"Strong-position check rejected: {name}")
    support = {rows[name]["support"] for name in HORIZONTAL}
    if len(support) != 1:
        raise ValueError("Horizontal controls were not recorded on the same support")

    left = rows["check_left"]
    right = rows["check_right"]
    midpoint = rows["center_repeat"]
    full_model = fit_two(left, right, field)
    cross_mid = predict(full_model, get_direction_x(midpoint))
    mid_resid = residual(cross_mid, midpoint[field])
    slope = full_model[-1]
    # 360 deg/u maps to a 1-wavelength baseline. Nominal RX2 is vertical, RX3 horizontal.
    baselines = [b/360 for b in slope]
    mid_dir_err = estimate_horizontal(cross_mid, midpoint[field], slope)
    loo = []
    for held in HORIZONTAL:
        train = [rows[n] for n in HORIZONTAL if n != held]
        model = fit_two(train[0], train[1], field)
        p = rows[held]
        pp = predict(model, get_direction_x(p))
        diffs = residual(pp, p[field])
        xerr = estimate_horizontal(pp, p[field], model[-1])
        # arcsin(u_x) approximately horizontal bearing when elevation is small.
        xtrue = get_direction_x(p)
        if xerr is None or not -1 <= xtrue+xerr <= 1:
            bearing_error = None
        else:
            bearing_error = math.degrees(math.asin(xtrue+xerr) - math.asin(xtrue))
        loo.append((held, diffs, bearing_error))
    return baselines, mid_resid, mid_dir_err, loo


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sweep", type=Path, help="Folder containing box-sweep-diagnostics.json")
    args=parser.parse_args()
    root=args.sweep
    path = root / "box-sweep-diagnostics.json"
    with path.open(encoding="utf-8") as f:
        document=json.load(f)
    rows={r["name"]:r for r in document["poses"]}
    print(f"Dataset: {root} (offline; read-only)")
    print("Same-support horizontal subset: check_left (-15 cm), center_repeat (0), check_right (+15 cm)")
    print("These are the ONLY original quality-PASS positions on the same support that span both horizontal signs.")
    print("(The two ±30 cm positions failed the original quality gate.)")
    nominal = document.get("nominal_baselines_wavelengths_rx2_rx3")
    if nominal is not None:
        nominal_horizontal = [float(row[0]) for row in nominal]
    else:
        nominal_horizontal = [0.0, -0.47]  # Fallback for the known hpf350 profile
    for label,field in [("BACKGROUND-SUBTRACTED", "relative_phase_deg"),
                        ("RAW TARGET (NO SUBTRACTION)", "raw_target_phase_deg_rx2_rx3")]:
        try:
            baselines,midres,xerr,loo=audit(rows,field)
        except (ValueError,KeyError) as e:
            print(f"{label}: unavailable: {e}")
            continue
        print(f"\n{label}")
        print(f"  Apparent horizontal phase slopes (RX2,RX3): {baselines[0]:+.3f}, {baselines[1]:+.3f} wavelengths")
        print(f"  Compare nominal horizontal baselines: RX2 {nominal_horizontal[0]:+.3f}, RX3 {nominal_horizontal[1]:+.3f} wavelengths")
        print(f"  Independent center-repeat phase residual (RX2,RX3): {midres[0]:+.2f}°, {midres[1]:+.2f}°")
        if xerr is not None:
            print(f"  Center-repeat inferred horizontal direction error: {math.degrees(math.asin(max(-1,min(1,xerr)))):+.2f}° (exploratory only)")
        print("  Leave-one-position-out phase residuals and inferred bearing errors:")
        for held,rr,b_err in loo:
            err = f"{b_err:+.2f}°" if b_err is not None else "not identifiable"
            print(f"    {held:<13} RX2 {rr[0]:+6.2f}°, RX3 {rr[1]:+6.2f}°, bearing {err}")
    print("\nINTERPRETATION (not a certified calibration):")
    print("- If RAW and SUBTRACTED horizontal slopes both disagree with nominal, subtraction alone cannot explain the disagreement.")
    print("- If RAW is near nominal but SUBTRACTED is not, subtraction likely distorts phases.")
    print("- Even a small three-point horizontal leave-one-out error does NOT establish 2D azimuth/elevation accuracy.")
    print("- The accepted vertical points use different support arrangements; height and support/multipath effects remain confounded.")
    print("- No calibration JSON is written; original recordings and official quality gates are untouched.")


if __name__=='__main__':
    main()
