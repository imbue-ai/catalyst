import React, { useState } from 'react'
import { XCircle, Folder, Cpu, ChevronRight } from 'lucide-react'
import * as api from '../api'

interface CreateTaskModalProps {
  onClose: () => void;
  onCreated: (task: api.Task) => void;
  isBackendDown: boolean;
}

export function CreateTaskModal({ onClose, onCreated, isBackendDown }: CreateTaskModalProps) {
  const [activeTab, setActiveTab] = useState<'develop-theory' | 'develop-theory-linear' | 'refine-theory-idea' | 'refine-theory-idea-linear' | 'import-theory'>('develop-theory')

  // Develop Theory Inputs
  const [newPhenomenon, setNewPhenomenon] = useState('')
  const [numRootTheories, setNumRootTheories] = useState(3)

  // Refine Theory Idea Inputs
  const [newIdea, setNewIdea] = useState('')
  const [applyExtensions, setApplyExtensions] = useState(false)

  // Import Theory Inputs
  const [importFilePath, setImportFilePath] = useState('')

  // Shared Inputs
  const [templateFolder, setTemplateFolder] = useState('')
  const [newFramework, setNewFramework] = useState('claude')
  const [newModel, setNewModel] = useState('')
  const [maxRefinements, setMaxRefinements] = useState(3)

  // Evolve Parameters
  const [evolveIterations, setEvolveIterations] = useState(3)
  const [numParents, setNumParents] = useState(3)
  const [streamlineProb, setStreamlineProb] = useState(0.25)
  const [numExtraScores, setNumExtraScores] = useState(5)

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()

    let workflow_inputs: any = {}
    if (activeTab === 'develop-theory') {
      workflow_inputs = {
        phenomenon: newPhenomenon,
        num_root_theories: numRootTheories,
        max_refinements: maxRefinements,
        evolve_iterations: evolveIterations,
        num_parents: numParents,
        streamline_prob: streamlineProb,
        num_extra_scores: numExtraScores
      }
    } else if (activeTab === 'develop-theory-linear') {
      workflow_inputs = { phenomenon: newPhenomenon, max_refinements: maxRefinements }
    } else if (activeTab === 'refine-theory-idea') {
      workflow_inputs = {
        idea: newIdea,
        apply_extensions: applyExtensions,
        max_refinements: maxRefinements,
        evolve_iterations: evolveIterations,
        num_parents: numParents,
        streamline_prob: streamlineProb,
        num_extra_scores: numExtraScores
      }
    } else if (activeTab === 'refine-theory-idea-linear') {
      workflow_inputs = { idea: newIdea, apply_extensions: applyExtensions, max_refinements: maxRefinements }
    } else if (activeTab === 'import-theory') {
      workflow_inputs = { file_path: importFilePath }
    }

    try {
      const task = await api.createTask({
        workflow_name: activeTab,
        workflow_inputs,
        template_folder: templateFolder || undefined,
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
      <div className="bg-white border-2 border-black p-8 w-full max-w-4xl shadow-[12px_12px_0px_0px_rgba(0,0,0,1)] flex flex-col max-h-[90vh]">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-black tracking-tighter">Start Research</h2>
          <button onClick={onClose} className="hover:rotate-90 transition-transform">
            <XCircle size={24} />
          </button>
        </div>

        <div className="flex flex-wrap border-b-2 border-black mb-6">
          <button
            type="button"
            className={`px-4 py-2 text-xs font-black tracking-widest transition-colors ${activeTab === 'develop-theory' ? 'bg-black text-white' : 'text-black hover:bg-gray-100'}`}
            onClick={() => setActiveTab('develop-theory')}
          >
            Develop Theory
          </button>
          <button
            type="button"
            className={`px-4 py-2 text-xs font-black tracking-widest transition-colors ${activeTab === 'develop-theory-linear' ? 'bg-black text-white' : 'text-black hover:bg-gray-100'}`}
            onClick={() => setActiveTab('develop-theory-linear')}
          >
            Develop Theory (Linear)
          </button>
          <button
            type="button"
            className={`px-4 py-2 text-xs font-black tracking-widest transition-colors ${activeTab === 'refine-theory-idea' ? 'bg-black text-white' : 'text-black hover:bg-gray-100'}`}
            onClick={() => setActiveTab('refine-theory-idea')}
          >
            Refine Idea
          </button>
          <button
            type="button"
            className={`px-4 py-2 text-xs font-black tracking-widest transition-colors ${activeTab === 'refine-theory-idea-linear' ? 'bg-black text-white' : 'text-black hover:bg-gray-100'}`}
            onClick={() => setActiveTab('refine-theory-idea-linear')}
          >
            Refine Idea (Linear)
          </button>
          <button
            type="button"
            className={`px-4 py-2 text-xs font-black tracking-widest transition-colors ${activeTab === 'import-theory' ? 'bg-black text-white' : 'text-black hover:bg-gray-100'}`}
            onClick={() => setActiveTab('import-theory')}
          >
            Import
          </button>
        </div>

        <form onSubmit={handleCreate} className="flex flex-col gap-6 overflow-y-auto custom-scrollbar pr-2">
          {activeTab === 'develop-theory' || activeTab === 'develop-theory-linear' ? (
            <>
              <div>
                <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Phenomenon to Explain</label>
                <textarea
                  autoFocus
                  required
                  rows={8}
                  value={newPhenomenon}
                  onChange={e => setNewPhenomenon(e.target.value)}
                  placeholder="Describe the phenomenon in detail..."
                  className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold placeholder:text-gray-200 resize-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-8">
                {activeTab === 'develop-theory' && (
                  <div>
                    <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Number of Root Theories</label>
                    <input
                      type="number"
                      min="1"
                      max="20"
                      required
                      value={numRootTheories}
                      onChange={e => setNumRootTheories(parseInt(e.target.value, 10))}
                      className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold"
                    />
                  </div>
                ) || (
                    <div>
                      <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Max Refinement Iterations</label>
                      <input
                        type="number"
                        min="0"
                        max="10"
                        required
                        value={maxRefinements}
                        onChange={e => setMaxRefinements(parseInt(e.target.value, 10))}
                        className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold"
                      />
                    </div>
                  )}
              </div>

              {activeTab === 'develop-theory' && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Evolve Iterations</label>
                    <input type="number" min="0" max="10" required value={evolveIterations} onChange={e => setEvolveIterations(parseInt(e.target.value, 10))} className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold" />
                  </div>
                  <div>
                    <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Num Parents</label>
                    <input type="number" min="1" max="10" required value={numParents} onChange={e => setNumParents(parseInt(e.target.value, 10))} className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold" />
                  </div>
                  <div>
                    <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Streamline Prob (0-1)</label>
                    <input type="number" min="0" max="1" step="any" required value={streamlineProb} onChange={e => setStreamlineProb(parseFloat(e.target.value))} className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold" />
                  </div>
                  <div>
                    <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Extra Scores</label>
                    <input type="number" min="0" max="10" required value={numExtraScores} onChange={e => setNumExtraScores(parseInt(e.target.value, 10))} className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold" />
                  </div>
                </div>
              )}
            </>
          ) : activeTab === 'refine-theory-idea' || activeTab === 'refine-theory-idea-linear' ? (
            <>
              <div>
                <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Idea / File Path</label>
                <textarea
                  autoFocus
                  required
                  rows={8}
                  value={newIdea}
                  onChange={e => setNewIdea(e.target.value)}
                  placeholder="Describe the idea or provide a file path..."
                  className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold placeholder:text-gray-200 resize-none"
                />
              </div>
              {activeTab === 'refine-theory-idea-linear' && (
                <div>
                  <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Max Refinement Iterations</label>
                  <input
                    type="number"
                    min="0"
                    max="10"
                    required
                    value={maxRefinements}
                    onChange={e => setMaxRefinements(parseInt(e.target.value, 10))}
                    className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold"
                  />
                </div>
              )}

              {activeTab === 'refine-theory-idea' && (
                <div className="grid grid-cols-2 gap-4 mt-4">
                  <div>
                    <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Evolve Iterations</label>
                    <input type="number" min="0" max="10" required value={evolveIterations} onChange={e => setEvolveIterations(parseInt(e.target.value, 10))} className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold" />
                  </div>
                  <div>
                    <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Num Parents</label>
                    <input type="number" min="1" max="10" required value={numParents} onChange={e => setNumParents(parseInt(e.target.value, 10))} className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold" />
                  </div>
                  <div>
                    <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Streamline Prob (0-1)</label>
                    <input type="number" min="0" max="1" step="any" required value={streamlineProb} onChange={e => setStreamlineProb(parseFloat(e.target.value))} className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold" />
                  </div>
                  <div>
                    <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Extra Scores</label>
                    <input type="number" min="0" max="10" required value={numExtraScores} onChange={e => setNumExtraScores(parseInt(e.target.value, 10))} className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold" />
                  </div>
                </div>
              )}

              <label className="flex items-center gap-3 cursor-pointer group mt-4">
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
          ) : (
            <div>
              <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">File Path to Import</label>
              <input
                autoFocus
                required
                value={importFilePath}
                onChange={e => setImportFilePath(e.target.value)}
                placeholder="/absolute/path/to/theory.md"
                className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold placeholder:text-gray-200"
              />
            </div>
          )}

          <hr className="border-t-2 border-gray-100" />

          <div>
            <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Template Folder (Optional)</label>
            <div className="flex items-center gap-2 border-b border-gray-200 focus-within:border-black transition-colors">
              <Folder size={16} className="text-gray-300" />
              <input
                value={templateFolder}
                onChange={e => setTemplateFolder(e.target.value)}
                placeholder="../templates/bifurcation"
                className="w-full p-3 outline-none text-sm font-bold"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-8">
            <div>
              <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Agent Framework</label>
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
              <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Model Identifier</label>
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

          <div className="flex gap-4 mt-8 pt-4 border-t border-gray-100">
            <button
              type="submit"
              disabled={isBackendDown}
              className="flex-1 bg-black text-white p-4 font-black text-sm tracking-widest hover:bg-gray-800 transition-all flex items-center justify-center gap-2 disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
            >
              {isBackendDown ? 'Backend Offline' : 'Start Research'} <ChevronRight size={18} />
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}