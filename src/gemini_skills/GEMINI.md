IMPORTANT INSTRUCTIONS:
* Be very thorough! You will frequently need to run 10+ experiments to perform a single topic exploration or falsification. I expect that you'll be working many hours on each step of this task. Don't stop after the first successful experiment - keep going until you've explored ALL reasonable ideas.
* Theory writeups are expected to be several pages in length, and include figures, plots, and detailed mathematical proofs.
* Whenever a skill mentions `${CLAUDE_SKILL_DIR}`, that is a placeholder for that skill's directory, i.e. `.gemini/skills/<SKILL_NAME>`
* ALWAYS use the `scientist` subagent type instead of generalist for spawning subagents. If the scientist agent type is not available, stop and tell the user that they need to install it.

If you find that the `uv` command is not installed:
1. First, check if it might already be installed in `.tmp/bin/uv`.
2. If not, install it using `export UV_UNMANAGED_INSTALL=.tmp/bin && curl -LsSf https://astral.sh/uv/install.sh | sh`. The uv binary will then be available in `.tmp/bin/uv`.