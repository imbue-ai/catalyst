import { useState, useEffect, useRef } from 'react'
import { Plus, Folder, Activity, Sun, Moon } from 'lucide-react'
import * as api from './api'
import { StatusBadge } from './components/StatusBadge'
import { TaskDetail } from './components/TaskDetail'
import { CreateTaskModal } from './components/CreateTaskModal'
import { DeleteConfirmModal } from './components/DeleteConfirmModal'
import { GameOfLife } from './components/GameOfLife'

function App() {
  const [tasks, setTasks] = useState<api.Task[]>([])
  const [currentHash, setCurrentHash] = useState(window.location.hash)
  const [showCreate, setShowCreate] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null)
  const [deleteInput, setDeleteInput] = useState('')
  const [isBackendDown, setIsBackendDown] = useState(false)
  const prevTasksRef = useRef<api.Task[]>([])

  const [isDarkMode, setIsDarkMode] = useState(() => {
    const saved = localStorage.getItem('theme');
    if (saved) {
      return saved === 'dark';
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  useEffect(() => {
    const root = document.documentElement;
    if (isDarkMode) {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [isDarkMode]);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e: MediaQueryListEvent) => {
      const saved = localStorage.getItem('theme');
      if (!saved) {
        setIsDarkMode(e.matches);
      }
    };
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  const toggleDarkMode = () => {
    setIsDarkMode(prev => {
      const next = !prev;
      localStorage.setItem('theme', next ? 'dark' : 'light');
      return next;
    });
  };

  useEffect(() => {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
  }, []);

  useEffect(() => {
    const handleHashChange = () => setCurrentHash(window.location.hash)
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  let selectedTaskId: string | null = null;
  let viewingArtifactId: string | null = null;
  const match = currentHash.split('?')[0].match(/^#\/task\/([^\/]+)(?:\/artifact\/([^\/]+))?/);
  if (match) {
    selectedTaskId = match[1];
    viewingArtifactId = match[2] || null;
  }

  const fetchTasks = async () => {
    try {
      const data = await api.listTasks()

      // Detect changes
      if (prevTasksRef.current.length > 0) {
        const oldTaskMap = new Map(prevTasksRef.current.map(t => [t.id, t]));
        data.forEach(task => {
          const oldTask = oldTaskMap.get(task.id);
          if (oldTask && oldTask.status !== task.status) {
            if (Notification.permission === "granted") {
              const notification = new Notification("Research Status Update", {
                body: `Research "${task.title || task.workflow_inputs.summary || task.id}" is now ${task.status}.`,
                icon: "/favicon.png"
              });
              notification.onclick = () => {
                window.focus();
                window.location.hash = `#/task/${task.id}`;
              };
            }
          }
        });
      }
      prevTasksRef.current = data;

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
        if (selectedTaskId === showDeleteConfirm) {
          window.location.hash = '';
        }
        setShowDeleteConfirm(null)
        setDeleteInput('')
      } catch (e) {
        alert("Failed to delete task")
      }
    }
  }

  const selectedTask = tasks.find(t => t.id === selectedTaskId)
  const isAnyTaskRunning = tasks.some(t => t.status === 'running')

  return (
    <div className="min-h-screen bg-white text-black font-mono selection:bg-black selection:text-white relative">
      {isBackendDown && (
        <div className="fixed inset-0 z-50 bg-black/20 backdrop-blur-[2px] pointer-events-none transition-all duration-300" />
      )}

      {/* Sidebar */}
      <div className="flex h-screen overflow-hidden">
        <aside className="w-96 border-r border-black flex flex-col bg-white">
          <div
            className="p-6 border-b border-black flex items-center justify-center cursor-pointer"
            onClick={() => { window.location.hash = ''; }}
            title="Return to Home"
          >
            <img
              src="/catalyst-small.png"
              alt="Catalyst"
              className="w-full h-auto object-contain"
            />
          </div>

          <div className="p-4 border-b border-black flex items-center justify-between bg-gray-50/50">
            <div className="flex items-center gap-2 text-[10px] font-bold text-gray-500 tracking-widest">
              <Activity size={12} /> Current Research
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
            {[...tasks].sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '')).map(task => (
              <a
                key={task.id}
                href={`#/task/${task.id}`}
                className={`group p-4 border-b border-black block cursor-pointer transition-all ${selectedTaskId === task.id ? 'bg-black text-white' : 'hover:bg-gray-50'}`}
              >
                <div className="flex justify-between items-start mb-2 gap-2">
                  <span className={`font-bold text-xs truncate flex-1 ${selectedTaskId === task.id ? 'text-white' : 'text-black'}`}>
                    {task.title || task.workflow_inputs.summary}
                  </span>
                  <StatusBadge status={task.status} />
                </div>
                <div className={`text-[10px] flex flex-col gap-1 ${selectedTaskId === task.id ? 'text-gray-400' : 'text-gray-500'}`}>
                  <div className="flex items-center gap-1 min-w-0">
                    <Folder size={10} className="shrink-0" />
                    <span
                      className="overflow-hidden whitespace-nowrap text-ellipsis min-w-0 flex-1"
                      style={{ direction: 'rtl', textAlign: 'left' }}
                      title={task.env_folder}
                    >
                      {/* Using unicode-bidi: plaintext to keep path characters (slashes, etc) in order but allow RTL truncation (ellipsis on left) */}
                      <span style={{ unicodeBidi: 'plaintext' }}>
                        {task.env_folder}
                      </span>
                    </span>
                  </div>
                </div>              </a>
            ))}
          </div>

          <div className="p-4 border-t border-black bg-white flex justify-between items-center text-[9px] font-bold text-gray-400 tracking-[0.2em] mt-auto">
            <span className={isBackendDown ? "text-red-500 animate-pulse no-invert" : "text-black"}>
              {isBackendDown ? "● Disconnected" : "● Connected"}
            </span>
            <button
              onClick={toggleDarkMode}
              className="p-1 hover:bg-gray-100 rounded transition-colors text-black flex items-center justify-center cursor-pointer"
              title={isDarkMode ? "Switch to Light Mode" : "Switch to Dark Mode"}
            >
              {isDarkMode ? <Sun size={12} /> : <Moon size={12} />}
            </button>
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto bg-white flex flex-col relative">
          {selectedTask ? (
            <TaskDetail
              key={selectedTask.id}
              task={selectedTask}
              viewingArtifactId={viewingArtifactId}
              onDeleteRequest={(id) => setShowDeleteConfirm(id)}
              onRefresh={fetchTasks}
              isBackendDown={isBackendDown}
            />
          ) : isAnyTaskRunning ? (
            <GameOfLife />
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-20 text-center">
              <div className="w-24 h-24 border border-black rounded-full flex items-center justify-center mb-6 animate-pulse">
                <Activity size={40} strokeWidth={1} className="text-gray-300" />
              </div>
              <h2 className="text-2xl font-black tracking-tighter mb-2">Ready for Discovery</h2>
              <p className="text-gray-400 max-w-sm text-sm">
                Select a research thread from the sidebar or start a new scientific inquiry.
              </p>
              <button
                onClick={() => setShowCreate(true)}
                className="mt-8 px-6 py-3 bg-black text-white font-bold text-xs tracking-widest hover:bg-gray-800 transition-colors"
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
            window.location.hash = `#/task/${task.id}`;
            setShowCreate(false);
          }}
          isBackendDown={isBackendDown}
        />
      )}
    </div>
  )
}

export default App
