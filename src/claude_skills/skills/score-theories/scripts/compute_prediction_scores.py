import argparse


def calculate_linear_score(r, n):
    if n == 0:
        return 0
    return (n - r + 1) / n


def calculate_reciprocal_score(r, n):
    # This is the "normalized reciprocal score"
    if n == 0 or r == 0:
        return 0
    return (n - r + 1) / (r * n)


def main():
    parser = argparse.ArgumentParser(description="Compute prediction scores.")
    parser.add_argument(
        "--theory_id",
        type=str,
        required=True,
        help="The theory being scored",
    )
    parser.add_argument(
        "-n", type=int, required=True, help="Total number of theories being scored."
    )
    parser.add_argument(
        "--ranks",
        required=True,
        help="Comma-separated list of prediction ranks in each experiment, sorted from most to least important (e.g., '1,2,NO_PREDICTION,1').",
    )

    args = parser.parse_args()

    # Parse ranks
    rank_strings = [r.strip().lower() for r in args.ranks.split(",")]
    m = len(rank_strings)

    if m == 0:
        print(f"{args.theory_id} prediction_accuracy_score", 1.0)
        print(f"{args.theory_id} prediction_coverage_score", 1.0)
        return

    # Calculate experiment importance scores (linear method)
    # I_i = (m - i + 1) / m where i is 1-indexed rank of experiment
    importances = [calculate_linear_score(i + 1, m) for i in range(m)]
    total_importance = sum(importances)

    weighted_accuracy_sum = 0.0
    covered_importance_sum = 0.0

    for i, r_str in enumerate(rank_strings):
        importance = importances[i]
        if r_str not in ("none", "no_prediction"):
            try:
                r = int(r_str)
                score = calculate_reciprocal_score(r, args.n)
                weighted_accuracy_sum += score * importance
                covered_importance_sum += importance
            except ValueError:
                raise ValueError(
                    f"Invalid rank value: '{r_str}'. Must be an integer or 'NO_PREDICTION'."
                )

    accuracy_score = 0.0
    if covered_importance_sum > 0:
        accuracy_score = weighted_accuracy_sum / covered_importance_sum

    coverage_score = 0.0
    if total_importance > 0:
        coverage_score = covered_importance_sum / total_importance

    print(f"{args.theory_id} prediction_accuracy_score:", round(accuracy_score, 2))
    print(f"{args.theory_id} prediction_coverage_score:", round(coverage_score, 2))


if __name__ == "__main__":
    main()
