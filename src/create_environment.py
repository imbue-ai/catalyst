import shutil
import argparse
from pathlib import Path

BASE_GEMINI_MD = """GENERAL INSTRUCTIONS:
* The user might have provided additional guidance in the file `GUIDANCE.txt`. You MUST read this file before you start any work and treat its contents as user instructions.
* Be very thorough! You will frequently need to run 10+ experiments to perform a single topic exploration or falsification. I expect that you'll be working many hours on each step of this task. Don't stop after the first successful experiment - keep going until you've explored ALL reasonable ideas.
* Make sure to consider and rule out ALL plausible alternative explanations before drawing conclusions.
* ALWAYS use the `scientist` subagent type instead of generalist for spawning subagents. If the scientist agent type is not available, stop and tell the user that they need to install it.
  * Exception: IF you are Antigravity, the `scientist` subagent type will not be available. Use the `self` subagent type instead of `scientist`.
* However, ONLY spawn a subagent when the execution steps in a skill explicitly tell you to.
* If you encounter any issues with following the instructions in a skill, or run into issues with your execution environment (e.g. missing permission, error while running a pre-provided script, etc.), please take a second to append a short, one-line issue description to `./tmp/agent_friction_log.txt`.

THEORY.MD INSTRUCTIONS:
* `theory.md` files are the main output of the research process that will be consumed by human researchers.
* Theories should be self-contained, define and/or introduce all necessary concepts, and should be highly polished. They must include figures, plots, and detailed mathematical proofs.
* Assume you're writing a high-quality scientific paper to be published in a leading journal in the field! Use language and rigour appropriate for that audience.
* You might need to perform multiple edits and iterations before your theory.md file is in a good shape.
* Use rigorous, objective language in all theories, reviews and reports. Be extremely precise, using specific objective observations, precise mathematical definitions, and mathematical proofs. NEVER present speculation as fact.
* Completely avoid self-promoting language. Never call your own theories "profound", "elegant", "complete", etc. Use neutral, factual language at all times.


If you find that the `uv` command is not installed:
1. First, check if it might already be installed in `./tmp/bin/uv`.
2. If not, install it using `export UV_UNMANAGED_INSTALL=./tmp/bin && curl -LsSf https://astral.sh/uv/install.sh | sh`. The uv binary will then be available in `./tmp/bin/uv`.

You might encounter a broken Python `.venv`, e.g. with symlinks pointing to non-existent files. If that happens, run `uv venv --clear` to recreate it.
"""

BASE_AGENTS_MD = """GENERAL INSTRUCTIONS:
* The user might have provided additional guidance in the file `GUIDANCE.txt`. You MUST read this file before you start any work and treat its contents as user instructions.
* If you encounter any issues with following the instructions in a skill, or run into issues with your execution environment (e.g. missing permission, error while running a pre-provided script, etc.), please take a second to append a short, one-line issue description to `./tmp/agent_friction_log.txt`.
* ONLY spawn a subagent when the execution steps in a skill explicitly tell you to.
* Always use precise, direct language. NEVER use metaphors to describe an idea, ever.

THEORY.MD INSTRUCTIONS:
* `theory.md` files are the main output of the research process that will be consumed by human researchers.
* Assume you're writing a high-quality scientific paper to be published in a leading journal in the field! Use language and rigour appropriate for that audience.
* Use rigorous, objective language in all theories, reviews and reports. Be extremely precise, using specific objective observations, precise mathematical definitions, and mathematical proofs. NEVER present speculation as fact.
* Completely avoid self-promoting language. Never call your own theories "profound", "elegant", "complete", etc. Use neutral, factual language at all times.
* Avoid *unnecessary* jargon. When you invoke a technical term, it should be for the purpose of adding clarity and/or precision.
"""

BASE_CLAUDE_MD = BASE_AGENTS_MD


def copy_resolved_and_no_hidden(src: Path, dst: Path, is_root: bool = False):
    """
    Copies src to dst. Resolves symlinks (replacing them with their contents).
    Skips any files or directories that start with '.' (except at the root level).
    """
    if src.is_symlink():
        src = src.resolve()

    if not src.exists():
        return

    if not is_root and src.name.startswith("."):
        return

    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            copy_resolved_and_no_hidden(item, dst / item.name)
    else:
        # It's a file
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def create_environment(target_path: str, template_path: str = None):
    target = Path(target_path).resolve()
    target.mkdir(parents=True, exist_ok=True)

    # Create empty tmp folder
    (target / "tmp").mkdir(parents=True, exist_ok=True)

    # 1. Initialize default setup
    base_dir = Path(__file__).parent.resolve()

    default_contents = {
        base_dir / "claude_skills": ".claude",
        base_dir / "gemini_skills": ".gemini",
        base_dir / "gemini_skills" / "skills": ".agents/skills",
        base_dir.parent / "darwinian_evolver": "darwinian_evolver",
        base_dir / "default_environment_pyproject.toml": "pyproject.toml",
    }

    for src_path, dst_name in default_contents.items():
        if not src_path.exists():
            raise FileNotFoundError(f"Required default path not found: {src_path}")

        dst_path = target / dst_name
        if src_path.is_dir():
            copy_resolved_and_no_hidden(src_path, dst_path, is_root=True)
        else:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path.resolve(), dst_path)

    # 2. If template is provided, copy its contents over
    if template_path:
        template = Path(template_path).resolve()
        if template.exists() and template.is_dir():
            for item in template.iterdir():
                copy_resolved_and_no_hidden(item, target / item.name)

    # 3. Append the base Gemini.md, Claude.md, and Agents.md instructions
    for md_filename, base_content in [
        ("GEMINI.md", BASE_GEMINI_MD),
        ("CLAUDE.md", BASE_CLAUDE_MD),
        ("AGENTS.md", BASE_AGENTS_MD),
    ]:
        md_path = target / md_filename
        if md_path.exists():
            with open(md_path, "a") as f:
                f.write("\n\n" + base_content)
        else:
            with open(md_path, "w") as f:
                f.write(base_content)

    # 4. Initialize GUIDANCE.txt
    guidance_path = target / "GUIDANCE.txt"
    with open(guidance_path, "w") as f:
        f.write("")

    print(f"Environment initialized at {target}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize a per-task environment.")
    parser.add_argument(
        "target_path", help="The destination path for the new environment."
    )
    parser.add_argument(
        "--template", default=None, help="Optional path to a template folder."
    )

    args = parser.parse_args()
    create_environment(args.target_path, args.template)
