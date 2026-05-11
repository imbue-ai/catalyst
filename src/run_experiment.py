"""Run Experiment — run an experiment script and store its results.

Run with ``--help`` to see the available CLI subcommands.
"""

import argparse
import os
import resource
import subprocess
import sys
import threading
from pathlib import Path

from context_manager import store_results


def stream_output(pipe, sys_stream, log_file):
    with open(log_file, "wb") as f:
        for line in iter(pipe.readline, b""):
            sys_stream.buffer.write(line)
            sys_stream.flush()
            f.write(line)


def main():
    parser = argparse.ArgumentParser(
        description="Run an experiment script and store results."
    )
    parser.add_argument("--experiment_folder", required=True, type=Path)
    parser.add_argument("--agent_type", required=True, type=str)
    parser.add_argument("--parent_theory", default=None, type=str)
    args = parser.parse_args()

    experiment_folder = args.experiment_folder.resolve()
    script_path = experiment_folder / "script.py"

    stdout_log = experiment_folder / "stdout.log"
    stderr_log = experiment_folder / "stderr.log"

    # Environment variables for limits
    nice_level = int(os.environ.get("AI_SCIENTIST_EXPERIMENT_NICE_LEVEL", 10))
    timeout_secs = int(os.environ.get("AI_SCIENTIST_EXPERIMENT_TIMEOUT_SECS", 60 * 60))
    memory_limit_as = int(
        os.environ.get("AI_SCIENTIST_EXPERIMENT_RLIMIT_AS", 16 * 1024 * 1024 * 1024)
    )

    def preexec_setup():
        # Set nice value
        try:
            os.nice(nice_level)
        except OSError:
            pass

        # Set memory limit (RLIMIT_AS)
        try:
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit_as, memory_limit_as))
        except (ValueError, OSError):
            pass

    print("Running script.py...", flush=True)

    process = subprocess.Popen(
        [sys.executable, str(script_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(experiment_folder),
        preexec_fn=preexec_setup,
    )

    stdout_thread = threading.Thread(
        target=stream_output, args=(process.stdout, sys.stdout, stdout_log)
    )
    stderr_thread = threading.Thread(
        target=stream_output, args=(process.stderr, sys.stderr, stderr_log)
    )

    stdout_thread.start()
    stderr_thread.start()

    try:
        exit_code = process.wait(timeout=timeout_secs)
    except subprocess.TimeoutExpired:
        process.kill()
        exit_code = process.wait()
        print(
            f"Error: Experiment timed out after {timeout_secs} seconds.",
            file=sys.stderr,
        )
        sys.exit(124)  # 124 is a common exit code for timeout

    stdout_thread.join()
    stderr_thread.join()

    if exit_code != 0:
        # Check stderr for common memory error indicators
        try:
            with open(stderr_log, "r") as f:
                stderr_content = f.read()
                if (
                    "MemoryError" in stderr_content
                    or "std::bad_alloc" in stderr_content
                ):
                    print(
                        f"Error: Experiment hit memory limit ({memory_limit_as} bytes).",
                        file=sys.stderr,
                    )
            sys.exit(137)  # 137 is common for OOM (128 + 9)
        except Exception:
            pass

        sys.exit(exit_code)

    print("script.py executed successfully.")

    metadata_extra = {"parent_agent_type": args.agent_type}

    new_id = store_results(
        from_agent_type="run-experiment",
        from_folder=experiment_folder,
        parent_theory=args.parent_theory,
        metadata_extra=metadata_extra,
    )

    print(f"Stored experiment into database under ID {new_id}.")


if __name__ == "__main__":
    main()
