import { useState, useEffect, useMemo } from 'react'
import { RotateCw } from 'lucide-react'
import * as api from '../../api'
import { InnerStepCard, InnerParallelCard, CancelStepsButton, StepIndicator, formatStageName } from './shared'

interface WorkflowLoopProps {
  name: string;
  baseStages?: string[];
  iterationStructures?: { [key: string]: any[] };
  iterations: number;
  task: api.Task;
  onSelect: (stage: string) => void;
  selectedStage?: string;
  onRetry: () => void;
  onRefresh: () => void;
  showConnector?: boolean;
}

export function WorkflowLoop({ name, baseStages, iterationStructures, iterations, task, onSelect, selectedStage, onRetry, onRefresh, showConnector = true }: WorkflowLoopProps) {
  const [activeIteration, setActiveIteration] = useState(1)
  const [lastLatest, setLastLatest] = useState(0)

  useEffect(() => {
    // Calculate what the current latest iteration is based on steps
    let currentLatest = 1
    for (let i = iterations; i >= 1; i--) {
      // Collect exact stage names for this iteration to avoid brittle suffix matching
      const iterationStages = new Set<string>();
      if (iterationStructures && iterationStructures[i.toString()]) {
        iterationStructures[i.toString()].forEach((item: any) => {
          if (item.type === 'step' && item.stage) {
            iterationStages.add(item.stage);
          } else if (item.type === 'parallel' && item.stages) {
            item.stages.forEach((s: string) => iterationStages.add(s));
          }
        });
      } else if (baseStages) {
        baseStages.forEach(bs => iterationStages.add(`${bs}-${i}`));
      }

      // Check if any of these exact stages are in a state other than 'pending'
      const hasStarted = task.steps.some(s => iterationStages.has(s.stage) && s.status !== 'pending');
      if (hasStarted) {
        currentLatest = i;
        break;
      }
    }

    if (lastLatest === 0) {
      // First load: sync both to latest
      setActiveIteration(currentLatest)
      setLastLatest(currentLatest)
    } else if (currentLatest > lastLatest) {
      // A new iteration has started! 
      // If the user was watching the "old" latest, move them to the "new" latest.
      if (activeIteration === lastLatest) {
        setActiveIteration(currentLatest)
      }
      setLastLatest(currentLatest)
    }
  }, [task.steps, iterations, activeIteration, lastLatest, iterationStructures, baseStages])

  const getStepForIteration = (it: number, baseStage: string) => {
    const stage = `${baseStage}-${it}`
    return task.steps.find(s => s.stage === stage)
  }

  // Pre-calculate stages to cancel and overall status
  const { stagesToCancel, overallStatus } = useMemo(() => {
    const stages: string[] = [];
    for (let i = 1; i <= iterations; i++) {
        if (iterationStructures && iterationStructures[i.toString()]) {
            iterationStructures[i.toString()].forEach((item: any) => {
                if (item.type === 'step') {
                    stages.push(item.stage)
                } else if (item.type === 'parallel') {
                    stages.push(...item.stages)
                }
            })
        } else if (baseStages) {
            baseStages.forEach(bs => stages.push(`${bs}-${i}`));
        }
    }

    const innerSteps = stages.map(stage => task.steps.find(s => s.stage === stage)).filter(Boolean)
    
    const hasRunning = stages.some(stage => task.current_stage === stage && (!task.steps.find(s => s.stage === stage) || task.steps.find(s => s.stage === stage)?.status === 'running')) || innerSteps.some(s => s?.status === 'running')
    const hasFailed = innerSteps.some(s => s?.status === 'failed')
    const hasPaused = innerSteps.some(s => s?.status === 'paused')
    const allCompleted = stages.length > 0 && stages.every(stage => task.steps.find(s => s.stage === stage)?.status === 'completed')
    const allCanceled = stages.length > 0 && stages.every(stage => task.steps.find(s => s.stage === stage)?.status === 'canceled')

    const status = allCompleted ? 'completed' : 
                   hasFailed ? 'failed' :
                   hasPaused ? 'paused' :
                   hasRunning ? 'running' :
                   allCanceled ? 'canceled' : 'upcoming'

    return { stagesToCancel: stages, overallStatus: status }
  }, [task, iterations, iterationStructures, baseStages])

  const activeStructure = iterationStructures ? iterationStructures[activeIteration.toString()] : null;

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
            <RotateCw size={16} />
            <h4 className="font-black text-xs tracking-[0.2em]">{formatStageName(name)}</h4>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex gap-1">
              {Array.from({ length: iterations }, (_, i) => i + 1).map(it => (
                <button 
                  key={it}
                  onClick={() => setActiveIteration(it)}
                  className={`w-6 h-6 text-[10px] font-black border transition-all ${activeIteration === it ? 'bg-black text-white border-black' : 'hover:bg-gray-100 border-gray-200'}`}
                >
                  {it}
                </button>
              ))}
            </div>
            {task.status !== 'completed' && stagesToCancel.length > 0 && overallStatus !== 'completed' && overallStatus !== 'canceled' && (
              <CancelStepsButton 
                task={task} 
                stagesToCancel={stagesToCancel} 
                onRefresh={onRefresh} 
                label="Cancel Tasks" 
              />
            )}
          </div>
        </div>

        <div className="space-y-4">
          {activeStructure ? (
             activeStructure.map((item: any, idx: number) => {
                 if (item.type === 'step') {
                     const step = task.steps.find(s => s.stage === item.stage)
                     const isRunning = step?.status === 'running' || (task.current_stage === item.stage && !step)
                     return (
                        <InnerStepCard
                          key={`loop-step-${item.stage}-${idx}-${activeIteration}`}
                          label={formatStageName(item.stage)}
                          step={step}
                          isRunning={isRunning}
                          isSelected={selectedStage === item.stage}
                          taskStatus={task.status}
                          onSelect={() => onSelect(item.stage)}
                          onRetry={(e) => { e.stopPropagation(); onRetry(); }}
                        />
                     )
                 } else if (item.type === 'parallel') {
                     return (
                        <InnerParallelCard
                           key={`loop-parallel-${item.name}-${idx}-${activeIteration}`}
                           name={item.name}
                           stages={item.stages}
                           task={task}
                           selectedStage={selectedStage}
                           onSelect={onSelect}
                           onRetry={onRetry}
                           onRefresh={onRefresh}
                        />
                     )
                 }
                 return null;
             })
          ) : baseStages ? (
              baseStages.map((baseStage, idx) => {
                const stageName = `${baseStage}-${activeIteration}`
                const step = getStepForIteration(activeIteration, baseStage)
                const isRunning = step?.status === 'running' || (task.current_stage === stageName && !step)
                
                return (
                  <InnerStepCard
                    key={`loop-base-${baseStage}-${idx}-${activeIteration}`}
                    label={formatStageName(baseStage)}
                    step={step}
                    isRunning={isRunning}
                    isSelected={selectedStage === stageName}
                    taskStatus={task.status}
                    onSelect={() => onSelect(stageName)}
                    onRetry={(e) => { e.stopPropagation(); onRetry(); }}
                  />
                )
              })
          ) : null}
        </div>
        
        <div className="mt-4 text-center">
          <div className="inline-block text-[8px] font-black tracking-widest text-gray-300">
            Iteration {activeIteration} of {iterations}
          </div>
        </div>
      </div>
    </div>
  )
}
