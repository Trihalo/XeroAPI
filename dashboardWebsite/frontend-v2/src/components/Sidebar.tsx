import { LayoutDashboard, History, FolderOpen } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/history', label: 'History', icon: History },
  { to: '/files', label: 'Files', icon: FolderOpen },
]

export default function Sidebar() {
  const location = useLocation()

  const isActive = (path: string) =>
    path === '/'
      ? location.pathname === '/' || location.pathname === '/dashboard'
      : location.pathname === path

  return (
    <aside className="w-60 shrink-0 flex flex-col text-slate-100" style={{ backgroundColor: '#151f4a' }}>
      {/* Logo */}
      <div className="px-5 py-5 border-b border-white/10">
        <img
          src="/trihalo_white.png"
          alt="Trihalo Accountancy"
          className="h-8 w-auto object-contain"
        />
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        <p className="px-3 mb-2 text-xs font-semibold uppercase tracking-wider text-white/40">
          Menu
        </p>
        {navItems.map(({ to, label, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            className={cn(
              'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
              isActive(to)
                ? 'font-semibold shadow-sm'
                : 'text-white/60 hover:bg-white/8 hover:text-white'
            )}
            style={isActive(to) ? { backgroundColor: '#38bdf8', color: '#151f4a' } : undefined}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {label}
          </Link>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-white/10">
        <p className="text-xs text-white/40">Automation Dashboard</p>
        <p className="text-xs text-white/25 mt-0.5">v2.0</p>
      </div>
    </aside>
  )
}
