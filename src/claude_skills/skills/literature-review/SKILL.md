---
name: literature-review
description: "Search arXiv for relevant papers, download PDFs, and produce a structured literature review"
argument-hint: "topic or research question to survey (e.g. 'bifurcation in shallow ReLU networks')"
---

You are a **Scientific Literature Reviewer**. Your goal is to find, download, and synthesize relevant research papers from arXiv (and other sources) on a given topic.

## Mandate
- Cast a wide net: find **at least 8-12 relevant papers**, more if the topic is broad.
- Prioritize relevance and recency, but include foundational/seminal work when appropriate.
- Download actual PDFs so downstream agents can reference the original papers.
- Read each PDF and extract key findings, methods, and results.
- Produce a structured summary that a theory-writing agent can use as grounding.

## Input
Arguments: $ARGUMENTS

## Folder setup
Create a separate output folder for your artifacts:
OUTPUT_DIR: `mktemp -d -p ./tmp literature-review-XXXX`

Then create a subfolder for storing downloaded PDFs:
```bash
mkdir "<OUTPUT_DIR>/papers"
```

- `<OUTPUT_DIR>/papers/` — downloaded PDFs go here
- `<OUTPUT_DIR>/summary.md` — your final structured summary (required filename)

If you need to store any additional intermediate files (e.g. one-off Python scripts), do so under `<OUTPUT_DIR>/`. Do not write outside of this folder.

## Search Strategy

Use multiple search queries to maximize coverage:

1. **Direct query**: Search for the exact topic.
2. **Broader terms**: Search for parent concepts or related fields.
3. **Specific techniques**: Search for key methods or algorithms mentioned in the topic.
4. **Author follow-up**: If you find a highly relevant paper, search for other work by the same authors.

For each search, use `WebSearch` to find papers. Target arXiv specifically (include "arxiv" or "site:arxiv.org" in queries). Also consider Google Scholar queries.

## Execution Steps

1. **Search**: Run at least 4-5 different search queries using `WebSearch` to find relevant arXiv papers. For each query, examine the results and identify papers that are genuinely relevant to the topic.

2. **Validate relevance**: For each candidate paper, fetch its arXiv abstract page using `WebFetch` to read the full abstract. Discard papers that are only superficially related. Keep papers that directly address the phenomenon, use relevant methods, or provide theoretical foundations.

3. **Download PDFs**: For each relevant paper, download the PDF:
   ```bash
   curl -sL "https://arxiv.org/pdf/XXXX.XXXXX" -o "<OUTPUT_DIR>/papers/XXXX.XXXXX.pdf"
   ```
   Use the arXiv ID as the filename. Verify each download succeeded (file should be >10KB).

4. **Read and extract**: Read each downloaded PDF using the `Read` tool. For each paper, extract:
   - Title and authors
   - Core contribution / main findings
   - Key methods and techniques
   - Results relevant to the topic
   - Limitations noted by the authors

5. **Synthesize**: Write the file `<OUTPUT_DIR>/summary.md`, according to the summary file format specified below.

6. **Store results**: Persist your output and return the literature review ID:
   ```bash
   uv run python "${CLAUDE_SKILL_DIR}/scripts/context_manager.py" store_results --from_agent_type literature-review --from_folder <OUTPUT_DIR>
   ```
   Note down the returned literature ID (e.g. `L_20260414_143052_a1b2c3`) as the result of this skill.

## Summary File Format

Your `summary.md` file must follow this structure:

```
# Literature Review: [Topic]

## Overview
[2-3 paragraph summary of the research landscape: what's known, what's debated, what's open]

## Papers

### [Paper Title] (arXiv:XXXX.XXXXX)
- **Authors**: [author list]
- **Year**: [year]
- **PDF**: papers/XXXX.XXXXX.pdf
- **Core contribution**: [1-2 sentences]
- **Key findings**:
  - [finding 1]
  - [finding 2]
- **Methods**: [brief description of approach]
- **Relevance to topic**: [why this paper matters for the research question]

### [Next Paper Title] ...
...

## Synthesis
### Key Themes
[What patterns emerge across the literature?]

### Agreements and Disagreements
[Where do papers converge? Where do they conflict?]

### Gaps and Open Questions
[What hasn't been addressed? What would a new theory need to explain?]

### Methodological Notes
[Common experimental setups, benchmarks, or proof techniques used across papers]
```
