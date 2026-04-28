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

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const updatedTask = await api.createAddon(task.id, {
        type: addonType,
        theory_id: theoryId,
        direction: addonType === 'streamline-theory' && direction ? direction : undefined,
        max_refinements: addonType === 'refinement-loop' ? maxRefinements : undefined,
        apply_extensions: addonType === 'refinement-loop' ? applyExtensions : undefined
      })
      onCreated(updatedTask)
    } catch (e: any) {
      alert(e.message || "Failed to add addon workflow")
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-white border-2 border-black p-8 w-full max-w-lg shadow-[12px_12px_0px_0px_rgba(0,0,0,1)]">
        <div className="flex justify-between items-center mb-8">
          <h2 className="text-2xl font-black uppercase tracking-tighter">Add Step</h2>
          <button onClick={onClose} className="hover:rotate-90 transition-transform">
            <XCircle size={24} />
          </button>
        </div>
        
        {availableTheoryIds.length === 0 ? (
          <div className="text-sm font-bold text-red-600 mb-6">
            No theories have been generated yet in this task. Please wait for a step to output a theory_id.
          </div>
        ) : (
          <form onSubmit={handleCreate} className="flex flex-col gap-6">
            <div>
              <label className="block text-[10px] font-black mb-2 uppercase tracking-widest text-gray-400">Target Theory ID</label>
              <select 
                required
                value={theoryId}
                onChange={e => setTheoryId(e.target.value)}
                className="w-full border-2 border-black p-3 outline-none font-bold text-sm bg-white cursor-pointer"
              >
                {availableTheoryIds.map(id => (
                  <option key={id} value={id}>{id}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[10px] font-black mb-2 uppercase tracking-widest text-gray-400">Add-on Skill</label>
              <select 
                value={addonType}
                onChange={e => setAddonType(e.target.value)}
                className="w-full border-2 border-black p-3 outline-none font-bold text-sm bg-white cursor-pointer"
              >
                <option value="streamline-theory">Streamline Theory</option>
                <option value="review-theory">Review Theory</option>
                <option value="refine-theory">Refine Theory</option>
                <option value="refinement-loop">Refinement Loop</option>
              </select>
            </div>

            {addonType === 'streamline-theory' && (
              <div>
                <label className="block text-[10px] font-black mb-2 uppercase tracking-widest text-gray-400">Streamlining Direction (Optional)</label>
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
                  <label className="block text-[10px] font-black mb-2 uppercase tracking-widest text-gray-400">Max Refinement Iterations</label>
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
                  <span className="text-xs font-bold uppercase tracking-widest">Apply Extensions</span>
                </label>
              </>
            )}
            
            <div className="flex gap-4 mt-8 pt-4 border-t border-gray-100">
              <button
                type="submit"
                disabled={isBackendDown}
                className="flex-1 bg-black text-white p-4 font-black uppercase text-sm tracking-widest hover:bg-gray-800 transition-all flex items-center justify-center gap-2 disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
              >
                {isBackendDown ? 'Backend Offline' : 'ADD STEP'} <ChevronRight size={18} />
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
