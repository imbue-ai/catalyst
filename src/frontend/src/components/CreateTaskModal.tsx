import React, { useState, useRef, useEffect } from 'react'
import { XCircle, Folder, Cpu, ChevronRight, ChevronDown, Settings2 } from 'lucide-react'
import * as api from '../api'

interface CreateTaskModalProps {
  onClose: () => void;
  onCreated: (task: api.Task) => void;
  isBackendDown: boolean;
}

type WorkflowType = 'develop-theory' | 'develop-theory-linear' | 'refine-theory-idea' | 'refine-theory-idea-linear' | 'import-theory';

export function CreateTaskModal({ onClose, onCreated, isBackendDown }: CreateTaskModalProps) {
  const [activeTab, setActiveTab] = useState<WorkflowType>('develop-theory')
  const [showAdditional, setShowAdditional] = useState(false)
  const [showTemplateDropdown, setShowTemplateDropdown] = useState(false)
  const templateDropdownRef = useRef<HTMLDivElement>(null)

  // Templates
  const [templates, setTemplates] = useState<string[]>([])

  useEffect(() => {
    api.getTemplates().then(setTemplates).catch(console.error)
  }, [])

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (templateDropdownRef.current && !templateDropdownRef.current.contains(event.target as Node)) {
        setShowTemplateDropdown(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  // State for all inputs
  const [inputs, setInputs] = useState({
    phenomenon: '',
    idea: '',
    importFilePath: '',
    numRootTheories: 3,
    maxRefinements: 3,
    evolveIterations: 3,
    numParents: 3,
    maxStreamlineProb: 0.5,
    numExtraScores: 5,
    applyExpansions: '',
    templateFolder: '',
    framework: 'claude',
    model: ''
  })

  const updateInput = (key: keyof typeof inputs, value: any) => {
    setInputs(prev => ({ ...prev, [key]: value }))
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()

    let workflow_inputs: any = {}
    if (activeTab === 'develop-theory') {
      workflow_inputs = {
        phenomenon: inputs.phenomenon,
        num_root_theories: inputs.numRootTheories,
        max_refinements: inputs.maxRefinements,
        evolve_iterations: inputs.evolveIterations,
        num_parents: inputs.numParents,
        max_streamline_prob: inputs.maxStreamlineProb,
        num_extra_scores: inputs.numExtraScores,
        apply_expansions: inputs.applyExpansions || undefined
      }
    } else if (activeTab === 'develop-theory-linear') {
      workflow_inputs = { phenomenon: inputs.phenomenon, max_refinements: inputs.maxRefinements, apply_expansions: inputs.applyExpansions || undefined }
    } else if (activeTab === 'refine-theory-idea') {
      workflow_inputs = {
        idea: inputs.idea,
        apply_expansions: inputs.applyExpansions || undefined,
        max_refinements: inputs.maxRefinements,
        evolve_iterations: inputs.evolveIterations,
        num_parents: inputs.numParents,
        max_streamline_prob: inputs.maxStreamlineProb,
        num_extra_scores: inputs.numExtraScores
      }
    } else if (activeTab === 'refine-theory-idea-linear') {
      workflow_inputs = { idea: inputs.idea, apply_expansions: inputs.applyExpansions || undefined, max_refinements: inputs.maxRefinements }
    } else if (activeTab === 'import-theory') {
      workflow_inputs = { file_path: inputs.importFilePath }
    }

    try {
      const task = await api.createTask({
        workflow_name: activeTab,
        workflow_inputs,
        template_folder: inputs.templateFolder || undefined,
        framework: inputs.framework,
        model: inputs.model || undefined
      })
      onCreated(task)
    } catch (e: any) {
      alert(e.message || "Failed to create task")
    }
  }

  const isEvolve = activeTab === 'develop-theory' || activeTab === 'refine-theory-idea'
  const isImport = activeTab === 'import-theory'

  const getTabLabel = (tab: WorkflowType) => {
    switch (tab) {
      case 'develop-theory': return 'Develop Theory';
      case 'develop-theory-linear': return 'Develop Theory (Linear)';
      case 'refine-theory-idea': return 'Refine Idea';
      case 'refine-theory-idea-linear': return 'Refine Idea (Linear)';
      case 'import-theory': return 'Import';
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-white border-2 border-black p-8 w-full max-w-4xl shadow-[12px_12px_0px_0px_rgba(0,0,0,1)] flex flex-col h-[1000px] max-h-[90vh]">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-black tracking-tighter">Start Research</h2>
          <button onClick={onClose} className="hover:rotate-90 transition-transform">
            <XCircle size={24} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b-2 border-black mb-8 overflow-x-auto no-scrollbar">
          {(['develop-theory', 'develop-theory-linear', 'refine-theory-idea', 'refine-theory-idea-linear', 'import-theory'] as WorkflowType[]).map(tab => (
            <button
              key={tab}
              type="button"
              className={`px-4 py-3 text-xs font-black tracking-widest whitespace-nowrap transition-colors ${activeTab === tab ? 'bg-black text-white' : 'text-black hover:bg-gray-100'}`}
              onClick={() => setActiveTab(tab)}
            >
              {getTabLabel(tab)}
            </button>
          ))}
        </div>

        <form onSubmit={handleCreate} className="flex-1 flex flex-col min-h-0">
          <div className="flex-1 overflow-y-auto custom-scrollbar pr-4 flex flex-col gap-8 pb-4">

            {/* Primary Input Section */}
            <div className="space-y-6">
              {(activeTab === 'develop-theory' || activeTab === 'develop-theory-linear') && (
                <div>
                  <label className="block text-[10px] font-black mb-3 tracking-widest text-gray-400">Phenomenon to Explain</label>
                  <textarea
                    autoFocus
                    required
                    rows={8}
                    value={inputs.phenomenon}
                    onChange={e => updateInput('phenomenon', e.target.value)}
                    placeholder="Describe the phenomenon that you want me to research..."
                    className="w-full border-2 border-black p-4 outline-none focus:bg-gray-50 text-sm font-bold placeholder:text-gray-200 resize-none transition-colors"
                  />
                </div>
              )}

              {(activeTab === 'refine-theory-idea' || activeTab === 'refine-theory-idea-linear') && (
                <div>
                  <label className="block text-[10px] font-black mb-3 tracking-widest text-gray-400">Idea or File Path</label>
                  <textarea
                    autoFocus
                    required
                    rows={8}
                    value={inputs.idea}
                    onChange={e => updateInput('idea', e.target.value)}
                    placeholder="Provide a theory idea or path to a markdown file..."
                    className="w-full border-2 border-black p-4 outline-none focus:bg-gray-50 text-sm font-bold placeholder:text-gray-200 resize-none transition-colors"
                  />
                </div>
              )}

              {activeTab === 'import-theory' && (
                <div>
                  <label className="block text-[10px] font-black mb-3 tracking-widest text-gray-400">File Path to Import</label>
                  <input
                    autoFocus
                    required
                    value={inputs.importFilePath}
                    onChange={e => updateInput('importFilePath', e.target.value)}
                    placeholder="/absolute/path/to/theory.md"
                    className="w-full border-2 border-black p-4 outline-none focus:bg-gray-50 text-sm font-bold placeholder:text-gray-200 transition-colors"
                  />
                </div>
              )}
            </div>

            {/* Global Settings (Always Visible) */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="md:col-span-1">
                <label className="block text-[10px] font-black mb-3 tracking-widest text-gray-400">Template</label>
                <div className="flex items-center gap-3 border-2 border-black p-3 focus-within:bg-gray-50 transition-colors relative" ref={templateDropdownRef}>
                  <Folder size={18} className="text-black shrink-0" />
                  <input
                    value={inputs.templateFolder}
                    onChange={e => updateInput('templateFolder', e.target.value)}
                    placeholder="Path or pick from list"
                    className="w-full outline-none text-sm font-bold bg-transparent"
                  />
                  <button
                    type="button"
                    onClick={() => setShowTemplateDropdown(!showTemplateDropdown)}
                    className="hover:text-gray-500 transition-colors"
                  >
                    <ChevronDown size={14} className={`transition-transform ${showTemplateDropdown ? 'rotate-180' : ''}`} />
                  </button>

                  {showTemplateDropdown && (
                    <div className="absolute left-0 right-0 top-full mt-2 bg-white border-2 border-black shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] z-50 max-h-60 overflow-y-auto custom-scrollbar">
                      <button
                        type="button"
                        onClick={() => { updateInput('templateFolder', ''); setShowTemplateDropdown(false); }}
                        className="w-full text-left px-4 py-3 text-xs font-bold hover:bg-black hover:text-white transition-colors border-b border-gray-100 uppercase tracking-widest"
                      >
                        Default (None)
                      </button>
                      {templates.map(t => (
                        <button
                          key={t}
                          type="button"
                          onClick={() => { updateInput('templateFolder', `../templates/${t}`); setShowTemplateDropdown(false); }}
                          className="w-full text-left px-4 py-3 text-xs font-bold hover:bg-black hover:text-white transition-colors border-b border-gray-100 last:border-0"
                        >
                          {t}
                        </button>
                      ))}
                      {templates.length === 0 && (
                        <div className="px-4 py-3 text-xs font-bold text-gray-400 italic">No templates found</div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-black mb-3 tracking-widest text-gray-400">Agent Framework</label>
                <div className="relative group">
                  <select
                    value={inputs.framework}
                    onChange={e => updateInput('framework', e.target.value)}
                    className="w-full border-2 border-black p-3 pr-10 outline-none font-bold text-sm bg-white appearance-none cursor-pointer focus:bg-gray-50 transition-colors"
                  >
                    <option value="claude">Claude Code</option>
                    <option value="gemini">Gemini CLI</option>
                  </select>
                  <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-black group-hover:translate-y-[-40%] transition-transform">
                    <ChevronDown size={14} />
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-black mb-3 tracking-widest text-gray-400">Model Identifier</label>
                <div className="flex items-center gap-3 border-2 border-black p-3 focus-within:bg-gray-50 transition-colors">
                  <Cpu size={18} className="text-black shrink-0" />
                  <input
                    value={inputs.model}
                    onChange={e => updateInput('model', e.target.value)}
                    placeholder="Default"
                    className="w-full outline-none text-sm font-bold bg-transparent"
                  />
                </div>
              </div>
            </div>

            {/* Collapsible Additional Parameters */}
            {!isImport && (
              <div className="space-y-6">
                <button
                  type="button"
                  onClick={() => setShowAdditional(!showAdditional)}
                  className="flex items-center gap-2 text-[10px] font-black tracking-widest hover:text-gray-500 transition-colors group"
                >
                  <Settings2 size={14} />
                  <span>Additional Parameters</span>
                  {showAdditional ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </button>

                {showAdditional && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-6 p-6 border-2 border-dashed border-gray-200">
                    {activeTab === 'develop-theory' && (
                      <div className="col-span-1">
                        <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Root Theories</label>
                        <input
                          type="number" min="1" max="20" required
                          value={inputs.numRootTheories}
                          onChange={e => updateInput('numRootTheories', parseInt(e.target.value, 10))}
                          className="w-full border-2 border-black p-2 outline-none text-sm font-bold"
                        />
                      </div>
                    )}

                    {(activeTab === 'develop-theory-linear' || activeTab === 'refine-theory-idea-linear') && (
                      <div className="col-span-1">
                        <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Max Refinements</label>
                        <input
                          type="number" min="0" max="10" required
                          value={inputs.maxRefinements}
                          onChange={e => updateInput('maxRefinements', parseInt(e.target.value, 10))}
                          className="w-full border-2 border-black p-2 outline-none text-sm font-bold"
                        />
                      </div>
                    )}

                    {isEvolve && (
                      <>
                        <div className="col-span-1">
                          <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Evolve Iterations</label>
                          <input
                            type="number" min="0" max="10" required
                            value={inputs.evolveIterations}
                            onChange={e => updateInput('evolveIterations', parseInt(e.target.value, 10))}
                            className="w-full border-2 border-black p-2 outline-none text-sm font-bold"
                          />
                        </div>
                        <div className="col-span-1">
                          <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Num Parents</label>
                          <input
                            type="number" min="1" max="10" required
                            value={inputs.numParents}
                            onChange={e => updateInput('numParents', parseInt(e.target.value, 10))}
                            className="w-full border-2 border-black p-2 outline-none text-sm font-bold"
                          />
                        </div>
                        <div className="col-span-1">
                          <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Max Streamline Prob</label>
                          <input
                            type="number" min="0" max="1" step="any" required
                            value={inputs.maxStreamlineProb}
                            onChange={e => updateInput('maxStreamlineProb', parseFloat(e.target.value))}
                            className="w-full border-2 border-black p-2 outline-none text-sm font-bold"
                          />
                        </div>
                        <div className="col-span-1">
                          <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Extra Scores</label>
                          <input
                            type="number" min="0" max="10" required
                            value={inputs.numExtraScores}
                            onChange={e => updateInput('numExtraScores', parseInt(e.target.value, 10))}
                            className="w-full border-2 border-black p-2 outline-none text-sm font-bold"
                          />
                        </div>
                      </>
                    )}

                    {!isImport && (
                      <div className="col-span-1">
                        <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Apply Expansion Reviews</label>
                        <select
                          value={inputs.applyExpansions}
                          onChange={e => updateInput('applyExpansions', e.target.value)}
                          className="w-full border-2 border-black p-2 outline-none text-sm font-bold bg-white cursor-pointer"
                        >
                          <option value="">Auto (Default)</option>
                          <option value="always">Always</option>
                          <option value="never">Never</option>
                        </select>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="flex gap-4 mt-8 pt-4 border-t border-gray-100 shrink-0">
            <button
              type="submit"
              disabled={isBackendDown}
              className="flex-1 bg-black text-white p-5 font-black text-sm tracking-widest hover:bg-gray-800 transition-all flex items-center justify-center gap-3 disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
            >
              {isBackendDown ? 'Backend Offline' : 'Start Research'} <ChevronRight size={20} />
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
