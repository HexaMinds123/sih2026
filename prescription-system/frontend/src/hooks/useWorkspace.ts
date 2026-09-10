import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { getDemoPatient, listDemoPatients } from '../mock/adapter'
import { healthCheck } from '../services/api'
import type { Analysis, Extraction, Patient, UploadResult } from '../types/index'

type Theme = 'light' | 'dark'

type WorkspaceValue = {
  theme: Theme
  setTheme: (theme: Theme) => void
  patientId: string
  setPatientId: (id: string) => void
  patient: Patient
  patients: Patient[]
  backend: { status: 'checking' | 'ok' | 'down'; message: string }
  lastUpload: UploadResult | null
  lastExtraction: Extraction | null
  lastAnalysis: Analysis | null
  recordUpload: (upload: UploadResult) => void
  recordExtraction: (extraction: Extraction) => void
  recordAnalysis: (analysis: Analysis) => void
}

const WorkspaceContext = createContext<WorkspaceValue | null>(null)

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => (localStorage.getItem('healthease-theme') as Theme) || 'light')
  const [patientId, setPatientId] = useState('P001')
  const [backend, setBackend] = useState<WorkspaceValue['backend']>({ status: 'checking', message: 'Checking FastAPI /health' })
  const [lastUpload, setLastUpload] = useState<UploadResult | null>(null)
  const [lastExtraction, setLastExtraction] = useState<Extraction | null>(null)
  const [lastAnalysis, setLastAnalysis] = useState<Analysis | null>(null)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('healthease-theme', theme)
  }, [theme])

  useEffect(() => {
    let cancelled = false
    healthCheck()
      .then((payload) => {
        if (!cancelled) setBackend({ status: 'ok', message: `FastAPI /health: ${payload.status}` })
      })
      .catch(() => {
        if (!cancelled) setBackend({ status: 'down', message: 'FastAPI /health unreachable (start uvicorn on :8000)' })
      })
    return () => {
      cancelled = true
    }
  }, [])

  const patients = useMemo(() => listDemoPatients(), [])
  const patient = useMemo(() => getDemoPatient(patientId), [patientId])

  const value: WorkspaceValue = {
    theme,
    setTheme: setThemeState,
    patientId,
    setPatientId,
    patient,
    patients,
    backend,
    lastUpload,
    lastExtraction,
    lastAnalysis,
    recordUpload: setLastUpload,
    recordExtraction: (extraction) => {
      setLastExtraction(extraction)
      setLastAnalysis(null)
    },
    recordAnalysis: setLastAnalysis,
  }

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

export function useWorkspace() {
  const context = useContext(WorkspaceContext)
  if (!context) throw new Error('useWorkspace must be used within WorkspaceProvider')
  return context
}
