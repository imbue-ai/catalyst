import { useEffect, useState, useMemo, memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import rehypeSlug from 'rehype-slug';
import 'katex/dist/katex.min.css';
import { Loader2, BookOpen } from 'lucide-react';
import * as api from '../api';

const MemoizedMarkdown = memo(({ content, components, remarkPlugins, rehypePlugins }: any) => (
  <ReactMarkdown
    remarkPlugins={remarkPlugins}
    rehypePlugins={rehypePlugins}
    components={components}
  >
    {content}
  </ReactMarkdown>
));

interface SummaryTabProps {
  taskId: string;
}

export function SummaryTab({ taskId }: SummaryTabProps) {
  const [summaries, setSummaries] = useState<api.SummaryArtifact[]>([]);
  const [latestSummaryId, setLatestSummaryId] = useState<string | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch the list of summaries and load the most recent one if changed
  const fetchSummaries = async (isPoll: boolean = false) => {
    if (!isPoll) {
      setLoading(true);
    }
    setError(null);
    try {
      const summaryList = await api.getSummaries(taskId);
      setSummaries(summaryList);
      
      if (summaryList.length > 0) {
        const latest = summaryList[0];
        // If it's a new summary or we haven't loaded any summary yet
        if (latest.id !== latestSummaryId) {
          const response = await fetch(`${api.API_BASE_URL}/api/tasks/${taskId}/artifacts/${latest.id}/primary?skip_disclaimer=true`);
          if (!response.ok) {
            throw new Error('Failed to fetch summary content');
          }
          const data = await response.json();
          setContent(data.content);
          setLatestSummaryId(latest.id);
        }
      } else {
        setContent(null);
        setLatestSummaryId(null);
      }
    } catch (err) {
      console.error('Error fetching summaries:', err);
      if (!isPoll) {
        setError(err instanceof Error ? err.message : 'Failed to retrieve research summaries');
      }
    } finally {
      setLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    fetchSummaries(false);
    // Reset state when taskId changes
    return () => {
      setSummaries([]);
      setLatestSummaryId(null);
      setContent(null);
      setLoading(true);
    };
  }, [taskId]);

  // 30-second polling
  useEffect(() => {
    const interval = setInterval(() => {
      fetchSummaries(true);
    }, 30000);

    return () => clearInterval(interval);
  }, [taskId, latestSummaryId]);

  const processedContent = useMemo(() => {
    if (!content) return '';
    
    // Process markdown to robustly handle math block lines
    const withNewlines = content.replace(/\$\$(.*?)\$\$/gs, (_, mathContent) => {
      return `\n\n$$\n${mathContent.trim()}\n$$\n\n`;
    });

    const parts = withNewlines.split(/(```[\s\S]*?```|`[^`]+`|\$\$[\s\S]*?\$\$)/g);
    return parts.map((part, i) => {
      if (i % 2 === 0) {
        let processed = part.replace(/\b([ELTRXPSOIU]_\d{8}_\d{6}_[a-f0-9]{6})\b/g, `[$1](#/task/${taskId}/artifact/$1)`);
        processed = processed.replace(/^([ \t]*-\s*)(Add\s+to\s+Guidance):\s*"([^"]+)"/gim, (_match, prefix, btnText, value) => {
          return `${prefix}[${btnText}](#add-to-guidance:${encodeURIComponent(value)}): "${value}"`;
        });
        return processed;
      } else {
        const match = part.match(/^`([ELTRXPSOIU]_\d{8}_\d{6}_[a-f0-9]{6})`$/);
        if (match) {
          return `[${part}](#/task/${taskId}/artifact/${match[1]})`;
        }
        return part;
      }
    }).join('');
  }, [content, taskId]);

  const markdownComponents = useMemo(() => ({
    a({ node, href, children, className, ...props }: any) {
      if (href && (href.startsWith('#add-to-guidance:') || href.startsWith('add-to-guidance:'))) {
        const isHash = href.startsWith('#add-to-guidance:');
        const prefixLen = isHash ? '#add-to-guidance:'.length : 'add-to-guidance:'.length;
        const queryIdx = href.indexOf('?');
        const encodedValue = queryIdx !== -1 
          ? href.slice(prefixLen, queryIdx)
          : href.slice(prefixLen);
        const value = decodeURIComponent(encodedValue);
        return (
          <button
            onClick={(e) => {
              e.preventDefault();
              window.dispatchEvent(new CustomEvent('add-to-guidance', { detail: { value } }));
            }}
            className="text-blue-600 font-bold hover:underline cursor-pointer bg-blue-50 px-1.5 py-0.5 rounded inline-flex items-center gap-1 align-baseline"
          >
            <span className="text-[10px]" aria-hidden="true">➕</span>
            {children}
          </button>
        );
      }
      return <a href={href} className={className} {...props}>{children}</a>;
    },
    img({ node, src, alt, className, ...props }: any) {
      let resolvedSrc = src;
      if (src && !src.startsWith('http') && !src.startsWith('data:')) {
        resolvedSrc = `${api.API_BASE_URL}/api/tasks/${taskId}/artifacts/${latestSummaryId}/files/${src.replace(/^\.\//, '')}`;
      }
      return (
        <span className="inline-block w-full">
          <img src={resolvedSrc} alt={alt} className={className} {...props} />
        </span>
      );
    }
  }), [taskId, latestSummaryId]);

  const remarkPlugins = useMemo(() => [remarkMath, remarkGfm], []);
  const rehypePlugins = useMemo(() => [rehypeSlug, [rehypeKatex, { strict: 'ignore' }]], []);

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-12 text-black opacity-50">
        <Loader2 size={36} className="animate-spin mb-3" strokeWidth={1.5} />
        <span className="text-[10px] font-black tracking-widest">Loading Latest Summary...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-50 text-red-600 p-6 border-2 border-red-600 font-bold text-sm shadow-[4px_4px_0px_0px_rgba(220,38,38,0.1)]">
          <div className="font-black tracking-widest text-[10px] mb-2">Error Loading Summary</div>
          {error}
        </div>
      </div>
    );
  }

  if (summaries.length === 0 || !content) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-12 text-center text-gray-400">
        <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mb-4 border-2 border-dashed border-gray-300 animate-pulse">
          <BookOpen size={24} className="text-gray-400" />
        </div>
        <h4 className="font-black text-black text-xs tracking-widest mb-1">No Summary Available</h4>
        <p className="text-xs text-gray-500 max-w-sm leading-relaxed">
          Research summaries will be generated by the next "Summarize Research" step
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Main Scrollable Content */}
      <div className="flex-1 overflow-y-auto p-6 md:p-8 custom-scrollbar">
        <div className="prose prose-sm max-w-none md:max-w-4xl prose-img:border-2 prose-img:border-black prose-img:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] prose-pre:border-2 prose-pre:border-black prose-pre:rounded-none prose-pre:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] prose-headings:font-black">
          <MemoizedMarkdown
            content={processedContent}
            remarkPlugins={remarkPlugins}
            rehypePlugins={rehypePlugins}
            components={markdownComponents}
          />
        </div>
      </div>
    </div>
  );
}
