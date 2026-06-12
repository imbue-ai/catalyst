"""Guard: the `mngr` the orchestrator drives must expose exactly the plugin
set Catalyst expects -- no more, no less.

Why this matters: the mngr-based runners shell out to whatever `mngr` is on
PATH (`subprocess.run(["mngr", ...])`). Catalyst pins a specific set of mngr
packages in `src/pyproject.toml` (imbue-mngr, -claude, -antigravity, -wait),
which register the plugins listed below. If an *extra* plugin becomes active
-- most dangerously `claude_subagent_proxy`, which reroutes Claude's Task
subagents through separate mngr agents -- agent behavior changes out from
under us. In particular, the runner detects turn end via `mngr wait --state
WAITING`, which keys on the agent's `active` lifecycle marker; a plugin that
changes how/when subagents run (and therefore when the parent is idle) can
make WAITING fire at the wrong time. This commonly happens when `mngr`
resolves to a *development* build (e.g. an mngr monorepo checkout / dev shim)
that has every workspace plugin installed, instead of Catalyst's pinned
PyPI install.

The test runs `mngr plugin list` against a throwaway host dir (so it reflects
the *installed* plugin set with default-enabled state, independent of any
user profile) and asserts the active set is exactly EXPECTED_ACTIVE_PLUGINS.

Maintenance: when Catalyst intentionally bumps its mngr dependencies and the
bundled plugin set changes, update EXPECTED_ACTIVE_PLUGINS deliberately. An
*unexpected* diff here is the signal this guard exists to catch.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

# The exact set of plugins Catalyst's pinned mngr install registers and
# enables. Captured from `mngr plugin list` against imbue-mngr 0.2.12 +
# imbue-mngr-claude 0.2.12 + imbue-mngr-antigravity 0.1.3 + imbue-mngr-wait
# 0.1.9 (see src/pyproject.toml). Notably ABSENT: claude_subagent_proxy.
EXPECTED_ACTIVE_PLUGINS = frozenset(
    {
        "antigravity",
        "builtin_help_topics",
        "claude",
        "code_guardian",
        "codex",
        "command",
        "docker",
        "fixme_fairy",
        "headless_claude",
        "headless_command",
        "local",
        "ssh",
        "wait",
    }
)


def _list_active_plugins() -> set[str]:
    """Return the set of enabled plugin names reported by `mngr plugin list`.

    Uses a throwaway MNGR_HOST_DIR so the result reflects the installed
    packages with default-enabled state and is not perturbed by the
    developer's real `~/.mngr` profile (which can also carry stale fields
    that make a profile-bound `plugin list` error out).
    """
    with tempfile.TemporaryDirectory(prefix="mngr-plugin-guard-") as host_dir:
        result = subprocess.run(
            ["mngr", "plugin", "list", "--fields", "name,enabled"],
            check=False,
            capture_output=True,
            text=True,
            env={"MNGR_HOST_DIR": host_dir, "PATH": os.environ.get("PATH", "")},
            timeout=120,
        )
    if result.returncode != 0:
        raise AssertionError(
            "`mngr plugin list` failed (exit "
            f"{result.returncode}).\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    active: set[str] = set()
    for line in result.stdout.splitlines():
        tokens = line.split()
        # Skip the header row and any blank/banner lines. Data rows are
        # "<name> <true|false>".
        if len(tokens) < 2 or tokens[-1] not in ("true", "false"):
            continue
        name, enabled = tokens[0], tokens[-1]
        if enabled == "true":
            active.add(name)
    return active


class TestMngrEnvironment(unittest.TestCase):
    @unittest.skipIf(shutil.which("mngr") is None, "mngr not on PATH")
    def test_only_expected_plugins_are_active(self) -> None:
        active = _list_active_plugins()
        unexpected = active - EXPECTED_ACTIVE_PLUGINS
        missing = EXPECTED_ACTIVE_PLUGINS - active
        self.assertEqual(
            active,
            set(EXPECTED_ACTIVE_PLUGINS),
            "Active mngr plugin set does not match Catalyst's expected set.\n"
            f"  UNEXPECTED (active but not wanted): {sorted(unexpected) or 'none'}\n"
            f"  MISSING (wanted but not active):    {sorted(missing) or 'none'}\n"
            "If 'claude_subagent_proxy' is unexpected, `mngr` is resolving to a "
            "development build instead of Catalyst's pinned install -- the "
            "orchestrator would then drive an agent whose subagent/turn-end "
            "behavior differs from production. If this change is intentional "
            "(a deliberate mngr dependency bump), update EXPECTED_ACTIVE_PLUGINS.",
        )


if __name__ == "__main__":
    unittest.main()
