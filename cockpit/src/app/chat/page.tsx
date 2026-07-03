import { getHealth, getSessions, getFleetRuns, getDomains } from '@/lib/bridge'
import type { Session, FleetRun, Domain, BridgeHealth } from '@/lib/bridge'

export const dynamic = 'force-dynamic'
export const revalidate = 0

function StatusBadge({ status }: { status: string }) {
  let color = '#98989d'
  if (status === 'ok' || status === 'running' || status === 'active') color = '#30d158'
  else if (status === 'error' || status === 'failed') color = '#ff453a'
  else if (status === 'pending' || status === 'queued') color = '#ffd60a'
  else if (status === 'idle') color = '#0a84ff'

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        padding: '2px 8px',
        borderRadius: 20,
        fontSize: 12,
        fontWeight: 500,
        background: `${color}22`,
        color,
        border: `1px solid ${color}44`,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: color,
          display: 'inline-block',
        }}
      />
      {status}
    </span>
  )
}

function Card({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <div
      style={{
        background: '#2c2c2e',
        border: '1px solid #3a3a3c',
        borderRadius: 12,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid #3a3a3c',
          fontWeight: 600,
          fontSize: 13,
          color: '#98989d',
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
        }}
      >
        {title}
      </div>
      <div style={{ padding: 16 }}>{children}</div>
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <div
      style={{
        color: '#48484a',
        fontSize: 13,
        textAlign: 'center',
        padding: '24px 0',
      }}
    >
      {message}
    </div>
  )
}

function SessionsPanel({ sessions }: { sessions: Session[] }) {
  return (
    <Card title={`Sessions (${sessions.length})`}>
      {sessions.length === 0 ? (
        <EmptyState message="No active sessions" />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {sessions.map((s) => (
            <div
              key={s.sid}
              style={{
                padding: 12,
                background: '#1c1c1e',
                borderRadius: 8,
                border: '1px solid #3a3a3c',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  marginBottom: 6,
                }}
              >
                <div style={{ fontWeight: 600, fontSize: 13, color: '#e5e5ea' }}>
                  {s.name || s.sid}
                </div>
                <StatusBadge status={s.status} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                {s.domain && (
                  <div style={{ fontSize: 12, color: '#98989d' }}>
                    <span style={{ color: '#636366' }}>domain: </span>
                    {s.domain}
                  </div>
                )}
                <div style={{ fontSize: 12, color: '#98989d' }}>
                  <span style={{ color: '#636366' }}>model: </span>
                  {s.model}
                </div>
                <div style={{ fontSize: 12, color: '#98989d' }}>
                  <span style={{ color: '#636366' }}>sid: </span>
                  <code style={{ fontFamily: 'monospace', fontSize: 11 }}>
                    {s.sid.slice(0, 16)}…
                  </code>
                </div>
                <div style={{ fontSize: 12, color: '#636366' }}>
                  {new Date(s.started_at).toLocaleString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function DomainsPanel({ domains }: { domains: Domain[] }) {
  return (
    <Card title={`Domains (${domains.length})`}>
      {domains.length === 0 ? (
        <EmptyState message="No domains configured" />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {domains.map((d) => (
            <div
              key={d.name}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '8px 12px',
                background: '#1c1c1e',
                borderRadius: 8,
                border: '1px solid #3a3a3c',
              }}
            >
              <div>
                <div style={{ fontWeight: 500, fontSize: 13 }}>{d.name}</div>
                {d.started_at && (
                  <div style={{ fontSize: 11, color: '#636366', marginTop: 2 }}>
                    {new Date(d.started_at).toLocaleString()}
                  </div>
                )}
              </div>
              <StatusBadge status={d.active ? 'active' : 'idle'} />
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function FleetPanel({ runs }: { runs: FleetRun[] }) {
  return (
    <Card title={`Fleet Runs (${runs.length})`}>
      {runs.length === 0 ? (
        <EmptyState message="No fleet runs" />
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: 13,
            }}
          >
            <thead>
              <tr>
                {['Run ID', 'Agent', 'Status', 'Objective', 'Cost', 'Started'].map((h) => (
                  <th
                    key={h}
                    style={{
                      textAlign: 'left',
                      padding: '6px 10px',
                      color: '#636366',
                      fontWeight: 500,
                      fontSize: 12,
                      borderBottom: '1px solid #3a3a3c',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr
                  key={r.run_id}
                  style={{ borderBottom: '1px solid #2c2c2e' }}
                >
                  <td style={{ padding: '8px 10px' }}>
                    <code style={{ fontFamily: 'monospace', fontSize: 11, color: '#98989d' }}>
                      {r.run_id.slice(0, 12)}…
                    </code>
                  </td>
                  <td style={{ padding: '8px 10px', fontWeight: 500 }}>{r.agent}</td>
                  <td style={{ padding: '8px 10px' }}>
                    <StatusBadge status={r.status} />
                  </td>
                  <td
                    style={{
                      padding: '8px 10px',
                      color: '#98989d',
                      maxWidth: 260,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {r.objective}
                  </td>
                  <td style={{ padding: '8px 10px', color: '#30d158', whiteSpace: 'nowrap' }}>
                    ${r.cost_usd_total.toFixed(4)}
                  </td>
                  <td style={{ padding: '8px 10px', color: '#636366', whiteSpace: 'nowrap' }}>
                    {new Date(r.started_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

function BridgeOfflineBanner() {
  return (
    <div
      style={{
        background: '#ff453a22',
        border: '1px solid #ff453a44',
        borderRadius: 10,
        padding: '16px 20px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        marginBottom: 24,
      }}
    >
      <span style={{ fontSize: 20 }}>⚠</span>
      <div>
        <div style={{ fontWeight: 600, color: '#ff453a', marginBottom: 2 }}>Bridge offline</div>
        <div style={{ fontSize: 13, color: '#98989d' }}>
          Cannot reach the Fleetwright bridge. Make sure it is running at{' '}
          <code style={{ fontFamily: 'monospace', fontSize: 12 }}>
            {process.env.BRIDGE_URL ?? 'http://localhost:8787'}
          </code>
        </div>
      </div>
    </div>
  )
}

export default async function ChatPage() {
  const [health, sessions, runs, domains] = await Promise.all([
    getHealth(),
    getSessions(),
    getFleetRuns(),
    getDomains(),
  ])

  const bridgeOnline = health !== null

  return (
    <div style={{ minHeight: '100vh', background: '#1c1c1e' }}>
      {/* Top bar */}
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          height: 56,
          borderBottom: '1px solid #3a3a3c',
          background: '#2c2c2e',
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span
            style={{
              fontSize: 18,
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: '#e5e5ea',
            }}
          >
            Fleetwright
          </span>
          {bridgeOnline && health ? (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                fontSize: 12,
                color: '#30d158',
                background: '#30d15822',
                border: '1px solid #30d15844',
                borderRadius: 20,
                padding: '2px 10px',
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: '#30d158',
                  display: 'inline-block',
                }}
              />
              bridge {health.version ?? 'online'}
            </span>
          ) : (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                fontSize: 12,
                color: '#ff453a',
                background: '#ff453a22',
                border: '1px solid #ff453a44',
                borderRadius: 20,
                padding: '2px 10px',
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: '#ff453a',
                  display: 'inline-block',
                }}
              />
              bridge offline
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 12, color: '#48484a' }}>
            {new Date().toLocaleTimeString()}
          </span>
          <a
            href="/chat"
            style={{
              fontSize: 12,
              padding: '5px 14px',
              borderRadius: 8,
              background: '#0a84ff22',
              border: '1px solid #0a84ff44',
              color: '#0a84ff',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            Refresh
          </a>
        </div>
      </header>

      {/* Main content */}
      <main style={{ padding: 24, maxWidth: 1400, margin: '0 auto' }}>
        {!bridgeOnline && <BridgeOfflineBanner />}

        {/* Summary row */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 12,
            marginBottom: 24,
          }}
        >
          {[
            { label: 'Sessions', value: sessions.length, color: '#0a84ff' },
            { label: 'Domains', value: domains.length, color: '#bf5af2' },
            {
              label: 'Active Domains',
              value: domains.filter((d) => d.active).length,
              color: '#30d158',
            },
            { label: 'Fleet Runs', value: runs.length, color: '#ffd60a' },
          ].map((stat) => (
            <div
              key={stat.label}
              style={{
                background: '#2c2c2e',
                border: '1px solid #3a3a3c',
                borderRadius: 12,
                padding: '16px 20px',
              }}
            >
              <div style={{ fontSize: 12, color: '#636366', marginBottom: 6 }}>
                {stat.label}
              </div>
              <div style={{ fontSize: 28, fontWeight: 700, color: stat.color }}>
                {stat.value}
              </div>
            </div>
          ))}
        </div>

        {/* Two-column layout */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '340px 1fr',
            gap: 20,
            alignItems: 'start',
          }}
        >
          {/* Left column: Sessions + Domains */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <SessionsPanel sessions={sessions} />
            <DomainsPanel domains={domains} />
          </div>

          {/* Right column: Fleet Runs */}
          <FleetPanel runs={runs} />
        </div>

        {/* Bridge info footer */}
        {bridgeOnline && health && (
          <div
            style={{
              marginTop: 24,
              padding: '12px 16px',
              background: '#2c2c2e',
              border: '1px solid #3a3a3c',
              borderRadius: 10,
              display: 'flex',
              gap: 24,
              fontSize: 12,
              color: '#636366',
            }}
          >
            {health.claude_binary && (
              <span>
                claude:{' '}
                <code style={{ fontFamily: 'monospace', color: '#98989d' }}>
                  {health.claude_binary}
                </code>
              </span>
            )}
            {health.db_backend && (
              <span>
                db:{' '}
                <code style={{ fontFamily: 'monospace', color: '#98989d' }}>
                  {health.db_backend}
                </code>
              </span>
            )}
            <span>
              version:{' '}
              <code style={{ fontFamily: 'monospace', color: '#98989d' }}>{health.version}</code>
            </span>
          </div>
        )}
      </main>
    </div>
  )
}
