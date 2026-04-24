import { useState, useEffect } from 'react'
import { Plus, List, ArrowRight, CheckCircle, XCircle, Loader2, Database, Folder, Cpu, Terminal, ChevronRight, Activity, FlaskConical, History, Play, Square, Trash2 } from 'lucide-react'
import * as api from './api'

function App() {
  const [tasks, setTasks] = useState<api.Task[]>([])
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null)
  const [deleteInput, setDeleteInput] = useState('')
  const [newPhenomenon, setNewPhenomenon] = useState('')
  const [newEnvFolder, setNewEnvFolder] = useState('')
  const [newFramework, setNewFramework] = useState('claude')
  const [newModel, setNewModel] = useState('')

  const fetchTasks = async () => {
    try {
      const data = await api.listTasks()
      setTasks(data)
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    fetchTasks()
    const interval = setInterval(fetchTasks, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const task = await api.createTask({
        phenomenon: newPhenomenon,
        env_folder: newEnvFolder,
        framework: newFramework,
        model: newModel || undefined
      })
      setTasks([task, ...tasks])
      setSelectedTaskId(task.id)
      setShowCreate(false)
      setNewPhenomenon('')
    } catch (e: any) {
      alert(e.message || "Failed to create task")
    }
  }

  const handleDelete = async () => {
    if (deleteInput.toLowerCase() === 'delete' && showDeleteConfirm) {
      try {
        await api.deleteTask(showDeleteConfirm)
        setTasks(tasks.filter(t => t.id !== showDeleteConfirm))
        setSelectedTaskId(null)
        setShowDeleteConfirm(null)
        setDeleteInput('')
      } catch (e) {
        alert("Failed to delete task")
      }
    }
  }

  const selectedTask = tasks.find(t => t.id === selectedTaskId)

  return (
    <div className="min-h-screen bg-white text-black font-mono selection:bg-black selection:text-white">
      {/* Sidebar */}
      <div className="flex h-screen overflow-hidden">
        <aside className="w-80 border-r border-black flex flex-col bg-white">
          <div className="p-6 border-b border-black flex items-center gap-3">
            <div className="bg-black p-2 rounded-sm text-white">
              <FlaskConical size={20} />
            </div>
            <h1 className="text-lg font-black tracking-tight leading-none uppercase">
              AI Scientist<br/><span className="text-gray-400">Orchestrator</span>
            </h1>
          </div>
          
          <div className="p-4 border-b border-black flex items-center justify-between bg-gray-50/50">
            <div className="flex items-center gap-2 text-[10px] font-bold text-gray-500 uppercase tracking-widest">
              <History size={12} /> Recent Research
            </div>
            <button 
              onClick={() => setShowCreate(true)}
              className="hover:scale-110 transition-transform p-1 bg-black text-white rounded-full"
              title="New Research Task"
            >
              <Plus size={16} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto custom-scrollbar">
            {tasks.length === 0 && (
              <div className="p-12 text-center text-gray-300 italic text-sm">
                No active research threads.
              </div>
            )}
            {tasks.map(task => (
              <div 
                key={task.id}
                onClick={() => setSelectedTaskId(task.id)}
                className={`group p-4 border-b border-black cursor-pointer transition-all ${selectedTaskId === task.id ? 'bg-black text-white' : 'hover:bg-gray-50'}`}
              >
                <div className="flex justify-between items-start mb-2 gap-2">
                  <span className={`font-bold text-xs uppercase truncate flex-1 ${selectedTaskId === task.id ? 'text-white' : 'text-black'}`}>
                    {task.title || task.phenomenon}
                  </span>
                  <StatusBadge status={task.status} inverted={selectedTaskId === task.id} />
                </div>
                <div className={`text-[10px] flex flex-col gap-1 ${selectedTaskId === task.id ? 'text-gray-400' : 'text-gray-500'}`}>
                  <div className="flex items-center gap-1 truncate"><Folder size={10} /> {task.env_folder}</div>
                </div>
              </div>
            ))}
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto bg-white flex flex-col relative">
          {selectedTask ? (
            <TaskDetail task={selectedTask} onDeleteRequest={(id) => setShowDeleteConfirm(id)} />
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-20 text-center">
              <div className="w-24 h-24 border border-black rounded-full flex items-center justify-center mb-6 animate-pulse">
                 <Activity size={40} strokeWidth={1} className="text-gray-300" />
              </div>
              <h2 className="text-2xl font-black uppercase tracking-tighter mb-2">Ready for Discovery</h2>
              <p className="text-gray-400 max-w-sm text-sm">
                Select a research thread from the sidebar or start a new scientific inquiry to observe the automated theory development process.
              </p>
              <button 
                onClick={() => setShowCreate(true)}
                className="mt-8 px-6 py-3 bg-black text-white font-bold uppercase text-xs tracking-widest hover:bg-gray-800 transition-colors"
              >
                + Start New Research
              </button>
            </div>
          )}
        </main>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
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
                onClick={() => { setShowDeleteConfirm(null); setDeleteInput(''); }}
                className="flex-1 border border-black p-4 font-black uppercase text-sm tracking-widest hover:bg-gray-100"
              >
                Cancel
              </button>
              <button 
                onClick={handleDelete}
                disabled={deleteInput.toLowerCase() !== 'delete'}
                className="flex-1 bg-red-600 text-white p-4 font-black uppercase text-sm tracking-widest hover:bg-red-700 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Delete Task
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white border-2 border-black p-8 w-full max-w-lg shadow-[12px_12px_0px_0px_rgba(0,0,0,1)]">
            <div className="flex justify-between items-center mb-8">
              <h2 className="text-2xl font-black uppercase tracking-tighter">Start Research</h2>
              <button onClick={() => setShowCreate(false)} className="hover:rotate-90 transition-transform">
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
                  className="flex-1 bg-black text-white p-4 font-black uppercase text-sm tracking-widest hover:bg-gray-800 transition-all flex items-center justify-center gap-2"
                >
                  START RESEARCH <ChevronRight size={18} />
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status, inverted }: { status: string, inverted?: boolean }) {
  const styles: any = {
    pending: 'bg-gray-200 text-gray-700',
    running: 'bg-blue-600 text-white animate-pulse',
    completed: 'bg-black text-white',
    failed: 'bg-red-600 text-white',
    paused: 'bg-yellow-500 text-white'
  }
  
  if (inverted) {
    return (
      <span className={`text-[8px] uppercase font-black px-1.5 py-0.5 rounded-sm border border-white/30`}>
        {status}
      </span>
    )
  }

  return (
    <span className={`text-[8px] uppercase font-black px-1.5 py-0.5 rounded-sm ${styles[status] || 'bg-gray-100'}`}>
      {status}
    </span>
  )
}
function TaskDetail({ task, onDeleteRequest }: { task: api.Task, onDeleteRequest: (id: string) => void }) {
  const [selectedStepIndex, setSelectedStepIndex] = useState<number | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [activeIteration, setActiveIteration] = useState(1)

  useEffect(() => {
    // Automatically set active iteration based on current task progress
    for (let i = 3; i >= 1; i--) {
      if (task.steps.some(s => s.stage.endsWith(`-${i}`))) {
        setActiveIteration(i)
        break
      }
    }
  }, [task.steps])

  const handleCancel = async () => {
    setIsProcessing(true)
    try {
      await api.cancelTask(task.id)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleResume = async () => {
    setIsProcessing(true)
    try {
      await api.resumeTask(task.id)
    } finally {
      setIsProcessing(false)
    }
  }

  const baseStages = [
    'summarize-title',
    'literature-review',
    'explore',
    'write-theory',
  ]

  const getStepForIteration = (it: number, type: 'review' | 'refine') => {
    const stage = `${type}-theory-${it}`
    return task.steps.find(s => s.stage === stage)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Task Header */}
      <div className="p-8 border-b border-black bg-white sticky top-0 z-10">
        <div className="flex justify-between items-start gap-8">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
               <StatusBadge status={task.status} />
               <span className="text-[10px] text-gray-400 font-bold uppercase tracking-widest">Research Session: {task.id.split('-')[0]}</span>
            </div>
            <h2 className="text-4xl font-black uppercase tracking-tighter leading-tight">{task.title || "Initializing..."}</h2>
            <p className="mt-4 text-xs text-gray-500 font-bold leading-relaxed max-w-2xl">{task.phenomenon}</p>

            <div className="mt-6 flex gap-3">
              {task.status === 'running' ? (
                <button 
                  disabled={isProcessing}
                  onClick={handleCancel}
                  className="bg-red-600 text-white px-4 py-2 text-[10px] font-black uppercase tracking-widest flex items-center gap-2 hover:bg-red-700 transition-colors disabled:opacity-50"
                >
                  {isProcessing ? <Loader2 size={12} className="animate-spin" /> : <Square size={12} fill="white" />}
                  Pause Research
                </button>
              ) : (task.status === 'paused' || task.status === 'failed' || task.status === 'completed') ? (
                <div className="flex gap-3">
                  {(task.status === 'paused' || task.status === 'failed') && (
                    <button 
                      disabled={isProcessing}
                      onClick={handleResume}
                      className="bg-black text-white px-4 py-2 text-[10px] font-black uppercase tracking-widest flex items-center gap-2 hover:bg-gray-800 transition-colors disabled:opacity-50"
                    >
                      {isProcessing ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} fill="white" />}
                      Resume Research
                    </button>
                  )}
                  <button 
                    disabled={isProcessing}
                    onClick={() => onDeleteRequest(task.id)}
                    className="border-2 border-red-600 text-red-600 px-4 py-2 text-[10px] font-black uppercase tracking-widest flex items-center gap-2 hover:bg-red-50 transition-colors disabled:opacity-50"
                  >
                    <Trash2 size={12} /> Delete Project
                  </button>
                </div>
              ) : null}
            </div>
          </div>
          <div className="text-right flex flex-col gap-2 items-end">
            <div className="bg-gray-100 p-3 flex items-center gap-2 text-[10px] font-bold">
              <Folder size={14} /> {task.env_folder}
            </div>
            <div className="bg-gray-100 p-3 flex items-center gap-2 text-[10px] font-bold uppercase">
              <Cpu size={14} /> {task.framework} {task.model && `[${task.model}]`}
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Timeline */}
        <div className="w-1/2 p-8 overflow-y-auto border-r border-gray-100">
          <div className="flex items-center justify-between mb-8">
            <h3 className="font-black text-xs uppercase tracking-widest flex items-center gap-2">
              <Activity size={16} /> Research Workflow
            </h3>
          </div>
          
          <div className="space-y-6">
            {baseStages.map((stage, idx) => {
              const step = task.steps.find(s => s.stage === stage)
              const isCurrent = task.current_stage === stage && (!step || step.status === 'running')
              const isPlaceholder = !step && !isCurrent

              return (
                <div 
                  key={stage}
                  onClick={() => {
                    const stepIdx = task.steps.findIndex(s => s.stage === stage)
                    if (stepIdx !== -1) setSelectedStepIndex(stepIdx)
                  }}
                  className={`relative pl-8 group transition-all ${step ? 'cursor-pointer' : 'cursor-default'}`}
                >
                  {/* Connector line */}
                  <div className="absolute left-[9px] top-5 w-[2px] h-full bg-gray-100 group-hover:bg-black transition-colors" />
                  
                  {/* Step indicator */}
                  <div className={`absolute left-0 top-0 w-5 h-5 rounded-full border-2 bg-white z-10 transition-all ${
                    step?.status === 'completed' ? 'border-black bg-black' : 
                    (step?.status === 'running' || isCurrent) ? 'border-blue-600' : 'border-gray-200'
                  }`}>
                     {step?.status === 'completed' && <CheckCircle size={12} className="text-white m-auto mt-[2px]" />}
                     {(step?.status === 'running' || isCurrent) && <div className="w-1 h-1 bg-blue-600 rounded-full m-auto mt-1.5 animate-ping" />}
                  </div>

                  <div className={`p-4 border-2 transition-all ${
                    selectedStepIndex !== null && task.steps[selectedStepIndex]?.stage === stage 
                      ? 'border-black bg-gray-50 -translate-y-1 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]' 
                      : (isPlaceholder ? 'border-dashed border-gray-100 opacity-40' : 'border-transparent hover:border-gray-100 hover:bg-gray-50/50')
                  }`}>
                    <div className="flex justify-between items-center mb-1">
                      <span className={`font-black text-xs uppercase tracking-tight ${isCurrent ? 'text-blue-600' : ''}`}>{stage}</span>
                      <span className={`text-[8px] font-bold px-1 py-0.5 rounded uppercase ${
                        step?.status === 'completed' ? 'bg-black text-white' : 
                        (step?.status === 'running' || isCurrent) ? 'bg-blue-100 text-blue-700' : 
                        step?.status === 'failed' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-400'
                      }`}>
                        {step?.status || (isCurrent ? 'running' : 'upcoming')}
                      </span>
                    </div>
                    {step?.session_id && (
                      <div className="text-[9px] text-gray-400 font-bold flex items-center gap-1">
                        <Terminal size={10} /> SESSION_{step.session_id.substring(0, 8)}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}

            {/* Refinement Loop Visualization */}
            <div className="relative pl-8 mt-12">
               <div className="absolute left-[9px] -top-12 w-[2px] h-12 bg-gray-100" />
               <div className="absolute left-[-10px] top-6 w-10 h-[200px] border-l-2 border-y-2 border-black rounded-l-2xl opacity-20" />
               
               <div className="bg-white border-2 border-black p-6 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
                  <div className="flex justify-between items-center mb-6">
                    <div className="flex items-center gap-2">
                       <History size={16} className="animate-spin-slow" />
                       <h4 className="font-black text-xs uppercase tracking-[0.2em]">Refinement Loop</h4>
                    </div>
                    <div className="flex gap-1">
                      {[1, 2, 3].map(it => (
                        <button 
                          key={it}
                          onClick={() => setActiveIteration(it)}
                          className={`w-6 h-6 text-[10px] font-black border transition-all ${activeIteration === it ? 'bg-black text-white border-black' : 'hover:bg-gray-100 border-gray-200'}`}
                        >
                          {it}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-4">
                    {['review', 'refine'].map(type => {
                      const step = getStepForIteration(activeIteration, type as any)
                      const isCurrent = task.current_stage === `${type}-theory-${activeIteration}`
                      
                      return (
                        <div 
                          key={type}
                          onClick={() => {
                             if (step) {
                               const idx = task.steps.findIndex(s => s.id === (step as any).id || s.stage === step.stage)
                               setSelectedStepIndex(idx)
                             }
                          }}
                          className={`p-3 border-2 transition-all ${
                            step ? 'cursor-pointer' : 'opacity-30 cursor-default'
                          } ${
                            selectedStepIndex !== null && task.steps[selectedStepIndex]?.stage === `${type}-theory-${activeIteration}`
                              ? 'border-black bg-gray-50' : 'border-gray-100 hover:border-black'
                          }`}
                        >
                          <div className="flex justify-between items-center">
                            <span className={`text-[10px] font-black uppercase ${isCurrent ? 'text-blue-600' : ''}`}>{type} theory</span>
                            <div className="flex items-center gap-2">
                              {isCurrent && <Loader2 size={10} className="animate-spin text-blue-600" />}
                              <span className="text-[8px] font-bold uppercase">{step?.status || (isCurrent ? 'running' : 'upcoming')}</span>
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                  
                  <div className="mt-4 text-center">
                    <div className="inline-block text-[8px] font-black uppercase tracking-widest text-gray-300">
                      Iteration {activeIteration} of 3
                    </div>
                  </div>
               </div>
            </div>
          </div>
        </div>

        {/* Step Inspector */}
        <div className="w-1/2 bg-gray-50/50 flex flex-col h-full border-l border-black">
          {selectedStepIndex !== null ? (
            <div className="flex flex-col h-full">
              <div className="p-6 border-b border-black bg-white flex justify-between items-center">
                <div className="flex items-center gap-3">
                   <div className="bg-black text-white p-1 rounded-sm"><Terminal size={16} /></div>
                   <span className="font-black text-xs uppercase tracking-widest">{task.steps[selectedStepIndex].stage}</span>
                </div>
                <button 
                  onClick={() => setSelectedStepIndex(null)}
                  className="text-[10px] font-black uppercase hover:underline"
                >
                  Dismiss
                </button>
              </div>
              
              <div className="flex-1 overflow-y-auto p-6 custom-scrollbar space-y-8">
                {task.steps[selectedStepIndex].session_id && (
                  <div className="group relative">
                    <div className="absolute -top-3 -left-1 px-2 py-1 bg-black text-white text-[8px] font-black uppercase tracking-widest z-10">
                      System Shell Access
                    </div>
                    <div className="bg-[#0c0c0c] text-[#00ff00] p-4 font-mono text-[11px] border border-black shadow-[4px_4px_0px_0px_rgba(0,255,0,0.1)]">
                      <div className="opacity-50 mb-2"># Use this command to resume this session manually</div>
                      <div className="flex items-center gap-2">
                        <span className="text-gray-500">$</span>
                        <code className="select-all">
                          {task.framework === 'gemini' ? `gemini -s ${task.steps[selectedStepIndex].session_id}` : `claude --resume ${task.steps[selectedStepIndex].session_id}`}
                        </code>
                      </div>
                    </div>
                  </div>
                )}
                
                <DataSection label="Execution Context" data={task.steps[selectedStepIndex].inputs} />
                
                {task.steps[selectedStepIndex].outputs && (
                  <DataSection label="Observation Results" data={task.steps[selectedStepIndex].outputs} primary />
                )}

                {task.steps[selectedStepIndex].error && (
                  <div className="bg-red-50 border border-red-200 p-4">
                    <div className="text-[10px] font-black uppercase text-red-500 mb-2 tracking-widest">Critical Failure</div>
                    <div className="text-xs font-bold text-red-900 leading-relaxed">
                      {task.steps[selectedStepIndex].error}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-12 text-center opacity-30">
              <Terminal size={48} strokeWidth={1} />
              <div className="mt-4 text-[10px] font-black uppercase tracking-widest">Awaiting node selection</div>
            </div>
          )}
        </div>
      </div>
      
      {/* Footer Info */}
      <div className="p-4 border-t border-black bg-white flex justify-between items-center text-[9px] font-bold text-gray-400 uppercase tracking-[0.2em]">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1"><Database size={10} /> {task.db_path}</span>
        </div>
        <div className="flex items-center gap-4">
          <span>AI Scientist Protocol v0.1.0</span>
          <span className="text-black">● Live Connection Established</span>
        </div>
      </div>
    </div>
  )
}

function DataSection({ label, data, primary }: { label: string, data: any, primary?: boolean }) {
  const isPromptOnly = data && typeof data === 'object' && 'prompt' in data && Object.keys(data).length === 1;

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <div className={`w-1.5 h-1.5 rounded-full ${primary ? 'bg-black' : 'bg-gray-300'}`} />
        <h4 className="text-[10px] font-black uppercase tracking-widest text-gray-500">{label}</h4>
      </div>
      <div className={`border p-4 bg-white overflow-x-auto ${primary ? 'border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,0.05)]' : 'border-gray-100'}`}>
        {isPromptOnly ? (
          <div className="text-xs font-bold whitespace-pre-wrap leading-relaxed text-gray-700 bg-gray-50 p-4 border-l-4 border-black">
            {data.prompt}
          </div>
        ) : (
          <pre className="text-[10px] leading-relaxed whitespace-pre-wrap">
            {JSON.stringify(data, null, 2)}
          </pre>
        )}
      </div>
    </div>
  )
}

export default App
