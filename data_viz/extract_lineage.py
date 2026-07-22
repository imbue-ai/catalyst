import json
import re
import argparse
import pandas as pd


def extract_lineage(json_file, task_id, output_csv, population_file=None):
    try:
        with open(json_file, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{json_file}' not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Failed to parse JSON from '{json_file}'.")
        return

    population_scores = {}
    if population_file:
        try:
            with open(population_file, "r") as f:
                pop_data = json.load(f)
        except FileNotFoundError:
            print(f"Error: Population file '{population_file}' not found.")
            return
        except json.JSONDecodeError:
            print(f"Error: Failed to parse JSON from '{population_file}'.")
            return

        organisms = pop_data.get("population", {}).get("organisms", [])
        for org in organisms:
            o_info = org.get("organism")
            if isinstance(o_info, dict):
                tid = o_info.get("theory_id")
                eval_res = org.get("evaluation_result")
                if tid and isinstance(eval_res, dict) and "score" in eval_res:
                    population_scores[tid] = eval_res["score"]

    # Check structure of the JSON
    tasks = data.get("tasks", []) if isinstance(data, dict) else []
    target_task = None
    for t in tasks:
        if t.get("id") == task_id:
            target_task = t
            break

    if not target_task:
        print(f"Error: Task with ID '{task_id}' not found.")
        return

    steps = target_task.get("steps", [])

    # Step 1: Gather all scores from completed score-theories steps
    scores_map = {}
    for step in steps:
        stage = step.get("stage") or ""
        if "score-theories" in stage and step.get("status") == "completed":
            outputs = step.get("outputs") or {}
            for tid, val in outputs.items():
                if isinstance(val, dict) and "score" in val:
                    scores_map.setdefault(tid, []).append(val["score"])

    # Step 2: Extract theories and their origins
    theories = {}
    for step in steps:
        stage = step.get("stage") or ""
        outputs = step.get("outputs") or {}
        inputs = step.get("inputs") or {}

        # Initial generation
        if stage == "write-n-theories":
            tids = outputs.get("theory_ids") or []
            for tid in tids:
                theories[tid] = {
                    "Generation": 0,
                    "Iteration": 0,
                    "Generator": "root",
                    "Inputs": "",
                }

        # Mutation steps
        elif "mutate" in stage:
            # We match mutate-generator-iteration-index format
            match_type = re.search(r"mutate-([a-zA-Z\-]+)-(\d+)-\d+", stage)
            if match_type:
                gen_type = match_type.group(1)
                iter_num = int(match_type.group(2))

                tid = outputs.get("theory_id")
                if tid:
                    prompt = inputs.get("prompt") or ""
                    # find all theory IDs starting with T_
                    parent_ids = re.findall(r"T_\d{8}_\d{6}_[a-zA-Z0-9]+", prompt)
                    theories[tid] = {
                        "Generation": iter_num,
                        "Iteration": iter_num,
                        "Generator": gen_type,
                        "Inputs": ", ".join(parent_ids),
                    }

    # Step 3: Build list of records
    records = []
    # Sort by Iteration then Theory ID for clean chronological output
    for tid, info in sorted(theories.items(), key=lambda x: (x[1]["Iteration"], x[0])):
        sc = scores_map.get(tid, [])
        initial_score = sc[0] if len(sc) > 0 else ""
        if population_file:
            final_score = population_scores.get(tid, sc[-1] if len(sc) > 0 else "")
        else:
            final_score = sc[-1] if len(sc) > 0 else ""

        records.append(
            {
                "Theory": tid,
                "Title": "",
                "Generation": info["Generation"],
                "Iteration": info["Iteration"],
                "Generator": info["Generator"],
                "Inputs": info["Inputs"],
                "Initial score": initial_score,
                "Final score": final_score,
                "Correct idea?": "",
            }
        )

    # Step 4: Write to CSV using pandas
    df = pd.DataFrame(records)
    df.to_csv(output_csv, index=False)
    print(
        f"Successfully extracted lineage to '{output_csv}' ({len(records)} theories)."
    )
    if not population_file:
        print(
            "WARNING: Final score is based on the last score-theories step, not the actual score from the population. Hence, it does not consider score decay."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract theory lineage from a tasks_state JSON file."
    )
    parser.add_argument("json_file", help="Path to the JSON task state file.")
    parser.add_argument("task_id", help="ID of the research task to extract.")
    parser.add_argument(
        "-o",
        "--output",
        default="extracted_lineage.csv",
        help="Path to save the output CSV.",
    )
    parser.add_argument(
        "--population",
        help="Path to the population JSON file (optional).",
    )
    args = parser.parse_args()

    extract_lineage(
        args.json_file,
        args.task_id,
        args.output,
        population_file=args.population,
    )
