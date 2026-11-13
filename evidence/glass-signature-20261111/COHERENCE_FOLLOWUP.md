# Follow-up fixed after the initial 27-metric audit

The initial run found RX1/RX2 coherence increasing on all nine paired closures
and exceeding maximum same-state repeat variation within each setup. No fixed
metric globally separates the recording medians. This follow-up is exploratory
and prompted by that result; it is not a second independent validation.

Question: is the coherence change evidence beyond a change in deterministic
stationary scene energy relative to fluctuations?

For each of the three receiver pairs, in each original ten-frame window, retain
the observed coherence and compute a stationary-mean surrogate. For spectra X,
let mu = mean over chirps and frames, P = mean |X|^2, and C_ab = mean Xa conj(Xb).
The shared normalization is D = sum_bins sqrt(Pa Pb).

- Observed coherence = sum_bins |C_ab| / D.
- Stationary-mean surrogate = sum_bins |mu_a conj(mu_b)| / D.
- Difference = observed coherence minus surrogate.
- Residual cross covariance = sum_bins |C_ab - mu_a conj(mu_b)| / D.

The surrogate corresponds to independently pairing samples between receivers
while preserving each receiver's deterministic complex mean and total power.
It removes correlated time-varying fluctuations. It is not a physical model of
glass, and cannot distinguish a glass reflection from any other stationary
scatterer. Agreement with it does not prove independent or Gaussian noise.

Use three regions without searching: the original surveyed pane ROI, the
original local reference bins, and all remaining usable bins outside both.
Report every pair/region, recording medians and paired changes, plus maximum
absolute window difference between observed and surrogate. Do not use the
follow-up to select a new detector or claim statistical significance.

Synthetic checks must distinguish a generic stationary coherent tone plus
independent noise from a coherent but zero-mean time-varying signal. Material
labels do not enter either synthetic construction.
