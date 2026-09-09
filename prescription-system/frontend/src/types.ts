export type Status =
  | 'INFORMATIONAL'
  | 'REVIEW_REQUIRED'
  | 'CRITICAL_REVIEW_REQUIRED'
  | 'INSUFFICIENT_INFORMATION'

type Patient = {
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
    patient: Patient
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
  status: Status
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
