"""Run Experiment — run an experiment script and store its results.

Run with ``--help`` to see the available CLI subcommands.
"""

import argparse
import os
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
    parser.add_argument("--nice", default=10, type=int, help="Nice value for the subprocess")
    args = parser.parse_args()

    experiment_folder = args.experiment_folder.resolve()
    script_path = experiment_folder / "script.py"

    stdout_log = experiment_folder / "stdout.log"
    stderr_log = experiment_folder / "stderr.log"

    def set_nice():
        try:
            os.nice(args.nice)
        except OSError:
            pass

    process = subprocess.Popen(
        [sys.executable, str(script_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(experiment_folder),
        preexec_fn=set_nice,
    )

    stdout_thread = threading.Thread(
        target=stream_output, args=(process.stdout, sys.stdout, stdout_log)
    )
    stderr_thread = threading.Thread(
        target=stream_output, args=(process.stderr, sys.stderr, stderr_log)
    )

    stdout_thread.start()
    stderr_thread.start()

    exit_code = process.wait()

    stdout_thread.join()
    stderr_thread.join()

    if exit_code != 0:
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
