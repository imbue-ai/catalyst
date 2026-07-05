import { useState, useEffect, useMemo, useRef } from 'react'
import { RotateCw, ChevronDown } from 'lucide-react'
import * as api from '../../api'
import { InnerStepCard, InnerParallelCard, CancelStepsButton, StepIndicator, formatStageName } from './shared'
import { getStepsMap } from '../../utils'

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
  const stepsMap = useMemo(() => getStepsMap(task.steps), [task.steps]);
  const [activeIteration, setActiveIteration] = useState(1)
  const [lastLatest, setLastLatest] = useState(0)
  const [showDropdown, setShowDropdown] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  useEffect(() => {
    if (showDropdown && scrollContainerRef.current) {
      const selectedElement = scrollContainerRef.current.querySelector('[data-selected="true"]')
      if (selectedElement) {
        requestAnimationFrame(() => {
          selectedElement.scrollIntoView({ block: 'nearest' })
        })
      }
    }
  }, [showDropdown])

  // Calculate what the current latest iteration is based on steps
  const currentLatest = useMemo(() => {
    let latest = 1
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
        latest = i;
        break;
      }
    }
    return latest;
  }, [task.steps, iterations, iterationStructures, baseStages])

  useEffect(() => {
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
  }, [currentLatest, activeIteration, lastLatest])

  const getStepForIteration = (it: number, baseStage: string) => {
    const stage = `${baseStage}-${it}`
    return stepsMap[stage]
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

    const innerSteps = stages.map(stage => stepsMap[stage]).filter(Boolean)

    const hasRunning = stages.some(stage => task.current_stage === stage && (!stepsMap[stage] || ['running', 'waiting'].includes(stepsMap[stage]?.status || ''))) || innerSteps.some(s => s?.status === 'running' || s?.status === 'waiting')
    const hasFailed = innerSteps.some(s => s?.status === 'failed')
    const hasPaused = innerSteps.some(s => s?.status === 'paused')
    const allCompleted = stages.length > 0 && stages.every(stage => stepsMap[stage]?.status === 'completed')
    const allCanceled = stages.length > 0 && stages.every(stage => stepsMap[stage]?.status === 'canceled')

    const status = allCompleted ? 'completed' :
      hasFailed ? 'failed' :
        hasPaused ? 'paused' :
          hasRunning ? 'running' :
            allCanceled ? 'canceled' : 'upcoming'

    return { stagesToCancel: stages, overallStatus: status }
  }, [task, stepsMap, iterations, iterationStructures, baseStages])

  const activeStructure = iterationStructures ? iterationStructures[activeIteration.toString()] : null;

  return (
    <div className={`relative pl-8 group transition-all mb-6`}>

      {/* Connector line */}
      {showConnector && (
        <div className={`absolute left-[9px] top-5 w-[2px] h-full transition-colors ${overallStatus === 'completed' ? 'bg-black' : 'bg-gray-100'}`} />
      )}

      <StepIndicator status={overallStatus} isRunning={overallStatus === 'running'} />

      <div className="bg-white border-2 border-gray-200 p-6">
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-2">
            <RotateCw size={16} />
            <h4 className="font-black text-xs tracking-[0.2em]">{formatStageName(name)}</h4>
          </div>
          <div className="flex items-center gap-4">
            {iterations > 5 ? (
              <div className="relative inline-block" ref={dropdownRef}>
                <button
                  type="button"
                  onClick={() => setShowDropdown(!showDropdown)}
                  className="border-2 border-black px-3 py-1.5 outline-none text-[10px] font-black bg-white cursor-pointer flex items-center gap-2 select-none min-w-[120px] justify-between"
                >
                  <span>Iteration {activeIteration}</span>
                  <ChevronDown size={12} className={`transition-transform duration-200 ${showDropdown ? 'rotate-180' : ''}`} />
                </button>

                {showDropdown && (
                  <div ref={scrollContainerRef} className="absolute right-0 top-full mt-1 w-[160px] bg-white border-2 border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,0.1)] z-50 max-h-[240px] overflow-y-auto custom-scrollbar">
                    {Array.from({ length: iterations }, (_, i) => i + 1).map(it => {
                      const isDeEmphasized = it > currentLatest;
                      const isSelected = activeIteration === it;
                      
                      let itemClass = `px-3 py-2 text-[10px] font-black border-b border-gray-100 last:border-0 cursor-pointer transition-colors `;
                      if (isSelected) {
                        itemClass += 'bg-black text-white';
                      } else if (isDeEmphasized) {
                        itemClass += 'text-gray-300 bg-gray-50/30 hover:bg-gray-100';
                      } else {
                        itemClass += 'text-black bg-white hover:bg-gray-100';
                      }
                      
                      return (
                        <div
                          key={it}
                          onClick={() => {
                            setActiveIteration(it);
                            setShowDropdown(false);
                          }}
                          className={itemClass}
                          data-selected={isSelected}
                        >
                          Iteration {it}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ) : (
              <div className="flex gap-1">
                {Array.from({ length: iterations }, (_, i) => i + 1).map(it => {
                  const isDeEmphasized = it > currentLatest;
                  const isSelected = activeIteration === it;
                  let btnClass = "w-6 h-6 text-[10px] font-black border transition-all cursor-pointer ";
                  
                  if (isSelected) {
                    btnClass += "bg-black text-white border-black";
                  } else if (isDeEmphasized) {
                    btnClass += "border-gray-200 text-gray-300 bg-gray-50/50 hover:bg-gray-100";
                  } else {
                    btnClass += "border-black text-black hover:bg-gray-100";
                  }
                  
                  return (
                    <button
                      key={it}
                      onClick={() => setActiveIteration(it)}
                      className={btnClass}
                    >
                      {it}
                    </button>
                  );
                })}
              </div>
            )}
            {task.status !== 'completed' && stagesToCancel.length > 0 && overallStatus !== 'completed' && overallStatus !== 'canceled' && (
              <CancelStepsButton
                task={task}
                stagesToCancel={stagesToCancel}
                onRefresh={onRefresh}
                label="Cancel Steps"
              />
            )}
          </div>
        </div>

        <div className="space-y-4">
          {activeStructure ? (
            activeStructure.map((item: any, idx: number) => {
              if (item.type === 'step') {
                const step = stepsMap[item.stage]
                const isRunning = step?.status === 'running' || step?.status === 'waiting' || (task.current_stage === item.stage && !step)
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
              const isRunning = step?.status === 'running' || step?.status === 'waiting' || (task.current_stage === stageName && !step)

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
