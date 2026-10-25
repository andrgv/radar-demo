"""Per-frame matched-filter reflectivity, not occupancy or reconstructed surfaces."""
from dataclasses import dataclass
import numpy as np


@dataclass
class SpatialVolume:
    ranges: np.ndarray
    azimuths: np.ndarray
    elevations: np.ndarray
    power: np.ndarray  # range, elevation, azimuth
    point_cloud: object = None


class SpatialMapper:
    def __init__(self, config, step_deg=5):
        if not 1 <= step_deg <= 30:
            raise ValueError('Angular grid step must be 1 to 30 degrees')
        self.ranges = config.ranges[2:-1]
        self.azimuths = np.arange(-60, 60.001, step_deg)
        self.elevations = np.arange(-60, 60.001, step_deg)
        az, el = np.meshgrid(np.radians(self.azimuths), np.radians(self.elevations))
        direction = np.array([np.sin(az) * np.cos(el), np.sin(el)]).reshape(2, -1)
        virtual = np.exp(2j * np.pi * config.array_geometry @ direction)
        # Predict RAW receive signatures. Normalizing in that domain avoids the
        # angle-dependent white-noise gain of non-unitary matrix correction.
        response = np.linalg.solve(config.angle_matrix, virtual)
        self.weights = response / np.linalg.norm(response, axis=0, keepdims=True)

    def process(self, spectrum):
        selected = spectrum[:, 2:-1]
        covariance = np.einsum('cra,crb->rab', selected, selected.conj()) / len(selected)
        power = np.einsum('ak,rab,bk->rk', self.weights.conj(), covariance,
                          self.weights, optimize=True).real
        shape = (len(self.ranges), len(self.elevations), len(self.azimuths))
        return SpatialVolume(self.ranges, self.azimuths, self.elevations,
                             np.maximum(power.reshape(shape), 0))


def draw_volume(figure, volume, dynamic_range_db=30, max_range_m=4.0):
    """Show projections and a display-limited subset of reflectivity cells."""
    point_cloud=volume.point_cloud
    keep = volume.ranges <= max_range_m
    if not np.any(keep):
        keep[0] = True
    volume = SpatialVolume(volume.ranges[keep], volume.azimuths, volume.elevations, volume.power[keep])
    cached = getattr(figure, '_radar_artists', None)
    if cached is None:
        az_axes = figure.add_subplot(221)
        el_axes = figure.add_subplot(222)
        cloud = figure.add_subplot(223, projection='3d')
        angular = figure.add_subplot(224)
    else:
        az_axes, el_axes, cloud, angular, image, el_image, angular_image, points = cached
    db = 10 * np.log10(np.maximum(volume.power, 1e-12))
    top = float(db.max())
    absolute_top=top
    db -= top  # Fixed color scale permits cached axes/ticks in the live view.
    top = 0.0
    limits = dict(vmin=top-dynamic_range_db, vmax=top, cmap='magma', aspect='auto', origin='lower')
    az_extent = [volume.azimuths[0], volume.azimuths[-1], volume.ranges[0], volume.ranges[-1]]
    el_extent = [volume.elevations[0], volume.elevations[-1], volume.ranges[0], volume.ranges[-1]]
    if cached is None:
        image = az_axes.imshow(db.max(axis=1), extent=az_extent, **limits)
        el_image = el_axes.imshow(db.max(axis=2), extent=el_extent, **limits)
    else:
        image.set_data(db.max(axis=1))
        el_image.set_data(db.max(axis=2))
        if list(image.get_extent()) != az_extent:
            image.set_extent(az_extent)
            el_image.set_extent(el_extent)
        image.set_clim(top-dynamic_range_db, top)
        el_image.set_clim(top-dynamic_range_db, top)
    az_axes.set(title='Max over elevation', xlabel='Azimuth (deg)', ylabel='Range (m)')
    el_axes.set(title='Max over azimuth', xlabel='Elevation (deg)', ylabel='Range (m)')
    r, e, a = np.nonzero(db >= top-dynamic_range_db)
    # Uniform deterministic sampling for rendering only, never a local-peak gate.
    stride = max(1, int(np.ceil(len(r)/2500)))
    r, e, a = r[::stride], e[::stride], a[::stride]
    az, el = np.radians(volume.azimuths[a]), np.radians(volume.elevations[e])
    radius = volume.ranges[r]
    xyz = (radius*np.sin(az)*np.cos(el), radius*np.cos(az)*np.cos(el), radius*np.sin(el))
    colors=db[r,e,a]
    if point_cloud is not None:
        visible=np.linalg.norm(point_cloud.xyz,axis=1)<=max_range_m
        xyz=tuple(point_cloud.xyz[visible].T)
        colors=point_cloud.power_db[visible]-absolute_top
    if cached is None:
        points = cloud.scatter(*xyz, c=colors, s=24 if point_cloud is not None else 5,
                               alpha=1 if point_cloud is not None else 0.3, cmap='magma',
                               depthshade=False, vmin=top-dynamic_range_db, vmax=top)
    else:
        points._offsets3d = xyz
        points.set_array(colors)
        points.set_clim(top-dynamic_range_db, top)
    maximum = max(1, float(volume.ranges[-1]))
    if cached is None or cloud.get_ylim()[1] != maximum:
        cloud.set(xlim=(-maximum,maximum), ylim=(0,maximum), zlim=(-maximum,maximum),
                  xlabel='Right (m)', ylabel='Forward (m)', zlabel='Up (m)', title='Reflectivity cells; NOT surface points')
    if point_cloud is not None:
        cloud.set_title(f'Scattering centers: {len(colors)} points; angles unvalidated')
    peak_range = int(np.argmax(volume.power.max(axis=(1,2))))
    if cached is None:
        angular_image = angular.imshow(db[peak_range], extent=[volume.azimuths[0],volume.azimuths[-1],volume.elevations[0],volume.elevations[-1]], **limits)
    else:
        angular_image.set_data(db[peak_range])
        angular_image.set_clim(top-dynamic_range_db, top)
    angular.set(title=f'Angular spread at {volume.ranges[peak_range]:.2f} m', xlabel='Azimuth (deg)', ylabel='Elevation (deg)')
    if cached is None:
        figure.colorbar(image, ax=[az_axes,el_axes,angular], label='Power relative to strongest visible cell (dB)', shrink=0.6)
        figure.suptitle('Radar reflectivity — broad lobes are ambiguity, not occupied surfaces')
        figure._radar_artists = (az_axes,el_axes,cloud,angular,image,el_image,angular_image,points)


class SpatialRenderer:
    """Cache static axes; repaint only images, title and projected markers."""
    def __init__(self, canvas):
        self.canvas = canvas
        self.background = None
        self.signature = None
        self.artists = ()
        canvas.mpl_connect('draw_event', self._on_draw)

    def _paint(self):
        self.canvas.restore_region(self.background)
        for artist in self.artists:
            if hasattr(artist, 'do_3d_projection'):
                artist.do_3d_projection()
            artist.axes.draw_artist(artist)
        self.canvas.blit(self.canvas.figure.bbox)

    def _on_draw(self, event):
        if self.artists:
            self.background = self.canvas.copy_from_bbox(self.canvas.figure.bbox)
            self._paint()

    def update(self, volume, dynamic_range_db=30, max_range_m=4):
        figure = self.canvas.figure
        draw_volume(figure, volume, dynamic_range_db, max_range_m)
        cached = figure._radar_artists
        self.artists = (*cached[4:], cached[3].title,cached[2].title)
        for artist in self.artists:
            artist.set_animated(True)
        signature = (dynamic_range_db, max_range_m)
        if self.background is None or signature != self.signature:
            self.canvas.draw()
            figure.set_layout_engine('none')
            self.signature = signature
        else:
            self._paint()


def main():
    import argparse
    from pathlib import Path
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from .config import Config
    from .processing import range_fft
    from .storage import replay
    parser = argparse.ArgumentParser()
    parser.add_argument('recording')
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    config = Config.load(args.config)
    mapper = SpatialMapper(config)
    total = None
    count = 0
    for frame in replay(args.recording):
        volume = mapper.process(range_fft(frame.adc, config))
        total = volume.power.copy() if total is None else total + volume.power
        count += 1
    if not count:
        raise ValueError('No frames')
    volume.power = total/count
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output.with_suffix('.npz'), ranges=volume.ranges,
                        azimuths=volume.azimuths, elevations=volume.elevations, power=volume.power,
                        frames=count, config_json=__import__('json').dumps(__import__('dataclasses').asdict(config)))
    figure = Figure(figsize=(13,10), layout='constrained')
    FigureCanvasAgg(figure)
    draw_volume(figure, volume)
    figure.savefig(output.with_suffix('.png'), dpi=120)
    print(f'{count} frames; saved mean POWER volume and diagnostic plot to {output}')


if __name__ == '__main__':
    main()
