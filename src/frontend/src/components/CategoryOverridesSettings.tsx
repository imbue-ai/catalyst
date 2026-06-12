import React, { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import * as api from '../api'
import { HarnessSettings } from './HarnessSettings'

interface CategoryOverridesSettingsProps {
  overrides: Record<api.StepCategory, api.AgentSettings>;
  onChange: (overrides: Record<api.StepCategory, api.AgentSettings>) => void;
  harnesses: api.HarnessInfo[];
  scrollContainerRef?: React.RefObject<HTMLDivElement | null>;
  collapsible?: boolean;
  forceVertical?: boolean;
}

export function CategoryOverridesSettings({
  overrides,
  onChange,
  harnesses,
  scrollContainerRef,
  collapsible = true,
  forceVertical = false,
}: CategoryOverridesSettingsProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [expandedCategories, setExpandedCategories] = useState<Record<api.StepCategory, boolean>>({} as any)

  const toggleCategory = (category: api.StepCategory) => {
    setExpandedCategories(prev => ({
      ...prev,
      [category]: !prev[category],
    }))
  }

  const handleOverrideChange = (category: api.StepCategory, updates: { framework?: string; model?: string; effort?: string }) => {
    const current = overrides[category] || {}
    const updated = {
      ...current,
      ...updates,
    }
    onChange({
      ...overrides,
      [category]: updated,
    })
  }

  const getCategorySummary = (override: api.AgentSettings) => {
    if (!override.framework && !override.model && !override.effort) {
      return 'Default'
    }
    const parts: string[] = []
    if (override.framework) {
      const displayFramework = harnesses.find(h => h.name === override.framework)?.display_name || override.framework
      parts.push(displayFramework)
    }
    if (override.model) {
      parts.push(override.model)
    }
    if (override.effort) {
      parts.push(`Effort: ${override.effort.charAt(0).toUpperCase() + override.effort.slice(1)}`)
    }
    return parts.join(' • ')
  }

  const renderContent = () => (
    <div className="flex flex-col gap-3">
      {api.STEP_CATEGORIES.map(category => {
        const override = overrides[category] || {}
        const isExpanded = !!expandedCategories[category]
        const summary = getCategorySummary(override)
        const hasOverride = summary !== 'Default'

        return (
          <div key={category} className="border border-black p-3 bg-white hover:bg-gray-50/50 transition-colors">
            {/* Collapsible Category Header Button */}
            <button
              type="button"
              onClick={() => toggleCategory(category)}
              className="w-full flex items-center justify-between text-left select-none cursor-pointer group"
            >
              <div className="flex flex-col gap-0.5">
                <span className="text-[11px] font-black text-black group-hover:text-gray-700 transition-colors">
                  {api.STEP_CATEGORY_LABELS[category]}
                </span>
                <span className={`text-[9px] font-bold ${hasOverride ? 'text-blue-600' : 'text-gray-400'}`}>
                  {summary}
                </span>
              </div>
              <div className="text-black/40 group-hover:text-black transition-colors">
                {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </div>
            </button>

            {/* Collapsible Harness Settings Panel */}
            {isExpanded && (
              <div className="mt-3 pt-3 border-t border-dashed border-black/10">
                <HarnessSettings
                  framework={override.framework || ''}
                  model={override.model || ''}
                  effort={override.effort || ''}
                  harnesses={harnesses}
                  onChange={(updates) => {
                    const frameworkVal = updates.framework !== undefined ? updates.framework : (override.framework || '')
                    const modelVal = updates.model !== undefined ? updates.model : (override.model || '')
                    const effortVal = updates.effort !== undefined ? updates.effort : (override.effort || '')
                    handleOverrideChange(category, {
                      framework: frameworkVal,
                      model: modelVal,
                      effort: effortVal,
                    })
                  }}
                  isCompact={true}
                  scrollContainerRef={scrollContainerRef}
                  allowDefaultFramework={true}
                  forceVertical={forceVertical}
                />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )

  if (!collapsible) {
    return (
      <div className="col-span-full border-t border-dashed border-gray-200 pt-6 mt-2">
        <h4 className="text-xs font-black tracking-widest text-black mb-4">
          Step Type Model Overrides
        </h4>
        {renderContent()}
      </div>
    )
  }

  return (
    <div className="col-span-full border-t border-dashed border-gray-200 pt-6 mt-2">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-[10px] font-black tracking-widest hover:text-gray-500 transition-colors group mb-4"
      >
        <span>Step Type Model Overrides</span>
        {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>

      {isOpen && (
        <div className="border-2 border-dashed border-gray-200 p-6 mt-2">
          {renderContent()}
        </div>
      )}
    </div>
  )
}
