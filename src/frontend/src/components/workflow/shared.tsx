import React, { useState } from 'react'
import { Loader2, RefreshCw, XCircle, LayoutGrid } from 'lucide-react'
import * as api from '../../api'

export function StepIndicator({ status, isRunning }: { status: string | undefined, isRunning: boolean }) {
  return (
    <div className={`absolute left-0 top-0 w-5 h-5 rounded-full border-2 bg-white z-10 transition-all flex items-center justify-center ${status === 'completed' ? 'border-green-600' :
      (isRunning || status === 'waiting') ? 'border-blue-600' :
        status === 'paused' ? 'border-yellow-500' :
          status === 'canceled' ? 'border-gray-500 bg-gray-500' :
            status === 'failed' ? 'border-red-600' : 'border-gray-200'
      } no-invert`}>
      {status === 'canceled' && <div className="w-2 h-0.5 bg-white" />}
      {isRunning && status !== 'waiting' && <div className="w-1 h-1 bg-blue-600 rounded-full animate-ping" />}
      {status === 'waiting' && <div className="w-1.5 h-1.5 bg-blue-600 rounded-full opacity-50" />}
      {status === 'paused' && <div className="w-1.5 h-1.5 bg-yellow-500 rounded-full" />}
    </div>
  )
}

export function formatStageName(name: string): string {
  return name
    .replace(/-/g, ' ')
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

interface InnerStepCardProps {
  label: string;
  step?: api.Step;
  isRunning: boolean;
  isSelected: boolean;
  taskStatus: string;
  onSelect: () => void;
  onRetry: (e: React.MouseEvent) => void;
}

export const InnerStepCard = React.memo(({ label, step, isRunning, isSelected, taskStatus, onSelect, onRetry }: InnerStepCardProps) => {
  return (
    <div
      onClick={onSelect}
      className={`p-3 border-2 transition-all cursor-pointer ${isSelected
        ? 'border-black bg-gray-50' : 'border-gray-100 hover:border-black'
        }`}
    >
      <div className="flex justify-between items-center">
        <span className={`text-[10px] font-black ${isRunning || step?.status === 'waiting' ? 'text-blue-600' : ''}`}>{label}</span>
        <div className="flex items-center gap-2">
          {step?.status === 'failed' && (
            <button
              onClick={(e) => { e.stopPropagation(); onRetry(e); }}
              disabled={isRunning || taskStatus === 'running'}
              className={`p-1 rounded-sm transition-colors ${(isRunning || taskStatus === 'running') ? 'text-gray-300 cursor-not-allowed' : 'hover:bg-red-200 text-red-600'}`}
              title={(isRunning || taskStatus === 'running') ? 'Waiting for parallel steps to finish...' : 'Retry this step'}
            >
              <RefreshCw size={10} strokeWidth={3} />
            </button>
          )}
          {isRunning && step?.status !== 'waiting' && <Loader2 size={10} className="animate-spin text-blue-600 no-invert" />}
          <span className={`text-[8px] font-bold uppercase ${step?.status === 'completed' ? 'text-green-600' :
            step?.status === 'paused' ? 'text-yellow-600' :
              step?.status === 'failed' ? 'text-red-600' :
                step?.status === 'canceled' ? 'text-gray-500' :
                  (isRunning || step?.status === 'waiting') ? 'text-blue-600' : 'text-gray-400'
            } no-invert`}>{step?.status || (isRunning ? 'running' : 'upcoming')}</span>
        </div>
      </div>
    </div>
  )
}, (prev, next) => {
  return prev.label === next.label &&
    prev.isRunning === next.isRunning &&
    prev.isSelected === next.isSelected &&
    prev.taskStatus === next.taskStatus &&
    prev.step?.status === next.step?.status &&
    prev.step?.session_id === next.step?.session_id;
});

interface CancelStepsButtonProps {
  task: api.Task;
  stagesToCancel: string[];
  onRefresh: () => void;
  label: string;
}

export function CancelStepsButton({ task, stagesToCancel, onRefresh, label }: CancelStepsButtonProps) {
  const [isCanceling, setIsCanceling] = useState(false)
  return (
    <button
      onClick={async (e) => {
        e.stopPropagation();
        setIsCanceling(true);
        try {
          await api.bulkCancelSteps(task.id, stagesToCancel);
          onRefresh();
        } catch (e: any) {
          alert(e.message || `Failed to cancel`);
        } finally {
          setIsCanceling(false);
        }
      }}
      disabled={isCanceling}
      className="text-[10px] font-black text-gray-400 hover:text-red-600 transition-colors flex items-center gap-1 bg-gray-50 px-2 py-1 rounded-sm border border-gray-200 hover:border-red-200"
    >
      {isCanceling ? <Loader2 size={10} className="animate-spin" /> : <XCircle size={10} />} {label}
    </button>
  )
}

interface InnerParallelCardProps {
  name: string;
  stages: string[];
  task: api.Task;
  selectedStage?: string;
  onSelect: (stage: string) => void;
  onRetry: (e: React.MouseEvent) => void;
  onRefresh: () => void;
}

export const InnerParallelCard = React.memo(({ name, stages, task, selectedStage, onSelect, onRetry, onRefresh }: InnerParallelCardProps) => {
  if (!stages || stages.length === 0) {
    return (
      <div className="p-3 border-2 border-dashed border-gray-200 opacity-40">
        <div className="flex items-center gap-2 mb-2"><LayoutGrid size={12} /> <span className="text-[10px] font-black">{name}</span></div>
        <div className="text-[8px] text-gray-400 font-bold">Pending...</div>
      </div>
    )
  }

  return (
    <div className="p-3 border-2 border-gray-200 bg-gray-50/50">
      <div className="flex justify-between items-center mb-3">
        <div className="flex items-center gap-2">
          <LayoutGrid size={12} />
          <span className="text-[10px] font-black">{formatStageName(name)}</span>
        </div>
        {task.status !== 'completed' && (
          <CancelStepsButton task={task} stagesToCancel={stages} onRefresh={onRefresh} label="Cancel Steps" />
        )}
      </div>
      <div className="grid grid-cols-2 gap-2">
        {stages.map(stage => {
          const step = task.steps.find(s => s.stage === stage)
          const isRunning = step?.status === 'running' || (task.current_stage === stage && !step)
          return (
            <InnerStepCard
              key={stage}
              label={formatStageName(stage)}
              step={step}
              isRunning={isRunning}
              isSelected={selectedStage === stage}
              taskStatus={task.status}
              onSelect={() => onSelect(stage)}
              onRetry={onRetry}
            />
          )
        })}
      </div>
    </div>
  )
}, (prev, next) => {
  const prevStepStatuses = prev.stages.map(s => prev.task.steps.find(st => st.stage === s)?.status).join(',');
  const nextStepStatuses = next.stages.map(s => next.task.steps.find(st => st.stage === s)?.status).join(',');

  return prev.name === next.name &&
    prev.selectedStage === next.selectedStage &&
    prev.task.status === next.task.status &&
    prev.task.current_stage === next.task.current_stage &&
    prevStepStatuses === nextStepStatuses &&
    JSON.stringify(prev.stages) === JSON.stringify(next.stages);
});

