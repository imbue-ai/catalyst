import { useEffect, useState } from 'react';
import { Briefcase, Clock } from 'lucide-react';
import { getSolutions } from '../api';
import type { SolutionArtifact } from '../api';

interface SolutionsListProps {
  taskId: string;
}

export function SolutionsList({ taskId }: SolutionsListProps) {
  const [solutions, setSolutions] = useState<SolutionArtifact[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSolutions = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getSolutions(taskId);
      setSolutions(data);
    } catch (err: any) {
      setError(err.message || "Failed to fetch solutions.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSolutions();
  }, [taskId]);

  return (
    <div className="flex flex-col h-full bg-white text-gray-800 font-mono">
      <div className="flex justify-between items-center px-6 py-4 border-b border-black flex-shrink-0 bg-white">
        <h2 className="text-xs font-black text-black tracking-widest">Solutions</h2>
        <div className="flex items-center gap-4">
          <button
            onClick={fetchSolutions}
            className="p-1 text-black hover:bg-gray-100 transition-colors focus:outline-none border border-black"
            title="Refresh Solutions"
          >
            <svg className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar">
        {loading && solutions.length === 0 ? (
          <div className="flex justify-center items-center h-full opacity-30">
            <div className="animate-pulse text-[10px] font-black tracking-widest">Loading Solutions...</div>
          </div>
        ) : error ? (
          <div className="p-4 bg-red-50 text-red-700 text-[10px] font-bold border border-red-200 tracking-widest">
            {error}
          </div>
        ) : solutions.length === 0 ? (
          <div className="text-center text-gray-400 py-10 text-[10px] font-black tracking-widest">
            No Solutions Found
          </div>
        ) : (
          <ul className="space-y-4">
            {solutions.map((sol) => (
              <li key={sol.id}>
                <a 
                  href={`#/task/${taskId}/artifact/${sol.id}`}
                  className="block p-4 bg-white border-2 border-gray-200 hover:border-black transition-all group cursor-pointer"
                >
                  <div className="flex justify-between items-start mb-3">
                    <span className="font-black text-xs text-black truncate mr-3 tracking-tight" title={sol.headline ? `${sol.id}: ${sol.headline}` : sol.id}>
                      {sol.headline ? `${sol.id}: ${sol.headline}` : sol.id}
                    </span>
                  </div>
                  <div className="text-[10px] text-gray-500 font-bold mb-1.5 flex items-center gap-2 tracking-wider capitalize">
                    <Briefcase size={12} className="text-gray-400 group-hover:text-black transition-colors" />
                    {(sol.extra?.parent_agent_type || sol.agent_type || 'unknown').replace(/-/g, ' ')}
                  </div>
                  <div className="text-[9px] text-gray-400 font-bold flex items-center gap-2 tracking-widest opacity-70">
                    <Clock size={12} className="text-gray-300" />
                    {sol.created_at
                      ? new Date(sol.created_at).toLocaleDateString() + ' ' + 
                        new Date(sol.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                      : 'Unknown Date'}
                  </div>
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
