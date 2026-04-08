"""Interactive Shallow MLP Gym — matplotlib-based live training visualization.

Matches the interactive experience of jamiesimon.io/shallow-mlps:
- Toggle target functions (staircase, Hermite, monomial, presets, custom)
- Adjust hyperparameters via sliders (width, lr, init scale, input dim, batch size)
- Select activation function
- Start/Pause/Reset training
- Watch live-updating plots: loss, neuron contributions, weight scatter, norms
"""

from __future__ import annotations

import math
import time
from typing import Any

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button, RadioButtons, TextBox
import matplotlib.cm as cm
import numpy as np
import torch
import torch.nn as nn

from .train import ShallowMLP_muP, get_activation


class ShallowMLPGym:
    """Interactive training gym with live visualization."""

    def __init__(self):
        # Default parameters (matching demo defaults)
        self.params = {
            "input_dim": 10,
            "width": 100,
            "alpha": 1.0,
            "lr": 0.01,
            "batch_size": 200,
            "activation": "relu",
            "target_type": "staircase",
            "target_order": 1,
            "custom_expr": "",
            "seed": None,
        }

        self.model: ShallowMLP_muP | None = None
        self.running = False
        self.step = 0

        # History for plots
        self.loss_history: list[float] = []
        self.W_norm_history: list[float] = []
        self.a_norm_history: list[float] = []
        self.step_history: list[int] = []

        self._build_ui()
        self._initialize()

    def _build_ui(self) -> None:
        """Create the matplotlib figure with plots and controls."""
        self.fig = plt.figure(figsize=(16, 10))
        self.fig.canvas.manager.set_window_title("Shallow MLP Gym")
        self.fig.set_facecolor("#1a1a2e")

        # --- Plot axes ---
        # Top row: loss curve, neuron scatter
        # Bottom row: function approx (1D) or utility (2D), weight norms
        self.ax_loss = self.fig.add_axes([0.06, 0.58, 0.40, 0.35])
        self.ax_scatter = self.fig.add_axes([0.54, 0.58, 0.40, 0.35])
        self.ax_fn = self.fig.add_axes([0.06, 0.15, 0.40, 0.35])
        self.ax_norms = self.fig.add_axes([0.54, 0.15, 0.40, 0.35])

        for ax in (self.ax_loss, self.ax_scatter, self.ax_fn, self.ax_norms):
            ax.set_facecolor("#16213e")
            ax.tick_params(colors="white", labelsize=8)
            ax.xaxis.label.set_color("white")
            ax.yaxis.label.set_color("white")
            ax.title.set_color("white")
            for spine in ax.spines.values():
                spine.set_color("#333")

        # --- Control panel (bottom strip) ---
        ctrl_y = 0.01
        ctrl_h = 0.025
        slider_color = "#0f3460"
        active_color = "#e94560"

        # Target type radio buttons
        self.ax_target = self.fig.add_axes([0.02, ctrl_y, 0.10, 0.10])
        self.ax_target.set_facecolor("#1a1a2e")
        self.radio_target = RadioButtons(
            self.ax_target,
            ["staircase", "hermite", "monomial", "abs", "step", "sine", "custom"],
            active=0,
            activecolor=active_color,
        )
        for label in self.radio_target.labels:
            label.set_fontsize(7)
            label.set_color("white")
        self.radio_target.on_clicked(self._on_target_change)

        # Sliders
        sl_x = 0.18
        sl_w = 0.25

        self.ax_sl_width = self.fig.add_axes([sl_x, ctrl_y + 0.08, sl_w, ctrl_h])
        self.sl_width = Slider(self.ax_sl_width, "Width n", 2, 500, valinit=100,
                               valstep=1, color=slider_color)
        self.sl_width.label.set_color("white")
        self.sl_width.valtext.set_color("white")
        self.sl_width.on_changed(self._on_param_change)

        self.ax_sl_lr = self.fig.add_axes([sl_x, ctrl_y + 0.05, sl_w, ctrl_h])
        self.sl_lr = Slider(self.ax_sl_lr, "LR η", -5, 1, valinit=-2,
                            color=slider_color)
        self.sl_lr.label.set_color("white")
        self.sl_lr.valtext.set_color("white")
        self.sl_lr.valfmt = "10^%.1f"
        self.sl_lr.on_changed(self._on_param_change)

        self.ax_sl_dim = self.fig.add_axes([sl_x, ctrl_y + 0.02, sl_w, ctrl_h])
        self.sl_dim = Slider(self.ax_sl_dim, "Dim d", 1, 50, valinit=10,
                             valstep=1, color=slider_color)
        self.sl_dim.label.set_color("white")
        self.sl_dim.valtext.set_color("white")
        self.sl_dim.on_changed(self._on_param_change)

        sl_x2 = 0.54
        self.ax_sl_alpha = self.fig.add_axes([sl_x2, ctrl_y + 0.08, sl_w, ctrl_h])
        self.sl_alpha = Slider(self.ax_sl_alpha, "Init α", -6, 0, valinit=0,
                               color=slider_color)
        self.sl_alpha.label.set_color("white")
        self.sl_alpha.valtext.set_color("white")
        self.sl_alpha.valfmt = "10^%.1f"
        self.sl_alpha.on_changed(self._on_param_change)

        self.ax_sl_batch = self.fig.add_axes([sl_x2, ctrl_y + 0.05, sl_w, ctrl_h])
        self.sl_batch = Slider(self.ax_sl_batch, "Batch B", 10, 2000, valinit=200,
                               valstep=10, color=slider_color)
        self.sl_batch.label.set_color("white")
        self.sl_batch.valtext.set_color("white")
        self.sl_batch.on_changed(self._on_param_change)

        self.ax_sl_order = self.fig.add_axes([sl_x2, ctrl_y + 0.02, sl_w, ctrl_h])
        self.sl_order = Slider(self.ax_sl_order, "Order T", 1, 5, valinit=1,
                               valstep=1, color=slider_color)
        self.sl_order.label.set_color("white")
        self.sl_order.valtext.set_color("white")
        self.sl_order.on_changed(self._on_param_change)

        # Buttons
        btn_color = "#0f3460"
        btn_hover = "#e94560"

        self.ax_btn_start = self.fig.add_axes([0.85, ctrl_y + 0.08, 0.06, 0.03])
        self.btn_start = Button(self.ax_btn_start, "Start", color=btn_color,
                                hovercolor=btn_hover)
        self.btn_start.label.set_color("white")
        self.btn_start.on_clicked(self._on_start_pause)

        self.ax_btn_reset = self.fig.add_axes([0.92, ctrl_y + 0.08, 0.06, 0.03])
        self.btn_reset = Button(self.ax_btn_reset, "Reset", color=btn_color,
                                hovercolor=btn_hover)
        self.btn_reset.label.set_color("white")
        self.btn_reset.on_clicked(self._on_reset)

        # Activation radio
        self.ax_activ = self.fig.add_axes([0.85, ctrl_y + 0.00, 0.13, 0.07])
        self.ax_activ.set_facecolor("#1a1a2e")
        self.radio_activ = RadioButtons(
            self.ax_activ, ["relu", "tanh", "gelu", "linear"],
            active=0, activecolor=active_color,
        )
        for label in self.radio_activ.labels:
            label.set_fontsize(7)
            label.set_color("white")
        self.radio_activ.on_clicked(self._on_param_change)

        # Steps/sec display
        self.steps_text = self.fig.text(
            0.85, ctrl_y + 0.12, "step: 0 | 0 steps/s",
            color="#aaa", fontsize=8,
        )

        # Timer for animation
        self.timer = self.fig.canvas.new_timer(interval=30)
        self.timer.add_callback(self._train_step)

    def _get_target_fn(self) -> callable:
        """Build target function from current params."""
        from .targets import make_demo_target, parse_target, PRESET_TARGETS

        tt = self.params["target_type"]
        if tt in ("staircase", "hermite", "monomial"):
            return make_demo_target(tt, self.params["target_order"], self.params["input_dim"])
        elif tt in PRESET_TARGETS:
            fn, _ = PRESET_TARGETS[tt]
            # Wrap 1D presets to work with (batch, d) input
            def wrapped(x: np.ndarray) -> np.ndarray:
                if x.ndim == 2:
                    return fn(x[:, 0])
                return fn(x)
            return wrapped
        elif tt == "custom" and self.params["custom_expr"]:
            return parse_target(self.params["custom_expr"], self.params["input_dim"])
        else:
            return make_demo_target("staircase", 1, self.params["input_dim"])

    def _initialize(self) -> None:
        """Initialize model and clear history."""
        self.step = 0
        self.loss_history.clear()
        self.W_norm_history.clear()
        self.a_norm_history.clear()
        self.step_history.clear()

        if self.params["seed"] is not None:
            torch.manual_seed(self.params["seed"])
            np.random.seed(self.params["seed"])

        self.model = ShallowMLP_muP(
            input_dim=self.params["input_dim"],
            width=self.params["width"],
            alpha=self.params["alpha"],
            activation=self.params["activation"],
        )

        # muP SGD: effective lr = η * n
        effective_lr = self.params["lr"] * self.params["width"]
        self.optimizer = torch.optim.SGD(self.model.parameters(), lr=effective_lr)

        self.target_fn = self._get_target_fn()
        self._update_plots()

    def _train_step(self) -> None:
        """Run a batch of SGD steps and update plots."""
        if not self.running or self.model is None:
            return

        t0 = time.time()
        steps_this_frame = 0

        # Run as many steps as fit in ~25ms (matching demo's time-budget approach)
        while time.time() - t0 < 0.025:
            d = self.params["input_dim"]
            B = self.params["batch_size"]

            # Sample batch: x ~ N(0, I_d)
            x_batch = torch.randn(B, d)
            x_np = x_batch.numpy()
            y_target = self.target_fn(x_np).astype(np.float32)
            y_batch = torch.from_numpy(y_target).unsqueeze(1)

            self.optimizer.zero_grad()
            y_pred = self.model(x_batch)
            loss = 0.5 * nn.functional.mse_loss(y_pred, y_batch)
            loss.backward()
            self.optimizer.step()

            self.step += 1
            steps_this_frame += 1

            # Record every 10 steps
            if self.step % 10 == 0:
                self.loss_history.append(float(loss.item()))
                norms = self.model.get_weight_norms()
                self.W_norm_history.append(norms["W_frob"])
                self.a_norm_history.append(norms["a_norm"])
                self.step_history.append(self.step)

        dt = time.time() - t0
        sps = steps_this_frame / max(dt, 1e-6)
        self.steps_text.set_text(f"step: {self.step:,} | {sps:.0f} steps/s")

        self._update_plots()

    def _update_plots(self) -> None:
        """Redraw all plots with current state."""
        if self.model is None:
            return

        self._plot_loss()
        self._plot_weight_scatter()
        self._plot_function()
        self._plot_norms()

        self.fig.canvas.draw_idle()

    def _plot_loss(self) -> None:
        ax = self.ax_loss
        ax.clear()
        ax.set_facecolor("#16213e")
        ax.set_title("Loss", fontsize=10)
        ax.set_xlabel("step")
        ax.set_ylabel("MSE / 2")

        if self.loss_history:
            ax.semilogy(self.step_history, self.loss_history, color="#e94560", linewidth=1)
        ax.tick_params(colors="white", labelsize=8)
        ax.title.set_color("white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")

    def _plot_weight_scatter(self) -> None:
        """Scatter of neurons in (W[:,0], W[:,1]) space, colored by a_i."""
        ax = self.ax_scatter
        ax.clear()
        ax.set_facecolor("#16213e")
        ax.set_title("Neuron weights (W[:,0] vs W[:,1])", fontsize=10)

        W = self.model.W.detach().cpu().numpy()  # (n, d)
        a = self.model.a.detach().cpu().numpy()   # (n,)

        if W.shape[1] >= 2:
            x_coords, y_coords = W[:, 0], W[:, 1]
        else:
            x_coords = W[:, 0]
            y_coords = np.zeros_like(x_coords)

        # Color by a_i: blue negative, red positive
        a_max = max(np.abs(a).max(), 1e-8)
        colors = cm.RdBu_r((a / a_max + 1) / 2)

        ax.scatter(x_coords, y_coords, c=colors, s=12, alpha=0.7, edgecolors="none")
        ax.axhline(0, color="#333", linewidth=0.5)
        ax.axvline(0, color="#333", linewidth=0.5)
        ax.set_xlabel("W[:,0]")
        ax.set_ylabel("W[:,1]")
        ax.tick_params(colors="white", labelsize=8)
        ax.title.set_color("white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")

    def _plot_function(self) -> None:
        """Plot learned function vs target (1D slice or neuron contributions)."""
        ax = self.ax_fn
        ax.clear()
        ax.set_facecolor("#16213e")

        d = self.params["input_dim"]
        n_pts = 200

        if d <= 2:
            # 1D slice along x[0], all other dims = 0
            grid = np.zeros((n_pts, d), dtype=np.float32)
            grid[:, 0] = np.linspace(-3, 3, n_pts)
            x_plot = grid[:, 0]

            target_vals = self.target_fn(grid)
            x_tensor = torch.from_numpy(grid)

            with torch.no_grad():
                contribs = self.model.get_neuron_contributions(x_tensor).cpu().numpy()
                learned = self.model(x_tensor).squeeze(1).cpu().numpy()

            # Draw individual neuron contributions
            n_neurons = contribs.shape[1]
            colors = cm.tab20(np.linspace(0, 1, max(n_neurons, 1)))
            for i in range(n_neurons):
                ax.plot(x_plot, contribs[:, i], color=colors[i % len(colors)],
                        alpha=0.4, linewidth=0.8)

            ax.plot(x_plot, learned, "w-", linewidth=2, label="Learned")
            ax.plot(x_plot, target_vals, color="#e94560", linewidth=2,
                    linestyle="--", label="Target")
            ax.legend(fontsize=7, loc="upper right",
                      facecolor="#16213e", edgecolor="#333", labelcolor="white")
            ax.set_title("Function (slice along x[0])", fontsize=10)
        else:
            # For high-d: show learned vs target on random test points
            x_test = np.random.randn(200, d).astype(np.float32)
            target_vals = self.target_fn(x_test)
            with torch.no_grad():
                learned = self.model(torch.from_numpy(x_test)).squeeze(1).cpu().numpy()

            ax.scatter(target_vals, learned, s=6, alpha=0.5, color="#e94560")
            lims = [min(target_vals.min(), learned.min()),
                    max(target_vals.max(), learned.max())]
            ax.plot(lims, lims, "w--", linewidth=1, alpha=0.5)
            ax.set_xlabel("Target")
            ax.set_ylabel("Learned")
            ax.set_title("Learned vs Target", fontsize=10)

        ax.tick_params(colors="white", labelsize=8)
        ax.title.set_color("white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")

    def _plot_norms(self) -> None:
        """Plot weight norms over time."""
        ax = self.ax_norms
        ax.clear()
        ax.set_facecolor("#16213e")
        ax.set_title("Weight norms", fontsize=10)

        if self.step_history:
            ax.plot(self.step_history, self.W_norm_history,
                    color="#00d2ff", linewidth=1, label="||W||_F")
            ax.plot(self.step_history, self.a_norm_history,
                    color="#e94560", linewidth=1, label="||a||")
            ax.legend(fontsize=7, loc="upper left",
                      facecolor="#16213e", edgecolor="#333", labelcolor="white")

        ax.set_xlabel("step")
        ax.tick_params(colors="white", labelsize=8)
        ax.title.set_color("white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")

    # --- Callbacks ---

    def _on_start_pause(self, event) -> None:
        self.running = not self.running
        self.btn_start.label.set_text("Pause" if self.running else "Start")
        if self.running:
            self.timer.start()
        else:
            self.timer.stop()
        self.fig.canvas.draw_idle()

    def _on_reset(self, event) -> None:
        self.running = False
        self.btn_start.label.set_text("Start")
        self.timer.stop()
        self._read_params()
        self._initialize()

    def _on_target_change(self, label) -> None:
        self.params["target_type"] = label
        self._on_reset(None)

    def _on_param_change(self, val) -> None:
        # Any parameter change triggers reset (matching demo behavior)
        self._on_reset(None)

    def _read_params(self) -> None:
        """Read current slider/radio values into params dict."""
        self.params["width"] = int(self.sl_width.val)
        self.params["lr"] = 10 ** self.sl_lr.val
        self.params["input_dim"] = int(self.sl_dim.val)
        self.params["alpha"] = 10 ** self.sl_alpha.val
        self.params["batch_size"] = int(self.sl_batch.val)
        self.params["target_order"] = int(self.sl_order.val)
        self.params["activation"] = self.radio_activ.value_selected

    def show(self) -> None:
        """Launch the interactive gym."""
        plt.show()


def launch():
    """Entry point for `shallow-mlps interactive`."""
    gym = ShallowMLPGym()
    gym.show()
