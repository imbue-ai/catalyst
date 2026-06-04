import unittest
from unittest.mock import patch
from ..harness import parse_version, discover_frameworks_bg, get_harnesses_list, harnesses_cache, harnesses_lock


class TestHarness(unittest.TestCase):
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
            harnesses_cache["claude"]["available"] = False
            harnesses_cache["gemini"]["available"] = False
            harnesses_cache["agy"]["available"] = False

        # Everything not installed
        mock_which.return_value = None

        discover_frameworks_bg(once=True)

        harnesses = get_harnesses_list()
        claude = next(h for h in harnesses if h.name == "claude")
        gemini = next(h for h in harnesses if h.name == "gemini")
        agy = next(h for h in harnesses if h.name == "agy")

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
