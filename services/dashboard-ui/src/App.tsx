import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import { OverviewPage } from '@/pages/OverviewPage'
import { ContentPage } from '@/pages/ContentPage'
import { CampaignsPage } from '@/pages/CampaignsPage'
import { AnalyticsPage } from '@/pages/AnalyticsPage'
import { EventsPage } from '@/pages/EventsPage'
import { SettingsPage } from '@/pages/SettingsPage'

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/overview" replace />} />
        <Route path="overview"  element={<OverviewPage />} />
        <Route path="content"   element={<ContentPage />} />
        <Route path="campaigns" element={<CampaignsPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="events"    element={<EventsPage />} />
        <Route path="settings"  element={<SettingsPage />} />
        {/* Legacy redirect: /manifests → /content */}
        <Route path="manifests" element={<Navigate to="/content" replace />} />
        {/* Legacy redirect: /system → /overview */}
        <Route path="system"    element={<Navigate to="/overview" replace />} />
      </Route>
    </Routes>
  )
}
