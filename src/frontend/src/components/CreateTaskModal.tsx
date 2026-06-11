import React, { useState, useRef, useEffect, useLayoutEffect } from 'react'
import { XCircle, FileText, Lightbulb, Sparkles, GitMerge, GitCommit, UploadCloud, Folder, HelpCircle, Settings2, ChevronRight, ChevronDown } from 'lucide-react'
import * as api from '../api'
import { useWorkflowParams } from '../hooks/useWorkflowParams'
import { AdditionalParamsSection } from './AdditionalParamsSection'
import { HarnessSettings } from './HarnessSettings'

interface CreateTaskModalProps {
  onClose: () => void;
  onCreated: (task: api.Task) => void;
  isBackendDown: boolean;
}

type WorkflowType = 'develop-theory' | 'develop-theory-linear' | 'refine-theory-idea' | 'refine-theory-idea-linear' | 'import-theory';
type InputCategory = 'phenomenon' | 'idea' | 'draft';

const CATEGORY_WORKFLOWS: Record<InputCategory, { id: WorkflowType, label: string, description: string, icon: React.ReactNode }[]> = {
  'phenomenon': [
    { id: 'develop-theory', label: 'Develop a Theory (Evolution)', description: 'Autonomously develop a theory to explain a phenomenon. Uses evolutionary methods to explore a diverse population of directions.', icon: <GitMerge size={18} /> },
    { id: 'develop-theory-linear', label: 'Develop a Theory (Linear)', description: 'Autonomously develop a theory to explain a phenomenon.', icon: <GitCommit size={18} /> }
  ],
  'idea': [
    { id: 'refine-theory-idea', label: 'Refine Idea (Evolution)', description: 'Flesh out a theory idea into a complete theory by gathering supporting evidence and performing refinement loops. Uses evolutionary methods to explore a diverse population of directions.', icon: <GitMerge size={18} /> },
    { id: 'refine-theory-idea-linear', label: 'Refine Idea (Linear)', description: 'Flesh out a theory idea into a complete theory by gathering supporting evidence and performing refinement loops.', icon: <GitCommit size={18} /> }
  ],
  'draft': [
    { id: 'import-theory', label: 'Import', description: 'Import an existing theory. You can add further steps later on.', icon: <UploadCloud size={18} /> }
  ]
};

export function CreateTaskModal({ onClose, onCreated, isBackendDown }: CreateTaskModalProps) {
  const [inputCategory, setInputCategory] = useState<InputCategory>('phenomenon')
  const [activeTab, setActiveTab] = useState<WorkflowType>('develop-theory')

  const [showAdditional, setShowAdditional] = useState(false)
  const [showTemplateDropdown, setShowTemplateDropdown] = useState(false)
  const templateDropdownRef = useRef<HTMLDivElement>(null)
  const templateMenuRef = useRef<HTMLDivElement>(null)
  const [openTemplateUpward, setOpenTemplateUpward] = useState(false)
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  // Templates
  const [templates, setTemplates] = useState<string[]>([])
  // Harnesses
  const [harnesses, setHarnesses] = useState<api.HarnessInfo[]>([])

  useLayoutEffect(() => {
    if (showTemplateDropdown && templateDropdownRef.current && templateMenuRef.current) {
      const triggerRect = templateDropdownRef.current.getBoundingClientRect()
      const menuRect = templateMenuRef.current.getBoundingClientRect()
      let spaceBelow = window.innerHeight - triggerRect.bottom
      if (scrollContainerRef.current) {
        const containerRect = scrollContainerRef.current.getBoundingClientRect()
        spaceBelow = containerRect.bottom - triggerRect.bottom
      }
      setOpenTemplateUpward(spaceBelow < menuRect.height)
    }
  }, [showTemplateDropdown, templates.length])

  useEffect(() => {
    api.getTemplates().then(setTemplates).catch(console.error)
  }, [])

  useEffect(() => {
    let active = true
    api.getHarnesses().then(data => {
      if (active) {
        setHarnesses(data)
        if (data.length > 0) {
          const firstAvailable = data.find(h => h.available)
          const defaultHarness = firstAvailable ? firstAvailable.name : data[0].name
          setInputs(prev => ({ ...prev, framework: defaultHarness }))
        }
      }
    }).catch(console.error)
    return () => { active = false }
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
  const {
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
    correctnessWeight,
    setCorrectnessWeight,
    powerWeight,
    setPowerWeight,
    adherenceWeight,
    setAdherenceWeight,
    generateIntermediateResearchSummaries,
    setGenerateIntermediateResearchSummaries
  } = useWorkflowParams()

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [inputs, setInputs] = useState({
    phenomenon: '',
    idea: '',
    templateFolder: '',
    framework: '',
    model: '',
    effort: ''
  })

  const selectedHarness = harnesses.find(h => h.name === inputs.framework)
  const effortOptions = selectedHarness?.effort_options
  const hasEffort = !!(effortOptions && effortOptions.length > 0)

  const updateInput = (key: keyof typeof inputs, value: any) => {
    setInputs(prev => ({ ...prev, [key]: value }))
  }

  const handleCategoryChange = (cat: InputCategory) => {
    setInputCategory(cat);
    setActiveTab(CATEGORY_WORKFLOWS[cat][0].id);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()

    let workflow_inputs: any = {}
    if (activeTab === 'develop-theory') {
      workflow_inputs = {
        phenomenon: inputs.phenomenon,
        num_root_theories: numRootTheories,
        max_refinements: maxRefinements,
        evolve_iterations: evolveIterations,
        num_parents: numParents,
        max_streamline_prob: maxStreamlineProb,
        write_different_prob: writeDifferentProb,
        num_extra_scores: numExtraScores,
        apply_expansions: applyExpansions || undefined,
        generate_intermediate_research_summaries: generateIntermediateResearchSummaries
      }
    } else if (activeTab === 'develop-theory-linear') {
      workflow_inputs = {
        phenomenon: inputs.phenomenon,
        max_refinements: maxRefinements,
        apply_expansions: applyExpansions || undefined,
        generate_intermediate_research_summaries: generateIntermediateResearchSummaries
      }
    } else if (activeTab === 'refine-theory-idea') {
      workflow_inputs = {
        idea: inputs.idea,
        apply_expansions: applyExpansions || undefined,
        max_refinements: maxRefinements,
        evolve_iterations: evolveIterations,
        num_parents: numParents,
        max_streamline_prob: maxStreamlineProb,
        write_different_prob: writeDifferentProb,
        num_extra_scores: numExtraScores,
        generate_intermediate_research_summaries: generateIntermediateResearchSummaries
      }
    } else if (activeTab === 'refine-theory-idea-linear') {
      workflow_inputs = {
        idea: inputs.idea,
        apply_expansions: applyExpansions || undefined,
        max_refinements: maxRefinements,
        generate_intermediate_research_summaries: generateIntermediateResearchSummaries
      }
    } else if (activeTab === 'import-theory') {
      workflow_inputs = {}
    }

    try {
      const task = await api.createTask({
        workflow_name: activeTab,
        workflow_inputs,
        template_folder: inputs.templateFolder || undefined,
        framework: inputs.framework,
        model: inputs.model || undefined,
        effort: hasEffort ? (inputs.effort || undefined) : undefined,
        theory_scoring_weights: isEvolve ? {
          correctness_weight: correctnessWeight,
          power_weight: powerWeight,
          adherence_weight: adherenceWeight
        } : undefined,
        file: selectedFile || undefined
      })
      onCreated(task)
    } catch (e: any) {
      alert(e.message || "Failed to create task")
    }
  }

  const isEvolve = activeTab === 'develop-theory' || activeTab === 'refine-theory-idea'
  const isImport = activeTab === 'import-theory'

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-white border-2 border-black p-8 w-full max-w-6xl shadow-[12px_12px_0px_0px_rgba(0,0,0,1)] flex flex-col h-[1200px] max-h-[90vh]">
        <div className="flex justify-between items-center mb-8 shrink-0">
          <h2 className="text-2xl font-black tracking-tighter">Start Research</h2>
          <button onClick={onClose} className="hover:rotate-90 transition-transform">
            <XCircle size={24} />
          </button>
        </div>

        <form onSubmit={handleCreate} className="flex-1 flex flex-col min-h-0">
          <div ref={scrollContainerRef} className="flex-1 overflow-y-auto custom-scrollbar pr-4 flex flex-col gap-10 pb-4">

            {/* STEP 1: Input Type */}
            <div>
              <h3 className="text-sm font-black mb-4">Step 1: I have a...</h3>
              <div className="flex flex-col md:flex-row gap-4">
                <label className={`flex-1 border-2 p-4 cursor-pointer transition-colors flex flex-col justify-center ${inputCategory === 'phenomenon' ? 'border-black bg-gray-50 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]' : 'border-gray-200 hover:border-gray-400'}`}>
                  <div className="flex items-center gap-3">
                    <input type="radio" checked={inputCategory === 'phenomenon'} onChange={() => handleCategoryChange('phenomenon')} />
                    <Sparkles size={18} className="text-gray-600" />
                    <span className="font-black text-sm">Phenomenon to Explain</span>
                  </div>
                </label>
                <label className={`flex-1 border-2 p-4 cursor-pointer transition-colors flex flex-col justify-center ${inputCategory === 'idea' ? 'border-black bg-gray-50 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]' : 'border-gray-200 hover:border-gray-400'}`}>
                  <div className="flex items-center gap-3">
                    <input type="radio" checked={inputCategory === 'idea'} onChange={() => handleCategoryChange('idea')} />
                    <Lightbulb size={18} className="text-gray-600" />
                    <span className="font-black text-sm">Theory Idea</span>
                  </div>
                </label>
                <label className={`flex-1 border-2 p-4 cursor-pointer transition-colors flex flex-col justify-center ${inputCategory === 'draft' ? 'border-black bg-gray-50 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]' : 'border-gray-200 hover:border-gray-400'}`}>
                  <div className="flex items-center gap-3">
                    <input type="radio" checked={inputCategory === 'draft'} onChange={() => handleCategoryChange('draft')} />
                    <FileText size={18} className="text-gray-600" />
                    <span className="font-black text-sm">Existing Theory Draft</span>
                  </div>
                </label>
              </div>
            </div>

            {/* STEP 2: Action */}
            <div>
              <h3 className="text-sm font-black mb-4">Step 2: And I want to...</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {CATEGORY_WORKFLOWS[inputCategory].map(workflow => (
                  <label key={workflow.id} className={`border-2 p-4 cursor-pointer transition-colors flex flex-col gap-2 ${activeTab === workflow.id ? 'border-black bg-gray-50 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]' : 'border-gray-200 hover:border-gray-400'}`}>
                    <div className="flex items-start gap-3">
                      <input type="radio" name="workflowType" className="mt-1" checked={activeTab === workflow.id} onChange={() => setActiveTab(workflow.id)} />
                      <div>
                        <div className="flex items-center gap-2 mb-2 text-black">
                          {workflow.icon}
                          <span className="font-black text-sm">{workflow.label}</span>
                        </div>
                        <p className="text-[10px] text-gray-500 font-bold leading-relaxed mt-2">
                          {workflow.description}
                        </p>
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* STEP 3: Configuration */}
            <div>
              <h3 className="text-sm font-black mb-4">Step 3: Configuration</h3>
              <div className="flex flex-col gap-6">

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
                    <div className="space-y-4">
                      <div>
                        <label className="block text-[10px] font-black mb-3 tracking-widest text-gray-400">Theory Idea</label>
                        <textarea
                          autoFocus
                          required={!selectedFile}
                          rows={8}
                          value={inputs.idea}
                          onChange={e => updateInput('idea', e.target.value)}
                          placeholder="Provide a theory idea..."
                          className="w-full border-2 border-black p-4 outline-none focus:bg-gray-50 text-sm font-bold placeholder:text-gray-200 resize-none transition-colors"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] font-black mb-3 tracking-widest text-gray-400">Optional: Upload Context File (.md, .tex, .pdf, .zip)</label>
                        <input
                          type="file"
                          accept=".md,.tex,.pdf,.zip"
                          onChange={e => setSelectedFile(e.target.files?.[0] || null)}
                          className="w-full border-2 border-black p-4 outline-none focus:bg-gray-50 text-sm font-bold transition-colors file:mr-4 file:py-2 file:px-4 file:border-0 file:text-xs file:font-black file:tracking-widest file:bg-black file:text-white hover:file:bg-gray-800 cursor-pointer"
                        />
                      </div>
                    </div>
                  )}

                  {activeTab === 'import-theory' && (
                    <div>
                      <label className="block text-[10px] font-black mb-3 tracking-widest text-gray-400">Theory File to Import (.md, .tex, .pdf, .zip)</label>
                      <input
                        autoFocus
                        type="file"
                        required
                        accept=".md,.tex,.pdf,.zip"
                        onChange={e => setSelectedFile(e.target.files?.[0] || null)}
                        className="w-full border-2 border-black p-4 outline-none focus:bg-gray-50 text-sm font-bold transition-colors file:mr-4 file:py-2 file:px-4 file:border-0 file:text-xs file:font-black file:tracking-widest file:bg-black file:text-white hover:file:bg-gray-800 cursor-pointer"
                      />
                    </div>
                  )}
                </div>

                {/* Global Settings (Always Visible) */}
                <div className="space-y-6">
                  {/* Template Row */}
                  <div>
                    <label className="flex items-center gap-1.5 text-[10px] font-black mb-3 tracking-widest text-gray-400">
                      Optional: Template
                      <div className="relative group/tooltip flex items-center justify-center">
                        <HelpCircle size={12} className="cursor-help hover:text-black transition-colors" />
                        <div className="absolute bottom-full left-0 mb-2 w-64 p-3 bg-black text-white text-[10px] leading-relaxed hidden group-hover/tooltip:block z-50 normal-case font-bold shadow-[4px_4px_0px_0px_rgba(0,0,0,0.2)]">
                          A template provides additional context to the agent. They can contain custom AGENTS.md files, prior literature that you want the agent to consider, or experimentation tools.
                          <div className="absolute top-full left-2 border-4 border-transparent border-t-black"></div>
                        </div>
                      </div>
                    </label>
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
                        <div ref={templateMenuRef} className={`absolute left-0 right-0 z-50 max-h-60 overflow-y-auto custom-scrollbar bg-white border-2 border-black ${
                          openTemplateUpward 
                            ? 'bottom-full mb-2 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]' 
                            : 'top-full mt-2 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]'
                        }`}>
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

                  {/* Framework, Model, and Effort Row */}
                  <HarnessSettings
                    framework={inputs.framework}
                    model={inputs.model}
                    effort={inputs.effort}
                    harnesses={harnesses}
                    onChange={(updates) => {
                      if (updates.framework !== undefined) {
                        updateInput('framework', updates.framework)
                        updateInput('model', '')
                        updateInput('effort', '')
                      }
                      if (updates.model !== undefined) updateInput('model', updates.model)
                      if (updates.effort !== undefined) updateInput('effort', updates.effort)
                    }}
                    isCompact={false}
                    scrollContainerRef={scrollContainerRef}
                  />
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
                      <AdditionalParamsSection
                        showRootTheories={activeTab === 'develop-theory'}
                        showMaxRefinements={activeTab === 'develop-theory-linear' || activeTab === 'refine-theory-idea-linear'}
                        showEvolveParams={isEvolve}
                        showApplyExpansions={!isImport}
                        showGenerateIntermediateResearchSummaries={!isImport}
                        numRootTheories={numRootTheories}
                        setNumRootTheories={setNumRootTheories}
                        maxRefinements={maxRefinements}
                        setMaxRefinements={setMaxRefinements}
                        evolveIterations={evolveIterations}
                        setEvolveIterations={setEvolveIterations}
                        numParents={numParents}
                        setNumParents={setNumParents}
                        maxStreamlineProb={maxStreamlineProb}
                        setMaxStreamlineProb={setMaxStreamlineProb}
                        writeDifferentProb={writeDifferentProb}
                        setWriteDifferentProb={setWriteDifferentProb}
                        numExtraScores={numExtraScores}
                        setNumExtraScores={setNumExtraScores}
                        applyExpansions={applyExpansions}
                        setApplyExpansions={setApplyExpansions}
                        showScoringWeights={isEvolve}
                        correctnessWeight={correctnessWeight}
                        setCorrectnessWeight={setCorrectnessWeight}
                        powerWeight={powerWeight}
                        setPowerWeight={setPowerWeight}
                        adherenceWeight={adherenceWeight}
                        setAdherenceWeight={setAdherenceWeight}
                        generateIntermediateResearchSummaries={generateIntermediateResearchSummaries}
                        setGenerateIntermediateResearchSummaries={setGenerateIntermediateResearchSummaries}
                      />
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="flex gap-4 pt-6 border-t border-gray-100 shrink-0">
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
