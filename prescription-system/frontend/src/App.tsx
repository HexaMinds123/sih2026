import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/common/AppShell'
import { WorkspaceProvider } from './hooks/useWorkspace'
import { DashboardPage } from './pages/DashboardPage'
import { PatientPage } from './pages/PatientPage'
import { PrescriptionPage } from './pages/PrescriptionPage'
import { OrchestratorPage } from './pages/OrchestratorPage'
import { VitalsPage } from './pages/VitalsPage'
import { AlertsPage } from './pages/AlertsPage'
import { AgentsPage } from './pages/AgentsPage'
import { SystemPage } from './pages/SystemPage'
import './styles.css'
import './dashboard.css'

export default function App() {
  return (
    <WorkspaceProvider>
      <AppShell>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/patient" element={<PatientPage />} />
          <Route path="/prescription" element={<PrescriptionPage />} />
          <Route path="/orchestrator" element={<OrchestratorPage />} />
          <Route path="/vitals" element={<VitalsPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/system" element={<SystemPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
    </WorkspaceProvider>
  )
}
