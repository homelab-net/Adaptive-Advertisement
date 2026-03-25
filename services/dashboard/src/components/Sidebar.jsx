import React from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Activity,
  Users,
  PlayCircle,
  GitBranch,
  Film,
  Megaphone,
  BarChart2,
  HeartPulse,
  Settings,
  ChevronLeft,
  ChevronRight,
  Zap,
} from 'lucide-react'

const NAV_SECTIONS = [
  {
    label: null,
    items: [
      { to: '/', icon: LayoutDashboard, label: 'Overview', phase: null, end: true },
    ],
  },
  {
    label: 'Live Data',
    items: [
      { to: '/metrics', icon: Activity, label: 'Metrics', phase: null },
    ],
  },
  {
    label: 'Phase 2+',
    items: [
      { to: '/audience', icon: Users, label: 'Audience State', phase: 2 },
      { to: '/player', icon: PlayCircle, label: 'Player Control', phase: 3 },
      { to: '/decisions', icon: GitBranch, label: 'Decision Trace', phase: 4 },
      { to: '/creatives', icon: Film, label: 'Creative Library', phase: 5 },
    ],
  },
  {
    label: 'Operations',
    items: [
      { to: '/campaigns', icon: Megaphone, label: 'Campaigns', phase: 7 },
      { to: '/analytics', icon: BarChart2, label: 'Analytics', phase: 7 },
      { to: '/health', icon: HeartPulse, label: 'System Health', phase: null },
      { to: '/settings', icon: Settings, label: 'Settings', phase: null },
    ],
  },
]

export default function Sidebar({ collapsed, onToggle }) {
  return (
    <aside
      className={`flex flex-col bg-slate-900 transition-all duration-200 ease-in-out flex-shrink-0 ${
        collapsed ? 'w-14' : 'w-56'
      }`}
    >
      {/* Logo */}
      <div className={`flex items-center gap-2 px-3 py-4 border-b border-slate-700 min-h-[60px] ${collapsed ? 'justify-center' : ''}`}>
        <div className="flex-shrink-0 bg-indigo-600 rounded-lg p-1.5">
          <Zap className="h-4 w-4 text-white" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="text-xs font-bold text-white leading-none truncate">Adaptive Advert</p>
            <p className="text-xs text-slate-400 leading-none mt-0.5">Operator Dashboard</p>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto overflow-x-hidden py-3 scrollbar-thin">
        {NAV_SECTIONS.map((section, si) => (
          <div key={si} className="mb-1">
            {section.label && !collapsed && (
              <p className="px-3 py-1.5 text-xs font-semibold text-slate-500 uppercase tracking-widest">
                {section.label}
              </p>
            )}
            {section.label && collapsed && <div className="mx-2 my-1 border-t border-slate-700" />}
            {section.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 mx-2 px-2 py-2 rounded-lg text-sm font-medium transition-colors duration-100 group ${
                    isActive
                      ? 'bg-indigo-600 text-white'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800'
                  } ${collapsed ? 'justify-center' : ''}`
                }
                title={collapsed ? item.label : undefined}
              >
                <item.icon className="h-4 w-4 flex-shrink-0" />
                {!collapsed && (
                  <>
                    <span className="flex-1 truncate">{item.label}</span>
                    {item.phase && (
                      <span className="flex-shrink-0 text-xs bg-slate-700 text-slate-400 rounded px-1 py-0.5 leading-none">
                        P{item.phase}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* Collapse toggle */}
      <div className="border-t border-slate-700 p-2">
        <button
          onClick={onToggle}
          className="w-full flex items-center justify-center p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          {!collapsed && <span className="ml-2 text-xs">Collapse</span>}
        </button>
      </div>
    </aside>
  )
}
