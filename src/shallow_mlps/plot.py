"""Matplotlib plotting utilities for shallow MLP experiments."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np

from .train import TrainResult, SweepResult


def plot_neuron_contributions(
    result: TrainResult,
    ax: plt.Axes | None = None,
    title: str | None = None,
) -> plt.Figure:
    """Plot individual neuron contributions as colored lines.

    Shows each neuron's contribution, the aggregate learned function,
    and the target function.
    """
    if result.input_dim == 2:
        return _plot_neuron_contributions_2d(result, ax, title)
    # For d>2 we use a 1D slice along x[0], same plotting as d=1

    created_fig = ax is None
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(8, 5))
    else:
        fig = ax.figure

    grid = result.grid[:, 0]
    width = result.neuron_contributions.shape[1]
    colors = cm.tab20(np.linspace(0, 1, max(width, 1)))

    for i in range(width):
        contrib = result.neuron_contributions[:, i]
        ax.plot(grid, contrib, color=colors[i % len(colors)], alpha=0.6, linewidth=1)

    ax.plot(grid, result.learned_fn, "k-", linewidth=2, label="Learned")
    ax.plot(grid, result.target_fn_values, "k--", linewidth=2, label="Target")

    ax.set_xlabel("x")
    ax.set_ylabel("y")
    if title:
        ax.set_title(title)
    else:
        ax.set_title(f"width={result.width}, lr={result.lr}, seed={result.seed}")
    ax.legend(loc="upper right", fontsize=8)

    if created_fig:
        fig.tight_layout()
    return fig


def _plot_neuron_contributions_2d(
    result: TrainResult,
    ax: plt.Axes | None = None,
    title: str | None = None,
) -> plt.Figure:
    """Heatmap visualization for 2D input functions."""
    created_fig = ax is None
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(6, 5))
    else:
        fig = ax.figure

    grid = result.grid
    side = int(np.sqrt(len(grid)))
    learned = result.learned_fn.reshape(side, side)

    x1 = grid[:side**2, 0].reshape(side, side)
    x2 = grid[:side**2, 1].reshape(side, side)

    im = ax.pcolormesh(x1, x2, learned, shading="auto", cmap="viridis")
    fig.colorbar(im, ax=ax)
    if title:
        ax.set_title(title)
    else:
        ax.set_title(f"width={result.width}, seed={result.seed}")
    ax.set_xlabel("x[1]")
    ax.set_ylabel("x[2]")

    if created_fig:
        fig.tight_layout()
    return fig


def plot_sweep(sweep: SweepResult, output_dir: str | Path) -> list[Path]:
    """Generate neuron-contribution plots for each parameter value in a sweep.

    Returns list of saved PNG paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    saved = []

    param_values = sweep.param_values
    n_cols = min(4, len(param_values))
    n_rows = (len(param_values) + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows))
    if n_rows == 1 and n_cols == 1:
        axes = np.array([[axes]])
    elif n_rows == 1:
        axes = axes.reshape(1, -1)
    elif n_cols == 1:
        axes = axes.reshape(-1, 1)

    for idx, pval in enumerate(param_values):
        row, col = divmod(idx, n_cols)
        ax = axes[row, col]
        # Use first seed as representative
        result = list(sweep.results[str(pval)].values())[0]
        plot_neuron_contributions(
            result, ax=ax,
            title=f"{sweep.sweep_param}={pval}",
        )

    # Hide unused axes
    for idx in range(len(param_values), n_rows * n_cols):
        row, col = divmod(idx, n_cols)
        axes[row, col].set_visible(False)

    fig.suptitle(f"Sweep over {sweep.sweep_param}", fontsize=14)
    fig.tight_layout()
    path = output_dir / "sweep_grid.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    saved.append(path)

    # Individual plots per parameter value
    for pval in param_values:
        result = list(sweep.results[str(pval)].values())[0]
        fig = plot_neuron_contributions(
            result, title=f"{sweep.sweep_param}={pval}"
        )
        path = output_dir / f"neurons_{sweep.sweep_param}_{pval}.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved.append(path)

    return saved


def plot_loss_curves(sweep: SweepResult, output_dir: str | Path) -> Path:
    """Plot loss curves across the sweep."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(1, 1, figsize=(10, 6))
    colors = cm.viridis(np.linspace(0, 1, len(sweep.param_values)))

    for idx, pval in enumerate(sweep.param_values):
        result = list(sweep.results[str(pval)].values())[0]
        ax.plot(
            result.loss_curve,
            color=colors[idx],
            label=f"{sweep.sweep_param}={pval}",
            alpha=0.8,
        )

    ax.set_xlabel("Training step (sampled)")
    ax.set_ylabel("MSE Loss")
    ax.set_title(f"Loss curves across {sweep.sweep_param} sweep")
    ax.set_yscale("log")
    ax.legend(fontsize=8)
    fig.tight_layout()

    path = output_dir / "loss_curves.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
