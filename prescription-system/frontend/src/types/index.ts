// ── Core prescription types (preserve existing contract) ──────────────────────

export type AnalysisStatus =
  | 'INFORMATIONAL'
  | 'REVIEW_REQUIRED'
  | 'CRITICAL_REVIEW_REQUIRED'
  | 'INSUFFICIENT_INFORMATION'

export type { AnalysisStatus as Status }

export interface Patient {
  name: string | null
  age: number | null
  gender: string | null
}

export interface Medication {
  name: string
  strength: string | null
  dose: string | null
  frequency: string | null
  route: string | null
  duration: string | null
  instructions: string | null
}

export interface Extraction {
  prescription_id: string
  ocr: {
    raw_text: string
    ocr_confidence: number | null
    warnings: string[]
    human_verification_required: boolean
  }
  prescription: {
    patient: Patient
    prescription_date: string | null
    condition: string | null
    medications: Medication[]
    uncertain_medications: { text: string; reason: string }[]
    warnings: { text: string; reason: string }[]
  }
  human_verification_required: boolean
}

export interface Evidence {
  text: string | null
  source: string | null
  document_id: string | null
  section: string | null
  page: number | null
  version: number | string | null
  jurisdiction: string | null
  publication_date: string | null
  source_url: string | null
  retrieval_similarity_score: number | null
}

export interface MedicationAnalysis {
  medication: string | null
  condition: string | null
  dosage: string | null
  evidence_status: string
  evidence: Evidence[]
}

export interface Analysis {
  prescription_id: string
  status: AnalysisStatus
  human_review_required: boolean
  medications: MedicationAnalysis[]
  drug_interactions: {
    interaction_found?: boolean
    drugs?: string[]
    interactions?: { drugs?: string[]; severity?: string; warning?: string }[]
    note?: string
  }
  issues: string[]
  audit: { tools_called: { tool: string; arguments: Record<string, unknown>; result_received: boolean }[] }
}

// ── EHR / Patient types ────────────────────────────────────────────────────────

export interface EHRPatient {
  patient_id: string
  name: string
  age: number
  gender: string
  allergies: string[]
  conditions: string[]
  bloodType?: string
  emergencyContact?: { name: string; phone: string; relation: string }
}

export interface VitalReading {
  timestamp: string
  heart_rate: number | null
  spo2: number | null
  systolic_bp: number | null
  diastolic_bp: number | null
  temperature: number | null
  glucose: number | null
}

export type VitalStatus = 'NORMAL' | 'WARNING' | 'CRITICAL'

// ── Agent / Orchestrator types ─────────────────────────────────────────────────

export type AgentState = 'ONLINE' | 'BUSY' | 'DEGRADED' | 'OFFLINE'

export interface AgentStatus {
  id: string
  name: string
  role: string
  state: AgentState
  lastActivity: string
  tools: string[]
  recentCalls: number
  description: string
}

export interface AgentEvent {
  id: string
  timestamp: string
  agent: string
  event: string
  detail: string
  status: 'ok' | 'warn' | 'error' | 'info'
}

export interface OrchestrationResult {
  orchestration_id: string
  patient_id: string
  risk_level: 'NORMAL' | 'MODERATE' | 'HIGH' | 'CRITICAL'
  status: string
  approved: false
  human_review_required: true
  events: AgentEvent[]
  final_message: string
  timestamp: string
}

// ── MCP types ─────────────────────────────────────────────────────────────────

export interface MCPTool {
  name: string
  description: string
  lastCalled?: string
  callCount: number
  errorCount: number
  avgLatencyMs?: number
}

export interface MCPServer {
  id: string
  name: string
  transport: 'stdio' | 'http' | 'ws'
  status: 'connected' | 'degraded' | 'disconnected'
  tools: MCPTool[]
  lastError?: string
  uptime?: string
}

// ── Alert types ────────────────────────────────────────────────────────────────

export type AlertSeverity = 'CRITICAL' | 'HIGH' | 'MODERATE' | 'INFO'
export type AlertCategory = 'VITALS' | 'DRUG_INTERACTION' | 'PRESCRIPTION_REVIEW' | 'MISSING_INFORMATION' | 'SYSTEM'

export interface Alert {
  id: string
  severity: AlertSeverity
  category: AlertCategory
  title: string
  detail: string
  patient_id: string
  patient_name: string
  timestamp: string
  status: 'PENDING_CONFIRMATION' | 'CONFIRMED' | 'REJECTED' | 'RESOLVED'
  event_id?: string
  escalation_chain: {
    step: string
    actor: string
    timestamp: string
    status: 'done' | 'pending' | 'skipped'
  }[]
}
