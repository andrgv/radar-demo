from dataclasses import asdict, replace
import json
from pathlib import Path
import numpy as np
from .config import Config
from .processing import range_fft
from .storage import replay


class SpectralBackground:
    def __init__(self, reference, config, frame_count, power_envelope=None):
        self.reference = np.asarray(reference, dtype=complex)
        self.config = config
        self.frame_count = frame_count
        self.power_envelope = (None if power_envelope is None else np.asarray(power_envelope, dtype=float))
        if self.power_envelope is not None and (self.power_envelope.shape != self.reference.shape
                or not np.isfinite(self.power_envelope).all() or np.any(self.power_envelope < 0)):
            raise ValueError("Invalid background power envelope")
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
        envelope = np.zeros_like(total.real)
        for frame in frames:
            if frame.profile_id != config.profile_id or frame.adc.shape != (config.chirps, config.samples, 3):
                raise ValueError("Background frame/configuration mismatch")
            if not frame.flags & 1:
                raise ValueError("Background must contain raw ADC frames")
            spectrum = range_fft(frame.adc, neutral)
            total += spectrum.mean(axis=0)
            envelope = np.maximum(envelope, np.mean(abs(spectrum)**2, axis=0))
            frame_count += 1
        if frame_count < 10:
            raise ValueError("Static background needs at least ten valid frames")
        return cls(total / frame_count, neutral, frame_count, envelope)

    def target_supported(self, spectrum, config):
        """Require >6 dB raw-power growth over the baseline maximum in 2 RX.

        This rejects phase-only subtraction residuals and shadowing. It is a
        conservative fixed-scene gate, not a calibrated false-alarm probability.
        Legacy snapshots lack variability data and cannot enable bin-1 detection.
        """
        supported = self.support_margin_db(spectrum, config) > 0
        if self.power_envelope is None:
            supported[1] = False
        return supported

    def support_margin_db(self, spectrum, config):
        """dB margin of the second strongest RX above the fixed support gate."""
        envelope = self.power_envelope
        if envelope is None:
            envelope = abs(self.reference)**2
        raw_power = np.mean(abs(spectrum)**2, axis=0)
        ratio = np.maximum(raw_power, 1e-30) / (np.maximum(envelope * abs(config.gains)**2, 1e-10) * 4)
        return np.sort(10 * np.log10(ratio), axis=1)[:, -2]

    def subtract(self, spectrum, config):
        return spectrum - self.reference[None, :, :] * config.gains[None, None, :]

    def save(self, path):
        extra = {} if self.power_envelope is None else {'power_envelope': self.power_envelope}
        np.savez_compressed(path, reference=self.reference, config=json.dumps(asdict(self.config)),
                            frame_count=self.frame_count, **extra)

    @classmethod
    def load(cls, path):
        with np.load(path, allow_pickle=False) as values:
            config = Config(**json.loads(str(values["config"]))).validate()
            return cls(values["reference"], config, int(values["frame_count"]),
                       values['power_envelope'] if 'power_envelope' in values else None)

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
