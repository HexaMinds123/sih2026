import { useState } from 'react'
import { Activity, ChevronDown, ChevronUp, Cpu, Database, Bell, FlaskConical, Stethoscope } from 'lucide-react'
import { MOCK_AGENTS, MOCK_ORCHESTRATION_EVENTS, MOCK_ORCHESTRATION_RESULT } from '../../mock/agents'
import { Timeline } from '../common/Timeline'
import { AgentStateBadge, DemoBadge, RiskBadge } from '../common/Badges'

export function OrchestratorPage() {
  const [detailOpen, setDetailOpen] = useState(false)

  const result = MOCK_ORCHESTRATION_RESULT

  return (
    <div className="page-content">
      <div className="page-header">
        <div>
          <p className="eyebrow">AI Reasoning Layer</p>
          <h1 className="page-title">AI Orchestrator</h1>
        </div>
        <DemoBadge />
      </div>

      <p className="page-note">
        The Orchestrator coordinates all agents. It does not delegate reasoning — it performs multi-factor risk assessment itself, using outputs from the Medical Agent, EHR Agent, and Notification Agent.
      </p>

      {/* Architecture diagram */}
      <div className="panel arch-panel">
        <div className="arch-header">
          <Cpu size={18} />
          <h3>System Architecture</h3>
        </div>
        <div className="arch-flow">
          <ArchNode icon={<Stethoscope size={16} />} label="Frontend" sub="React dashboard" type="client" />
          <ArchArrow />
          <ArchNode icon={<Cpu size={16} />} label="Healthcare Orchestrator" sub="Central reasoning · risk synthesis" type="orchestrator" />
          <div className="arch-branch">
            <div className="arch-branch-col">
              <ArchArrow dir="down" />
              <ArchNode icon={<FlaskConical size={16} />} label="Medical Agent" sub="Prescription analysis (deterministic)" type="agent" />
              <ArchArrow dir="down" />
              <ArchNode icon={<Database size={16} />} label="Clinical MCP" sub="Drug interactions · RAG evidence" type="mcp" />
            </div>
            <div className="arch-branch-col">
              <ArchArrow dir="down" />
              <ArchNode icon={<Database size={16} />} label="EHR Agent / MCP" sub="Patient context · allergies" type="mcp" />
            </div>
            <div className="arch-branch-col">
              <ArchArrow dir="down" />
              <ArchNode icon={<Bell size={16} />} label="Notification Agent / MCP" sub="Audit trail · human gate · SMS" type="mcp" />
            </div>
          </div>
        </div>
      </div>

      {/* Agent status row */}
      <div className="panel" style={{ padding: '20px 24px' }}>
        <h3 className="panel-title">Agent Status</h3>
        <div className="agent-row-grid">
          {MOCK_AGENTS.map(a => (
            <div key={a.id} className="agent-mini-card">
              <AgentStateBadge state={a.state} />
              <strong>{a.name}</strong>
              <span className="muted" style={{ fontSize: 11 }}>{a.lastActivity}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Latest orchestration result */}
      <div className="panel" style={{ padding: '22px 24px' }}>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Latest run</p>
            <h3>Orchestration Result — {result.orchestration_id}</h3>
          </div>
          <RiskBadge level={result.risk_level} />
        </div>
        <div className="orch-result-meta">
          <MetaField label="Patient" value={result.patient_id} />
          <MetaField label="Status" value={result.status} />
          <MetaField label="Approved" value="No — awaiting clinician confirmation" />
          <MetaField label="Human Review" value="Required" />
          <MetaField label="Timestamp" value={new Date(result.timestamp).toLocaleString()} />
        </div>
        <div className="result-message">
          <Activity size={14} />
          <p>{result.final_message}</p>
        </div>

        <button className="audit-toggle" style={{ marginTop: 16 }} onClick={() => setDetailOpen(o => !o)}>
          <span><p className="eyebrow">Full trace</p><strong>Execution Timeline</strong></span>
          {detailOpen ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </button>
        {detailOpen && <Timeline events={MOCK_ORCHESTRATION_EVENTS} />}
      </div>
    </div>
  )
}

function ArchNode({ icon, label, sub, type }: { icon: React.ReactNode; label: string; sub: string; type: string }) {
  return (
    <div className={`arch-node arch-${type}`}>
      <div className="arch-node-icon">{icon}</div>
      <div>
        <strong>{label}</strong>
        <span>{sub}</span>
      </div>
    </div>
  )
}

function ArchArrow({ dir = 'right' }: { dir?: 'right' | 'down' }) {
  return <div className={`arch-arrow arch-arrow-${dir}`} />
}

function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="field-label">{label}</span>
      <span>{value}</span>
    </div>
  )
}
