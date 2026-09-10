import { DataSourceTag, DemoBanner, PageHeader } from '../common/ui'
import { mergeAgentCatalog } from '../../mock/adapter'
import { useWorkspace } from '../../hooks/useWorkspace'

export function AgentMonitor() {
  const { lastAnalysis } = useWorkspace()
  const agents = mergeAgentCatalog(lastAnalysis)

  return (
    <div className="page dash-page">
      <PageHeader
        eyebrow="Operations"
        title="Agent monitoring"
        copy="Orchestrator, specialized agents, and MCP servers. Recent Clinical MCP calls become live after a successful Analyze Prescription."
        extra={<DataSourceTag source="demo" />}
      />
      <DemoBanner />
      <div className="agent-table-wrap panel">
        <table className="agent-table">
          <thead>
            <tr>
              <th>Component</th>
              <th>Layer</th>
              <th>Status</th>
              <th>Last activity</th>
              <th>Responsibility</th>
              <th>Tools</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((agent) => (
              <tr key={agent.id}>
                <td><strong>{agent.name}</strong></td>
                <td>{agent.layer.replaceAll('_', ' ')}</td>
                <td><span className={`level-badge level-${agent.status}`}>{agent.status}</span></td>
                <td>{agent.last_activity}</td>
                <td>{agent.responsibility}</td>
                <td>{agent.tools.join(', ')}</td>
                <td><DataSourceTag source={agent.source} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="split-grid">
        {agents.map((agent) => (
          <article className="panel padded" key={`${agent.id}-calls`}>
            <p className="eyebrow">{agent.name}</p>
            <h2>Recent calls</h2>
            {agent.recent_calls.length ? agent.recent_calls.map((call) => (
              <div className="code-block" key={call.id}>
                <strong>{call.action}</strong>
                <code>{call.input_summary}</code>
                <p className="muted">{call.output_summary}</p>
              </div>
            )) : <p className="empty-state">No calls in this session. Run Analyze Prescription to populate Medical Agent / Clinical MCP from the live audit trail.</p>}
          </article>
        ))}
      </div>
    </div>
  )
}
