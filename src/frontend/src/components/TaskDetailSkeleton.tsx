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
      <div className="p-8 border-b-2 border-black">
        <div className="flex justify-between items-start mb-4">
          <div className="space-y-2 flex-1">
            {/* Title Skeleton */}
            <div className="h-6 w-64 bg-gray-200 rounded" />
            {/* Folder / model skeleton */}
            <div className="flex gap-2">
              <div className="h-4 w-32 bg-gray-100 rounded" />
            </div>
          </div>
          {/* Action buttons skeleton */}
          <div className="flex gap-2">
            <div className="h-8 w-28 bg-gray-200 rounded" />
            <div className="h-8 w-32 bg-gray-200 rounded" />
          </div>
        </div>
        
        {/* Badges row skeleton */}
        <div className="flex items-center gap-2 mt-4">
          <div className="h-8 w-40 bg-gray-100 rounded flex items-center px-3 gap-2">
            <Folder size={14} className="text-gray-300" />
            <div className="h-3 w-24 bg-gray-200 rounded" />
          </div>
          <div className="h-8 w-48 bg-gray-100 rounded flex items-center px-3 gap-2">
            <Cpu size={14} className="text-gray-300" />
            <div className="h-3 w-32 bg-gray-200 rounded" />
          </div>
        </div>
      </div>

      {/* Main split skeleton */}
      <div className="flex-1 flex overflow-hidden">
        {/* Timeline Column Skeleton */}
        <div className="w-1/2 p-8 overflow-y-auto border-r border-gray-100 flex flex-col">
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
        <div className="w-1/2 flex flex-col h-full border-l border-black bg-gray-50/50">
          {/* Tabs skeleton */}
          <div className="flex border-b-2 border-black bg-white">
            <div className="px-6 py-3 border-r border-black">
              <div className="h-3 w-16 bg-gray-200 rounded" />
            </div>
            <div className="px-6 py-3 border-r border-black">
              <div className="h-3 w-12 bg-gray-200 rounded" />
            </div>
            <div className="px-6 py-3 border-r border-black">
              <div className="h-3 w-16 bg-gray-200 rounded" />
            </div>
          </div>

          {/* Details body skeleton */}
          <div className="flex-1 p-6 flex flex-col gap-4">
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
