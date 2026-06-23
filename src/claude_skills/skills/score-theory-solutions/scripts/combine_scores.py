import argparse
import json


def calculate_linear_score(r: int, n: int) -> float:
    if n == 0:
        return 0.0
    return (n - r + 1) / n


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

    args = parser.parse_args()

    if args.verification_adherence < 0.0 or args.verification_adherence > 1.0:
        raise ValueError("verification_adherence must be between 0.0 and 1.0")

    solution_score = calculate_linear_score(args.solution_rank, args.n)
    overall_score = solution_score * args.verification_adherence

    output = {
        args.theory_id: {
            "score": round(overall_score, 2),
            "solution": round(solution_score, 2),
            "verification_adherence": round(args.verification_adherence, 2),
        }
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
