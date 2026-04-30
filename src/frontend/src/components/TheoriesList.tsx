import { useEffect, useState } from 'react';
import { Briefcase, Clock } from 'lucide-react';
import { getTheories } from '../api';
import type { TheoryArtifact } from '../api';

interface TheoriesListProps {
  taskId: string;
}

export function TheoriesList({ taskId }: TheoriesListProps) {
  const [theories, setTheories] = useState<TheoryArtifact[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTheories = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getTheories(taskId);
      setTheories(data);
    } catch (err: any) {
      setError(err.message || "Failed to fetch theories.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTheories();
  }, [taskId]);

  const validScores = theories.map(t => t.score).filter(s => s != null && s !== 0.0) as number[];
  const minScore = validScores.length > 0 ? Math.min(...validScores) : 0;
  const maxScore = validScores.length > 0 ? Math.max(...validScores) : 0;

  const getScoreStyle = (score: number | null | undefined) => {
    if (score == null || score === 0.0) {
      return { className: "bg-gray-200 text-gray-600 border border-gray-300", style: {} };
    }
    
    let normalized = 1;
    if (maxScore > minScore) {
      normalized = (score - minScore) / (maxScore - minScore);
    }
    
    // Green (120) for max score, Red (0) for min score.
    const hue = Math.round(normalized * 120);
    return {
      className: "border",
      style: {
        backgroundColor: `hsl(${hue}, 80%, 92%)`,
        color: `hsl(${hue}, 85%, 25%)`,
        borderColor: `hsl(${hue}, 80%, 85%)`
      }
    };
  };

  return (
    <div className="flex flex-col h-full bg-white text-gray-800 font-mono">
      <div className="flex justify-between items-center px-6 py-4 border-b border-black flex-shrink-0 bg-white">
        <h2 className="text-xs font-black text-black tracking-widest uppercase">Top Theories</h2>
        <button
          onClick={fetchTheories}
          className="p-1 text-black hover:bg-gray-100 transition-colors focus:outline-none border border-black"
          title="Refresh Theories"
        >
          <svg className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar">
        {loading && theories.length === 0 ? (
          <div className="flex justify-center items-center h-full opacity-30">
            <div className="animate-pulse text-[10px] font-black tracking-widest uppercase">Loading Theories...</div>
          </div>
        ) : error ? (
          <div className="p-4 bg-red-50 text-red-700 text-[10px] font-bold border border-red-200 tracking-widest">
            {error}
          </div>
        ) : theories.length === 0 ? (
          <div className="text-center text-gray-400 py-10 text-[10px] font-black tracking-widest uppercase">
            No theories found
          </div>
        ) : (
          <ul className="space-y-4">
            {theories.map((theory) => (
              <li key={theory.id}>
                <a 
                  href={`#/task/${taskId}/artifact/${theory.id}`}
                  className="block p-4 bg-white border-2 border-gray-200 hover:border-black transition-all group cursor-pointer"
                >
                  <div className="flex justify-between items-start mb-3">
                    <span className="font-black text-xs text-black truncate mr-3 tracking-tight" title={theory.id}>
                      {theory.id}
                    </span>
                    <span 
                      className={`inline-flex items-center px-2.5 py-1 rounded text-[12px] font-black uppercase shrink-0 border ${getScoreStyle(theory.score).className}`}
                      style={getScoreStyle(theory.score).style}
                    >
                      {theory.score != null ? theory.score.toFixed(4) : "N/A"}
                    </span>
                  </div>
                  <div className="text-[10px] text-gray-500 font-bold mb-1.5 flex items-center gap-2 uppercase tracking-wider">
                    <Briefcase size={12} className="text-gray-400 group-hover:text-black transition-colors" />
                    {theory.agent_type.replace(/-/g, ' ')}
                  </div>
                  <div className="text-[9px] text-gray-400 font-bold flex items-center gap-2 tracking-widest uppercase opacity-70">
                    <Clock size={12} className="text-gray-300" />
                    {new Date(theory.created_at).toLocaleDateString()} {new Date(theory.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
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
