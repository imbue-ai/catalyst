interface StatusBadgeProps {
  status: string;
  inverted?: boolean;
}

export function StatusBadge({ status, inverted }: StatusBadgeProps) {
  const styles: any = {
    pending: 'bg-gray-200 text-gray-700',
    running: 'bg-blue-600 text-white animate-pulse',
    completed: 'bg-green-600 text-white',
    failed: 'bg-red-600 text-white',
    paused: 'bg-yellow-500 text-white'
  }
  
  if (inverted) {
    return (
      <span className={`text-[8px] uppercase font-black px-1.5 py-0.5 rounded-sm border border-white/30`}>
        {status}
      </span>
    )
  }

  return (
    <span className={`text-[8px] uppercase font-black px-1.5 py-0.5 rounded-sm ${styles[status] || 'bg-gray-100'}`}>
      {status}
    </span>
  )
}
