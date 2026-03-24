import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import { ManifestsPage } from '@/pages/ManifestsPage'
import { CampaignsPage } from '@/pages/CampaignsPage'
import { SystemPage } from '@/pages/SystemPage'
import { AnalyticsPage } from '@/pages/AnalyticsPage'
import { EventsPage } from '@/pages/EventsPage'
import { SettingsPage } from '@/pages/SettingsPage'

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/system" replace />} />
        <Route path="system"    element={<SystemPage />} />
        <Route path="manifests" element={<ManifestsPage />} />
        <Route path="campaigns" element={<CampaignsPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="events"    element={<EventsPage />} />
        <Route path="settings"  element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}
