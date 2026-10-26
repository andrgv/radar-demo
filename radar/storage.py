from dataclasses import asdict
import json
from pathlib import Path
import time
from .protocol import Parser, encode


class Recorder:
    def __init__(self, path, config, metadata=None):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=False)
        config.save(self.path / "config.json")
        self.raw = (self.path / "frames.grd").open("wb")
        self.timestamps = (self.path / "arrivals.jsonl").open("w", encoding="utf-8")
        self.features = (self.path / "features.jsonl").open("w", encoding="utf-8")
        self.count = 0
        self.wire = None
        self.transport = None
        self.clouds = None
        self.tracking = None
        self.metadata = {"schema": 1, "created_unix_s": time.time(), "label": "unknown",
                         "session_id": self.path.name, "scene_id": "unspecified", **(metadata or {})}
        (self.path / "metadata.json").write_text(json.dumps(self.metadata, indent=2), encoding="utf-8")

    def write(self, frame, result=None):
        self.raw.write(encode(frame))
        self.timestamps.write(json.dumps({"sequence": frame.sequence, "host_unix_ns": time.time_ns(),
            "capture_elapsed_us":frame.capture_elapsed_us}) + "\n")
        if result is not None:
            if self.tracking is None:
                self.tracking = (self.path / 'tracking.jsonl').open('w', encoding='utf-8')
            self.tracking.write(json.dumps(dict(schema=1, sequence=frame.sequence,
                timestamp_us=frame.timestamp_us, tracks=[asdict(item) for item in result.tracks],
                detection_diagnostics=result.detection_diagnostics), allow_nan=False) + '\n')
            self.features.write(json.dumps({"sequence": frame.sequence, **result.features,
                "calibrated": result.calibrated, "label": self.metadata["label"]}, allow_nan=False) + "\n")
            volume=getattr(result,'spatial_volume',None)
            cloud=getattr(volume,'point_cloud',None)
            if cloud is not None:
                if self.clouds is None:
                    self.clouds=(self.path/'pointcloud.jsonl').open('w',encoding='utf-8')
                self.clouds.write(json.dumps(dict(schema=1,frame_id='radar',sequence=frame.sequence,
                    timestamp_us=frame.timestamp_us,angular_calibration_verified=self.metadata.get('angular_calibration_verified',False),
                    **{key:value.tolist() for key,value in asdict(cloud).items()}),allow_nan=False)+'\n')
        self.count += 1
        if self.count % 10 == 0:
            self.raw.flush()
            self.timestamps.flush()
            self.features.flush()
            if self.clouds is not None:
                self.clouds.flush()
            if self.tracking is not None:
                self.tracking.flush()

    def write_transport(self, data, parser):
        """Preserve original serial chunks, including rejected packets, for audit."""
        if self.wire is None:
            self.wire = (self.path/'serial-wire.bin').open('wb')
            self.transport = (self.path/'transport.jsonl').open('w',encoding='utf-8')
        self.wire.write(data)
        self.transport.write(json.dumps(dict(host_unix_ns=time.time_ns(),wire_end=self.wire.tell(),
            bytes=len(data),gaps=parser.gaps,bad_crc=parser.bad_crc,bad_headers=parser.bad_headers,
            restarts=parser.restarts,discarded_bytes=parser.discarded_bytes))+'\n')

    def close(self):
        if self.tracking is not None:
            self.tracking.close()
        if self.clouds is not None:
            self.clouds.close()
        if self.wire is not None:
            self.wire.close()
            self.transport.close()
        self.raw.close()
        self.timestamps.close()
        self.features.close()

    def __enter__(self):
        return self

    def __exit__(self, *arguments):
        self.close()


def replay(path, parser=None):
    path = Path(path)
    parser = parser or Parser()
    with (path / "frames.grd" if path.is_dir() else path).open("rb") as source:
        while chunk := source.read(65536):
            yield from parser.feed(chunk)


def export_detections(result):
    return {"schema": 1, "frame_id": "radar", "sequence": result.sequence,
            "device_timestamp_us": result.timestamp_us, "calibrated": result.calibrated,
            "detections": [asdict(item) for item in result.detections]}
