from dataclasses import asdict, replace
import json
from pathlib import Path
import numpy as np
from .config import Config
from .processing import range_fft
from .storage import replay


class SpectralBackground:
    def __init__(self, reference, config, frame_count):
        self.reference = np.asarray(reference, dtype=complex)
        self.config = config
        self.frame_count = frame_count
        if self.reference.shape != (config.samples // 2 + 1, 3) or not np.isfinite(self.reference).all():
            raise ValueError("Invalid static background spectrum")

    def validate(self, config):
        fields = ("profile_id", "samples", "chirps", "discard_chirps", "sample_rate_hz",
                  "slope_hz_s", "carrier_hz", "chirp_interval_s")
        if any(getattr(self.config, field) != getattr(config, field) for field in fields):
            raise ValueError("Background acquisition parameters do not match the current configuration")

    @classmethod
    def fit(cls, frames, config):
        neutral = replace(config, gains_real=[1, 1, 1], gains_imag=[0, 0, 0])
        total = np.zeros((config.samples // 2 + 1, 3), dtype=complex)
        frame_count = 0
        for frame in frames:
            if frame.profile_id != config.profile_id or frame.adc.shape != (config.chirps, config.samples, 3):
                raise ValueError("Background frame/configuration mismatch")
            if not frame.flags & 1:
                raise ValueError("Background must contain raw ADC frames")
            total += range_fft(frame.adc, neutral).mean(axis=0)
            frame_count += 1
        if frame_count < 10:
            raise ValueError("Static background needs at least ten valid frames")
        return cls(total / frame_count, neutral, frame_count)

    def subtract(self, spectrum, config):
        return spectrum - self.reference[None, :, :] * config.gains[None, None, :]

    def save(self, path):
        np.savez_compressed(path, reference=self.reference, config=json.dumps(asdict(self.config)),
                            frame_count=self.frame_count)

    @classmethod
    def load(cls, path):
        with np.load(path, allow_pickle=False) as values:
            config = Config(**json.loads(str(values["config"]))).validate()
            return cls(values["reference"], config, int(values["frame_count"]))

    @classmethod
    def from_path(cls, path, config):
        path = Path(path)
        if path.suffix == ".npz":
            background = cls.load(path)
        else:
            source_config = Config.load(path / "config.json")
            background = cls.fit(replay(path), source_config)
        background.validate(config)
        return background
