"""Matplotlib top-down display shared by live, replay and synthetic CFAR maps."""
import numpy as np


class MapPlot:
    def __init__(self, detector, interactive=True, scene_map=None, save_callback=None):
        self.platform = None
        if interactive:
            from .qt_platform import staged_platform_plugins
            self.platform = staged_platform_plugins()
            self.platform.__enter__()
        import matplotlib.pyplot as plt
        self.plt = plt
        self.interactive = interactive
        self.detector = detector
        self.scene_map = scene_map
        self.save_callback = save_callback
        if interactive:
            plt.ion()
        self.figure = plt.figure(figsize=(13, 8), layout='constrained', facecolor='#101827')
        grid = self.figure.add_gridspec(2, 2, height_ratios=[3, 1.25], width_ratios=[1, 1.15])
        self.profile = self.figure.add_subplot(grid[0, 0])
        self.plan = self.figure.add_subplot(grid[0, 1])
        self.readings = self.figure.add_subplot(grid[1, :])
        self.last = None
        initial = detector.invalid('waiting_for_frames')
        if scene_map is not None:
            initial['scene_map'] = scene_map.snapshot(now=scene_map.last_time)
            self.figure.get_layout_engine().set(rect=(0, .055, 1, .94))
            if interactive:
                from matplotlib.widgets import Button
                self.clear_button = Button(self.figure.add_axes([.72, .012, .12, .035]), 'Clear map',
                                           color='#cbd5e1', hovercolor='#f1f5f9')
                self.save_button = Button(self.figure.add_axes([.86, .012, .12, .035]), 'Save map',
                                          color='#cbd5e1', hovercolor='#f1f5f9')
                self.clear_button.on_clicked(self.clear_map)
                self.save_button.on_clicked(self.save_map)
        self.update(initial)
        if interactive:
            plt.show(block=False)

    def update(self, result):
        if result is None:
            if self.interactive:
                self.plt.pause(.01)
            return
        self.last = result
        for axis in (self.profile, self.plan, self.readings):
            axis.clear()
            axis.set_facecolor('#172235')
            axis.tick_params(colors='#cbd5e1', labelsize=9)
            for spine in axis.spines.values():
                spine.set_color('#475569')
            axis.xaxis.label.set_color('#cbd5e1')
            axis.yaxis.label.set_color('#cbd5e1')
            axis.title.set_color('#f1f5f9')
        meta = self.detector.metadata
        maximum = meta['max_range_m']
        scene = result.get('scene_map')
        state = scene['sensor_state'] if scene else result['state']
        self.figure.suptitle(
            f"{'Persistent object map' if scene else 'CFAR obstacle map'}  |  {state}  |  fixed radar\n"
            f"Assumed Z {self.detector.z:+.3f} m · ±{self.detector.limit_deg:g}° bearing · experimental positions",
            color='#f1f5f9', fontsize=13)
        self.profile.set(title='Range detection', xlabel='Slant range (m)', ylabel='Power (dB, ADC units)',
                         xlim=(meta['min_range_m'], maximum))
        if result['power_db']:
            ranges = self.detector.config.ranges
            self.profile.plot(ranges, result['power_db'], color='#60a5fa', label='Raw range power')
            threshold = [np.nan if v is None else v for v in result['threshold_db']]
            self.profile.plot(ranges, threshold, '--', color='#fbbf24', label='CA-CFAR threshold')
            for item in result['observations']:
                k = item['range_bin']
                self.profile.scatter(ranges[k], result['power_db'][k], color='#f8fafc', s=25)
            self.profile.legend(facecolor='#172235', labelcolor='#e2e8f0', fontsize=8)
        self.profile.grid(alpha=.15)
        extent = maximum*max(.55, np.sin(np.radians(self.detector.limit_deg))+.1)
        self.plan.set(title='Persistent object regions' if scene else 'Top-down reflector positions',
                      xlabel='Right X (m)', ylabel='Forward Y (m)',
                      xlim=(-extent, extent), ylim=(0, maximum))
        self.plan.set_aspect('equal', adjustable='box')
        self.plan.grid(alpha=.15)
        self.plan.scatter([0], [0], marker='^', color='#f8fafc', s=65)
        theta = np.radians(self.detector.limit_deg)
        for sign in (-1, 1):
            self.plan.plot([0, sign*maximum*np.sin(theta)], [0, maximum*np.cos(theta)],
                           '--', color='#64748b', linewidth=.8)
        if scene:
            self._draw_regions(scene)
        for item in result['observations']:
            if item['state'] == 'LOCALIZED':
                if not scene:
                    self.plan.scatter(item['x_m'], item['y_m'], color='#34d399', s=65, zorder=3)
                    self.plan.annotate(
                        f"#{item['track_id']}  {item['range_m']:.2f} m\n{item['azimuth_deg']:+.1f}°",
                        (item['x_m'], item['y_m']), xytext=(7, 5), textcoords='offset points',
                        color='#d1fae5', fontsize=9)
            elif item['confirmed']:
                # A range-only return is a band over the permitted bearings,
                # never a guessed straight-ahead point.
                angles = np.linspace(-theta, theta, 81)
                distance = item['range_m'] or item['provisional_range_m']
                radius = np.sqrt(max(distance**2-self.detector.z**2, 0))
                self.plan.plot(radius*np.sin(angles), radius*np.cos(angles), '--',
                               color='#fb923c', linewidth=2, alpha=.75)
        localized = sum(v['state'] == 'LOCALIZED' for v in result['observations'])
        unresolved = sum(v['state'] == 'UNRESOLVED' for v in result['observations'])
        confirmed_regions = sum(v['confirmed'] for v in scene['objects']) if scene else localized
        key = ('Green: current · amber: remembered · gray: stale\nCircles: return spread, not object outlines'
               if scene else 'Green: located · orange arc: range only')
        self.plan.text(.02, .98, f'{confirmed_regions} mapped · {unresolved} unresolved returns\n{key}',
                       transform=self.plan.transAxes, va='top', color='#cbd5e1', fontsize=8)
        self.readings.axis('off')
        rows = []
        if scene:
            objects = sorted(scene['objects'], key=lambda v: (v['state'] == 'STALE', -v['last_seen_s']))
            for item in objects[:8]:
                rows.append([str(item['object_id']), f"{item['range_m']:.3f}", f"{item['azimuth_deg']:+.2f}",
                    item['state'], str(item['observations']), f"{100*item['support_score']:.0f}%",
                    f"Last seen {item['age_s']:.1f} s ago · X {item['x_m']:+.2f}, Y {item['y_m']:.2f} m"])
            labels = ['Object', 'Range (m)', 'Bearing (°)', 'Map state', 'Hits', 'Support', 'Position / age']
        else:
            labels = ['ID', 'Range (m)', 'Bearing (°)', 'State', 'Hits', 'Coherence', 'Diagnostic']
            for item in result['observations']:
                distance, angle, coherence = item['range_m'], item['azimuth_deg'], item['coherence_rx2']
                rows.append([str(item['track_id']), f'{distance:.3f}' if distance is not None else 'unresolved',
                    f'{angle:+.2f}' if angle is not None else 'unresolved', item['state'],
                    f"{item['confirmation_hits']}/{meta['confirmation_frames']}",
                    f'{coherence:.3f}' if coherence is not None else '—', item['reason']])
        if rows:
            table = self.readings.table(cellText=rows,
                colLabels=labels,
                colWidths=[.04, .10, .10, .12, .06, .10, .48], loc='center', cellLoc='left')
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1, min(1.5, 7/(len(rows)+1)))
            for (row, _), cell in table.get_celld().items():
                cell.set_facecolor('#26354b' if row == 0 else '#172235')
                cell.set_edgecolor('#334155')
                cell.get_text().set_color('#f1f5f9')
        else:
            self.readings.text(.02, .65, result['reason'].replace('_', ' '), color='#cbd5e1', fontsize=12)
        footer = ('Radar must stay fixed. Support is not probability. Remembered objects are not current detections.'
                  if scene else 'One direction per range group. Same-range obstacles may merge. No return does not establish free space.')
        if scene and scene['capacity_reached']:
            footer = 'Map capacity reached: clear the map to admit new object regions.'
        if scene and len(scene['objects']) > 8:
            footer += f" Table shows 8/{len(scene['objects'])} regions; all are plotted and saved."
        self.readings.text(.02, -.12, footer,
                           color='#94a3b8', fontsize=9)
        self.figure.canvas.draw_idle()
        if self.interactive:
            self.plt.pause(.01)

    def _draw_regions(self, scene):
        from matplotlib.patches import Ellipse
        colors = dict(CURRENT='#34d399', REMEMBERED='#fbbf24', STALE='#94a3b8', TENTATIVE='#60a5fa')
        for item in scene['objects']:
            color = colors[item['state']]
            opacity = .35 if item['state'] == 'STALE' else .9
            width = max(.16, 4*item['spread_x_m'])
            height = max(.16, 4*item['spread_y_m'])
            self.plan.add_patch(Ellipse((item['x_m'], item['y_m']), width, height,
                                       facecolor=color, edgecolor=color, alpha=.15))
            self.plan.scatter(item['x_m'], item['y_m'], color=color, alpha=opacity, s=50, zorder=3)
            label = f"Object {item['object_id']} · {item['range_m']:.2f} m\n{item['azimuth_deg']:+.1f}°"
            if item['state'] != 'CURRENT':
                label += f" · {item['state'].lower()} {item['age_s']:.1f}s"
            self.plan.annotate(label, (item['x_m'], item['y_m']), xytext=(7, 5),
                               textcoords='offset points', color=color, fontsize=8, alpha=opacity)

    def clear_map(self, event=None):
        if self.scene_map is not None:
            self.scene_map.clear()
            self.save_map()

    def save_map(self, event=None):
        if self.save_callback:
            snapshot = self.save_callback()
            if self.last is not None:
                self.update(dict(self.last, scene_map=snapshot))

    def is_open(self):
        return self.plt.fignum_exists(self.figure.number)

    def save(self, path):
        self.figure.savefig(path, dpi=160, facecolor=self.figure.get_facecolor())

    def close(self):
        self.plt.close(self.figure)
        if self.platform:
            self.platform.__exit__(None, None, None)
            self.platform = None
