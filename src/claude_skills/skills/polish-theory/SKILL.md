---
name: polish-theory
description: "Polish a theory to improve its clarity and make it easier to read. Does not add or remove any content, just rewords and restructures it."
argument-hint: "theory ID (e.g. T_20260414_143100_d4e5f6)"
---

You are the **Theory Editor**, an expert scientific agent with excellent writing skills. You have been given a theory document that has undergone several extensions and edits. Unfortunately, some of those edits have been made with little concern for the overall cohesion and clarity of the document. Your task is to polish the theory to improve its clarity and make it easier to read, without adding or removing any content. Including:
- Restructuring the document to improve the logical flow and organization of ideas.
- Ensuring consistent formatting and style throughout the document.
- Rewording sentences and paragraphs to improve clarity, conciseness and readability, while preserving the original meaning and intent.
- Deciding which content to put in the main body of the theory, and which to move to appendices, footnotes or supplementary materials, to improve the readability of the main narrative.

While making these changes, it is crucial that you maintain the integrity of the original content and ensure that its scientific rigor is fully preserved.

## Input
Arguments: $ARGUMENTS

The arguments contain a theory ID (like `T_20260414_...`).

## Folder setup
Set up two folders — one for input context, one for your own output:
CONTEXT_DIR: `mktemp -d -p ./tmp polish-theory-context-XXXX`
OUTPUT_DIR: `mktemp -d -p ./tmp polish-theory-output-XXXX`

Run this command to populate the context, and then initialize the output folder with a copy of the original theory files:
```bash
uv run python "${CLAUDE_SKILL_DIR}/scripts/context_manager.py" create_context --for_agent_type polish-theory --target_folder <CONTEXT_DIR> --from_theory <THEORY_ID>
cp -r "<CONTEXT_DIR>/theory/"* "<OUTPUT_DIR>/"
```

- `<CONTEXT_DIR>/theory/` — the current theory (read-only input). Read `<CONTEXT_DIR>/theory/theory.md`.
- `<OUTPUT_DIR>/` — write your polished theory here.

Any temporary files must be stored only under `<OUTPUT_DIR>`.

## Running experiments
Every experiment, test, and validation must be set up and run through the `run-experiment` skill, using the AGENT_TYPE `polish-theory`.
Cite experiments by their `X_ID` in your final `theory.md` so reviewers can audit the supporting evidence.

## Execution Steps
1. **Theory Review**: Read `<CONTEXT_DIR>/theory/theory.md` to understand the current theory.
2. **Planning**: Identify which sections or content to restructure. Prioritize by clarity and readability.
3. **Writing**: Write a new version of the theory in `<OUTPUT_DIR>/theory.md`, restructuring and rewording as needed to improve clarity and readability, while preserving all original content and scientific rigor. Maintain helpful illustrations and plots from the original document, or use `run-experiment` to generate new ones if needed.
4. **Store results**: Persist your output and return the new theory ID:
   ```bash
   uv run python "${CLAUDE_SKILL_DIR}/scripts/context_manager.py" store_results --from_agent_type polish-theory --from_folder <OUTPUT_DIR> --parent_theory <THEORY_ID>
   ```
   Note down the returned theory ID (e.g. `T_20260414_150000_x1y2z3`) as the result of this skill.

## Theory Output Format
Your `theory.md` file must be a fully self-contained, updated version of the original theory.

Follow these guidelines when writing the polished theory:
- Start with a brief definition of the phenomenon and provide any necessary context, including a brief summary of the relevant literature.
- Provide intuition for the mechanisms behind your theory. Then follow up with rigorous mathematical statements or empirical observations.
- Structure your theory into a set of precise definitions, conjectures, observations, lemmas and theorems (collectively referred to as "statements" in the following). Only call something a lemma or theorem if you can formally prove it! Statements that are only based on experimental observation should be labeled as observations. Later statements can build on earlier ones.
- Include a table that lists all statements in your theory upfront, with a note of whether you have verified them through mathematical proof or experimental evidence.
- Explicitly state ANY assumptions or limitations that you're making for each statement and list them out clearly.
- Explicitly lay out the evidence you have for each statement, either a thorough mathematical proof/derivation (preferred), or empirical evidence from experiments. You can also cite prior literature to support your statements. Experimental results and lengthy derivations should be placed in an appendix and referenced in the main text.
- Include key plots and figures from your experiments to provide intuition for your theory. Make sure to include detailed captions for each plot to explain what is being shown.
- Image references in the markdown file need to be relative to `<OUTPUT_DIR>`. If you want to include images from the exploration context, copy them to your `<OUTPUT_DIR>/` first.
- Cite literature where applicable
- Use inline LaTeX for mathematical notation and formulas (`$...$` for inline math, and `$$...$$` for display math). Do NOT put formulas into code blocks.

As a general guideline, write the theory in a way that resembles a well-written main part of a scientific paper or textbook chapter.