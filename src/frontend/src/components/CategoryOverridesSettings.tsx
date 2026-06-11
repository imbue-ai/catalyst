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

  const renderContent = () => (
    <div className="flex flex-col gap-6">
      {api.STEP_CATEGORIES.map(category => {
        const override = overrides[category] || {}
        const rowClass = forceVertical
          ? "flex flex-col gap-3 pb-6 border-b border-gray-200 last:border-0 last:pb-0"
          : "flex flex-col md:flex-row md:items-center gap-4 pb-4 border-b border-gray-200 last:border-0 last:pb-0"
        const labelClass = forceVertical
          ? "shrink-0 pb-1"
          : "md:w-1/4 shrink-0 pt-1"

        return (
          <div key={category} className={rowClass}>
            {/* Left Column: Category Label */}
            <div className={labelClass}>
              <span className="text-xs font-black text-black">
                {api.STEP_CATEGORY_LABELS[category]}
              </span>
            </div>
            {/* Right Column: Harness Settings */}
            <div className="flex-1">
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
