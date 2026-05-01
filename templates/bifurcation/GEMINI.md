We're researching the phenomenon of bifurcation in shallow multi level perceptrons (MLPs).
In particular, we're interested in pitchfork bifurcation during training time: When training a shallow multilayer perceptron (MLP) via gradient descent with a very small weight initialization variance ($\alpha \to 0$), the network's weights sometimes exhibit a phenomenon known as **bifurcation**. The weights initially collapse onto a single 1-dimensional line, temporarily plateau in loss, and then suddenly "unzip" or bifurcate into two or more distinct branches to more fully match the target function's features.

* Use `uv run python ...` to run Python commands
* You can use the existing tool in the `shallow_mlps` folder to experiment with shallow MLPs and generate plots of their behavior. Make sure to follow the instructions in the run-experiments skill instead of running the script directly.
* The paradigm your research is in is called "Learning mechanics". At the beginning of any exploration or theory writing task, please review the file `there_will_be_a_scientific_theory_of_deep_learning.pdf` in your workspace to understand the overarching goal behind your research, and to grasp the spirit and style in which it should be presented.

We know that the following custom function works well for illustrating the phenomenon: 'x[1] + x[2] + abs(x[1]) + abs(x[2]) - 0.2 * abs(x[1] + x[2])'
As can be seen in the `scatterplot.gif` / `scatterplot.png` resulting from:
```bash
uv run python -m shallow_mlps.cli run --target-type custom --width 100 --input-dim 2 --alpha 0.000001 --lr 0.04 --activation relu --steps 1000 --custom-expr 'x[1] + x[2] + abs(x[1]) + abs(x[2]) - 0.2 * abs(x[1] + x[2])' --output-dir <...>
```
(Do not run this command directly - use run_experiment.py as described in the run-experiments skill.)

IMPORTANT INSTRUCTIONS:
* Be very thorough! You will frequently need to run 10+ experiments to perform a single topic exploration or falsification. I expect that you'll be working many hours on each step of this task. Don't stop after the first successful experiment - keep going until you've explored ALL reasonable ideas.
* Theory writeups are expected to be many pages in length, and include figures, plots, and detailed mathematical proofs.
* Whenever a skill mentions `${CLAUDE_SKILL_DIR}`, that is a placeholder for that skill's directory, i.e. `.gemini/skills/<SKILL_NAME>`.
* ALWAYS use the `scientist` subagent type instead of generalist for spawning subagents.
