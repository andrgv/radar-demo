import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import time
import math
from .config import Config
from .processing import Processor
from .storage import Recorder, replay
from .synthetic import generate


def main(argv=None):
    parser = argparse.ArgumentParser(description="Three-RX radar acquisition and material feature research")
    commands = parser.add_subparsers(dest="command", required=True)
    gui = commands.add_parser("gui")
    gui.add_argument("--config")
    inputs = gui.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--synthetic", action="store_true", help="Show simulated targets; does not read the radar")
    inputs.add_argument("--port")
    inputs.add_argument("--replay")
    gui.add_argument("--record")
    gui.add_argument('--seconds', type=float, help='Stop acquisition, save recording and exit after this many seconds')
    gui.add_argument('--start-delay', type=float, default=0, help='Visible setup countdown in seconds before acquisition starts')
    gui.add_argument('--spatial-map', action='store_true', help='Show per-frame 3D reflectivity volume, not reconstructed surfaces')
    gui.add_argument('--point-cloud',action='store_true',help='Extract range-Doppler scattering centers with joint azimuth/elevation fitting')
    gui.add_argument("--metadata")
    gui.add_argument("--phase-probe", type=float, metavar="METERS",
                     help="Diagnostic phase estimate at a fixed range bin; not a detected/tracked object")
    gui.add_argument("--mount-roll", type=float, metavar="DEGREES",
                     help="Counterclockwise array rotation in the antenna-face drawing; does not change boresight")
    gui.add_argument("--background", metavar="RECORDING_OR_NPZ",
                     help="Experimental fixed complex-spectrum subtraction from a matching static scene")
    synthetic = commands.add_parser("synthetic")
    synthetic.add_argument("output")
    synthetic.add_argument("--frames", type=int, default=100)
    record = commands.add_parser("record")
    record.add_argument("output")
    record.add_argument("--port", required=True)
    record.add_argument("--config", required=True)
    record.add_argument("--metadata", required=True)
    record.add_argument("--seconds", type=float, default=60)
    record.add_argument("--background", metavar="RECORDING_OR_NPZ")
    analyze = commands.add_parser("analyze")
    analyze.add_argument("recording")
    diagnostic = commands.add_parser("diagnose", help="Inspect raw ADC health and per-RX spectral bins")
    diagnostic.add_argument("recording")
    calibration = commands.add_parser("calibrate")
    calibration.add_argument("recording")
    calibration.add_argument("output")
    calibration.add_argument("--distance", type=float, required=True)
    calibration.add_argument("--azimuth", type=float, default=0)
    calibration.add_argument("--elevation", type=float, default=0)
    benchmark = commands.add_parser("benchmark")
    benchmark.add_argument("--frames", type=int, default=200)
    research = commands.add_parser("research")
    research.add_argument("root")
    research.add_argument("output")
    research.add_argument("--heldout-scenes", nargs="+", required=True)
    sweep = commands.add_parser("sweep", help="Guided fixed-radar angular characterization with measured target positions")
    sweep.add_argument("output")
    sweep.add_argument("--port", required=True)
    sweep.add_argument("--config", required=True)
    sweep.add_argument("--distance", type=float, default=1.3)
    sweep.add_argument("--offset", type=float, default=0.3)
    sweep.add_argument("--seconds", type=float, default=5)
    sweep.add_argument("--handheld", action="store_true",
                       help="Label approximate handheld positions; qualitative response test, not precision calibration")
    sweep_analysis = commands.add_parser("sweep-analyze", help="Reprocess a saved guided angular sweep")
    sweep_analysis.add_argument("recording")
    audit = commands.add_parser("audit", help="Offline raw ADC, packing and register-profile audit")
    audit.add_argument("recordings")
    audit.add_argument("--output", required=True)
    audit.add_argument("--profile", default="firmware/vendor/presence_detection_tracking.h")
    paired = commands.add_parser('paired-audit', help='Paired target/control covariance, uncertainty and bin-23 audit')
    paired.add_argument('recordings')
    paired.add_argument('--config', required=True)
    paired.add_argument('--output', required=True)
    arguments = parser.parse_args(argv)
    if arguments.command == "gui":
        if not math.isfinite(arguments.start_delay) or arguments.start_delay < 0:
            parser.error('--start-delay must be finite and nonnegative')
        if arguments.seconds is not None and (not math.isfinite(arguments.seconds) or arguments.seconds <= 0):
            parser.error('--seconds must be finite and greater than zero')
        if arguments.port and not arguments.config:
            parser.error("Hardware acquisition requires --config; start with configs/hardware-provisional.json")
        config = Config.load(arguments.config) if arguments.config else (
            Config.load(Path(arguments.replay) / "config.json") if arguments.replay else
            Config(chirp_timing_verified=True,carrier_frequency_verified=True))
        if arguments.mount_roll is not None:
            config = replace(config, mount_roll_deg=arguments.mount_roll).validate()
        metadata = json.loads(Path(arguments.metadata).read_text()) if arguments.metadata else None
        background_path = arguments.background
        if background_path is None and arguments.replay:
            snapshot = Path(arguments.replay) / "spectral-background.npz"
            if snapshot.exists():
                background_path = str(snapshot)
        from .gui import run
        return run(config, port=arguments.port, recording=arguments.replay, record=arguments.record,
                   metadata=metadata, phase_probe_range=arguments.phase_probe, background_path=background_path,
                   spatial_map=arguments.spatial_map, seconds=arguments.seconds, start_delay=arguments.start_delay,
                   point_cloud=arguments.point_cloud)
    if arguments.command == "synthetic":
        config = Config(calibration_id="synthetic-known-geometry", verified=True,
                        chirp_timing_verified=True,carrier_frequency_verified=True)
        processor = Processor(config)
        with Recorder(arguments.output, config, {"label": "synthetic", "scene_id": "synthetic"}) as recorder:
            for sequence in range(1, arguments.frames + 1):
                frame = generate(config, sequence, seed=sequence)
                recorder.write(frame, processor.process(frame))
        print(f"Recorded {arguments.frames} synthetic frames to {arguments.output}")
    elif arguments.command == "record":
        from .acquisition import Source, paced_frames
        config = Config.load(arguments.config)
        metadata = json.loads(Path(arguments.metadata).read_text(encoding="utf-8"))
        from .background import SpectralBackground
        background = SpectralBackground.from_path(arguments.background, config) if arguments.background else None
        metadata["background_method"] = "fixed_complex_spectrum" if background else "none"
        metadata["background_source"] = arguments.background
        source = Source(config, port=arguments.port)
        processor = Processor(config, background=background)
        deadline = time.monotonic() + arguments.seconds
        try:
            with Recorder(arguments.output, config, metadata) as recorder:
                source.transport_recorder = recorder
                if background is not None:
                    background.save(recorder.path / "spectral-background.npz")
                while time.monotonic() < deadline:
                    frame = source.read()
                    if frame is None:
                        continue
                    recorder.write(frame, processor.process(frame))
                print(json.dumps({"recorded": recorder.count, "parser": {
                    "gaps": source.parser.gaps, "crc_errors": source.parser.bad_crc,
                    "bad_headers": source.parser.bad_headers}}, indent=2))
        finally:
            source.close()
    elif arguments.command == "diagnose":
        from .diagnostics import diagnose
        print(json.dumps(diagnose(arguments.recording), indent=2))
    elif arguments.command == "analyze":
        config = Config.load(Path(arguments.recording) / "config.json")
        snapshot = Path(arguments.recording) / "spectral-background.npz"
        from .background import SpectralBackground
        background = SpectralBackground.from_path(snapshot, config) if snapshot.exists() else None
        processor = Processor(config, background=background)
        count = 0
        result = None
        for frame in replay(arguments.recording):
            result = processor.process(frame)
            count += 1
        print(json.dumps({"frames": count, "last_features": result.features if result else {},
            "last_detections": [asdict(item) for item in result.detections] if result else []}, indent=2))
    elif arguments.command == "calibrate":
        from .calibration import calibrate_channels
        config = Config.load(Path(arguments.recording) / "config.json")
        frames = []
        for frame in replay(arguments.recording):
            frames.append(frame)
            if len(frames) >= 100:
                break
        calibrated = calibrate_channels(frames, config, arguments.distance, arguments.azimuth, arguments.elevation)
        calibrated.save(arguments.output)
        print(f"Saved channel corrections to {arguments.output}; timing/geometry verification state unchanged")
    elif arguments.command == "benchmark":
        config = Config()
        processor = Processor(config)
        frames = [generate(config, index + 1, seed=index) for index in range(arguments.frames)]
        timings = []
        for frame in frames:
            start = time.perf_counter()
            processor.process(frame)
            timings.append((time.perf_counter() - start) * 1000)
        import numpy as np
        print(json.dumps({"frames": len(frames), "median_ms": float(np.median(timings)),
                          "p95_ms": float(np.percentile(timings, 95))}, indent=2))
    elif arguments.command == 'paired-audit':
        from .paired import write_report
        report = write_report(arguments.recordings,arguments.config,arguments.output)
        print(json.dumps(report['pairs'],indent=2))
    elif arguments.command == "audit":
        from .recording_audit import write_audit
        report = write_audit(arguments.recordings, arguments.output, arguments.profile)
        print(json.dumps({"frames": report["total_frames"], "adc_containers": report["total_adc_containers"],
            "nominal_waveform": report["nominal_waveform"], "plate_checks": report["plate_nominal_range_checks"]}, indent=2))
    elif arguments.command == "sweep":
        from .sweep import record_sweep
        report = record_sweep(arguments.output, Config.load(arguments.config), arguments.port,
                              arguments.distance, arguments.offset, arguments.seconds, handheld=arguments.handheld)
        print(json.dumps(report, indent=2))
    elif arguments.command == "sweep-analyze":
        from .sweep import analyze_sweep
        print(json.dumps(analyze_sweep(arguments.recording), indent=2))
    elif arguments.command == "research":
        from .research import evaluate
        report = evaluate(arguments.root, arguments.output, set(arguments.heldout_scenes))
        print(json.dumps({key: value for key, value in report.items() if key != "model"}, indent=2))
    return 0
