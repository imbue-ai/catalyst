import React from 'react';

interface DataSectionProps {
  label: string;
  data: any;
  primary?: boolean;
  taskId?: string;
}

const ARTIFACT_REGEX = /^[ELTRXP]_\d{8}_\d{6}_[a-f0-9]{6}$/;

function renderJsonValue(val: any, taskId?: string): React.ReactNode {
  if (typeof val === 'string') {
    if (ARTIFACT_REGEX.test(val) && taskId) {
      return (
        <a 
          href={`#/task/${taskId}/artifact/${val}`}
          className="text-blue-600 font-black hover:underline cursor-pointer bg-blue-50 px-1 py-0.5 rounded-sm inline-block"
        >
          {val}
        </a>
      );
    }
    return <span className="text-green-700">"{val}"</span>;
  }
  if (typeof val === 'number' || typeof val === 'boolean') {
    return <span className="text-blue-500">{String(val)}</span>;
  }
  if (val === null) {
    return <span className="text-gray-400 font-bold">null</span>;
  }
  if (Array.isArray(val)) {
    if (val.length === 0) return <span>[]</span>;
    return (
      <div className="pl-4 border-l border-gray-200 ml-2">
        <span className="text-gray-500">[</span>
        <div className="pl-2">
          {val.map((item, idx) => (
            <div key={idx} className="flex">
              {renderJsonValue(item, taskId)}
              {idx < val.length - 1 && <span className="text-gray-400">,</span>}
            </div>
          ))}
        </div>
        <span className="text-gray-500">]</span>
      </div>
    );
  }
  if (typeof val === 'object') {
    const keys = Object.keys(val);
    if (keys.length === 0) return <span>{}</span>;
    return (
      <div className="pl-4 border-l border-gray-200 ml-2">
        <span className="text-gray-500">{'{'}</span>
        <div className="pl-2">
          {keys.map((k, idx) => (
            <div key={k} className="flex">
              <span className="text-gray-800 font-bold mr-2">"{k}":</span>
              {renderJsonValue(val[k], taskId)}
              {idx < keys.length - 1 && <span className="text-gray-400">,</span>}
            </div>
          ))}
        </div>
        <span className="text-gray-500">{'}'}</span>
      </div>
    );
  }
  return <span>{String(val)}</span>;
}

export function DataSection({ label, data, primary, taskId }: DataSectionProps) {
  const isPromptOnly = data && typeof data === 'object' && 'prompt' in data && Object.keys(data).length === 1;

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <div className={`w-1.5 h-1.5 rounded-full ${primary ? 'bg-black' : 'bg-gray-300'}`} />
        <h4 className="text-[10px] font-black uppercase tracking-widest text-gray-500">{label}</h4>
      </div>
      <div className={`border p-4 bg-white overflow-x-auto ${primary ? 'border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,0.05)]' : 'border-gray-100'}`}>
        {isPromptOnly ? (
          <div className="text-xs font-bold whitespace-pre-wrap leading-relaxed text-gray-700 bg-gray-50 p-4 border-l-4 border-black">
            {data.prompt}
          </div>
        ) : (
          <div className="text-[10px] leading-relaxed whitespace-pre-wrap font-mono">
            {renderJsonValue(data, taskId)}
          </div>
        )}
      </div>
    </div>
  )
}
