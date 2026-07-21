import argparse
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import matplotlib.colors as colors
import math
import random

# Parse command line arguments
parser = argparse.ArgumentParser(
    description="Plot a theory evolution & lineage graph from a CSV file."
)
parser.add_argument(
    "csv_file", help="Path to the CSV file containing theory lineage data."
)
parser.add_argument(
    "-o",
    "--output",
    default="theory_evolution_graph_optimized.png",
    help="Path to save the output graph image.",
)
parser.add_argument(
    "--title",
    default="Theory Evolution Graph",
    help="Title for the top of the graph.",
)
args = parser.parse_args()

# Read the data
df = pd.read_csv(args.csv_file)

G = nx.DiGraph()
nodes_by_iter = {}
for idx, row in df.iterrows():
    node = row["Theory"]
    it = row["Iteration"]
    G.add_node(node)
    nodes_by_iter.setdefault(it, []).append(node)
    inputs = row["Inputs"]
    if not pd.isna(inputs) and inputs != "":
        input_list = [t.strip() for t in inputs.split(",") if t.strip()]
        for inp in input_list:
            G.add_edge(inp, node, generator=row["Generator"])


def get_total_length(G, pos_mapping):
    total = 0.0
    for u, v in G.edges():
        x1, y1 = pos_mapping[u]
        x2, y2 = pos_mapping[v]
        total += math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
    return total


def build_pos(nodes_by_iter_ordered):
    pos_mapping = {}
    for it, nodes in nodes_by_iter_ordered.items():
        n = len(nodes)
        dy_offset = 0.3 * (it % 3 - 1)
        for i, node in enumerate(nodes):
            y = (i - (n - 1) / 2.0) if n > 1 else 0.0
            pos_mapping[node] = (it, y + dy_offset)
    return pos_mapping


# Calculate initial layout
best_order = {it: list(nodes) for it, nodes in nodes_by_iter.items()}
pos = build_pos(best_order)
best_length = get_total_length(G, pos)

# Run a multi-start greedy local search optimization to minimize edge lengths
num_starts = 50
for start in range(num_starts):
    if start == 0:
        order = {it: list(nodes) for it, nodes in nodes_by_iter.items()}
    else:
        order = {it: list(nodes) for it, nodes in nodes_by_iter.items()}
        for it in order:
            random.shuffle(order[it])

    current_pos = build_pos(order)
    length = get_total_length(G, current_pos)

    improved = True
    while improved:
        improved = False
        for it in order:
            nodes = order[it]
            n = len(nodes)
            if n < 2:
                continue
            for i in range(n):
                for j in range(i + 1, n):
                    # Swap nodes and test layout length
                    nodes[i], nodes[j] = nodes[j], nodes[i]
                    test_pos = build_pos(order)
                    test_length = get_total_length(G, test_pos)

                    if test_length < length - 1e-6:
                        length = test_length
                        current_pos = test_pos
                        improved = True
                    else:
                        # Revert swap
                        nodes[i], nodes[j] = nodes[j], nodes[i]

    if length < best_length:
        best_length = length
        best_order = {it: list(nodes) for it, nodes in order.items()}
        pos = current_pos

# Update nodes_by_iter to use the optimized chronological-sorted order
nodes_by_iter = best_order

min_score = df["Final score"].min()
max_score = df["Final score"].max()
norm = colors.Normalize(vmin=min_score, vmax=max_score)
cmap = plt.get_cmap("RdYlGn")

fig = plt.figure(figsize=(14, 9))
ax = fig.add_axes([0.04, 0.08, 0.87, 0.80])

# Draw edges
for u, v, d in G.edges(data=True):
    gen = d["generator"]
    x1, y1 = pos[u]
    x2, y2 = pos[v]

    # Calculate direction and normal vectors for positioning
    dx = x2 - x1
    dy = y2 - y1
    L = math.sqrt(dx**2 + dy**2)
    if L > 0:
        ux = dx / L
        uy = dy / L
    else:
        ux, uy = 1.0, 0.0

    # Normal vector perpendicular to the edge (pointing left/up)
    norm_x = -uy
    norm_y = ux

    mx_straight = (x1 + x2) / 2.0
    my_straight = (y1 + y2) / 2.0

    # Calculate angle for text rotation (making sure text is never upside down)
    angle = math.degrees(math.atan2(dy, dx))
    if angle > 90:
        angle -= 180
    elif angle < -90:
        angle += 180

    shift_L = 1.25 + (L * 0.5)

    if gen == "write-different":
        nx.draw_networkx_edges(
            G,
            pos,
            edgelist=[(u, v)],
            style="dashed",
            edge_color="red",
            width=3.0,  # Increased width proportionally (2.0 -> 3.0)
            arrowstyle="->",
            arrowsize=25,
            connectionstyle="arc3,rad=0.05",
            node_size=1800,
        )  # Increased arrowsize proportionally (20 -> 25)
        # Shift in the same direction as curvature (bends upwards/leftwards, so positive normal)
        shift = -0.05
        mx = mx_straight + shift_L * norm_x * shift
        my = my_straight + shift_L * norm_y * shift
        text_color = "darkred"
    else:
        # Standard transition
        nx.draw_networkx_edges(
            G,
            pos,
            edgelist=[(u, v)],
            style="solid",
            edge_color="darkgray",
            width=5.0,  # Increased width proportionally (3.5 -> 5.0)
            arrowstyle="->",
            arrowsize=28,
            connectionstyle="arc3,rad=-0.05",
            node_size=1800,
        )  # Increased arrowsize proportionally (22 -> 28)
        # Shift in the same direction as curvature (bends downwards/rightwards, so negative normal)
        shift = 0.05
        mx = mx_straight + shift_L * norm_x * shift
        my = my_straight + shift_L * norm_y * shift
        text_color = "blue"

    # Edge Label
    predecessors = list(G.predecessors(v))
    should_label = True
    if len(predecessors) > 1:
        top_u = max(predecessors, key=lambda p: (pos[p][1], p))
        if u != top_u:
            should_label = False

    if should_label:
        plt.text(
            mx,
            my,
            gen,
            color=text_color,
            fontsize=13,
            fontweight="bold",
            horizontalalignment="center",
            verticalalignment="center",
            rotation=angle,
        )

highest_score_idx = df["Final score"].idxmax()

# Draw nodes
for idx, row in df.iterrows():
    node = row["Theory"]
    score = row["Final score"]
    color = cmap(norm(score))
    is_correct = row["Correct idea?"] == "y"

    # 3. Every node is now a circle ('o')
    # Updated node size to 2x (node_size=1800)
    nx.draw_networkx_nodes(
        G,
        pos,
        nodelist=[node],
        node_color=[color],
        node_shape="o",
        node_size=1800,
        edgecolors="black",
        linewidths=1.5,
    )

    # Place a black plus inside if correct idea, and a star inside of the highest-scoring node.
    # Updated plus size proportionally (s=360)
    if idx == highest_score_idx:
        plt.scatter(
            pos[node][0], pos[node][1], marker="*", color="black", s=360, zorder=5
        )
    elif is_correct:
        plt.scatter(
            pos[node][0], pos[node][1], marker="+", color="black", s=360, zorder=5
        )

    # 2. Text boxes detailing the ID/Score are removed completely to keep it clean.

plt.title(args.title, fontsize=16, fontweight="bold", pad=25)
ax = plt.gca()
ax.xaxis.set_visible(True)
ax.set_xticks(list(nodes_by_iter.keys()))
ax.set_xticklabels(
    ["Initial" if i == 0 else f"Iteration {i}" for i in nodes_by_iter.keys()], fontsize=12, fontweight="bold"
)
ax.tick_params(axis="x", which="both", bottom=True, labelbottom=True)
max_iter = max(nodes_by_iter.keys()) if nodes_by_iter else 0
plt.xlim(-0.5, max_iter + 0.5)
plt.ylim(-1.6, 1.6)
plt.grid(True, axis="x", linestyle="--", alpha=0.7)
ax.yaxis.set_visible(False)

# Add color reference (colorbar) for the final score colors of the nodes
sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
sm.set_array([])
cax = fig.add_axes([0.93, 0.20, 0.02, 0.55])
cbar = fig.colorbar(sm, cax=cax, orientation="vertical")
cbar.ax.set_xlabel("Score", fontsize=11, fontweight="bold", labelpad=10)
cbar.ax.tick_params(labelsize=10)

plt.savefig(args.output, dpi=300)
plt.close()

