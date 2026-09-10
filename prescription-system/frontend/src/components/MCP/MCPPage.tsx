import { useState } from 'react'
import { Server, ChevronDown, ChevronUp, Layers } from 'lucide-react'
import { MOCK_MCP_SERVERS } from '../../mock/mcp'
import { DemoBadge } from '../common/Badges'

export function MCPPage() {
  const [expandedServer, setExpandedServer] = useState<string | null>(MOCK_MCP_SERVERS[0]?.id ?? null)

  const toggleExpand = (id: string) => {
    setExpandedServer(prev => prev === id ? null : id)
  }

  const totalTools = MOCK_MCP_SERVERS.reduce((acc, s) => acc + s.tools.length, 0)
  const totalCalls = MOCK_MCP_SERVERS.reduce((acc, s) => acc + s.tools.reduce((tAcc, t) => tAcc + t.callCount, 0), 0)
  const totalErrors = MOCK_MCP_SERVERS.reduce((acc, s) => acc + s.tools.reduce((tAcc, t) => tAcc + t.errorCount, 0), 0)

  return (
    <div className="page-content">
      <div className="page-header">
        <div>
          <p className="eyebrow">Model Context Protocol</p>
          <h1 className="page-title">MCP Servers & Tool Ecosystem</h1>
        </div>
        <DemoBadge />
      </div>

      <div className="agent-summary-bar panel">
        <div className="summary-stat-item">
          <span className="field-label">Active MCP Servers</span>
          <strong>{MOCK_MCP_SERVERS.length}</strong>
        </div>
        <div className="summary-stat-item">
          <span className="field-label">Transport Protocol</span>
          <strong>stdio (FastMCP)</strong>
        </div>
        <div className="summary-stat-item">
          <span className="field-label">Registered Tools</span>
          <strong>{totalTools}</strong>
        </div>
        <div className="summary-stat-item">
          <span className="field-label">Total Invocations</span>
          <strong>{totalCalls}</strong>
        </div>
        <div className="summary-stat-item">
          <span className="field-label">Reported Errors</span>
          <strong style={{ color: totalErrors > 0 ? 'var(--amber)' : 'var(--green)' }}>{totalErrors}</strong>
        </div>
      </div>

      <div className="mcp-servers-stack">
        {MOCK_MCP_SERVERS.map((server) => {
          const isExpanded = expandedServer === server.id
          const srvCalls = server.tools.reduce((acc, t) => acc + t.callCount, 0)

          return (
            <div key={server.id} className="panel mcp-server-card">
              <div className="mcp-server-header" onClick={() => toggleExpand(server.id)}>
                <div className="mcp-header-icon-box">
                  <Server size={20} className="mcp-server-icon" />
                </div>
                <div className="mcp-header-title-box">
                  <div className="mcp-title-row">
                    <h3>{server.name}</h3>
                    <span className="mcp-id-tag">{server.id}</span>
                    <span className={`status-badge ${server.status === 'connected' ? 'status-informational' : 'status-critical_review_required'}`} style={{ padding: '3px 8px', fontSize: '10px' }}>
                      {server.status.toUpperCase()}
                    </span>
                  </div>
                  <p className="muted" style={{ margin: 0 }}>
                    Transport: <code>{server.transport}</code> · Uptime: {server.uptime} · {server.tools.length} tools registered · {srvCalls} invocations
                  </p>
                </div>
                <div className="mcp-toggle-icon">
                  {isExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                </div>
              </div>

              {isExpanded && (
                <div className="mcp-tools-container">
                  <p className="field-label" style={{ marginBottom: 12 }}>
                    <Layers size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                    Available Tools & Remote Procedure Endpoints
                  </p>

                  <div className="mcp-tools-table-wrap">
                    <table className="mcp-tools-table">
                      <thead>
                        <tr>
                          <th>Tool Identifier</th>
                          <th>Functional Description</th>
                          <th>Invocations</th>
                          <th>Avg Latency</th>
                          <th>Errors</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {server.tools.map((tool) => (
                          <tr key={tool.name}>
                            <td>
                              <code className="tool-name-highlight">{tool.name}</code>
                            </td>
                            <td className="tool-desc-cell">{tool.description}</td>
                            <td>
                              <strong>{tool.callCount}</strong>
                            </td>
                            <td>
                              {tool.avgLatencyMs ? `${tool.avgLatencyMs} ms` : '—'}
                            </td>
                            <td>
                              <span className={tool.errorCount > 0 ? 'text-amber' : 'text-green'}>
                                {tool.errorCount}
                              </span>
                            </td>
                            <td>
                              <span className="status-badge status-informational" style={{ padding: '2px 6px', fontSize: '10px' }}>
                                READY
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
