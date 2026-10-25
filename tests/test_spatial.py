import unittest
from dataclasses import replace
import numpy as np
from radar.config import Config
from radar.spatial import SpatialMapper


class SpatialTests(unittest.TestCase):
    def test_default_scene_view_retains_weaker_range_return(self):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from radar.spatial import draw_volume
        config=Config()
        spectrum=np.zeros((16,33,3),complex)
        spectrum[:,4]=100
        spectrum[:,12]=10  # A simultaneous return 20 dB below the strongest.
        volume=SpatialMapper(config).process(spectrum)
        figure=Figure();FigureCanvasAgg(figure)
        draw_volume(figure,volume)
        xyz=np.array(figure._radar_artists[-1]._offsets3d)
        radii=np.linalg.norm(xyz,axis=0)
        self.assertTrue(np.any(np.isclose(radii,config.ranges[4])))
        self.assertTrue(np.any(np.isclose(radii,config.ranges[12])))

    def test_cached_renderer_updates_cells_and_survives_range_resize(self):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from radar.spatial import SpatialRenderer
        mapper = SpatialMapper(Config())
        spectrum = np.zeros((16,33,3),complex)
        spectrum[:,5] = 1
        figure = Figure(figsize=(6,4))
        canvas = FigureCanvasAgg(figure)
        renderer = SpatialRenderer(canvas)
        renderer.update(mapper.process(spectrum), max_range_m=2)
        first_pixels = np.asarray(canvas.buffer_rgba()).copy()
        artists = figure._radar_artists
        spectrum[:,5] = 0
        spectrum[:,10] = 1
        renderer.update(mapper.process(spectrum), max_range_m=2)
        self.assertFalse(np.array_equal(first_pixels,np.asarray(canvas.buffer_rgba())))
        self.assertIs(artists[4],figure._radar_artists[4])
        self.assertEqual(len(figure.axes),5)
        figure.set_size_inches(7,5)
        canvas.draw()
        renderer.update(mapper.process(spectrum), dynamic_range_db=12, max_range_m=3)
        self.assertEqual(len(figure.axes),5)
        self.assertEqual(figure._radar_artists[4].get_clim(),(-12,0))

    def test_joint_angle_peak_and_multiple_ranges_survive(self):
        config = Config()
        mapper = SpatialMapper(config)
        spectrum = np.zeros((16,33,3), dtype=complex)
        for index, az, el in [(5,20,-10),(12,-30,15)]:
            direction = [np.sin(np.radians(az))*np.cos(np.radians(el)),np.sin(np.radians(el))]
            spectrum[:,index] = np.exp(2j*np.pi*config.array_geometry @ direction)
        volume = mapper.process(spectrum)
        for index, az, el in [(5,20,-10),(12,-30,15)]:
            e,a = np.unravel_index(volume.power[index-2].argmax(), volume.power.shape[1:])
            self.assertEqual(volume.azimuths[a], az)
            self.assertEqual(volume.elevations[e], el)
            self.assertGreater(volume.power[index-2].min(), 0)  # retains broad angular response

    def test_nonunitary_mixing_does_not_color_white_noise(self):
        matrix = np.array([[1,0,0],[0.2+0.1j,2,0],[0.1,0,0.5j]])
        config = replace(Config(), angle_matrix_real=matrix.real.tolist(),angle_matrix_imag=matrix.imag.tolist())
        mapper = SpatialMapper(config)
        # Exactly white sample covariance, not a stochastic approximation.
        spectrum = np.tile(np.eye(3)[:,None,:], (1,33,1)).astype(complex)
        volume = mapper.process(spectrum)
        np.testing.assert_allclose(volume.power, 1/3, atol=1e-12)

    def test_forward_response_inversion(self):
        matrix = np.array([[1,0,0],[0.1j,1,0],[0.1,0,1]])
        config = replace(Config(),angle_matrix_real=matrix.real.tolist(),angle_matrix_imag=matrix.imag.tolist())
        mapper = SpatialMapper(config)
        direction = [np.sin(np.radians(15))*np.cos(np.radians(10)),np.sin(np.radians(10))]
        raw = np.linalg.solve(matrix,np.exp(2j*np.pi*config.array_geometry @ direction))
        spectrum = np.zeros((16,33,3),complex)
        spectrum[:,8] = raw
        volume = mapper.process(spectrum)
        e,a = np.unravel_index(volume.power[6].argmax(), volume.power.shape[1:])
        self.assertEqual(volume.azimuths[a],15)
        self.assertEqual(volume.elevations[e],10)
