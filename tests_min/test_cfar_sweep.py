import unittest
import contextlib
import io
import json
from pathlib import Path
import tempfile
from radar.storage import Recorder
from radar_min.cfar import CfarConfig, CfarDetector
from tests_min.test_cfar import C, frame
from tools.sweep_cfar import aggregate, choose, episodes, measure, main, load_sessions


class SweepTests(unittest.TestCase):
    def test_episodes_split_at_missing_frame_and_timestamp_gap(self):
        frames=[frame(i) for i in [1,2,4,5,6]]
        runs=episodes([True]*5,frames,.1)
        self.assertEqual([r['frames'] for r in runs],[2,3])
        self.assertEqual([r['duration_s'] for r in runs],[.2,.3])
        self.assertEqual(episodes([False]*5,frames,.1),[])

    def test_metrics_count_wrong_bin_and_misses_in_denominator(self):
        frames=[frame(i) for i in range(1,5)]
        readings=[dict(target_detected=hit,range_bin=k,provisional_range_m=k*C.spacing_m if hit else None,reason='test')
                  for hit,k in [(False,None),(True,1),(True,2),(False,None)]]
        m=measure(readings,frames,C,.3)
        self.assertEqual(m['detection_rate'],.5)
        self.assertEqual(m['expected_bin_rate'],.25)
        self.assertEqual(m['wrong_bin_frames'],1)
        self.assertEqual(len(m['detection_episodes']),1)
        self.assertEqual(m['accepted_bin_switches'],1)

    def test_selection_respects_empty_constraint_and_ignores_validation(self):
        def item(factor, coverage, empty, longest):
            return dict(settings=dict(guard_cells=2,training_cells=8,min_training_cells=8,factor=factor),
                tune=dict(target_expected_bin_rate=coverage,target_detection_rate=coverage,empty_detection_rate=empty,
                          longest_empty_detection_s=longest,balanced_score=(coverage+1-empty)/2),
                validation=dict(target_expected_bin_rate=1-coverage))
        good=item(3,.7,0,0)
        candidates=[item(2,.99,.02,.6),good,item(4,.4,0,0)]
        chosen,feasible=choose(candidates,.01,.5)
        self.assertIs(chosen,good);self.assertTrue(feasible)
        chosen,feasible=choose([candidates[0]],0,0)
        self.assertFalse(feasible)

    def test_macro_average_does_not_weight_long_recordings_more(self):
        rows=[]
        for label,rate,matched,n in [(None,0,None,100),(.3,1,1,10),(.5,0,0,1000)]:
            rows.append(dict(target_m=label,metrics=dict(detection_rate=rate,expected_bin_rate=matched,
                detection_episodes=[],longest_detection_s=0,longest_miss_s=0,frames=n)))
        a=aggregate(rows)
        self.assertEqual(a['target_detection_rate'],.5)
        self.assertEqual(a['balanced_score'],.75)

    def test_cli_creates_report_plots_and_provenance_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            sessions=[]
            for index, (split, label) in enumerate([('tune', None), ('tune', 2*C.spacing_m),
                                                   ('validation', None), ('validation', 2*C.spacing_m)]):
                name=f'r{index}'
                with Recorder(root/name,C) as recorder:
                    for seq in range(index*10+1,index*10+6):
                        recorder.write(frame(seq,amplitude=0 if label is None else 1000))
                sessions.append(dict(recording=name,group=name,split=split,target_m=label))
            manifest=root/'manifest.json';manifest.write_text(json.dumps(dict(sessions=sessions)))
            out=root/'report'
            args=['--manifest',str(manifest),'--root',str(root),'--output',str(out),
                  '--guards','1','--training','4','--factors','2','6']
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main(args),0)
            report=json.loads((out/'report.json').read_text())
            self.assertEqual(len(report['grid']),2)
            self.assertEqual(report['comparisons']['selected']['splits']['validation']['recordings'],2)
            self.assertFalse(report['comparisons']['selected']['splits']['stress']['meets_empty_constraints'])
            self.assertTrue(report['source_sha256']['radar_min/cfar.py'])
            for name in ['README.md','tradeoff.png','recording-coverage.png','selected-timeline.png',
                         'selected-settings.json','grid.csv','timelines.jsonl']:
                self.assertGreater((out/name).stat().st_size,0)
            with self.assertRaises(FileExistsError):main(args)
            sessions[2]['group']=sessions[0]['group']
            manifest.write_text(json.dumps(dict(sessions=sessions)))
            with self.assertRaisesRegex(ValueError,'group cannot span splits'):
                load_sessions(manifest,root)

    def test_actual_detector_metrics_include_confirmation_startup(self):
        frames=[frame(i) for i in range(1,6)]
        detector=CfarDetector(C,CfarConfig(factor=3))
        readings=[detector.update(f) for f in frames]
        m=measure(readings,frames,C,2*C.spacing_m)
        self.assertEqual(m['detected_frames'],3)
        self.assertEqual(m['expected_bin_rate'],.6)
        self.assertEqual(m['longest_miss_s'],.2)


if __name__ == '__main__':unittest.main()
