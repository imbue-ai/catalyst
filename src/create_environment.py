import os
import sys
import shutil
import argparse
from pathlib import Path

def copy_resolved_and_no_hidden(src: Path, dst: Path, is_root: bool = False):
    """
    Copies src to dst. Resolves symlinks (replacing them with their contents).
    Skips any files or directories that start with '.' (except at the root level).
    """
    if src.is_symlink():
        src = src.resolve()

    if not src.exists():
        return

    if not is_root and src.name.startswith('.'):
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
        base_dir / "gemini_skills" / "GEMINI.md": "GEMINI.md",
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

    print(f"Environment initialized at {target}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize a per-task environment.")
    parser.add_argument("target_path", help="The destination path for the new environment.")
    parser.add_argument("--template", default=None, help="Optional path to a template folder.")
    
    args = parser.parse_args()
    create_environment(args.target_path, args.template)
