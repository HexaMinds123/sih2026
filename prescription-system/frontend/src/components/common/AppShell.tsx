import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import {
  Activity,
  Bell,
  Brain,
  Database,
  HeartPulse,
  LayoutDashboard,
  Moon,
  Pill,
  Server,
  Sun,
  Users,
  Workflow,
} from 'lucide-react'
import { useWorkspace } from '../../hooks/useWorkspace'

const links = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/patient', label: 'Patient / EHR', icon: Users },
  { to: '/prescription', label: 'Prescription Analysis', icon: Pill },
  { to: '/orchestrator', label: 'AI Orchestrator', icon: Workflow },
  { to: '/vitals', label: 'Live Vitals', icon: HeartPulse },
  { to: '/alerts', label: 'Alerts & Escalation', icon: Bell },
  { to: '/agents', label: 'Agent Monitoring', icon: Brain },
  { to: '/system', label: 'System / MCP', icon: Server },
]

export function AppShell({ children }: { children: ReactNode }) {
  const { theme, setTheme, backend, patient, patients, setPatientId } = useWorkspace()

  return (
    <div className="app-shell dash-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon"><Activity size={20} /></div>
          <div>
            <span>SIH 2026</span>
            <strong>HealthEase</strong>
          </div>
        </div>
        <nav className="side-nav">
          {links.map((link) => {
            const Icon = link.icon
            return (
              <NavLink key={link.to} to={link.to} end={link.to === '/'} className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
                <Icon size={17} />
                {link.label}
              </NavLink>
            )
          })}
        </nav>
        <div className="sidebar-foot">
          <p className="eyebrow">Architecture</p>
          <p className="muted compact">Orchestrator reasons. Medical Agent analyzes. MCPs retrieve. Frontend never runs RAG.</p>
        </div>
      </aside>
      <div className="main-column">
        <header className="dash-topbar">
          <div className="patient-picker">
            <Users size={16} />
            <label>
              Context patient
              <select value={patient.patient_id} onChange={(event) => setPatientId(event.target.value)}>
                {patients.map((item) => (
                  <option key={item.patient_id} value={item.patient_id}>
                    {item.patient_id} · {item.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="topbar-actions">
            <div className={`connection-state ${backend.status}`}>
              <span className="pulse" />
              {backend.status === 'ok' ? 'Prescription API ready' : backend.status === 'checking' ? 'Checking API…' : 'Prescription API offline'}
            </div>
            <button
              className="theme-toggle"
              type="button"
              onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
              aria-label="Toggle color theme"
            >
              {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
            </button>
          </div>
        </header>
        <div className="workspace">{children}</div>
      </div>
    </div>
  )
}
