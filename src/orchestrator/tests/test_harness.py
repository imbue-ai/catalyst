import unittest
from unittest.mock import patch
from ..harness import parse_version, discover_frameworks_bg, get_harnesses_list, harnesses_cache, harnesses_lock


class TestHarness(unittest.TestCase):
    def setUp(self):
        with harnesses_lock:
            harnesses_cache["codex"]["available"] = False
            harnesses_cache["codex"]["help_message"] = "Checking framework availability..."
            harnesses_cache["claude"]["available"] = False
            harnesses_cache["claude"]["help_message"] = "Checking framework availability..."
            harnesses_cache["gemini"]["available"] = False
            harnesses_cache["gemini"]["help_message"] = "Checking framework availability..."
            harnesses_cache["agy"]["available"] = False
            harnesses_cache["agy"]["help_message"] = "Checking framework availability..."
            harnesses_cache["agy"]["models"] = []
            harnesses_cache["mngr-claude"]["available"] = False
            harnesses_cache["mngr-claude"]["help_message"] = "Checking framework availability..."
            harnesses_cache["mngr-antigravity"]["available"] = False
            harnesses_cache["mngr-antigravity"]["help_message"] = "Checking framework availability..."
            harnesses_cache["mngr-antigravity"]["models"] = []

    def test_parse_version(self):
        self.assertEqual(parse_version("2.1.0"), (2, 1, 0))
        self.assertEqual(parse_version("0.43.2-alpha"), (0, 43, 2))
        self.assertEqual(parse_version("version 1.0.5"), (1, 0, 5))
        self.assertEqual(parse_version("invalid"), (0, 0, 0))

    @patch("shutil.which")
    @patch("orchestrator.harness.run_cmd")
    def test_discover_frameworks_all_unavailable(self, mock_run_cmd, mock_which):
        # Setup initial cache state: all unavailable
        with harnesses_lock:
            harnesses_cache["codex"]["available"] = False
            harnesses_cache["claude"]["available"] = False
            harnesses_cache["gemini"]["available"] = False
            harnesses_cache["agy"]["available"] = False

        # Everything not installed
        mock_which.return_value = None

        discover_frameworks_bg(once=True)

        harnesses = get_harnesses_list()
        codex = next(h for h in harnesses if h.name == "codex")
        claude = next(h for h in harnesses if h.name == "claude")
        gemini = next(h for h in harnesses if h.name == "gemini")
        agy = next(h for h in harnesses if h.name == "agy")

        self.assertFalse(codex.available)
        self.assertIn("not installed", codex.help_message)

        self.assertFalse(claude.available)
        self.assertIn("not installed", claude.help_message)

        self.assertFalse(gemini.available)
        self.assertIn("not installed", gemini.help_message)

        self.assertFalse(agy.available)
        self.assertIn("not installed", agy.help_message)

    @patch("shutil.which")
    @patch("orchestrator.harness.run_cmd")
    def test_discover_frameworks_claude_version_old(self, mock_run_cmd, mock_which):
        # Setup initial cache state: all unavailable
        with harnesses_lock:
            harnesses_cache["claude"]["available"] = False
            harnesses_cache["gemini"]["available"] = False
            harnesses_cache["agy"]["available"] = False

        # Claude is installed but has version 2.0.0 (older than 2.1.0)
        def side_effect(args):
            if args == ["claude", "--version"]:
                return 0, "2.0.0", ""
            return 0, "", ""

        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd if cmd in ["claude"] else None
        mock_run_cmd.side_effect = side_effect

        discover_frameworks_bg(once=True)

        harnesses = get_harnesses_list()
        claude = next(h for h in harnesses if h.name == "claude")
        self.assertFalse(claude.available)
        self.assertIn("older than the minimum required version", claude.help_message)

    @patch("shutil.which")
    @patch("orchestrator.harness.run_cmd")
    def test_discover_frameworks_claude_unauthenticated(self, mock_run_cmd, mock_which):
        # Setup initial cache state: all unavailable
        with harnesses_lock:
            harnesses_cache["claude"]["available"] = False
            harnesses_cache["gemini"]["available"] = False
            harnesses_cache["agy"]["available"] = False

        # Claude is installed and version ok (2.1.0) but unauthenticated
        def side_effect(args):
            if args == ["claude", "--version"]:
                return 0, "2.1.0", ""
            if args == ["claude", "auth", "status"]:
                return 1, "", "Not logged in"
            return 0, "", ""

        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd if cmd in ["claude"] else None
        mock_run_cmd.side_effect = side_effect

        discover_frameworks_bg(once=True)

        harnesses = get_harnesses_list()
        claude = next(h for h in harnesses if h.name == "claude")
        self.assertFalse(claude.available)
        self.assertIn("not authenticated", claude.help_message)

    @patch("shutil.which")
    @patch("orchestrator.harness.run_cmd")
    def test_discover_frameworks_claude_json_not_logged_in(self, mock_run_cmd, mock_which):
        # Setup initial cache state: all unavailable
        with harnesses_lock:
            harnesses_cache["claude"]["available"] = False
            harnesses_cache["gemini"]["available"] = False
            harnesses_cache["agy"]["available"] = False

        # Claude is installed, version ok (2.1.0) but JSON loggedIn is False
        def side_effect(args):
            if args == ["claude", "--version"]:
                return 0, "2.1.0", ""
            if args == ["claude", "auth", "status"]:
                return 0, '{"loggedIn": false}', ""
            return 0, "", ""

        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd if cmd in ["claude"] else None
        mock_run_cmd.side_effect = side_effect

        discover_frameworks_bg(once=True)

        harnesses = get_harnesses_list()
        claude = next(h for h in harnesses if h.name == "claude")
        self.assertFalse(claude.available)
        self.assertIn("not authenticated", claude.help_message)

    @patch("shutil.which")
    @patch("orchestrator.harness.run_cmd")
    def test_discover_frameworks_all_available(self, mock_run_cmd, mock_which):
        # Setup initial cache state: all unavailable
        with harnesses_lock:
            harnesses_cache["claude"]["available"] = False
            harnesses_cache["gemini"]["available"] = False
            harnesses_cache["agy"]["available"] = False

        # Everything available and authenticated/correct versions
        def side_effect(args):
            if args == ["claude", "--version"]:
                return 0, "2.2.0", ""
            if args == ["claude", "auth", "status"]:
                return 0, '{"loggedIn": true}', ""
            if args == ["gemini", "--version"]:
                return 0, "0.43.0", ""
            if args == ["agy", "--version"]:
                return 0, "1.0.5", ""
            if args == ["agy", "models"]:
                return 0, "model-a\nmodel-b\n", ""
            return 0, "", ""

        mock_which.return_value = "/usr/bin/cmd"
        mock_run_cmd.side_effect = side_effect

        discover_frameworks_bg(once=True)

        harnesses = get_harnesses_list()
        claude = next(h for h in harnesses if h.name == "claude")
        gemini = next(h for h in harnesses if h.name == "gemini")
        agy = next(h for h in harnesses if h.name == "agy")

        self.assertTrue(claude.available)
        self.assertIsNone(claude.help_message)

        self.assertTrue(gemini.available)
        self.assertIsNone(gemini.help_message)

        self.assertTrue(agy.available)
        self.assertIsNone(agy.help_message)
        self.assertEqual(agy.models, ["model-a", "model-b"])

    @patch("shutil.which")
    @patch("orchestrator.harness.run_cmd")
    def test_discover_frameworks_agy_unauthenticated(self, mock_run_cmd, mock_which):
        # Setup initial cache state: all unavailable
        with harnesses_lock:
            harnesses_cache["claude"]["available"] = False
            harnesses_cache["gemini"]["available"] = False
            harnesses_cache["agy"]["available"] = False

        # agy is installed but running `agy models` outputs sign in error message
        def side_effect(args):
            if args == ["claude", "--version"]:
                return 0, "2.2.0", ""
            if args == ["claude", "auth", "status"]:
                return 0, '{"loggedIn": true}', ""
            if args == ["gemini", "--version"]:
                return 0, "0.43.0", ""
            if args == ["agy", "--version"]:
                return 0, "1.0.5", ""
            if args == ["agy", "models"]:
                return 0, "Error: Please sign in to view available models. Launch the CLI without arguments to sign in.", ""
            return 0, "", ""

        mock_which.return_value = "/usr/bin/cmd"
        mock_run_cmd.side_effect = side_effect

        discover_frameworks_bg(once=True)

        harnesses = get_harnesses_list()
        agy = next(h for h in harnesses if h.name == "agy")

        self.assertFalse(agy.available)
        self.assertIn("not authenticated", agy.help_message)
        self.assertIn("running `agy`", agy.help_message)

    @patch("shutil.which")
    @patch("orchestrator.harness.run_cmd")
    def test_discover_frameworks_only_unavailable_rechecked(self, mock_run_cmd, mock_which):
        # Setup initial cache state: claude is available, gemini is unavailable, agy is unavailable
        with harnesses_lock:
            harnesses_cache["claude"]["available"] = True
            harnesses_cache["claude"]["help_message"] = None
            harnesses_cache["gemini"]["available"] = False
            harnesses_cache["gemini"]["help_message"] = "old message"
            harnesses_cache["agy"]["available"] = False
            harnesses_cache["agy"]["help_message"] = "old message"

        # Mock mock_run_cmd and mock_which to only make Gemini/Agy available
        def side_effect(args):
            if "claude" in args:
                self.fail("Claude should not have been checked since it was already available")
            if args == ["gemini", "--version"]:
                return 0, "0.43.0", ""
            if args == ["agy", "--version"]:
                return 0, "1.0.5", ""
            if args == ["agy", "models"]:
                return 0, "model-x\n", ""
            return 0, "", ""

        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd if cmd in ["gemini", "agy"] else None
        mock_run_cmd.side_effect = side_effect

        discover_frameworks_bg(once=True)

        harnesses = get_harnesses_list()
        claude = next(h for h in harnesses if h.name == "claude")
        gemini = next(h for h in harnesses if h.name == "gemini")
        agy = next(h for h in harnesses if h.name == "agy")

        # Claude should still be available (not touched)
        self.assertTrue(claude.available)
        self.assertIsNone(claude.help_message)

        # Gemini and Agy should now be available
        self.assertTrue(gemini.available)
        self.assertTrue(agy.available)

    @patch("shutil.which")
    @patch("orchestrator.harness.run_cmd")
    def test_discover_frameworks_mngr_dependencies_missing(self, mock_run_cmd, mock_which):
        # Base harnesses (claude and agy) are available, but mngr deps are missing
        def side_effect(args):
            if args == ["claude", "--version"]:
                return 0, "2.2.0", ""
            if args == ["claude", "auth", "status"]:
                return 0, '{"loggedIn": true}', ""
            if args == ["gemini", "--version"]:
                return 0, "0.43.0", ""
            if args == ["agy", "--version"]:
                return 0, "1.0.5", ""
            if args == ["agy", "models"]:
                return 0, "model-a\n", ""
            if args == ["uv", "run", "mngr", "dependencies"]:
                return 1, "", "tmux is missing"
            return 0, "", ""

        mock_which.return_value = "/usr/bin/cmd"
        mock_run_cmd.side_effect = side_effect

        discover_frameworks_bg(once=True)

        harnesses = get_harnesses_list()
        claude = next(h for h in harnesses if h.name == "claude")
        agy = next(h for h in harnesses if h.name == "agy")
        mngr_claude = next(h for h in harnesses if h.name == "mngr-claude")
        mngr_agy = next(h for h in harnesses if h.name == "mngr-antigravity")

        # Base harnesses are available
        self.assertTrue(claude.available)
        self.assertTrue(agy.available)

        # mngr wrapper harnesses are not available
        self.assertFalse(mngr_claude.available)
        self.assertIn("Some mngr dependencies are missing", mngr_claude.help_message)
        self.assertIn("uv run mngr dependencies -i", mngr_claude.help_message)

        self.assertFalse(mngr_agy.available)
        self.assertIn("Some mngr dependencies are missing", mngr_agy.help_message)
        self.assertIn("uv run mngr dependencies -i", mngr_agy.help_message)
        # mngr-antigravity still has model list synchronized
        self.assertEqual(mngr_agy.models, ["model-a"])

    @patch("shutil.which")
    @patch("orchestrator.harness.run_cmd")
    def test_discover_frameworks_mngr_dependencies_ok(self, mock_run_cmd, mock_which):
        # Base harnesses are available, and mngr deps pass
        def side_effect(args):
            if args == ["claude", "--version"]:
                return 0, "2.2.0", ""
            if args == ["claude", "auth", "status"]:
                return 0, '{"loggedIn": true}', ""
            if args == ["gemini", "--version"]:
                return 0, "0.43.0", ""
            if args == ["agy", "--version"]:
                return 0, "1.0.5", ""
            if args == ["agy", "models"]:
                return 0, "model-a\n", ""
            if args == ["uv", "run", "mngr", "dependencies"]:
                return 0, "", ""
            return 0, "", ""

        mock_which.return_value = "/usr/bin/cmd"
        mock_run_cmd.side_effect = side_effect

        discover_frameworks_bg(once=True)

        harnesses = get_harnesses_list()
        mngr_claude = next(h for h in harnesses if h.name == "mngr-claude")
        mngr_agy = next(h for h in harnesses if h.name == "mngr-antigravity")

        self.assertTrue(mngr_claude.available)
        self.assertIsNone(mngr_claude.help_message)

        self.assertTrue(mngr_agy.available)
        self.assertIsNone(mngr_agy.help_message)
        self.assertEqual(mngr_agy.models, ["model-a"])

    @patch("shutil.which")
    @patch("orchestrator.harness.run_cmd")
    def test_discover_frameworks_mngr_base_unavailable(self, mock_run_cmd, mock_which):
        # Base harnesses are not available (not installed / version old)
        def side_effect(args):
            if args == ["claude", "--version"]:
                return 0, "2.0.0", ""  # older than 2.1.0
            if args == ["gemini", "--version"]:
                return 0, "0.43.0", ""
            if args == ["agy", "--version"]:
                return 0, "1.0.5", ""
            if args == ["agy", "models"]:
                return 0, "model-a\n", ""
            if args == ["uv", "run", "mngr", "dependencies"]:
                return 0, "", ""
            return 0, "", ""

        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd if cmd in ["claude", "gemini", "agy"] else None
        mock_run_cmd.side_effect = side_effect

        discover_frameworks_bg(once=True)

        harnesses = get_harnesses_list()
        mngr_claude = next(h for h in harnesses if h.name == "mngr-claude")
        mngr_agy = next(h for h in harnesses if h.name == "mngr-antigravity")

        # claude is old -> mngr-claude should be unavailable and share the same version failure
        self.assertFalse(mngr_claude.available)
        self.assertIn("older than the minimum required version", mngr_claude.help_message)

        # agy is available and mngr deps are ok -> mngr-antigravity is available
        self.assertTrue(mngr_agy.available)

    @patch("shutil.which")
    @patch("orchestrator.harness.run_cmd")
    def test_discover_frameworks_codex_version_old(self, mock_run_cmd, mock_which):
        # Setup initial cache: all unavailable
        with harnesses_lock:
            harnesses_cache["codex"]["available"] = False

        # codex version is 0.136.0 (older than 0.137.0)
        def side_effect(args):
            if args == ["codex", "--version"]:
                return 0, "0.136.0", ""
            return 0, "", ""

        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd if cmd in ["codex"] else None
        mock_run_cmd.side_effect = side_effect

        discover_frameworks_bg(once=True)

        harnesses = get_harnesses_list()
        codex = next(h for h in harnesses if h.name == "codex")
        self.assertFalse(codex.available)
        self.assertIn("older than the minimum required version", codex.help_message)

    @patch("shutil.which")
    @patch("orchestrator.harness.run_cmd")
    def test_discover_frameworks_codex_unauthenticated(self, mock_run_cmd, mock_which):
        with harnesses_lock:
            harnesses_cache["codex"]["available"] = False

        # version 0.137.0 but 'Not logged in' in status
        def side_effect(args):
            if args == ["codex", "--version"]:
                return 0, "0.137.0", ""
            if args == ["codex", "login", "status"]:
                return 0, "Not logged in", ""
            return 0, "", ""

        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd if cmd in ["codex"] else None
        mock_run_cmd.side_effect = side_effect

        discover_frameworks_bg(once=True)

        harnesses = get_harnesses_list()
        codex = next(h for h in harnesses if h.name == "codex")
        self.assertFalse(codex.available)
        self.assertIn("not authenticated", codex.help_message)

    @patch("shutil.which")
    @patch("orchestrator.harness.run_cmd")
    def test_discover_frameworks_codex_available(self, mock_run_cmd, mock_which):
        with harnesses_lock:
            harnesses_cache["codex"]["available"] = False

        # version 0.137.0 and logged in (status output has "Logged in using ChatGPT")
        def side_effect(args):
            if args == ["codex", "--version"]:
                return 0, "0.137.0", ""
            if args == ["codex", "login", "status"]:
                return 0, "Logged in using ChatGPT", ""
            return 0, "", ""

        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd if cmd in ["codex"] else None
        mock_run_cmd.side_effect = side_effect

        discover_frameworks_bg(once=True)

        harnesses = get_harnesses_list()
        codex = next(h for h in harnesses if h.name == "codex")
        self.assertTrue(codex.available)
        self.assertIsNone(codex.help_message)
