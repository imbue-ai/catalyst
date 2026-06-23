import { useState } from 'react'
import type { TheoryScoringWeights } from '../api'
import { isVerifiableGoalWorkflow } from '../utils'

interface EditGuidanceModalProps {
  onClose: () => void;
  onSave: (guidance: string, weights: TheoryScoringWeights) => Promise<void>;
  initialGuidance: string;
  initialWeights?: TheoryScoringWeights;
  newlyAddedText?: string | null;
  workflowName?: string;
}

export function EditGuidanceModal({ onClose, onSave, initialGuidance, initialWeights, newlyAddedText, workflowName }: EditGuidanceModalProps) {
  const isVerifiableGoal = isVerifiableGoalWorkflow(workflowName)
  const [guidance, setGuidance] = useState(initialGuidance)
  const [correctnessWeight, setCorrectnessWeight] = useState(initialWeights?.correctness_weight ?? 0.9)
  const [powerWeight, setPowerWeight] = useState(initialWeights?.power_weight ?? 0.7)
  const [adherenceWeight, setAdherenceWeight] = useState(initialWeights?.adherence_weight ?? 0.5)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async () => {
    setIsSubmitting(true)
    try {
      await onSave(guidance, {
        correctness_weight: correctnessWeight,
        power_weight: powerWeight,
        adherence_weight: adherenceWeight,
      })
      onClose()
    } catch (e: any) {
      alert(e.message || "Failed to save guidance")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-[60]">
      <div className="bg-white border-2 border-black p-8 w-full max-w-4xl shadow-[12px_12px_0px_0px_rgba(0,0,0,1)]">
        <h2 className="text-2xl font-black tracking-tighter text-black mb-2">Provide Guidance</h2>
        <p className="text-xs font-bold text-gray-700 mb-2 leading-relaxed">
          Provide additional guidance to the agents within this task. E.g. direction to focus on, type of desired theory, literature to consider, etc.
          {!isVerifiableGoal && " You can also adjust the component weights of the theory scores used in evolution-based workflows."}
        </p>
        <p className="text-xs font-bold text-gray-400 mb-6 tracking-tight leading-relaxed">
          Any changes will only apply to future steps that are not yet running.
        </p>
        {newlyAddedText && (
          <style>{`
            @keyframes textarea-flash {
              0% {
                background-color: rgb(219, 234, 254);
                border-color: rgb(37, 99, 235);
                box-shadow: 0 0 12px rgba(37, 99, 235, 0.4);
              }
              30% {
                background-color: rgb(219, 234, 254);
                border-color: rgb(37, 99, 235);
                box-shadow: 0 0 12px rgba(37, 99, 235, 0.4);
              }
              100% {
                background-color: rgb(249, 250, 251);
                border-color: rgb(0, 0, 0);
                box-shadow: none;
              }
            }
            .animate-textarea-flash {
              animation: textarea-flash 2.5s ease-out forwards;
            }
          `}</style>
        )}

        <h4 className="text-xs font-black tracking-widest text-black mb-4">
          Research Guidance
        </h4>
        <textarea 
          autoFocus
          value={guidance}
          onChange={e => setGuidance(e.target.value)}
          placeholder="No additional guidance."
          rows={10}
          className={`w-full border-2 p-3 outline-none text-sm font-bold mb-6 resize-y min-h-[200px] ${
            newlyAddedText 
              ? 'animate-textarea-flash' 
              : 'border-black bg-gray-50/50'
          }`}
        />

        {!isVerifiableGoal && (
          <div className="mb-8">
            <h4 className="text-xs font-black tracking-widest text-black mb-4">Theory Scoring Weights</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
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
            </div>
          </div>
        )}

        <div className="flex gap-4">
          <button 
            onClick={onClose}
            disabled={isSubmitting}
            className="flex-1 border border-black p-4 font-black text-sm tracking-widest hover:bg-gray-100 disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
          <button 
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="flex-1 bg-black text-white p-4 font-black text-sm tracking-widest hover:bg-gray-800 disabled:opacity-50 transition-colors"
          >
            {isSubmitting ? "Saving..." : "Save Guidance"}
          </button>
        </div>
      </div>
    </div>
  )
}
