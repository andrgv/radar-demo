from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import numpy as np

C = 299792458.0
PROFILE_ID = 0x33525801


@dataclass
class Config:
    profile_id: int = PROFILE_ID
    samples: int = 64
    chirps: int = 17
    sample_rate_hz: float = 1e6
    slope_hz_s: float = 3e13
    carrier_hz: float = 60e9
    chirp_interval_s: float = 0.001
    frame_interval_s: float = 0.1
    geometry_wavelengths: list = field(default_factory=lambda: [[0, 0], [0.5, 0], [0, 0.5]])
    geometry_mm: list | None = None
    geometry_label: str = "generic array; hardware orientation unverified"
    mount_roll_deg: float = 0.0
    gains_real: list = field(default_factory=lambda: [1, 1, 1])
    gains_imag: list = field(default_factory=lambda: [0, 0, 0])
    range_offset_m: float = 0.0
    range_scale: float = 1.0
    verified: bool = False
    calibration_id: str = "uncalibrated"
    discard_chirps: int = 1
    snr_db: float = 12.0
    angle_matrix_real: list | None = None
    angle_matrix_imag: list | None = None
    probe_search_bins: int = 0
    chirp_timing_verified: bool = False
    carrier_frequency_verified: bool = False

    @property
    def velocity_scale_verified(self):
        return self.chirp_timing_verified and self.carrier_frequency_verified

    def validate(self):
        if type(self.chirp_timing_verified) is not bool or type(self.carrier_frequency_verified) is not bool:
            raise ValueError('Timing and carrier verification flags must be booleans')
        if type(self.probe_search_bins) is not int or not 0 <= self.probe_search_bins <= 3:
            raise ValueError("Probe search radius must be an integer from 0 to 3 bins")
        for value in (self.sample_rate_hz, self.slope_hz_s, self.carrier_hz,
                      self.chirp_interval_s, self.frame_interval_s):
            if not np.isfinite(value) or value <= 0:
                raise ValueError("Timing and RF parameters must be finite and positive")
        if self.samples < 16 or self.chirps < 8 or not 0 <= self.discard_chirps < self.chirps - 4:
            raise ValueError("Invalid acquisition dimensions")
        source_geometry = self.geometry_wavelengths if self.geometry_mm is None else self.geometry_mm
        geometry = np.asarray(source_geometry, dtype=float)
        if geometry.shape != (3, 2) or not np.isfinite(geometry).all():
            raise ValueError("Supply three RX coordinates in geometry_mm or geometry_wavelengths")
        if not np.isfinite(self.mount_roll_deg):
            raise ValueError("Mounting rotation must be finite")
        if np.linalg.matrix_rank(geometry[1:] - geometry[0]) != 2:
            raise ValueError("Azimuth/elevation require two independent baselines")
        gains = self.gains
        if (self.angle_matrix_real is None) != (self.angle_matrix_imag is None):
            raise ValueError("Angle matrix requires real and imaginary parts")
        if self.angle_matrix_real is not None:
            matrix = self.angle_matrix
            if matrix.shape != (3, 3) or not np.isfinite(matrix).all() or np.linalg.matrix_rank(matrix) != 3:
                raise ValueError("Angle matrix must be a finite full-rank 3x3 matrix")
        if gains.shape != (3,) or not np.isfinite(gains).all() or np.any(abs(gains) < 1e-8):
            raise ValueError("Invalid channel calibration")
        if (not np.isfinite(self.range_offset_m) or not np.isfinite(self.snr_db)
                or not np.isfinite(self.range_scale) or self.range_scale <= 0):
            raise ValueError("Invalid processing configuration")
        return self

    @property
    def angle_matrix(self):
        if self.angle_matrix_real is None:
            return np.eye(3, dtype=complex)
        return np.asarray(self.angle_matrix_real) + 1j * np.asarray(self.angle_matrix_imag)

    @property
    def array_geometry(self):
        geometry = np.asarray(self.geometry_wavelengths, dtype=float) if self.geometry_mm is None else (
            np.asarray(self.geometry_mm, dtype=float) * 1e-3 * self.carrier_hz / C)
        roll = np.radians(self.mount_roll_deg)
        rotation = np.array([[np.cos(roll), -np.sin(roll)], [np.sin(roll), np.cos(roll)]])
        return geometry @ rotation.T

    @property
    def gains(self):
        return np.asarray(self.gains_real) + 1j * np.asarray(self.gains_imag)

    @property
    def ranges(self):
        return (np.fft.rfftfreq(self.samples, 1 / self.sample_rate_hz) * C
                / (2 * self.slope_hz_s) * self.range_scale + self.range_offset_m)

    def save(self, path):
        Path(path).write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path):
        return cls(**json.loads(Path(path).read_text(encoding="utf-8"))).validate()
