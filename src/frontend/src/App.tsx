import { useState, useEffect } from 'react'
import { Plus, List, Database, Folder, Cpu, Activity, FlaskConical, History, XCircle } from 'lucide-react'
import * as api from './api'
import { StatusBadge } from './components/StatusBadge'
import { TaskDetail } from './components/TaskDetail'
import { CreateTaskModal } from './components/CreateTaskModal'
import { DeleteConfirmModal } from './components/DeleteConfirmModal'

function App() {
  const [tasks, setTasks] = useState<api.Task[]>([])
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null)
  const [deleteInput, setDeleteInput] = useState('')
  const [isBackendDown, setIsBackendDown] = useState(false)

  const fetchTasks = async () => {
    try {
      const data = await api.listTasks()
      setTasks(data)
      setIsBackendDown(false)
    } catch (e) {
      console.error(e)
      setIsBackendDown(true)
    }
  }

  useEffect(() => {
    fetchTasks()
    const interval = setInterval(fetchTasks, 2000)
    return () => clearInterval(interval)
  }, [])

  const handleDelete = async () => {
    if (deleteInput.toLowerCase() === 'delete' && showDeleteConfirm) {
      try {
        await api.deleteTask(showDeleteConfirm)
        setTasks(tasks.filter(t => t.id !== showDeleteConfirm))
        setSelectedTaskId(null)
        setShowDeleteConfirm(null)
        setDeleteInput('')
      } catch (e) {
        alert("Failed to delete task")
      }
    }
  }

  const selectedTask = tasks.find(t => t.id === selectedTaskId)

  return (
    <div className="min-h-screen bg-white text-black font-mono selection:bg-black selection:text-white">
      {isBackendDown && (
        <div className="bg-red-600 text-white p-2 text-[10px] font-black uppercase tracking-[0.3em] flex items-center justify-center gap-4 sticky top-0 z-[100] animate-pulse">
          <XCircle size={14} /> Backend Server Offline - Reconnecting...
        </div>
      )}

      {/* Sidebar */}
      <div className="flex h-screen overflow-hidden">
        <aside className="w-80 border-r border-black flex flex-col bg-white">
          <div className="p-6 border-b border-black flex items-center gap-3">
            <div className="bg-black p-2 rounded-sm text-white">
              <FlaskConical size={20} />
            </div>
            <h1 className="text-lg font-black tracking-tight leading-none uppercase">
              AI Scientist<br /><span className="text-gray-400">Orchestrator</span>
            </h1>
          </div>

          <div className="p-4 border-b border-black flex items-center justify-between bg-gray-50/50">
            <div className="flex items-center gap-2 text-[10px] font-bold text-gray-500 uppercase tracking-widest">
              <History size={12} /> Recent Research
            </div>
            <button
              onClick={() => setShowCreate(true)}
              className="hover:scale-110 transition-transform p-1 bg-black text-white rounded-full"
              title="New Research Task"
            >
              <Plus size={16} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto custom-scrollbar">
            {tasks.length === 0 && (
              <div className="p-12 text-center text-gray-300 italic text-sm">
                No active research threads.
              </div>
            )}
            {tasks.map(task => (
              <div
                key={task.id}
                onClick={() => setSelectedTaskId(task.id)}
                className={`group p-4 border-b border-black cursor-pointer transition-all ${selectedTaskId === task.id ? 'bg-black text-white' : 'hover:bg-gray-50'}`}
              >
                <div className="flex justify-between items-start mb-2 gap-2">
                  <span className={`font-bold text-xs uppercase truncate flex-1 ${selectedTaskId === task.id ? 'text-white' : 'text-black'}`}>
                    {task.title || task.phenomenon}
                  </span>
                  <StatusBadge status={task.status} inverted={selectedTaskId === task.id} />
                </div>
                <div className={`text-[10px] flex flex-col gap-1 ${selectedTaskId === task.id ? 'text-gray-400' : 'text-gray-500'}`}>
                  <div className="flex items-center gap-1 truncate"><Folder size={10} /> {task.env_folder}</div>
                </div>
              </div>
            ))}
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto bg-white flex flex-col relative">
          {selectedTask ? (
            <TaskDetail
              key={selectedTask.id}
              task={selectedTask}
              onDeleteRequest={(id) => setShowDeleteConfirm(id)}
              onRefresh={fetchTasks}
            />
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-20 text-center">
              <div className="w-24 h-24 border border-black rounded-full flex items-center justify-center mb-6 animate-pulse">
                <Activity size={40} strokeWidth={1} className="text-gray-300" />
              </div>
              <h2 className="text-2xl font-black uppercase tracking-tighter mb-2">Ready for Discovery</h2>
              <p className="text-gray-400 max-w-sm text-sm">
                Select a research thread from the sidebar or start a new scientific inquiry to observe the automated theory development process.
              </p>
              <button
                onClick={() => setShowCreate(true)}
                className="mt-8 px-6 py-3 bg-black text-white font-bold uppercase text-xs tracking-widest hover:bg-gray-800 transition-colors"
              >
                + Start New Research
              </button>
            </div>
          )}
        </main>
      </div>

      {/* Modals */}
      {showDeleteConfirm && (
        <DeleteConfirmModal
          onClose={() => { setShowDeleteConfirm(null); setDeleteInput(''); }}
          onDelete={handleDelete}
          deleteInput={deleteInput}
          setDeleteInput={setDeleteInput}
        />
      )}

      {showCreate && (
        <CreateTaskModal
          onClose={() => setShowCreate(false)}
          onCreated={(task) => {
            setTasks([task, ...tasks]);
            setSelectedTaskId(task.id);
            setShowCreate(false);
          }}
          isBackendDown={isBackendDown}
        />
      )}
    </div>
  )
}

export default App
