import { Bot, Cpu, Database, Bell, FlaskConical, Shield, Wrench, Activity } from 'lucide-react'
import { MOCK_AGENTS } from '../../mock/agents'
import { AgentStateBadge, DemoBadge } from '../common/Badges'

export function AgentsPage() {
  const getAgentIcon = (id: string) => {
    switch (id) {
      case 'orchestrator':
        return <Cpu size={22} className="agent-ico-orch" />
      case 'medical-agent':
        return <FlaskConical size={22} className="agent-ico-med" />
      case 'ehr-agent':
      case 'ehr-mcp':
        return <Database size={22} className="agent-ico-ehr" />
      case 'notification-agent':
      case 'notification-mcp':
        return <Bell size={22} className="agent-ico-notif" />
      case 'clinical-mcp':
        return <Shield size={22} className="agent-ico-clin" />
      default:
        return <Bot size={22} />
    }
  }

  return (
    <div className="page-content">
      <div className="page-header">
        <div>
          <p className="eyebrow">Topology & Runtime</p>
          <h1 className="page-title">Agent Registry & Monitoring</h1>
        </div>
        <DemoBadge />
      </div>

      <div className="agent-summary-bar panel">
        <div className="summary-stat-item">
          <span className="field-label">Total Nodes</span>
          <strong>{MOCK_AGENTS.length}</strong>
        </div>
        <div className="summary-stat-item">
          <span className="field-label">Online</span>
          <strong style={{ color: 'var(--green)' }}>{MOCK_AGENTS.filter(a => a.state === 'ONLINE').length}</strong>
        </div>
        <div className="summary-stat-item">
          <span className="field-label">Total Tools Exposed</span>
          <strong>{MOCK_AGENTS.reduce((acc, a) => acc + a.tools.length, 0)}</strong>
        </div>
        <div className="summary-stat-item">
          <span className="field-label">Total Calls (1h)</span>
          <strong>{MOCK_AGENTS.reduce((acc, a) => acc + a.recentCalls, 0)}</strong>
        </div>
      </div>

      <div className="agents-cards-grid">
        {MOCK_AGENTS.map((agent) => (
          <div key={agent.id} className="panel agent-monitor-card">
            <div className="agent-card-topbar">
              <div className="agent-card-icon-container">
                {getAgentIcon(agent.id)}
              </div>
              <div>
                <strong className="agent-title-text">{agent.name}</strong>
                <p className="agent-role-sub">{agent.role}</p>
              </div>
              <div style={{ marginLeft: 'auto' }}>
                <AgentStateBadge state={agent.state} />
              </div>
            </div>

            <p className="agent-card-description">{agent.description}</p>

            <div className="agent-metrics-row">
              <div>
                <span className="field-label">Last Activity</span>
                <span className="agent-metric-val">{agent.lastActivity}</span>
              </div>
              <div>
                <span className="field-label">Calls (1 hr)</span>
                <span className="agent-metric-val"><Activity size={12} style={{ marginRight: 3 }} /> {agent.recentCalls}</span>
              </div>
            </div>

            <div className="agent-tools-section">
              <span className="field-label"><Wrench size={11} style={{ marginRight: 4 }} /> Exposed Methods / Tools ({agent.tools.length})</span>
              <div className="agent-tools-tags">
                {agent.tools.map((tool) => (
                  <code key={tool} className="tool-code-chip">{tool}</code>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

