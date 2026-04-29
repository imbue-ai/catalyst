import { useState, useEffect } from 'react'
import { RotateCw, Loader2, RefreshCw, XCircle } from 'lucide-react'
import * as api from '../../api'

interface WorkflowLoopProps {
  name: string;
  baseStages: string[];
  iterations: number;
  task: api.Task;
  onSelect: (stage: string) => void;
  selectedStage?: string;
  onRetry: () => void;
  onRefresh: () => void;
}

export function WorkflowLoop({ name, baseStages, iterations, task, onSelect, selectedStage, onRetry, onRefresh }: WorkflowLoopProps) {
  const [activeIteration, setActiveIteration] = useState(1)
  const [lastLatest, setLastLatest] = useState(0)
  const [isCanceling, setIsCanceling] = useState(false)

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
      
      <div className="bg-white border-2 border-gray-200 p-6">
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <RotateCw size={16} />
              <h4 className="font-black text-xs uppercase tracking-[0.2em]">{name}</h4>
            </div>
            {task.status !== 'completed' && (
              <button 
                onClick={async () => {
                  setIsCanceling(true);
                  try {
                    const stagesToCancel: string[] = [];
                    for (let i = 1; i <= iterations; i++) {
                      baseStages.forEach(bs => stagesToCancel.push(`${bs}-${i}`));
                    }
                    await api.bulkCancelSteps(task.id, stagesToCancel);
                    onRefresh();
                  } catch (e: any) {
                    alert(e.message || "Failed to cancel loop");
                  } finally {
                    setIsCanceling(false);
                  }
                }}
                disabled={isCanceling}
                className="text-[10px] font-black uppercase text-gray-400 hover:text-red-600 transition-colors flex items-center gap-1 bg-gray-50 px-2 py-1 rounded-sm border border-gray-200 hover:border-red-200"
              >
                {isCanceling ? <Loader2 size={10} className="animate-spin" /> : <XCircle size={10} />} Cancel Loop
              </button>
            )}
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
            const isCurrent = task.current_stage === stageName && (!step || step.status === 'running')
            
            return (
              <div 
                key={baseStage}
                onClick={() => onSelect(stageName)}
                className={`p-3 border-2 transition-all cursor-pointer ${
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
                      step?.status === 'canceled' ? 'text-gray-500' :
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
