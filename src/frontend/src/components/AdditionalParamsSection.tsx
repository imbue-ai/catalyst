import React from 'react'

interface AdditionalParamsSectionProps {
  showRootTheories?: boolean;
  showMaxRefinements?: boolean;
  showEvolveParams?: boolean;
  showApplyExpansions?: boolean;

  numRootTheories?: number;
  setNumRootTheories?: (v: number) => void;

  maxRefinements?: number;
  setMaxRefinements?: (v: number) => void;

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

  // Option to restrict widths like in CreateAddonModal (e.g., md:w-1/3)
  useRestrictedWidths?: boolean;
  children?: React.ReactNode;
}

export function AdditionalParamsSection({
  showRootTheories,
  showMaxRefinements,
  showEvolveParams,
  showApplyExpansions,

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
  setApplyExpansions,

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
      {children}
    </div>
  )
}
