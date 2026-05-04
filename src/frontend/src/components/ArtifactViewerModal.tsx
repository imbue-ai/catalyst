import { useEffect, useState, useMemo } from 'react';
import { createPortal } from 'react-dom';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import rehypeSlug from 'rehype-slug';
import GithubSlugger from 'github-slugger';
import 'katex/dist/katex.min.css';
import { X, Loader2, Printer, List as ListIcon, ArrowLeft, Download } from 'lucide-react';
import * as api from '../api';

interface ArtifactViewerModalProps {
  taskId: string;
  artifactId: string;
  onClose: () => void;
}

interface TocEntry {
  id: string;
  text: string;
  level: number;
}

export function ArtifactViewerModal({ taskId, artifactId, onClose }: ArtifactViewerModalProps) {
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchContent = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`${api.API_BASE_URL}/api/tasks/${taskId}/artifacts/${artifactId}/primary`);
        if (!response.ok) {
          throw new Error('Failed to fetch artifact content');
        }
        const data = await response.json();
        setContent(data.content);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchContent();
  }, [taskId, artifactId]);

  const handleExport = async () => {
    setExporting(true);
    try {
      await api.exportArtifact(taskId, artifactId);
    } catch (err: any) {
      alert(err.message || 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  // Prevent background scrolling when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = 'auto';
    };
  }, []);

  const processContent = (text: string) => {
    // Ensure display math blocks ($$ ... $$) are robustly handled.
    // remark-math v6+ requires delimiters to be on their own lines for block math.
    // This transforms $$math$$ -> $$\nmath\n$$ and also ensures blank lines around it.
    const withNewlines = text.replace(/\$\$(.*?)\$\$/gs, (_, content) => {
      return `\n\n$$\n${content.trim()}\n$$\n\n`;
    });

    const parts = withNewlines.split(/(```[\s\S]*?```|`[^`]+`|\$\$[\s\S]*?\$\$)/g);
    return parts.map((part, i) => {
      if (i % 2 === 0) {
        return part.replace(/\b([ELTRXP]_\d{8}_\d{6}_[a-f0-9]{6})\b/g, `[$1](#/task/${taskId}/artifact/$1?from=artifact)`);
      } else {
        const match = part.match(/^`([ELTRXP]_\d{8}_\d{6}_[a-f0-9]{6})`$/);
        if (match) {
          return `[${part}](#/task/${taskId}/artifact/${match[1]}?from=artifact)`;
        }
        return part;
      }
    }).join('');
  };

  const toc = useMemo(() => {
    if (!content) return [];

    const slugger = new GithubSlugger();
    const lines = content.split('\n');
    const entries: TocEntry[] = [];

    // basic regex to find markdown headings. Note this doesn't handle code blocks perfectly but works for most standard use cases.
    const headingRegex = /^(#{1,4})\s+(.+)$/;

    let inCodeBlock = false;
    for (const line of lines) {
      if (line.startsWith('```')) {
        inCodeBlock = !inCodeBlock;
        continue;
      }

      if (!inCodeBlock) {
        const match = line.match(headingRegex);
        if (match) {
          const level = match[1].length;
          // Strip basic markdown formatting from heading text for the ToC
          let text = match[2].replace(/[*_~`]/g, '');
          entries.push({
            id: slugger.slug(text),
            text: text.trim(),
            level
          });
        }
      }
    }

    return entries;
  }, [content]);

  const scrollToHeading = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const hasPreviousArtifact = window.location.hash.includes('from=artifact');

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 sm:p-8 print:static print:bg-transparent print:p-0 print:block" onClick={onClose}>
      <div
        className="bg-white w-full h-full max-w-7xl rounded-sm border-2 border-black shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] flex flex-col overflow-hidden print:border-none print:shadow-none print:max-w-none print:overflow-visible print:h-auto print:block print:w-full"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b-2 border-black bg-gray-50 print:hidden">
          <div className="flex items-center gap-3">
            {hasPreviousArtifact && (
              <button
                onClick={() => window.history.back()}
                className="p-1 hover:bg-gray-200 rounded transition-colors"
                title="Go Back"
              >
                <ArrowLeft size={20} strokeWidth={3} />
              </button>
            )}
            <span className="font-black text-sm tracking-widest">{artifactId}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleExport}
              disabled={exporting || loading}
              className="p-1 hover:bg-gray-200 rounded transition-colors disabled:opacity-50"
              title="Export as ZIP"
            >
              {exporting ? <Loader2 size={20} strokeWidth={3} className="animate-spin" /> : <Download size={20} strokeWidth={3} />}
            </button>
            <button
              onClick={() => window.print()}
              className="p-1 hover:bg-gray-200 rounded transition-colors"
              title="Print Artifact"
            >
              <Printer size={20} strokeWidth={3} />
            </button>
            <button
              onClick={onClose}
              className="p-1 hover:bg-gray-200 rounded transition-colors"
            >
              <X size={20} strokeWidth={3} />
            </button>
          </div>
        </div>

        <div className="flex-1 flex overflow-hidden print:block print:overflow-visible">
          {/* Table of Contents Sidebar */}
          {toc.length > 0 && !loading && !error && (
            <div className="w-64 border-r-2 border-black bg-gray-50 flex flex-col print:hidden flex-shrink-0">
              <div className="p-4 border-b-2 border-black flex items-center gap-2">
                <ListIcon size={16} />
                <span className="font-black text-xs tracking-widest">Contents</span>
              </div>
              <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                <ul className="space-y-2">
                  {toc.map((entry, idx) => (
                    <li
                      key={`${entry.id}-${idx}`}
                      style={{ paddingLeft: `${(entry.level - 1) * 0.75}rem` }}
                    >
                      <button
                        onClick={() => scrollToHeading(entry.id)}
                        className="text-left w-full text-sm font-bold text-gray-600 hover:text-black hover:underline truncate"
                        title={entry.text}
                      >
                        {entry.text}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Main Content Area */}
          <div className="flex-1 overflow-y-auto p-6 md:p-10 custom-scrollbar bg-white print:overflow-visible print:p-0 relative">
            {loading && (
              <div className="flex flex-col items-center justify-center h-full opacity-50 text-black">
                <Loader2 size={48} className="animate-spin mb-4" strokeWidth={1} />
                <div className="font-black text-xs tracking-widest">Loading Artifact...</div>
              </div>
            )}
            {error && (
              <div className="bg-red-50 text-red-600 p-6 border-2 border-red-600 font-bold text-sm">
                Error: {error}
              </div>
            )}
            {!loading && !error && content && (
              <div className="prose prose-sm md:prose-base max-w-none md:max-w-4xl lg:max-w-5xl mx-auto prose-img:border-2 prose-img:border-black prose-img:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] prose-pre:border-2 prose-pre:border-black prose-pre:rounded-none prose-pre:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] prose-headings:font-black">
                <ReactMarkdown
                  remarkPlugins={[remarkMath, remarkGfm]}
                  rehypePlugins={[rehypeSlug, [rehypeKatex, { strict: 'ignore' }]]}
                  components={{
                    img({ node, src, alt, className, ...props }) {
                      const combinedClassName = className ? `${className} print:break-inside-avoid` : 'print:break-inside-avoid';
                      const imgStyle = { pageBreakInside: 'avoid', breakInside: 'avoid' } as React.CSSProperties;
                      const wrapperStyle = { display: 'inline-block', pageBreakInside: 'avoid', breakInside: 'avoid', width: '100%' } as React.CSSProperties;
                      
                      let resolvedSrc = src;
                      if (src && !src.startsWith('http') && !src.startsWith('data:')) {
                        // rewrite local relative paths to our files endpoint
                        resolvedSrc = `${api.API_BASE_URL}/api/tasks/${taskId}/artifacts/${artifactId}/files/${src.replace(/^\.\//, '')}`;
                      }

                      return (
                        <span className="print:break-inside-avoid" style={wrapperStyle}>
                          <img src={resolvedSrc} alt={alt} className={combinedClassName} style={imgStyle} {...props} />
                        </span>
                      );
                    },
                    pre({ node, className, children, ...props }) {
                      const wrapperStyle = { display: 'inline-block', pageBreakInside: 'avoid', breakInside: 'avoid', width: '100%' } as React.CSSProperties;
                      return (
                        <div className="print:break-inside-avoid" style={wrapperStyle}>
                          <pre className={className} {...props}>{children}</pre>
                        </div>
                      );
                    },
                    div({ node, className, children, ...props }) {
                      if (className && (className.includes('math-display') || className.includes('katex-display'))) {
                        const wrapperStyle = { display: 'inline-block', pageBreakInside: 'avoid', breakInside: 'avoid', width: '100%' } as React.CSSProperties;
                        const combinedClassName = `${className} print:break-inside-avoid`;
                        return <div className={combinedClassName} style={wrapperStyle} {...props}>{children}</div>;
                      }
                      return <div className={className} {...props}>{children}</div>;
                    },
                    span({ node, className, children, ...props }) {
                      if (className && (className.includes('math-display') || className.includes('katex-display'))) {
                        const wrapperStyle = { display: 'inline-block', pageBreakInside: 'avoid', breakInside: 'avoid', width: '100%' } as React.CSSProperties;
                        const combinedClassName = `${className} print:break-inside-avoid`;
                        return <span className={combinedClassName} style={wrapperStyle} {...props}>{children}</span>;
                      }
                      return <span className={className} {...props}>{children}</span>;
                    }
                  }}
                >
                  {processContent(content)}
                </ReactMarkdown>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
