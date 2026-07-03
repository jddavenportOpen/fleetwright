const BRIDGE = process.env.BRIDGE_URL ?? 'http://localhost:8787'

export interface Session {
  sid: string
  name: string
  cwd: string
  domain: string | null
  model: string
  status: string
  started_at: string
  cc_session_id: string | null
}

export interface FleetRun {
  run_id: string
  agent: string
  status: string
  objective: string
  cost_usd_total: number
  started_at: string
}

export interface Domain {
  name: string
  active: boolean
  sid: string | null
  started_at: string | null
}

export interface BridgeHealth {
  status: string
  version: string
  claude_binary?: string
  db_backend?: string
}

async function bFetch(path: string): Promise<Response> {
  return fetch(`${BRIDGE}${path}`, { cache: 'no-store', signal: AbortSignal.timeout(4000) })
}

export async function getHealth(): Promise<BridgeHealth | null> {
  try {
    const r = await bFetch('/health')
    if (!r.ok) return null
    return r.json()
  } catch {
    return null
  }
}

export async function getSessions(): Promise<Session[]> {
  try {
    const r = await bFetch('/api/sessions')
    if (!r.ok) return []
    const data = await r.json()
    return data.sessions ?? []
  } catch {
    return []
  }
}

export async function getFleetRuns(): Promise<FleetRun[]> {
  try {
    const r = await bFetch('/api/fleet/sessions')
    if (!r.ok) return []
    const data = await r.json()
    return data.runs ?? []
  } catch {
    return []
  }
}

export async function getDomains(): Promise<Domain[]> {
  try {
    const r = await bFetch('/api/domains')
    if (!r.ok) return []
    const data = await r.json()
    return data.domains ?? []
  } catch {
    return []
  }
}
