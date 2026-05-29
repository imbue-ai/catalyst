---
name: search-literature
description: "Run a targeted literature search on specific findings or questions that emerged during theory development"
argument-hint: "specific findings, questions, or phenomena to investigate"
---

You are working on finding literature as part of a broader research effort. Your goal is to find prior work that *directly* bears on the query and produce a focused summary of the literature you find.

## Literature Search Mandate
- Stay narrowly scoped: **2–6 papers** that *precisely* bear on the query is the target. Fewer is fine if it directly addresses the query; do not pad with tangential work.
- Prioritize papers that directly study the specific phenomenon, technique, or claim under investigation — not papers that merely touch the same parent field.
- Relevant literature can include work that falsifies or bounds the specified phenomenon, technique, or claim. Not just work that supports it.
- Download actual PDFs so downstream agents can reference the originals.
- Read each PDF and extract the parts that speak to the query; skip unrelated material. Also skip appendix sections and/or supplementary material to avoid exhausting context size limits.
- Produce a structured summary framed around the original query, not a general landscape map.

## Literature Search Input
Arguments: $ARGUMENTS

The arguments describe the findings or questions to investigate.

## Literature Search Folder setup
Set up an output folder for your artifacts:
OUTPUT_DIR: `mktemp -d -p ./tmp search-literature-output-XXXX`

```bash
mkdir -p "<OUTPUT_DIR>/papers"
```

- `<OUTPUT_DIR>/papers/` — downloaded PDFs go here
- `<OUTPUT_DIR>/summary.md` — your final structured summary (required filename)

## Literature Search Strategy
Because the query is specific, run **fewer but sharper** searches than a generic review:

1. **Exact-phenomenon query**: Search for the precise phenomenon or finding described in the query, using the same technical vocabulary the user used.
2. **Mechanism query**: Search for the likely underlying mechanism or mathematical structure (e.g. "symmetry breaking", "stationary manifold", "gradient flow bifurcation").
3. **Disconfirming query**: Search for results that would *contradict* or bound the finding — knowing the failure modes matters as much as confirmation.
4. **Follow-up** (optional): If one paper is highly relevant, search for related work by the same authors or papers that cite it.

Target arXiv specifically (include `arxiv` or `site:arxiv.org` in queries). Google Scholar is acceptable too.

## Literature Search Summary File Format
Your `summary.md` file must follow this structure:

```
# Targeted Literature Search: [one-line restatement of the query]

## Query
[The specific finding or question you investigated, in 1–3 sentences. Include any background context the caller provided.]

## Direct Answers from the Literature
[2–3 paragraphs: what do the papers collectively say about the query? Lead with the most load-bearing finding. Call out confirming, disconfirming, and partial results separately.]

## Papers

### [Paper Title] (arXiv:XXXX.XXXXX)
- **Authors**: [author list]
- **Year**: [year]
- **PDF**: papers/XXXX.XXXXX.pdf
- **Relevance to query**: [the one or two specific reasons this paper bears on the query]
- **Key excerpted finding**: [the specific result, bound, or mechanism the paper contributes to this query — not a general summary of the paper]
- **Methods/setup**: [only the parts relevant to the query]
- **Caveats**: [assumptions or scope limits that could restrict the finding's applicability]

### [Next Paper Title] ...
...

## Open Questions
[What does the literature *not* resolve about the query? These are candidate hypotheses the caller may want to investigate empirically or leave as acknowledged gaps.]
```

## Literature Search Execution Steps
1. **Parse query**: Extract the specific findings/questions from the arguments.
2. **Search**: Run 2–4 focused `WebSearch` queries following the strategy above. Identify candidate papers.
3. **Validate relevance**: For each candidate, fetch the arXiv abstract page with `WebFetch`. Keep only papers that directly address the query. Err on the side of rejection — an irrelevant paper is worse than a missing one here because the caller is already deep in their own work.
4. **Download PDFs**: For each kept paper:
   ```bash
   curl -sL "https://arxiv.org/pdf/XXXX.XXXXX" -o "<OUTPUT_DIR>/papers/XXXX.XXXXX.pdf"
   ```
   Use the arXiv ID as filename. Verify each download succeeded (file >10KB).
5. **Read and extract**: Read each PDF. Make sure you skip any appendix sections and/or supplementary material to avoid exhausting context size limits. For each paper, note only the content that speaks to the query — the specific finding, the relevant method, the directly applicable result or bound. Skip the rest.
6. **Synthesize**: Write `<OUTPUT_DIR>/summary.md` per the format below. Frame the synthesis around the query, not as a general landscape survey.
7. **Store results**: Persist your output:
   ```bash
   uv run python <SKILL_BASE_DIR>/scripts/context_manager.py store_results --from_agent_type search-literature --from_folder <OUTPUT_DIR>
   ```
   Note down the returned literature ID (e.g. `L_20260416_143052_a1b2c3`) as the result of this skill and continue with any remaining steps in your current workflow.

