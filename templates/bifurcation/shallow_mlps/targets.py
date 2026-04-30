"""Target function definitions matching the jamiesimon.io/shallow-mlps demo.

The demo supports: staircase, Hermite, monomial, and custom expressions.
Each target type takes an "order T" parameter controlling complexity.
We also keep simple presets for the batch CLI.

Key functions for the simulation engine:
  compute_target(x, target_type, num_terms) -> (y, f_terms)
  num_coeff_terms(target_type, num_terms) -> int
  num_input_coords(target_type, num_terms) -> int | None
"""

from __future__ import annotations

import math
import numpy as np
from typing import Callable


# ---------------------------------------------------------------------------
# Demo target types (faithful port of targets.js)
# ---------------------------------------------------------------------------


def compute_target(
    x: np.ndarray,
    target_type: str,
    num_terms: int,
    custom_fn: Callable | None = None,
) -> tuple[float, np.ndarray]:
    """Compute target value and basis terms for a single input vector.

    Args:
        x: input vector of shape (d,)
        target_type: one of "staircase", "hermite", "monomial", "custom"
        num_terms: order T
        custom_fn: callable for custom target (takes single x vector, returns float)

    Returns:
        (y_target, f_terms) where f_terms has length num_coeff_terms(target_type, num_terms)
    """
    if target_type == "staircase":
        return _compute_staircase(x, num_terms)
    elif target_type == "hermite":
        return _compute_hermite(x, num_terms)
    elif target_type == "monomial":
        return _compute_monomial(x, num_terms)
    elif target_type == "custom":
        if custom_fn is None:
            raise ValueError("custom target_type requires custom_fn")
        y = float(custom_fn(x))
        return y, np.array([y])
    else:
        raise ValueError(f"Unknown target type: {target_type!r}")


def num_coeff_terms(target_type: str, num_terms: int) -> int:
    """Number of basis functions for coefficient projection."""
    if target_type == "staircase":
        return num_terms  # one term per cumulative product
    elif target_type == "hermite":
        return 1
    elif target_type == "monomial":
        return 1
    elif target_type == "custom":
        return 1
    else:
        return 1


def num_input_coords(target_type: str, num_terms: int) -> int | None:
    """Number of input coordinates the target depends on, or None for all."""
    if target_type == "staircase":
        return num_terms
    elif target_type == "hermite":
        return 1
    elif target_type == "monomial":
        return num_terms
    elif target_type == "custom":
        return None
    else:
        return None


def parse_custom_expr_single(expr: str) -> Callable:
    """Parse a custom expression into a callable that takes a single vector x (shape (d,)).

    Supports x[1], x[2], ... indexing (1-based, matching the demo).
    """

    def fn(x: np.ndarray) -> float:
        class _Indexable:
            def __getitem__(self, idx):
                return float(x[idx - 1])  # 1-based indexing

        namespace = {**_SAFE_NUMPY, "x": _Indexable()}
        return float(eval(expr, {"__builtins__": {}}, namespace))  # noqa: S307

    return fn


# --- Staircase: f* = x1 + x1*x2 + x1*x2*x3 + ... ---
# fTerms[k] = x[0]*x[1]*...*x[k]  (cumulative product)
# y = sum(fTerms)


def _compute_staircase(x: np.ndarray, T: int) -> tuple[float, np.ndarray]:
    f_terms = np.zeros(T)
    prod = 1.0
    for k in range(T):
        if k < len(x):
            prod *= x[k]
        f_terms[k] = prod
    y = float(np.sum(f_terms))
    return y, f_terms


# --- Hermite: f* = He_T(x[0]) / sqrt(T!) ---
# Uses probabilist's Hermite polynomials


def _hermite_polynomial(x: float, n: int) -> float:
    """Probabilist's Hermite polynomial He_n(x) via recurrence."""
    if n == 0:
        return 1.0
    if n == 1:
        return x
    h_prev2 = 1.0
    h_prev1 = x
    for k in range(2, n + 1):
        h_curr = x * h_prev1 - (k - 1) * h_prev2
        h_prev2 = h_prev1
        h_prev1 = h_curr
    return h_prev1


def _compute_hermite(x: np.ndarray, T: int) -> tuple[float, np.ndarray]:
    he_val = _hermite_polynomial(float(x[0]), T)
    y = he_val / math.sqrt(math.factorial(T))
    f_terms = np.array([y])
    return y, f_terms


# --- Monomial: f* = x[0]*x[1]*...*x[T-1] ---


def _compute_monomial(x: np.ndarray, T: int) -> tuple[float, np.ndarray]:
    prod = 1.0
    for k in range(T):
        if k < len(x):
            prod *= x[k]
    y = prod
    f_terms = np.array([y])
    return y, f_terms


# ---------------------------------------------------------------------------
# Batch-mode target functions (for train.py / sweep CLI)
# ---------------------------------------------------------------------------


def staircase(order: int, input_dim: int) -> Callable:
    """Staircase target (batch mode): sum of cumulative products."""

    def fn(x: np.ndarray) -> np.ndarray:
        if x.ndim == 1:
            x = x.reshape(-1, 1)
        result = np.zeros(x.shape[0])
        prod = np.ones(x.shape[0])
        for k in range(min(order, x.shape[1])):
            prod = prod * x[:, k]
            result += prod
        return result

    return fn


def hermite(order: int, input_dim: int) -> Callable:
    """Hermite polynomial target (batch mode): He_T(x1) / sqrt(T!)."""
    norm = math.sqrt(math.factorial(order))

    def fn(x: np.ndarray) -> np.ndarray:
        if x.ndim == 1:
            x = x.reshape(-1, 1)
        vals = np.zeros(x.shape[0])
        for i in range(x.shape[0]):
            vals[i] = _hermite_polynomial(float(x[i, 0]), order)
        return vals / norm

    return fn


def monomial(order: int, input_dim: int) -> Callable:
    """Monomial target (batch mode): product of first T coordinates."""

    def fn(x: np.ndarray) -> np.ndarray:
        if x.ndim == 1:
            x = x.reshape(-1, 1)
        result = np.ones(x.shape[0])
        for k in range(min(order, x.shape[1])):
            result *= x[:, k]
        return result

    return fn


DEMO_TARGET_TYPES: dict[str, Callable] = {
    "staircase": staircase,
    "hermite": hermite,
    "monomial": monomial,
}


def make_demo_target(target_type: str, order: int, input_dim: int) -> Callable:
    """Create a target function matching the demo's parameterized targets."""
    if target_type not in DEMO_TARGET_TYPES:
        raise ValueError(
            f"Unknown target type: {target_type!r}. "
            f"Choose from {list(DEMO_TARGET_TYPES)}"
        )
    return DEMO_TARGET_TYPES[target_type](order, input_dim)


# ---------------------------------------------------------------------------
# Simple presets for batch CLI
# ---------------------------------------------------------------------------


def _abs_target(x: np.ndarray) -> np.ndarray:
    return np.abs(x)


def _step_target(x: np.ndarray) -> np.ndarray:
    return np.where(x >= 0, 1.0, 0.0)


def _sine_target(x: np.ndarray) -> np.ndarray:
    return np.sin(np.pi * x)


def _quadratic_target(x: np.ndarray) -> np.ndarray:
    return x**2


def _sawtooth_target(x: np.ndarray) -> np.ndarray:
    return x - np.floor(x + 0.5)


def _relu_target(x: np.ndarray) -> np.ndarray:
    return np.maximum(x, 0)


def _hat_target(x: np.ndarray) -> np.ndarray:
    return np.maximum(1 - np.abs(x), 0)


PRESET_TARGETS: dict[str, tuple[Callable, str]] = {
    "abs": (_abs_target, "|x| — classic V-shape, known to exhibit bifurcation"),
    "step": (_step_target, "Step function — discontinuous, tests neuron allocation"),
    "sine": (_sine_target, "sin(pi*x) — smooth periodic, interesting width scaling"),
    "quadratic": (_quadratic_target, "x^2 — smooth, typically no bifurcation"),
    "sawtooth": (_sawtooth_target, "Sawtooth wave — piecewise linear"),
    "relu": (_relu_target, "ReLU — half-linear, degenerate case"),
    "hat": (_hat_target, "Hat function — piecewise linear, compact support"),
}


# Safe namespace for custom expression evaluation
_SAFE_NUMPY = {
    "abs": np.abs,
    "sin": np.sin,
    "cos": np.cos,
    "exp": np.exp,
    "log": np.log,
    "sqrt": np.sqrt,
    "pi": np.pi,
    "sign": np.sign,
    "maximum": np.maximum,
    "minimum": np.minimum,
    "where": np.where,
    "floor": np.floor,
    "ceil": np.ceil,
    "clip": np.clip,
}


def parse_target(spec_string: str, input_dim: int = 1) -> Callable:
    """Parse a target function specification.

    Supports:
    - Named presets: "abs", "step", "sine", etc.
    - Demo targets: "staircase:3", "hermite:2", "monomial:1"
    - Custom expressions: "sin(x[1]) + x[2]"
    """
    spec_string = spec_string.strip()

    # Check presets
    if spec_string.lower() in PRESET_TARGETS:
        fn, _ = PRESET_TARGETS[spec_string.lower()]
        return fn

    # Check demo target types (format: "type:order")
    if ":" in spec_string:
        parts = spec_string.split(":", 1)
        if parts[0].lower() in DEMO_TARGET_TYPES:
            return make_demo_target(parts[0].lower(), int(parts[1]), input_dim)

    # Check bare demo target names (default order=1)
    if spec_string.lower() in DEMO_TARGET_TYPES:
        return make_demo_target(spec_string.lower(), 1, input_dim)

    # Custom expression
    expr = spec_string

    if input_dim == 1:

        def target_fn(x: np.ndarray) -> np.ndarray:
            namespace = {**_SAFE_NUMPY}

            class _Indexable:
                def __getitem__(self, idx):
                    if idx == 1:
                        return x
                    raise IndexError(f"1D input only has x[1], got x[{idx}]")

                def __abs__(self):
                    return np.abs(x)

                def __add__(self, other):
                    return x + other

                def __radd__(self, other):
                    return other + x

                def __sub__(self, other):
                    return x - other

                def __rsub__(self, other):
                    return other - x

                def __mul__(self, other):
                    return x * other

                def __rmul__(self, other):
                    return other * x

                def __truediv__(self, other):
                    return x / other

                def __rtruediv__(self, other):
                    return other / x

                def __pow__(self, other):
                    return x**other

                def __neg__(self):
                    return -x

            namespace["x"] = _Indexable()
            result = eval(expr, {"__builtins__": {}}, namespace)  # noqa: S307
            return np.asarray(result, dtype=np.float64)

        return target_fn
    else:

        def target_fn_2d(x: np.ndarray) -> np.ndarray:
            class _Indexable2D:
                def __getitem__(self, idx):
                    if 1 <= idx <= input_dim:
                        return x[:, idx - 1]
                    raise IndexError(f"Input dim {idx} out of range [1, {input_dim}]")

            namespace = {**_SAFE_NUMPY, "x": _Indexable2D()}
            result = eval(expr, {"__builtins__": {}}, namespace)  # noqa: S307
            return np.asarray(result, dtype=np.float64)

        return target_fn_2d
