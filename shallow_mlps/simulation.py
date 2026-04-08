"""Faithful Python port of simulation.js from jamiesimon.io/shallow-mlps.

Network:  f(x) = (1/n) * sum_i a_i * sigma(w_i^T x / sqrt(d))
Init:     W ~ N(0, alpha^2), a = 0 (muP)
Data:     x ~ N(0, I_d)
Loss:     (1/2) * E[(f_hat - f*)^2]
Training: SGD with muP scaling (step *= n)
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from .targets import compute_target, num_coeff_terms, parse_custom_expr_single


# ---- Activations (matching simulation.js exactly) ---------------------------

def _relu(x): return np.where(x > 0, x, 0.0)
def _relu_d(x): return np.where(x > 0, 1.0, 0.0)

def _tanh(x): return np.tanh(x)
def _tanh_d(x): c = np.cosh(x); return 1.0 / (c * c)

def _gelu(x):
    t = np.tanh(0.7978845608 * (x + 0.044715 * x**3))
    return 0.5 * x * (1 + t)
def _gelu_d(x):
    t = np.tanh(0.7978845608 * (x + 0.044715 * x**3))
    dt = (1 - t**2) * 0.7978845608 * (1 + 3 * 0.044715 * x**2)
    return 0.5 * (1 + t) + 0.5 * x * dt

def _linear(x): return x
def _linear_d(x): return np.ones_like(x)

ACTIVATIONS: dict[str, tuple[Callable, Callable]] = {
    "relu":   (_relu, _relu_d),
    "tanh":   (_tanh, _tanh_d),
    "gelu":   (_gelu, _gelu_d),
    "linear": (_linear, _linear_d),
}


# ---- Data classes -----------------------------------------------------------

@dataclass
class SimParams:
    """Parameters matching the demo's control panel."""
    n: int = 100             # width
    d: int = 10              # input dimension
    alpha: float = 1.0       # init scale
    eta: float = 0.01        # learning rate
    batch_size: int = 200    # batch size B
    activation: str = "relu"
    target_type: str = "staircase"
    num_terms: int = 2       # order T
    custom_expr: str = ""
    seed: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "n": self.n, "d": self.d, "alpha": self.alpha,
            "eta": self.eta, "batch_size": self.batch_size,
            "activation": self.activation, "target_type": self.target_type,
            "num_terms": self.num_terms, "custom_expr": self.custom_expr,
            "seed": self.seed,
        }


@dataclass
class NormRecord:
    step: int
    w_frob: float          # ||W||_F
    a_norm: float          # ||a||
    w_dir: list[float]     # per-direction column norms + rest
    h_rms: float           # RMS pre-activation


@dataclass
class CoeffRecord:
    step: int
    coeffs: list[float]    # projection onto target basis
    remainder: float       # ||f_hat - projection||


@dataclass
class SimState:
    """Full simulation state, serializable for output."""
    params: SimParams
    W: np.ndarray              # (n, d)
    a: np.ndarray              # (n,)
    iteration: int = 0
    loss_history: list[dict] = field(default_factory=list)
    norm_history: list[NormRecord] = field(default_factory=list)
    coeff_history: list[CoeffRecord] = field(default_factory=list)


# ---- Simulation engine (faithful port of simulation.js) ---------------------

class Simulation:
    """Shallow MLP training simulation matching the JS demo exactly."""

    def __init__(self, params: SimParams):
        self.params = params
        self.W: np.ndarray | None = None
        self.a: np.ndarray | None = None
        self.iteration = 0
        self.loss_history: list[dict[str, float]] = []
        self.norm_history: list[NormRecord] = []
        self.coeff_history: list[CoeffRecord] = []
        self.rng = np.random.default_rng(params.seed)

        # Parse custom expression once if needed
        self._custom_fn = None
        if params.target_type == "custom" and params.custom_expr:
            self._custom_fn = parse_custom_expr_single(params.custom_expr)

        self._initialize()

    def _initialize(self) -> None:
        p = self.params
        self.W = self.rng.standard_normal((p.n, p.d)) * p.alpha
        self.a = np.zeros(p.n)
        self.iteration = 0
        self.loss_history = []
        self.norm_history = []
        self.coeff_history = []
        self._record_norms()

    def step(self) -> float:
        """Run one SGD step. Returns the batch loss."""
        p = self.params
        sigma, dsigma = ACTIVATIONS[p.activation]
        sqrt_d = math.sqrt(p.d)
        n_coeff = num_coeff_terms(p.target_type, p.num_terms)

        # Accumulators
        dW = np.zeros_like(self.W)
        da = np.zeros_like(self.a)
        total_loss = 0.0

        # For coefficient projection
        v = np.zeros(n_coeff)        # v = Q^T f_hat
        G = np.zeros((n_coeff, n_coeff))  # G = Q^T Q
        f_hat_sq_sum = 0.0

        for b in range(p.batch_size):
            # Sample x ~ N(0, I_d)
            x = self.rng.standard_normal(p.d)

            # Target
            y_target, f_terms = compute_target(x, p.target_type, p.num_terms, self._custom_fn)

            # Forward: z_i = W[i,:] . x / sqrt(d), h_i = sigma(z_i)
            z = self.W @ x / sqrt_d       # (n,)
            h = sigma(z)                    # (n,)
            y_pred = float(np.dot(self.a, h) / p.n)

            err = y_pred - y_target
            total_loss += 0.5 * err * err

            # Coefficient accumulation
            for j in range(n_coeff):
                v[j] += y_pred * f_terms[j]
                for k in range(n_coeff):
                    G[j, k] += f_terms[j] * f_terms[k]
            f_hat_sq_sum += y_pred * y_pred

            # Gradients
            d_out = err / p.batch_size
            da += d_out * h / p.n
            coeff_vec = d_out * (self.a / p.n) * dsigma(z) / sqrt_d  # (n,)
            dW += np.outer(coeff_vec, x)

        total_loss /= p.batch_size

        # Solve G * c_ls = v for least-squares coefficients
        try:
            c_ls = np.linalg.solve(G, v)
        except np.linalg.LinAlgError:
            c_ls = np.zeros(n_coeff)

        # Reported coefficients: E[f_hat * f*_k]
        c = v / p.batch_size

        # Remainder: ||f_hat||^2 - ||proj||^2
        proj_sq = float(np.dot(c_ls, v))
        rem_sq = max(0.0, f_hat_sq_sum - proj_sq) / p.batch_size

        # muP SGD update: multiply by n
        self.a -= p.eta * p.n * da
        self.W -= p.eta * p.n * dW

        self.iteration += 1
        self.loss_history.append({"step": self.iteration, "loss": total_loss})
        self.coeff_history.append(CoeffRecord(
            step=self.iteration,
            coeffs=c.tolist(),
            remainder=math.sqrt(rem_sq),
        ))
        self._record_norms()
        return total_loss

    def _record_norms(self) -> None:
        p = self.params
        from .targets import num_input_coords
        n_coords = num_input_coords(p.target_type, p.num_terms) or p.d

        w_sq = float(np.sum(self.W ** 2))
        a_sq = float(np.sum(self.a ** 2))

        # Per-direction column norms
        w_dir = []
        for k in range(min(n_coords, p.d)):
            w_dir.append(float(np.linalg.norm(self.W[:, k])))
        # "rest" norm
        if n_coords < p.d:
            rest_sq = float(np.sum(self.W[:, n_coords:] ** 2))
            w_dir.append(math.sqrt(rest_sq))

        h_rms = math.sqrt(w_sq / (p.n * p.d))

        self.norm_history.append(NormRecord(
            step=self.iteration,
            w_frob=math.sqrt(w_sq),
            a_norm=math.sqrt(a_sq),
            w_dir=w_dir,
            h_rms=h_rms,
        ))

    def run(self, steps: int, log_interval: int = 100, verbose: bool = True,
            snapshot_interval: int | None = None) -> None:
        """Run multiple SGD steps.

        If snapshot_interval is set, saves (W, a) copies at that interval
        into self.snapshots for time-evolution plots.
        """
        if snapshot_interval is None:
            snapshot_interval = max(1, steps // 8)

        # Always snapshot initial state
        self.snapshots: list[tuple[int, np.ndarray, np.ndarray]] = [
            (self.iteration, self.W.copy(), self.a.copy())
        ]

        t0 = time.time()
        for i in range(steps):
            loss = self.step()
            if (i + 1) % snapshot_interval == 0:
                self.snapshots.append(
                    (self.iteration, self.W.copy(), self.a.copy())
                )
            if verbose and (i + 1) % log_interval == 0:
                elapsed = time.time() - t0
                sps = (i + 1) / max(elapsed, 1e-6)
                print(f"  step {self.iteration:>7d}  loss={loss:.6f}  "
                      f"({sps:.0f} steps/s)")

        # Ensure final state is captured
        if self.snapshots[-1][0] != self.iteration:
            self.snapshots.append(
                (self.iteration, self.W.copy(), self.a.copy())
            )

    def get_state(self) -> SimState:
        return SimState(
            params=self.params,
            W=self.W.copy(),
            a=self.a.copy(),
            iteration=self.iteration,
            loss_history=list(self.loss_history),
            norm_history=list(self.norm_history),
            coeff_history=list(self.coeff_history),
        )

    def evaluate_on_grid(self, n_points: int = 200) -> dict[str, Any]:
        """Evaluate learned function on a grid (for plotting)."""
        p = self.params
        sigma, _ = ACTIVATIONS[p.activation]
        sqrt_d = math.sqrt(p.d)

        # 1D slice along x[0], other dims = 0
        grid = np.zeros((n_points, p.d))
        grid[:, 0] = np.linspace(-3, 3, n_points)

        # Target values
        y_target = np.array([
            compute_target(grid[i], p.target_type, p.num_terms, self._custom_fn)[0]
            for i in range(n_points)
        ])

        # Forward pass
        z = grid @ self.W.T / sqrt_d  # (n_points, n)
        h = sigma(z)                   # (n_points, n)
        y_pred = (h @ self.a) / p.n    # (n_points,)

        # Per-neuron contributions
        contributions = h * (self.a / p.n)  # (n_points, n)

        return {
            "grid_x": grid[:, 0].tolist(),
            "target": y_target.tolist(),
            "learned": y_pred.tolist(),
            "neuron_contributions": contributions.tolist(),
        }

    def to_json(self) -> dict[str, Any]:
        """Serialize full state for output."""
        grid_data = self.evaluate_on_grid()
        return {
            "params": self.params.to_dict(),
            "iteration": self.iteration,
            "loss_history": self.loss_history,
            "coeff_history": [
                {"step": c.step, "coeffs": c.coeffs, "remainder": c.remainder}
                for c in self.coeff_history
            ],
            "norm_history": [
                {"step": n.step, "w_frob": n.w_frob, "a_norm": n.a_norm,
                 "w_dir": n.w_dir, "h_rms": n.h_rms}
                for n in self.norm_history
            ],
            "grid": grid_data,
            "weights": {
                "W": self.W.tolist(),
                "a": self.a.tolist(),
            },
        }
