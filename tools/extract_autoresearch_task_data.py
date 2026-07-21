#!/usr/bin/env python3
"""
Task Data Extractor

This script parses a tasks_state.json file and extracts the validation Bits-Per-Byte (val_bpb)
evolution over iterations for a specific task. It compiles the results into a CSV file with columns:
1. Number of experiments/solutions (chronological run count)
2. iteration number (sequential iteration across main and addon loops)
3. min val_bpb (the lowest val_bpb recorded in that run)
4. result_id (the experiment or solution candidate ID)
"""

import argparse
import json
import os
import re
import sys

# Robust regex to capture val_bpb values while excluding deltas (e.g. d_val_bpb, delta_val_bpb)
val_bpb_re = re.compile(r'(?<![a-zA-Z_])val[_\s/-]?bpb\s*[=:]\s*(\d+\.\d+|\.\d+)', re.IGNORECASE)

def get_min_val_bpb(log_path):
    if not os.path.exists(log_path):
        return None, "File not found"
    
    with open(log_path, 'r', errors='ignore') as f:
        content = f.read()
        
    lines = content.split('\n')
    vals = []
    for line in lines:
        match = val_bpb_re.search(line)
        if match:
            val_str = match.group(1)
            try:
                vals.append(float(val_str))
            except ValueError:
                pass
                
    if not vals:
        return None, "No val_bpb values found"
        
    return min(vals), None

def parse_iteration(stage_name):
    # Determine if it belongs to an addon loop
    is_addon = 'addon-0' in stage_name
    
    # Search for standard iteration indicators
    match = re.search(r'(?:proposal|solution-candidate)-(\d+)-\d+', stage_name)
    if match:
        iter_num = int(match.group(1))
        if is_addon:
            return 50 + iter_num  # Offset addon-0 by 50 (main loop max iterations)
        return iter_num
    else:
        # Fallback numeric extraction
        numbers = re.findall(r'\d+', stage_name)
        if len(numbers) >= 2:
            if is_addon:
                iter_num = int(numbers[1])
                return 50 + iter_num
            else:
                return int(numbers[0])
        elif len(numbers) == 1:
            return int(numbers[0])
            
    return None

def extract_task_metrics(json_path, target_task_id, output_csv_path):
    print(f"Loading task state JSON from: {json_path}")
    if not os.path.exists(json_path):
        print(f"Error: JSON file '{json_path}' does not exist.", file=sys.stderr)
        return False
        
    with open(json_path, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Failed to parse JSON file. {e}", file=sys.stderr)
            return False

    tasks = data.get("tasks", [])
    target_task = None
    for t in tasks:
        if t.get("id") == target_task_id or t.get("task_id") == target_task_id:
            target_task = t
            break

    if not target_task:
        print(f"Error: Task ID '{target_task_id}' not found in the tasks list.", file=sys.stderr)
        return False

    print(f"Found Task: '{target_task.get('title')}'")
    env_folder = target_task.get("env_folder", "")
    
    # Resolve the workspace and .ai-scientist-db paths
    json_dir = os.path.dirname(os.path.abspath(json_path))
    task_workspace_dir = os.path.join(json_dir, env_folder)
    db_dir = os.path.join(task_workspace_dir, ".ai-scientist-db")
    
    print(f"Task Workspace resolved to: {task_workspace_dir}")
    print(f"Database directory: {db_dir}")
    
    if not os.path.exists(db_dir):
        print(f"Error: Database directory '{db_dir}' does not exist.", file=sys.stderr)
        return False

    steps = target_task.get("steps", [])
    print(f"Analyzing {len(steps)} workflow steps...")

    valid_runs = []
    skipped_count = 0
    literature_ids = []
    for idx, s in enumerate(steps):
        stage = s.get('stage', '') or ''
        outputs = s.get('outputs') or {}
        status = s.get('status', '') or ''
        
        # Check for literature search IDs in outputs
        for k, v in outputs.items():
            if isinstance(v, str) and v.startswith("L_"):
                if v not in literature_ids:
                    literature_ids.append(v)
                    print(f"  [Found Literature Search] ID: {v} in step '{stage}'")
        
        is_execute = any(keyword in stage for keyword in ['execute-proposal', 'execute-solution', 'execute-solution-candidate'])
        if is_execute and status == 'completed':
            exp_id = outputs.get('experiment_id')
            sol_id = outputs.get('solution_candidate_id') or outputs.get('solution_id')
            
            run_id = None
            log_path = None
            run_type = None
            
            if exp_id:
                run_id = exp_id
                log_path = os.path.join(db_dir, 'experiment', exp_id, 'stdout.log')
                run_type = 'experiment'
            elif sol_id:
                run_id = sol_id
                log_path = os.path.join(db_dir, 'solution', sol_id, 'stdout.log')
                run_type = 'solution'
                
            if run_id:
                min_bpb, err = get_min_val_bpb(log_path)
                iter_num = parse_iteration(stage)
                
                if not err:
                    valid_runs.append({
                        'stage': stage,
                        'run_type': run_type,
                        'run_id': run_id,
                        'min_val_bpb': min_bpb,
                        'iter_num': iter_num
                    })
                else:
                    skipped_count += 1
                    # Performance timing runs or profiling runs are skipped gracefully
                    print(f"  [Skipped] ID: {run_id} ({stage}) -> Reason: {err}")

    print(f"Extraction complete: {len(valid_runs)} runs extracted, {skipped_count} runs skipped.")
    if literature_ids:
        print(f"Discovered {len(literature_ids)} Literature Search IDs:")
        for lit_id in literature_ids:
            print(f"  - {lit_id}")
        print()
    
    # Write output to CSV
    print(f"Writing CSV output to: {output_csv_path}")
    try:
        with open(output_csv_path, 'w') as f:
            f.write("Number of experiments/solutions,iteration number,min val_bpb,result_id\n")
            for i, r in enumerate(valid_runs):
                f.write(f"{i+1},{r['iter_num']},{r['min_val_bpb']:.6f},{r['run_id']}\n")
        print("Success! CSV file created successfully.")
        return True
    except IOError as e:
        print(f"Error: Failed to write CSV file. {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Extract and compile val_bpb evolution trajectory for an AI-Scientist task."
    )
    parser.add_argument(
        "--json_path", 
        default="../../tasks_state.json",
        help="Path to the tasks_state.json file (default: ../../tasks_state.json)"
    )
    parser.add_argument(
        "--task_id", 
        default="b42fd4bd-2570-4a8b-849c-2f572f1e9c2c",
        help="The target Task ID (default: b42fd4bd-2570-4a8b-849c-2f572f1e9c2c)"
    )
    parser.add_argument(
        "--output", 
        default="experiment_val_bpb_evolution.csv",
        help="Path to save the output CSV (default: experiment_val_bpb_evolution.csv)"
    )

    args = parser.parse_args()
    
    success = extract_task_metrics(args.json_path, args.task_id, args.output)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
