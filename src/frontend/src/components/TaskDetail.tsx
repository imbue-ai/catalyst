/**
 * NOTE ON LAYOUT-PRESERVING SKELETONS:
 * If you modify the structural layout, padding, grid sizes, or headers of this component,
 * PLEASE make sure to also update TaskDetailSkeleton.tsx in this directory to match!
 * This avoids visual layout shift or flickering during transitions.
 */
import { useState, useMemo, useRef, useEffect, useCallback, lazy, Suspense } from 'react'
import { Activity, Folder, Cpu, Loader2, Square, Play, Trash2, Workflow, Plus, XCircle, Copy, Check, Compass, BrushCleaning } from 'lucide-react'
import * as api from '../api'
import { StatusBadge } from './StatusBadge'
import { DataSection } from './DataSection'
import { WorkflowStep } from './workflow/WorkflowStep'
import { WorkflowLoop } from './workflow/WorkflowLoop'
import { WorkflowParallel } from './workflow/WorkflowParallel'
import { formatStageName } from './workflow/shared'

const ArtifactViewerModal = lazy(() => import('./ArtifactViewerModal').then(m => ({ default: m.ArtifactViewerModal })))
import { CreateAddonModal } from './CreateAddonModal'
import { TheoriesList } from './TheoriesList'
import { ExperimentsList } from './ExperimentsList'
import { EditGuidanceModal } from './EditGuidanceModal'

interface TaskDetailProps {
  task: api.Task;
  viewingArtifactId: string | null;
  onDeleteRequest: (id: string) => void;
  onRefresh: () => void;
  isBackendDown?: boolean;
}

export function TaskDetail({ task, viewingArtifactId, onDeleteRequest, onRefresh, isBackendDown }: TaskDetailProps) {
  const [selectedStage, setSelectedStage] = useState<string | null>(null)
  const [activeRightTab, setActiveRightTab] = useState<'stepDetails' | 'topTheories' | 'experiments'>('stepDetails')
  const [isProcessing, setIsProcessing] = useState(false)
  const [copied, setCopied] = useState(false)
  const [showAddonModal, setShowAddonModal] = useState(false)
  const [showGuidanceModal, setShowGuidanceModal] = useState(false)
  const copyTimeoutRef = useRef<number | null>(null)

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    if (copyTimeoutRef.current) {
      window.clearTimeout(copyTimeoutRef.current)
    }
    copyTimeoutRef.current = window.setTimeout(() => setCopied(false), 2000)
  }

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) {
        window.clearTimeout(copyTimeoutRef.current)
      }
    }
  }, [])

  const handleRefresh = useCallback(() => {
    onRefresh()
  }, [onRefresh])

  const handleResume = useCallback(async () => {
    setIsProcessing(true)
    try {
      await api.resumeTask(task.id)
      onRefresh()
    } catch (e: any) {
      alert(e.message || "Failed to resume task")
    } finally {
      setIsProcessing(false)
    }
  }, [task.id, onRefresh])

  const handleSelectStage = useCallback((stage: string) => {
    setSelectedStage(stage)
    setActiveRightTab('stepDetails')
  }, [])

  const handleCancel = async () => {
    setIsProcessing(true)
    try {
      await api.cancelTask(task.id)
      onRefresh()
    } finally {
      setIsProcessing(false)
    }
  }

  const handleDeleteTempFiles = async () => {
    setIsProcessing(true)
    try {
      await api.deleteTempFiles(task.id)
      onRefresh()
    } catch (e: any) {
      alert(e.message || "Failed to delete temporary files")
    } finally {
      setIsProcessing(false)
    }
  }

  const availableLiteratureIds = useMemo(() => Array.from(new Set(
    task.steps
      .filter(s => s.outputs && s.outputs.literature_review_id)
      .map(s => s.outputs.literature_review_id)
  )).reverse(), [task.steps])

  return (
    <div className="flex flex-col h-full">
      {/* Task Header */}
      <div className="p-8 border-b border-black bg-white sticky top-0 z-10">
        <div className="flex justify-between items-start gap-8">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <StatusBadge status={task.status} />
              <span className="text-[10px] text-gray-400 font-bold tracking-widest">Research Session: {task.id.split('-')[0]}</span>
            </div>
            <h2 className="text-4xl font-black tracking-tighter leading-tight">{task.title || "Initializing..."}</h2>
            <p className="mt-4 text-xs text-gray-500 font-bold leading-relaxed whitespace-pre-wrap line-clamp-6 overflow-hidden">{task.workflow_inputs.summary}</p>

            <div className="mt-6 flex gap-3 items-center">
              {task.status === 'running' ? (
                <button
                  disabled={isProcessing}
                  onClick={handleCancel}
                  className="bg-gray-500 text-white px-4 py-2 text-[10px] font-black tracking-widest flex items-center gap-2 hover:bg-gray-600 transition-colors disabled:opacity-50"
                >
                  {isProcessing ? <Loader2 size={12} className="animate-spin" /> : <Square size={12} fill="white" />}
                  Pause Research
                </button>
              ) : (task.status === 'paused' || task.status === 'failed') ? (
                <button
                  disabled={isProcessing}
                  onClick={handleResume}
                  className="bg-black text-white px-4 py-2 text-[10px] font-black tracking-widest flex items-center gap-2 hover:bg-gray-800 transition-colors disabled:opacity-50"
                >
                  {isProcessing ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} fill="white" />}
                  Resume Research
                </button>
              ) : null}

              <button
                disabled={isProcessing}
                onClick={() => setShowGuidanceModal(true)}
                className="border-2 border-black text-black px-4 py-2 text-[10px] font-black tracking-widest flex items-center gap-2 hover:bg-gray-50 transition-colors disabled:opacity-50"
              >
                <Compass size={12} /> Provide Guidance
              </button>

              {(task.status === 'paused' || task.status === 'failed' || task.status === 'completed') && (
                <button
                  disabled={isProcessing}
                  onClick={handleDeleteTempFiles}
                  className="border-2 border-black text-black px-4 py-2 text-[10px] font-black tracking-widest flex items-center gap-2 hover:bg-gray-50 transition-colors disabled:opacity-50"
                >
                  <BrushCleaning size={12} /> Clean Temp Files
                </button>
              )}

              {(task.status === 'paused' || task.status === 'failed' || task.status === 'completed') && (
                <button
                  disabled={isProcessing}
                  onClick={() => onDeleteRequest(task.id)}
                  className="border-2 border-red-600 text-red-600 px-4 py-2 text-[10px] font-black tracking-widest flex items-center gap-2 hover:bg-red-50 transition-colors disabled:opacity-50"
                >
                  <Trash2 size={12} /> Delete Research
                </button>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="bg-gray-100 p-3 flex items-center gap-2 text-[10px] font-bold">
              <Folder size={14} /> {task.env_folder}
            </div>
            <div className="bg-gray-100 p-3 flex items-center gap-2 text-[10px] font-bold">
              <Cpu size={14} /> {task.framework} {task.model && `[${task.model}]`}
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Timeline */}
        <div className="w-1/2 p-8 overflow-y-auto border-r border-gray-100">
          <div className="flex items-center justify-between mb-8">
            <h3 className="font-black text-xs tracking-widest flex items-center gap-2">
              Workflow
            </h3>
          </div>

          <div className="space-y-6 pb-20">
            {task.workflow_structure.map((item, idx) => {
              const showConnector = idx < task.workflow_structure.length - 1;

              if (item.type === 'step') {
                return (
                  <WorkflowStep
                    key={`step-${item.stage}-${idx}`}
                    stage={item.stage}
                    task={task}
                    isSelected={selectedStage === item.stage}
                    onSelect={handleSelectStage}
                    onRetry={handleResume}
                    showConnector={showConnector}
                  />
                )
              }

              if (item.type === 'parallel') {
                return (
                  <WorkflowParallel
                    key={`parallel-${item.name}-${idx}`}
                    name={item.name}
                    stages={item.stages}
                    task={task}
                    onSelect={handleSelectStage}
                    selectedStage={selectedStage || undefined}
                    onRetry={handleResume}
                    onRefresh={handleRefresh}
                    showConnector={showConnector}
                  />
                )
              }

              if (item.type === 'loop') {
                return (
                  <WorkflowLoop
                    key={`loop-${item.name}-${idx}`}
                    name={item.name}
                    baseStages={item.base_stages}
                    iterationStructures={item.iteration_structures}
                    iterations={item.iterations}
                    task={task}
                    onSelect={handleSelectStage}
                    selectedStage={selectedStage || undefined}
                    onRetry={handleResume}
                    onRefresh={handleRefresh}
                    showConnector={showConnector}
                  />
                )
              }

              return null;
            })}

            <div className="flex justify-center mt-8">
              <button
                disabled={isProcessing}
                onClick={() => setShowAddonModal(true)}
                className={`flex flex-col items-center gap-2 transition-colors ${isProcessing ? 'opacity-30 cursor-not-allowed text-gray-400' : 'text-gray-400 hover:text-black'}`}
              >
                <div className={`p-1 rounded-full ${isProcessing ? 'bg-gray-400' : 'bg-black text-white'}`}>
                  <Plus size={16} />
                </div>
                <span className="text-[10px] font-black tracking-widest">Add step</span>
              </button>
            </div>
          </div>
        </div>

        {/* Right Panel Tabs & Content */}
        <div className="w-1/2 flex flex-col h-full border-l border-black bg-gray-50/50">
          <div className="flex border-b-2 border-black bg-white">
            <button
              onClick={() => setActiveRightTab('stepDetails')}
              className={`px-6 py-3 text-[10px] font-black tracking-widest transition-colors border-r border-black ${activeRightTab === 'stepDetails'
                ? 'bg-black text-white'
                : 'text-black hover:bg-gray-100'
                }`}
            >
              Step Details
            </button>
            <button
              onClick={() => setActiveRightTab('topTheories')}
              className={`px-6 py-3 text-[10px] font-black tracking-widest transition-colors border-r border-black ${activeRightTab === 'topTheories'
                ? 'bg-black text-white'
                : 'text-black hover:bg-gray-100'
                }`}
            >
              Theories
            </button>
            <button
              onClick={() => setActiveRightTab('experiments')}
              className={`px-6 py-3 text-[10px] font-black tracking-widest transition-colors border-r border-black ${activeRightTab === 'experiments'
                ? 'bg-black text-white'
                : 'text-black hover:bg-gray-100'
                }`}
            >
              Experiments
            </button>
          </div>

          <div className="flex-1 overflow-hidden flex flex-col">
            {activeRightTab === 'topTheories' ? (
              <TheoriesList taskId={task.id} />
            ) : activeRightTab === 'experiments' ? (
              <ExperimentsList taskId={task.id} />
            ) : selectedStage !== null ? (
              <div className="flex flex-col h-full">
                <div className="p-6 border-b border-black bg-white flex justify-between items-center">
                  <div className="flex items-center gap-3">
                    <div className="bg-black text-white p-1 rounded-sm"><Workflow size={16} /></div>
                    <span className="font-black text-xs tracking-widest">{formatStageName(selectedStage)}</span>
                  </div>
                  {['failed', 'paused', 'pending', 'waiting'].includes(task.steps.find(s => s.stage === selectedStage)?.status || 'pending') && (
                    <button
                      disabled={isProcessing}
                      onClick={async () => {
                        setIsProcessing(true)
                        try {
                          await api.cancelStep(task.id, selectedStage)
                          onRefresh()
                        } catch (e: any) {
                          alert(e.message || "Failed to cancel step")
                        } finally {
                          setIsProcessing(false)
                        }
                      }}
                      className="text-[10px] font-black tracking-widest bg-gray-100 hover:bg-gray-200 text-gray-600 px-3 py-1.5 transition-colors flex items-center gap-1"
                    >
                      <XCircle size={12} /> Cancel Step
                    </button>
                  )}
                </div>

                <div className="flex-1 overflow-y-auto p-6 custom-scrollbar space-y-8 pb-20">
                  {(() => {
                    const step = task.steps.find(s => s.stage === selectedStage);
                    if (!step) {
                      return (
                        <div className="text-center mt-10 text-gray-400 text-[10px] font-black tracking-widest">
                          Step has not started yet
                        </div>
                      )
                    }
                    return (
                      <>
                        {step.session_id && (() => {
                          const isMngr = task.framework === 'mngr-claude' || task.framework === 'mngr-antigravity';
                          let cmd: string;
                          if (isMngr) {
                            cmd = `MNGR_HOST_DIR=~/.mngr-catalyst uv run mngr connect ${step.session_id}`;
                          } else if (task.framework === 'gemini') {
                            cmd = `cd "${task.env_folder}" && gemini --resume ${step.session_id}`;
                          } else if (task.framework === 'codex') {
                            cmd = `cd "${task.env_folder}" && codex resume ${step.session_id}`;
                          } else if (task.framework === 'claude') {
                            cmd = `cd "${task.env_folder}" && claude --resume ${step.session_id}`;
                          } else {
                            cmd = `cd "${task.env_folder}" && agy --resume ${step.session_id}`;
                          }
                          const comment = isMngr
                            ? "# Attach to this agent's tmux session (restarts it if stopped)"
                            : '# Use this command to resume this session manually';
                          return (
                            <div className="group relative">
                              <div className="absolute -top-3 -left-1 px-2 py-1 bg-black text-white text-[8px] font-black tracking-widest z-10">
                                Inspect Agent
                              </div>
                              <div className="bg-[#1a1a1a] text-gray-300 p-4 font-mono text-[11px] border border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,0.1)]">
                                <div className="flex justify-between items-start mb-2">
                                  <div className="text-gray-400">{comment}</div>
                                  <button
                                    onClick={() => handleCopy(cmd)}
                                    className="text-gray-300 hover:text-white transition-colors p-1"
                                    title="Copy to clipboard"
                                  >
                                    {copied ? <Check size={14} /> : <Copy size={14} />}
                                  </button>
                                </div>
                                <div className="flex items-center gap-2">
                                  <span className="text-gray-400">$</span>
                                  <code className="select-all">{cmd}</code>
                                </div>
                              </div>
                            </div>
                          );
                        })()}

                        <DataSection label="Prompt" data={step.inputs} taskId={task.id} />

                        {step.last_status && step.status === 'running' && (
                          <div className="border-2 border-blue-600 bg-blue-50/30 p-4 relative overflow-hidden">
                            <div className="absolute top-0 right-0 p-1">
                              <div className="w-1 h-1 bg-blue-600 rounded-full animate-ping" />
                            </div>
                            <div className="text-[10px] font-black text-blue-600 mb-2 tracking-widest flex items-center gap-2">
                              <Activity size={10} /> Current Activity
                            </div>
                            <div className="text-[11px] font-bold text-blue-900 leading-relaxed italic">
                              "{step.last_status}"
                            </div>
                          </div>
                        )}

                        {step.outputs && (
                          <DataSection label="Result" data={step.outputs} primary taskId={task.id} />
                        )}

                        {step.error && step.status !== 'paused' && step.status !== 'canceled' && (
                          <div className="bg-red-50 border border-red-200 p-4">
                            <div className="text-[10px] font-black text-red-500 mb-2 tracking-widest">Critical Failure</div>
                            <div className="text-xs font-bold text-red-900 leading-relaxed">
                              {step.error}
                            </div>
                          </div>
                        )}
                      </>
                    )
                  })()}
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-12 text-center opacity-30">
                <Workflow size={48} strokeWidth={1} />
                <div className="mt-4 text-[10px] font-black tracking-widest">Select step to see details</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {viewingArtifactId && (
        <Suspense fallback={null}>
          <ArtifactViewerModal
            taskId={task.id}
            artifactId={viewingArtifactId}
            onClose={() => { window.location.hash = `#/task/${task.id}` }}
          />
        </Suspense>
      )}

      {showAddonModal && (
        <CreateAddonModal
          task={task}
          availableLiteratureIds={availableLiteratureIds}
          onClose={() => setShowAddonModal(false)}
          onCreated={() => {
            setShowAddonModal(false)
            onRefresh()
          }}
          isBackendDown={!!isBackendDown}
        />
      )}

      {showGuidanceModal && (
        <EditGuidanceModal
          onClose={() => setShowGuidanceModal(false)}
          initialGuidance={task.guidance || "No additional guidance."}
          initialWeights={task.theory_scoring_weights}
          onSave={async (newGuidance, newWeights) => {
            await api.updateGuidance(task.id, newGuidance, newWeights)
            onRefresh()
          }}
        />
      )}
    </div>
  )
}
