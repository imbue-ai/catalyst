# Theory: Width-Complexity Threshold Bifurcation

## Core Hypothesis

Bifurcation in shallow ReLU MLPs occurs when the network width crosses a critical threshold relative to the "piecewise-linear complexity" of the target function. Specifically, a target function that is well-approximated by K linear pieces requires approximately K ReLU neurons to represent faithfully. When width < K, the network is forced into a qualitatively different (and suboptimal) representational strategy. When width >= K, the network can adopt the "natural" piecewise-linear decomposition. The transition between these regimes is abrupt — a bifurcation.

## Predictions

1. **Width threshold**: For a target function with K "kinks" (points of non-differentiability), bifurcation should occur near width = K. For example, |x| has 1 kink, so bifurcation should occur between width 1 and width 2-3.

2. **Smooth targets resist bifurcation**: Smooth target functions (like x^2 or sin(x)) should show gradual, not abrupt, changes in representation as width increases, because they don't have a natural piecewise-linear decomposition at any specific K.

3. **Learning rate interaction**: Higher learning rates may shift the bifurcation threshold, as SGD dynamics with large steps may fail to find the optimal decomposition even when width is sufficient.

4. **Representation signature**: Below the threshold, neurons tend to all contribute similar, overlapping components. Above the threshold, neurons specialize into distinct linear pieces covering different regions of the input domain.

## Proposed Mechanism

The loss landscape has multiple local minima corresponding to different representational strategies. Below the critical width, only the "distributed" strategy (many overlapping, similar neurons) exists as a local minimum. Above the critical width, a "specialized" strategy (neurons covering distinct regions) becomes available and is lower-loss. The bifurcation occurs when the specialized minimum first appears and the optimization trajectory falls into it.
