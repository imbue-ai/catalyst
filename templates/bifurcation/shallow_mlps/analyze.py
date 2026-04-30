"""Programmatic bifurcation detection heuristics."""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import numpy as np

from .train import SweepResult, TrainResult


@dataclasses.dataclass
class BifurcationReport:
    """Report from bifurcation detection analysis."""
    bifurcation_points: list[dict[str, Any]]
    overall_detected: bool
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "bifurcation_points": self.bifurcation_points,
            "overall_detected": self.overall_detected,
            "summary": self.summary,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


def _flatten_weights(result: TrainResult) -> np.ndarray:
    """Flatten all model weights into a single vector."""
    parts = []
    for name, vals in result.weights.items():
        parts.append(np.array(vals).ravel())
    return np.concatenate(parts)


def _weight_discontinuity(sweep: SweepResult) -> BifurcationReport:
    """Detect bifurcation via sudden jumps in weight-space distance."""
    param_values = sweep.param_values
    if len(param_values) < 3:
        return BifurcationReport([], False, "Too few parameter values for detection.")

    # Use neuron contribution patterns (same grid size) instead of raw weights
    # (weights have different sizes when sweeping width).
    contribution_signatures = []
    for pval in param_values:
        seed_results = sweep.results[str(pval)]
        # Average the learned function and contribution norms across seeds
        sigs = []
        for r in seed_results.values():
            # Use sorted neuron contribution norms as a fixed-length signature
            norms = np.linalg.norm(r.neuron_contributions, axis=0)
            sorted_norms = np.sort(norms)[::-1]
            # Pad/truncate to fixed length for comparison
            fixed_len = 64
            if len(sorted_norms) < fixed_len:
                sorted_norms = np.pad(sorted_norms, (0, fixed_len - len(sorted_norms)))
            else:
                sorted_norms = sorted_norms[:fixed_len]
            # Also include the learned function as part of signature
            sig = np.concatenate([sorted_norms, r.learned_fn[:100]])
            sigs.append(sig)
        contribution_signatures.append(np.mean(sigs, axis=0))

    # Compute distances between consecutive parameter values
    distances = []
    for i in range(1, len(contribution_signatures)):
        d = float(np.linalg.norm(contribution_signatures[i] - contribution_signatures[i - 1]))
        distances.append(d)

    distances_arr = np.array(distances)
    if len(distances_arr) == 0:
        return BifurcationReport([], False, "Insufficient data.")

    # Detect outlier jumps (> 2 std above mean, or > 3x median)
    median_d = float(np.median(distances_arr))
    mean_d = float(np.mean(distances_arr))
    std_d = float(np.std(distances_arr))

    bifurcation_points = []
    for i, d in enumerate(distances):
        threshold = max(mean_d + 2 * std_d, 3 * median_d) if std_d > 0 else 2 * median_d
        if d > threshold and d > 0.1:
            confidence = min(1.0, (d - median_d) / (median_d + 1e-8))
            bifurcation_points.append({
                "param_value": param_values[i + 1],
                "prev_param_value": param_values[i],
                "magnitude": d,
                "confidence": round(confidence, 3),
                "description": (
                    f"Weight-space jump of {d:.3f} between "
                    f"{sweep.sweep_param}={param_values[i]} and "
                    f"{sweep.sweep_param}={param_values[i+1]} "
                    f"(median distance: {median_d:.3f})"
                ),
            })

    detected = len(bifurcation_points) > 0
    if detected:
        pts = ", ".join(
            f"{sweep.sweep_param}={bp['param_value']}" for bp in bifurcation_points
        )
        summary = (
            f"Detected {len(bifurcation_points)} bifurcation point(s) at {pts} "
            f"using weight-space discontinuity analysis."
        )
    else:
        summary = (
            "No bifurcation detected. Weight-space distances were relatively "
            f"uniform (median={median_d:.3f}, std={std_d:.3f})."
        )

    return BifurcationReport(bifurcation_points, detected, summary)


def _representation_clustering(sweep: SweepResult) -> BifurcationReport:
    """Detect bifurcation via changes in neuron contribution patterns."""
    param_values = sweep.param_values
    if len(param_values) < 3:
        return BifurcationReport([], False, "Too few parameter values for detection.")

    # For each param value, compute a "representation signature":
    # sort neuron contributions by their L2 norm and look at the structure
    signatures = []
    for pval in param_values:
        seed_results = sweep.results[str(pval)]
        # Use first seed as representative
        result = list(seed_results.values())[0]
        contribs = result.neuron_contributions  # (n_grid, width)
        # Signature: sorted L2 norms of neuron contributions
        norms = np.linalg.norm(contribs, axis=0)
        sorted_norms = np.sort(norms)[::-1]
        # Normalize
        total = np.sum(sorted_norms) + 1e-8
        signatures.append(sorted_norms / total)

    # Pad signatures to same length (widths may differ in sweep)
    max_len = max(len(s) for s in signatures)
    padded = [np.pad(s, (0, max_len - len(s))) for s in signatures]

    # Compute distances between consecutive signatures
    distances = []
    for i in range(1, len(padded)):
        d = float(np.linalg.norm(padded[i] - padded[i - 1]))
        distances.append(d)

    distances_arr = np.array(distances)
    median_d = float(np.median(distances_arr))
    mean_d = float(np.mean(distances_arr))
    std_d = float(np.std(distances_arr))

    bifurcation_points = []
    for i, d in enumerate(distances):
        threshold = max(mean_d + 2 * std_d, 3 * median_d) if std_d > 0 else 2 * median_d
        if d > threshold and d > 0.05:
            confidence = min(1.0, (d - median_d) / (median_d + 1e-8))
            bifurcation_points.append({
                "param_value": param_values[i + 1],
                "prev_param_value": param_values[i],
                "magnitude": round(d, 4),
                "confidence": round(confidence, 3),
                "description": (
                    f"Representation structure change of {d:.4f} between "
                    f"{sweep.sweep_param}={param_values[i]} and "
                    f"{sweep.sweep_param}={param_values[i+1]}"
                ),
            })

    detected = len(bifurcation_points) > 0
    if detected:
        pts = ", ".join(
            f"{sweep.sweep_param}={bp['param_value']}" for bp in bifurcation_points
        )
        summary = f"Detected {len(bifurcation_points)} bifurcation point(s) at {pts} using representation clustering."
    else:
        summary = "No bifurcation detected via representation clustering."

    return BifurcationReport(bifurcation_points, detected, summary)


def _loss_landscape(sweep: SweepResult) -> BifurcationReport:
    """Detect bifurcation via abrupt changes in loss curve character."""
    param_values = sweep.param_values
    if len(param_values) < 3:
        return BifurcationReport([], False, "Too few parameter values for detection.")

    # For each param value, summarize the loss curve
    final_losses = []
    for pval in param_values:
        seed_results = sweep.results[str(pval)]
        avg_loss = np.mean([r.final_loss for r in seed_results.values()])
        final_losses.append(avg_loss)

    final_arr = np.array(final_losses)

    # Look for sudden changes in final loss
    bifurcation_points = []
    for i in range(1, len(final_arr) - 1):
        # Second derivative of loss w.r.t. parameter index
        d2 = abs(final_arr[i + 1] - 2 * final_arr[i] + final_arr[i - 1])
        avg_loss = np.mean(final_arr)
        if d2 > 0.1 * avg_loss and d2 > 0.01:
            bifurcation_points.append({
                "param_value": param_values[i],
                "magnitude": round(float(d2), 4),
                "confidence": round(min(1.0, float(d2 / (avg_loss + 1e-8))), 3),
                "description": (
                    f"Loss landscape inflection at {sweep.sweep_param}={param_values[i]} "
                    f"(second derivative: {d2:.4f})"
                ),
            })

    detected = len(bifurcation_points) > 0
    if detected:
        pts = ", ".join(
            f"{sweep.sweep_param}={bp['param_value']}" for bp in bifurcation_points
        )
        summary = f"Detected {len(bifurcation_points)} bifurcation point(s) at {pts} via loss landscape analysis."
    else:
        summary = "No bifurcation detected via loss landscape analysis."

    return BifurcationReport(bifurcation_points, detected, summary)


_METHODS = {
    "weight_discontinuity": _weight_discontinuity,
    "representation_clustering": _representation_clustering,
    "loss_landscape": _loss_landscape,
}


def detect_bifurcation(
    sweep: SweepResult,
    method: str = "weight_discontinuity",
) -> BifurcationReport:
    """Analyze a parameter sweep for bifurcation events.

    Args:
        sweep: Results from a parameter sweep.
        method: Detection method. One of "weight_discontinuity",
            "representation_clustering", "loss_landscape".
    """
    if method not in _METHODS:
        raise ValueError(f"Unknown method {method!r}. Choose from {list(_METHODS)}")
    return _METHODS[method](sweep)
