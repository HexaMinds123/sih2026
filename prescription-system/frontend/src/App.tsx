import { useState, useEffect } from 'react'
import { Sidebar, type Page } from './layout/Sidebar'
import { Topbar } from './layout/Topbar'
import { DashboardPage } from './components/Dashboard/DashboardPage'
import { PatientPage } from './components/Patient/PatientPage'
import { PrescriptionPage } from './components/Prescription/PrescriptionPage'
import { OrchestratorPage } from './components/Orchestrator/OrchestratorPage'
import { VitalsPage } from './components/Vitals/VitalsPage'
import { AlertsPage } from './components/Alerts/AlertsPage'
import { AgentsPage } from './components/Agents/AgentsPage'
import { MCPPage } from './components/MCP/MCPPage'
import { checkHealth } from './services/api'
import { MOCK_ALERTS } from './mock/alerts'
import './styles.css'

const VALID_PAGES: Page[] = [
  'dashboard',
  'patient',
  'prescription',
  'orchestrator',
  'vitals',
  'alerts',
  'agents',
  'mcp',
]

function getInitialPage(): Page {
  const hash = window.location.hash.replace('#', '').toLowerCase() as Page
  if (VALID_PAGES.includes(hash)) {
    return hash
  }
  return 'dashboard'
}

export default function App() {
  const [currentPage, setCurrentPage] = useState<Page>(getInitialPage)
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)

  useEffect(() => {
    checkHealth().then(setBackendOnline)
    const interval = setInterval(() => {
      checkHealth().then(setBackendOnline)
    }, 15000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '').toLowerCase() as Page
      if (VALID_PAGES.includes(hash)) {
        setCurrentPage(hash)
      }
    }
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  const navigateTo = (page: Page) => {
    setCurrentPage(page)
    window.location.hash = page
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const activeAlertsCount = MOCK_ALERTS.filter(a => a.status === 'PENDING_CONFIRMATION').length

  const renderCurrentPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <DashboardPage onNavigate={navigateTo} />
      case 'patient':
        return <PatientPage />
      case 'prescription':
        return <PrescriptionPage />
      case 'orchestrator':
        return <OrchestratorPage />
      case 'vitals':
        return <VitalsPage />
      case 'alerts':
        return <AlertsPage />
      case 'agents':
        return <AgentsPage />
      case 'mcp':
        return <MCPPage />
      default:
        return <DashboardPage onNavigate={navigateTo} />
    }
  }

  return (
    <div className="health-app-container">
      <Sidebar
        current={currentPage}
        onChange={navigateTo}
        backendOnline={backendOnline ?? false}
        alertCount={activeAlertsCount}
      />
      <div className="main-viewport">
        <Topbar
          currentPage={currentPage}
          backendOnline={backendOnline}
          alertCount={activeAlertsCount}
          onNavigate={navigateTo}
        />
        <main className="dashboard-content-area">
          {renderCurrentPage()}
        </main>
        <footer className="dashboard-footer">
          <div className="footer-left">
            <span>SIH 2026 HealthEase Healthcare AI System</span>
            <span className="footer-sep">·</span>
            <span>Central Orchestration & Multi-MCP Architecture</span>
          </div>
          <div className="footer-right">
            <span className="footer-safety-badge">Safety Invariant Enforced: Human Clinician Gate Required</span>
          </div>
        </footer>
      </div>
    </div>
  )
}
