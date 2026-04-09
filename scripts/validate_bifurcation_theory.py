#!/usr/bin/env python3
"""Validate the bifurcation theory predictions.

Key theoretical prediction:
    t_bif ≈ (π / (2η)) · ln(s* / α)

where:
- η = learning rate
- α = init scale
- s* = diagonal saturation norm ≈ O(1), depends on target
- 2/π = transverse Lyapunov exponent (for ReLU + Gaussian input)

This script runs parameter sweeps and compares measured bifurcation times
to the theoretical prediction.
"""

import sys, math, json
import numpy as np
sys.path.insert(0, "/Users/catherinekim/ai-scientist")

from shallow_mlps.simulation import Simulation, SimParams


def run_and_measure(alpha, eta, width=1000, steps=60000, seed=42):
    """Run simulation and extract bifurcation diagnostics."""
    p = SimParams(
        n=width, d=2, alpha=alpha, eta=eta, batch_size=200,
        activation="relu",
        target_type="custom", num_terms=2,
        custom_expr="abs(x[1]) + x[1] + abs(x[2]) + x[2] - 0.2*(abs(x[1]+x[2]) + x[1] + x[2])",
        seed=seed,
    )
    sim = Simulation(p)

    # Diagonal/transverse basis for d=2
    e_plus = np.array([1, 1]) / np.sqrt(2)   # diagonal
    e_minus = np.array([1, -1]) / np.sqrt(2)  # transverse

    record_interval = max(1, steps // 500)
    records = []

    for step in range(steps):
        loss = sim.step()

        if (step + 1) % record_interval == 0:
            W = sim.W  # (n, 2)
            a = sim.a  # (n,)

            # Project weights onto diagonal/transverse
            w_par = W @ e_plus    # (n,) diagonal component
            w_perp = W @ e_minus  # (n,) transverse component

            # Compute statistics
            R_mean = np.mean(np.abs(w_par))          # mean radial magnitude
            R_rms = np.sqrt(np.mean(w_par**2))        # RMS radial
            delta_rms = np.sqrt(np.mean(w_perp**2))   # RMS transverse
            a_mean = np.mean(a)                        # mean second-layer weight
            a_rms = np.sqrt(np.mean(a**2))

            # Transverse "bifurcation ratio"
            bif_ratio = delta_rms / max(R_rms, 1e-20)

            records.append({
                "step": step + 1,
                "loss": loss,
                "R_rms": R_rms,
                "delta_rms": delta_rms,
                "bif_ratio": bif_ratio,
                "a_mean": a_mean,
                "a_rms": a_rms,
            })

    return records


def find_bifurcation_time(records, method="loss_drop"):
    """Find the bifurcation step from diagnostics."""
    if method == "loss_drop":
        # Find the step where loss first drops below 50% of the plateau
        losses = [r["loss"] for r in records]
        plateau = np.percentile(losses[:len(losses)//4], 90)  # early plateau
        threshold = plateau * 0.5
        for r in records:
            if r["loss"] < threshold:
                return r["step"]
        return records[-1]["step"]  # never bifurcated

    elif method == "bif_ratio":
        # Find step where transverse/radial ratio exceeds 0.3
        for r in records:
            if r["bif_ratio"] > 0.3:
                return r["step"]
        return records[-1]["step"]


def theoretical_t_bif(alpha, eta, s_star=1.86):
    """Predicted bifurcation time."""
    C_perp = 2.0 / math.pi  # transverse Lyapunov coefficient
    return math.log(s_star / alpha) / (C_perp * eta)


# ============================================================
# EXPERIMENT 1: Alpha sweep (fixed eta)
# ============================================================
print("=" * 60)
print("EXPERIMENT 1: Alpha sweep (eta=0.002 fixed)")
print("=" * 60)

eta_fixed = 0.002
alphas = [1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8]
results_alpha = []

for alpha in alphas:
    max_steps = int(theoretical_t_bif(alpha, eta_fixed) * 2.5)
    max_steps = max(5000, min(max_steps, 120000))
    print(f"\n  alpha={alpha:.0e}, running {max_steps} steps...", end=" ", flush=True)

    records = run_and_measure(alpha, eta_fixed, steps=max_steps)
    t_bif_loss = find_bifurcation_time(records, "loss_drop")
    t_bif_ratio = find_bifurcation_time(records, "bif_ratio")
    t_pred = theoretical_t_bif(alpha, eta_fixed)
    final_loss = records[-1]["loss"]

    results_alpha.append({
        "alpha": alpha,
        "t_bif_loss": t_bif_loss,
        "t_bif_ratio": t_bif_ratio,
        "t_pred": t_pred,
        "final_loss": final_loss,
    })
    print(f"t_bif(loss)={t_bif_loss}, t_bif(ratio)={t_bif_ratio}, "
          f"t_pred={t_pred:.0f}, final_loss={final_loss:.4f}")

print("\n\nAlpha sweep summary:")
print(f"{'alpha':>10s} {'ln(1/α)':>8s} {'t_bif':>8s} {'t_pred':>8s} {'ratio':>8s}")
for r in results_alpha:
    ln_inv_a = math.log(1/r["alpha"])
    ratio = r["t_bif_loss"] / r["t_pred"] if r["t_pred"] > 0 else float('inf')
    print(f"{r['alpha']:>10.0e} {ln_inv_a:>8.1f} {r['t_bif_loss']:>8d} "
          f"{r['t_pred']:>8.0f} {ratio:>8.2f}")


# ============================================================
# EXPERIMENT 2: Eta sweep (fixed alpha)
# ============================================================
print("\n" + "=" * 60)
print("EXPERIMENT 2: Eta sweep (alpha=1e-6 fixed)")
print("=" * 60)

alpha_fixed = 1e-6
etas = [0.0005, 0.001, 0.002, 0.004, 0.008]
results_eta = []

for eta in etas:
    max_steps = int(theoretical_t_bif(alpha_fixed, eta) * 2.5)
    max_steps = max(5000, min(max_steps, 120000))
    print(f"\n  eta={eta}, running {max_steps} steps...", end=" ", flush=True)

    records = run_and_measure(alpha_fixed, eta, steps=max_steps)
    t_bif_loss = find_bifurcation_time(records, "loss_drop")
    t_bif_ratio = find_bifurcation_time(records, "bif_ratio")
    t_pred = theoretical_t_bif(alpha_fixed, eta)
    final_loss = records[-1]["loss"]

    results_eta.append({
        "eta": eta,
        "t_bif_loss": t_bif_loss,
        "t_bif_ratio": t_bif_ratio,
        "t_pred": t_pred,
        "final_loss": final_loss,
    })
    print(f"t_bif(loss)={t_bif_loss}, t_bif(ratio)={t_bif_ratio}, "
          f"t_pred={t_pred:.0f}, final_loss={final_loss:.4f}")

print("\n\nEta sweep summary:")
print(f"{'eta':>10s} {'1/η':>8s} {'t_bif':>8s} {'t_pred':>8s} {'ratio':>8s}")
for r in results_eta:
    ratio = r["t_bif_loss"] / r["t_pred"] if r["t_pred"] > 0 else float('inf')
    print(f"{r['eta']:>10.4f} {1/r['eta']:>8.0f} {r['t_bif_loss']:>8d} "
          f"{r['t_pred']:>8.0f} {ratio:>8.2f}")


# ============================================================
# EXPERIMENT 3: Width sweep (check n-independence)
# ============================================================
print("\n" + "=" * 60)
print("EXPERIMENT 3: Width sweep (alpha=1e-6, eta=0.002)")
print("=" * 60)

widths = [100, 500, 1000, 5000]
results_n = []

for n in widths:
    max_steps = 30000
    print(f"\n  n={n}, running {max_steps} steps...", end=" ", flush=True)

    records = run_and_measure(alpha_fixed, eta_fixed, width=n, steps=max_steps)
    t_bif_loss = find_bifurcation_time(records, "loss_drop")
    t_bif_ratio = find_bifurcation_time(records, "bif_ratio")
    t_pred = theoretical_t_bif(alpha_fixed, eta_fixed)
    final_loss = records[-1]["loss"]

    results_n.append({
        "n": n,
        "t_bif_loss": t_bif_loss,
        "t_bif_ratio": t_bif_ratio,
        "t_pred": t_pred,
        "final_loss": final_loss,
    })
    print(f"t_bif(loss)={t_bif_loss}, t_bif(ratio)={t_bif_ratio}, "
          f"t_pred={t_pred:.0f}, final_loss={final_loss:.4f}")

print("\n\nWidth sweep summary:")
print(f"{'n':>6s} {'t_bif':>8s} {'t_pred':>8s} {'ratio':>8s}")
for r in results_n:
    ratio = r["t_bif_loss"] / r["t_pred"] if r["t_pred"] > 0 else float('inf')
    print(f"{r['n']:>6d} {r['t_bif_loss']:>8d} {r['t_pred']:>8.0f} {ratio:>8.2f}")


# ============================================================
# EXPERIMENT 4: Seed sweep (check statistical spread)
# ============================================================
print("\n" + "=" * 60)
print("EXPERIMENT 4: Seed sweep (alpha=1e-6, eta=0.002, n=1000)")
print("=" * 60)

seeds = list(range(10))
results_seed = []

for seed in seeds:
    max_steps = 25000
    records = run_and_measure(alpha_fixed, eta_fixed, width=1000, steps=max_steps, seed=seed)
    t_bif_loss = find_bifurcation_time(records, "loss_drop")
    results_seed.append(t_bif_loss)

t_pred = theoretical_t_bif(alpha_fixed, eta_fixed)
mean_t = np.mean(results_seed)
std_t = np.std(results_seed)

print(f"\nSeed sweep: {results_seed}")
print(f"Mean t_bif = {mean_t:.0f} ± {std_t:.0f}")
print(f"Predicted   = {t_pred:.0f}")
print(f"Ratio mean/pred = {mean_t/t_pred:.2f}")


# ============================================================
# EXPERIMENT 5: Transverse Lyapunov exponent measurement
# ============================================================
print("\n" + "=" * 60)
print("EXPERIMENT 5: Measure transverse Lyapunov exponent")
print("=" * 60)

# Run one detailed simulation and fit exponential to delta_rms
records = run_and_measure(1e-6, 0.002, width=1000, steps=25000, seed=42)

# Extract delta_rms in the pre-bifurcation phase
steps_arr = np.array([r["step"] for r in records])
delta_arr = np.array([r["delta_rms"] for r in records])
R_arr = np.array([r["R_rms"] for r in records])
a_arr = np.array([r["a_rms"] for r in records])

# Find pre-bifurcation region: delta growing but bif_ratio < 0.2
pre_bif = [(r["step"], r["delta_rms"]) for r in records
           if r["delta_rms"] > 1e-10 and r["bif_ratio"] < 0.2]

if len(pre_bif) > 10:
    t_vals = np.array([p[0] for p in pre_bif])
    d_vals = np.array([p[1] for p in pre_bif])
    log_d = np.log(d_vals)

    # Linear fit: log(delta) = lambda*t + const
    coeffs = np.polyfit(t_vals, log_d, 1)
    lambda_measured = coeffs[0]
    lambda_predicted = (2/math.pi) * 0.002

    print(f"\nFitted transverse growth: log(δ) = {coeffs[0]:.6f}·t + {coeffs[1]:.2f}")
    print(f"Measured Lyapunov exponent: λ_⊥ = {lambda_measured:.6f} per step")
    print(f"Predicted (2/π)·η = {lambda_predicted:.6f} per step")
    print(f"Ratio measured/predicted = {lambda_measured/lambda_predicted:.3f}")
else:
    print("Not enough pre-bifurcation data for Lyapunov fit")


# Print summary for the a≈R conservation law check
print("\n" + "=" * 60)
print("EXPERIMENT 6: Check a ≈ R conservation law")
print("=" * 60)

for r in records[::len(records)//10]:
    a_over_R = r["a_rms"] / max(r["R_rms"], 1e-20)
    print(f"  step {r['step']:>6d}: a_rms={r['a_rms']:.4f}, R_rms={r['R_rms']:.4f}, "
          f"a/R={a_over_R:.3f}, loss={r['loss']:.4f}")

print("\n\nAll experiments complete.")
