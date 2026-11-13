import json
import contextlib
import io
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np

from radar.angle_lab import raw_model_phase
from radar.cfar_map import MultiObstacleMap, demo_frame, iter_results, main
from radar.config import Config
from radar.live_results import LiveResults
from radar.protocol import Frame, Parser, encode
from radar.storage import Recorder


class LiveResultsTests(unittest.TestCase):
    def test_slow_display_keeps_latest_and_producer_consumes_every_result(self):
        finished = threading.Event()
        consumed = []
        def produce():
            try:
                for i in range(100):
                    consumed.append(i)
                    yield dict(sequence=i)
            finally:
                finished.set()
        results = LiveResults(produce())
        try:
            self.assertTrue(finished.wait(2))
            self.assertEqual(consumed, list(range(100)))
            self.assertEqual(results.mailbox.qsize(), 1)
            self.assertEqual(next(results)['sequence'], 99)
            with self.assertRaises(StopIteration):
                next(results)
        finally:
            results.close()

    def test_worker_errors_reach_consumer_and_iterator_closes_in_owner_thread(self):
        thread_ids = []
        def produce():
            try:
                thread_ids.append(threading.get_ident())
                yield dict(sequence=1)
                raise TimeoutError('radar stopped')
            finally:
                thread_ids.append(threading.get_ident())
        results = LiveResults(produce())
        try:
            self.assertTrue(results.done.wait(2))
            self.assertEqual(next(results)['sequence'], 1)
            with self.assertRaisesRegex(TimeoutError, 'radar stopped'):
                next(results)
            self.assertEqual(thread_ids[0], thread_ids[1])
            self.assertNotEqual(thread_ids[0], threading.get_ident())
        finally:
            results.close()

    def test_close_stops_producer_and_releases_resources(self):
        released = threading.Event()
        def produce():
            try:
                while True:
                    threading.Event().wait(.005)
                    yield None
            finally:
                released.set()
        results = LiveResults(produce())
        results.close()
        self.assertTrue(released.is_set())
        self.assertFalse(results.thread.is_alive())

    def test_fragmented_ten_hz_serial_keeps_timing_valid_during_slow_render(self):
        cfg = Config.load('configs/exploratory-roll90-phase.json')
        packets = [encode(demo_frame(cfg, i)) for i in range(1, 21)]
        class Serial:
            def __init__(self):
                self.buffer = bytearray()
                self.index = 0
                self.started = None
                self.closed = False
                self.commands = []
            @property
            def in_waiting(self): return len(self.buffer)
            def write(self, command):
                self.commands.append(command)
                if command == b'B': self.started = time.monotonic()
            def flush(self): pass
            def reset_input_buffer(self): self.buffer.clear()
            def read(self, count):
                if not self.buffer:
                    if self.index >= len(packets): return b''
                    delay = self.started+(self.index+1)*.1-time.monotonic()
                    if delay > 0: threading.Event().wait(delay)
                    self.buffer.extend(packets[self.index])
                    self.index += 1
                n = min(count, 1020, len(self.buffer))
                result = bytes(self.buffer[:n])
                del self.buffer[:n]
                return result
            def close(self): self.closed = True
        serial = Serial()
        xyz = [0, 2, 0]
        detector = MultiObstacleMap(cfg, raw_model_phase(cfg, xyz)[0], xyz,
                                    min_range=.7, max_range=10)
        with tempfile.TemporaryDirectory() as tmp, patch('serial.Serial', return_value=serial), \
                patch('radar.acquisition.time.sleep'):
            output = Path(tmp)/'live'
            results = LiveResults(iter_results(detector, port='fake', output=output, seconds=1.35))
            try:
                first = None
                while first is None:
                    first = next(results)
                # Reproduce a >0.5s GUI render without delaying serial ingestion.
                threading.Event().wait(.65)
                self.assertGreaterEqual(serial.index, 6)
                self.assertLessEqual(results.mailbox.qsize(), 1)
                latest = next(results)
                self.assertGreaterEqual(latest['sequence'], first['sequence']+4)
                self.assertLess(time.monotonic()-latest['host_received_monotonic_s'], .3)
                list(results)
            finally:
                results.close()
            rows = [json.loads(line) for line in (output/'obstacles2d.jsonl').read_text().splitlines()]
            frames = [row for row in rows if 'clock_sync' in row]
            self.assertGreaterEqual(len(frames), 12)
            self.assertTrue(all(row['clock_sync']['reason'] is None for row in frames))
            self.assertTrue(any(row['obstacles'] for row in frames))
            self.assertTrue(serial.closed)
            self.assertEqual(serial.commands, [b'c', b'B', b'c'])

    def test_live_dashboard_slow_draw_does_not_stop_capture_or_mapping(self):
        cfg = Config(sample_rate_hz=5e6, slope_hz_s=33691406250000,
                     geometry_mm=[[0, 0], [0, 2.35], [-2.35, 0]], mount_roll_deg=90)
        class Source:
            def __init__(self, *args, **kwargs):
                self.started = time.monotonic()
                self.index = 0
                self.parser = Parser()
                self.pending = []
                self.serial = SimpleNamespace(in_waiting=0)
                self.closed = False
            def read(self):
                self.index += 1
                delay = self.started+self.index*.1-time.monotonic()
                if delay > 0: threading.Event().wait(delay)
                return demo_frame(cfg, self.index)
            def close(self): self.closed = True
        class SlowPlot:
            def __init__(self, *args, **kwargs): pass
            def update(self, result):
                if result is not None: threading.Event().wait(.65)
            def is_open(self): return True
            def close(self): pass
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root/'config.json'
            cfg.save(config_path)
            reference, output = root/'reference', root/'live'
            adc = 32768+1500*np.cos(2*np.pi*6*np.arange(cfg.samples)/cfg.samples)
            adc = np.broadcast_to(adc[None, :, None], (cfg.chirps, cfg.samples, 3)).astype('uint16')
            with Recorder(reference, cfg) as recorder:
                for i in range(1, 12):
                    recorder.write(Frame(i, i*100000, cfg.profile_id, adc))
            with patch('radar.acquisition.Source', Source), patch('radar.cfar_map_gui.MapPlot', SlowPlot), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = main(['--port', 'fake', '--config', str(config_path), '--reference', str(reference),
                    '--reference-xyz', '0', str(cfg.ranges[6]), '0', '--plot', '--seconds', '1.2',
                    '--output', str(output)])
            self.assertEqual(code, 0)
            rows = [json.loads(line) for line in (output/'obstacles2d.jsonl').read_text().splitlines()]
            frames = [row for row in rows if 'clock_sync' in row]
            self.assertGreaterEqual(len(frames), 10)
            self.assertTrue(all(row['clock_sync']['reason'] is None for row in frames))
            saved = json.loads((output/'map.json').read_text())
            self.assertEqual(len(saved['objects']), 3)
            self.assertTrue(all(item['confirmed'] for item in saved['objects']))


if __name__ == '__main__':
    unittest.main()
