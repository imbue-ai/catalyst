import { useState } from 'react'
import { CheckCircle, Loader2, RefreshCw, XCircle, LayoutGrid } from 'lucide-react'
import * as api from '../../api'

interface WorkflowParallelProps {
  name: string;
  stages: string[];
  task: api.Task;
  onSelect: (stage: string) => void;
  selectedStage?: string;
  onRetry: () => void;
  onRefresh: () => void;
  showConnector?: boolean;
}

export function WorkflowParallel({ name, stages, task, onSelect, selectedStage, onRetry, onRefresh, showConnector = true }: WorkflowParallelProps) {
  const [isCanceling, setIsCanceling] = useState(false)

  // Determine overall status
  const innerSteps = stages.map(stage => task.steps.find(s => s.stage === stage))
  
  const hasRunning = stages.some(stage => task.current_stage === stage && (!task.steps.find(s => s.stage === stage) || task.steps.find(s => s.stage === stage)?.status === 'running')) || innerSteps.some(s => s?.status === 'running')
  const hasFailed = innerSteps.some(s => s?.status === 'failed')
  const hasPaused = innerSteps.some(s => s?.status === 'paused')
  const allCompleted = innerSteps.length > 0 && innerSteps.every(s => s?.status === 'completed')
  const allCanceled = innerSteps.length > 0 && innerSteps.every(s => s?.status === 'canceled')
  
  const overallStatus = allCompleted ? 'completed' : 
                        hasFailed ? 'failed' :
                        hasPaused ? 'paused' :
                        hasRunning ? 'running' :
                        allCanceled ? 'canceled' : 'upcoming'

  return (
    <div className={`relative pl-8 group transition-all mb-6`}>
      {/* Connector line */}
      {showConnector && (
        <div className="absolute left-[9px] top-5 w-[2px] h-full bg-gray-100 group-hover:bg-black transition-colors" />
      )}
      
      {/* Step indicator */}
      <div className={`absolute left-0 top-0 w-5 h-5 rounded-full border-2 bg-white z-10 transition-all ${
        overallStatus === 'completed' ? 'border-green-600 bg-green-600' : 
        overallStatus === 'running' ? 'border-blue-600' : 
        overallStatus === 'paused' ? 'border-yellow-500' : 
        overallStatus === 'canceled' ? 'border-gray-500 bg-gray-500' : 
        overallStatus === 'failed' ? 'border-red-600' : 'border-gray-200'
      }`}>
         {overallStatus === 'completed' && <CheckCircle size={12} className="text-white m-auto mt-[2px]" />}
         {overallStatus === 'canceled' && <div className="w-2 h-0.5 bg-white m-auto mt-2" />}
         {overallStatus === 'running' && <div className="w-1 h-1 bg-blue-600 rounded-full m-auto mt-1.5 animate-ping" />}
         {overallStatus === 'paused' && <div className="w-1.5 h-1.5 bg-yellow-500 rounded-full m-auto mt-1.5" />}
      </div>

      <div className="bg-white border-2 border-black p-6 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-2">
            <LayoutGrid size={16} />
            <h4 className="font-black text-xs uppercase tracking-[0.2em]">{name || "Parallel Tasks"}</h4>
          </div>
          {task.status !== 'completed' && overallStatus !== 'completed' && overallStatus !== 'canceled' && (
            <button 
              onClick={async (e) => {
                e.stopPropagation();
                setIsCanceling(true);
                try {
                  await api.bulkCancelSteps(task.id, stages);
                  onRefresh();
                } catch (e: any) {
                  alert(e.message || "Failed to cancel tasks");
                } finally {
                  setIsCanceling(false);
                }
              }}
              disabled={isCanceling}
              className="text-[10px] font-black uppercase text-gray-400 hover:text-red-600 transition-colors flex items-center gap-1 bg-gray-50 px-2 py-1 rounded-sm border border-gray-200 hover:border-red-200"
            >
              {isCanceling ? <Loader2 size={10} className="animate-spin" /> : <XCircle size={10} />} Cancel Tasks
            </button>
          )}
        </div>

        <div className="space-y-4">
          {stages.map(stage => {
            const step = task.steps.find(s => s.stage === stage)
            const isRunning = step?.status === 'running' || (task.current_stage === stage && !step)
            
            return (
              <div 
                key={stage}
                onClick={() => onSelect(stage)}
                className={`p-3 border-2 transition-all cursor-pointer ${
                  selectedStage === stage
                    ? 'border-black bg-gray-50' : 'border-gray-100 hover:border-black'
                }`}
              >
                <div className="flex justify-between items-center">
                  <span className={`text-[10px] font-black uppercase ${isRunning ? 'text-blue-600' : ''}`}>{stage.replace(/-/g, ' ')}</span>
                  <div className="flex items-center gap-2">
                    {step?.status === 'failed' && task.status !== 'running' && (
                      <button 
                        onClick={(e) => { e.stopPropagation(); onRetry(); }}
                        className="p-1 hover:bg-red-200 rounded-sm text-red-600 transition-colors"
                        title="Retry this step"
                      >
                        <RefreshCw size={10} strokeWidth={3} />
                      </button>
                    )}
                    {isRunning && <Loader2 size={10} className="animate-spin text-blue-600" />}
                    <span className={`text-[8px] font-bold uppercase ${
                      step?.status === 'completed' ? 'text-green-600' :
                      step?.status === 'paused' ? 'text-yellow-600' :
                      step?.status === 'failed' ? 'text-red-600' :
                      step?.status === 'canceled' ? 'text-gray-500' :
                      isRunning ? 'text-blue-600' : 'text-gray-400'
                    }`}>{step?.status || (isRunning ? 'running' : 'upcoming')}</span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
