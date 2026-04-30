We're researching the phenomenon of bifurcation in shallow multi level perceptrons (MLPs).
In particular, we're interested in pitchfork bifurcation during training time: When training a shallow multilayer perceptron (MLP) via gradient descent with a very small weight initialization variance ($\alpha \to 0$), the network's weights sometimes exhibit a phenomenon known as **bifurcation**. The weights initially collapse onto a single 1-dimensional line, temporarily plateau in loss, and then suddenly "unzip" or bifurcate into two or more distinct branches to more fully match the target function's features.

* Use `uv run python ...` to run Python commands
* You can use the existing tool in the shallow_mlps folder (`uv run python -m shallow_mlps.cli`) to experiment with shallow MLPs and generate plots of their behavior

We know that the following custom function works well for illustrating the phenomenon: 'x[1] + x[2] + abs(x[1]) + abs(x[2]) - 0.2 * abs(x[1] + x[2])'
As can be seen in the `scatterplot.gif` / `scatterplot.png` resulting from:
```bash
uv run python -m shallow_mlps.cli run --target-type custom --width 100 --input-dim 2 --alpha 0.000001 --lr 0.04 --activation relu --steps 1000 --custom-expr 'x[1] + x[2] + abs(x[1]) + abs(x[2]) - 0.2 * abs(x[1] + x[2])' --output-dir <...>
```