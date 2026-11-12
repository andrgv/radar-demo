"""Empirical 2D CA-CFAR on full linear-power range–Doppler maps.

Range DC/Nyquist are excluded from both tests and training. Range never wraps.
The Doppler FFT is periodic; wrapping or truncation is an explicit setting.
Connected cells are candidate groups, not associated objects or calibrated speed.
"""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Cfar2DConfig:
    guard_range: int = 1
    guard_doppler: int = 1
    training_range: int = 3
    training_doppler: int = 2
    min_training: int = 16
    factor: float = 4.0
    doppler_edge: str = 'wrap'

    def __post_init__(self):
        for key in ('guard_range', 'guard_doppler', 'training_range', 'training_doppler', 'min_training'):
            if type(getattr(self, key)) is not int:
                raise ValueError('CFAR counts must be integers')
        if min(self.guard_range, self.guard_doppler) < 0 or min(self.training_range, self.training_doppler, self.min_training) < 1:
            raise ValueError('CFAR needs nonnegative guards and positive training widths/count')
        if not np.isfinite(self.factor) or self.factor <= 1:
            raise ValueError('CFAR factor must be finite and greater than one')
        if self.doppler_edge not in ('wrap', 'truncate'):
            raise ValueError('Doppler edge policy must be wrap or truncate')


class CaCfar2D:
    def __init__(self, shape, settings=None):
        self.settings = settings or Cfar2DConfig()
        if len(shape) != 2 or any(type(n) is not int or n < 3 for n in shape):
            raise ValueError('CFAR requires a two-dimensional grid of at least 3 × 3')
        self.shape = shape
        nd, nr = shape
        c = self.settings
        od, ore = c.guard_doppler+c.training_doppler, c.guard_range+c.training_range
        if c.doppler_edge == 'wrap' and 2*od+1 > nd:
            raise ValueError('Wrapped Doppler window must not reuse a Doppler row')
        if od >= nd or ore >= nr:
            raise ValueError('CFAR window is larger than the map')
        # Precompute each unique reference cell. Padding is masked in detect().
        refs = [[] for _ in range(nd*nr)]
        for d in range(nd):
            for r in range(1, nr-1):
                for dd in range(-od, od+1):
                    sd = d+dd
                    if c.doppler_edge == 'wrap':
                        sd %= nd
                    elif not 0 <= sd < nd:
                        continue
                    for dr in range(-ore, ore+1):
                        sr = r+dr
                        if not 1 <= sr < nr-1:
                            continue
                        if abs(dd) <= c.guard_doppler and abs(dr) <= c.guard_range:
                            continue
                        refs[d*nr+r].append(sd*nr+sr)
        self.counts = np.array([len(x) for x in refs], dtype=int).reshape(shape)
        width = int(self.counts.max())
        self.indices = np.zeros((nd*nr, width), dtype=int)
        self.reference_mask = np.zeros_like(self.indices, dtype=bool)
        for i, cells in enumerate(refs):
            self.indices[i, :len(cells)] = cells
            self.reference_mask[i, :len(cells)] = True
        self.testable = self.counts >= c.min_training
        self.testable[:, (0, nr-1)] = False
        if not self.testable.any():
            raise ValueError('No cells have enough CFAR training references')

    def detect(self, power):
        p = np.asarray(power, dtype=float)
        if p.shape != self.shape or not np.isfinite(p).all() or np.any(p < 0):
            raise ValueError('CFAR expects a finite nonnegative map with the configured shape')
        sums = np.sum(np.where(self.reference_mask, p.ravel()[self.indices], 0), axis=1).reshape(self.shape)
        noise = np.full(self.shape, np.nan)
        noise[self.testable] = np.maximum(sums[self.testable]/self.counts[self.testable], 1e-12)
        threshold = noise*self.settings.factor
        accepted = self.testable & (p > threshold)
        return noise, threshold, accepted, cluster_cells(p, accepted, self.settings.doppler_edge)


def cluster_cells(power, accepted, doppler_edge='wrap'):
    """Eight-connected components; keep local maxima inside merged components.

An accepted ridge may connect static and moving returns. Exporting its local
maxima preserves that ambiguity instead of reporting one object per component.
Plateaus of neighboring equal maxima produce one deterministic representative.
"""
    p = np.asarray(power, dtype=float)
    mask = np.asarray(accepted, dtype=bool)
    if p.ndim != 2 or mask.shape != p.shape or doppler_edge not in ('wrap', 'truncate'):
        raise ValueError('Invalid candidate clustering map or edge policy')
    nd, nr = p.shape
    frequencies = np.fft.fftshift(np.fft.fftfreq(nd))

    def neighbors(cell):
        d, r = cell
        for dd in (-1, 0, 1):
            sd = d+dd
            if doppler_edge == 'wrap':
                sd %= nd
            elif not 0 <= sd < nd:
                continue
            for dr in (-1, 0, 1):
                sr = r+dr
                if (dd or dr) and 1 <= sr < nr-1:
                    yield sd, sr

    def components(cells):
        remaining = {tuple(int(value) for value in cell) for cell in cells}
        while remaining:
            seed = min(remaining)
            remaining.remove(seed)
            group, queue = [seed], [seed]
            while queue:
                for cell in neighbors(queue.pop()):
                    if cell in remaining:
                        remaining.remove(cell)
                        group.append(cell)
                        queue.append(cell)
            yield sorted(group)

    def peak_dict(cell):
        d, r = cell
        return dict(doppler_bin=int(d), range_bin=int(r),
                    cycles_per_saved_block=float(frequencies[d]),
                    power=float(p[cell]))

    clusters = []
    for cells in components(map(tuple, np.argwhere(mask))):
        cell_set = set(cells)
        maxima = [cell for cell in cells if all(p[cell] >= p[other] for other in neighbors(cell))]
        plateau_peaks = [min(group) for group in components(maxima)]
        peak = min(cells, key=lambda cell: (-p[cell], cell))
        clusters.append(dict(cluster_id=len(clusters), cell_count=len(cells),
            cells=[list(cell) for cell in cells], range_bins=sorted({r for _, r in cells}),
            doppler_bins=sorted({d for d, _ in cells}),
            touches_zero_doppler=any(d == nd//2 for d, _ in cells),
            crosses_doppler_seam=doppler_edge == 'wrap' and any(
                (nd-1, r+dr) in cell_set for d, r in cells if d == 0 for dr in (-1, 0, 1)),
            peak=peak_dict(peak), local_maxima=[peak_dict(cell) for cell in plateau_peaks]))
    return clusters
