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

import type { Step } from './api';

/**
 * Creates a map of steps by stage for O(1) lookup.
 */
export function getStepsMap(steps: Step[]): Record<string, Step> {
  const map: Record<string, Step> = {};
  for (const step of steps) {
    map[step.stage] = step;
  }
  return map;
}
