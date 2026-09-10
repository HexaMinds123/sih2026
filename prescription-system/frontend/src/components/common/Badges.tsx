import type { AnalysisStatus, AgentState, AlertSeverity, VitalStatus } from '../../types/index'

// ── Status Badge (prescription analysis) ─────────────────────────────────────
const STATUS_LABELS: Record<AnalysisStatus, string> = {
  INFORMATIONAL: 'INFORMATIONAL',
  REVIEW_REQUIRED: 'REVIEW REQUIRED',
  CRITICAL_REVIEW_REQUIRED: 'CRITICAL REVIEW',
  INSUFFICIENT_INFORMATION: 'INSUFFICIENT INFO',
}

export function StatusBadge({ status }: { status: AnalysisStatus }) {
  return (
    <span className={`status-badge status-${status.toLowerCase()}`}>
      {STATUS_LABELS[status]}
    </span>
  )
}

// ── Risk Level Badge ─────────────────────────────────────────────────────────
type RiskLevel = 'NORMAL' | 'MODERATE' | 'HIGH' | 'CRITICAL'
export function RiskBadge({ level }: { level: RiskLevel }) {
  return <span className={`risk-badge risk-${level.toLowerCase()}`}>{level}</span>
}

// ── Agent State Dot + Label ──────────────────────────────────────────────────
const AGENT_STATE_LABELS: Record<AgentState, string> = {
  ONLINE: 'Online',
  BUSY: 'Busy',
  DEGRADED: 'Degraded',
  OFFLINE: 'Offline',
}
export function AgentStateBadge({ state }: { state: AgentState }) {
  return (
    <span className={`agent-badge agent-${state.toLowerCase()}`}>
      <span className="agent-dot" />
      {AGENT_STATE_LABELS[state]}
    </span>
  )
}

// ── Vital Status Chip ────────────────────────────────────────────────────────
export function VitalBadge({ status }: { status: VitalStatus }) {
  return <span className={`vital-badge vital-${status.toLowerCase()}`}>{status}</span>
}

// ── Alert Severity Chip ──────────────────────────────────────────────────────
export function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  return <span className={`severity-badge sev-${severity.toLowerCase()}`}>{severity}</span>
}

// ── Demo Data Badge ──────────────────────────────────────────────────────────
export function DemoBadge() {
  return <span className="demo-badge">DEMO DATA</span>
}
