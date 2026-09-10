import {
  Activity, AlertTriangle, Bot, Cpu, FileText,
  Heart, LayoutDashboard, Server, User, ChevronRight, Cross
} from 'lucide-react'

export type Page =
  | 'dashboard'
  | 'patient'
  | 'prescription'
  | 'orchestrator'
  | 'vitals'
  | 'alerts'
  | 'agents'
  | 'mcp'

interface NavItem {
  id: Page
  label: string
  icon: React.ReactNode
  group: string
}

const NAV: NavItem[] = [
  { id: 'dashboard',    label: 'Dashboard',         icon: <LayoutDashboard size={17} />, group: 'Overview' },
  { id: 'patient',      label: 'Patient / EHR',      icon: <User size={17} />,            group: 'Overview' },
  { id: 'prescription', label: 'Prescription',       icon: <FileText size={17} />,        group: 'Clinical' },
  { id: 'orchestrator', label: 'AI Orchestrator',    icon: <Cpu size={17} />,             group: 'Clinical' },
  { id: 'vitals',       label: 'Live Vitals',        icon: <Heart size={17} />,           group: 'Monitoring' },
  { id: 'alerts',       label: 'Alerts & Escalation',icon: <AlertTriangle size={17} />,   group: 'Monitoring' },
  { id: 'agents',       label: 'Agent Monitoring',   icon: <Bot size={17} />,             group: 'System' },
  { id: 'mcp',          label: 'MCP Servers',        icon: <Server size={17} />,          group: 'System' },
]

const GROUPS = ['Overview', 'Clinical', 'Monitoring', 'System']

interface Props {
  current: Page
  onChange: (p: Page) => void
  backendOnline: boolean
  alertCount: number
}

export function Sidebar({ current, onChange, backendOnline, alertCount }: Props) {
  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="sidebar-brand">
        <div className="brand-icon"><Cross size={18} /></div>
        <div>
          <span className="brand-sub">SIH 2026</span>
          <strong className="brand-name">HealthEase</strong>
        </div>
      </div>

      {/* Backend status */}
      <div className={`api-status ${backendOnline ? 'online' : 'offline'}`}>
        <span className="api-dot" />
        {backendOnline ? 'Backend online' : 'Backend offline'}
      </div>

      {/* Nav groups */}
      {GROUPS.map((group) => (
        <div key={group} className="nav-group">
          <p className="nav-group-label">{group}</p>
          {NAV.filter((n) => n.group === group).map((item) => (
            <button
              key={item.id}
              className={`nav-item ${current === item.id ? 'nav-active' : ''}`}
              onClick={() => onChange(item.id)}
            >
              {item.icon}
              <span>{item.label}</span>
              {item.id === 'alerts' && alertCount > 0 && (
                <span className="nav-badge">{alertCount}</span>
              )}
              {current === item.id && <ChevronRight size={14} className="nav-chevron" />}
            </button>
          ))}
        </div>
      ))}

      <div className="sidebar-footer">
        <Activity size={13} />
        <span>Multi-agent healthcare AI</span>
      </div>
    </aside>
  )
}
