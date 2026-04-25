interface DataSectionProps {
  label: string;
  data: any;
  primary?: boolean;
}

export function DataSection({ label, data, primary }: DataSectionProps) {
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
          <pre className="text-[10px] leading-relaxed whitespace-pre-wrap">
            {JSON.stringify(data, null, 2)}
          </pre>
        )}
      </div>
    </div>
  )
}
