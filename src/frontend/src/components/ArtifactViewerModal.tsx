import { useEffect, useState, useMemo, memo } from 'react';
import { createPortal } from 'react-dom';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import rehypeSlug from 'rehype-slug';
import GithubSlugger from 'github-slugger';
import 'katex/dist/katex.min.css';
import { X, Loader2, Printer, List as ListIcon, ArrowLeft, Download, FileCode, FileText, Image as ImageIcon } from 'lucide-react';
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

  const [files, setFiles] = useState<string[]>([]);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [hash, setHash] = useState(window.location.hash);

  useEffect(() => {
    const handler = () => setHash(window.location.hash);
    window.addEventListener('hashchange', handler);
    return () => window.removeEventListener('hashchange', handler);
  }, []);

  const hashParams = useMemo(() => new URLSearchParams(hash.split('?')[1] || ''), [hash]);
  const selectedFile = hashParams.get('file');

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

    const fetchFiles = async () => {
      try {
        const fileList = await api.listArtifactFiles(taskId, artifactId);
        setFiles(fileList);
      } catch (err) {
        console.error('Failed to fetch files:', err);
      }
    };

    fetchContent();
    fetchFiles();
  }, [taskId, artifactId]);

  useEffect(() => {
    if (selectedFile && !['png', 'jpg', 'gif'].some(ext => selectedFile.toLowerCase().endsWith(ext))) {
      const fetchFileContent = async () => {
        setFileLoading(true);
        setFileContent(null);
        try {
          const response = await fetch(`${api.API_BASE_URL}/api/tasks/${taskId}/artifacts/${artifactId}/files/${selectedFile}`);
          if (!response.ok) throw new Error('Failed to fetch file content');
          const text = await response.text();
          setFileContent(text);
        } catch (err) {
          console.error(err);
          setFileContent('Failed to load file content.');
        } finally {
          setFileLoading(false);
        }
      };
      fetchFileContent();
    } else {
      setFileContent(null);
    }
  }, [taskId, artifactId, selectedFile]);

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

  const processedContent = useMemo(() => {
    if (!content) return '';
    
    // Ensure display math blocks ($$ ... $$) are robustly handled.
    // remark-math v6+ requires delimiters to be on their own lines for block math.
    // This transforms $$math$$ -> $$\nmath\n$$ and also ensures blank lines around it.
    const withNewlines = content.replace(/\$\$(.*?)\$\$/gs, (_, mathContent) => {
      return `\n\n$$\n${mathContent.trim()}\n$$\n\n`;
    });

    const parts = withNewlines.split(/(```[\s\S]*?```|`[^`]+`|\$\$[\s\S]*?\$\$)/g);
    return parts.map((part, i) => {
      if (i % 2 === 0) {
        return part.replace(/\b([ELTRXPS]_\d{8}_\d{6}_[a-f0-9]{6})\b/g, `[$1](#/task/${taskId}/artifact/$1?from=artifact)`);
      } else {
        const match = part.match(/^`([ELTRXPS]_\d{8}_\d{6}_[a-f0-9]{6})`$/);
        if (match) {
          return `[${part}](#/task/${taskId}/artifact/${match[1]}?from=artifact)`;
        }
        return part;
      }
    }).join('');
  }, [content, taskId]);

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

  const filteredFiles = useMemo(() => {
    const allowedExtensions = ['.png', '.jpg', '.gif', '.py', '.log', '.txt', '.csv', '.json', '.jsonl'];
    return files.filter(f => {
      const lower = f.toLowerCase();
      return f !== 'metadata.json' && allowedExtensions.some(ext => lower.endsWith(ext));
    });
  }, [files]);

  const scrollToHeading = (id: string) => {
    if (selectedFile) {
      const [base, queryStr] = window.location.hash.split('?');
      const params = new URLSearchParams(queryStr || '');
      params.delete('file');
      window.location.hash = params.toString() ? `${base}?${params.toString()}` : base;
      // Slight delay to allow markdown to render before scrolling
      setTimeout(() => {
        const element = document.getElementById(id);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth' });
        }
      }, 0);
    } else {
      const element = document.getElementById(id);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth' });
      }
    }
  };

  const hasPreviousArtifact = window.location.hash.includes('from=artifact');

  const markdownComponents = useMemo(() => ({
    img({ node, src, alt, className, ...props }: any) {
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
    pre({ node, className, children, ...props }: any) {
      const wrapperStyle = { display: 'inline-block', pageBreakInside: 'avoid', breakInside: 'avoid', width: '100%' } as React.CSSProperties;
      return (
        <div className="print:break-inside-avoid" style={wrapperStyle}>
          <pre className={className} {...props}>{children}</pre>
        </div>
      );
    },
    div({ node, className, children, ...props }: any) {
      if (className && (className.includes('math-display') || className.includes('katex-display'))) {
        const wrapperStyle = { display: 'inline-block', pageBreakInside: 'avoid', breakInside: 'avoid', width: '100%' } as React.CSSProperties;
        const combinedClassName = `${className} print:break-inside-avoid`;
        return <div className={combinedClassName} style={wrapperStyle} {...props}>{children}</div>;
      }
      return <div className={className} {...props}>{children}</div>;
    },
    span({ node, className, children, ...props }: any) {
      if (className && (className.includes('math-display') || className.includes('katex-display'))) {
        const wrapperStyle = { display: 'inline-block', pageBreakInside: 'avoid', breakInside: 'avoid', width: '100%' } as React.CSSProperties;
        const combinedClassName = `${className} print:break-inside-avoid`;
        return <span className={combinedClassName} style={wrapperStyle} {...props}>{children}</span>;
      }
      return <span className={className} {...props}>{children}</span>;
    }
  }), [taskId, artifactId]);

  const remarkPlugins = useMemo(() => [remarkMath, remarkGfm], []);
  const rehypePlugins = useMemo(() => [rehypeSlug, [rehypeKatex, { strict: 'ignore' }]], []);

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 sm:p-8 print:static print:bg-transparent print:p-0 print:block" onClick={onClose}>
      <div
        className="bg-white w-full h-full max-w-7xl rounded-sm border-2 border-black shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] flex flex-col overflow-hidden print:border-none print:shadow-none print:max-w-none print:overflow-visible print:h-auto print:block print:w-full"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b-2 border-black bg-gray-50 print:hidden">
          <div className="flex items-center gap-3">
            {(hasPreviousArtifact || selectedFile) && (
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
          {/* Sidebar */}
          {(toc.length > 0 || filteredFiles.length > 0) && !loading && !error && (
            <div className="w-64 border-r-2 border-black bg-gray-50 flex flex-col print:hidden flex-shrink-0">
              {/* Table of Contents */}
              {toc.length > 0 && (
                <div className={`${filteredFiles.length > 0 ? 'h-2/3 border-b-2 border-black' : 'h-full'} flex flex-col overflow-hidden`}>
                  <div className="p-4 border-b-2 border-black flex items-center gap-2 flex-shrink-0">
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

              {/* Files Section */}
              {filteredFiles.length > 0 && (
                <div className={`${toc.length > 0 ? 'h-1/3' : 'h-full'} flex flex-col overflow-hidden`}>
                  <div className="p-4 border-b-2 border-black flex items-center gap-2 flex-shrink-0">
                    <FileCode size={16} />
                    <span className="font-black text-xs tracking-widest">Files</span>
                  </div>
                  <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                    <ul className="space-y-1">
                      {filteredFiles.map((file, idx) => {
                        const isSelected = selectedFile === file;
                        const isImage = ['.png', '.jpg', '.gif'].some(ext => file.toLowerCase().endsWith(ext));
                        const isCode = file.toLowerCase().endsWith('.py');
                        
                        return (
                          <li key={`${file}-${idx}`}>
                            <button
                              onClick={() => {
                                const [base, queryStr] = window.location.hash.split('?');
                                const params = new URLSearchParams(queryStr || '');
                                params.set('file', file);
                                window.location.hash = `${base}?${params.toString()}`;
                              }}
                              className={`text-left w-full text-[11px] font-bold p-1.5 flex items-center gap-2 border border-transparent transition-all hover:bg-white hover:border-black ${isSelected ? 'bg-white border-black text-black' : 'text-gray-500'}`}
                              title={file}
                            >
                              {isImage ? <ImageIcon size={12} className="shrink-0" /> : isCode ? <FileCode size={12} className="shrink-0" /> : <FileText size={12} className="shrink-0" />}
                              <span className="truncate w-full" style={{ direction: 'rtl', textAlign: 'left' }}>
                                <bdi>{file}</bdi>
                              </span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Main Content Area */}
          <div className="flex-1 overflow-y-auto p-6 md:p-10 custom-scrollbar bg-white print:overflow-visible print:p-0 relative">
            {(loading || (selectedFile && fileLoading)) && (
              <div className="flex flex-col items-center justify-center h-full opacity-50 text-black">
                <Loader2 size={48} className="animate-spin mb-4" strokeWidth={1} />
                <div className="font-black text-xs tracking-widest">{fileLoading ? 'Loading File...' : 'Loading Artifact...'}</div>
              </div>
            )}
            {error && (
              <div className="bg-red-50 text-red-600 p-6 border-2 border-red-600 font-bold text-sm">
                Error: {error}
              </div>
            )}
            {!loading && !error && selectedFile && !fileLoading && (
              <div className="max-w-none md:max-w-4xl lg:max-w-5xl mx-auto">
                {['png', 'jpg', 'gif'].some(ext => selectedFile.toLowerCase().endsWith(ext)) ? (
                  <div className="border-2 border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] bg-white p-4">
                    <img
                      src={`${api.API_BASE_URL}/api/tasks/${taskId}/artifacts/${artifactId}/files/${selectedFile}`}
                      alt={selectedFile}
                      className="max-w-full h-auto mx-auto"
                    />
                  </div>
                ) : (
                  <div className="border-2 border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] bg-gray-50 overflow-hidden">
                    <div className="px-4 py-2 border-b-2 border-black bg-white flex justify-between items-center">
                      <span className="font-mono text-xs font-bold">{selectedFile}</span>
                    </div>
                    <pre className="p-4 font-mono text-[11px] leading-relaxed whitespace-pre-wrap overflow-x-auto text-gray-800">
                      <code>{fileContent}</code>
                    </pre>
                  </div>
                )}
              </div>
            )}
            {!loading && !error && !selectedFile && content && (
              <div className="prose prose-sm md:prose-base max-w-none md:max-w-4xl lg:max-w-5xl mx-auto prose-img:border-2 prose-img:border-black prose-img:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] prose-pre:border-2 prose-pre:border-black prose-pre:rounded-none prose-pre:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] prose-headings:font-black">
                <MemoizedMarkdown
                  content={processedContent}
                  remarkPlugins={remarkPlugins}
                  rehypePlugins={rehypePlugins}
                  components={markdownComponents}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
