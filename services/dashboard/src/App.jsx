import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import LiveMetrics from './pages/LiveMetrics'
import AudienceState from './pages/AudienceState'
import PlayerControl from './pages/PlayerControl'
import DecisionTrace from './pages/DecisionTrace'
import CreativeLibrary from './pages/CreativeLibrary'
import Campaigns from './pages/Campaigns'
import Analytics from './pages/Analytics'
import SystemHealth from './pages/SystemHealth'
import Settings from './pages/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="metrics" element={<LiveMetrics />} />
          <Route path="audience" element={<AudienceState />} />
          <Route path="player" element={<PlayerControl />} />
          <Route path="decisions" element={<DecisionTrace />} />
          <Route path="creatives" element={<CreativeLibrary />} />
          <Route path="campaigns" element={<Campaigns />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="health" element={<SystemHealth />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
