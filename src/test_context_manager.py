import os
import shutil
import subprocess
import sys
import tempfile
import json
import unittest
from pathlib import Path

# We can import constants to drive the test logic, as requested to be thorough.
from context_manager import (
    AGENT_TYPE_MAP,
    CATEGORY_MD_MAP,
)


class TestContextManager(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for the DB and workspaces
        self.test_dir = Path(tempfile.mkdtemp())
        self.db_path = self.test_dir / "test_db"
        self.env = os.environ.copy()
        self.env["AI_SCIENTIST_DB_PATH"] = str(self.db_path)

        # Path to the script and python executable
        self.script_path = Path(__file__).parent / "context_manager.py"
        self.python_exe = sys.executable

    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.test_dir)

    def run_cmd(self, *args, check=True, tx_id=None, **kwargs):
        env = self.env.copy()
        if tx_id:
            env["CONTEXT_TRANSACTION_ID"] = tx_id

        cmd = [self.python_exe, str(self.script_path)] + list(args)
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, **kwargs)
        if check and result.returncode != 0:
            self.fail(
                f"Command failed: {' '.join(cmd)}\nStdout: {result.stdout}\nStderr: {result.stderr}"
            )
        return result

    def test_init_db(self):
        """Verify that init creates the database directory."""
        self.run_cmd("init")
        self.assertTrue(self.db_path.is_dir())
        # Re-running init should be fine
        self.run_cmd("init")

    def test_store_results_all_agents(self):
        """Iterate over all agent types and verify store_results works."""
        self.run_cmd("init")

        # 1. Create a parent theory first, as some agents require it
        parent_dir = self.test_dir / "theory_src"
        parent_dir.mkdir()
        (parent_dir / "theory.md").write_text("Parent theory")
        res = self.run_cmd(
            "store_results",
            "--from_agent_type",
            "write-theory",
            "--from_folder",
            str(parent_dir),
        )
        parent_theory_id = res.stdout.strip().split()[-1]

        # 2. Iterate through all agent types
        for agent_type, category in AGENT_TYPE_MAP.items():
            # Skip write-theory as we already did it for the parent
            if agent_type == "write-theory":
                continue

            src_dir = self.test_dir / f"src_{agent_type}"
            src_dir.mkdir(parents=True, exist_ok=True)

            expected_md = CATEGORY_MD_MAP[category]
            (src_dir / expected_md).write_text(f"Content for {agent_type}")

            args = [
                "store_results",
                "--from_agent_type",
                agent_type,
                "--from_folder",
                str(src_dir),
            ]

            # Add parent theory if allowed/required
            parent_theory_required_agents = (
                "falsify-hypothesis",
                "suggest-expansions",
                "predict-experiments",
                "refine-hypothesis",
                "polish-theory",
                "streamline-theory",
                "expand-theory",
                "edit-theory",
            )
            parent_theory_allowed_agents = parent_theory_required_agents + (
                "run-experiment",
                "support-idea",
            )

            if agent_type in parent_theory_allowed_agents:
                args += ["--parent_theory", parent_theory_id]

            res = self.run_cmd(*args)
            new_id = res.stdout.strip().split()[-1]
            self.assertTrue(len(new_id) > 0)

            # Verify metadata
            target_meta = self.db_path / category / new_id / "metadata.json"
            self.assertTrue(target_meta.exists())
            meta_data = json.loads(target_meta.read_text())
            self.assertEqual(meta_data["id"], new_id)
            self.assertEqual(meta_data["agent_type"], agent_type)

    def test_create_context_all_agent_types(self):
        """Verify create_context works for all supported target agent types."""
        self.run_cmd("init")

        # Setup base artifacts
        def store_simple(agent, cat, content_file, parent=None, extra_files=None):
            d = self.test_dir / f"seed_{agent}"
            d.mkdir(parents=True, exist_ok=True)
            (d / content_file).write_text(f"Seed {agent}")
            if extra_files:
                for f, c in extra_files.items():
                    (d / f).write_text(c)
            args = [
                "store_results",
                "--from_agent_type",
                agent,
                "--from_folder",
                str(d),
            ]
            if parent:
                args += ["--parent_theory", parent]
            return self.run_cmd(*args).stdout.strip().split()[-1]

        e_id = store_simple("explorer", "exploration", "report.md")
        l_id = store_simple("literature-review", "literature", "summary.md")
        t_id = store_simple("write-theory", "theory", "theory.md")
        r_id = store_simple("falsify-hypothesis", "review", "review.md", parent=t_id)
        x_id = store_simple(
            "run-experiment",
            "experiment",
            "description.md",
            parent=t_id,
            extra_files={"script.py": "print(1)"},
        )
        p_id = store_simple(
            "predict-experiments", "prediction", "predictions.md", parent=t_id
        )

        target_agents = [
            ("write-theory", {"--from_exploration": e_id, "--from_literature": l_id}),
            ("falsify-hypothesis", {"--from_theory": t_id}),
            ("refine-hypothesis", {"--from_theory": t_id, "--from_review": r_id}),
            ("review-theory", {"--from_theory": t_id}),
            ("suggest-expansions", {"--from_theory": t_id}),
            ("expand-theory", {"--from_theory": t_id, "--from_review": r_id}),
            ("predict-experiments", {"--from_theory": t_id, "--from_experiment": x_id}),
            (
                "rank-predictions",
                {"--from_experiment": x_id, "--from_prediction": p_id},
            ),
            ("score-theories", {"--from_theory": t_id}),
            ("score-soundness", {"--from_theory": t_id}),
            ("rank-explanatory-power", {"--from_theory": t_id}),
            ("polish-theory", {"--from_theory": t_id}),
            ("streamline-theory", {"--from_theory": t_id}),
            ("edit-theory", {"--from_theory": t_id}),
            ("write-different-theory", {"--from_theory": t_id}),
        ]

        for agent, flags in target_agents:
            target_folder = self.test_dir / f"ctx_{agent}"
            args = [
                "create_context",
                "--for_agent_type",
                agent,
                "--target_folder",
                str(target_folder),
            ]
            for k, v in flags.items():
                args += [k, v]

            self.run_cmd(*args)
            self.assertTrue(target_folder.is_dir())
            # Basic sanity check: target folder should not be empty
            self.assertTrue(any(target_folder.iterdir()))

    def test_transactions(self):
        """Verify transaction isolation and commit."""
        self.run_cmd("init")

        src_dir = self.test_dir / "tx_src"
        src_dir.mkdir()
        (src_dir / "theory.md").write_text("Transactional theory")

        tx_id = "test_tx_42"

        # 1. Store with transaction
        res = self.run_cmd(
            "store_results",
            "--from_agent_type",
            "write-theory",
            "--from_folder",
            str(src_dir),
            tx_id=tx_id,
        )
        t_id = res.stdout.strip().split()[-1]

        # 2. Verify invisible without tx_id
        res = self.run_cmd("list", "--type", "theory", "--json")
        entries = json.loads(res.stdout)
        self.assertEqual(len(entries), 0, f"Expected 0 entries, found: {entries}")

        # 3. Verify visible with tx_id
        res = self.run_cmd("list", "--type", "theory", "--json", tx_id=tx_id)
        entries = json.loads(res.stdout)
        self.assertEqual(
            len(entries), 1, f"Expected 1 entry with tx_id={tx_id}, got 0."
        )
        self.assertEqual(entries[0]["id"], t_id)

        # 4. Commit
        self.run_cmd("commit", tx_id)

        # 5. Verify visible everywhere
        res = self.run_cmd("list", "--type", "theory", "--json")
        entries = json.loads(res.stdout)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["id"], t_id)

    def test_search_experiments(self):
        """Verify experiment search logic."""
        self.run_cmd("init")

        src_dir = self.test_dir / "exp_src"
        src_dir.mkdir()
        (src_dir / "description.md").write_text("Testing quantum gravity effects")

        self.run_cmd(
            "store_results",
            "--from_agent_type",
            "run-experiment",
            "--from_folder",
            str(src_dir),
            "--metadata",
            "tags=quantum,gravity,test",
        )

        # Search by tag
        res = self.run_cmd("search_experiments", "--tag", "quantum", "--json")
        hits = json.loads(res.stdout)
        self.assertEqual(len(hits), 1)
        self.assertIn("quantum", hits[0]["extra"]["tags"])

        # Search by query
        res = self.run_cmd("search_experiments", "--query", "gravity", "--json")
        hits = json.loads(res.stdout)
        self.assertEqual(len(hits), 1)
        self.assertIn("gravity", hits[0]["preview"].lower())

    def test_rescore_and_sample(self):
        """Verify rescoring and sampling of theories."""
        self.run_cmd("init")

        def store_t(content):
            d = self.test_dir / f"t_{content.replace(' ', '_')}"
            d.mkdir(parents=True, exist_ok=True)
            (d / "theory.md").write_text(content)
            return (
                self.run_cmd(
                    "store_results",
                    "--from_agent_type",
                    "write-theory",
                    "--from_folder",
                    str(d),
                )
                .stdout.strip()
                .split()[-1]
            )

        def store_r(t_id):
            d = self.test_dir / f"r_{t_id}"
            d.mkdir(parents=True, exist_ok=True)
            (d / "review.md").write_text("Review content")
            return (
                self.run_cmd(
                    "store_results",
                    "--from_agent_type",
                    "falsify-hypothesis",
                    "--from_folder",
                    str(d),
                    "--parent_theory",
                    t_id,
                )
                .stdout.strip()
                .split()[-1]
            )

        t1 = store_t("Theory 1")
        t2 = store_t("Theory 2")

        # Add reviews to make them eligible for sampling
        store_r(t1)
        store_r(t2)

        # Rescore - explicitly setting is_viable to True
        scores = {
            t1: {"score": 0.9, "is_viable": True},
            t2: {"score": 0.1, "is_viable": True},
        }
        self.run_cmd("rescore_theories", json.dumps(scores))

        # List sorted by score
        res = self.run_cmd("list", "--type", "theory", "--sort_by", "score", "--json")
        entries = json.loads(res.stdout)
        self.assertEqual(entries[0]["id"], t2)  # 0.1 is lower
        self.assertEqual(entries[1]["id"], t1)  # 0.9 is higher

        # Sample
        res = self.run_cmd(
            "sample_theories", "--num_theories", "1", "--purpose", "mutation", "--json"
        )
        sampled = [t["id"] for t in json.loads(res.stdout)]
        self.assertEqual(len(sampled), 1)
        self.assertIn(sampled[0], [t1, t2])

    def test_fetch_helpers(self):
        """Verify fetch_literature and fetch_experiment."""
        self.run_cmd("init")

        # 1. Literature
        lit_dir = self.test_dir / "lit_src"
        lit_dir.mkdir()
        (lit_dir / "summary.md").write_text("Lit summary")
        res = self.run_cmd(
            "store_results",
            "--from_agent_type",
            "literature-review",
            "--from_folder",
            str(lit_dir),
        )
        l_id = res.stdout.strip().split()[-1]

        # 2. Experiment
        exp_dir = self.test_dir / "exp_src_fetch"
        exp_dir.mkdir()
        (exp_dir / "description.md").write_text("Exp desc")
        (exp_dir / "script.py").write_text("print(1)")
        res = self.run_cmd(
            "store_results",
            "--from_agent_type",
            "run-experiment",
            "--from_folder",
            str(exp_dir),
        )
        x_id = res.stdout.strip().split()[-1]

        target = self.test_dir / "fetch_target"
        target.mkdir()

        self.run_cmd(
            "fetch_literature",
            "--target_folder",
            str(target),
            "--from_literature",
            l_id,
        )
        self.assertTrue((target / "literature" / l_id / "summary.md").exists())

        self.run_cmd(
            "fetch_experiment",
            "--target_folder",
            str(target),
            "--from_experiment",
            x_id,
        )
        self.assertTrue((target / "experiments" / x_id / "description.md").exists())

    def test_export_population(self):
        """Verify population export."""
        self.run_cmd("init")
        src_dir = self.test_dir / "pop_src"
        src_dir.mkdir()
        (src_dir / "theory.md").write_text("Theory for export")
        self.run_cmd(
            "store_results",
            "--from_agent_type",
            "write-theory",
            "--from_folder",
            str(src_dir),
        )

        export_path = self.test_dir / "pop.json"
        self.run_cmd("export_theory_population", str(export_path))

        self.assertTrue(export_path.exists())
        data = json.loads(export_path.read_text())
        self.assertIn("organisms", data)
        self.assertEqual(len(data["organisms"]), 1)


if __name__ == "__main__":
    unittest.main()
