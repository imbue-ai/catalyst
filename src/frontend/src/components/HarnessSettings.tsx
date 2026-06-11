import { useState, useRef, useEffect } from 'react'
import { Cpu, ChevronDown, HelpCircle } from 'lucide-react'
import * as api from '../api'

interface HarnessSettingsProps {
  framework: string;
  model: string;
  effort: string;
  harnesses: api.HarnessInfo[];
  onChange: (updates: { framework?: string; model?: string; effort?: string }) => void;
  isCompact?: boolean;
}

export function HarnessSettings({
  framework,
  model,
  effort,
  harnesses,
  onChange,
  isCompact = false,
}: HarnessSettingsProps) {
  const [showFrameworkDropdown, setShowFrameworkDropdown] = useState(false)
  const [showModelDropdown, setShowModelDropdown] = useState(false)
  const [showEffortDropdown, setShowEffortDropdown] = useState(false)

  const frameworkDropdownRef = useRef<HTMLDivElement>(null)
  const modelDropdownRef = useRef<HTMLDivElement>(null)
  const effortDropdownRef = useRef<HTMLDivElement>(null)

  // Click outside listener for self-contained dropdown controls
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (frameworkDropdownRef.current && !frameworkDropdownRef.current.contains(event.target as Node)) {
        setShowFrameworkDropdown(false)
      }
      if (modelDropdownRef.current && !modelDropdownRef.current.contains(event.target as Node)) {
        setShowModelDropdown(false)
      }
      if (effortDropdownRef.current && !effortDropdownRef.current.contains(event.target as Node)) {
        setShowEffortDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const formatEffortLabel = (effortVal: string) => {
    return effortVal.charAt(0).toUpperCase() + effortVal.slice(1)
  }

  const selectedHarness = harnesses.find(h => h.name === framework)
  const effortOptions = selectedHarness?.effort_options
  const hasEffort = !!(effortOptions && effortOptions.length > 0)
  const harnessModels = selectedHarness?.models || []

  // Define dynamic CSS classes based on the isCompact layout mode
  const labelClass = isCompact
    ? 'block text-[10px] font-black mb-1.5 tracking-widest text-gray-400'
    : 'block text-[10px] font-black mb-3 tracking-widest text-gray-400'

  const containerClass = isCompact
    ? 'flex items-center gap-2 border border-black p-2 bg-white relative'
    : 'flex items-center gap-3 border-2 border-black p-3 focus-within:bg-gray-50 transition-colors relative'

  const dropdownMenuClass = isCompact
    ? 'absolute left-0 right-0 top-full mt-1 bg-white border border-black z-50 overflow-visible shadow-[4px_4px_0px_0px_rgba(0,0,0,0.1)]'
    : 'absolute left-0 right-0 top-full mt-2 bg-white border-2 border-black shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] z-50 overflow-visible'

  const dropdownItemClass = isCompact
    ? 'w-full flex justify-between items-center px-3 py-2 text-xs font-bold border-b border-gray-100 last:border-0 relative group/item transition-colors bg-white'
    : 'w-full flex justify-between items-center px-4 py-3 text-xs font-bold border-b border-gray-100 last:border-0 relative group/item transition-colors bg-white'

  const textClass = isCompact ? 'text-xs font-bold' : 'text-sm font-bold'
  const iconSize = isCompact ? 14 : 18
  const chevronSize = isCompact ? 12 : 14

  // Premium, context-aware tooltip positioning to prevent viewport overflow
  const tooltipClass = isCompact
    ? 'absolute right-full top-0 mr-2 w-64 p-3 bg-black text-white text-[10px] leading-relaxed hidden group-hover/item:block z-50 normal-case font-bold shadow-[4px_4px_0px_0px_rgba(0,0,0,0.2)]'
    : 'absolute left-full top-0 ml-2 w-64 p-3 bg-black text-white text-[10px] leading-relaxed hidden group-hover/item:block z-50 normal-case font-bold shadow-[4px_4px_0px_0px_rgba(0,0,0,0.2)]'

  const tooltipArrowClass = isCompact
    ? 'absolute top-3 left-full border-4 border-transparent border-l-black'
    : 'absolute top-3 right-full border-4 border-transparent border-r-black'

  return (
    <div className={isCompact ? 'space-y-4' : `grid grid-cols-1 md:grid-cols-${hasEffort ? '3' : '2'} gap-6`}>
      {/* Agent Framework Dropdown */}
      <div>
        <label className={labelClass}>Agent Framework</label>
        <div className={containerClass} ref={frameworkDropdownRef}>
          <Cpu size={iconSize} className="text-black shrink-0" />
          <div
            className={`w-full bg-transparent select-none cursor-pointer ${textClass}`}
            onClick={() => setShowFrameworkDropdown(!showFrameworkDropdown)}
          >
            {selectedHarness?.display_name || framework}
          </div>
          <button
            type="button"
            onClick={() => setShowFrameworkDropdown(!showFrameworkDropdown)}
            className="hover:text-gray-500 transition-colors shrink-0"
          >
            <ChevronDown size={chevronSize} className={`transition-transform ${showFrameworkDropdown ? 'rotate-180' : ''}`} />
          </button>

          {showFrameworkDropdown && (
            <div className={dropdownMenuClass}>
              {harnesses.map(h => (
                <div
                  key={h.name}
                  className={`${dropdownItemClass} ${h.available
                    ? 'hover:bg-black hover:text-white cursor-pointer text-black bg-white'
                    : 'bg-gray-50 text-gray-400 cursor-not-allowed'
                    }`}
                  onClick={() => {
                    if (h.available) {
                      onChange({ framework: h.name, model: '', effort: '' })
                      setShowFrameworkDropdown(false)
                    }
                  }}
                >
                  <span>{h.display_name}</span>
                  {!h.available && (
                    <div className="flex items-center gap-1.5 shrink-0">
                      <HelpCircle size={14} className="text-gray-400 group-hover/item:text-gray-600" />
                      {h.help_message && (
                        <div className={tooltipClass}>
                          {h.help_message}
                          <div className={tooltipArrowClass}></div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Model Identifier input & optional dropdown */}
      <div>
        <label className={labelClass}>Model Identifier</label>
        <div className={containerClass} ref={modelDropdownRef}>
          <Cpu size={iconSize} className="text-black shrink-0" />
          <input
            value={model}
            onChange={e => onChange({ model: e.target.value })}
            placeholder="Default"
            className={`w-full outline-none bg-transparent ${textClass}`}
          />
          {harnessModels.length > 0 && (
            <button
              type="button"
              onClick={() => setShowModelDropdown(!showModelDropdown)}
              className="hover:text-gray-500 transition-colors shrink-0"
            >
              <ChevronDown size={chevronSize} className={`transition-transform ${showModelDropdown ? 'rotate-180' : ''}`} />
            </button>
          )}

          {showModelDropdown && harnessModels.length > 0 && (
            <div className={dropdownMenuClass}>
              <button
                type="button"
                onClick={() => {
                  onChange({ model: '' })
                  setShowModelDropdown(false)
                }}
                className="w-full text-left px-4 py-3 text-xs font-bold hover:bg-black hover:text-white transition-colors border-b border-gray-100 uppercase tracking-widest bg-white"
              >
                Default
              </button>
              {harnessModels.map(m => (
                <button
                  key={m}
                  type="button"
                  onClick={() => {
                    onChange({ model: m })
                    setShowModelDropdown(false)
                  }}
                  className="w-full text-left px-4 py-3 text-xs font-bold hover:bg-black hover:text-white transition-colors border-b border-gray-100 last:border-0 bg-white"
                >
                  {m}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Reasoning Effort Dropdown */}
      {hasEffort && effortOptions && (
        <div>
          <label className={labelClass}>Reasoning Effort</label>
          <div className={containerClass} ref={effortDropdownRef}>
            <Cpu size={iconSize} className="text-black shrink-0" />
            <div
              className={`w-full bg-transparent select-none cursor-pointer ${textClass}`}
              onClick={() => setShowEffortDropdown(!showEffortDropdown)}
            >
              {effort ? formatEffortLabel(effort) : 'Default'}
            </div>
            <button
              type="button"
              onClick={() => setShowEffortDropdown(!showEffortDropdown)}
              className="hover:text-gray-500 transition-colors shrink-0"
            >
              <ChevronDown size={chevronSize} className={`transition-transform ${showEffortDropdown ? 'rotate-180' : ''}`} />
            </button>

            {showEffortDropdown && (
              <div className={dropdownMenuClass}>
                <button
                  type="button"
                  onClick={() => {
                    onChange({ effort: '' })
                    setShowEffortDropdown(false)
                  }}
                  className="w-full text-left px-4 py-3 text-xs font-bold hover:bg-black hover:text-white transition-colors border-b border-gray-100 uppercase tracking-widest bg-white"
                >
                  Default
                </button>
                {effortOptions.map(opt => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => {
                      onChange({ effort: opt })
                      setShowEffortDropdown(false)
                    }}
                    className="w-full text-left px-4 py-3 text-xs font-bold hover:bg-black hover:text-white transition-colors border-b border-gray-100 last:border-0 bg-white"
                  >
                    {formatEffortLabel(opt)}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
