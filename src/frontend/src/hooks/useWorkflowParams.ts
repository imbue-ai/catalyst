import { useState } from 'react'
import {
  DEFAULT_MAX_REFINEMENTS,
  DEFAULT_MAX_ITERATIONS,
  DEFAULT_EVOLVE_ITERATIONS,
  DEFAULT_NUM_PARENTS,
  DEFAULT_MAX_STREAMLINE_PROB,
  DEFAULT_WRITE_DIFFERENT_PROB,
  DEFAULT_NUM_EXTRA_SCORES,
  DEFAULT_NUM_ROOT_THEORIES,
  DEFAULT_CORRECTNESS_WEIGHT,
  DEFAULT_POWER_WEIGHT,
  DEFAULT_ADHERENCE_WEIGHT,
  DEFAULT_NUM_STRANDS,
  DEFAULT_NUM_EXECUTIONS_PER_ITERATION,
  DEFAULT_EXECUTION_COST
} from '../constants'

export function useWorkflowParams() {
  const [numRootTheories, setNumRootTheories] = useState(DEFAULT_NUM_ROOT_THEORIES)
  const [maxRefinements, setMaxRefinements] = useState(DEFAULT_MAX_REFINEMENTS)
  const [maxIterations, setMaxIterations] = useState(DEFAULT_MAX_ITERATIONS)
  const [evolveIterations, setEvolveIterations] = useState(DEFAULT_EVOLVE_ITERATIONS)
  const [numParents, setNumParents] = useState(DEFAULT_NUM_PARENTS)
  const [maxStreamlineProb, setMaxStreamlineProb] = useState(DEFAULT_MAX_STREAMLINE_PROB)
  const [writeDifferentProb, setWriteDifferentProb] = useState(DEFAULT_WRITE_DIFFERENT_PROB)
  const [numExtraScores, setNumExtraScores] = useState(DEFAULT_NUM_EXTRA_SCORES)
  const [applyExpansions, setApplyExpansions] = useState('')
  const [numStrands, setNumStrands] = useState(DEFAULT_NUM_STRANDS)
  const [numExecutionsPerIteration, setNumExecutionsPerIteration] = useState(DEFAULT_NUM_EXECUTIONS_PER_ITERATION)
  const [executionCost, setExecutionCost] = useState(DEFAULT_EXECUTION_COST)

  const [correctnessWeight, setCorrectnessWeight] = useState(DEFAULT_CORRECTNESS_WEIGHT)
  const [powerWeight, setPowerWeight] = useState(DEFAULT_POWER_WEIGHT)
  const [adherenceWeight, setAdherenceWeight] = useState(DEFAULT_ADHERENCE_WEIGHT)
  const [generateIntermediateResearchSummaries, setGenerateIntermediateResearchSummaries] = useState(true)

  return {
    numRootTheories,
    setNumRootTheories,
    maxRefinements,
    setMaxRefinements,
    maxIterations,
    setMaxIterations,
    evolveIterations,
    setEvolveIterations,
    numParents,
    setNumParents,
    maxStreamlineProb,
    setMaxStreamlineProb,
    writeDifferentProb,
    setWriteDifferentProb,
    numExtraScores,
    setNumExtraScores,
    applyExpansions,
    setApplyExpansions,
    numStrands,
    setNumStrands,
    numExecutionsPerIteration,
    setNumExecutionsPerIteration,
    executionCost,
    setExecutionCost,
    correctnessWeight,
    setCorrectnessWeight,
    powerWeight,
    setPowerWeight,
    adherenceWeight,
    setAdherenceWeight,
    generateIntermediateResearchSummaries,
    setGenerateIntermediateResearchSummaries
  }
}
