"""Offline nuisance search outside connected detected component support."""
import numpy as np
from tools.joint_component_fit import JointComponentFit

class SupportedNuisanceFit(JointComponentFit):
    def __init__(self,c):
        super().__init__(c)
        self.wide_grid=np.arange(.05,5.0001,.01)
        self.wide_q=np.array([self.basis(r) for r in self.wide_grid])
    def fit_associated(self,traces,candidate_bin,qualified_bins=None,max_iterations=8):
        low=high=candidate_bin;qualified=set(qualified_bins or [])
        while low-1 in qualified:low-=1
        while high+1 in qualified:high+=1
        lower=(low-1)*self.c.spacing_m;upper=(high+1)*self.c.spacing_m
        # Mask uses the detector, never a measured target-distance label.
        outside=(self.wide_grid<lower)|(self.wide_grid>upper)
        self.far_grid=self.wide_grid[outside];self.far_q=self.wide_q[outside]
        result=super().fit_associated(traces,candidate_bin,qualified_bins,max_iterations)
        result['target_support_m']=[lower,upper]
        return result
