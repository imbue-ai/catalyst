interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const styles: any = {
    pending: 'bg-gray-200 text-gray-700',
    running: 'bg-blue-600 text-white animate-pulse',
    completed: 'bg-green-600 text-white',
    failed: 'bg-red-600 text-white',
    paused: 'bg-yellow-500 text-white',
    canceled: 'bg-gray-500 text-white'
  }
  
  return (
    <span className={`text-[8px] uppercase font-black px-1.5 py-0.5 rounded-sm ${styles[status] || 'bg-gray-100'}`}>
      {status}
    </span>
  )
}
