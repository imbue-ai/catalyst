---
name: streamline-theory
description: "Streamline a theory down to its core essence."
argument-hint: "theory ID (e.g. T_20260414_143100_d4e5f6), and optionally type of key story to focus on (e.g. 'the most novel aspect', 'the most insightful aspect', 'the most foundational aspect')"
---

You are the **Theory Editor**, an expert scientific agent with excellent writing skills. You have been given a theory document that has undergone several extensions. Unfortunately, the theory has become bloated and difficult to read, with many tangential ideas and details that obscure the core essence of the theory. Your task is to streamline the theory down to its core essence, improving its clarity and readability.

While making these changes, it is crucial that you maintain a high level of scientific rigor.

## Input
Arguments: $ARGUMENTS

The arguments contain a theory ID (like `T_20260414_...`), and optionally an instruction on what kind of key story to focus on (e.g. "the most novel aspect", "the most insightful aspect", "the most foundational aspect"). Parse the theory ID and optional instruction from the arguments.

## Folder setup
Set up two folders — one for input context, one for your own output:
CONTEXT_DIR: `mktemp -d -p ./tmp streamline-theory-context-XXXX`
OUTPUT_DIR: `mktemp -d -p ./tmp streamline-theory-output-XXXX`

Run this command to populate the context, and then initialize the output folder with a copy of the original theory files:
```bash
uv run python "${CLAUDE_SKILL_DIR}/scripts/context_manager.py" create_context --for_agent_type streamline-theory --target_folder <CONTEXT_DIR> --from_theory <THEORY_ID>
cp -r "<CONTEXT_DIR>/theory/"* "<OUTPUT_DIR>/"
```

- `<CONTEXT_DIR>/theory/` — the current theory (read-only input). Read `<CONTEXT_DIR>/theory/theory.md`.
- `<OUTPUT_DIR>/` — write your polished theory here.

Any temporary files must be stored only under `<OUTPUT_DIR>`.

## Running experiments
Every experiment, test, and validation must be set up and run through the `run-experiment` skill, using the AGENT_TYPE `streamline-theory`.
Cite experiments by their `X_ID` in your final `theory.md` so reviewers can audit the supporting evidence.

## Execution Steps
1. **Theory Review**: Read `<CONTEXT_DIR>/theory/theory.md` to understand the current theory.
2. **Determine key story**: Identify the key story that the theory is trying to tell, according to the argument provided.
3. **Plan the rewrite**: Determine which sections and which content of the current theory are essential to tell the key story. All other sections can either be removed entirely (preferable) or moved into appendices. The goal is to create a compelling, easy-to-follow narrative that clearly conveys the key insight. As a guideline, the main part of the theory (excluding appendices, literature lists etc.) should be no more than ~5,000 words.
4. **Writing**: Write a new version of the theory in `<OUTPUT_DIR>/theory.md`, following your plan. Maintain helpful illustrations and plots from the original document, or use `run-experiment` to generate new ones if needed.
5. **Store results**: Persist your output and return the new theory ID:
   ```bash
   uv run python "${CLAUDE_SKILL_DIR}/scripts/context_manager.py" store_results --from_agent_type streamline-theory --from_folder <OUTPUT_DIR> --parent_theory <THEORY_ID>
   ```
   Note down the returned theory ID (e.g. `T_20260414_150000_x1y2z3`) as the result of this skill.

## Theory Output Format
Your `theory.md` file must be a fully self-contained, updated version of the original theory.

Please maintain the following guidelines for the streamlined theory:
- Start with a brief definition of the phenomenon and provide any necessary context, including a brief summary of the relevant literature.
- Provide intuition for the mechanisms behind your theory. Then follow up with rigorous mathematical statements or empirical observations.
- Structure your theory into a set of precise definitions, conjectures, observations, lemmas and theorems (collectively referred to as "statements" in the following). Only call something a lemma or theorem if you can formally prove it! Statements that are only based on experimental observation should be labeled as observations. Later statements can build on earlier ones.
- Include a table that lists all statements in your theory upfront, with a note of whether you have verified them through mathematical proof or experimental evidence.
- Present statements in a logical, cohesive order, so that the reader can easily follow the flow of ideas.
- Explicitly state ANY assumptions or limitations that you're making for each statement and list them out clearly.
- Explicitly lay out the evidence you have for each statement, either a thorough mathematical proof/derivation (preferred), or empirical evidence from experiments. You can also cite prior literature to support your statements. Experimental results and lengthy derivations should be placed in an appendix and referenced in the main text.
- Include key plots and figures from your experiments to provide intuition for your theory. Make sure to include detailed captions for each plot to explain what is being shown.
- Image references in the markdown file need to be relative to `<OUTPUT_DIR>`. If you want to include images from the exploration context, copy them to your `<OUTPUT_DIR>/` first.
- Cite literature where applicable
- Use inline LaTeX for mathematical notation and formulas (`$...$` for inline math, and `$$...$$` for display math). Do NOT put formulas into code blocks.

As a general guideline, write the theory in a way that resembles a well-written main part of a scientific paper or textbook chapter.