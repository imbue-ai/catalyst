import { useState } from 'react'

interface DeleteConfirmModalProps {
  onClose: () => void;
  onDelete: () => void;
  deleteInput: string;
  setDeleteInput: (val: string) => void;
}

export function DeleteConfirmModal({ onClose, onDelete, deleteInput, setDeleteInput }: DeleteConfirmModalProps) {
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-[60]">
      <div className="bg-white border-2 border-red-600 p-8 w-full max-w-md shadow-[12px_12px_0px_0px_rgba(220,38,38,1)]">
        <h2 className="text-2xl font-black uppercase tracking-tighter text-red-600 mb-4">Confirm Deletion</h2>
        <p className="text-sm font-bold text-gray-500 mb-6 uppercase tracking-tight leading-relaxed">
          This will permanently delete the research project and its temporary database folder. 
          This action cannot be undone.
        </p>
        <label className="block text-[10px] font-black mb-2 uppercase tracking-widest text-gray-400">Type "delete" to confirm</label>
        <input 
          autoFocus
          value={deleteInput}
          onChange={e => setDeleteInput(e.target.value)}
          placeholder="delete"
          className="w-full border-b-2 border-red-600 p-3 outline-none bg-red-50/30 text-sm font-bold mb-8"
        />
        <div className="flex gap-4">
          <button 
            onClick={onClose}
            className="flex-1 border border-black p-4 font-black uppercase text-sm tracking-widest hover:bg-gray-100"
          >
            Cancel
          </button>
          <button 
            onClick={onDelete}
            disabled={deleteInput.toLowerCase() !== 'delete'}
            className="flex-1 bg-red-600 text-white p-4 font-black uppercase text-sm tracking-widest hover:bg-red-700 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Delete Task
          </button>
        </div>
      </div>
    </div>
  )
}
