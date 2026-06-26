import argparse
import json
import os

PAST_PERFORMANCE_WEIGHT = float(
    os.environ.get("CATALYST_SCORING_PAST_PERFORMANCE_WEIGHT", 0.8)
)
FUTURE_POTENTIAL_WEIGHT = float(
    os.environ.get("CATALYST_SCORING_FUTURE_POTENTIAL_WEIGHT", 0.5)
)


def calculate_linear_score(r: int, n: int) -> float:
    if n == 0:
        return 0.0
    return (n - r + 1) / n


def calculate_reciprocal_score(r, n):
    if n == 0:
        return 0.0
    return (n - r + 1) / (r * n)


def main():
    parser = argparse.ArgumentParser(
        description="Compute and combine solution scores into a theory score."
    )
    parser.add_argument(
        "--theory_id",
        type=str,
        required=True,
        help="The theory being scored",
    )
    parser.add_argument(
        "--solution_rank",
        type=int,
        required=True,
        help="1-indexed rank of this solution among all compared solutions",
    )
    parser.add_argument(
        "-n",
        type=int,
        required=True,
        help="Total number of solutions being scored.",
    )
    parser.add_argument(
        "--verification_adherence",
        type=float,
        required=True,
        help="Verification adherence score (0.0 to 1.0)",
    )
    parser.add_argument(
        "--novelty_rank",
        type=int,
        required=False,
        help="1-indexed rank of this solution's parent theory's plan for next research steps among all compared theories",
    )

    args = parser.parse_args()

    if args.verification_adherence < 0.0 or args.verification_adherence > 1.0:
        raise ValueError("verification_adherence must be between 0.0 and 1.0")

    solution_score = calculate_linear_score(args.solution_rank, args.n)
    plan_novelty_score = (
        calculate_reciprocal_score(args.novelty_rank, args.n)
        if args.novelty_rank is not None
        else 0.0
    )
    past_performance_score = solution_score * args.verification_adherence
    future_potential_score = plan_novelty_score
    overall_score = (
        PAST_PERFORMANCE_WEIGHT * past_performance_score
        + (1.0 - PAST_PERFORMANCE_WEIGHT)
    ) * (
        FUTURE_POTENTIAL_WEIGHT * future_potential_score
        + (1.0 - FUTURE_POTENTIAL_WEIGHT)
    )

    output = {
        args.theory_id: {
            "score": round(overall_score, 2),
            "solution": round(solution_score, 2),
            "verification_adherence": round(args.verification_adherence, 2),
            "plan_novelty": round(plan_novelty_score, 2),
        }
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
