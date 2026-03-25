import { NavLink } from 'react-router-dom'
import {
  FileVideo,
  Megaphone,
  Activity,
  BarChart2,
  ScrollText,
  Settings,
  Tv2,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/system',    icon: Activity,    label: 'System' },
  { to: '/manifests', icon: FileVideo,   label: 'Content' },
  { to: '/campaigns', icon: Megaphone,   label: 'Campaigns' },
  { to: '/analytics', icon: BarChart2,   label: 'Analytics' },
  { to: '/events',    icon: ScrollText,  label: 'Audit Log' },
]

export function Sidebar() {
  return (
    <aside className="flex h-screen w-[220px] flex-shrink-0 flex-col bg-[hsl(var(--sidebar))] border-r border-[hsl(var(--sidebar-border))]">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-[hsl(var(--sidebar-border))]">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary">
          <Tv2 className="h-4 w-4 text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold text-[hsl(var(--sidebar-foreground))] leading-tight">Adaptive Ad</p>
          <p className="text-[10px] text-[hsl(var(--sidebar-muted))] leading-tight">Control Panel</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-4 px-2">
        <ul className="space-y-0.5">
          {NAV.map(({ to, icon: Icon, label }) => (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                    isActive
                      ? 'bg-[hsl(var(--sidebar-active))] text-[hsl(var(--sidebar-foreground))] font-medium'
                      : 'text-[hsl(var(--sidebar-muted))] hover:bg-[hsl(var(--sidebar-active))] hover:text-[hsl(var(--sidebar-foreground))]'
                  )
                }
              >
                <Icon className="h-4 w-4 flex-shrink-0" />
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* Settings at bottom */}
      <div className="border-t border-[hsl(var(--sidebar-border))] p-2">
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
              isActive
                ? 'bg-[hsl(var(--sidebar-active))] text-[hsl(var(--sidebar-foreground))] font-medium'
                : 'text-[hsl(var(--sidebar-muted))] hover:bg-[hsl(var(--sidebar-active))] hover:text-[hsl(var(--sidebar-foreground))]'
            )
          }
        >
          <Settings className="h-4 w-4 flex-shrink-0" />
          Settings
        </NavLink>
      </div>
    </aside>
  )
}
