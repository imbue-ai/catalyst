---
name: import-theory
description: "Import a pre-existing theory from a latex/pdf/markdown file and store in the context database."
argument-hint: "path to the pre-existing theory file (.tex, .pdf, or .md)"
---

You are an expert scientific agent. Your goal is to **import** a pre-existing theory from a provided file (latex, pdf, or markdown) and rewrite it into a markdown file, while preserving as much of the content and structure as possible. You'll then store the theory into our context database for future use.

## Input
Arguments: $ARGUMENTS

The arguments contain a path to the pre-existing theory file (with extension `.tex`, `.pdf`, or `.md`).

## Folder setup
All commands must be run in the current working directory. Do not `cd` anywhere else, do not try to use the global `/tmp` folder or TMPDIR (only use the local `./tmp` folder).

Set up an output folder:
OUTPUT_DIR: `mktemp -d -p ./tmp import-theory-output-XXXX`

- `<OUTPUT_DIR>/` — write the imported theory and all required image files here.

Any temporary files must be stored only under `<OUTPUT_DIR>`.

## Reading the input theory
- `.md` / `.tex`: read with the `Read` tool directly.
- `.pdf`: read with the `Read` tool (it handles PDFs natively). For large PDFs (>10 pages), read page ranges incrementally with the `pages` parameter.

Copy and/or extract all images and figures from the source into `<OUTPUT_DIR>/` so you can reference them in your final markdown.

## Execution Steps
1. **Parse input**: Extract the file path from `$ARGUMENTS`. Validate the file exists and has extension `.tex`, `.pdf`, or `.md`.
2. **Extract figures**: If the source file contains images/figures, extract and save and/or copy them into `<OUTPUT_DIR>/` and note their new paths for referencing in the markdown. Crop the relevant sections of a PDF to isolate figures if needed. Inspect each image file to verify that you have obtained the correctg content.
3. **Convert file**: Write the theory as a markdown file to `<OUTPUT_DIR>/theory.md` (this exact filename is required). Make sure you maintain any mathematical formulas. Correctly reference any images relative to `<OUTPUT_DIR>`.
4. **Store results**: Persist your output and return the theory ID:
   ```bash
   uv run python <SKILL_BASE_DIR>/scripts/context_manager.py store_results --from_agent_type import-theory --from_folder <OUTPUT_DIR>
   ```
   Note down the returned theory ID (e.g. `T_20260421_150000_x1y2z3`) as the result of this skill.
