import logging
import re
import shutil
import subprocess
import threading
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class HarnessInfo(BaseModel):
    name: str
    display_name: str
    available: bool
    help_message: Optional[str] = None
    models: List[str]


harnesses_lock = threading.Lock()
harnesses_cache: Dict[str, Dict[str, Any]] = {
    "claude": {
        "name": "claude",
        "display_name": "Claude Code",
        "available": False,
        "help_message": "Checking framework availability...",
        "models": ["opus", "sonnet", "haiku"],
    },
    "gemini": {
        "name": "gemini",
        "display_name": "Gemini CLI",
        "available": False,
        "help_message": "Checking framework availability...",
        "models": ["pro", "flash"],
    },
    "agy": {
        "name": "agy",
        "display_name": "Antigravity CLI",
        "available": False,
        "help_message": "Checking framework availability...",
        "models": [],
    },
}


def parse_version(version_str: str) -> tuple:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_str)
    if match:
        return tuple(int(x) for x in match.groups())
    return (0, 0, 0)


def run_cmd(args: List[str]) -> tuple:
    try:
        res = subprocess.run(args, capture_output=True, text=True, check=False)
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        return -1, "", str(e)


def discover_frameworks_bg():
    global harnesses_cache
    logger.info("[SERVER] Starting agent frameworks discovery in the background...")

    # 1. Check Claude Code
    claude_path = shutil.which("claude")
    if not claude_path:
        claude_available = False
        claude_help = (
            "Claude Code is not installed on the system. "
            "To install, run: `curl -fsSL https://claude.ai/install.sh | bash`"
        )
    else:
        code, stdout, stderr = run_cmd(["claude", "--version"])
        if code != 0:
            claude_available = False
            claude_help = f"Failed to check Claude Code version. Executable found but execution failed: {stderr.strip()}"
        else:
            version_str = stdout.strip()
            version = parse_version(version_str)
            min_version = (2, 1, 0)
            if version < min_version:
                claude_available = False
                claude_help = (
                    f"Installed Claude Code version {version_str.split()[0]} is older than the minimum required version {'.'.join(map(str, min_version))}. "
                    "Please upgrade by running: `claude upgrade`"
                )
            else:
                claude_available = True
                claude_help = None

    # 2. Check Gemini CLI
    gemini_path = shutil.which("gemini")
    if not gemini_path:
        gemini_available = False
        gemini_help = (
            "Gemini CLI is not installed on the system. "
            "To install, run: `npm install -g @google/gemini-cli`"
        )
    else:
        code, stdout, stderr = run_cmd(["gemini", "--version"])
        if code != 0:
            gemini_available = False
            gemini_help = f"Failed to check Gemini CLI version. Executable found but execution failed: {stderr.strip()}"
        else:
            version_str = stdout.strip()
            version = parse_version(version_str)
            min_version = (0, 43, 0)
            if version < min_version:
                gemini_available = False
                gemini_help = (
                    f"Installed Gemini CLI version {version_str} is older than the minimum required version {'.'.join(map(str, min_version))}. "
                    "Please upgrade by running: `npm install -g @google/gemini-cli`"
                )
            else:
                gemini_available = True
                gemini_help = None

    # 3. Check Antigravity CLI
    agy_path = shutil.which("agy")
    agy_models = []
    if not agy_path:
        agy_available = False
        agy_help = (
            "Antigravity CLI (agy) is not installed on the system. "
            "To install, run: `curl -fsSL https://antigravity.google/cli/install.sh | bash`"
        )
    else:
        code, stdout, stderr = run_cmd(["agy", "--version"])
        if code != 0:
            agy_available = False
            agy_help = f"Failed to check Antigravity CLI version. Executable found but execution failed: {stderr.strip()}"
        else:
            version_str = stdout.strip()
            version = parse_version(version_str)
            min_version = (1, 0, 5)
            if version < min_version:
                agy_available = False
                agy_help = (
                    f"Installed Antigravity CLI version {version_str} is older than the minimum required version {'.'.join(map(str, min_version))}. "
                    "Please upgrade by running: `agy update`"
                )
            else:
                agy_available = True
                agy_help = None

                # Fetch models
                m_code, m_stdout, m_stderr = run_cmd(["agy", "models"])
                if m_code == 0:
                    for line in m_stdout.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        if "Fetching" in line:
                            continue
                        if any(0x2800 <= ord(c) <= 0x28FF for c in line):
                            continue
                        agy_models.append(line)

    with harnesses_lock:
        harnesses_cache["claude"]["available"] = claude_available
        harnesses_cache["claude"]["help_message"] = claude_help

        harnesses_cache["gemini"]["available"] = gemini_available
        harnesses_cache["gemini"]["help_message"] = gemini_help

        harnesses_cache["agy"]["available"] = agy_available
        harnesses_cache["agy"]["help_message"] = agy_help
        harnesses_cache["agy"]["models"] = agy_models

    logger.info("[SERVER] Agent frameworks discovery complete.")


def get_harnesses_list() -> List[HarnessInfo]:
    with harnesses_lock:
        return [
            HarnessInfo(
                name=h["name"],
                display_name=h["display_name"],
                available=h["available"],
                help_message=h["help_message"],
                models=h["models"],
            )
            for h in harnesses_cache.values()
        ]
