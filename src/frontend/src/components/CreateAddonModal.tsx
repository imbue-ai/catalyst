import React, { useState } from 'react'
import { XCircle, ChevronRight } from 'lucide-react'
import * as api from '../api'

interface CreateAddonModalProps {
  task: api.Task;
  availableTheoryIds: string[];
  onClose: () => void;
  onCreated: (task: api.Task) => void;
  isBackendDown: boolean;
}

export function CreateAddonModal({ task, availableTheoryIds, onClose, onCreated, isBackendDown }: CreateAddonModalProps) {
  const [addonType, setAddonType] = useState('streamline-theory')
  const [theoryId, setTheoryId] = useState(availableTheoryIds[0] || '')
  const [direction, setDirection] = useState('')
  const [maxRefinements, setMaxRefinements] = useState(3)
  const [applyExtensions, setApplyExtensions] = useState(false)
  const [evolveIterations, setEvolveIterations] = useState(3)
  const [numParents, setNumParents] = useState(3)
  const [maxStreamlineProb, setMaxStreamlineProb] = useState(0.5)
  const [numExtraScores, setNumExtraScores] = useState(5)

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const updatedTask = await api.createAddon(task.id, {
        type: addonType,
        theory_id: addonType === 'evolve-loop' ? 'none' : theoryId, // Evolve loop doesn't strictly need a theory ID
        direction: addonType === 'streamline-theory' && direction ? direction : undefined,
        max_refinements: addonType === 'refinement-loop' ? maxRefinements : undefined,
        apply_extensions: addonType === 'refinement-loop' ? applyExtensions : undefined,
        evolve_iterations: addonType === 'evolve-loop' ? evolveIterations : undefined,
        num_parents: addonType === 'evolve-loop' ? numParents : undefined,
        max_streamline_prob: addonType === 'evolve-loop' ? maxStreamlineProb : undefined,
        num_extra_scores: addonType === 'evolve-loop' ? numExtraScores : undefined
      })
      onCreated(updatedTask)
    } catch (e: any) {
      alert(e.message || "Failed to add addon workflow")
    }
  }

  const isTheoryIdDisabled = addonType === 'evolve-loop';

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-white border-2 border-black p-8 w-full max-w-lg shadow-[12px_12px_0px_0px_rgba(0,0,0,1)] max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-8">
          <h2 className="text-2xl font-black tracking-tighter">Add Step</h2>
          <button onClick={onClose} className="hover:rotate-90 transition-transform">
            <XCircle size={24} />
          </button>
        </div>

        {task.status !== 'completed' && task.status !== 'running' && (
          <div className="text-xs font-bold text-yellow-700 bg-yellow-100 p-4 border border-yellow-300 mb-6 flex gap-2 items-start">
            <span className="shrink-0 mt-0.5">⚠️</span>
            <span>Warning: Adding a step to an incomplete workflow will cancel any remaining steps in the current workflow sequence.</span>
          </div>
        )}

        {availableTheoryIds.length === 0 && !isTheoryIdDisabled ? (
          <div className="text-sm font-bold text-red-600 mb-6">
            No theories have been generated yet in this task. Please wait for a step to output a theory_id.
          </div>
        ) : (
          <form onSubmit={handleCreate} className="flex flex-col gap-6">
            <div>
              <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Target Theory ID</label>
              <select
                required={!isTheoryIdDisabled}
                disabled={isTheoryIdDisabled}
                value={isTheoryIdDisabled ? '' : theoryId}
                onChange={e => setTheoryId(e.target.value)}
                className={`w-full border-2 border-black p-3 outline-none font-bold text-sm bg-white cursor-pointer ${isTheoryIdDisabled ? 'opacity-50 cursor-not-allowed bg-gray-100' : ''}`}
              >
                {isTheoryIdDisabled && <option value="">N/A (Population Based)</option>}
                {!isTheoryIdDisabled && availableTheoryIds.map(id => (
                  <option key={id} value={id}>{id}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Add-on Skill</label>
              <select
                value={addonType}
                onChange={e => setAddonType(e.target.value)}
                className="w-full border-2 border-black p-3 outline-none font-bold text-sm bg-white cursor-pointer"
              >
                <option value="streamline-theory">Streamline Theory</option>
                <option value="review-theory">Review Theory</option>
                <option value="refine-theory">Refine Theory</option>
                <option value="refinement-loop">Refinement Loop</option>
                <option value="evolve-loop">Evolve Theory Loop</option>
              </select>
            </div>

            {addonType === 'streamline-theory' && (
              <div>
                <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Streamlining Direction (Optional)</label>
                <input
                  type="text"
                  value={direction}
                  onChange={e => setDirection(e.target.value)}
                  placeholder="e.g., focus on aspect XY"
                  className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold placeholder:text-gray-200"
                />
              </div>
            )}

            {addonType === 'refinement-loop' && (
              <>
                <div>
                  <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Max Refinement Iterations</label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    required
                    value={maxRefinements}
                    onChange={e => setMaxRefinements(parseInt(e.target.value, 10))}
                    className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold"
                  />
                </div>
                <label className="flex items-center gap-3 cursor-pointer group">
                  <div className="relative flex items-center justify-center w-5 h-5 border-2 border-black group-hover:border-gray-500 transition-colors">
                    <input
                      type="checkbox"
                      className="absolute opacity-0 w-full h-full cursor-pointer"
                      checked={applyExtensions}
                      onChange={e => setApplyExtensions(e.target.checked)}
                    />
                    {applyExtensions && <div className="w-3 h-3 bg-black" />}
                  </div>
                  <span className="text-xs font-bold tracking-widest">Apply Extensions</span>
                </label>
              </>
            )}

            {addonType === 'evolve-loop' && (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Iterations</label>
                    <input
                      type="number" min="1" max="10" required
                      value={evolveIterations} onChange={e => setEvolveIterations(parseInt(e.target.value, 10))}
                      className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Num Parents</label>
                    <input
                      type="number" min="1" max="10" required
                      value={numParents} onChange={e => setNumParents(parseInt(e.target.value, 10))}
                      className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Streamline Prob (0-1)</label>
                    <input
                      type="number" min="0" max="1" step="any" required
                      value={maxStreamlineProb} onChange={e => setMaxStreamlineProb(parseFloat(e.target.value))}
                      className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Extra Scores</label>
                    <input
                      type="number" min="0" max="10" required
                      value={numExtraScores} onChange={e => setNumExtraScores(parseInt(e.target.value, 10))}
                      className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold"
                    />
                  </div>
                </div>
              </>
            )}

            <div className="flex gap-4 mt-8 pt-4 border-t border-gray-100">
              <button
                type="submit"
                disabled={isBackendDown}
                className="flex-1 bg-black text-white p-4 font-black text-sm tracking-widest hover:bg-gray-800 transition-all flex items-center justify-center gap-2 disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
              >
                {isBackendDown ? 'Backend Offline' : 'Add Step'} <ChevronRight size={18} />
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

