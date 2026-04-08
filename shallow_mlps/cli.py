"""CLI entry point for the shallow-mlps experiment tool."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import targets


def cmd_run(args: argparse.Namespace) -> None:
    """Run the simulation engine (faithful port of the JS demo)."""
    from .simulation import Simulation, SimParams

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    target_type = args.target_type
    custom_expr = args.custom_expr
    if custom_expr and target_type != "custom":
        target_type = "custom"

    params = SimParams(
        n=args.width,
        d=args.input_dim,
        alpha=args.alpha,
        eta=args.lr,
        batch_size=args.batch_size,
        activation=args.activation,
        target_type=target_type,
        num_terms=args.num_terms,
        custom_expr=custom_expr,
        seed=args.seed,
    )

    print(f"Running simulation: {params.target_type} (T={params.num_terms})")
    print(f"  width={params.n}, d={params.d}, alpha={params.alpha}, "
          f"eta={params.eta}, batch={params.batch_size}")
    print(f"  activation={params.activation}, seed={params.seed}")
    print(f"  steps={args.steps}")

    sim = Simulation(params)
    sim.run(args.steps, log_interval=max(1, args.steps // 20), verbose=True,
            snapshot_interval=args.snapshot_interval)

    # Save JSON results
    data = sim.to_json()
    (output_dir / "results.json").write_text(json.dumps(data, indent=2))

    # Generate plots
    plots_dir = output_dir / "plots"
    plots_dir.mkdir(exist_ok=True)
    _plot_simulation(sim, plots_dir)

    summary = (
        f"Simulation complete.\n"
        f"  Target: {params.target_type} (T={params.num_terms})\n"
        f"  Width: {params.n}, d={params.d}, alpha={params.alpha}\n"
        f"  LR: {params.eta}, batch={params.batch_size}, activation={params.activation}\n"
        f"  Steps: {args.steps}, Seed: {params.seed}\n"
        f"  Final loss: {sim.loss_history[-1]['loss']:.6f}\n"
    )
    (output_dir / "summary.txt").write_text(summary)
    print(summary)
    print(f"Output written to {output_dir}")


def _scatter_one_frame(ax, W_i, a_i, step_i, p, vmax_a, wlims, plt, np):
    """Draw a single scatterplot frame onto ax.

    For d>=2: plots W[:,0] vs W[:,1] (first two weight directions per neuron),
    colored by readout weight a_i.
    For d==1: plots W[:,0] vs a_i since there's only one weight direction.
    """
    if p.d >= 2:
        sc = ax.scatter(
            W_i[:, 0], W_i[:, 1],
            c=a_i, cmap="RdBu", edgecolors="k", linewidths=0.3,
            s=20, alpha=0.7, vmin=-vmax_a, vmax=vmax_a,
        )
        ax.set_xlim(-wlims[0], wlims[0])
        ax.set_ylim(-wlims[1], wlims[1])
        ax.set_aspect("equal")
        ax.set_xlabel("$W_{:,1}$")
        ax.set_ylabel("$W_{:,2}$")
    else:
        sc = ax.scatter(
            W_i[:, 0], a_i,
            c=a_i, cmap="RdBu", edgecolors="k", linewidths=0.3,
            s=20, alpha=0.7, vmin=-vmax_a, vmax=vmax_a,
        )
        ax.set_xlim(-wlims[0], wlims[0])
        ax.set_ylim(-wlims[1], wlims[1])
        ax.set_xlabel("$w_i$")
        ax.set_ylabel("$a_i$")
    ax.axhline(0, color="gray", linewidth=0.5)
    ax.axvline(0, color="gray", linewidth=0.5)
    ax.set_title(f"step {step_i}")
    return sc


def _compute_scatter_limits(snapshots, p, np):
    """Compute shared axis/color limits across all snapshots.

    Returns (vmax_a, wlims) where wlims = (xlim, ylim) are symmetric
    bounds for the scatter axes, fixed across all frames so the
    bifurcation is visible as growth rather than rescaling.
    """
    all_a = np.concatenate([s[2] for s in snapshots])
    vmax_a = float(np.max(np.abs(all_a))) or 1.0
    all_w0 = np.concatenate([s[1][:, 0] for s in snapshots])
    xlim = max(abs(all_w0.min()), abs(all_w0.max())) * 1.1 or 1.0
    if p.d >= 2:
        all_w1 = np.concatenate([s[1][:, 1] for s in snapshots])
        ylim = max(abs(all_w1.min()), abs(all_w1.max())) * 1.1 or 1.0
    else:
        # d==1: y-axis shows a_i
        ylim = vmax_a * 1.1 or 1.0
    return vmax_a, (xlim, ylim)


def _plot_scatter_frames(sim, snapshots, plots_dir, plt, np):
    """Save individual PNG per snapshot + stitch into video."""
    p = sim.params
    vmax_a, wlims = _compute_scatter_limits(snapshots, p, np)

    frames_dir = plots_dir / "frames"
    frames_dir.mkdir(exist_ok=True)

    frame_paths = []
    for idx, (step_i, W_i, a_i) in enumerate(snapshots):
        fig, ax = plt.subplots(figsize=(6, 6))
        sc = _scatter_one_frame(ax, W_i, a_i, step_i, p, vmax_a, wlims, plt, np)
        fig.colorbar(sc, ax=ax, label="a_i")
        fig.suptitle(f"Neuron Weights (n={p.n})", fontsize=12)
        fig.tight_layout()
        frame_path = frames_dir / f"frame_{idx:04d}_step{step_i}.png"
        fig.savefig(frame_path, dpi=120)
        plt.close(fig)
        frame_paths.append(frame_path)

    print(f"  {len(frame_paths)} scatter frames saved to {frames_dir}/")

    # Stitch into video
    _stitch_video(frame_paths, plots_dir / "scatterplot.mp4", fps=4)


def _stitch_video(frame_paths, output_path, fps=4):
    """Stitch PNGs into mp4 (ffmpeg) or gif (pillow fallback)."""
    import subprocess
    import shutil

    # Try ffmpeg first
    if shutil.which("ffmpeg"):
        # ffmpeg expects a glob pattern — symlink or use concat
        frames_dir = frame_paths[0].parent
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-framerate", str(fps),
                    "-pattern_type", "glob", "-i", str(frames_dir / "frame_*.png"),
                    "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(output_path),
                ],
                capture_output=True, timeout=30,
            )
            if output_path.exists():
                print(f"  Video saved to {output_path}")
                return
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # Fallback: animated gif via pillow
    try:
        from PIL import Image
        gif_path = output_path.with_suffix(".gif")
        imgs = [Image.open(p) for p in frame_paths]
        imgs[0].save(
            gif_path, save_all=True, append_images=imgs[1:],
            duration=int(1000 / fps), loop=0,
        )
        print(f"  GIF saved to {gif_path}")
    except ImportError:
        print("  (Install Pillow or ffmpeg to generate video/gif)")


def _plot_scatter_grid(sim, snapshots, plots_dir, plt, np):
    """Save the multi-panel grid overview (scatterplot.png)."""
    p = sim.params
    vmax_a, wlims = _compute_scatter_limits(snapshots, p, np)

    n_snaps = len(snapshots)
    n_cols = min(4, n_snaps)
    n_rows = (n_snaps + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 5 * n_rows),
                              squeeze=False)
    for idx, (step_i, W_i, a_i) in enumerate(snapshots):
        row, col = divmod(idx, n_cols)
        _scatter_one_frame(axes[row][col], W_i, a_i, step_i, p, vmax_a, wlims, plt, np)

    for idx in range(n_snaps, n_rows * n_cols):
        row, col = divmod(idx, n_cols)
        axes[row][col].set_visible(False)

    fig.suptitle(f"Neuron Weights Over Time (n={p.n})", fontsize=14)
    fig.tight_layout()
    fig.savefig(plots_dir / "scatterplot.png", dpi=150)
    plt.close(fig)


def _plot_simulation(sim, plots_dir: Path) -> None:
    """Generate PNG plots from a completed simulation."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    import numpy as np

    grid_data = sim.evaluate_on_grid()
    grid_x = np.array(grid_data["grid_x"])
    target_y = np.array(grid_data["target"])
    learned_y = np.array(grid_data["learned"])
    contributions = np.array(grid_data["neuron_contributions"])

    # 1) Function approximation + neuron contributions
    fig, ax = plt.subplots(figsize=(8, 5))
    n_neurons = contributions.shape[1]
    colors = cm.tab20(np.linspace(0, 1, max(n_neurons, 1)))
    for i in range(n_neurons):
        ax.plot(grid_x, contributions[:, i], color=colors[i % len(colors)],
                alpha=0.4, linewidth=0.8)
    ax.plot(grid_x, learned_y, "k-", linewidth=2, label="Learned")
    ax.plot(grid_x, target_y, "k--", linewidth=2, label="Target")
    ax.set_xlabel("x[0]")
    ax.set_ylabel("y")
    p = sim.params
    ax.set_title(f"n={p.n}, d={p.d}, α={p.alpha}, η={p.eta}, "
                 f"{p.activation}, {p.target_type}(T={p.num_terms})")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(plots_dir / "function.png", dpi=150)
    plt.close(fig)

    # 2) Loss curve
    steps = [h["step"] for h in sim.loss_history]
    losses = [h["loss"] for h in sim.loss_history]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(steps, losses)
    ax.set_xlabel("Step")
    ax.set_ylabel("Loss")
    ax.set_title("Training Loss")
    ax.set_yscale("log")
    fig.tight_layout()
    fig.savefig(plots_dir / "loss.png", dpi=150)
    plt.close(fig)

    # 3) Weight norms
    norm_steps = [n.step for n in sim.norm_history]
    w_frob = [n.w_frob for n in sim.norm_history]
    a_norm = [n.a_norm for n in sim.norm_history]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(norm_steps, w_frob, label="||W||_F")
    ax.plot(norm_steps, a_norm, label="||a||")
    ax.set_xlabel("Step")
    ax.set_ylabel("Norm")
    ax.set_title("Weight Norms")
    ax.legend()
    fig.tight_layout()
    fig.savefig(plots_dir / "norms.png", dpi=150)
    plt.close(fig)

    # 4) Per-direction weight norms
    if sim.norm_history and sim.norm_history[0].w_dir:
        n_dirs = len(sim.norm_history[0].w_dir)
        fig, ax = plt.subplots(figsize=(8, 4))
        for k in range(n_dirs):
            label = f"dir {k}" if k < n_dirs - 1 or n_dirs == p.d else "rest"
            vals = [n.w_dir[k] for n in sim.norm_history]
            ax.plot(norm_steps, vals, label=label)
        ax.set_xlabel("Step")
        ax.set_ylabel("Column Norm")
        ax.set_title("Per-direction Weight Norms")
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(plots_dir / "dir_norms.png", dpi=150)
        plt.close(fig)

    # 5) Neuron weight scatterplot — time evolution
    snapshots = getattr(sim, "snapshots", [(sim.iteration, sim.W, sim.a)])
    _plot_scatter_frames(sim, snapshots, plots_dir, plt, np)
    _plot_scatter_grid(sim, snapshots, plots_dir, plt, np)

    # 6) Coefficient evolution
    if sim.coeff_history:
        n_coeffs = len(sim.coeff_history[0].coeffs)
        coeff_steps = [c.step for c in sim.coeff_history]
        fig, ax = plt.subplots(figsize=(8, 4))
        for k in range(n_coeffs):
            vals = [c.coeffs[k] for c in sim.coeff_history]
            ax.plot(coeff_steps, vals, label=f"coeff {k}")
        remainders = [c.remainder for c in sim.coeff_history]
        ax.plot(coeff_steps, remainders, "k--", label="remainder", alpha=0.6)
        ax.set_xlabel("Step")
        ax.set_ylabel("Coefficient")
        ax.set_title("Coefficient Projection onto Target Basis")
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(plots_dir / "coefficients.png", dpi=150)
        plt.close(fig)

    print(f"  Plots saved to {plots_dir}/")


def cmd_train(args: argparse.Namespace) -> None:
    """Run a single MLP training."""
    from . import train, plot
    target_fn = targets.parse_target(args.target, args.input_dim)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = train.train_mlp(
        target_fn=target_fn,
        width=args.width,
        lr=args.lr,
        steps=args.steps,
        input_dim=args.input_dim,
        weight_decay=args.weight_decay,
        seed=args.seed,
    )

    # Write results
    results_path = output_dir / "results.json"
    results_path.write_text(json.dumps(result.to_dict(), indent=2))

    # Write summary
    summary = (
        f"Training complete.\n"
        f"  Target: {args.target}\n"
        f"  Width: {args.width}, LR: {args.lr}, Steps: {args.steps}\n"
        f"  Input dim: {args.input_dim}, Seed: {args.seed}\n"
        f"  Final loss: {result.final_loss:.6f}\n"
    )
    (output_dir / "summary.txt").write_text(summary)
    print(summary)

    # Plot
    plots_dir = output_dir / "plots"
    plots_dir.mkdir(exist_ok=True)
    fig = plot.plot_neuron_contributions(result)
    fig.savefig(plots_dir / "neurons.png", dpi=150)
    import matplotlib.pyplot as plt
    plt.close(fig)
    print(f"Output written to {output_dir}")


def cmd_sweep(args: argparse.Namespace) -> None:
    """Run a parameter sweep."""
    from . import train, plot, analyze
    target_fn = targets.parse_target(args.target, args.input_dim)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse sweep range
    param_values = _parse_sweep_range(args.sweep_range, args.sweep_param)
    seeds = list(range(args.seeds))

    fixed_params = {
        "width": args.width,
        "lr": args.lr,
        "steps": args.steps,
        "input_dim": args.input_dim,
        "weight_decay": args.weight_decay,
    }
    # Remove the swept parameter from fixed params
    fixed_params.pop(args.sweep_param, None)

    print(f"Sweeping {args.sweep_param} over {param_values} ({args.seeds} seeds)")
    result = train.sweep_parameter(
        target_fn=target_fn,
        param_name=args.sweep_param,
        param_values=param_values,
        fixed_params=fixed_params,
        seeds=seeds,
    )

    # Write results
    results_path = output_dir / "results.json"
    results_path.write_text(json.dumps(result.to_dict(), indent=2))

    # Plots
    plots_dir = output_dir / "plots"
    plot.plot_sweep(result, plots_dir)
    plot.plot_loss_curves(result, plots_dir)

    # Bifurcation detection
    report = analyze.detect_bifurcation(result)
    (output_dir / "bifurcation_report.json").write_text(report.to_json())

    # Summary
    summary = (
        f"Sweep complete.\n"
        f"  Target: {args.target}\n"
        f"  Swept: {args.sweep_param} over {param_values}\n"
        f"  Seeds: {args.seeds}, Steps: {args.steps}\n"
        f"  Bifurcation detected: {report.overall_detected}\n"
        f"  {report.summary}\n"
    )
    (output_dir / "summary.txt").write_text(summary)
    print(summary)
    print(f"Output written to {output_dir}")


def cmd_analyze(args: argparse.Namespace) -> None:
    """Run bifurcation detection on saved sweep results."""
    from . import train, analyze
    results_path = Path(args.results_file)
    with open(results_path) as f:
        data = json.load(f)

    # Reconstruct SweepResult from JSON
    sweep = _load_sweep_from_json(data)

    for method in (args.method if args.method != "all" else analyze._METHODS.keys()):
        report = analyze.detect_bifurcation(sweep, method=method)
        print(f"\n--- {method} ---")
        print(report.summary)
        for bp in report.bifurcation_points:
            print(f"  {bp['description']} (confidence: {bp['confidence']})")

        if args.output_dir:
            out = Path(args.output_dir)
            out.mkdir(parents=True, exist_ok=True)
            (out / f"bifurcation_{method}.json").write_text(report.to_json())


def cmd_list_targets(args: argparse.Namespace) -> None:
    """List available preset target functions."""
    print("Available targets:\n")
    print("Demo targets (parameterized by order T):")
    for name in ("staircase", "hermite", "monomial"):
        print(f"  {name}:T    e.g. --target staircase:3")
    print("\nSimple presets:")
    for name, (_, desc) in sorted(targets.PRESET_TARGETS.items()):
        print(f"  {name:12s}  {desc}")
    print("\nCustom expressions also supported, e.g.:")
    print('  --target "abs(x) + sin(2*pi*x)"')
    print('  --target "abs(x[1]) + x[2]"  (for 2D)')


def cmd_interactive(args: argparse.Namespace) -> None:
    """Launch the interactive training gym."""
    from .interactive import launch
    launch()


def _parse_sweep_range(range_str: str, param_name: str) -> list:
    """Parse sweep range string into list of values."""
    parts = [p.strip() for p in range_str.split(",")]
    if param_name == "width":
        return [int(p) for p in parts]
    elif param_name == "lr":
        return [float(p) for p in parts]
    elif param_name == "steps":
        return [int(p) for p in parts]
    else:
        # Try int first, then float
        try:
            return [int(p) for p in parts]
        except ValueError:
            return [float(p) for p in parts]


def _load_sweep_from_json(data: dict) -> train.SweepResult:
    """Reconstruct a SweepResult from JSON data."""
    import numpy as np
    results = {}
    for pval_str, seed_dict in data["results"].items():
        seed_results = {}
        for seed_str, r in seed_dict.items():
            tr = train.TrainResult(
                width=r["width"],
                lr=r["lr"],
                steps=r["steps"],
                seed=r["seed"],
                final_loss=r["final_loss"],
                loss_curve=r["loss_curve"],
                neuron_contributions=np.array(r["neuron_contributions"]),
                learned_fn=np.array(r["learned_fn"]),
                target_fn_values=np.array(r["target_fn_values"]),
                grid=np.array(r["grid"]),
                weights=r["weights"],
                input_dim=r["input_dim"],
            )
            seed_results[int(seed_str)] = tr
        results[pval_str] = seed_results

    return train.SweepResult(
        sweep_param=data["sweep_param"],
        param_values=data["param_values"],
        seeds=data["seeds"],
        results=results,
        fixed_params=data["fixed_params"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="shallow-mlps",
        description="Train and analyze shallow ReLU MLPs for bifurcation phenomena.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- run (simulation engine, faithful JS port) --
    p_run = subparsers.add_parser("run", help="Run simulation (faithful port of JS demo)")
    p_run.add_argument("--target-type", default="staircase",
                       choices=["staircase", "hermite", "monomial", "custom"])
    p_run.add_argument("--num-terms", type=int, default=2, help="Order T")
    p_run.add_argument("--width", type=int, default=100, help="Number of neurons n")
    p_run.add_argument("--input-dim", type=int, default=10, help="Input dimension d")
    p_run.add_argument("--alpha", type=float, default=1.0, help="Init scale")
    p_run.add_argument("--lr", type=float, default=0.01, help="Learning rate eta")
    p_run.add_argument("--batch-size", type=int, default=200)
    p_run.add_argument("--activation", default="relu",
                       choices=["relu", "tanh", "gelu", "linear"])
    p_run.add_argument("--custom-expr", default="", help="Custom target expression, e.g. 'abs(x[1]) + x[2]'")
    p_run.add_argument("--steps", type=int, default=1000)
    p_run.add_argument("--snapshot-interval", type=int, default=None,
                       help="Steps between scatterplot snapshots (default: steps/8)")
    p_run.add_argument("--seed", type=int, default=42)
    p_run.add_argument("--output-dir", required=True)
    p_run.set_defaults(func=cmd_run)

    # -- train --
    p_train = subparsers.add_parser("train", help="Train a single MLP (batch mode)")
    p_train.add_argument("--target", required=True, help="Target function (preset name or expression)")
    p_train.add_argument("--width", type=int, default=16)
    p_train.add_argument("--lr", type=float, default=0.01)
    p_train.add_argument("--steps", type=int, default=5000)
    p_train.add_argument("--input-dim", type=int, default=1)
    p_train.add_argument("--weight-decay", type=float, default=0.0)
    p_train.add_argument("--seed", type=int, default=0)
    p_train.add_argument("--output-dir", required=True)
    p_train.set_defaults(func=cmd_train)

    # -- sweep --
    p_sweep = subparsers.add_parser("sweep", help="Run parameter sweep")
    p_sweep.add_argument("--target", required=True)
    p_sweep.add_argument("--sweep-param", required=True, choices=["width", "lr", "steps"])
    p_sweep.add_argument("--sweep-range", required=True, help="Comma-separated values, e.g. 2,4,8,16,32,64")
    p_sweep.add_argument("--seeds", type=int, default=1, help="Number of seed replicates")
    p_sweep.add_argument("--width", type=int, default=16)
    p_sweep.add_argument("--lr", type=float, default=0.01)
    p_sweep.add_argument("--steps", type=int, default=5000)
    p_sweep.add_argument("--input-dim", type=int, default=1)
    p_sweep.add_argument("--weight-decay", type=float, default=0.0)
    p_sweep.add_argument("--output-dir", required=True)
    p_sweep.set_defaults(func=cmd_sweep)

    # -- analyze --
    p_analyze = subparsers.add_parser("analyze", help="Run bifurcation detection on saved results")
    p_analyze.add_argument("results_file", help="Path to results.json from a sweep")
    p_analyze.add_argument("--method", default="all", choices=["all", "weight_discontinuity", "representation_clustering", "loss_landscape"])
    p_analyze.add_argument("--output-dir", default=None)
    p_analyze.set_defaults(func=cmd_analyze)

    # -- list-targets --
    p_list = subparsers.add_parser("list-targets", help="Show available preset target functions")
    p_list.set_defaults(func=cmd_list_targets)

    # -- interactive --
    p_interactive = subparsers.add_parser(
        "interactive",
        help="Launch interactive training gym with live plots",
    )
    p_interactive.set_defaults(func=cmd_interactive)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
