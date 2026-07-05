import { NavLink } from 'react-router-dom'
import { clsx } from 'clsx'
import {
  LayoutDashboard, Users, FileText, Upload,
  CreditCard, Settings, Wifi, Shield, LogOut
} from 'lucide-react'
import { useAuthStore } from '../../store/auth'
import { useBridgeStore } from '../../store/bridge'

const navItems = [
  { to: '/dashboard',  label: 'Dashboard',  icon: LayoutDashboard },
  { to: '/people',     label: 'People',      icon: Users },
  { to: '/contracts',  label: 'Contracts',   icon: FileText },
  { to: '/cards',      label: 'ID Cards',    icon: CreditCard },
  { to: '/import',     label: 'Import',      icon: Upload },
  { to: '/access',     label: 'Access',      icon: Shield },
  { to: '/settings',   label: 'Settings',    icon: Settings },
]

export function Sidebar() {
  const { user, logout } = useAuthStore()
  const { status } = useBridgeStore()

  const bridgeColour = status === 'connected' ? 'text-green-500' : status === 'connecting' ? 'text-yellow-500' : 'text-gray-400'

  return (
    <aside className="w-64 h-screen flex flex-col bg-gray-900 text-gray-100 fixed left-0 top-0 z-40">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-gray-700">
        <h1 className="text-lg font-bold text-white">EMS</h1>
        <p className="text-xs text-gray-400 mt-0.5">Employee Management</p>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 overflow-y-auto">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-6 py-2.5 text-sm transition-colors',
                isActive ? 'bg-blue-700 text-white' : 'text-gray-300 hover:bg-gray-800 hover:text-white'
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Bridge status */}
      <div className="px-6 py-3 border-t border-gray-700">
        <div className="flex items-center gap-2 text-xs">
          <Wifi className={clsx('h-3.5 w-3.5', bridgeColour)} />
          <span className={bridgeColour}>Bridge: {status}</span>
        </div>
      </div>

      {/* User */}
      <div className="px-4 py-4 border-t border-gray-700 flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-xs font-bold">
          {user?.display_name?.[0]?.toUpperCase() ?? '?'}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{user?.display_name}</p>
          <p className="text-xs text-gray-400 truncate">{user?.role?.replace('_', ' ')}</p>
        </div>
        <button onClick={logout} className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white">
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </aside>
  )
}
