// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function nowMinus(minutes) {
  return new Date(Date.now() - minutes * 60 * 1000).toISOString()
}

function randomBetween(min, max) {
  return Math.random() * (max - min) + min
}

function randomInt(min, max) {
  return Math.floor(randomBetween(min, max + 1))
}

// ---------------------------------------------------------------------------
// Static identity / site config
// ---------------------------------------------------------------------------

export const SITE_CONFIG = {
  tenant_id: 'tenant_001',
  site_id: 'site_pilot_01',
  site_name: 'Pilot Site 1',
  camera_id: 'cam_01',
  pipeline_id: 'pipeline_001',
  mqtt_broker: 'mqtt://localhost:1883',
  mqtt_topic_prefix: 'adv/tenant_001/site_pilot_01',
}

// ---------------------------------------------------------------------------
// Camera source config (mirrors camera-source.json)
// ---------------------------------------------------------------------------

export const CAMERA_SOURCE_CONFIG = {
  camera_id: 'cam_01',
  device_path: '/dev/video0',
  resolution: { width: 1280, height: 720 },
  fps_target: 30,
  inference_model: 'yolov8n',
  window_ms: 100,
  confidence_threshold: 0.45,
  reopen_delay_ms: 2000,
  max_reopen_attempts: 10,
}

// ---------------------------------------------------------------------------
// Services registry
// ---------------------------------------------------------------------------

export const SERVICES = [
  {
    id: 'input-cv',
    name: 'input-cv',
    description: 'Computer vision pipeline (person detection)',
    phase: 1,
    status: 'online',
  },
  {
    id: 'audience-state',
    name: 'audience-state',
    description: 'Audience smoothing & confidence engine',
    phase: 2,
    status: 'offline',
  },
  {
    id: 'player',
    name: 'player',
    description: 'Ad playback controller',
    phase: 3,
    status: 'offline',
  },
  {
    id: 'decision-engine',
    name: 'decision-engine',
    description: 'Creative selection & explainability',
    phase: 4,
    status: 'offline',
  },
  {
    id: 'creative-manager',
    name: 'creative-manager',
    description: 'Creative asset library & approval workflow',
    phase: 5,
    status: 'offline',
  },
  {
    id: 'campaign-manager',
    name: 'campaign-manager',
    description: 'Campaign scheduling & management',
    phase: 7,
    status: 'offline',
  },
  {
    id: 'analytics',
    name: 'analytics',
    description: 'Impression & dwell analytics aggregator',
    phase: 7,
    status: 'offline',
  },
  {
    id: 'mqtt-broker',
    name: 'mqtt-broker',
    description: 'Internal MQTT message broker (Mosquitto)',
    phase: 1,
    status: 'online',
  },
]

// ---------------------------------------------------------------------------
// CvObservation — current snapshot
// ---------------------------------------------------------------------------

export const CURRENT_CV_OBSERVATION = {
  schema_version: '1.0.0',
  message_type: 'cv_observation',
  message_id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  produced_at: new Date().toISOString(),
  tenant_id: 'tenant_001',
  site_id: 'site_pilot_01',
  camera_id: 'cam_01',
  pipeline_id: 'pipeline_001',
  frame_seq: 74821,
  window_ms: 100,
  counts: {
    persons: 3,
    confidence_mean: 0.87,
  },
  quality: {
    pipeline_fps: 29.8,
    inference_ms: 12.4,
  },
  privacy: {
    contains_images: false,
    contains_frame_urls: false,
    contains_face_embeddings: false,
  },
}

// ---------------------------------------------------------------------------
// Health snapshot (input-cv)
// ---------------------------------------------------------------------------

export const CURRENT_HEALTH = {
  camera_id: 'cam_01',
  pipeline_id: 'pipeline_001',
  device_present: true,
  device_path: '/dev/video0',
  pipeline_state: 'running', // starting | running | reopening | failed
  last_frame_ts: new Date().toISOString(),
  last_pipeline_start_ts: nowMinus(47),
  reopen_count: 0,
  uptime_seconds: 47 * 60,
}

// ---------------------------------------------------------------------------
// Time-series data for the last 30 minutes (one point per 20 seconds → 90 points)
// ---------------------------------------------------------------------------

function generateTimeSeries() {
  const points = []
  const now = Date.now()
  const count = 90 // one point per 20 s = 30 min
  const intervalMs = 20 * 1000

  // Simulate a realistic audience pattern: low -> ramp -> peak -> taper
  let persons = 1

  for (let i = count - 1; i >= 0; i--) {
    const ts = new Date(now - i * intervalMs)
    const minutesAgo = (i * intervalMs) / 60000
    const label = ts.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

    // Simulate crowd dynamics
    const trend = Math.sin((minutesAgo / 30) * Math.PI) * 4 // gentle arc
    persons = Math.max(0, Math.round(persons + randomBetween(-0.5, 0.8) + (trend > persons ? 0.3 : -0.1)))
    persons = Math.min(persons, 8)

    const confidence_mean = persons > 0
      ? Math.min(0.99, 0.6 + randomBetween(0, 0.35))
      : randomBetween(0, 0.3)

    const pipeline_fps = randomBetween(28.5, 30.2)
    const inference_ms = randomBetween(10.5, 16.8)

    points.push({
      ts: ts.toISOString(),
      label,
      persons,
      confidence_mean: parseFloat(confidence_mean.toFixed(3)),
      pipeline_fps: parseFloat(pipeline_fps.toFixed(1)),
      inference_ms: parseFloat(inference_ms.toFixed(1)),
    })
  }

  return points
}

export const TIME_SERIES = generateTimeSeries()

// ---------------------------------------------------------------------------
// Recent activity feed
// ---------------------------------------------------------------------------

export const RECENT_ACTIVITY = [
  {
    id: 1,
    ts: nowMinus(0.5),
    type: 'metric',
    icon: 'users',
    message: 'Person count updated: 3 persons detected',
    level: 'info',
  },
  {
    id: 2,
    ts: nowMinus(1.2),
    type: 'health',
    icon: 'heart-pulse',
    message: 'input-cv health check: pipeline running nominally',
    level: 'success',
  },
  {
    id: 3,
    ts: nowMinus(3.8),
    type: 'metric',
    icon: 'users',
    message: 'Person count updated: 5 persons detected',
    level: 'info',
  },
  {
    id: 4,
    ts: nowMinus(7.1),
    type: 'system',
    icon: 'settings',
    message: 'Pipeline restarted (device reopen)',
    level: 'warning',
  },
  {
    id: 5,
    ts: nowMinus(12.4),
    type: 'health',
    icon: 'heart-pulse',
    message: 'MQTT broker connected successfully',
    level: 'success',
  },
  {
    id: 6,
    ts: nowMinus(18.0),
    type: 'system',
    icon: 'power',
    message: 'input-cv service started',
    level: 'info',
  },
  {
    id: 7,
    ts: nowMinus(47.2),
    type: 'system',
    icon: 'power',
    message: 'Dashboard service started',
    level: 'info',
  },
]

// ---------------------------------------------------------------------------
// Creative Library (Phase 5 mock)
// ---------------------------------------------------------------------------

export const CREATIVE_ASSETS = [
  {
    id: 'cre_001',
    name: 'Summer Sale Banner',
    type: 'template',
    status: 'approved',
    dimensions: '1920x1080',
    duration_s: 15,
    updated_at: nowMinus(120),
    tags: ['sale', 'seasonal'],
  },
  {
    id: 'cre_002',
    name: 'Product Launch — Model X',
    type: 'headline',
    status: 'pending',
    dimensions: '1920x1080',
    duration_s: 10,
    updated_at: nowMinus(30),
    tags: ['launch', 'product'],
  },
  {
    id: 'cre_003',
    name: 'Brand Awareness CTA',
    type: 'cta',
    status: 'approved',
    dimensions: '1920x1080',
    duration_s: 20,
    updated_at: nowMinus(480),
    tags: ['brand'],
  },
  {
    id: 'cre_004',
    name: 'Clearance Event Spot',
    type: 'template',
    status: 'rejected',
    dimensions: '1920x1080',
    duration_s: 15,
    updated_at: nowMinus(240),
    tags: ['clearance'],
  },
  {
    id: 'cre_005',
    name: 'Loyalty Programme Reminder',
    type: 'cta',
    status: 'approved',
    dimensions: '1920x1080',
    duration_s: 12,
    updated_at: nowMinus(720),
    tags: ['loyalty'],
  },
]

// ---------------------------------------------------------------------------
// Campaigns (Phase 7 mock)
// ---------------------------------------------------------------------------

export const CAMPAIGNS = [
  {
    id: 'camp_001',
    name: 'Q1 Summer Push',
    status: 'active',
    start_date: '2026-01-15',
    end_date: '2026-03-31',
    budget: 4500,
    impressions: 12480,
    creatives: ['cre_001', 'cre_003'],
  },
  {
    id: 'camp_002',
    name: 'Model X Launch',
    status: 'pending_approval',
    start_date: '2026-04-01',
    end_date: '2026-04-30',
    budget: 8000,
    impressions: 0,
    creatives: ['cre_002'],
  },
  {
    id: 'camp_003',
    name: 'Clearance Week',
    status: 'paused',
    start_date: '2026-02-01',
    end_date: '2026-02-14',
    budget: 2000,
    impressions: 3210,
    creatives: ['cre_004'],
  },
  {
    id: 'camp_004',
    name: 'Loyalty Q2',
    status: 'active',
    start_date: '2026-03-01',
    end_date: '2026-06-30',
    budget: 3200,
    impressions: 5640,
    creatives: ['cre_005'],
  },
]

// ---------------------------------------------------------------------------
// Analytics mock (Phase 7)
// ---------------------------------------------------------------------------

function generateAnalyticsSeries() {
  const days = []
  for (let i = 29; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000)
    const label = d.toLocaleDateString('en-GB', { month: 'short', day: 'numeric' })
    const impressions = randomInt(200, 800)
    const dwell_proxy = parseFloat(randomBetween(4.2, 18.5).toFixed(1))
    const static_ctr = parseFloat(randomBetween(0.8, 2.1).toFixed(2))
    const adaptive_ctr = parseFloat(randomBetween(2.0, 4.8).toFixed(2))
    days.push({ label, impressions, dwell_proxy, static_ctr, adaptive_ctr })
  }
  return days
}

export const ANALYTICS_SERIES = generateAnalyticsSeries()

// ---------------------------------------------------------------------------
// System uptime (mocked)
// ---------------------------------------------------------------------------

export const SYSTEM_UPTIME_SECONDS = 47 * 60 + 33

export function formatUptime(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}h ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

export function formatRelativeTime(isoString) {
  const diff = Date.now() - new Date(isoString).getTime()
  const s = Math.floor(diff / 1000)
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  return `${h}h ${m % 60}m ago`
}
