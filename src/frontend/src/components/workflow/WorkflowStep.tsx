import React from 'react'
import { Terminal, RefreshCw } from 'lucide-react'
import * as api from '../../api'
import { StepIndicator, formatStageName } from './shared'

interface WorkflowStepProps {
  stage: string;
  task: api.Task;
  onSelect: (stage: string) => void;
  isSelected: boolean;
  onRetry: () => void;
  isPlaceholder?: boolean;
  showConnector?: boolean;
}

export const WorkflowStep = React.memo(({ stage, task, onSelect, isSelected, onRetry, isPlaceholder, showConnector = true }: WorkflowStepProps) => {
  const step = task.steps.find(s => s.stage === stage)
  const isRunning = step?.status === 'running' || step?.status === 'waiting' || (task.current_stage === stage && !step)
  
  return (
    <div 
      onClick={() => onSelect(stage)}
      className={`relative pl-8 group transition-all cursor-pointer`}
    >
      {/* Connector line */}
      {showConnector && (
        <div className="absolute left-[9px] top-5 w-[2px] h-full bg-gray-100 group-hover:bg-black transition-colors" />
      )}
      
      <StepIndicator status={step?.status} isRunning={isRunning} />

      <div className={`p-4 border-2 transition-all ${
        isSelected 
          ? 'border-black bg-gray-50' 
          : (isPlaceholder ? 'border-dashed border-gray-200 opacity-40' : 'border-gray-200 hover:border-black')
      }`}>
        <div className="flex justify-between items-center mb-1">
          <span className={`font-black text-xs tracking-tight ${isRunning ? 'text-blue-600' : ''}`}>{formatStageName(stage)}</span>
          <div className="flex items-center gap-2">
            {step?.status === 'failed' && (
              <button
                onClick={(e) => { e.stopPropagation(); onRetry(); }}
                disabled={task.status === 'running'}
                className={`p-1 rounded-sm transition-colors ${task.status === 'running' ? 'text-gray-300 cursor-not-allowed' : 'hover:bg-red-200 text-red-600'}`}
                title={task.status === 'running' ? 'Waiting for parallel steps to finish...' : 'Retry this step'}
              >
                <RefreshCw size={10} strokeWidth={3} />
              </button>
            )}
            <span className={`text-[8px] font-bold px-1 py-0.5 rounded uppercase ${
              step?.status === 'completed' ? 'bg-green-600 text-white' : 
              isRunning ? 'bg-blue-100 text-blue-700' : 
              step?.status === 'failed' ? 'bg-red-100 text-red-700' : 
              step?.status === 'paused' ? 'bg-yellow-500 text-white' : 
              step?.status === 'canceled' ? 'bg-gray-500 text-white' : 'bg-gray-100 text-gray-400'
            } no-invert`}>
              {step?.status || (isRunning ? 'running' : 'upcoming')}
            </span>
          </div>
        </div>
        {step?.session_id && (
          <div className="text-[9px] text-gray-400 font-bold flex items-center gap-1">
            <Terminal size={10} /> SESSION_{step.session_id.substring(0, 8)}
          </div>
        )}
      </div>
    </div>
  )
}, (prev, next) => {
  const prevStep = prev.task.steps.find(s => s.stage === prev.stage);
  const nextStep = next.task.steps.find(s => s.stage === next.stage);
  
  return prev.stage === next.stage &&
         prev.isSelected === next.isSelected &&
         prev.isPlaceholder === next.isPlaceholder &&
         prev.showConnector === next.showConnector &&
         prev.task.current_stage === next.task.current_stage &&
         prev.task.status === next.task.status &&
         prevStep?.status === nextStep?.status &&
         prevStep?.session_id === nextStep?.session_id;
});
