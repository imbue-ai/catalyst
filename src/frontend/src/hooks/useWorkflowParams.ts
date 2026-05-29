import { useState } from 'react'
import {
  DEFAULT_MAX_REFINEMENTS,
  DEFAULT_EVOLVE_ITERATIONS,
  DEFAULT_NUM_PARENTS,
  DEFAULT_MAX_STREAMLINE_PROB,
  DEFAULT_WRITE_DIFFERENT_PROB,
  DEFAULT_NUM_EXTRA_SCORES,
  DEFAULT_NUM_ROOT_THEORIES
} from '../constants'

export function useWorkflowParams() {
  const [numRootTheories, setNumRootTheories] = useState(DEFAULT_NUM_ROOT_THEORIES)
  const [maxRefinements, setMaxRefinements] = useState(DEFAULT_MAX_REFINEMENTS)
  const [evolveIterations, setEvolveIterations] = useState(DEFAULT_EVOLVE_ITERATIONS)
  const [numParents, setNumParents] = useState(DEFAULT_NUM_PARENTS)
  const [maxStreamlineProb, setMaxStreamlineProb] = useState(DEFAULT_MAX_STREAMLINE_PROB)
  const [writeDifferentProb, setWriteDifferentProb] = useState(DEFAULT_WRITE_DIFFERENT_PROB)
  const [numExtraScores, setNumExtraScores] = useState(DEFAULT_NUM_EXTRA_SCORES)
  const [applyExpansions, setApplyExpansions] = useState('')

  return {
    numRootTheories,
    setNumRootTheories,
    maxRefinements,
    setMaxRefinements,
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
    setApplyExpansions
  }
}
