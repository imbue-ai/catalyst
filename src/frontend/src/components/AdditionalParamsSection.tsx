import React from 'react'

interface AdditionalParamsSectionProps {
  showRootTheories?: boolean;
  showMaxRefinements?: boolean;
  showEvolveParams?: boolean;
  showApplyExpansions?: boolean;
  showScoringWeights?: boolean;
  showNumStrands?: boolean;
  showNumExecutionsPerIteration?: boolean;
  showExecutionCost?: boolean;

  numRootTheories?: number;
  setNumRootTheories?: (v: number) => void;

  maxRefinements?: number;
  setMaxRefinements?: (v: number) => void;
  showMaxIterations?: boolean;
  maxIterations?: number;
  setMaxIterations?: (v: number) => void;

  evolveIterations?: number;
  setEvolveIterations?: (v: number) => void;

  numParents?: number;
  setNumParents?: (v: number) => void;

  maxStreamlineProb?: number;
  setMaxStreamlineProb?: (v: number) => void;

  writeDifferentProb?: number;
  setWriteDifferentProb?: (v: number) => void;

  numExtraScores?: number;
  setNumExtraScores?: (v: number) => void;

  applyExpansions?: string;
  setApplyExpansions?: (v: string) => void;

  correctnessWeight?: number;
  setCorrectnessWeight?: (v: number) => void;

  powerWeight?: number;
  setPowerWeight?: (v: number) => void;

  adherenceWeight?: number;
  setAdherenceWeight?: (v: number) => void;

  showGenerateIntermediateResearchSummaries?: boolean;
  generateIntermediateResearchSummaries?: boolean;
  setGenerateIntermediateResearchSummaries?: (v: boolean) => void;

  numStrands?: number;
  setNumStrands?: (v: number) => void;

  numExecutionsPerIteration?: number;
  setNumExecutionsPerIteration?: (v: number) => void;

  executionCost?: number;
  setExecutionCost?: (v: number) => void;

  // Option to restrict widths like in CreateAddonModal (e.g., md:w-1/3)
  useRestrictedWidths?: boolean;
  children?: React.ReactNode;
}

export function AdditionalParamsSection({
  showRootTheories,
  showMaxRefinements,
  showEvolveParams,
  showApplyExpansions,
  showScoringWeights,
  showNumStrands,
  showNumExecutionsPerIteration,
  showExecutionCost,

  numRootTheories,
  setNumRootTheories,

  maxRefinements,
  setMaxRefinements,
  showMaxIterations,
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

  correctnessWeight,
  setCorrectnessWeight,

  powerWeight,
  setPowerWeight,

  adherenceWeight,
  setAdherenceWeight,

  showGenerateIntermediateResearchSummaries,
  generateIntermediateResearchSummaries,
  setGenerateIntermediateResearchSummaries,

  numStrands,
  setNumStrands,

  numExecutionsPerIteration,
  setNumExecutionsPerIteration,

  executionCost,
  setExecutionCost,

  useRestrictedWidths = false,
  children,
}: AdditionalParamsSectionProps) {
  const inputClass = "w-full border-2 border-black p-2 outline-none text-sm font-bold bg-white"
  const selectClass = "w-full border-2 border-black p-2 outline-none text-sm font-bold bg-white cursor-pointer"

  return (
    <div className={useRestrictedWidths ? "flex flex-col gap-6 p-6 border-2 border-dashed border-gray-200" : "grid grid-cols-2 md:grid-cols-4 gap-6 p-6 border-2 border-dashed border-gray-200"}>
      {showRootTheories && setNumRootTheories && (
        <div className="col-span-1">
          <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Root Theories</label>
          <input
            type="number" min="1" max="20" required
            value={numRootTheories}
            onChange={e => setNumRootTheories(parseInt(e.target.value, 10))}
            className={inputClass}
          />
        </div>
      )}

      {showMaxRefinements && setMaxRefinements && (
        <div className={useRestrictedWidths ? "w-full md:w-1/3" : "col-span-1"}>
          <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Max Refinements</label>
          <input
            type="number" min="0" max="10" required
            value={maxRefinements}
            onChange={e => setMaxRefinements(parseInt(e.target.value, 10))}
            className={inputClass}
          />
        </div>
      )}

      {showMaxIterations && setMaxIterations && (
        <div className={useRestrictedWidths ? "w-full md:w-1/3" : "col-span-1"}>
          <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Max Iterations</label>
          <input
            type="number" min="0" max="100" required
            value={maxIterations}
            onChange={e => setMaxIterations(parseInt(e.target.value, 10))}
            className={inputClass}
          />
        </div>
      )}

      {showNumStrands && setNumStrands && (
        <div className={useRestrictedWidths ? "w-full md:w-1/3" : "col-span-1"}>
          <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Number of Strands</label>
          <input
            type="number" min="1" max="10" required
            value={numStrands}
            onChange={e => setNumStrands(parseInt(e.target.value, 10))}
            className={inputClass}
          />
        </div>
      )}

      {showNumExecutionsPerIteration && setNumExecutionsPerIteration && (
        <div className={useRestrictedWidths ? "w-full md:w-1/3" : "col-span-1"}>
          <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Number of Executions per Iteration</label>
          <input
            type="number" min="1" max="10" required
            value={numExecutionsPerIteration}
            onChange={e => setNumExecutionsPerIteration(parseInt(e.target.value, 10))}
            className={inputClass}
          />
        </div>
      )}

      {showExecutionCost && setExecutionCost && (
        <div className={useRestrictedWidths ? "w-full md:w-1/3" : "col-span-1"}>
          <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Execution Cost</label>
          <input
            type="number" min="1" max="5" required
            value={executionCost}
            onChange={e => setExecutionCost(parseInt(e.target.value, 10))}
            className={inputClass}
          />
        </div>
      )}

      {showEvolveParams && (
        <>
          {setEvolveIterations && (
            <div className="col-span-1">
              <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Evolve Iterations</label>
              <input
                type="number" min="0" max="10" required
                value={evolveIterations}
                onChange={e => setEvolveIterations(parseInt(e.target.value, 10))}
                className={inputClass}
              />
            </div>
          )}
          {setNumParents && (
            <div className="col-span-1">
              <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Num Parents</label>
              <input
                type="number" min="1" max="10" required
                value={numParents}
                onChange={e => setNumParents(parseInt(e.target.value, 10))}
                className={inputClass}
              />
            </div>
          )}
          {setMaxStreamlineProb && (
            <div className="col-span-1">
              <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Max Streamline Prob</label>
              <input
                type="number" min="0" max="1" step="any" required
                value={maxStreamlineProb}
                onChange={e => setMaxStreamlineProb(parseFloat(e.target.value))}
                className={inputClass}
              />
            </div>
          )}
          {setWriteDifferentProb && (
            <div className="col-span-1">
              <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Write Different Prob</label>
              <input
                type="number" min="0" max="1" step="any" required
                value={writeDifferentProb}
                onChange={e => setWriteDifferentProb(parseFloat(e.target.value))}
                className={inputClass}
              />
            </div>
          )}
          {setNumExtraScores && (
            <div className="col-span-1">
              <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Extra Scores</label>
              <input
                type="number" min="0" max="10" required
                value={numExtraScores}
                onChange={e => setNumExtraScores(parseInt(e.target.value, 10))}
                className={inputClass}
              />
            </div>
          )}
        </>
      )}

      {showApplyExpansions && setApplyExpansions && (
        <div className={useRestrictedWidths ? "w-full md:w-1/3" : "col-span-1"}>
          <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Apply Expansion Reviews</label>
          <select
            value={applyExpansions}
            onChange={e => setApplyExpansions(e.target.value)}
            className={selectClass}
          >
            <option value="">Auto (Default)</option>
            <option value="always">Always</option>
            <option value="never">Never</option>
          </select>
        </div>
      )}

      {showGenerateIntermediateResearchSummaries && setGenerateIntermediateResearchSummaries && (
        <div className={useRestrictedWidths ? "w-full md:w-2/3 flex items-center gap-2 pt-4" : "col-span-1 md:col-span-2 flex items-center gap-2 pt-4"}>
          <input
            id="generate-intermediate-summaries"
            type="checkbox"
            checked={generateIntermediateResearchSummaries}
            onChange={e => setGenerateIntermediateResearchSummaries(e.target.checked)}
            className="w-4 h-4 accent-black cursor-pointer border-2 border-black"
          />
          <label htmlFor="generate-intermediate-summaries" className="text-xs font-bold text-black cursor-pointer select-none">
            Generate Intermediate Research Summaries
          </label>
        </div>
      )}

      {showScoringWeights && (
        <div className="col-span-full border-t border-dashed border-gray-200 pt-6 mt-2">
          <h4 className="text-xs font-black tracking-widest text-black mb-4">Theory Scoring Weights</h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {setCorrectnessWeight && correctnessWeight !== undefined && (
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="text-[10px] font-black tracking-widest text-gray-400">Correctness</label>
                  <span className="text-xs font-black bg-black text-white px-2 py-0.5 rounded-sm">{correctnessWeight.toFixed(2)}</span>
                </div>
                <input
                  type="range" min="0" max="1" step="0.05"
                  value={correctnessWeight}
                  onChange={e => setCorrectnessWeight(parseFloat(e.target.value))}
                  className="w-full h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-black"
                />
              </div>
            )}

            {setPowerWeight && powerWeight !== undefined && (
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="text-[10px] font-black tracking-widest text-gray-400">Explanatory and Predictive Power</label>
                  <span className="text-xs font-black bg-black text-white px-2 py-0.5 rounded-sm">{powerWeight.toFixed(2)}</span>
                </div>
                <input
                  type="range" min="0" max="1" step="0.05"
                  value={powerWeight}
                  onChange={e => setPowerWeight(parseFloat(e.target.value))}
                  className="w-full h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-black"
                />
              </div>
            )}

            {setAdherenceWeight && adherenceWeight !== undefined && (
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="text-[10px] font-black tracking-widest text-gray-400">Instruction Adherence</label>
                  <span className="text-xs font-black bg-black text-white px-2 py-0.5 rounded-sm">{adherenceWeight.toFixed(2)}</span>
                </div>
                <input
                  type="range" min="0" max="1" step="0.05"
                  value={adherenceWeight}
                  onChange={e => setAdherenceWeight(parseFloat(e.target.value))}
                  className="w-full h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-black"
                />
              </div>
            )}
          </div>
        </div>
      )}
      {children}
    </div>
  )
}
