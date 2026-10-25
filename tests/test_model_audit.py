from dataclasses import replace
from pathlib import Path
import unittest
import numpy as np
from radar.config import Config
from radar.model_audit import ambiguity_certificate,raw_ambiguity_certificate,dominant_mode_scores,steering_grid,source_facts


class ModelAuditTests(unittest.TestCase):
    def test_raw_chirps_also_have_coherent_scene_ambiguity(self):
        c=raw_ambiguity_certificate(Config())
        self.assertLess(c['raw_complex_vector_relative_difference'],1e-12)
        self.assertEqual(len(c['scene_a_indices']),3)
        self.assertEqual(len(c['scene_b_indices']),1)
    def test_two_distinct_nonnegative_scenes_have_equal_covariance(self):
        c=ambiguity_certificate(Config())
        a,b=np.array(c['scene_a_power']),np.array(c['scene_b_power'])
        self.assertTrue(np.all(a>=0) and np.all(b>=0))
        self.assertAlmostEqual(a.sum(),1)
        self.assertAlmostEqual(b.sum(),1)
        self.assertGreater(np.linalg.norm(a-b),0.3)
        self.assertLess(c['covariance_relative_difference'],1e-12)
        self.assertLessEqual(c['design_rank'],7)

    def test_conjugation_sign_ambiguity_is_exact(self):
        config=Config()
        directions,virtual=steering_grid(config)
        vector=virtual[:,300]
        covariance=np.outer(vector,vector.conj())[None]
        score,indices,_=dominant_mode_scores(covariance,np.eye(3),[0,1,2],False,virtual)
        reflected_score,reflected_indices,_=dominant_mode_scores(covariance,np.eye(3),[0,1,2],True,virtual)
        np.testing.assert_allclose(score,reflected_score,atol=1e-12)
        np.testing.assert_allclose(directions[:,indices[0]],-directions[:,reflected_indices[0]],atol=1e-12)

    def test_consistency_scoring_does_not_certify_true_model(self):
        config=Config()
        _,virtual=steering_grid(config)
        matrix=np.array([[1,0,0],[0.15j,1,0],[0.1,0,1]])
        raw=np.linalg.solve(matrix,virtual[:,400])
        covariance=np.outer(raw,raw.conj())[None]
        score,_,_=dominant_mode_scores(covariance,matrix,[0,1,2],False,virtual)
        self.assertAlmostEqual(score[0],1,places=12)

    def test_register_profile_reveals_highpass_corner(self):
        root=Path(__file__).resolve().parents[1]
        facts=source_facts(root/'firmware/vendor/presence_detection_tracking.h',
            root.parent/'mtb_shared/sensor-xensiv-bgt60cutrxx/release-v1.1.0/register_hal/xensiv_bgt60cutrxxb_register_hal.h',root/'firmware/main.c')
        self.assertEqual([rx['hpf1_hz'] for rx in facts['rx_register_configuration']],[350000]*3)
        self.assertEqual([rx['gain_db'] for rx in facts['rx_register_configuration']],[42]*3)
        self.assertEqual(facts['profile_averaging_factor'],16)
        self.assertIsNone(facts['chirp_interval_measured_s'])
