# Pitchfork Bifurcation in Shallow MLP Training: A Mechanistic Theory

## 1. Setup

We study a two-layer (shallow) MLP trained with SGD in the mean-field (muP) parameterization:

$$f(x) = \frac{1}{n} \sum_{i=1}^{n} a_i \, \sigma(w_i^\top x / \sqrt{d})$$

where $n$ is the width, $d$ is the input dimension, $\sigma = \text{ReLU}$, $w_i \in \mathbb{R}^d$ are first-layer weights, and $a_i \in \mathbb{R}$ are second-layer weights.

**Initialization.** $W \sim \mathcal{N}(0, \alpha^2 I)$ with $\alpha \ll 1$ (small init scale), $a_i = 0$ for all $i$.

**SGD update (muP scaling).** For squared loss $L = \frac{1}{2B}\sum_b (f(x_b) - T(x_b))^2$:

$$a_i \leftarrow a_i - \eta \cdot n \cdot \frac{\partial L}{\partial a_i}, \qquad w_i \leftarrow w_i - \eta \cdot n \cdot \frac{\partial L}{\partial w_i}$$

The factor of $n$ in the update ensures the network operates in the mean-field regime where individual neurons contribute $O(1/n)$ to the output but their collective dynamics remain $O(1)$.

**Target function.** We focus on $d = 2$ with the target:

$$T(x_1, x_2) = 2\,\text{relu}(x_1) + 2\,\text{relu}(x_2) - 0.4\,\text{relu}(x_1 + x_2)$$

This target has an exact $x_1 \leftrightarrow x_2$ permutation symmetry and requires exactly **two distinct neuron directions** in its optimal representation.

## 2. The Bifurcation Phenomenon

Training exhibits three distinct phases visible in the neuron weight scatter plot $(w_{i,1}, w_{i,2})$:

| Phase | Steps (typical) | Description |
|-------|----------------|-------------|
| **Handle** | 0 – ~8,000 | All neurons cluster on the diagonal $w_1 = w_2$, forming a thin line ("handle") |
| **Fork** | ~8,000 – ~12,000 | The line destabilizes and splits into two branches |
| **Prongs** | ~12,000+ | Two stable branches along $w \propto e_1$ and $w \propto e_2$, loss drops suddenly |

The transition from handle to prongs is a **supercritical pitchfork bifurcation** in the neuron weight dynamics. The loss remains at a plateau throughout the handle phase and drops sharply at the fork — the plateau duration is entirely determined by the bifurcation time.

## 3. Phase I: Diagonal Growth (The Handle)

### 3.1 Coordinate system

Define the diagonal and transverse directions:

$$e_+ = \frac{1}{\sqrt{2}}(1, 1), \qquad e_- = \frac{1}{\sqrt{2}}(1, -1)$$

Decompose each neuron's weight as $w_i = R_i \, e_+ + \delta_i \, e_-$ where $R_i$ is the diagonal (radial) component and $\delta_i$ is the transverse component.

### 3.2 Why neurons align on the diagonal

At initialization, $a_i = 0$ and $w_i \sim \mathcal{N}(0, \alpha^2 I)$. The gradient of the loss with respect to $w_i$ is:

$$\frac{\partial L}{\partial w_i} = -\frac{a_i}{n\sqrt{d}} \cdot \frac{1}{B} \sum_b (T(x_b) - f(x_b)) \cdot \sigma'(w_i^\top x_b / \sqrt{d}) \cdot x_b$$

Since $a_i = 0$ initially, the first-layer weights $w_i$ receive **zero gradient**. But $a_i$ does receive a gradient:

$$\frac{\partial L}{\partial a_i} = -\frac{1}{n} \cdot \frac{1}{B} \sum_b (T(x_b) - f(x_b)) \cdot \sigma(w_i^\top x_b / \sqrt{d})$$

Since $f \approx 0$ initially, this simplifies to $\frac{\partial L}{\partial a_i} \approx \frac{1}{n} \mathbb{E}[T(x) \cdot \text{relu}(w_i^\top x / \sqrt{d})]$.

For our symmetric target, the projection $Q(w) = \mathbb{E}[T(x) \cdot \text{relu}(w^\top x)]$ is maximized along the diagonal $e_+$ due to the $x_1 \leftrightarrow x_2$ symmetry. Once $a_i$ becomes nonzero, $w_i$ starts receiving gradient that pushes it toward the direction maximizing $Q$ — the diagonal.

### 3.3 Coupled radial dynamics

On the diagonal manifold ($\delta_i = 0$), the mean-field dynamics reduce to a coupled ODE for each neuron's radial component $R$ and second-layer weight $a$:

$$\dot{a} = \eta \, Q \, R, \qquad \dot{R} = \eta \, Q \, a$$

where $Q = \mathbb{E}[T(x) \cdot \text{relu}(x_+)] / \sqrt{2} \approx 1.228$ is the target projection onto the diagonal ReLU feature.

These are the equations of a **hyperbolic system** with solution:

$$a(t) = \alpha \sinh(\lambda t), \qquad R(t) = \alpha \cosh(\lambda t)$$

where $\lambda = \eta Q / \sqrt{2}$ is the diagonal growth rate. This yields the conservation law:

$$R^2(t) - a^2(t) = \alpha^2 \quad \text{(constant)}$$

which implies $a \approx R$ for $t \gg 1/\lambda$ (both grow exponentially as $\sim \alpha e^{\lambda t}$).

**Empirical validation:** The ratio $a_{\text{rms}} / R_{\text{rms}}$ converges to $\approx 1$ during the handle phase, confirming the conservation law.

## 4. Phase II: Transverse Instability (The Fork)

### 4.1 Linear stability analysis

The diagonal manifold is a fixed subspace of the dynamics. To determine its stability, we linearize the gradient flow around a neuron at position $(R, 0)$ (on the diagonal) and ask: does a small transverse perturbation $\delta$ grow or shrink?

For a neuron with weight $w = R \, e_+ + \delta \, e_-$ and $|\delta| \ll R$, the transverse component of the gradient is:

$$\dot{\delta} = \eta \cdot a \cdot \mathbb{E}\left[\frac{\partial}{\partial \delta} \left[ r(x) \cdot \text{relu}(Rx_+ + \delta x_-) \right] \right]$$

where $r(x) = T(x) - f_{\text{diag}}(x)$ is the residual not captured by the diagonal fit.

The key insight is that $\text{relu}(Rx_+ + \delta x_-)$ has a kink at $x_+ = -\delta x_- / R$. For $R$ large and $\delta$ small, this kink is near $x_+ = 0$, and the transverse derivative picks up a contribution proportional to $|x_-|$ — the absolute value of the transverse input component.

### 4.2 The equator residual

The residual evaluated at the "equator" ($x_+ = 0$, i.e., $x_1 = -x_2$) is:

$$r(0, v) = T(v/\sqrt{2}, -v/\sqrt{2}) = \sqrt{2}|v|$$

This is **nonzero and independent of the diagonal fitting progress** — the diagonal fit (which only involves $x_+$) cannot reduce the residual on the equator. This persistent residual is the source of the transverse instability.

### 4.3 Transverse Lyapunov exponent

The linearized growth rate of $\delta$ is:

$$\frac{\dot{\delta}}{\delta} = \frac{2}{\pi} \cdot \eta \cdot \frac{a}{R} \approx \frac{2}{\pi} \cdot \eta$$

where the factor $2/\pi$ arises from the Gaussian integral $\mathbb{E}[|x_-| \cdot \mathbf{1}_{x_+ > 0}]$ for standard normal $x_\pm$, and we used $a \approx R$ from the conservation law (Phase I).

The quantity $\lambda_\perp = (2/\pi) \cdot \eta$ is the **transverse Lyapunov exponent** — the exponential growth rate of perturbations perpendicular to the diagonal.

### 4.4 Why this is a pitchfork

The bifurcation is a pitchfork (not a transcritical or saddle-node) because:

1. **Symmetry:** The target and initialization are invariant under $x_1 \leftrightarrow x_2$ (equivalently, $\delta \to -\delta$). This forces the diagonal to be a fixed point of the transverse dynamics for all time.
2. **Instability:** The transverse Lyapunov exponent $\lambda_\perp > 0$, so the diagonal becomes unstable once neurons have grown large enough.
3. **Supercritical:** The two branches (prongs) are stable — neurons settle into the two directions $e_1$ and $e_2$ needed by the target.

The $\delta \to -\delta$ symmetry means perturbations must grow symmetrically in both directions, creating exactly two prongs.

## 5. Bifurcation Time Formula

### 5.1 Derivation

The transverse perturbation grows as:

$$\delta(t) \sim \delta_0 \cdot \exp\left(\lambda_\perp \cdot t\right) = \delta_0 \cdot \exp\left(\frac{2}{\pi} \eta \, t\right)$$

where $\delta_0 \sim O(\alpha)$ is the initial transverse spread from random initialization.

Bifurcation becomes visible when $\delta(t)$ becomes comparable to $R(t)$, i.e., when $\delta / R \sim O(1)$. Since $R(t)$ saturates at a value $s^* \sim O(1)$ (determined by the target norm), the bifurcation occurs when:

$$\alpha \cdot e^{(2/\pi) \eta \, t_{\text{bif}}} \sim s^*$$

Solving:

$$\boxed{t_{\text{bif}} = \frac{\pi}{2\eta} \ln\!\left(\frac{s^*}{\alpha}\right)}$$

where $s^* \approx 1.86$ is the diagonal saturation norm (empirically measured).

### 5.2 Empirical correction

The first-order theory systematically overestimates $t_{\text{bif}}$ by a constant factor. Measured across all parameter regimes:

$$t_{\text{bif}}^{\text{(measured)}} \approx \kappa \cdot \frac{\pi}{2\eta} \ln\!\left(\frac{s^*}{\alpha}\right), \qquad \kappa \approx 0.76$$

The correction factor $\kappa$ likely arises from:
- Higher-order terms in the linearization (the pre-bifurcation growth is not purely exponential)
- The fact that $a/R$ slightly exceeds 1 during the growth phase (boosting $\lambda_\perp$)
- Finite batch-size fluctuations that seed the instability earlier

The remarkable feature is that $\kappa$ is **constant across all parameter regimes** — it does not depend on $\alpha$, $\eta$, or $n$.

## 6. Scaling Laws

The bifurcation time formula immediately yields three scaling predictions:

### 6.1 Logarithmic dependence on init scale: $t_{\text{bif}} \propto \ln(1/\alpha)$

| $\alpha$ | $\ln(1/\alpha)$ | $t_{\text{bif}}$ (measured) | $t_{\text{bif}}$ (predicted) | ratio |
|-----------|-----------------|----------------------------|------------------------------|-------|
| $10^{-3}$ | 6.9 | 4,669 | 5,913 | 0.79 |
| $10^{-4}$ | 9.2 | 5,890 | 7,721 | 0.76 |
| $10^{-5}$ | 11.5 | 7,285 | 9,530 | 0.76 |
| $10^{-6}$ | 13.8 | 8,792 | 11,338 | 0.78 |
| $10^{-7}$ | 16.1 | 9,880 | 13,147 | 0.75 |
| $10^{-8}$ | 18.4 | 11,248 | 14,955 | 0.75 |

The ratio $t_{\text{bif}}^{\text{meas}} / t_{\text{bif}}^{\text{pred}}$ is constant at $0.76 \pm 0.02$ across **5 decades** of $\alpha$, confirming the $\ln(1/\alpha)$ scaling.

### 6.2 Inverse dependence on learning rate: $t_{\text{bif}} \propto 1/\eta$

| $\eta$ | $1/\eta$ | $t_{\text{bif}}$ (measured) | $t_{\text{bif}}$ (predicted) | ratio |
|--------|---------|----------------------------|------------------------------|-------|
| 0.0005 | 2,000 | 34,352 | 45,352 | 0.76 |
| 0.001 | 1,000 | 17,402 | 22,676 | 0.77 |
| 0.002 | 500 | 8,792 | 11,338 | 0.78 |
| 0.004 | 250 | 4,312 | 5,669 | 0.76 |
| 0.008 | 125 | 2,142 | 2,835 | 0.76 |

Again, the ratio is constant at $0.76 \pm 0.01$ across a $16\times$ range of learning rates, confirming $t_{\text{bif}} \propto 1/\eta$.

### 6.3 Independence of width: $t_{\text{bif}} \not\propto n$

| Width $n$ | $t_{\text{bif}}$ (measured) | $t_{\text{bif}}$ (predicted) | ratio |
|-----------|----------------------------|------------------------------|-------|
| 100 | 8,700 | 11,338 | 0.77 |
| 500 | 8,580 | 11,338 | 0.76 |
| 1,000 | 8,700 | 11,338 | 0.77 |

The bifurcation time is independent of width (all within $\pm 1\%$), confirming that this is a **mean-field** phenomenon — each neuron's dynamics are governed by the population-level loss landscape, not by finite-width fluctuations.

## 7. Necessary Conditions for Pitchfork Bifurcation

The theory identifies three necessary conditions:

### 7.1 Discrete symmetry in the target

The target must be invariant under some permutation/reflection of the input coordinates. This symmetry creates a fixed subspace (the "diagonal") in weight space that all neurons initially approach.

**Counter-example:** The asymmetric target $T(x) = 3\,\text{relu}(x_1) + \text{relu}(x_2)$ has no $x_1 \leftrightarrow x_2$ symmetry. Training this target produces a **fan pattern** (neurons spread continuously in the first quadrant) rather than a pitchfork. There is no handle phase and no sudden loss drop.

### 7.2 Interaction term breaking the diagonal optimum

The target must require neurons in directions that are **not** on the diagonal. Pure diagonal targets like $\text{relu}(x_1 + x_2)$ can be fit entirely on the diagonal without bifurcation.

The interaction term $-0.4\,\text{relu}(x_1 + x_2)$ creates a nonzero equator residual $r(0, v) \neq 0$, driving the transverse instability.

### 7.3 Small initialization scale

The init scale $\alpha$ must be small enough that the handle phase is long relative to the transverse growth timescale. For $\alpha \sim O(1)$, bifurcation happens immediately (no visible handle). The dramatic pitchfork effect requires $\alpha \ll s^*$, i.e., $\ln(s^*/\alpha) \gg 1$.

## 8. Summary

The pitchfork bifurcation in shallow MLP training is a **symmetry-breaking instability** with a fully predictive theory:

1. **Mechanism:** Symmetric initialization + symmetric target $\Rightarrow$ all neurons first align on the diagonal (handle). The diagonal fit cannot resolve the equator residual, which drives exponential growth of transverse perturbations at rate $\lambda_\perp = (2/\pi)\eta$. When perturbations reach $O(1)$, the diagonal becomes unstable and neurons split into the target's component directions (prongs).

2. **Bifurcation time:**
$$t_{\text{bif}} \approx 0.76 \cdot \frac{\pi}{2\eta} \ln\!\left(\frac{s^*}{\alpha}\right)$$

3. **Scaling laws** (all empirically validated):
   - $t_{\text{bif}} \propto \ln(1/\alpha)$ — logarithmic in init scale
   - $t_{\text{bif}} \propto 1/\eta$ — inverse in learning rate
   - $t_{\text{bif}} \not\propto n$ — independent of width (mean-field)

4. **The $2/\pi$ constant** is the transverse Lyapunov exponent for ReLU activations with Gaussian inputs, arising from $\mathbb{E}[|z| \cdot \mathbf{1}_{z' > 0}] = \sqrt{2/\pi} \cdot 1/\sqrt{2} = 1/\sqrt{\pi}$ integrated over the joint distribution.

5. **Loss plateau = handle phase.** The sudden loss drop that makes this phenomenon striking is not a separate effect — it is the bifurcation itself. The loss cannot decrease significantly until neurons differentiate from the diagonal.
