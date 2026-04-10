def score(experiments: list[dict]) -> float:
    """Score experiments against the width-complexity threshold theory.

    The theory predicts:
    1. Bifurcation occurs near width = K (number of kinks in target)
    2. Smooth targets don't bifurcate
    3. Below threshold: distributed representation; above: specialized
    """
    if not experiments:
        return 0.0

    total = 0.0
    count = 0

    for exp in experiments:
        bif_report = exp.get("bifurcation_report", {})
        sweep_param = exp.get("sweep_param", "")

        if sweep_param == "width":
            # Reward: bifurcation detected in width sweeps (core prediction)
            if bif_report.get("overall_detected"):
                total += 6.0

                # Extra reward if bifurcation point is at small width
                # (consistent with kink-count theory)
                for bp in bif_report.get("bifurcation_points", []):
                    pval = bp.get("param_value", 0)
                    if isinstance(pval, (int, float)) and pval <= 10:
                        total += 2.0  # Low-width bifurcation matches theory
            else:
                total += 1.0  # Partial credit for completed experiment

        elif sweep_param == "lr":
            # Learning rate sweeps are informative either way
            if bif_report.get("overall_detected"):
                total += 3.0  # LR can also trigger bifurcation
            else:
                total += 1.0

        else:
            total += 1.0  # Any completed experiment has some value

        # Reward low final loss (well-trained models are more informative)
        results = exp.get("results", {})
        if isinstance(results, dict):
            for pval_results in results.values():
                if isinstance(pval_results, dict):
                    for seed_result in pval_results.values():
                        if isinstance(seed_result, dict):
                            loss = seed_result.get("final_loss", 1.0)
                            if loss < 0.01:
                                total += 0.5

        count += 1

    return total / max(count, 1)
