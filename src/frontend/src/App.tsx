import { useState, useEffect, useRef } from 'react'
import { Plus, Folder, Activity, Sun, Moon, Menu, X } from 'lucide-react'
import * as api from './api'
import { StatusBadge } from './components/StatusBadge'
import { TaskDetail } from './components/TaskDetail'
import { CreateTaskModal } from './components/CreateTaskModal'
import { DeleteConfirmModal } from './components/DeleteConfirmModal'
import { GameOfLife } from './components/GameOfLife'
import { TaskDetailSkeleton } from './components/TaskDetailSkeleton'

function App() {
  const [tasks, setTasks] = useState<api.TaskShallow[]>([])
  const [currentHash, setCurrentHash] = useState(window.location.hash)
  const [showCreate, setShowCreate] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null)
  const [deleteInput, setDeleteInput] = useState('')
  const [isBackendDown, setIsBackendDown] = useState(false)
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const prevTasksRef = useRef<api.TaskShallow[]>([])
  const [selectedTaskDetails, setSelectedTaskDetails] = useState<api.Task | null>(null)
  const [taskError, setTaskError] = useState<string | null>(null)

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
    const root = document.documentElement;
    const timeout = setTimeout(() => {
      root.classList.add('theme-loaded');
    }, 150);
    return () => clearTimeout(timeout);
  }, []);

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
    const handleHashChange = () => {
      setCurrentHash(window.location.hash)
      setMobileSidebarOpen(false)
    }
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
                body: `Research "${task.title || task.id}" is now ${task.status}.`,
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

  const fetchSelectedTaskDetails = async (id: string, guard?: { active: boolean }) => {
    try {
      const detail = await api.getTask(id)
      if (!guard || guard.active) {
        setSelectedTaskDetails(detail)
        setTaskError(null)
      }
    } catch (e: any) {
      console.error(e)
      if (!guard || guard.active) {
        setSelectedTaskDetails(null)
        setTaskError(e.message || "Failed to load task details")
      }
    }
  }

  const handleRefresh = () => {
    fetchTasks()
    if (selectedTaskId) {
      fetchSelectedTaskDetails(selectedTaskId)
    }
  }

  useEffect(() => {
    const guard = { active: true }

    // Initial load
    fetchTasks()
    if (selectedTaskId) {
      setSelectedTaskDetails(null)
      setTaskError(null)
      fetchSelectedTaskDetails(selectedTaskId, guard)
    } else {
      setSelectedTaskDetails(null)
      setTaskError(null)
    }

    // Polling interval
    const interval = setInterval(() => {
      fetchTasks()
      if (selectedTaskId) {
        fetchSelectedTaskDetails(selectedTaskId, guard)
      }
    }, 2000)

    return () => {
      guard.active = false
      clearInterval(interval)
    }
  }, [selectedTaskId])

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

  const isAnyTaskRunning = tasks.some(t => t.status === 'running')

  return (
    <div className="min-h-screen bg-white text-black font-mono selection:bg-black selection:text-white relative flex flex-col h-screen overflow-hidden">
      {isBackendDown && (
        <div className="fixed inset-0 z-50 bg-black/20 backdrop-blur-[2px] pointer-events-none transition-all duration-300" />
      )}

      {/* Mobile Top Header */}
      <header className="xl:hidden border-b border-black bg-white p-3 flex items-center justify-between shrink-0 z-30">
        <button
          onClick={() => setMobileSidebarOpen(!mobileSidebarOpen)}
          className="p-2 border border-black bg-gray-50 hover:bg-gray-100 flex items-center justify-center transition-colors"
          aria-label="Toggle Navigation"
        >
          {mobileSidebarOpen ? <X size={18} /> : <Menu size={18} />}
        </button>
        <div
          className="h-6 cursor-pointer flex items-center"
          onClick={() => { window.location.hash = ''; setMobileSidebarOpen(false); }}
        >
          <img src="/catalyst-small.png" alt="Catalyst" className="h-full w-auto object-contain" />
        </div>
        <div className="w-9" />
      </header>

      <div className="flex flex-1 overflow-hidden relative">
        {/* Mobile Backdrop */}
        {mobileSidebarOpen && (
          <div
            className="xl:hidden fixed inset-0 bg-black/50 z-30 transition-opacity"
            onClick={() => setMobileSidebarOpen(false)}
          />
        )}

        {/* Sidebar */}
        <aside
          className={`fixed xl:relative inset-y-0 left-0 z-40 w-full sm:w-80 xl:w-96 border-r border-black flex flex-col bg-white transition-transform duration-300 ${
            mobileSidebarOpen ? 'translate-x-0' : '-translate-x-full xl:translate-x-0'
          }`}
        >
          <div
            className="p-6 border-b border-black flex items-center justify-center cursor-pointer hidden xl:flex"
            onClick={() => { window.location.hash = ''; setMobileSidebarOpen(false); }}
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
              onClick={() => { setShowCreate(true); setMobileSidebarOpen(false); }}
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
                onClick={() => setMobileSidebarOpen(false)}
                className={`group p-4 border-b border-black block cursor-pointer transition-all ${selectedTaskId === task.id ? 'bg-black text-white' : 'hover:bg-gray-50'}`}
              >
                <div className="flex justify-between items-start mb-2 gap-2">
                  <span className={`font-bold text-xs truncate flex-1 ${selectedTaskId === task.id ? 'text-white' : 'text-black'}`}>
                    {task.title}
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
          {selectedTaskId ? (
            taskError ? (
              <div className="flex-1 flex flex-col items-center justify-center p-20 text-center">
                <h2 className="text-2xl font-black tracking-tighter mb-2">Task Not Found</h2>
                <p className="text-gray-400 max-w-sm text-sm mb-6">
                  {taskError}
                </p>
                <button
                  onClick={() => { window.location.hash = ''; }}
                  className="px-6 py-3 bg-black text-white font-bold text-xs tracking-widest hover:bg-gray-800 transition-colors"
                >
                  Back to Dashboard
                </button>
              </div>
            ) : selectedTaskDetails ? (
              <TaskDetail
                key={selectedTaskDetails.id}
                task={selectedTaskDetails}
                viewingArtifactId={viewingArtifactId}
                onDeleteRequest={(id) => setShowDeleteConfirm(id)}
                onRefresh={handleRefresh}
                isBackendDown={isBackendDown}
              />
            ) : (
              <TaskDetailSkeleton />
            )
          ) : isAnyTaskRunning ? (
            <GameOfLife
              useHighLifeRules={tasks.some(
                t => t.status === 'running' && (t.workflow_name === 'develop-theory' || t.workflow_name === 'solve-verifiable-goal')
              )}
            />
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-20 text-center">
              <h2 className="text-2xl font-black tracking-tighter mb-2">Ready for Discovery</h2>
              <p className="text-gray-400 max-w-sm text-sm">
                Select a research thread from the sidebar or start a new inquiry.
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
