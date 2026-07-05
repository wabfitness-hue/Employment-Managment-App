import { clsx } from 'clsx'

type BadgeVariant = 'blue' | 'orange' | 'green' | 'red' | 'yellow' | 'gray'

interface BadgeProps {
  children: React.ReactNode
  variant?: BadgeVariant
  className?: string
}

const variants: Record<BadgeVariant, string> = {
  blue:   'bg-blue-100 text-blue-800',
  orange: 'bg-orange-100 text-orange-800',
  green:  'bg-green-100 text-green-800',
  red:    'bg-red-100 text-red-800',
  yellow: 'bg-yellow-100 text-yellow-800',
  gray:   'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200',
}

export function Badge({ children, variant = 'gray', className }: BadgeProps) {
  return (
    <span className={clsx('inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium', variants[variant], className)}>
      {children}
    </span>
  )
}

export function PersonTypeBadge({ type }: { type: 'employee' | 'contractor' }) {
  return <Badge variant={type === 'employee' ? 'blue' : 'orange'}>{type === 'employee' ? 'Employee' : 'Contractor'}</Badge>
}

export function ExpiryBadge({ level }: { level: string }) {
  const map: Record<string, { variant: BadgeVariant; label: string }> = {
    none:     { variant: 'green',  label: 'Active' },
    notice:   { variant: 'blue',   label: '≤90d' },
    warning:  { variant: 'yellow', label: '≤30d' },
    critical: { variant: 'red',    label: '≤14d' },
    expired:  { variant: 'red',    label: 'Expired' },
  }
  const { variant, label } = map[level] ?? { variant: 'gray', label: level }
  return <Badge variant={variant}>{label}</Badge>
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, BadgeVariant> = {
    active: 'green', inactive: 'gray', suspended: 'yellow', terminated: 'red',
  }
  return <Badge variant={map[status] ?? 'gray'}>{status}</Badge>
}
