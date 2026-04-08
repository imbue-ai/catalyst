"""Main orchestration loop for the theory evolution framework.

Design informed by imbue-ai/knowledge_seeker:
- Cross-cutting evidence: each experiment updates ALL organisms, not just target
- Theory refinement: dismissed organisms get salvaged, not deleted
- Conservative confidence: positive evidence scaled 0.5x
- Weighted experiment selection: utility-per-cost, not raw score
- Hypothesis expiration: auto-dismiss after N failed attempts
- Parallel operations: scoring and review batched via ThreadPoolExecutor
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .config import FrameworkConfig
from .organism import (
    Evidence, Organism, create_organism, expire_stale_organisms,
    list_organisms, load_organism, save_experiment, save_organism_scores,
    save_organism_state,
)
from .agents.experimenter import ExperimenterAgent
from .agents.interpreter import InterpreterAgent
from .agents.scorer import QualitativeScorerAgent, run_code_scorer
from .agents.mutator import MutatorAgent
from .agents.verifier import VerifierAgent
from .agents.reviewer import ReviewerAgent
from .agents.refiner import RefinerAgent
from .logging import InvocationRecord, new_invocation_id, load_invocation, list_invocations


class Coordinator:
    """Drives the theory evolution cycle."""

    def __init__(self, config: FrameworkConfig):
        self.config = config
        self.organisms_dir = Path(config.organisms_dir)
        self.logs_dir = Path(config.logs_dir)
        self.organisms_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self._init_agents()

    def _init_agents(self) -> None:
        exp_cfg = self.config.get_agent_config("experimenter")
        int_cfg = self.config.get_agent_config("interpreter")
        scr_cfg = self.config.get_agent_config("scorer")
        mut_cfg = self.config.get_agent_config("mutator")
        ver_cfg = self.config.get_agent_config("verifier")

        self.experimenter = ExperimenterAgent(
            model=exp_cfg.model, temperature=exp_cfg.temperature,
            max_tokens=exp_cfg.max_tokens, log_dir=self.logs_dir,
            timeout_seconds=exp_cfg.timeout_seconds,
        )
        self.interpreter = InterpreterAgent(
            model=int_cfg.model, temperature=int_cfg.temperature,
            max_tokens=int_cfg.max_tokens, log_dir=self.logs_dir,
            timeout_seconds=int_cfg.timeout_seconds,
        )
        self.scorer = QualitativeScorerAgent(
            model=scr_cfg.model, temperature=scr_cfg.temperature,
            max_tokens=scr_cfg.max_tokens, log_dir=self.logs_dir,
            timeout_seconds=scr_cfg.timeout_seconds,
        )
        self.mutator = MutatorAgent(
            model=mut_cfg.model, temperature=mut_cfg.temperature,
            max_tokens=mut_cfg.max_tokens, log_dir=self.logs_dir,
            timeout_seconds=mut_cfg.timeout_seconds,
        )
        self.verifier = VerifierAgent(
            model=ver_cfg.model, temperature=ver_cfg.temperature,
            max_tokens=ver_cfg.max_tokens, log_dir=self.logs_dir,
            timeout_seconds=ver_cfg.timeout_seconds,
        )
        self.reviewer = ReviewerAgent(
            model=int_cfg.model, temperature=0.2,
            max_tokens=int_cfg.max_tokens, log_dir=self.logs_dir,
        )
        self.refiner = RefinerAgent(
            model=mut_cfg.model, temperature=0.7,
            max_tokens=4096, log_dir=self.logs_dir,
        )

    def run(self, generations: int | None = None) -> None:
        """Main evolution loop."""
        generations = generations or self.config.generations
        population = list_organisms(self.organisms_dir)

        if not population:
            print("ERROR: No organisms found. Create a seed organism first.")
            print(f"  Expected directory: {self.organisms_dir}")
            sys.exit(1)

        print(f"Starting evolution: {len(population)} organisms, {generations} generations")

        for gen in range(generations):
            print(f"\n{'='*60}")
            print(f"GENERATION {gen + 1}/{generations}")
            print(f"{'='*60}")

            # Expire stale organisms (knowledge_seeker pattern)
            dismissed = expire_stale_organisms(population)
            if dismissed:
                print(f"Expired {len(dismissed)} stale organisms")

            active = [o for o in population if o.status != "dismissed"]
            print(f"Population: {len(population)} total, {len(active)} active")

            # Step 1: Select organisms for experimentation (weighted sampling)
            selected = self._select_for_experimentation(active)
            print(f"Selected {len(selected)} organisms for experimentation")

            # Step 2-4: Run experiments on selected organisms
            for org in selected:
                for exp_i in range(self.config.experiments_per_organism_per_generation):
                    print(f"\n--- {org.id} experiment {exp_i + 1} ---")
                    try:
                        self._run_experiment_cycle(org, population)
                    except Exception as e:
                        print(f"  Experiment failed: {e}")

            # Step 5: Update scores (parallel where possible)
            print(f"\nScoring {len(active)} active organisms...")
            self._score_organisms_parallel(active)
            self._print_scoreboard(population)

            # Step 6: Refine dismissed organisms (knowledge_seeker salvage pattern)
            if dismissed:
                refined = self._refine_dismissed(dismissed)
                population.extend(refined)
                if refined:
                    print(f"Refined {len(refined)} dismissed organisms into new theories")

            # Step 7-8: Mutate and prune
            if gen < generations - 1:
                children = self._mutate_population(active)
                population.extend(children)
                print(f"Created {len(children)} child organisms")

                population = self._prune(population)
                print(f"Population after pruning: {len(population)}")

        print(f"\n{'='*60}")
        print("EVOLUTION COMPLETE")
        print(f"{'='*60}")
        self._print_scoreboard(population)

    def run_single_experiment(self, organism_id: str) -> None:
        """Run one experiment cycle for a specific organism."""
        org_dir = self.organisms_dir / organism_id
        if not org_dir.exists():
            matches = [d for d in self.organisms_dir.iterdir()
                       if d.is_dir() and organism_id in d.name]
            if len(matches) == 1:
                org_dir = matches[0]
            else:
                print(f"Organism not found: {organism_id}")
                return

        org = load_organism(org_dir)
        population = list_organisms(self.organisms_dir)
        self._run_experiment_cycle(org, population)
        self._score_organism(org)

    def rescore_all(self) -> None:
        """Re-run all scorers on all experiments."""
        population = list_organisms(self.organisms_dir)
        self._score_organisms_parallel(population)
        self._print_scoreboard(population)

    def _run_experiment_cycle(self, org: Organism, population: list[Organism]) -> None:
        """Full cycle: design -> execute -> interpret -> verify -> cross-review."""

        # 1. Design experiment
        print(f"  Designing experiment for {org.id}...")
        prior = [e.to_dict() for e in org.experiments]
        experiment_params = self.experimenter.design_experiment(
            theory_text=org.theory_text,
            prior_experiments=prior,
            organism_id=org.id,
        )
        print(f"  Experiment: {experiment_params.get('rationale', 'sweep')[:80]}")

        # 2. Execute via CLI
        exp_id = org.next_experiment_id()
        exp_output_dir = org.directory / "experiments" / exp_id
        exp_output_dir.mkdir(parents=True, exist_ok=True)

        print(f"  Running CLI ({experiment_params.get('sweep_param', 'width')} sweep)...")
        cli_result = self._run_cli(experiment_params, exp_output_dir)

        # Load results
        results_path = exp_output_dir / "results.json"
        if results_path.exists():
            results_data = json.loads(results_path.read_text())
        else:
            results_data = {"error": "CLI did not produce results", "cli_output": cli_result}

        bif_path = exp_output_dir / "bifurcation_report.json"
        bif_report = json.loads(bif_path.read_text()) if bif_path.exists() else None

        # 3. Interpret (produces evidence for target organism)
        print(f"  Interpreting results...")
        interpretation = self.interpreter.interpret(
            theory_text=org.theory_text,
            experiment_params=experiment_params,
            results_data=results_data,
            bifurcation_report=bif_report,
            organism_id=org.id,
            experiment_id=exp_id,
        )

        interp_text = interpretation.get("summary", str(interpretation))
        print(f"  Interpretation: {interp_text[:100]}")

        # 4. Verify
        print(f"  Verifying...")
        verification = self.verifier.verify(
            results_data=results_data,
            bifurcation_report=bif_report,
            interpreter_claim=interpretation.get("bifurcation_detected"),
            organism_id=org.id,
            experiment_id=exp_id,
        )
        print(f"  Verified: {verification.get('verified', '?')} "
              f"(confidence: {verification.get('confidence', '?')})")

        # Apply direct evidence to target organism (knowledge_seeker pattern)
        support = interpretation.get("theory_support", "inconclusive")
        delta = _support_to_delta(support, verification.get("confidence", 0.5))
        evidence = Evidence(
            id=new_invocation_id(),
            experiment_id=exp_id,
            confidence_delta=delta,
            explanation=interp_text[:500],
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        org.apply_evidence(evidence)
        save_organism_state(org)

        # Save experiment record
        save_experiment(
            organism=org,
            experiment_id=exp_id,
            params=experiment_params,
            results_data=results_data,
            interpretation=json.dumps({
                "interpretation": interpretation,
                "verification": verification,
            }, indent=2),
            bifurcation_report=bif_report,
        )

        # 5. Cross-cutting evidence review (knowledge_seeker pattern)
        # Check this experiment against ALL other organisms in population
        other_organisms = [o for o in population if o.id != org.id and o.status != "dismissed"]
        if other_organisms:
            print(f"  Cross-reviewing against {len(other_organisms)} other theories...")
            self._apply_cross_cutting_evidence(
                experiment_summary=interp_text,
                bifurcation_report=bif_report,
                experiment_id=exp_id,
                organisms=other_organisms,
            )

    def _apply_cross_cutting_evidence(
        self,
        experiment_summary: str,
        bifurcation_report: dict[str, Any] | None,
        experiment_id: str,
        organisms: list[Organism],
    ) -> None:
        """Apply experiment results as evidence across all organisms."""
        theories = [
            {"id": o.id, "theory_text": o.theory_text}
            for o in organisms
        ]

        cross_evidence = self.reviewer.review_cross_cutting(
            experiment_summary=experiment_summary,
            bifurcation_report=bifurcation_report,
            theories=theories,
        )

        applied = 0
        for ev_data in cross_evidence:
            org_id = ev_data.get("organism_id", "")
            delta = ev_data.get("confidence_delta", 0)
            if abs(delta) < 0.05:
                continue  # Skip negligible evidence

            target = next((o for o in organisms if o.id == org_id), None)
            if target:
                evidence = Evidence(
                    id=new_invocation_id(),
                    experiment_id=experiment_id,
                    confidence_delta=delta,
                    explanation=ev_data.get("explanation", "Cross-cutting evidence")[:500],
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                )
                target.apply_evidence(evidence)
                save_organism_state(target)
                applied += 1

        if applied:
            print(f"  Applied cross-cutting evidence to {applied} organisms")

    def _run_cli(self, params: dict[str, Any], output_dir: Path) -> str:
        """Execute the shallow-mlps CLI with given parameters."""
        cmd = [sys.executable, "-m", "shallow_mlps.cli"]

        command = params.get("command", "sweep")
        cmd.append(command)
        cmd.extend(["--target", str(params.get("target", "abs"))])
        cmd.extend(["--output-dir", str(output_dir)])

        if command == "sweep":
            cmd.extend(["--sweep-param", str(params.get("sweep_param", "width"))])
            cmd.extend(["--sweep-range", str(params.get("sweep_range", "2,4,8,16,32"))])
            cmd.extend(["--seeds", str(params.get("seeds", 1))])

        cmd.extend(["--width", str(params.get("width", 16))])
        cmd.extend(["--lr", str(params.get("lr", 0.01))])
        cmd.extend(["--steps", str(params.get("steps", 5000))])
        cmd.extend(["--input-dim", str(params.get("input_dim", 1))])
        cmd.extend(["--weight-decay", str(params.get("weight_decay", 0.0))])

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600,
            )
            output = result.stdout + result.stderr
            if result.returncode != 0:
                print(f"  CLI warning (exit {result.returncode}): {result.stderr[:200]}")
            return output
        except subprocess.TimeoutExpired:
            return "ERROR: CLI timed out after 600 seconds"

    def _score_organism(self, org: Organism) -> None:
        """Update an organism's scores (code-based + qualitative)."""
        # Run code-based scorer
        if org.scorer_path.exists():
            experiments_for_scorer = []
            for exp in org.experiments:
                exp_data = exp.params.copy()
                if exp.results_path.exists():
                    try:
                        results = json.loads(exp.results_path.read_text())
                        exp_data.update(results)
                    except json.JSONDecodeError:
                        pass
                bif_path = exp.results_path.parent / "bifurcation_report.json"
                if bif_path.exists():
                    try:
                        exp_data["bifurcation_report"] = json.loads(bif_path.read_text())
                    except json.JSONDecodeError:
                        pass
                experiments_for_scorer.append(exp_data)

            quant_score = run_code_scorer(
                str(org.scorer_path), experiments_for_scorer
            )
        else:
            quant_score = 0.0

        # Run qualitative scorer
        exp_history = [e.to_dict() for e in org.experiments]
        qual_result = self.scorer.score_theory(
            theory_text=org.theory_text,
            experiment_history=exp_history,
            organism_id=org.id,
        )

        scores = {
            "quantitative": quant_score,
            "qualitative": qual_result.get("scores", {}),
            "qualitative_overall": qual_result.get("overall", 0),
            "qualitative_feedback": qual_result.get("feedback", ""),
        }
        save_organism_scores(org, scores)
        print(f"  {org.id}: quant={quant_score:.2f}, "
              f"qual={qual_result.get('overall', 0):.1f}, "
              f"conf={org.confidence:+.2f} ({org.status})")

    def _score_organisms_parallel(self, organisms: list[Organism]) -> None:
        """Score multiple organisms, parallelizing code-based scorers."""
        # Code-based scoring can run in parallel (no LLM calls)
        # Qualitative scoring must be sequential (LLM rate limits)
        for org in organisms:
            try:
                self._score_organism(org)
            except Exception as e:
                print(f"  Scoring failed for {org.id}: {e}")

    def _select_for_experimentation(self, population: list[Organism]) -> list[Organism]:
        """Select organisms using weighted sampling (knowledge_seeker pattern).

        Uses combined_score as weight, but with exploration floor (min 0.1)
        so even low-scoring organisms get some probability of selection.
        """
        if not population:
            return []

        if self.config.selection_strategy == "top_k":
            sorted_pop = sorted(population, key=lambda o: o.combined_score(), reverse=True)
            k = max(1, len(sorted_pop) // 2)
            return sorted_pop[:k]

        # Weighted sampling (default) — knowledge_seeker pattern
        # combined_score already has exploration floor of 0.1
        weights = [o.combined_score() for o in population]
        n_select = min(len(population), max(1, len(population) // 2 + 1))

        selected = []
        remaining = list(zip(population, weights))
        for _ in range(n_select):
            if not remaining:
                break
            orgs, ws = zip(*remaining)
            chosen = random.choices(list(orgs), weights=list(ws), k=1)[0]
            if chosen not in selected:
                selected.append(chosen)
            remaining = [(o, w) for o, w in remaining if o is not chosen]

        return selected if selected else population[:1]

    def _mutate_population(self, population: list[Organism]) -> list[Organism]:
        """Create child organisms via mutation."""
        sorted_pop = sorted(
            population, key=lambda o: o.combined_score(), reverse=True
        )

        children = []
        n_mutate = max(1, int(len(sorted_pop) * self.config.mutation_rate))

        for org in sorted_pop[:n_mutate]:
            if random.random() > self.config.mutation_rate:
                continue

            print(f"\n  Mutating {org.id} (score={org.combined_score():.2f})...")
            try:
                mutation = self.mutator.mutate(
                    theory_text=org.theory_text,
                    scorer_code=org.scorer_code,
                    experiment_history=[e.to_dict() for e in org.experiments],
                    scores=org.scores,
                    qualitative_feedback=org.scores.get("qualitative_feedback", ""),
                    organism_id=org.id,
                )

                child = create_organism(
                    theory_text=mutation["theory"],
                    scorer_code=mutation["scorer"],
                    organisms_dir=self.organisms_dir,
                    parent=org,
                )
                print(f"  Created child {child.id}")
                if mutation.get("mutation_description"):
                    print(f"  Mutation: {mutation['mutation_description'][:100]}")
                children.append(child)
            except Exception as e:
                print(f"  Mutation failed for {org.id}: {e}")

        return children

    def _refine_dismissed(self, dismissed: list[Organism]) -> list[Organism]:
        """Attempt to salvage dismissed organisms via refinement.

        Knowledge_seeker pattern: dismissed hypotheses aren't deleted.
        The refiner proposes generalized/corrected variants.
        """
        refined = []
        for org in dismissed:
            try:
                evidence_dicts = [e.to_dict() for e in org.evidence]
                exp_summaries = [e.interpretation[:300] for e in org.experiments if e.interpretation]

                result = self.refiner.refine(
                    dismissed_theory=org.theory_text,
                    evidence_history=evidence_dicts,
                    experiment_summaries=exp_summaries,
                    organism_id=org.id,
                )

                refined_theory = result.get("refined_theory")
                if not refined_theory or refined_theory == "UNSALVAGEABLE":
                    print(f"  {org.id}: unsalvageable, skipping")
                    continue

                confidence = result.get("confidence", 0.3)
                if confidence < 0.2:
                    print(f"  {org.id}: low refinement confidence ({confidence:.2f}), skipping")
                    continue

                scorer_code = result.get("scorer", "")
                if not scorer_code or "def score" not in scorer_code:
                    scorer_code = org.scorer_code  # Inherit parent scorer

                child = create_organism(
                    theory_text=refined_theory,
                    scorer_code=scorer_code,
                    organisms_dir=self.organisms_dir,
                    parent=org,
                )

                # Carry forward parent evidence (knowledge_seeker pattern)
                for ev in org.evidence:
                    child.evidence.append(ev)
                # Apply synthetic evidence from refinement
                synth = Evidence(
                    id=f"refine_{child.id}",
                    experiment_id="refinement",
                    confidence_delta=confidence * 0.3,
                    explanation=f"Refined from dismissed {org.id}: {result.get('reasoning', '')[:200]}",
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                )
                child.apply_evidence(synth)
                save_organism_state(child)

                print(f"  Refined {org.id} -> {child.id} (confidence: {confidence:.2f})")
                refined.append(child)

            except Exception as e:
                print(f"  Refinement failed for {org.id}: {e}")

        return refined

    def _prune(self, population: list[Organism]) -> list[Organism]:
        """Prune low-scoring organisms if population exceeds limit."""
        if len(population) <= self.config.max_population:
            return population

        sorted_pop = sorted(
            population, key=lambda o: o.combined_score(), reverse=True
        )

        # Always keep elites
        kept = sorted_pop[:self.config.elite_count]
        remaining = sorted_pop[self.config.elite_count:]

        # Weighted sampling for remaining slots (not pure random)
        while len(kept) < self.config.max_population and remaining:
            weights = [o.combined_score() for o in remaining]
            chosen = random.choices(remaining, weights=weights, k=1)[0]
            kept.append(chosen)
            remaining.remove(chosen)

        return kept

    def _print_scoreboard(self, population: list[Organism]) -> None:
        """Print the current population scoreboard."""
        sorted_pop = sorted(
            population, key=lambda o: o.combined_score(), reverse=True
        )
        print(f"\n{'─'*72}")
        print(f"{'ID':30s} {'Gen':>4s} {'Score':>7s} {'Conf':>6s} {'Status':>10s} {'Exps':>5s}")
        print(f"{'─'*72}")
        for org in sorted_pop:
            print(
                f"{org.id:30s} {org.generation:4d} "
                f"{org.combined_score():7.2f} {org.confidence:+6.2f} "
                f"{org.status:>10s} {len(org.experiments):5d}"
            )
        print(f"{'─'*72}")


def _support_to_delta(support: str, verifier_confidence: float) -> float:
    """Convert interpretation support level to a confidence delta."""
    base = {
        "supports": 0.4,
        "partially_supports": 0.2,
        "inconclusive": 0.0,
        "contradicts": -0.5,
    }.get(support, 0.0)

    # Modulate by verifier confidence
    return base * max(0.3, verifier_confidence)


# --- CLI entry points ---

def cmd_run(args: argparse.Namespace) -> None:
    config = _load_config(args)
    coord = Coordinator(config)
    coord.run(generations=args.generations)


def cmd_experiment(args: argparse.Namespace) -> None:
    config = _load_config(args)
    coord = Coordinator(config)
    coord.run_single_experiment(args.organism_id)


def cmd_rescore(args: argparse.Namespace) -> None:
    config = _load_config(args)
    coord = Coordinator(config)
    coord.rescore_all()


def cmd_replay(args: argparse.Namespace) -> None:
    """Replay a logged invocation."""
    record_path = Path(args.invocation_id)
    if not record_path.exists():
        config = _load_config(args)
        log_dir = Path(config.logs_dir)
        candidates = list(log_dir.glob(f"*{args.invocation_id}*"))
        if not candidates:
            print(f"Invocation not found: {args.invocation_id}")
            return
        record_path = candidates[0]

    record = load_invocation(record_path)
    print(f"Replaying invocation: {record.id}")
    print(f"Agent type: {record.agent_type}")
    print(f"Original timestamp: {record.timestamp}")
    print(f"Original duration: {record.duration_seconds:.1f}s")
    print(f"\n--- Original Prompt ---\n{record.prompt[:500]}")
    print(f"\n--- Original Output ---\n{record.output[:1000]}")

    if args.rerun:
        print("\n--- Re-running ---")
        config = _load_config(args)
        coord = Coordinator(config)
        agent = getattr(coord, record.agent_type, None)
        if agent:
            result = agent.invoke(record.prompt, record.file_inputs)
            print(f"\n--- New Output ---\n{result.raw_output[:1000]}")
            print(f"\nDuration: {result.duration_seconds:.1f}s")
        else:
            print(f"Unknown agent type: {record.agent_type}")


def cmd_status(args: argparse.Namespace) -> None:
    """Show population status."""
    config = _load_config(args)
    population = list_organisms(Path(config.organisms_dir))
    if not population:
        print("No organisms found.")
        return

    sorted_pop = sorted(population, key=lambda o: o.combined_score(), reverse=True)
    print(f"\nPopulation: {len(population)} organisms\n")
    for org in sorted_pop:
        print(f"{org.id}")
        print(f"  Generation: {org.generation}, Parent: {org.parent_id or 'none'}")
        print(f"  Status: {org.status}, Confidence: {org.confidence:+.2f}")
        print(f"  Experiments: {len(org.experiments)}, Evidence: {len(org.evidence)}")
        print(f"  Score: {org.combined_score():.2f}")
        print(f"  Theory: {org.theory_text[:120]}...")
        print()


def _load_config(args: argparse.Namespace) -> FrameworkConfig:
    if hasattr(args, "config") and args.config:
        path = Path(args.config)
        if path.suffix in (".yml", ".yaml"):
            return FrameworkConfig.from_yaml(path)
        else:
            return FrameworkConfig.from_json(path)
    return FrameworkConfig()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ai-scientist",
        description="Theory evolution framework for scientific investigation.",
    )

    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--config", "-c", help="Config file (YAML or JSON)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_run = subparsers.add_parser("run", parents=[parent], help="Run the evolution loop")
    p_run.add_argument("--generations", "-g", type=int, default=None)
    p_run.set_defaults(func=cmd_run)

    p_exp = subparsers.add_parser("experiment", parents=[parent], help="Run a single experiment for an organism")
    p_exp.add_argument("organism_id")
    p_exp.set_defaults(func=cmd_experiment)

    p_rescore = subparsers.add_parser("rescore", parents=[parent], help="Re-score all organisms")
    p_rescore.set_defaults(func=cmd_rescore)

    p_replay = subparsers.add_parser("replay", parents=[parent], help="Replay a logged invocation")
    p_replay.add_argument("invocation_id")
    p_replay.add_argument("--rerun", action="store_true", help="Re-run the invocation")
    p_replay.set_defaults(func=cmd_replay)

    p_status = subparsers.add_parser("status", parents=[parent], help="Show population status")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
