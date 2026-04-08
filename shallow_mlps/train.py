"""Core training module for shallow (two-layer) MLPs.

Supports two parameterizations:
- Standard: f(x) = W2 @ relu(W1 @ x + b1) + b2
- muP (matching jamiesimon.io/shallow-mlps demo):
    f(x) = (1/n) * Σ_i a_i * σ(w_i^T x / √d)
    W ~ N(0, α²), a initialized to zeros
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any, Callable

import numpy as np
import torch
import torch.nn as nn


# --- Activation functions ---

ACTIVATIONS = {
    "relu": torch.relu,
    "tanh": torch.tanh,
    "gelu": nn.functional.gelu,
    "linear": lambda x: x,
}


def get_activation(name: str) -> Callable:
    name = name.lower()
    if name in ACTIVATIONS:
        return ACTIVATIONS[name]
    raise ValueError(f"Unknown activation: {name!r}. Choose from {list(ACTIVATIONS)}")


# --- Models ---

class ShallowMLP(nn.Module):
    """Standard two-layer network: input -> Linear(width) -> ReLU -> Linear(1)."""

    def __init__(self, input_dim: int, width: int, activation: str = "relu"):
        super().__init__()
        self.input_dim = input_dim
        self.width = width
        self.hidden = nn.Linear(input_dim, width)
        self.output = nn.Linear(width, 1)
        self.activation_fn = get_activation(activation)
        self.activation_name = activation

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.output(self.activation_fn(self.hidden(x)))

    def get_neuron_contributions(self, x: torch.Tensor) -> torch.Tensor:
        """Per-neuron output contributions. Shape: (n_points, width)."""
        hidden_out = self.activation_fn(self.hidden(x))
        output_weights = self.output.weight.detach()  # (1, width)
        return hidden_out.detach() * output_weights

    def get_weights_snapshot(self) -> dict[str, list]:
        return {
            name: param.detach().cpu().numpy().tolist()
            for name, param in self.named_parameters()
        }


class ShallowMLP_muP(nn.Module):
    """muP-parameterized shallow MLP matching the demo at jamiesimon.io/shallow-mlps.

    f(x) = (1/n) * Σ_i a_i * σ(w_i^T x / √d)

    - W initialized as N(0, α²)
    - a initialized to zeros (muP convention)
    - SGD with muP width-scaling: Δw = -η·n·∇_w L, Δa = -η·n·∇_a L
    """

    def __init__(
        self,
        input_dim: int,
        width: int,
        alpha: float = 1.0,
        activation: str = "relu",
    ):
        super().__init__()
        self.d = input_dim
        self.n = width
        self.alpha = alpha
        self.activation_fn = get_activation(activation)
        self.activation_name = activation

        # W: (n, d), a: (n,)
        self.W = nn.Parameter(torch.randn(width, input_dim) * alpha)
        self.a = nn.Parameter(torch.zeros(width))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, d)
        # h = W @ x^T / sqrt(d) -> (n, batch)
        h = self.W @ x.T / math.sqrt(self.d)
        activated = self.activation_fn(h)  # (n, batch)
        # f = (1/n) * a^T @ activated -> (batch,)
        out = (self.a @ activated) / self.n
        return out.unsqueeze(1)  # (batch, 1)

    def get_preactivations(self, x: torch.Tensor) -> torch.Tensor:
        """Return h = Wx/√d for each neuron. Shape: (batch, n)."""
        h = self.W @ x.T / math.sqrt(self.d)
        return h.T.detach()

    def get_neuron_contributions(self, x: torch.Tensor) -> torch.Tensor:
        """Per-neuron output contributions (before 1/n averaging). Shape: (batch, n)."""
        h = self.W @ x.T / math.sqrt(self.d)
        activated = self.activation_fn(h)  # (n, batch)
        # contribution_i = a_i * σ(h_i) / n
        contribs = (self.a.unsqueeze(1) * activated / self.n).T  # (batch, n)
        return contribs.detach()

    def get_weights_snapshot(self) -> dict[str, list]:
        return {
            "W": self.W.detach().cpu().numpy().tolist(),
            "a": self.a.detach().cpu().numpy().tolist(),
        }

    def get_weight_norms(self) -> dict[str, float]:
        """Return Frobenius norm of W and L2 norm of a."""
        W_np = self.W.detach().cpu().numpy()
        a_np = self.a.detach().cpu().numpy()
        result = {
            "W_frob": float(np.linalg.norm(W_np)),
            "a_norm": float(np.linalg.norm(a_np)),
        }
        # Per-column norms of W (one per input dimension)
        for k in range(min(self.d, 5)):
            result[f"W_col_{k}"] = float(np.linalg.norm(W_np[:, k]))
        return result


# --- Data classes ---

@dataclasses.dataclass
class TrainResult:
    """Result from training a single MLP instance."""
    width: int
    lr: float
    steps: int
    seed: int
    final_loss: float
    loss_curve: list[float]
    neuron_contributions: np.ndarray
    learned_fn: np.ndarray
    target_fn_values: np.ndarray
    grid: np.ndarray
    weights: dict[str, list]
    input_dim: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "lr": self.lr,
            "steps": self.steps,
            "seed": self.seed,
            "final_loss": self.final_loss,
            "loss_curve": self.loss_curve,
            "neuron_contributions": self.neuron_contributions.tolist(),
            "learned_fn": self.learned_fn.tolist(),
            "target_fn_values": self.target_fn_values.tolist(),
            "grid": self.grid.tolist(),
            "weights": self.weights,
            "input_dim": self.input_dim,
        }


@dataclasses.dataclass
class SweepResult:
    """Result from a parameter sweep across multiple training runs."""
    sweep_param: str
    param_values: list
    seeds: list[int]
    results: dict[str, dict[int, TrainResult]]
    fixed_params: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        results_dict = {}
        for pval, seed_results in self.results.items():
            results_dict[str(pval)] = {
                str(s): r.to_dict() for s, r in seed_results.items()
            }
        return {
            "sweep_param": self.sweep_param,
            "param_values": self.param_values,
            "seeds": self.seeds,
            "results": results_dict,
            "fixed_params": self.fixed_params,
        }


# --- Training functions ---

def train_mlp(
    target_fn: Callable,
    width: int = 16,
    lr: float = 0.01,
    steps: int = 5000,
    input_dim: int = 1,
    weight_decay: float = 0.0,
    seed: int = 0,
    grid_points: int = 200,
) -> TrainResult:
    """Train a single shallow MLP (standard parameterization)."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    model = ShallowMLP(input_dim, width)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    n_train = 500
    if input_dim == 1:
        x_train_np = np.random.uniform(-2, 2, (n_train, 1)).astype(np.float32)
        target_vals = target_fn(x_train_np[:, 0]).astype(np.float32)
    else:
        x_train_np = np.random.uniform(-2, 2, (n_train, input_dim)).astype(np.float32)
        target_vals = target_fn(x_train_np).astype(np.float32)

    x_train = torch.from_numpy(x_train_np)
    y_train = torch.from_numpy(target_vals).unsqueeze(1)

    loss_curve = []
    log_interval = max(1, steps // 100)
    for step in range(steps):
        optimizer.zero_grad()
        pred = model(x_train)
        loss = nn.functional.mse_loss(pred, y_train)
        loss.backward()
        optimizer.step()
        if step % log_interval == 0 or step == steps - 1:
            loss_curve.append(float(loss.item()))

    if input_dim == 1:
        grid_np = np.linspace(-2, 2, grid_points).reshape(-1, 1).astype(np.float32)
        target_grid = target_fn(grid_np[:, 0]).astype(np.float64)
    elif input_dim == 2:
        side = int(np.sqrt(grid_points))
        g1, g2 = np.linspace(-2, 2, side), np.linspace(-2, 2, side)
        g1v, g2v = np.meshgrid(g1, g2)
        grid_np = np.stack([g1v.ravel(), g2v.ravel()], axis=1).astype(np.float32)
        target_grid = target_fn(grid_np).astype(np.float64)
    else:
        # For d>2: 1D slice along x[0], other dims zero (visualizable)
        grid_np = np.zeros((grid_points, input_dim), dtype=np.float32)
        grid_np[:, 0] = np.linspace(-2, 2, grid_points)
        target_grid = target_fn(grid_np).astype(np.float64)

    grid_tensor = torch.from_numpy(grid_np)
    with torch.no_grad():
        contributions = model.get_neuron_contributions(grid_tensor).cpu().numpy()
        learned = model(grid_tensor).squeeze(1).cpu().numpy()

    return TrainResult(
        width=width, lr=lr, steps=steps, seed=seed,
        final_loss=float(loss.item()), loss_curve=loss_curve,
        neuron_contributions=contributions,
        learned_fn=learned.astype(np.float64),
        target_fn_values=target_grid,
        grid=grid_np.astype(np.float64),
        weights=model.get_weights_snapshot(),
        input_dim=input_dim,
    )


def sweep_parameter(
    target_fn: Callable,
    param_name: str,
    param_values: list,
    fixed_params: dict[str, Any] | None = None,
    seeds: list[int] | None = None,
) -> SweepResult:
    """Train MLPs across a parameter sweep."""
    if fixed_params is None:
        fixed_params = {}
    if seeds is None:
        seeds = [0]

    defaults = {"width": 16, "lr": 0.01, "steps": 5000, "input_dim": 1, "weight_decay": 0.0}
    defaults.update(fixed_params)

    results: dict[str, dict[int, TrainResult]] = {}
    for pval in param_values:
        seed_results: dict[int, TrainResult] = {}
        for s in seeds:
            params = {**defaults, param_name: pval, "seed": s}
            result = train_mlp(target_fn=target_fn, **params)
            seed_results[s] = result
        results[str(pval)] = seed_results

    return SweepResult(
        sweep_param=param_name,
        param_values=param_values,
        seeds=seeds,
        results=results,
        fixed_params={k: v for k, v in defaults.items() if k != param_name},
    )
