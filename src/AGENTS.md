When working on the (Python) backend:
* Use `uv run python` for running any Python code.
* Run `uv run python -m unittest test_context_manager.py` after making changes to `context_manager.py`.
* Run `uv run python -m unittest discover -t . -s orchestrator` after making changes to any file in the orchestrator folder.
* Run `uv run python -m unittest test_server.py` after making changes to `server.py`.
* Run `uvx ruff check` after any change.

When working on the frontend:
* We don't use all-cap titles or labels. All titles and labels should follow Chicago style capitalization. (only exceptions: task/step state labels and the "CATALYST" title)
* Run `cd frontend && npm run build` to validate frontend changes.
