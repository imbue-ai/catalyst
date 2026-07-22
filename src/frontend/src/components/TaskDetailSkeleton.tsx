/**
 * TaskDetailSkeleton renders a layout-preserving wireframe during task loading.
 *
 * IMPORTANT: This component MUST structurally mirror TaskDetail.tsx (its margins, padding,
 * columns, headers, and grid dimensions) to prevent jarring layout shift/flickering.
 * If you update TaskDetail.tsx, make sure to update this file in sync!
 */
import { Folder, Cpu, Workflow } from 'lucide-react'

export function TaskDetailSkeleton() {
  return (
    <div className="flex-1 flex flex-col min-h-0 bg-white animate-pulse">
      {/* Header Skeleton */}
      <div className="p-4 sm:p-8 border-b-2 border-black bg-white">
        <div className="flex flex-col md:flex-row justify-between items-start gap-4 md:gap-8">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-2 flex-wrap">
              {/* StatusBadge skeleton */}
              <div className="h-5 w-16 bg-gray-200 rounded animate-pulse" />
              {/* Research Session text skeleton */}
              <div className="h-3 w-36 bg-gray-100 rounded animate-pulse" />
            </div>
            {/* Title Skeleton */}
            <div className="h-8 sm:h-10 w-full max-w-sm bg-gray-200 rounded animate-pulse" />
          </div>
          {/* Metadata labels skeleton */}
          <div className="hidden sm:flex flex-wrap items-center gap-2 shrink-0">
            <div className="bg-gray-100 p-2.5 sm:p-3 flex items-center gap-2">
              <Folder size={14} className="text-gray-300" />
              <div className="h-3 w-24 bg-gray-200 rounded animate-pulse" />
            </div>
            <div className="bg-gray-100 p-2.5 sm:p-3 flex items-center gap-2">
              <Cpu size={14} className="text-gray-300" />
              <div className="h-3 w-32 bg-gray-200 rounded animate-pulse" />
            </div>
          </div>
        </div>

        {/* Summary Description Skeleton */}
        <div className="mt-4 space-y-2 max-w-2xl hidden sm:block">
          <div className="h-3 w-full bg-gray-100 rounded animate-pulse" />
          <div className="h-3 w-11/12 bg-gray-100 rounded animate-pulse" />
          <div className="h-3 w-4/5 bg-gray-100 rounded animate-pulse" />
        </div>

        {/* Buttons Skeleton */}
        <div className="mt-6 flex flex-wrap gap-2 sm:gap-3 items-center">
          <div className="h-8 w-32 bg-gray-200 rounded animate-pulse" />
          <div className="h-8 w-36 bg-gray-200 rounded animate-pulse" />
        </div>
      </div>

      {/* Main split skeleton */}
      <div className="flex-1 flex flex-col xl:flex-row overflow-hidden">
        {/* Timeline Column Skeleton */}
        <div className="w-full xl:w-1/2 p-4 sm:p-8 overflow-y-auto border-r border-gray-100 flex flex-col">
          <div className="h-4 w-24 bg-gray-200 rounded mb-8" />
          
          <div className="space-y-8 flex-1 relative pl-6 border-l border-dashed border-gray-200 ml-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="relative flex gap-4 items-start">
                {/* Node indicator */}
                <div className="absolute -left-[31px] top-0 w-4 h-4 rounded-full bg-gray-200 border-2 border-white" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-32 bg-gray-200 rounded" />
                  <div className="h-16 bg-gray-100 rounded border border-gray-100" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Panel Skeleton */}
        <div className="w-full xl:w-1/2 hidden xl:flex flex-col h-full border-l border-black bg-gray-50/50">
          {/* Tabs skeleton */}
          <div className="flex border-b-2 border-black bg-white overflow-x-auto whitespace-nowrap custom-scrollbar">
            <div className="px-4 sm:px-6 py-3 border-r border-black shrink-0">
              <div className="h-3 w-16 bg-gray-200 rounded" />
            </div>
            <div className="px-4 sm:px-6 py-3 border-r border-black shrink-0">
              <div className="h-3 w-12 bg-gray-200 rounded" />
            </div>
            <div className="px-4 sm:px-6 py-3 border-r border-black shrink-0">
              <div className="h-3 w-16 bg-gray-200 rounded" />
            </div>
          </div>

          {/* Details body skeleton */}
          <div className="flex-1 p-4 sm:p-6 flex flex-col gap-4">
            <div className="h-10 bg-white border border-gray-200 p-4 rounded flex items-center gap-3">
              <Workflow size={16} className="text-gray-300" />
              <div className="h-3 w-24 bg-gray-200 rounded" />
            </div>
            <div className="flex-1 bg-white border border-gray-200 p-6 rounded space-y-4">
              <div className="h-3 w-1/3 bg-gray-200 rounded" />
              <div className="space-y-2">
                <div className="h-3 bg-gray-100 rounded" />
                <div className="h-3 bg-gray-100 rounded" />
                <div className="h-3 w-5/6 bg-gray-100 rounded" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
