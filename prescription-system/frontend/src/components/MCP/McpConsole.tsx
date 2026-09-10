import { useState } from 'react'
import { LoaderCircle } from 'lucide-react'
import { DataSourceTag, DemoBanner, PageHeader } from '../common/ui'
import { mergeMcpServers } from '../../mock/adapter'
import { mcpCheck } from '../../services/api'
import { useWorkspace } from '../../hooks/useWorkspace'

export function McpConsole() {
  const { lastExtraction, lastAnalysis } = useWorkspace()
  const [busy, setBusy] = useState(false)
  const [connected, setConnected] = useState<boolean | null>(null)
  const [tools, setTools] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [latency, setLatency] = useState<number | null>(null)

  async function probe() {
    if (!lastExtraction) return
    setBusy(true)
    setError(null)
    const started = performance.now()
    try {
      const result = await mcpCheck(lastExtraction.prescription_id)
      setConnected(result.mcp.connected)
      setTools(result.mcp.available_tools || [])
      setError(result.mcp.error || null)
      setLatency(Math.round(performance.now() - started))
    } catch (requestError) {
      setConnected(false)
      setError(requestError instanceof Error ? requestError.message : 'MCP check failed')
      setLatency(Math.round(performance.now() - started))
    } finally {
      setBusy(false)
    }
  }

  const servers = mergeMcpServers(lastAnalysis, connected, tools, error).map((server) =>
    server.id === 'clinical-guidelines' && latency !== null ? { ...server, latency_ms: latency } : server,
  )

  return (
    <div className="page dash-page">
      <PageHeader
        eyebrow="Infrastructure"
        title="System / MCP"
        copy="MCP servers are stdio processes. The only HTTP probe in this repo is POST /prescription/{id}/mcp-check after an extraction."
        extra={<DataSourceTag source={connected === null ? 'demo' : 'live'} />}
      />
      <DemoBanner />
      <section className="panel padded">
        <p className="eyebrow">Live probe</p>
        <h2>Clinical MCP via FastAPI</h2>
        <p className="muted">Requires a prescription extracted in this session. EHR and Notification MCP cannot be probed from the browser.</p>
        <button className="primary-button" type="button" disabled={!lastExtraction || busy} onClick={probe}>
          {busy ? <LoaderCircle className="spin" size={16} /> : null}
          {lastExtraction ? 'Run mcp-check' : 'Extract a prescription first'}
        </button>
      </section>
      <div className="split-grid">
        {servers.map((server) => (
          <article className="panel padded" key={server.id}>
            <div className="section-heading">
              <div>
                <p className="eyebrow">{server.transport}</p>
                <h2>{server.name}</h2>
              </div>
              <DataSourceTag source={server.source} />
            </div>
            <p className="muted">{server.command} · {server.cwd}</p>
            <p>Connection: {server.connected === null ? 'Not probed' : server.connected ? 'Connected' : 'Disconnected'}</p>
            <p>Latency: {server.latency_ms === null ? 'Not available' : `${server.latency_ms} ms`}</p>
            <h3>Tools</h3>
            <ul className="tool-list">
              {server.tools.map((tool) => (
                <li key={tool.name}><strong>{tool.name}</strong><span>{tool.description}</span></li>
              ))}
            </ul>
            {server.errors.length > 0 && (
              <div className="warning-box">
                {server.errors.map((item) => <p key={item}>{item}</p>)}
              </div>
            )}
            <h3>Recent calls</h3>
            {server.recent_calls.length ? server.recent_calls.map((call) => (
              <div className="code-block" key={call.id}><strong>{call.action}</strong><code>{call.input_summary}</code></div>
            )) : <p className="empty-state">No live calls yet.</p>}
          </article>
        ))}
      </div>
    </div>
  )
}
