import React, { useState } from 'react'
import { XCircle, Folder, Cpu, ChevronRight } from 'lucide-react'
import * as api from '../api'

interface CreateTaskModalProps {
  onClose: () => void;
  onCreated: (task: api.Task) => void;
  isBackendDown: boolean;
}

export function CreateTaskModal({ onClose, onCreated, isBackendDown }: CreateTaskModalProps) {
  const [newPhenomenon, setNewPhenomenon] = useState('')
  const [newEnvFolder, setNewEnvFolder] = useState('')
  const [newFramework, setNewFramework] = useState('claude')
  const [newModel, setNewModel] = useState('')

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const task = await api.createTask({
        phenomenon: newPhenomenon,
        env_folder: newEnvFolder,
        framework: newFramework,
        model: newModel || undefined
      })
      onCreated(task)
    } catch (e: any) {
      alert(e.message || "Failed to create task")
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-white border-2 border-black p-8 w-full max-w-lg shadow-[12px_12px_0px_0px_rgba(0,0,0,1)]">
        <div className="flex justify-between items-center mb-8">
          <h2 className="text-2xl font-black uppercase tracking-tighter">Start Research</h2>
          <button onClick={onClose} className="hover:rotate-90 transition-transform">
            <XCircle size={24} />
          </button>
        </div>
        
        <form onSubmit={handleCreate} className="flex flex-col gap-6">
          <div>
            <label className="block text-[10px] font-black mb-2 uppercase tracking-widest text-gray-400">Phenomenon to Explain</label>
            <textarea 
              autoFocus
              required
              rows={4}
              value={newPhenomenon}
              onChange={e => setNewPhenomenon(e.target.value)}
              placeholder="Describe the phenomenon in detail..."
              className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold placeholder:text-gray-200 resize-none"
            />
          </div>
          
          <div>
            <label className="block text-[10px] font-black mb-2 uppercase tracking-widest text-gray-400">Local Environment Path</label>
            <div className="flex items-center gap-2 border-b border-gray-200 focus-within:border-black transition-colors">
              <Folder size={16} className="text-gray-300" />
              <input 
                required
                value={newEnvFolder}
                onChange={e => setNewEnvFolder(e.target.value)}
                placeholder="../sharpening_gym"
                className="w-full p-3 outline-none text-sm font-bold"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-8">
            <div>
              <label className="block text-[10px] font-black mb-2 uppercase tracking-widest text-gray-400">Agent Framework</label>
              <select 
                value={newFramework}
                onChange={e => setNewFramework(e.target.value)}
                className="w-full border border-black p-3 outline-none font-bold text-sm bg-white appearance-none cursor-pointer"
              >
                <option value="gemini">Gemini CLI</option>
                <option value="claude">Claude Code</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-black mb-2 uppercase tracking-widest text-gray-400">Model Identifier</label>
              <div className="flex items-center gap-2 border-b border-gray-200 focus-within:border-black transition-colors">
                <Cpu size={16} className="text-gray-300" />
                <input 
                  value={newModel}
                  onChange={e => setNewModel(e.target.value)}
                  placeholder="Default"
                  className="w-full p-3 outline-none text-sm font-bold"
                />
              </div>
            </div>
          </div>

          <div className="flex gap-4 mt-8">
            <button 
              type="submit"
              disabled={isBackendDown}
              className="flex-1 bg-black text-white p-4 font-black uppercase text-sm tracking-widest hover:bg-gray-800 transition-all flex items-center justify-center gap-2 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              {isBackendDown ? 'Backend Offline' : 'START RESEARCH'} <ChevronRight size={18} />
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
