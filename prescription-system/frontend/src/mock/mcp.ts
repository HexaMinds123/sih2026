import type { MCPServer } from '../types/index'

// DEMO DATA — MCP server registry
export const MOCK_MCP_SERVERS: MCPServer[] = [
  {
    id: 'clinical-mcp',
    name: 'Clinical MCP',
    transport: 'stdio',
    status: 'connected',
    uptime: '14h 22m',
    tools: [
      { name: 'query_drug_interactions', description: 'Check drug-drug interaction severity for a medication list', callCount: 18, errorCount: 0, avgLatencyMs: 320 },
      { name: 'search_prescription_guidance', description: 'RAG retrieval of prescription evidence by medication/condition/dosage', callCount: 34, errorCount: 1, avgLatencyMs: 580, lastCalled: '4 min ago' },
      { name: 'search_clinical_guidance', description: 'Retrieve clinical guidelines for anomaly codes (e.g. LOW_SPO2)', callCount: 12, errorCount: 0, avgLatencyMs: 410 },
    ],
  },
  {
    id: 'ehr-mcp',
    name: 'EHR MCP',
    transport: 'stdio',
    status: 'connected',
    uptime: '14h 22m',
    tools: [
      { name: 'patient_profile', description: 'Demographics, conditions, allergies (public resource, no auth)', callCount: 22, errorCount: 0, avgLatencyMs: 45 },
      { name: 'fetch_active_prescriptions', description: 'Active prescriptions — requires API token', callCount: 14, errorCount: 0, avgLatencyMs: 62 },
      { name: 'get_allergies', description: 'Documented allergies — requires API token', callCount: 14, errorCount: 0, avgLatencyMs: 38 },
      { name: 'get_emergency_contact', description: 'Emergency contact — requires API token', callCount: 7, errorCount: 0, avgLatencyMs: 40 },
      { name: 'semantic_patient_search', description: 'MongoDB RAG semantic search over patient records', callCount: 3, errorCount: 2, avgLatencyMs: 1240, lastCalled: '1h ago' },
    ],
  },
  {
    id: 'notification-mcp',
    name: 'Notification MCP',
    transport: 'stdio',
    status: 'connected',
    uptime: '14h 22m',
    tools: [
      { name: 'log_audit_trail', description: 'Record clinical event in tamper-evident SQLite audit log', callCount: 5, errorCount: 0, avgLatencyMs: 28 },
      { name: 'confirm_escalation', description: 'Mint single-use doctor confirmation token (human gate)', callCount: 2, errorCount: 0, avgLatencyMs: 35 },
      { name: 'reject_escalation', description: 'Record clinician rejection with reason', callCount: 1, errorCount: 0, avgLatencyMs: 30 },
      { name: 'trigger_emergency_sms', description: 'Dispatch SMS — requires valid confirmation token', callCount: 2, errorCount: 0, avgLatencyMs: 145 },
      { name: 'get_audit_trail', description: 'Retrieve full audit event by event_id', callCount: 4, errorCount: 0, avgLatencyMs: 22 },
    ],
  },
]
