import { useEffect, useState } from 'react';
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
    <div className="flex flex-col h-full bg-white text-gray-800">
      <div className="flex justify-between items-center px-6 py-4 border-b border-gray-100 flex-shrink-0">
        <h2 className="text-xl font-bold text-gray-900 tracking-tight">Top Theories</h2>
        <button
          onClick={fetchTheories}
          className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
          title="Refresh Theories"
        >
          <svg className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {loading && theories.length === 0 ? (
          <div className="flex justify-center items-center h-full">
            <div className="animate-pulse flex space-x-2">
              <div className="h-2 w-2 bg-blue-400 rounded-full"></div>
              <div className="h-2 w-2 bg-blue-400 rounded-full"></div>
              <div className="h-2 w-2 bg-blue-400 rounded-full"></div>
            </div>
          </div>
        ) : error ? (
          <div className="p-4 bg-red-50 text-red-700 rounded-lg text-sm border border-red-100">
            {error}
          </div>
        ) : theories.length === 0 ? (
          <div className="text-center text-gray-500 py-10">
            No theories found for this task.
          </div>
        ) : (
          <ul className="space-y-3">
            {theories.map((theory) => (
              <li key={theory.id} className="p-4 bg-gray-50 rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex justify-between items-start mb-2">
                  <a 
                    href={`#/task/${taskId}/artifact/${theory.id}`}
                    className="font-mono text-sm font-semibold text-blue-700 truncate mr-3 hover:underline cursor-pointer" 
                    title={theory.id}
                  >
                    {theory.id}
                  </a>
                  <span 
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium shrink-0 ${getScoreStyle(theory.score).className}`}
                    style={getScoreStyle(theory.score).style}
                  >
                    {theory.score != null ? theory.score.toFixed(4) : "N/A"}
                  </span>
                  </div>                <div className="text-sm text-gray-600 mb-1 flex items-center">
                  <svg className="w-4 h-4 mr-1.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                  {theory.agent_type}
                </div>
                <div className="text-xs text-gray-500 mt-2 flex items-center">
                  <svg className="w-3.5 h-3.5 mr-1.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {new Date(theory.created_at).toLocaleString()}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
