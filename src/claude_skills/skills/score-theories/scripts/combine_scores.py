import argparse
import json


def score_type(x):
    try:
        val = float(x)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Score must be a float, got '{x}'")
    if val < 0.0 or val > 1.0:
        raise argparse.ArgumentTypeError(
            f"Score must be between 0.0 and 1.0, got {val}"
        )
    return val


def main():
    parser = argparse.ArgumentParser(
        description="Combine theory subscores into an overall score."
    )
    parser.add_argument(
        "--theory_id",
        type=str,
        required=True,
        help="The theory being scored",
    )
    parser.add_argument(
        "--prediction_accuracy",
        type=score_type,
        required=True,
        help="Prediction Accuracy Score (0-1)",
    )
    parser.add_argument(
        "--prediction_coverage",
        type=score_type,
        required=True,
        help="Prediction Coverage Score (0-1)",
    )
    parser.add_argument(
        "--soundness", type=score_type, required=True, help="Soundness Score (0-1)"
    )
    parser.add_argument(
        "--explanatory_power",
        type=score_type,
        required=True,
        help="Explanatory Power Score (0-1)",
    )
    parser.add_argument(
        "--length", type=score_type, required=True, help="Length Score (0-1)"
    )
    parser.add_argument(
        "--adherence",
        type=score_type,
        required=True,
        help="Guidance Adherence Score (0-1)",
    )

    args = parser.parse_args()

    correctness_part = 0.1 + 0.6 * args.prediction_accuracy + 0.3 * args.soundness
    power_part = (
        0.3
        + (0.4 * args.explanatory_power + 0.3 * args.prediction_coverage) * args.length
    )
    adherence_part = 0.5 + 0.5 * args.adherence
    overall_score = correctness_part * power_part * adherence_part

    output = {
        args.theory_id: {
            "score": round(overall_score, 2),
            "prediction_accuracy": args.prediction_accuracy,
            "prediction_coverage": args.prediction_coverage,
            "soundness": args.soundness,
            "explanatory_power": args.explanatory_power,
            "length": args.length,
            "adherence": args.adherence,
        }
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
