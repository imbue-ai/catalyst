/**
 * Centralized utility and helper functions for the frontend.
 */

/**
 * Checks if a given workflow name corresponds to a verifiable goal based workflow.
 */
export function isVerifiableGoalWorkflow(workflowName: string | undefined | null): boolean {
  if (!workflowName) return false;
  return workflowName === 'solve-verifiable-goal-multi-strand' || workflowName === 'solve-verifiable-goal';
}
