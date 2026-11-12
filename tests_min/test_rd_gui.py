import argparse
import contextlib
from copy import deepcopy
from dataclasses import replace
import io
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import numpy as np
from PyQt6 import QtWidgets

from radar.qt_platform import staged_platform_plugins
from radar.storage import Recorder
from radar_min.__main__ import main,range_doppler_options
from radar_min.rd_gui import Window
from tests_min.test_range_doppler import C,tone


def arguments(config,replay=None):
    parser=argparse.ArgumentParser();range_doppler_options(parser,mode=False)
    args=parser.parse_args([])
    args.config=str(config);args.replay=str(replay)if replay else None
    args.port='must-not-open';args.snapshot=None;args.snapshot_frame=0;args.view_range_bins=8
    return args


class RDGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugins=staged_platform_plugins();cls.plugins.__enter__()
        cls.app=QtWidgets.QApplication.instance()or QtWidgets.QApplication([])

    @classmethod
    def tearDownClass(cls):cls.plugins.__exit__(None,None,None)

    def test_joint_comparison_selection_and_stale_clear(self):
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'config.json';C.save(config)
            window=Window(arguments(config))
            try:
                for seq in (1,2,3):reading=window.processor.update(tone([(2.2,0,2000)],seq))
                window.latest=(time.monotonic(),reading,window.processor.snapshot)
                window.tick()
                self.assertIn('cm',window.primary_label.text())
                self.assertGreater(window.candidate_table.rowCount(),0)
                self.assertIn('RX 1:',window.rx_label.text())
                self.assertEqual(sum(len(line.get_xdata())for line in window.rx_peak_lines),3)
                window.candidate_table.selectRow(0);self.app.processEvents()
                self.assertIn('Inspecting',window.inspection_label.text())
                self.assertIn('Selected confirmed 1D group',window.rx_label.text())
                self.assertTrue(window.slice_axis.lines)
                window.render(reading,window.processor.snapshot,False)
                self.assertEqual(window.primary_label.text(),'1D baseline distance: —')
                self.assertEqual(window.candidate_table.rowCount(),0)
                self.assertIn('No fresh',window.inspection_label.text())
                self.assertTrue(all(len(line.get_xdata())==0 for line in window.slice_lines))
                self.assertTrue(all(len(line.get_xdata())==0 for line in window.rx_peak_lines))
                self.assertIn('no fresh',window.rx_label.text())
            finally:window.close()

    def test_redraw_cap_never_delays_rejection_or_stale_clearing(self):
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'config.json';C.save(config)
            window=Window(arguments(config));window.timer.stop()
            try:
                for seq in (1,2,3):reading=window.processor.update(tone([(2.2,0,2000)],seq))
                with patch('radar_min.rd_gui.time.monotonic',return_value=10) as clock,patch.object(window,'render',wraps=window.render) as render:
                    window.latest=(10,reading,window.processor.snapshot);window.tick()
                    self.assertEqual(render.call_count,1)
                    reading=window.processor.update(tone([(2.2,0,2000)],4))
                    clock.return_value=10.05
                    window.latest=(10.05,reading,window.processor.snapshot);window.tick()
                    self.assertEqual(render.call_count,1)
                    rejected=window.processor.reject_frame(tone([(2.2,0,2000)],5),'clock_fit_unstable')
                    clock.return_value=10.06
                    window.latest=(10.06,rejected,None);window.tick()
                    self.assertEqual(render.call_count,2)
                    self.assertEqual(window.candidate_table.rowCount(),0)
                    self.assertIn('Stop and start',window.quality.text())
                    clock.return_value=11.1;window.tick()
                    self.assertEqual(render.call_count,3)
                    self.assertIn('No fresh',window.quality.text())
            finally:window.close()

    def test_only_active_canvas_redraws(self):
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'config.json';C.save(config)
            window=Window(arguments(config));window.timer.stop()
            try:
                for seq in (1,2,3):reading=window.processor.update(tone([(2.2,0,2000)],seq))
                window.latest=(time.monotonic(),reading,window.processor.snapshot)
                with patch.object(window.comparison_canvas,'draw_idle') as comparison,patch.object(window.canvas,'draw_idle') as maps:
                    window.render(reading,window.processor.snapshot,True)
                    self.assertEqual(comparison.call_count,1);self.assertEqual(maps.call_count,0)
                    window.tabs.setCurrentIndex(1)
                    self.assertEqual(comparison.call_count,1);self.assertEqual(maps.call_count,1)
            finally:window.close()

    def test_os_comparison_is_explicit_and_clears_on_fault(self):
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'config.json';C.save(config)
            args=arguments(config);args.experimental_os=True
            window=Window(args);window.timer.stop()
            try:
                for seq in (1,2,3):reading=window.processor.update(tone([(2.2,0,2000)],seq))
                window.render(reading,window.processor.snapshot,True)
                self.assertIn('Experimental OS inspection',window.os_label.text())
                self.assertEqual(len(window.os_threshold_line.get_xdata()),33)
                primary=reading['results']['primary']
                self.assertEqual(primary['source'],'frozen 1D baseline')
                rejected=window.processor.reject_frame(tone([(2.2,0,2000)],4),'clock_fit_unstable')
                window.render(rejected,None,False)
                self.assertIn('No current comparison',window.os_label.text())
                self.assertEqual(len(window.os_threshold_line.get_xdata()),0)
            finally:window.close()

    def test_weak_candidate_inspection_is_optional_and_never_replaces_primary(self):
        with tempfile.TemporaryDirectory()as folder:
            config=Path(folder)/'config.json';C.save(config)
            args=arguments(config);args.experimental_weak=True
            window=Window(args);window.timer.stop()
            try:
                for seq in(1,2,3,4,5):reading=window.processor.update(tone([(2.2,0,2000)],seq))
                window.render(reading,window.processor.snapshot,True)
                self.assertIn('Weak scene candidate (inspection only)',window.weak_label.text())
                self.assertIn('Not a verified object distance',window.weak_label.text())
                self.assertIn('motion link: unseeded',window.weak_label.text())
                self.assertIn('Confirmed weak scene feature (inspection)',window.weak_feature_label.text())
                self.assertIn('1D baseline distance:',window.primary_label.text())
                self.assertEqual(reading['results']['primary']['source'],'frozen 1D baseline')
                self.assertIsNotNone(window.os_threshold_line)
                rejected=window.processor.reject_frame(tone([(2.2,0,2000)],6),'serial_backlog')
                window.render(rejected,None,False)
                self.assertIn('No fresh current comparison',window.weak_label.text())
                self.assertNotIn('passed original fit checks',window.weak_label.text())
                self.assertNotIn('motion link: unseeded',window.weak_label.text())
                self.assertIn('no fresh',window.weak_feature_label.text())
            finally:window.close()

    def test_weak_feature_history_breaks_between_ids_and_cannot_reuse_mismatched_measurements(self):
        with tempfile.TemporaryDirectory()as folder:
            config=Path(folder)/'config.json';C.save(config)
            args=arguments(config);args.experimental_weak=True
            window=Window(args);window.timer.stop()
            try:
                for seq in(1,2,3,4,5):reading=window.processor.update(tone([(2.2,0,2000)],seq))
                window.remember_entry((1,np.nan,dict(__weak_feature__=80.,__weak_feature_id__='weak:1')))
                window.remember_entry((2,np.nan,dict(__weak_feature__=81.,__weak_feature_id__='weak:1')))
                window.remember_entry((3,np.nan,dict(__weak_feature__=120.,__weak_feature_id__='weak:2')))
                window.draw_comparison(reading,window.processor.snapshot,True)
                y=window.weak_feature_history_line.get_ydata()
                self.assertTrue(np.isnan(y[2]));self.assertEqual(y[-1],120.)
                reading['weak_feature_result']['measurement_sequence']=4
                self.assertNotIn('__weak_feature__',window.history_entry(reading,True)[2])
                reading['weak_feature_result']['frame_sequence']=0
                window.render_results(reading,window.processor.snapshot,True)
                self.assertIn('no fresh',window.weak_feature_label.text())
            finally:window.close()

    def test_motion_readout_and_per_frame_history_survive_skipped_redraws(self):
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'config.json';C.save(config)
            args=arguments(config);args.motion_aware=True
            window=Window(args);window.timer.stop()
            try:
                for seq in range(1,7):
                    reading=window.processor.update(tone([(6,-1/16,2000)],seq))
                    window.pending_history.append(window.history_entry(reading,True))
                window.latest=(time.monotonic(),reading,window.processor.snapshot);window.tick()
                self.assertIn('Experimental motion-aware distance:',window.primary_label.text())
                self.assertNotEqual(window.primary_label.text(),'Experimental motion-aware distance: —')
                self.assertIn('1D baseline distance: —',window.baseline_label.text())
                self.assertEqual([h[0] for h in window.result_history],[1,2,3,4,5,6])
                self.assertEqual(reading['motion_result']['source'],'RD motion')
                stopped=window.processor.update(tone([(6,0,2000)],7))
                self.assertEqual(stopped['motion_result']['source'],'RD stopped')
                rejected=window.processor.reject_frame(tone([(6,0,2000)],8),'serial_backlog')
                window.render(rejected,None,False)
                self.assertEqual(window.primary_label.text(),'Experimental motion-aware distance: —')
            finally:window.close()

    def test_replay_snapshot_table_zoom_stale_and_mismatched_view_clear(self):
        with tempfile.TemporaryDirectory()as folder:
            config=Path(folder)/'config.json';C.save(config)
            recording=Path(folder)/'recording'
            with Recorder(recording,C)as recorder:
                for seq in range(1,6):recorder.write(tone([(6,0,2000),(13,-.25,1000)],seq))
            with patch('radar_min.rd_gui.stream',side_effect=AssertionError('Replay must not open serial')):
                window=Window(arguments(config,recording))
                try:
                    window.replay_snapshot(3);self.app.processEvents();window.tick()
                    self.assertGreaterEqual(window.table.rowCount(),2)
                    self.assertGreaterEqual(len(window.track_points.get_offsets()),2)
                    self.assertTrue(any(window.table.item(i,2).text().startswith('~')for i in range(window.table.rowCount())))
                    self.assertTrue(any(window.table.item(i,3).text()=='13'for i in range(window.table.rowCount())))
                    window.view_bins.setValue(5)
                    self.assertTrue(any(window.table.item(i,3).text()=='13'for i in range(window.table.rowCount())))
                    self.assertFalse(window.root.exists())
                    stamp,reading,view=window.latest
                    window.latest=(time.monotonic(),reading,replace(view,sequence=0));window.tick()
                    self.assertEqual(window.table.rowCount(),0)
                    self.assertEqual(len(window.track_points.get_offsets()),0)
                    self.assertTrue(np.ma.getmaskarray(window.full_image.get_array()).all())
                    window.latest=(time.monotonic()-2,reading,view);window.tick()
                    self.assertEqual(window.table.rowCount(),0)
                    self.assertIn('No fresh frame',window.quality.text())
                    window.latest=(time.monotonic(),reading,view);window.tick();window.stop_run()
                    self.assertEqual(window.table.rowCount(),0)
                    self.assertEqual(len(window.track_points.get_offsets()),0)
                finally:window.close()

    def test_ambiguous_or_missing_state_never_displays_an_old_point(self):
        with tempfile.TemporaryDirectory()as folder:
            config=Path(folder)/'config.json';C.save(config)
            window=Window(arguments(config))
            try:
                for seq in (1,2,3):reading=window.processor.update(tone([(6,0,2000)],seq))
                view=window.processor.snapshot;reading=deepcopy(reading)
                for t in reading['association']['tracks']:
                    t['state']='ambiguous';t['current_support_cells']=[[8,6],[8,7]]
                window.render(reading,view,True)
                self.assertGreater(window.table.rowCount(),0)
                self.assertTrue(all(window.table.item(i,2).text()=='—'for i in range(window.table.rowCount())))
                self.assertEqual(len(window.track_points.get_offsets()),0)
                self.assertEqual(len(window.support_points.get_offsets()),2)
                for t in reading['association']['tracks']:t['state']='missed';t['current_support_cells']=[]
                window.render(reading,view,True)
                self.assertEqual(len(window.support_points.get_offsets()),0)
                self.assertTrue(all(window.table.item(i,2).text()=='—'for i in range(window.table.rowCount())))
                rejected=window.processor.reject_frame(tone([(6,0,2000)],4),'clock_fit_unstable')
                window.render(rejected,None,True)
                self.assertEqual(window.table.rowCount(),0)
                self.assertTrue(np.ma.getmaskarray(window.margin_image.get_array()).all())
            finally:window.close()

    def test_replay_worker_stops_clears_and_never_records_or_opens_serial(self):
        with tempfile.TemporaryDirectory()as folder:
            config=Path(folder)/'config.json';C.save(config)
            recording=Path(folder)/'recording'
            with Recorder(recording,C)as recorder:
                for seq in range(1,21):recorder.write(tone([(6,0,2000)],seq))
            with patch('radar_min.rd_gui.stream',side_effect=AssertionError('No serial in replay')):
                window=Window(arguments(config,recording))
                try:
                    window.start();deadline=time.monotonic()+4
                    while time.monotonic()<deadline and not len(window.track_points.get_offsets()):
                        self.app.processEvents();window.tick();time.sleep(.01)
                    self.assertGreater(len(window.track_points.get_offsets()),0)
                    window.stop_run();window.thread.join(timeout=5);window.tick()
                    self.assertFalse(window.thread.is_alive())
                    self.assertEqual(window.table.rowCount(),0)
                    self.assertTrue(window.start_button.isEnabled())
                    self.assertFalse(window.root.exists())
                finally:window.close()

    def test_live_start_wires_shared_stream_and_clears_on_completion(self):
        with tempfile.TemporaryDirectory()as folder:
            config=Path(folder)/'config.json';C.save(config)
            window=Window(arguments(config));window.root=Path(folder)/'gui'
            calls=[]
            def fake_stream(port,config,output,seconds,detector,observer,stop_event,quiet):
                calls.append((port,output,detector.metadata,quiet))
                for seq in (1,2,3):
                    f=tone([(6,0,2000)],seq);observer(f,detector.update(f))
            try:
                with patch('radar_min.rd_gui.stream',side_effect=fake_stream):
                    window.start();window.thread.join(timeout=5);window.tick()
                self.assertEqual(len(calls),1)
                self.assertEqual(calls[0][1],window.root/'live-001')
                self.assertTrue(calls[0][3]);self.assertIn('association',calls[0][2])
                self.assertEqual(window.table.rowCount(),0)
                self.assertEqual(window.processor.associator.tracks,[])
                self.assertIn('Recording saved',window.saved.text())
            finally:window.close()

    def test_cli_does_not_allow_implicit_live_access(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['rd-gui','--snapshot','unused.png']),2)
            self.assertEqual(main(['rd-gui','--config','configs/qualification-avg16-timing.json']),2)


if __name__=='__main__':unittest.main()
