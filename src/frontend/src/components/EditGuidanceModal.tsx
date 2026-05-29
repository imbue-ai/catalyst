import { useState } from 'react'

interface EditGuidanceModalProps {
  onClose: () => void;
  onSave: (guidance: string) => Promise<void>;
  initialGuidance: string;
}

export function EditGuidanceModal({ onClose, onSave, initialGuidance }: EditGuidanceModalProps) {
  const [guidance, setGuidance] = useState(initialGuidance)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async () => {
    setIsSubmitting(true)
    try {
      await onSave(guidance)
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
        </p>
        <p className="text-xs font-bold text-gray-400 mb-6 tracking-tight leading-relaxed">
          Any changes will only apply to future steps that are not yet running.
        </p>

        <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">
          Research Guidance
        </label>
        <textarea 
          autoFocus
          value={guidance}
          onChange={e => setGuidance(e.target.value)}
          placeholder="No additional guidance."
          rows={15}
          className="w-full border-2 border-black p-3 outline-none bg-gray-50/50 text-sm font-bold mb-8 resize-y min-h-[320px]"
        />

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
