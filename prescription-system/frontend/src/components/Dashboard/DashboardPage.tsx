import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, FileText, Heart, RefreshCw } from 'lucide-react'
import { checkHealth } from '../../services/api'
import { MOCK_ALERTS } from '../../mock/alerts'
import { MOCK_AGENTS, MOCK_ORCHESTRATION_EVENTS } from '../../mock/agents'
import { ACTIVE_PATIENT } from '../../mock/patients'
import { CURRENT_VITALS, getVitalStatus } from '../../mock/vitals'
import { AgentStateBadge, DemoBadge, SeverityBadge } from '../common/Badges'
import type { Page } from '../../layout/Sidebar'

interface Props { onNavigate: (p: Page) => void }

export function DashboardPage({ onNavigate }: Props) {
  const [online, setOnline] = useState<boolean | null>(null)
  const critical = MOCK_ALERTS.filter(a => a.severity === 'CRITICAL').length

  useEffect(() => {
    checkHealth().then(setOnline)
  }, [])

  return (
    <div className="page-content">
      <div className="page-header">
        <div>
          <p className="eyebrow">Overview</p>
          <h1 className="page-title">Dashboard</h1>
        </div>
        <button className="icon-btn" onClick={() => checkHealth().then(setOnline)} title="Refresh">
          <RefreshCw size={15} />
        </button>
      </div>

      {/* Top stat row */}
      <div className="stat-row">
        <StatCard icon={<AlertTriangle size={18} />} color="red" label="Active Alerts" value={MOCK_ALERTS.length} sub={`${critical} critical`} onClick={() => onNavigate('alerts')} />
        <StatCard icon={<Heart size={18} />} color="amber" label="Vitals Warnings" value={2} sub="P001 elevated" onClick={() => onNavigate('vitals')} />
        <StatCard icon={<FileText size={18} />} color="green" label="Prescriptions Today" value={7} sub="3 pending review" onClick={() => onNavigate('prescription')} />
        <StatCard icon={<Activity size={18} />} color="blue" label="Agent Calls" value={64} sub="last hour" onClick={() => onNavigate('agents')} />
      </div>

      <div className="dash-grid">
        {/* Patient summary */}
        <div className="dash-card">
          <div className="dash-card-header">
            <h3>Active Patient</h3>
            <DemoBadge />
          </div>
          <div className="patient-mini">
            <div className="patient-avatar">{ACTIVE_PATIENT.name.split(' ').map(n => n[0]).join('')}</div>
            <div>
              <strong>{ACTIVE_PATIENT.name}</strong>
              <p>{ACTIVE_PATIENT.age}y · {ACTIVE_PATIENT.gender} · {ACTIVE_PATIENT.patient_id}</p>
              <p className="patient-conditions">{ACTIVE_PATIENT.conditions.join(', ')}</p>
            </div>
          </div>
          <button className="text-btn" onClick={() => onNavigate('patient')}>View EHR →</button>
        </div>

        {/* Current vitals mini */}
        <div className="dash-card">
          <div className="dash-card-header">
            <h3>Current Vitals</h3>
            <DemoBadge />
          </div>
          <div className="vitals-mini-grid">
            <VitalMini label="Heart Rate" value={`${CURRENT_VITALS.heart_rate} bpm`} status={getVitalStatus('heart_rate', CURRENT_VITALS.heart_rate)} />
            <VitalMini label="SpO₂" value={`${CURRENT_VITALS.spo2}%`} status={getVitalStatus('spo2', CURRENT_VITALS.spo2)} />
            <VitalMini label="Blood Pressure" value={`${CURRENT_VITALS.systolic_bp}/${CURRENT_VITALS.diastolic_bp}`} status={getVitalStatus('systolic_bp', CURRENT_VITALS.systolic_bp)} />
            <VitalMini label="Glucose" value={`${CURRENT_VITALS.glucose} mg/dL`} status={getVitalStatus('glucose', CURRENT_VITALS.glucose)} />
          </div>
          <button className="text-btn" onClick={() => onNavigate('vitals')}>Live vitals →</button>
        </div>

        {/* Agent status */}
        <div className="dash-card">
          <div className="dash-card-header">
            <h3>Agent Status</h3>
            <DemoBadge />
          </div>
          <div className="agent-status-list">
            {MOCK_AGENTS.slice(0, 4).map(a => (
              <div key={a.id} className="agent-status-row">
                <AgentStateBadge state={a.state} />
                <span className="agent-name">{a.name}</span>
                <span className="agent-last">{a.lastActivity}</span>
              </div>
            ))}
          </div>
          <button className="text-btn" onClick={() => onNavigate('agents')}>All agents →</button>
        </div>

        {/* Orchestration feed */}
        <div className="dash-card span-2">
          <div className="dash-card-header">
            <h3>Recent Orchestration Activity</h3>
            <DemoBadge />
          </div>
          <div className="orch-feed">
            {MOCK_ORCHESTRATION_EVENTS.slice(-5).reverse().map(ev => (
              <div key={ev.id} className={`orch-row orch-${ev.status}`}>
                <span className="orch-agent">{ev.agent}</span>
                <span className="orch-event">{ev.event}</span>
                <span className="orch-detail">{ev.detail}</span>
                <span className="orch-time">{new Date(ev.timestamp).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
          <button className="text-btn" onClick={() => onNavigate('orchestrator')}>Full orchestration view →</button>
        </div>

        {/* Recent alerts */}
        <div className="dash-card">
          <div className="dash-card-header">
            <h3>Active Alerts</h3>
            <span className="count-chip alert">{MOCK_ALERTS.length}</span>
          </div>
          {MOCK_ALERTS.map(a => (
            <div key={a.id} className="alert-mini-row">
              <SeverityBadge severity={a.severity} />
              <div>
                <span className="alert-mini-title">{a.title}</span>
                <span className="alert-mini-patient">{a.patient_name}</span>
              </div>
            </div>
          ))}
          <button className="text-btn" onClick={() => onNavigate('alerts')}>All alerts →</button>
        </div>

        {/* Backend connectivity */}
        <div className="dash-card">
          <div className="dash-card-header">
            <h3>Backend Connectivity</h3>
          </div>
          <div className="conn-list">
            <ConnRow label="FastAPI (Prescription)" status={online} endpoint="GET /api/health" />
            <ConnRow label="Clinical MCP" status={true} endpoint="stdio · server.py" demo />
            <ConnRow label="EHR MCP" status={true} endpoint="stdio · server.py" demo />
            <ConnRow label="Notification MCP" status={true} endpoint="stdio · server.py" demo />
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({ icon, color, label, value, sub, onClick }: {
  icon: React.ReactNode; color: string; label: string; value: number; sub: string; onClick: () => void
}) {
  return (
    <button className={`stat-card stat-${color}`} onClick={onClick}>
      <div className={`stat-icon stat-icon-${color}`}>{icon}</div>
      <div>
        <p className="stat-label">{label}</p>
        <strong className="stat-value">{value}</strong>
        <p className="stat-sub">{sub}</p>
      </div>
    </button>
  )
}

function VitalMini({ label, value, status }: { label: string; value: string; status: 'NORMAL' | 'WARNING' | 'CRITICAL' }) {
  return (
    <div className={`vital-mini vital-mini-${status.toLowerCase()}`}>
      <span className="vital-mini-label">{label}</span>
      <strong className="vital-mini-value">{value}</strong>
    </div>
  )
}

function ConnRow({ label, status, endpoint, demo }: {
  label: string; status: boolean | null; endpoint: string; demo?: boolean
}) {
  const dot = status === null ? 'checking' : status ? 'online' : 'offline'
  const text = status === null ? 'Checking…' : status ? 'Connected' : 'Offline'
  return (
    <div className="conn-row">
      <span className={`conn-dot conn-${dot}`} />
      <div>
        <span className="conn-label">{label}</span>
        <span className="conn-endpoint">{endpoint}{demo ? ' · DEMO' : ''}</span>
      </div>
      <span className={`conn-status conn-status-${dot}`}>{text}</span>
    </div>
  )
}
