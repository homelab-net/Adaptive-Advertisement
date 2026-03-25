import React, { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import { CURRENT_HEALTH } from '../data/mockData'

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(c => !c)} />

      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <TopBar health={CURRENT_HEALTH} />

        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>

        {/* Privacy footer */}
        <footer className="flex-shrink-0 bg-slate-100 border-t border-slate-200 px-6 py-2">
          <p className="text-xs text-slate-500 text-center">
            All data is metadata-only. No images, frames, or biometrics are collected.
          </p>
        </footer>
      </div>
    </div>
  )
}
