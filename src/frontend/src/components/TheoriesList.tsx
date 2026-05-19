import { useEffect, useState } from 'react';
import { Briefcase, Clock, ChevronDown, ChevronUp } from 'lucide-react';
import { getTheories, getReviews } from '../api';
import type { TheoryArtifact, ReviewArtifact } from '../api';

interface TheoriesListProps {
  taskId: string;
}

export function TheoriesList({ taskId }: TheoriesListProps) {
  const [theories, setTheories] = useState<TheoryArtifact[]>([]);
  const [reviews, setReviews] = useState<ReviewArtifact[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [expandedTheories, setExpandedTheories] = useState<Set<string>>(new Set());

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [theoriesData, reviewsData] = await Promise.all([
        getTheories(taskId),
        getReviews(taskId).catch(() => []) // Default to empty array if reviews fail to fetch
      ]);
      setTheories(theoriesData);
      setReviews(reviewsData);
    } catch (err: any) {
      setError(err.message || "Failed to fetch data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [taskId]);

  const filteredTheories = theories.filter(t => showAll || (t.score != null && t.score !== 0.0) || t.is_leaf_node);

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

  const toggleExpand = (theoryId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setExpandedTheories(prev => {
      const newSet = new Set(prev);
      if (newSet.has(theoryId)) {
        newSet.delete(theoryId);
      } else {
        newSet.add(theoryId);
      }
      return newSet;
    });
  };

  return (
    <div className="flex flex-col h-full bg-white text-gray-800 font-mono">
      <div className="flex justify-between items-center px-6 py-4 border-b border-black flex-shrink-0 bg-white">
        <h2 className="text-xs font-black text-black tracking-widest">Top Theories</h2>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 cursor-pointer group">
            <div className={`w-3 h-3 border-2 border-black flex items-center justify-center transition-colors ${showAll ? 'bg-black' : 'bg-white'}`}>
              {showAll && <div className="w-1.5 h-1.5 bg-white" />}
              <input
                type="checkbox"
                className="hidden"
                checked={showAll}
                onChange={e => setShowAll(e.target.checked)}
              />
            </div>
            <span className="text-[10px] font-black tracking-widest text-gray-400 group-hover:text-black transition-colors">Show All</span>
          </label>          <button
            onClick={fetchData}
            className="p-1 text-black hover:bg-gray-100 transition-colors focus:outline-none border border-black"
            title="Refresh Data"
          >
            <svg className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
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
        ) : filteredTheories.length === 0 ? (
          <div className="text-center text-gray-400 py-10 text-[10px] font-black tracking-widest uppercase">
            {theories.length > 0 ? "No scored theories found" : "No theories found"}
          </div>
        ) : (
          <ul className="space-y-4">
            {filteredTheories.map((theory) => {
              const theoryReviews = reviews.filter(r => r.parent_theory === theory.id);
              const isExpanded = expandedTheories.has(theory.id);

              return (
                <li key={theory.id}>
                  <div className="bg-white border-2 border-gray-200 hover:border-black transition-all group">
                    <a 
                      href={`#/task/${taskId}/artifact/${theory.id}`}
                      className="block p-4 cursor-pointer"
                    >
                      <div className="flex justify-between items-start mb-3">
                        <span className="font-black text-xs text-black truncate mr-3 tracking-tight" title={theory.headline ? `${theory.id}: ${theory.headline}` : theory.id}>
                          {theory.headline ? `${theory.id}: ${theory.headline}` : theory.id}
                        </span>
                        <span 
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-black shrink-0 border ${getScoreStyle(theory.score).className}`}
                          style={getScoreStyle(theory.score).style}
                          title={theory.subscores && Object.keys(theory.subscores).length > 0
                            ? Object.entries(theory.subscores).map(([k, v]) => `${k.charAt(0).toUpperCase() + k.slice(1)}: ${typeof v === 'number' ? v.toFixed(4) : v}`).join('\n')
                            : undefined}
                        >
                          {theory.score != null ? theory.score.toFixed(4) : "N/A"}
                        </span>
                      </div>
                      <div className="flex justify-between items-end">
                        <div>
                          <div className="text-[10px] text-gray-500 font-bold mb-1.5 flex items-center gap-2 tracking-wider capitalize">
                            <Briefcase size={12} className="text-gray-400 group-hover:text-black transition-colors" />
                            {(theory.agent_type || (theory as any).type || 'unknown').replace(/-/g, ' ')}
                          </div>
                          <div className="text-[9px] text-gray-400 font-bold flex items-center gap-2 tracking-widest uppercase opacity-70">
                            <Clock size={12} className="text-gray-300" />
                            {theory.created_at || (theory as any).timestamp 
                              ? new Date(theory.created_at || (theory as any).timestamp).toLocaleDateString() + ' ' + 
                                new Date(theory.created_at || (theory as any).timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                              : 'Unknown Date'}
                          </div>
                        </div>
                        {theoryReviews.length > 0 && (
                          <button 
                            onClick={(e) => toggleExpand(theory.id, e)}
                            className="text-[10px] font-black tracking-widest uppercase text-gray-500 hover:text-black flex items-center gap-1 transition-colors"
                          >
                            {isExpanded ? 'Hide Reviews' : `${theoryReviews.length} Review${theoryReviews.length > 1 ? 's' : ''} Available`}
                            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                          </button>
                        )}
                      </div>
                    </a>
                    
                    {isExpanded && theoryReviews.length > 0 && (
                      <div className="border-t-2 border-gray-100 bg-gray-50 p-4">
                        <ul className="space-y-2">
                          {theoryReviews.map(review => (
                            <li key={review.id}>
                              <a 
                                href={`#/task/${taskId}/artifact/${review.id}`}
                                className="block p-2 bg-white border border-gray-200 hover:border-black transition-colors"
                              >
                                <div className="text-[10px] font-black text-black truncate tracking-widest mb-1">
                                  {review.id}
                                </div>
                                {review.headline && (
                                  <div className="text-[10px] text-gray-600 font-bold truncate">
                                    {review.headline}
                                  </div>
                                )}
                              </a>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
