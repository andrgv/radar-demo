import unittest

from radar_min.tracking import SingleRangeTracker, accepted_measurement, enrich_tracking
from radar_min.tracking_gui import tracking_display


class SingleRangeTrackerTests(unittest.TestCase):
    def tracker(self, **values):
        return SingleRangeTracker(**values)

    def update(self, tracker, value, frame):
        return tracker.update(value, frame * 100_000)

    def test_three_consecutive_measurements_confirm_track(self):
        tracker = self.tracker()
        self.assertEqual(self.update(tracker, 0.50, 0)['state'], 'tentative')
        self.assertEqual(self.update(tracker, 0.51, 1)['state'], 'tentative')
        result = self.update(tracker, 0.49, 2)
        self.assertEqual(result['state'], 'tracking')
        self.assertTrue(result['measured'])
        self.assertAlmostEqual(result['range_m'], 0.4984, places=4)

    def test_tentative_track_requires_consecutive_measurements(self):
        tracker = self.tracker()
        first = self.update(tracker, 0.5, 0)
        lost = self.update(tracker, None, 1)
        second = self.update(tracker, 0.5, 2)
        self.assertEqual(lost['state'], 'lost')
        self.assertNotEqual(first['track_id'], second['track_id'])
        self.assertEqual(second['hits'], 1)

    def test_confirmed_track_marks_misses_and_expires(self):
        tracker = self.tracker(max_misses=3)
        for frame in range(3):
            result = self.update(tracker, 0.5, frame)
        self.assertEqual(result['state'], 'tracking')
        for frame in (3, 4):
            result = self.update(tracker, None, frame)
            self.assertEqual(result['state'], 'coasting')
            self.assertFalse(result['measured'])
            self.assertIsNone(result['raw_range_m'])
            self.assertAlmostEqual(result['range_m'], 0.5)
        result = self.update(tracker, None, 5)
        self.assertEqual(result['state'], 'lost')
        self.assertFalse(result['measured'])

    def test_default_tracker_bridges_detector_reconfirmation_gap(self):
        tracker = self.tracker()
        for frame in range(3):
            result = self.update(tracker, 0.5, frame)
        track_id = result['track_id']
        for frame in range(3,10):
            result = self.update(tracker, None, frame)
            self.assertEqual(result['state'], 'coasting')
            self.assertFalse(result['measured'])
        result = self.update(tracker, 0.46, 10)
        self.assertEqual(result['state'], 'tracking')
        self.assertEqual(result['track_id'], track_id)

    def test_large_jump_starts_new_track(self):
        tracker = self.tracker(base_gate_m=0.05, max_speed_mps=0)
        for frame in range(3):
            old = self.update(tracker, 0.5, frame)
        new = self.update(tracker, 0.9, 3)
        self.assertNotEqual(old['track_id'], new['track_id'])
        self.assertEqual(new['state'], 'tentative')

    def test_motion_direction_uses_multiple_measurements(self):
        closer = self.tracker(smoothing=1)
        away = self.tracker(smoothing=1)
        for frame, value in enumerate((0.80, 0.78, 0.76, 0.74, 0.72, 0.70)):
            close_result = self.update(closer, value, frame)
        for frame, value in enumerate((0.40, 0.42, 0.44, 0.46, 0.48, 0.50)):
            away_result = self.update(away, value, frame)
        self.assertEqual(close_result['motion'], 'moving_closer')
        self.assertEqual(away_result['motion'], 'moving_away')

    def test_stream_fault_resets_active_track(self):
        tracker = self.tracker()
        for frame in range(3):
            self.update(tracker, 0.5, frame)
        result = tracker.update(None, 300_000, reset_reason='sequence_gap')
        self.assertEqual(result['state'], 'lost')
        self.assertEqual(result['reset_reason'], 'sequence_gap')
        self.assertEqual(self.update(tracker, 0.5, 4)['state'], 'tentative')

    def test_only_current_accepted_estimate_can_feed_tracker(self):
        reading = dict(target_detected=True, experimental_range_m=0.4,
                       fit_boundary=False, timestamp_us=0,
                       reason='spectral_change_uncalibrated')
        self.assertEqual(accepted_measurement(reading), 0.4)
        reading['fit_boundary'] = True
        self.assertIsNone(accepted_measurement(reading))
        reading['fit_boundary'] = False
        reading['target_detected'] = False
        self.assertIsNone(accepted_measurement(reading))

    def test_enrichment_is_json_safe_and_marks_reset_reason(self):
        tracker = self.tracker()
        reading = dict(target_detected=False, experimental_range_m=None,
                       fit_boundary=False, timestamp_us=0,
                       reason='sequence_gap')
        enrich_tracking(reading, tracker)
        self.assertEqual(reading['track']['state'], 'idle')
        self.assertEqual(reading['track']['reset_reason'], 'sequence_gap')

    def test_tracking_display_distinguishes_current_and_retained_values(self):
        current=dict(track=dict(state='tracking',track_id=2,range_m=0.48,
            motion='moving_closer',measured=True))
        retained=dict(track=dict(state='coasting',track_id=2,range_m=0.48,
            measurement_age_s=0.2,measured=False))
        self.assertIn('moving closer',tracking_display(current,True))
        self.assertIn('No current measurement',tracking_display(retained,True))


if __name__ == '__main__':
    unittest.main()
