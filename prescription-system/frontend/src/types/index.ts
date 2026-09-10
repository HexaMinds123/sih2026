export type DataSourceKind = 'live' | 'demo'

export type AnalysisStatus =
  | 'INFORMATIONAL'
  | 'REVIEW_REQUIRED'
  | 'CRITICAL_REVIEW_REQUIRED'
  | 'INSUFFICIENT_INFORMATION'

export type VitalLevel = 'NORMAL' | 'WARNING' | 'CRITICAL'

export type PatientRecord = {
  name: string | null
  age: number | null
  gender: string | null
}

export type Medication = {
  name: string
  strength: string | null
  dose: string | null
  frequency: string | null
  route: string | null
  duration: string | null
  instructions: string | null
}

export type Extraction = {
  prescription_id: string
  ocr: {
    raw_text: string
    ocr_confidence: number | null
    warnings: string[]
    human_verification_required: boolean
  }
  prescription: {
    patient: PatientRecord
    prescription_date: string | null
    condition: string | null
    medications: Medication[]
    uncertain_medications: { text: string; reason: string }[]
    warnings: { text: string; reason: string }[]
  }
  human_verification_required: boolean
}

export type Evidence = {
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

export type MedicationAnalysis = {
  medication: string | null
  condition: string | null
  dosage: string | null
  evidence_status: string
  evidence: Evidence[]
}

export type Analysis = {
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

export type AnalysisResponse = Analysis

export type Prescription = Extraction['prescription'] & {
  prescription_id?: string
}

export type Allergy = {
  name: string
  severity: string
}

export type Condition = {
  name: string
  onset: string | null
  status: string
}

export type EhrMedication = {
  drug: string
  dosage: string
  frequency: string
  prescribed_date: string | null
  active: boolean
}

export type TimelineEvent = {
  at: string
  title: string
  detail: string
}

export type Patient = {
  patient_id: string
  name: string
  age: number
  gender: string
  allergies: Allergy[]
  conditions: Condition[]
  medications: EhrMedication[]
  emergency_contact: { name: string; phone: string; relation: string }
  medical_history: TimelineEvent[]
  ehr_retrieval: {
    status: 'idle' | 'retrieved' | 'unavailable'
    last_query: string
    latency_ms: number | null
    note: string
  }
}

export type Vital = {
  id: string
  label: string
  key: 'heart_rate' | 'spo2' | 'blood_pressure' | 'temperature' | 'glucose' | 'activity'
  value: number | string
  unit: string
  level: VitalLevel
  reference: string
  updated_at: string
}

export type AlertKind =
  | 'CRITICAL_VITALS'
  | 'DRUG_INTERACTION'
  | 'HUMAN_REVIEW'
  | 'MISSING_INFORMATION'
  | 'ESCALATION'

export type Alert = {
  id: string
  kind: AlertKind
  severity: 'CRITICAL' | 'HIGH' | 'MODERATE'
  title: string
  message: string
  patient_id: string
  created_at: string
  escalation_status: string
  chain: { stage: string; actor: string; detail: string }[]
  source: DataSourceKind
}

export type Notification = {
  id: string
  event_id: string
  patient_id: string
  event_type: string
  risk_level: string
  status: string
  message: string
  created_at: string
  confirmed_by: string | null
  source: DataSourceKind
}

export type AgentKind =
  | 'orchestrator'
  | 'medical_agent'
  | 'ehr_agent'
  | 'notification_agent'
  | 'clinical_mcp'
  | 'ehr_mcp'
  | 'notification_mcp'

export type AgentStatus = {
  id: AgentKind
  name: string
  layer: 'reasoning' | 'specialized_agent' | 'mcp'
  status: 'online' | 'degraded' | 'demo' | 'unknown'
  last_activity: string
  responsibility: string
  tools: string[]
  recent_calls: AgentEvent[]
  source: DataSourceKind
}

export type AgentEvent = {
  id: string
  at: string
  agent: string
  action: string
  input_summary: string
  output_summary: string
  ok: boolean
}

export type MCPServer = {
  id: string
  name: string
  transport: string
  command: string
  cwd: string
  connected: boolean | null
  tools: { name: string; description: string }[]
  recent_calls: AgentEvent[]
  errors: string[]
  latency_ms: number | null
  source: DataSourceKind
}

export type OrchestrationStep = {
  id: string
  at: string
  title: string
  actor: string
  input: string
  output: string
  status: 'complete' | 'running' | 'pending' | 'skipped'
}

export type OrchestrationResult = {
  scenario: string
  patient_id: string
  started_at: string
  finished_at: string | null
  orchestrator_status: string
  risk_level: string
  status: string
  approved: boolean
  human_review_required: boolean
  requires_human_confirmation: boolean
  event_id: string | null
  steps: OrchestrationStep[]
  agent_inputs: Record<string, string>
  agent_outputs: Record<string, string>
  final_result: string
  source: DataSourceKind
  note: string
}

export type McpCheckResponse = {
  prescription_id: string
  mcp: {
    connected: boolean
    available_tools?: string[]
    drug_interactions?: Record<string, unknown>
    guideline_evidence?: unknown[]
    error?: string
    human_review_required?: boolean
  }
}

export type UploadResult = {
  prescription_id: string
  filename: string
  status: string
}
