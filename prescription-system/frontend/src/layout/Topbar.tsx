import { Bell, User } from 'lucide-react'
import type { Page } from './Sidebar'
import { ACTIVE_PATIENT } from '../mock/patients'

interface TopbarProps {
  currentPage: Page
  backendOnline: boolean | null
  alertCount: number
  onNavigate: (page: Page) => void
}

const PAGE_TITLES: Record<Page, { title: string; subtitle: string }> = {
  dashboard: { title: 'HealthEase Command Center', subtitle: 'SIH 2026 AI Healthcare Ecosystem' },
  patient: { title: 'Patient Profile & EHR Context', subtitle: 'EHR-MCP Server Integration' },
  prescription: { title: 'Prescription Extraction & Guidance', subtitle: 'Medical Agent & Clinical MCP' },
  orchestrator: { title: 'AI Orchestrator Execution Flow', subtitle: 'Central Reasoning & Multi-Factor Risk Synthesis' },
  vitals: { title: 'Real-Time Telemetry & Vitals Stream', subtitle: 'Wearable Sensor Analytics & Anomaly Detection' },
  alerts: { title: 'Clinical Escalation & Safety Gate', subtitle: 'Attending Clinician Decision Gateway' },
  agents: { title: 'Agent Topology & Monitoring', subtitle: 'Multi-Agent Subsystem Status & Metrics' },
  mcp: { title: 'MCP Servers & Tool Ecosystem', subtitle: 'Model Context Protocol FastMCP Connectors' },
}

export function Topbar({ currentPage, backendOnline, alertCount, onNavigate }: TopbarProps) {
  const info = PAGE_TITLES[currentPage]

  return (
    <header className="dashboard-topbar">
      <div className="topbar-left">
        <div className="topbar-title-wrap">
          <h2 className="topbar-title">{info.title}</h2>
          <span className="topbar-sub">{info.subtitle}</span>
        </div>
      </div>

      <div className="topbar-right">
        {/* Active Patient chip */}
        <button className="topbar-patient-chip" onClick={() => onNavigate('patient')} title="Switch / View Patient">
          <User size={14} />
          <span>Patient: <strong>{ACTIVE_PATIENT.name}</strong> ({ACTIVE_PATIENT.patient_id})</span>
        </button>

        {/* Alerts quick badge */}
        <button
          className={`topbar-alert-btn ${alertCount > 0 ? 'has-alerts' : ''}`}
          onClick={() => onNavigate('alerts')}
          title="Active Alerts"
        >
          <Bell size={16} />
          {alertCount > 0 && <span className="alert-count-dot">{alertCount}</span>}
        </button>

        {/* Backend API status badge */}
        <div className="topbar-conn-badge">
          <span className={`conn-indicator ${backendOnline === true ? 'online' : backendOnline === false ? 'offline' : 'checking'}`} />
          <span className="conn-text">
            {backendOnline === true ? 'API Connected' : backendOnline === false ? 'API Offline (Local)' : 'Checking…'}
          </span>
        </div>
      </div>
    </header>
  )
}
