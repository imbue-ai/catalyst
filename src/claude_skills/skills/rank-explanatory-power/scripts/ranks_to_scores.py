import argparse


def calculate_linear_score(r, n):
    return (n - r + 1) / n


def calculate_reciprocal_score(r, n):
    # This is the "normalized reciprocal score" from SKILL.md
    return (n - r + 1) / (r * n)


def main():
    parser = argparse.ArgumentParser(description="Convert ranks to scores.")
    parser.add_argument(
        "--score_type",
        choices=["linear", "reciprocal"],
        required=True,
        help="Type of score calculation.",
    )
    parser.add_argument(
        "-n", type=int, required=True, help="Total number of items ranked."
    )

    args = parser.parse_args()

    for r in range(1, args.n + 1):
        if args.score_type == "linear":
            score = calculate_linear_score(r, args.n)
        else:
            score = calculate_reciprocal_score(r, args.n)
        print(r, round(score, 2))


if __name__ == "__main__":
    main()
