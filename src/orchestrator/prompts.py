from typing import List, Optional


def get_write_theory_prompt(
    phenomenon: str, exploration_id: str, lit_review_id: str
) -> str:
    return (
        f"Please run the write-theory skill for the following phenomenon:\n```\n{phenomenon}\n```\n"
        f"Use exploration_id: {exploration_id} and literature_review_id: {lit_review_id}. "
        "When you are done, return ONLY a JSON object with the key 'theory_id'."
    )


def get_write_n_theories_prompt(
    num_theories: int, phenomenon: str, exploration_id: str, lit_review_id: str
) -> str:
    return (
        f"Please run the write-n-theories skill to generate {num_theories} theories for the following phenomenon:\n```\n{phenomenon}\n```\n"
        f"Use exploration_id: {exploration_id} and literature_review_id: {lit_review_id}. "
        "When you are done, return ONLY a JSON object with the key 'theory_ids' containing the list of generated theory IDs."
    )


def get_review_theory_prompt(theory_id: str) -> str:
    return (
        f"Please run the review-theory skill for theory_id: {theory_id}. "
        "When you are done, return ONLY a JSON object with four keys: "
        "1. 'review_ids' containing the full list of generated review IDs (falsification, expansion, and adherence), "
        "2. 'statement_reviews' containing a mapping of each reviewed statement (by number and/or title) to the associated falsification review ID, "
        "3. 'expansion_reviews' containing a list of only the expansion review IDs, "
        "4. 'adherence_reviews' containing a list of only the adherence review IDs."
    )


def get_score_theories_prompt(theory_ids: List[str]) -> str:
    joined_ids = ", ".join(theory_ids)
    return (
        f"Please run the score-theories skill for the following theory_ids: {joined_ids}. "
        "When you are done, return ONLY a JSON object mapping each theory ID to its assigned scores object (including subscores)."
    )


def get_write_different_theory_prompt(
    theory_ids: List[str], lit_review_id: Optional[str] = None
) -> str:
    joined_ids = ", ".join(theory_ids)
    prompt = f"Please run the write-different-theory skill with the following list of theory_ids: {joined_ids}. "
    if lit_review_id:
        prompt += f"Also pass literature_review_id: {lit_review_id}. "
    prompt += "When you are done, return ONLY a JSON object with the key 'theory_id'."
    return prompt


def get_refine_theory_prompt(
    theory_id: str,
    apply_expansions: Optional[str] = None,
    lit_review_id: Optional[str] = None,
) -> str:
    prompt = f"Please run the refine-theory skill for theory_id: {theory_id}. "
    if lit_review_id:
        prompt += f"Also pass literature_review_id: {lit_review_id}. "

    if apply_expansions == "never":
        prompt += "Tell the skill: Do NOT apply expansion reviews."
    elif apply_expansions == "always":
        prompt += "Tell the skill: ALWAYS apply expansion reviews."

    prompt += "\n\nWhen you are done, return ONLY a JSON object with the keys 'theory_id' (the ID of the new, final theory), 'major_changes' (boolean - whether any major changes have been made to the theory), and 'expansions_applied' (boolean - whether any expansion reviews have been applied)."

    return prompt


def get_polish_theory_prompt(theory_id: str) -> str:
    return (
        f"Please run the polish-theory skill for theory_id: {theory_id}. "
        "When you are done, return ONLY a JSON object with the key 'theory_id'."
    )


def get_refine_hypothesis_prompt(
    theory_id: str, review_id: str, lit_review_id: Optional[str] = None
) -> str:
    prompt = f"Please run the refine-hypothesis skill for theory_id: {theory_id} using review_id: {review_id}. "
    if lit_review_id:
        prompt += f"Also pass literature_review_id: {lit_review_id}. "
    prompt += "When you are done, return ONLY a JSON object with the key 'theory_id'."
    return prompt


def get_falsify_hypothesis_prompt(theory_id: str, hypothesis_title: str) -> str:
    return (
        f"Please run the falsify-hypothesis skill for theory_id: {theory_id} and hypothesis title: '{hypothesis_title}'. "
        "When you are done, return ONLY a JSON object with the key 'review_id'."
    )


def get_suggest_expansions_prompt(theory_id: str) -> str:
    return (
        f"Please run the suggest-expansions skill for theory_id: {theory_id}. "
        "When you are done, return ONLY a JSON object with the key 'review_id'."
    )


def get_review_adherence_prompt(theory_id: str) -> str:
    return (
        f"Please run the review-adherence skill for theory_id: {theory_id}. "
        "When you are done, return ONLY a JSON object with the key 'review_id'."
    )


def get_improve_adherence_prompt(
    theory_id: str, review_id: str, lit_review_id: Optional[str] = None
) -> str:
    prompt = f"Please run the improve-adherence skill for theory_id: {theory_id} using review_id: {review_id}. "
    if lit_review_id:
        prompt += f"Also pass literature_review_id: {lit_review_id}. "
    prompt += "When you are done, return ONLY a JSON object with the key 'theory_id'."
    return prompt


def get_expand_theory_prompt(
    theory_id: str, review_id: str, lit_review_id: Optional[str] = None
) -> str:
    prompt = f"Please run the expand-theory skill for theory_id: {theory_id} using review_id: {review_id}. "
    if lit_review_id:
        prompt += f"Also pass literature_review_id: {lit_review_id}. "
    prompt += "When you are done, return ONLY a JSON object with the key 'theory_id'."
    return prompt


def get_edit_theory_prompt(
    theory_id: str, instruction: str, lit_review_id: Optional[str] = None
) -> str:
    prompt = f"Please run the edit-theory skill for theory_id: {theory_id} with the following instruction:\n```\n{instruction}\n```\n"
    if lit_review_id:
        prompt += f"Also pass literature_review_id: {lit_review_id}. "
    prompt += "When you are done, return ONLY a JSON object with the key 'theory_id'."
    return prompt


def get_streamline_theory_variations_prompt(theory_id: str) -> str:
    return (
        f"Please run the streamline-theory-variations skill for theory_id: {theory_id}. "
        "When you are done, return ONLY a JSON object with the key 'theory_ids' containing a list of the generated theory IDs."
    )


def get_streamline_theory_prompt(
    theory_id: str, direction: Optional[str] = None
) -> str:
    prompt = f"Please run the streamline-theory skill for theory_id: {theory_id}."
    if direction:
        prompt += f"Direction:\n```\n{direction}\n```\n"
    prompt += "When you are done, return ONLY a JSON object with the key 'theory_id'."
    return prompt


def get_summarize_title_prompt(content_desc: str) -> str:
    return (
        f"Please provide a very short, summarized title (maximum 5 words) for the following research:\n```\n{content_desc}\n```\n"
        "Return ONLY a JSON object with the key 'title'."
    )


def get_support_idea_prompt(idea: str, file_path: Optional[str] = None) -> str:
    prompt = "Please run the support-idea skill."
    if idea:
        prompt += f" Idea:\n```\n{idea}\n```\n"
    if file_path:
        prompt += f" You can find the relevant uploaded files at `{file_path}`. "
    prompt += "When you are done, return ONLY a JSON object with the key 'theory_id'."
    return prompt


def get_import_theory_prompt(file_path: str) -> str:
    return (
        f"Please run the import-theory skill for the following file path: `{file_path}`. "
        "When you are done, return ONLY a JSON object with the key 'theory_id'."
    )


def get_summarize_research_prompt() -> str:
    return (
        "Please run the summarize-research skill.\n"
        "When you are done, return ONLY a JSON object with the key 'summary_id'."
    )


def get_propose_experiment_prompt(theory_id: str) -> str:
    return (
        f"Please run the propose-experiment skill for theory ID: {theory_id}. "
        "When you are done, return ONLY a JSON object with the key 'proposal_id'."
    )


def get_rank_proposals_prompt(proposal_ids: List[str]) -> str:
    joined_ids = " ".join(proposal_ids)
    return (
        f"Please run the rank-proposals skill with the following list of proposal IDs: {joined_ids}. "
        "When you are done, return ONLY a JSON object with two keys: "
        "'rankings' (a list of the experiment/literature-search proposal IDs in order from best to worst) "
        "and 'solution_candidates' (a list containing all solution-candidate proposal IDs)."
    )


def get_execute_proposal_prompt(proposal_id: str) -> str:
    return (
        f"Please run the execute-proposal skill for proposal ID: {proposal_id}. "
        "Depending on the proposal type, return ONLY a JSON object with one of these keys: "
        "'experiment_id' (for an experiment, e.g. X_...), 'literature_id' (for literature research, e.g. L_...), "
        "or 'solution_id' (for a solution candidate, e.g. U_...)."
    )


def get_interpret_result_prompt(theory_id: str, result_ids: list[str]) -> str:
    result_ids_str = " ".join(result_ids)
    return (
        f"Please run the interpret-result skill for theory ID: {theory_id} and result IDs: {result_ids_str}. "
        "When you are done, return ONLY a JSON object with the key 'theory_id'."
    )
