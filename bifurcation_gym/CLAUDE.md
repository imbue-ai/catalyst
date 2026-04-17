We're researching the phenomenon of bifurcation in shallow multi level perceptrons (MLPs).
In particular, we're interested in pitchfork bifurcation during training time: When training a shallow multilayer perceptron (MLP) via gradient descent with a very small weight initialization variance ($\alpha \to 0$), the network's weights sometimes exhibit a phenomenon known as **bifurcation**. The weights initially collapse onto a single 1-dimensional line, temporarily plateau in loss, and then suddenly "unzip" or bifurcate into two or more distinct branches to more fully match the target function's features.

* Use `uv run python ...` to run Python commands
* You can use the existing tool in the shallow_mlps folder (`uv run python -m shallow_mlps.cli`) to experiment with shallow MLPs and generate plots of their behavior
