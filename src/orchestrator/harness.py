import json
import logging
import re
import shutil
import subprocess
import threading
import time
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
    "mngr-claude": {
        "name": "mngr-claude",
        "display_name": "Claude Code (mngr)",
        "available": False,
        "help_message": "Checking framework availability...",
        "models": ["opus", "sonnet", "haiku"],
    },
    "claude": {
        "name": "claude",
        "display_name": "Claude Code (claude -p)",
        "available": False,
        "help_message": "Checking framework availability...",
        "models": ["opus", "sonnet", "haiku"],
    },
    "mngr-antigravity": {
        "name": "mngr-antigravity",
        "display_name": "Antigravity CLI (mngr)",
        "available": False,
        "help_message": "Checking framework availability...",
        "models": [],
    },
    "agy": {
        "name": "agy",
        "display_name": "Antigravity CLI (agy -p)",
        "available": False,
        "help_message": "Checking framework availability...",
        "models": [],
    },
    "gemini": {
        "name": "gemini",
        "display_name": "Gemini CLI (gemini -p)",
        "available": False,
        "help_message": "Checking framework availability...",
        "models": ["pro", "flash"],
    },
    "codex": {
        "name": "codex",
        "display_name": "Codex CLI (codex exec)",
        "available": False,
        "help_message": "Checking framework availability...",
        "models": ["gpt-5.5", "gpt-5.4-mini"],
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


def _check_claude() -> tuple[bool, Optional[str]]:
    claude_path = shutil.which("claude")
    if not claude_path:
        return False, (
            "Claude Code is not installed on the system. "
            "To install, run: `curl -fsSL https://claude.ai/install.sh | bash`"
        )

    code, stdout, stderr = run_cmd(["claude", "--version"])
    if code != 0:
        return (
            False,
            f"Failed to check Claude Code version. Executable found but execution failed: {stderr.strip()}",
        )

    version_str = stdout.strip()
    version = parse_version(version_str)
    min_version = (2, 1, 0)
    if version < min_version:
        return False, (
            f"Installed Claude Code version {version_str.split()[0]} is older than the minimum required version {'.'.join(map(str, min_version))}. "
            "Please upgrade by running: `claude upgrade`"
        )

    # Check authentication status
    auth_code, auth_stdout, auth_stderr = run_cmd(["claude", "auth", "status"])
    claude_auth_help = (
        "Claude Code is not authenticated. "
        "Please login by running `claude auth login` in your terminal."
    )
    if auth_code != 0:
        return False, claude_auth_help

    try:
        auth_data = json.loads(auth_stdout.strip())
        if not auth_data.get("loggedIn"):
            return False, claude_auth_help
        return True, None
    except Exception:
        # Fallback if parsing json fails but exit code was 0
        return True, None


def _check_codex() -> tuple[bool, Optional[str]]:
    codex_path = shutil.which("codex")
    if not codex_path:
        return False, (
            "Codex CLI is not installed on the system. "
            "To install, please check the Codex documentation."
        )

    code, stdout, stderr = run_cmd(["codex", "--version"])
    if code != 0:
        return (
            False,
            f"Failed to check Codex CLI version. Executable found but execution failed: {stderr.strip()}",
        )

    version_str = stdout.strip()
    version = parse_version(version_str)
    min_version = (0, 137, 0)
    if version < min_version:
        v_parts = version_str.split()
        v_display = (
            v_parts[1] if len(v_parts) > 1 else (v_parts[0] if v_parts else version_str)
        )
        return False, (
            f"Installed Codex CLI version {v_display} is older than the minimum required version {'.'.join(map(str, min_version))}. "
            "Please upgrade Codex CLI."
        )

    # Check authentication status
    auth_code, auth_stdout, auth_stderr = run_cmd(["codex", "login", "status"])
    codex_auth_help = (
        "Codex CLI is not authenticated. "
        "Please login by running `codex login` in your terminal."
    )
    if auth_code != 0:
        return False, codex_auth_help

    combined_output = (auth_stdout + "\n" + auth_stderr).strip()
    if "Not logged in" in combined_output:
        return False, codex_auth_help

    return True, None


def _check_gemini() -> tuple[bool, Optional[str]]:
    gemini_path = shutil.which("gemini")
    if not gemini_path:
        return False, (
            "Gemini CLI is not installed on the system. "
            "To install, run: `npm install -g @google/gemini-cli`"
        )

    code, stdout, stderr = run_cmd(["gemini", "--version"])
    if code != 0:
        return (
            False,
            f"Failed to check Gemini CLI version. Executable found but execution failed: {stderr.strip()}",
        )

    version_str = stdout.strip()
    version = parse_version(version_str)
    min_version = (0, 43, 0)
    if version < min_version:
        return False, (
            f"Installed Gemini CLI version {version_str} is older than the minimum required version {'.'.join(map(str, min_version))}. "
            "Please upgrade by running: `npm install -g @google/gemini-cli`"
        )

    return True, None


def _check_agy() -> tuple[bool, Optional[str], List[str]]:
    agy_path = shutil.which("agy")
    agy_models: List[str] = []
    if not agy_path:
        return (
            False,
            (
                "Antigravity CLI (agy) is not installed on the system. "
                "To install, run: `curl -fsSL https://antigravity.google/cli/install.sh | bash`"
            ),
            agy_models,
        )

    code, stdout, stderr = run_cmd(["agy", "--version"])
    if code != 0:
        return (
            False,
            f"Failed to check Antigravity CLI version. Executable found but execution failed: {stderr.strip()}",
            agy_models,
        )

    version_str = stdout.strip()
    version = parse_version(version_str)
    min_version = (1, 0, 5)
    if version < min_version:
        return (
            False,
            (
                f"Installed Antigravity CLI version {version_str} is older than the minimum required version {'.'.join(map(str, min_version))}. "
                "Please upgrade by running: `agy update`"
            ),
            agy_models,
        )

    # Fetch models and check auth status
    m_code, m_stdout, m_stderr = run_cmd(["agy", "models"])
    combined_output = (m_stdout + "\n" + m_stderr).lower()

    if "error" in combined_output and "sign in" in combined_output:
        return (
            False,
            (
                "Antigravity CLI is not authenticated. "
                "Please login by running `agy` in your terminal."
            ),
            agy_models,
        )

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

    return True, None, agy_models


def _check_mngr_deps() -> tuple[bool, Optional[str]]:
    code, stdout, stderr = run_cmd(
        ["uv", "run", "mngr", "dependencies", "--scope", "core"]
    )
    if code != 0:
        return False, (
            "Some mngr dependencies are missing. "
            "Please run `uv run mngr dependencies -i` in your terminal to install them."
        )
    return True, None


def discover_frameworks_bg(once: bool = False):
    logger.info("[SERVER] Starting agent frameworks discovery background loop...")

    while True:
        try:
            # Check current availability status from cache
            with harnesses_lock:
                codex_was_avail = harnesses_cache["codex"]["available"]
                claude_was_avail = harnesses_cache["claude"]["available"]
                gemini_was_avail = harnesses_cache["gemini"]["available"]
                agy_was_avail = harnesses_cache["agy"]["available"]
                mngr_claude_was_avail = harnesses_cache["mngr-claude"]["available"]
                mngr_agy_was_avail = harnesses_cache["mngr-antigravity"]["available"]

            if not codex_was_avail:
                codex_available, codex_help = _check_codex()
                with harnesses_lock:
                    harnesses_cache["codex"]["available"] = codex_available
                    harnesses_cache["codex"]["help_message"] = codex_help

            # Only check if currently unavailable
            if not claude_was_avail:
                claude_available, claude_help = _check_claude()
                with harnesses_lock:
                    harnesses_cache["claude"]["available"] = claude_available
                    harnesses_cache["claude"]["help_message"] = claude_help
            else:
                claude_available = True
                with harnesses_lock:
                    claude_help = harnesses_cache["claude"]["help_message"]

            if not gemini_was_avail:
                gemini_available, gemini_help = _check_gemini()
                with harnesses_lock:
                    harnesses_cache["gemini"]["available"] = gemini_available
                    harnesses_cache["gemini"]["help_message"] = gemini_help

            if not agy_was_avail:
                agy_available, agy_help, agy_models = _check_agy()
                with harnesses_lock:
                    harnesses_cache["agy"]["available"] = agy_available
                    harnesses_cache["agy"]["help_message"] = agy_help
                    harnesses_cache["agy"]["models"] = agy_models
            else:
                agy_available = True
                with harnesses_lock:
                    agy_help = harnesses_cache["agy"]["help_message"]
                    agy_models = harnesses_cache["agy"]["models"]

            mngr_deps_ok = None
            mngr_deps_help = None

            def check_mngr_lazy():
                nonlocal mngr_deps_ok, mngr_deps_help
                if mngr_deps_ok is None:
                    mngr_deps_ok, mngr_deps_help = _check_mngr_deps()
                return mngr_deps_ok, mngr_deps_help

            if not mngr_claude_was_avail:
                if claude_available:
                    deps_ok, deps_help = check_mngr_lazy()
                    if deps_ok:
                        m_claude_avail = True
                        m_claude_help = None
                    else:
                        m_claude_avail = False
                        m_claude_help = deps_help
                else:
                    m_claude_avail = False
                    m_claude_help = claude_help

                with harnesses_lock:
                    harnesses_cache["mngr-claude"]["available"] = m_claude_avail
                    harnesses_cache["mngr-claude"]["help_message"] = m_claude_help

            if not mngr_agy_was_avail:
                if agy_available:
                    deps_ok, deps_help = check_mngr_lazy()
                    if deps_ok:
                        m_agy_avail = True
                        m_agy_help = None
                    else:
                        m_agy_avail = False
                        m_agy_help = deps_help
                else:
                    m_agy_avail = False
                    m_agy_help = agy_help

                with harnesses_lock:
                    harnesses_cache["mngr-antigravity"]["available"] = m_agy_avail
                    harnesses_cache["mngr-antigravity"]["help_message"] = m_agy_help
                    harnesses_cache["mngr-antigravity"]["models"] = agy_models
            else:
                with harnesses_lock:
                    harnesses_cache["mngr-antigravity"]["models"] = agy_models

        except Exception as e:
            logger.error(f"[SERVER] Error in discover_frameworks_bg: {e}")

        if once:
            break
        time.sleep(30)


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
