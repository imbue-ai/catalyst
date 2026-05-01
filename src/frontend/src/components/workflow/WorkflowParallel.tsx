import { LayoutGrid } from 'lucide-react'
import * as api from '../../api'
import { StepIndicator, InnerStepCard, CancelStepsButton, formatStageName } from './shared'

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
      
      <StepIndicator status={overallStatus} isRunning={overallStatus === 'running'} />

      <div className="bg-white border-2 border-gray-200 p-6">
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-2">
            <LayoutGrid size={16} />
            <h4 className="font-black text-xs tracking-[0.2em]">{formatStageName(name || "Parallel Tasks")}</h4>
          </div>
          {task.status !== 'completed' && overallStatus !== 'completed' && overallStatus !== 'canceled' && (
            <CancelStepsButton 
              task={task} 
              stagesToCancel={stages} 
              onRefresh={onRefresh} 
              label="Cancel Tasks" 
            />
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
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
                onRetry={(e) => { e.stopPropagation(); onRetry(); }}
              />
            )
          })}
        </div>
      </div>
    </div>
  )
}
