import { useState } from 'react'
import { Activity, Folder, Cpu, Terminal, Loader2, Square, Play, Trash2, Database, Copy, Check } from 'lucide-react'
import * as api from '../api'
import { StatusBadge } from './StatusBadge'
import { DataSection } from './DataSection'
import { WorkflowStep } from './workflow/WorkflowStep'
import { WorkflowLoop } from './workflow/WorkflowLoop'

interface TaskDetailProps {
  task: api.Task;
  onDeleteRequest: (id: string) => void;
  onRefresh: () => void;
}

export function TaskDetail({ task, onDeleteRequest, onRefresh }: TaskDetailProps) {
  const [selectedStepIndex, setSelectedStepIndex] = useState<number | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleCancel = async () => {
    setIsProcessing(true)
    try {
      await api.cancelTask(task.id)
      onRefresh()
    } finally {
      setIsProcessing(false)
    }
  }

  const handleResume = async () => {
    setIsProcessing(true)
    try {
      await api.resumeTask(task.id)
      onRefresh()
    } finally {
      setIsProcessing(false)
    }
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
                  className="bg-gray-500 text-white px-4 py-2 text-[10px] font-black uppercase tracking-widest flex items-center gap-2 hover:bg-gray-600 transition-colors disabled:opacity-50"
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

          <div className="space-y-6 pb-20">
            {task.workflow_structure.map((item, idx) => {
              const showConnector = idx < task.workflow_structure.length - 1;

              if (item.type === 'step') {
                return (
                  <WorkflowStep
                    key={item.stage}
                    stage={item.stage}
                    task={task}
                    isSelected={selectedStepIndex !== null && task.steps[selectedStepIndex]?.stage === item.stage}
                    onSelect={setSelectedStepIndex}
                    onRetry={handleResume}
                    showConnector={showConnector}
                  />
                )
              }

              if (item.type === 'parallel') {
                return (
                  <div key={idx} className="flex flex-col gap-2">
                    {item.stages.map((stage: string, sidx: number) => (
                      <WorkflowStep
                        key={stage}
                        stage={stage}
                        task={task}
                        isSelected={selectedStepIndex !== null && task.steps[selectedStepIndex]?.stage === stage}
                        onSelect={setSelectedStepIndex}
                        onRetry={handleResume}
                        showConnector={showConnector || sidx < item.stages.length - 1}
                      />
                    ))}
                  </div>
                )
              }

              if (item.type === 'loop') {
                return (
                  <WorkflowLoop
                    key={item.name}
                    name={item.name}
                    baseStages={item.base_stages}
                    iterations={item.iterations}
                    task={task}
                    onSelect={setSelectedStepIndex}
                    selectedStage={selectedStepIndex !== null ? task.steps[selectedStepIndex]?.stage : undefined}
                    onRetry={handleResume}
                  />
                )
              }

              return null;
            })}
          </div>
        </div>

        {/* Step Inspector */}
        <div className="w-1/2 bg-gray-50/50 flex flex-col h-full border-l border-black">
          {selectedStepIndex !== null && task.steps[selectedStepIndex] ? (
            <div className="flex flex-col h-full">
              <div className="p-6 border-b border-black bg-white flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <div className="bg-black text-white p-1 rounded-sm"><Terminal size={16} /></div>
                  <span className="font-black text-xs uppercase tracking-widest">{task.steps[selectedStepIndex].stage}</span>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-6 custom-scrollbar space-y-8 pb-20">
                {task.steps[selectedStepIndex].session_id && (
                  <div className="group relative">
                    <div className="absolute -top-3 -left-1 px-2 py-1 bg-black text-white text-[8px] font-black uppercase tracking-widest z-10">
                      Inspect Agent
                    </div>
                    <div className="bg-[#0c0c0c] text-[#00ff00] p-4 font-mono text-[11px] border border-black shadow-[4px_4px_0px_0px_rgba(0,255,0,0.1)]">
                      <div className="flex justify-between items-start mb-2">
                        <div className="opacity-50"># Use this command to resume this session manually</div>
                        <button 
                          onClick={() => {
                            const cmd = task.framework === 'gemini' 
                              ? `gemini --resume ${task.steps[selectedStepIndex].session_id}` 
                              : `claude --resume ${task.steps[selectedStepIndex].session_id}`;
                            handleCopy(cmd);
                          }}
                          className="text-[#00ff00] hover:text-white transition-colors p-1"
                          title="Copy to clipboard"
                        >
                          {copied ? <Check size={14} /> : <Copy size={14} />}
                        </button>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-gray-500">$</span>
                        <code className="select-all">
                          {task.framework === 'gemini' ? `gemini --resume ${task.steps[selectedStepIndex].session_id}` : `claude --resume ${task.steps[selectedStepIndex].session_id}`}
                        </code>
                      </div>
                    </div>
                  </div>
                )}

                <DataSection label="Prompt" data={task.steps[selectedStepIndex].inputs} />

                {task.steps[selectedStepIndex].last_status && task.steps[selectedStepIndex].status === 'running' && (
                  <div className="border-2 border-blue-600 bg-blue-50/30 p-4 relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-1">
                      <div className="w-1 h-1 bg-blue-600 rounded-full animate-ping" />
                    </div>
                    <div className="text-[10px] font-black uppercase text-blue-600 mb-2 tracking-widest flex items-center gap-2">
                      <Activity size={10} /> Current Activity
                    </div>
                    <div className="text-[11px] font-bold text-blue-900 leading-relaxed italic">
                      "{task.steps[selectedStepIndex].last_status}"
                    </div>
                  </div>
                )}

                {task.steps[selectedStepIndex].outputs && (
                  <DataSection label="Result" data={task.steps[selectedStepIndex].outputs} primary />
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
              <div className="mt-4 text-[10px] font-black uppercase tracking-widest">Select step to see details</div>
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
