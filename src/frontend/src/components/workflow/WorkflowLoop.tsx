import { useState, useEffect } from 'react'
import { History, Loader2, RefreshCw } from 'lucide-react'
import * as api from '../../api'

interface WorkflowLoopProps {
  name: string;
  baseStages: string[];
  iterations: number;
  task: api.Task;
  onSelect: (idx: number) => void;
  selectedStage?: string;
  onRetry: () => void;
}

export function WorkflowLoop({ name, baseStages, iterations, task, onSelect, selectedStage, onRetry }: WorkflowLoopProps) {
  const [activeIteration, setActiveIteration] = useState(1)
  const [lastLatest, setLastLatest] = useState(0)

  useEffect(() => {
    // Calculate what the current latest iteration is based on steps
    let currentLatest = 1
    for (let i = iterations; i >= 1; i--) {
      if (task.steps.some(s => s.stage.endsWith(`-${i}`))) {
        currentLatest = i
        break
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
  }, [task.steps, iterations, activeIteration, lastLatest])

  const getStepForIteration = (it: number, baseStage: string) => {
    const stage = `${baseStage}-${it}`
    return task.steps.find(s => s.stage === stage)
  }

  return (
    <div className="relative pl-8 mt-12">
      <div className="absolute left-[9px] -top-12 w-[2px] h-12 bg-gray-100" />
      <div className="absolute left-[-10px] top-6 w-10 h-[200px] border-l-2 border-y-2 border-black rounded-l-2xl opacity-20" />
      
      <div className="bg-white border-2 border-black p-6 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-2">
            <History size={16} />
            <h4 className="font-black text-xs uppercase tracking-[0.2em]">{name}</h4>
          </div>
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
        </div>

        <div className="space-y-4">
          {baseStages.map(baseStage => {
            const stageName = `${baseStage}-${activeIteration}`
            const step = getStepForIteration(activeIteration, baseStage)
            const isCurrent = task.current_stage === stageName
            
            return (
              <div 
                key={baseStage}
                onClick={() => {
                   if (step) {
                     const idx = task.steps.findIndex(s => s.stage === step.stage)
                     onSelect(idx)
                   }
                }}
                className={`p-3 border-2 transition-all ${
                  step ? 'cursor-pointer' : 'opacity-30 cursor-default'
                } ${
                  selectedStage === stageName
                    ? 'border-black bg-gray-50' : 'border-gray-100 hover:border-black'
                }`}
              >
                <div className="flex justify-between items-center">
                  <span className={`text-[10px] font-black uppercase ${isCurrent ? 'text-blue-600' : ''}`}>{baseStage.replace(/-/g, ' ')}</span>
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
                    {isCurrent && <Loader2 size={10} className="animate-spin text-blue-600" />}
                    <span className={`text-[8px] font-bold uppercase ${
                      step?.status === 'completed' ? 'text-green-600' :
                      step?.status === 'paused' ? 'text-yellow-600' :
                      step?.status === 'failed' ? 'text-red-600' :
                      (step?.status === 'running' || isCurrent) ? 'text-blue-600' : 'text-gray-400'
                    }`}>{step?.status || (isCurrent ? 'running' : 'upcoming')}</span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
        
        <div className="mt-4 text-center">
          <div className="inline-block text-[8px] font-black uppercase tracking-widest text-gray-300">
            Iteration {activeIteration} of {iterations}
          </div>
        </div>
      </div>
    </div>
  )
}
