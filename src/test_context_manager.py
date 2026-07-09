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
        self.env["CATALYST_DB_PATH"] = str(self.db_path)

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

            if agent_type == "interpret-result":
                expected_md = "interpretation_log.md"
            else:
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
                "review-adherence",
                "improve-adherence",
                "interpret-result",
                "integrate-interpretations",
            )
            parent_theory_allowed_agents = parent_theory_required_agents + (
                "run-experiment",
                "support-idea",
                "propose-experiment",
                "execute-proposal",
                "generate-solution",
            )

            if agent_type in parent_theory_allowed_agents:
                args += ["--parent_theory", parent_theory_id]

            res = self.run_cmd(*args)
            new_id = res.stdout.strip().split()[-1]
            self.assertTrue(len(new_id) > 0)

            if agent_type == "interpret-result":
                # For interpret-result, it updates in-place, returning the parent_theory_id
                self.assertEqual(new_id, parent_theory_id)
                # Verify that interpretation_log.md is successfully updated
                target_log = (
                    self.db_path / "theory" / parent_theory_id / "interpretation_log.md"
                )
                self.assertTrue(target_log.exists())
                self.assertEqual(target_log.read_text(), f"Content for {agent_type}")
            else:
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
        t_parent_id = store_simple(
            "interpret-result", "theory", "interpretation_log.md", parent=t_id
        )
        prop_id = store_simple("propose-experiment", "proposal", "proposal.md")

        # Store a solution with parent_theory
        d_sol = self.test_dir / "seed_solution"
        d_sol.mkdir(parents=True, exist_ok=True)
        (d_sol / "solution.md").write_text("Seed solution")
        sol_id = (
            self.run_cmd(
                "store_results",
                "--from_agent_type",
                "execute-proposal",
                "--from_folder",
                str(d_sol),
                "--parent_theory",
                t_id,
            )
            .stdout.strip()
            .split()[-1]
        )

        target_agents = [
            ("write-theory", {"--from_exploration": e_id, "--from_literature": l_id}),
            ("falsify-hypothesis", {"--from_theory": t_id}),
            ("refine-hypothesis", {"--from_theory": t_id, "--from_review": r_id}),
            ("review-theory", {"--from_theory": t_id}),
            ("review-adherence", {"--from_theory": t_id}),
            ("improve-adherence", {"--from_theory": t_id, "--from_review": r_id}),
            ("suggest-expansions", {"--from_theory": t_id}),
            ("expand-theory", {"--from_theory": t_id, "--from_review": r_id}),
            ("predict-experiments", {"--from_theory": t_id, "--from_experiment": x_id}),
            (
                "rank-predictions",
                {"--from_experiment": x_id, "--from_prediction": p_id},
            ),
            ("rank-experiments", {"--from_theory": t_id}),
            ("score-theory-local-subscores", {"--from_theory": t_id}),
            ("rank-explanatory-power", {"--from_theory": t_id}),
            ("polish-theory", {"--from_theory": t_id}),
            ("streamline-theory", {"--from_theory": t_id}),
            ("edit-theory", {"--from_theory": t_id}),
            ("write-different-theory", {"--from_theory": t_id}),
            (
                "interpret-result",
                {"--from_theory": t_parent_id, "--from_experiment": x_id},
            ),
            ("integrate-interpretations", {"--from_theory": t_id}),
            ("propose-experiment", {"--from_theory": t_parent_id}),
            ("rank-proposals", {"--from_proposal": prop_id}),
            ("execute-proposal", {"--from_proposal": prop_id}),
            ("score-theory-solutions", {"--from_solution": sol_id}),
            ("initialize-theories", {}),
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
            # Basic sanity check: target folder should not be empty (unless initialize-theories)
            if agent != "initialize-theories":
                self.assertTrue(any(target_folder.iterdir()))
            if agent == "score-theory-solutions":
                parent_theory_folder = target_folder / "theories" / t_id
                self.assertTrue(parent_theory_folder.is_dir())
                self.assertTrue((parent_theory_folder / "theory.md").exists())

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
            "tags:quantum,gravity,test",
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

    def test_rescore_decay(self):
        """Verify that rescore_theories decays remaining theories correctly."""
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

        t1 = store_t("Theory 1")
        t2 = store_t("Theory 2")

        # Set initial scores by rescoring them both
        scores = {
            t1: {"score": 1.0},
            t2: {"score": 1.0},
        }
        self.run_cmd("rescore_theories", json.dumps(scores))

        # Rescore only t1 with a default decay rate (0.2), which multiplies remaining (t2) by 1.0 - 0.2 = 0.8
        self.run_cmd("rescore_theories", json.dumps({t1: {"score": 1.0}}))

        res = self.run_cmd("list", "--type", "theory", "--sort_by", "score", "--json")
        entries = {e["id"]: e["score"] for e in json.loads(res.stdout)}
        self.assertAlmostEqual(entries[t2], 0.8)

        # Rescore only t1 again, with an explicit decay_rate of 0.4, which multiplies remaining (t2) by 1.0 - 0.4 = 0.6
        # t2's score becomes 0.8 * 0.6 = 0.48
        self.run_cmd(
            "rescore_theories", "--decay_rate", "0.4", json.dumps({t1: {"score": 1.0}})
        )

        res = self.run_cmd("list", "--type", "theory", "--sort_by", "score", "--json")
        entries = {e["id"]: e["score"] for e in json.loads(res.stdout)}
        self.assertAlmostEqual(entries[t2], 0.48)

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

        # 3. Solution
        sol_dir = self.test_dir / "sol_src_fetch"
        sol_dir.mkdir()
        (sol_dir / "solution.md").write_text("Solution text")
        res = self.run_cmd(
            "store_results",
            "--from_agent_type",
            "generate-solution",
            "--from_folder",
            str(sol_dir),
        )
        u_id = res.stdout.strip().split()[-1]

        self.run_cmd(
            "fetch_solution",
            "--target_folder",
            str(target),
            "--from_solution",
            u_id,
        )
        self.assertTrue((target / "solutions" / u_id / "solution.md").exists())

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
        self.assertIn("population", data)
        population = data["population"]
        self.assertIn("organisms", population)
        self.assertEqual(len(population["organisms"]), 1)

    def test_summarize_research(self):
        """Verify context population and storage for summarize-research."""
        self.run_cmd("init")

        # 1. Helper to store a theory
        def store_t(name, parent=None):
            d = self.test_dir / f"theory_{name}"
            d.mkdir(parents=True, exist_ok=True)
            (d / "theory.md").write_text(f"Theory content for {name}")
            args = [
                "store_results",
                "--from_agent_type",
                "write-theory",
                "--from_folder",
                str(d),
            ]
            if parent:
                args += ["--parent_theory", parent]
            res = self.run_cmd(*args)
            return res.stdout.strip().split()[-1]

        # 2. Helper to store a review
        def store_r(agent_type, t_id):
            d = self.test_dir / f"review_{agent_type}_{t_id}"
            d.mkdir(parents=True, exist_ok=True)
            (d / "review.md").write_text(f"Review by {agent_type} for {t_id}")
            res = self.run_cmd(
                "store_results",
                "--from_agent_type",
                agent_type,
                "--from_folder",
                str(d),
                "--parent_theory",
                t_id,
            )
            return res.stdout.strip().split()[-1]

        # Seed theories
        t1 = store_t("T1")  # Will have score 0.9, is_leaf_node=True
        t2 = store_t("T2")  # Will have score 0.1, is_leaf_node=False
        t3 = store_t("T3")  # Will have score 0.0, is_leaf_node=True
        t4 = store_t("T4")  # Will have score 0.0, is_leaf_node=False (has child t7)
        t5 = store_t("T5")  # Will have score None, is_leaf_node=True
        t6 = store_t("T6")  # Will have score None, is_leaf_node=False (has child t8)

        # Store children to make t4 and t6 non-leaf nodes
        t7 = store_t("T7", parent=t4)
        t8 = store_t("T8", parent=t6)

        # Add reviews to create leaf node structure or just satisfy requirements
        r1_falsify = store_r("falsify-hypothesis", t1)
        r1_adherence = store_r("review-adherence", t1)
        # Note: suggest-expansions reviews should NOT be copied under reviews/
        r1_suggest = store_r("suggest-expansions", t1)

        store_r("falsify-hypothesis", t3)
        store_r("falsify-hypothesis", t5)

        # Rescore theories to set explicit scores and leaf node statuses in the population
        scores = {
            t1: {"score": 0.9, "is_viable": True},
            t2: {"score": 0.1, "is_viable": True},
            t3: {"score": 0.0, "is_viable": True},
            t4: {"score": 0.0, "is_viable": True},
            t5: {"score": None, "is_viable": True},
            t7: {"score": 0.0, "is_viable": True},
            t8: {"score": None, "is_viable": True},
        }
        self.run_cmd("rescore_theories", json.dumps(scores))

        # 3. Create context for summarize-research
        target_folder = self.test_dir / "summarize_context"
        self.run_cmd(
            "create_context",
            "--for_agent_type",
            "summarize-research",
            "--target_folder",
            str(target_folder),
        )

        self.assertTrue(target_folder.is_dir())
        theory_list_file = target_folder / "theory_list.json"
        self.assertTrue(theory_list_file.is_file())

        top_theories = json.loads(theory_list_file.read_text())
        top_ids = [t["id"] for t in top_theories]

        # Verify filtering and descending score order:
        # Expected: T1 (0.9), T2 (0.1), and then leaf nodes T3 (0.0) and T5 (None)
        # Excluded: T4 (0.0, not leaf) and T6 (None, not leaf)
        self.assertIn(t1, top_ids)
        self.assertIn(t2, top_ids)
        self.assertIn(t3, top_ids)
        self.assertIn(t5, top_ids)
        self.assertNotIn(t4, top_ids)
        self.assertNotIn(t6, top_ids)

        # Verify sort order: T1 first, then T2
        self.assertEqual(top_ids[0], t1)
        self.assertEqual(top_ids[1], t2)

        # Verify that directories for T1, T2, T3, T5 exist
        for tid in [t1, t2, t3, t5]:
            self.assertTrue((target_folder / "theories" / tid).is_dir())
            self.assertTrue((target_folder / "theories" / tid / "theory.md").is_file())

        # Verify T1 reviews subfolder contents
        t1_reviews_dir = target_folder / "theories" / t1 / "reviews"
        self.assertTrue(t1_reviews_dir.is_dir())
        # Should copy falsify-hypothesis and review-adherence
        self.assertTrue((t1_reviews_dir / r1_falsify / "review.md").is_file())
        self.assertTrue((t1_reviews_dir / r1_adherence / "review.md").is_file())
        # Should NOT copy suggest-expansions review
        self.assertFalse((t1_reviews_dir / r1_suggest).exists())

        # 4. Test storing summarize-research results (summary.md)
        summary_src = self.test_dir / "summary_src"
        summary_src.mkdir(parents=True, exist_ok=True)
        (summary_src / "summary.md").write_text(
            "# Research Summary Report\nThis is a summary."
        )

        res_store = self.run_cmd(
            "store_results",
            "--from_agent_type",
            "summarize-research",
            "--from_folder",
            str(summary_src),
        )
        s_id = res_store.stdout.strip().split()[-1]
        self.assertTrue(s_id.startswith("S_"))

        # Check metadata
        meta_file = self.db_path / "summary" / s_id / "metadata.json"
        self.assertTrue(meta_file.is_file())
        meta = json.loads(meta_file.read_text())
        self.assertEqual(meta["id"], s_id)
        self.assertEqual(meta["category"], "summary")
        self.assertEqual(meta["agent_type"], "summarize-research")
        self.assertEqual(meta["headline"], "Research Summary Report")
        self.assertIsNone(meta.get("parent_theory"))

    def test_summarize_goal_progress(self):
        """Verify context population and storage for summarize-goal-progress."""
        self.run_cmd("init")

        # Helpers
        def store_t(name):
            d = self.test_dir / f"theory_{name}"
            d.mkdir(parents=True, exist_ok=True)
            (d / "theory.md").write_text(f"Theory content for {name}")
            res = self.run_cmd(
                "store_results",
                "--from_agent_type",
                "write-theory",
                "--from_folder",
                str(d),
            )
            return res.stdout.strip().split()[-1]

        def store_s(name, parent_id):
            d = self.test_dir / f"solution_{name}"
            d.mkdir(parents=True, exist_ok=True)
            (d / "solution.md").write_text(f"Solution content for {name}")
            res = self.run_cmd(
                "store_results",
                "--from_agent_type",
                "execute-proposal",
                "--from_folder",
                str(d),
                "--parent_theory",
                parent_id,
            )
            return res.stdout.strip().split()[-1]

        # 1. Store theories
        t1 = store_t("T1")  # score 0.9, no solution
        t2 = store_t("T2")  # score 0.85, has solution
        t3 = store_t("T3")  # score 0.7, has solution

        # 2. Rescore them
        scores = {
            t1: {"score": 0.9, "is_viable": True},
            t2: {"score": 0.85, "is_viable": True},
            t3: {"score": 0.7, "is_viable": True},
        }
        self.run_cmd("rescore_theories", json.dumps(scores))

        # 3. Store solutions
        sol2 = store_s("Sol2", t2)
        sol3 = store_s("Sol3", t3)
        self.assertIsNotNone(sol3)

        # 4. Create context for summarize-goal-progress
        target_folder = self.test_dir / "goal_progress_context"
        self.run_cmd(
            "create_context",
            "--for_agent_type",
            "summarize-goal-progress",
            "--target_folder",
            str(target_folder),
        )

        self.assertTrue(target_folder.is_dir())
        self.assertTrue((target_folder / "theory" / "theory.md").is_file())
        self.assertTrue((target_folder / "solution" / "solution.md").is_file())

        info_file = target_folder / "info.json"
        self.assertTrue(info_file.is_file())
        info_data = json.loads(info_file.read_text())
        self.assertEqual(info_data["theory_id"], t2)
        self.assertEqual(info_data["solution_id"], sol2)

        # 5. Test storing summarize-goal-progress results (summary.md)
        summary_src = self.test_dir / "goal_summary_src"
        summary_src.mkdir(parents=True, exist_ok=True)
        (summary_src / "summary.md").write_text(
            "# Goal Progress Summary\nThis is a progress summary."
        )

        res_store = self.run_cmd(
            "store_results",
            "--from_agent_type",
            "summarize-goal-progress",
            "--from_folder",
            str(summary_src),
        )
        s_id = res_store.stdout.strip().split()[-1]
        self.assertTrue(s_id.startswith("S_"))

        # Check metadata
        meta_file = self.db_path / "summary" / s_id / "metadata.json"
        self.assertTrue(meta_file.is_file())
        meta = json.loads(meta_file.read_text())
        self.assertEqual(meta["id"], s_id)
        self.assertEqual(meta["category"], "summary")
        self.assertEqual(meta["agent_type"], "summarize-goal-progress")
        self.assertEqual(meta["headline"], "Goal Progress Summary")
        self.assertIsNone(meta.get("parent_theory"))

    def test_record_and_sample_solutions(self):
        """Verify recording solutions and sampling theories with latest_solution field."""
        self.run_cmd("init")

        # 1. Create and store a theory
        theory_dir = self.test_dir / "t_sol_test"
        theory_dir.mkdir(parents=True, exist_ok=True)
        (theory_dir / "theory.md").write_text("# Sol Test Theory")
        t_id = (
            self.run_cmd(
                "store_results",
                "--from_agent_type",
                "write-theory",
                "--from_folder",
                str(theory_dir),
            )
            .stdout.strip()
            .split()[-1]
        )

        # 2. Create and store a solution with that theory as parent
        sol_dir = self.test_dir / "s_sol_test"
        sol_dir.mkdir(parents=True, exist_ok=True)
        (sol_dir / "solution.md").write_text("# Solution candidate")
        sol_id = (
            self.run_cmd(
                "store_results",
                "--from_agent_type",
                "execute-proposal",
                "--from_folder",
                str(sol_dir),
                "--parent_theory",
                t_id,
            )
            .stdout.strip()
            .split()[-1]
        )

        # 3. Rescore the theory to make it sampleable under "scoring"
        scores = {t_id: {"score": 0.85, "is_viable": True}}
        self.run_cmd("rescore_theories", json.dumps(scores))

        # 4. Sample the theory with "scoring" purpose and check results
        res = self.run_cmd(
            "sample_theories",
            "--num_theories",
            "1",
            "--purpose",
            "scoring",
            "--json",
        )
        sampled = json.loads(res.stdout)
        self.assertEqual(len(sampled), 1)
        self.assertEqual(sampled[0]["id"], t_id)
        self.assertEqual(sampled[0]["latest_solution"], sol_id)


if __name__ == "__main__":
    unittest.main()
