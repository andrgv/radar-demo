"""Verify held-out boundaries and fitting behavior, not accuracy on hardware."""
from dataclasses import replace
import unittest
import numpy as np
from tools.calibrate_range_offline import Record,fit_model,predict,splits,FEATURES


def record(name,setup,label,peak,n=4):
    x=np.zeros((n,len(FEATURES)));x[:,0]=peak
    return Record(name,setup,label,x,np.ones(n,bool),name)

class CalibrationTests(unittest.TestCase):
    def test_group_splits_hold_entire_setup_out(self):
        rows=[record('a','one',.3,.2),record('b','one',.4,.3),record('c','two',.5,.4)]
        tested=[]
        for fold,train,test in splits(rows,'setup'):
            self.assertFalse({r.setup for r in train}&{r.setup for r in test})
            self.assertFalse({r.name for r in train}&{r.name for r in test})
            tested.extend(r.name for r in test)
        self.assertCountEqual(tested,['a','b','c'])

    def test_distance_splits_remove_every_occurrence(self):
        rows=[record('a','one',.4,.3),record('b','two',.4,.3),record('c','two',.5,.4)]
        for fold,train,test in splits(rows,'distance'):
            self.assertFalse({r.label for r in train}&{r.label for r in test})

    def test_affine_mapping_and_no_prediction_clipping(self):
        rows=[record('a','one',.3,.2),record('b','two',.5,.4)]
        model=fit_model(rows,'linear_peak')
        x=record('unseen','three',.99,.3).x
        np.testing.assert_allclose(predict(model,x),.4)
        x[:,0]=1
        np.testing.assert_allclose(predict(model,x),1.1)
        self.assertAlmostEqual(model['mean'][0],.3)
        self.assertAlmostEqual(model['scale'][0],.1)

    def test_long_capture_does_not_dominate_fit(self):
        rows=[record('a','one',.3,.2),record('b','two',.5,.45)]
        expanded=[replace(rows[0],x=np.repeat(rows[0].x,30,axis=0)),rows[1]]
        for kind in ('constant','linear_peak','spectral_ridge'):
            m1=fit_model(rows,kind);m2=fit_model(expanded,kind)
            np.testing.assert_allclose(predict(m1,rows[0].x),predict(m2,rows[0].x),atol=1e-12)

    def test_fitting_ignores_test_labels_and_features(self):
        train=[record('a','one',.3,.2),record('b','two',.5,.4)]
        held=record('test','other',.4,.3)
        before=fit_model(train,'spectral_ridge')
        held.label=-500;held.x[:]=1e8
        after=fit_model(train,'spectral_ridge')
        self.assertEqual(before,after)

if __name__=='__main__':unittest.main()
