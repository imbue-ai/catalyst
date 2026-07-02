/**
 * Centralized default parameter values for theory development and evolution workflows.
 */

export const DEFAULT_MAX_REFINEMENTS = 3;
export const DEFAULT_MAX_ITERATIONS = 20;
export const DEFAULT_EVOLVE_ITERATIONS = 5;
export const DEFAULT_NUM_PARENTS = 3;
export const DEFAULT_MAX_STREAMLINE_PROB = 0.5;
export const DEFAULT_WRITE_DIFFERENT_PROB = 0.25;
export const DEFAULT_NUM_EXTRA_SCORES = 5;
export const DEFAULT_NUM_STRANDS = 3;
export const DEFAULT_NUM_PROPOSALS = 3;


// CreateTaskModal specific defaults
export const DEFAULT_NUM_ROOT_THEORIES = 3;
export const DEFAULT_NUM_EXECUTIONS_PER_ITERATION = 2;
export const DEFAULT_EXECUTION_COST = 1;
export const DEFAULT_INTEGRATION_INTERVAL = 5;
export const DEFAULT_RESCORE_INTERVAL = 5;
export const DEFAULT_NUM_EXTRA_INTERPRETATIONS = 3;
export const DEFAULT_BRANCH_PROB = 0.5;

// Default scoring weights
export const DEFAULT_CORRECTNESS_WEIGHT = 0.9;
export const DEFAULT_POWER_WEIGHT = 0.7;
export const DEFAULT_ADHERENCE_WEIGHT = 0.5;
export const DEFAULT_PAST_PERFORMANCE_WEIGHT = 0.8;
export const DEFAULT_FUTURE_POTENTIAL_WEIGHT = 0.5;

// Centralized regex for matching artifact IDs (format: [ELTRXPSOIU]_YYYYMMDD_HHMMSS_ffffff)
export const ARTIFACT_ID_PATTERN = '[ELTRXPSOIU]_\\d{8}_\\d{6}_[a-f0-9]{6}';
export const ARTIFACT_REGEX = new RegExp(`^${ARTIFACT_ID_PATTERN}$`);
export const ARTIFACT_FIND_GLOBAL_REGEX = new RegExp(`\\b(${ARTIFACT_ID_PATTERN})\\b`, 'g');
export const ARTIFACT_BACKTICK_REGEX = new RegExp(`^\`(${ARTIFACT_ID_PATTERN})\`$`);

